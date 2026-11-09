"""Covered Call Hedging (Dhan investment portfolio) - signals + live option tracker.

Rules (user, 2026-11-08):
  * Universe = the investment-portfolio stocks that have listed options (data/cc_config.json).
  * RSI(14) overrides the colour: RSI > 70 -> sell the call (0.10 delta); RSI < 30 -> bull put spread.
  * Otherwise Supertrend GREEN -> bull put spread: sell the put nearest 0.15 delta, buy the put 2 listed strikes
    lower (no flip-age window for options - any green stock without a put spread is a signal).
  * Supertrend RED   -> sell the call nearest 0.10 delta only (no put spread).
  * Expiry: the current month; after the 15th the next month is shown as well.
  * 1 lot per signal (flagged when the shares held do not cover the lot). Lot sizes: NSE's official F&O lot file
    (data/nse_lots.json, per expiry month, from update_lot_sizes.py); cc_config.json is the fallback.
  * Averaging (the shares themselves): Supertrend green AND loss on the holding <= -6% -> buy 1/10 of the open
    quantity (min 1 share, same rounding as dh252), at most once every 7 days (data/cc_adds.json holds the last add date).
  * Exits: (1) short option price >= 3x its sold premium  -> EXIT
           (2) stock touches the short strike              -> WARN
           (3) end-of-day Supertrend colour change vs the colour at entry -> FLIP (close the structure,
               open the opposite). Needs an entry colour, so it only fires for stocks tagged in data/cc_tags.json.

Inputs are the RAW text the Dhan MCP returns (the refresh-dhan skill saves them verbatim, nothing is retyped):
  data/cc_raw/positions.txt                      portfolio_agent_tool "positions"
  data/cc_raw/chains/<SYMBOL>_<YYYY-MM-DD>.txt   market_data_agent_tool "optionchain" (only for stocks with a signal)
plus holdings_snapshot.json and backtester's supertrend_full.json. Deltas are not provided by Dhan; they are
computed here (Black-Scholes from the chain's IV, r from the config, no dividends), so treat them as estimates.

Usage: python scripts/compute_covered_call.py --supertrend <supertrend_full.json> [--out covered_call_signals.json]
"""

import argparse
import json
import math
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def num(s):
    return float(s.replace(",", ""))


# ---------- parsers for the raw MCP text ----------
POS_HEAD = re.compile(r"^([A-Z0-9&]+)-([A-Za-z]{3})(\d{4})-([\d.]+)-(CE|PE) \[(\w+)\] (LONG|SHORT)")


def parse_positions(text, expiries):
    by_ym = {e[:7]: e for e in expiries}
    legs, cur = [], None
    for line in text.splitlines():
        m = POS_HEAD.match(line.strip())
        if m:
            sym, mon, yr, strike, typ, _, side = m.groups()
            ym = f"{yr}-{MONTHS[mon]:02d}"
            cur = {"symbol": sym, "expiry": by_ym.get(ym, ym), "strike": float(strike), "type": typ, "side": side}
            legs.append(cur)
        elif cur and line.strip().startswith("Net:"):
            cur["qty"] = abs(int(re.search(r"Net:\s*(-?\d+)", line).group(1)))
            b = re.search(r"Buy\s+(\d+)\s*@\s*₹([\d,.]+)", line); s = re.search(r"Sell\s+(\d+)\s*@\s*₹([\d,.]+)", line)
            cur["buy_avg"] = num(b.group(2)) if b else 0.0
            cur["sell_avg"] = num(s.group(2)) if s else 0.0
        elif cur and line.strip().startswith("P&L:"):
            p = re.search(r"([▲▼])\s*₹([\d,.]+)", line)
            cur["pnl_rs"] = (1 if p.group(1) == "▲" else -1) * num(p.group(2))
    return [l for l in legs if "qty" in l and "pnl_rs" in l]


def parse_chain(text):
    spot = re.search(r"underlying LTP ₹([\d,.]+)", text)
    rows = []
    for line in text.splitlines():
        m = re.match(r"\s*([\d.]+)\s*\|\s*([\d.]+)\s+(\d+)\s+([\d.]+)\s*\|\s*([\d.]+)\s+(\d+)\s+([\d.]+)", line)
        if m:
            k, cl, co, ci, pl, po, pi = m.groups()
            rows.append({"strike": float(k), "ce_ltp": float(cl), "ce_oi": int(co), "ce_iv": float(ci),
                         "pe_ltp": float(pl), "pe_oi": int(po), "pe_iv": float(pi)})
    return {"spot": num(spot.group(1)) if spot else None, "rows": rows}


# ---------- math ----------
def norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bs_delta(kind, spot, strike, iv_pct, days, r):
    if iv_pct <= 0 or spot <= 0 or strike <= 0:
        return None
    t, v = max(days, 1) / 365.0, iv_pct / 100.0
    d1 = (math.log(spot / strike) + (r + v * v / 2) * t) / (v * math.sqrt(t))
    return norm_cdf(d1) if kind == "CE" else norm_cdf(d1) - 1


def listed(row):  # placeholder strikes in the chain have no price and no OI
    return row["ce_ltp"] > 0 or row["pe_ltp"] > 0 or row["ce_oi"] > 0 or row["pe_oi"] > 0


# ---------- suggestions ----------
def suggest(kind, chain, expiry, today, rules, lot, spot):
    """kind 'PUT_SPREAD' or 'CALL'. Returns a dict (or {'missing_chain': True})."""
    if not chain or not chain["rows"]:
        return {"expiry": expiry, "structure": kind, "missing_chain": True}
    spot = spot or chain["spot"]
    days = (date.fromisoformat(expiry) - today).days
    r = rules["risk_free_rate"]
    rows = sorted([x for x in chain["rows"] if listed(x)], key=lambda x: x["strike"])
    out = {"expiry": expiry, "days": days, "structure": kind, "expiry_week": days <= rules["expiry_week_days"]}
    if kind == "CALL":
        target, side, ltp_k, iv_k = rules["short_call_delta"], "CE", "ce_ltp", "ce_iv"
        cand = [x for x in rows if x["strike"] > spot and x[ltp_k] > 0 and x[iv_k] > 0]
    else:
        target, side, ltp_k, iv_k = rules["short_put_delta"], "PE", "pe_ltp", "pe_iv"
        cand = [x for x in rows if x["strike"] < spot and x[ltp_k] > 0 and x[iv_k] > 0]
    best = None
    for x in cand:
        d = bs_delta(side, spot, x["strike"], x[iv_k], days, r)
        if d is not None and (best is None or abs(abs(d) - target) < abs(abs(best[1]) - target)):
            best = (x, d)
    if not best:
        out["no_strike"] = True
        return out
    x, d = best
    out["short"] = {"type": side, "strike": x["strike"], "ltp": x[ltp_k], "iv": x[iv_k], "delta": round(d, 3), "oi": x[side.lower() + "_oi"]}
    out["stop_premium"] = round(rules["stop_premium_multiple"] * x[ltp_k], 2)
    if kind == "CALL":
        out["credit"] = x[ltp_k]
        out["credit_rs"] = round(x[ltp_k] * lot, 2) if lot else None
        out["strike_distance_pct"] = round((x["strike"] / spot - 1) * 100, 2)
        return out
    below = [y for y in rows if y["strike"] < x["strike"]]
    n = rules["hedge_strikes_below"]
    out["strike_distance_pct"] = round((x["strike"] / spot - 1) * 100, 2)
    if len(below) < n:
        out["no_hedge"] = True
        return out
    h = below[-n]
    out["hedge"] = {"type": "PE", "strike": h["strike"], "ltp": h["pe_ltp"], "iv": h["pe_iv"]}
    credit = round(x[ltp_k] - h["pe_ltp"], 2)
    out["credit"] = credit
    out["width"] = round(x["strike"] - h["strike"], 2)
    if lot:
        out["credit_rs"] = round(credit * lot, 2)
        out["max_loss_rs"] = round((out["width"] - credit) * lot, 2)
    return out


def lot_for(sym, expiry, lots, uni):
    """Lot size for the symbol in the expiry's month: NSE file first, then cc_config.json."""
    by_month = lots.get(sym, {})
    if expiry and expiry[:7] in by_month:
        return by_month[expiry[:7]]
    if by_month and not expiry:
        return by_month[sorted(by_month)[0]]
    return uni.get(sym, {}).get("lot")


# ---------- main ----------
def strike_zone(l, spot, near_pct):
    """How far the stock is from a leg's strike: beyond_pct > 0 = spot at/past the strike (in the money)."""
    ce = l["type"] == "CE"
    beyond = (spot / l["strike"] - 1) * 100 if ce else (1 - spot / l["strike"]) * 100
    intrinsic = max(0.0, (spot - l["strike"]) if ce else (l["strike"] - spot))
    l["beyond_pct"] = round(beyond, 2)
    l["intrinsic_rs"] = round(intrinsic * l["qty"])
    l["touched"] = beyond >= 0
    l["near"] = (not l["touched"]) and -beyond <= near_pct
    return beyond


def strike_alerts(sym, my_legs, spot, near_pct, stop_alerted):
    """Graded alerts for the stock price against the open legs (spot = the last close in the signals).
    EXIT   = price is through the hedge leg too (the spread is at its maximum loss)
    BREACH = price has reached or passed a short strike
    WARN   = price is within near_pct of a short strike"""
    out = []
    for l in my_legs:
        d = {"expiry": l["expiry"], "strike": l["strike"], "opt_type": l["type"], "qty": l["qty"], "spot": spot,
             "beyond_pct": l["beyond_pct"], "intrinsic_rs": l["intrinsic_rs"]}
        if l["side"] == "SHORT" and l["touched"]:
            hedges = [h for h in my_legs if h["side"] == "LONG" and h["type"] == l["type"] and h["expiry"] == l["expiry"]
                      and ((h["type"] == "CE" and h["strike"] > l["strike"]) or (h["type"] == "PE" and h["strike"] < l["strike"]))]
            thru = [h for h in hedges if h["touched_h"]]
            base = (f"{sym} {l['expiry']}: price {spot:g} is {abs(l['beyond_pct']):.1f}% {'above' if l['type']=='CE' else 'below'} the short "
                    f"{l['strike']:g}{l['type']} (in the money, intrinsic Rs{l['intrinsic_rs']:,} on {l['qty']} qty)")
            if thru:
                out.append({**d, "level": "EXIT", "type": "Through hedge", "hedge_strike": thru[0]["strike"], "symbol": sym,
                            "concern": f"Price {abs(l['beyond_pct']):.1f}% past the short and through the {thru[0]['strike']:g} hedge: max loss, Rs{l['intrinsic_rs']:,} intrinsic", "action": "Close or roll now", "text": base + f"; it is also through the {thru[0]['strike']:g}{thru[0]['type']} hedge - the spread is at maximum loss, decide now"})
            else:
                out.append({**d, "level": "BREACH", "type": "Beyond strike", "symbol": sym,
                            "concern": f"In the money: price {abs(l['beyond_pct']):.1f}% past the strike, Rs{l['intrinsic_rs']:,} intrinsic", "action": "Roll, close or hold", "text": base + "; decide: roll, close, or hold"})
        elif l["side"] == "SHORT" and l["near"]:
            out.append({**d, "level": "WARN", "type": "Near strike", "symbol": sym,
                            "concern": f"Price {abs(l['beyond_pct']):.1f}% from the short strike", "action": "Watch; plan the roll", "text": f"{sym} {l['expiry']}: price {spot:g} is within {abs(l['beyond_pct']):.1f}% of the short {l['strike']:g}{l['type']}"})
    return out


def structure_alerts(sym, my_legs, shares_held, gtt_active):
    """Alerts about how the open legs are set up (not about price): a short leg without hedge, a short leg without a buy-back GTT."""
    out = []
    groups = {}
    for l in my_legs:
        groups.setdefault((l["type"], l["expiry"]), []).append(l)
    for (typ, exp), ls in groups.items():
        short_q = sum(l["qty"] for l in ls if l["side"] == "SHORT")
        if not short_q:
            continue
        long_q = sum(l["qty"] for l in ls if l["side"] == "LONG")
        cover = long_q + (shares_held if typ == "CE" else 0)
        if cover < short_q:
            strikes = "/".join(f"{l['strike']:g}" for l in ls if l["side"] == "SHORT")
            extra = f" + {shares_held} shares" if typ == "CE" and shares_held else ""
            out.append({"level": "WARN", "type": "No hedge" if cover == 0 else "Partly hedged", "symbol": sym, "expiry": exp, "strike": ls[0]["strike"], "opt_type": typ,
                        "concern": f"{short_q - cover} of {short_q} qty uncovered (hedge {long_q}{extra})", "action": "Buy a hedge" + (" or hold shares" if typ == "CE" else ""),
                        "text": f"{sym} {exp}: short {strikes}{typ} {short_q} qty, hedge {long_q} qty{extra} - {short_q - cover} qty uncovered"})
    if gtt_active is not None:
        for l in my_legs:
            if l["side"] == "SHORT" and l.get("tradingsymbol") and l["tradingsymbol"] not in gtt_active:
                out.append({"level": "WARN", "type": "No GTT placed", "symbol": sym, "expiry": l["expiry"], "strike": l["strike"], "opt_type": l["type"], "qty": l["qty"],
                            "concern": "No buy-back GTT on this short", "action": f"Place GTT at {l['stop_at']:g} (3x premium)",
                            "text": f"{sym} {l['expiry']} short {l['strike']:g}{l['type']}: no active buy-back GTT (3x premium stop = {l['stop_at']})"})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--supertrend", required=True)
    ap.add_argument("--holdings", default=str(DATA / "holdings_snapshot.json"))
    ap.add_argument("--config", default=str(DATA / "cc_config.json"))
    ap.add_argument("--tags", default=str(DATA / "cc_tags.json"))
    ap.add_argument("--positions", default=str(DATA / "cc_raw" / "positions.txt"))
    ap.add_argument("--market-screens", default=str(DATA / "cache" / "market_screens_full.json"), help="for RSI14")
    ap.add_argument("--lots", default=str(DATA / "nse_lots.json"))
    ap.add_argument("--adds", default=str(DATA / "cc_adds.json"))
    ap.add_argument("--invest-trades", default=str(DATA / "invest_trades.json"))
    ap.add_argument("--chains-dir", default=str(DATA / "cc_raw" / "chains"))
    ap.add_argument("--out", default=str(ROOT / "covered_call_signals.json"))
    ap.add_argument("--as-of", default=None, help="override 'today' (YYYY-MM-DD)")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text())
    rules, uni, expiries = cfg["rules"], cfg["universe"], cfg["expiries"]
    tags = json.loads(Path(args.tags).read_text()).get("tags", {}) if Path(args.tags).exists() else {}
    st = json.loads(Path(args.supertrend).read_text())
    st_by = {e["symbol"].replace(".NS", ""): e for e in st["entries"]}
    market_date = st.get("latest_market_date")
    today = date.fromisoformat(args.as_of or market_date or datetime.now(timezone.utc).date().isoformat())
    rsi_by = {}
    if Path(args.market_screens).exists():
        ms = json.loads(Path(args.market_screens).read_text())
        rsi_by = {r["symbol"].replace(".NS", ""): r["rsi14"] for r in ms.get("rsi_all", []) if r.get("rsi14") is not None}
    hold_rows = {h["symbol"]: h for h in json.loads(Path(args.holdings).read_text())["holdings"]}
    held = {k: v["qty"] for k, v in hold_rows.items()}
    lots = json.loads(Path(args.lots).read_text()).get("lots", {}) if Path(args.lots).exists() else {}
    last_add = json.loads(Path(args.adds).read_text()).get("last_add", {}) if Path(args.adds).exists() else {}
    # previous closed trade per stock (invest_trades.py): the next entry reinvests that trade's capital + profit
    inv_path = Path(args.invest_trades)
    prev_trade = {}
    if inv_path.exists():
        for t in sorted(json.loads(inv_path.read_text()).get("closed", []), key=lambda x: x["exit_date"]):
            prev_trade[t["symbol"]] = t

    legs = parse_positions(Path(args.positions).read_text(encoding="utf-8"), expiries) if Path(args.positions).exists() else []
    chains = {}
    for f in Path(args.chains_dir).glob("*_*.txt") if Path(args.chains_dir).exists() else []:
        sym, exp = f.stem.rsplit("_", 1)
        chains.setdefault(sym, {})[exp] = parse_chain(f.read_text(encoding="utf-8"))

    # expiries shown for new suggestions: current month, plus next month after the cut-off day
    future = sorted(e for e in expiries if date.fromisoformat(e) >= today)
    show_exp = future[:1] + (future[1:2] if today.day > rules["show_next_month_after_day"] else [])

    stocks, alerts, shares_rows, share_entries, share_exits = [], [], [], [], []
    mult = rules["stop_premium_multiple"]
    lp_file = DATA / "cc_live_prices.json"
    live = json.loads(lp_file.read_text(encoding="utf-8")) if lp_file.exists() else {}
    ist_today = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%Y-%m-%d")
    live_px = live.get("prices", {}) if str(live.get("fetched_at", ""))[:10] == ist_today else {}   # only same-day live prices count
    for sym, u in uni.items():
        e = st_by.get(sym)
        if not e:
            stocks.append({"symbol": sym, "status": "NO_DATA", "note": "not in the Supertrend universe file"})
            continue
        spot, colour = e["close"], e["color"]
        spot_now = live_px.get(sym, spot)   # live price when pulled today, else the last close (signals stay end-of-day)
        shares = held.get(sym, 0)
        lot = lot_for(sym, show_exp[0] if show_exp else None, lots, uni)
        # "last flip" = when the current colour began (the recent_flip_* fields are empty once the flip is older
        # than the screener's lookback, which left red stocks blank)
        flip_date = e.get("current_streak_start_date") or e.get("recent_flip_date")
        flip_days = e.get("current_streak_trading_days")
        if flip_days is None:
            flip_days = e.get("recent_flip_trading_days_ago")
        rsi = rsi_by.get(sym)
        my_legs = [l for l in legs if l["symbol"] == sym]
        for l in my_legs:
            if l["side"] == "SHORT":
                l["ltp"] = round(l["sell_avg"] - l["pnl_rs"] / l["qty"], 2)
                l["stop_at"] = round(mult * l["sell_avg"], 2)
                l["stop_hit"] = l["ltp"] >= l["stop_at"]
            else:
                l["ltp"] = round(l["buy_avg"] + l["pnl_rs"] / l["qty"], 2)
            strike_zone(l, spot_now, rules.get("near_strike_pct", 2))
            l["touched_h"] = l["touched"] if l["side"] == "LONG" else False
            l["dist_pct"] = round((l["strike"] / spot_now - 1) * 100, 2)
            leg_lot = lot_for(sym, l["expiry"], lots, uni)
            l["lot"] = leg_lot
            l["lots"] = round(l["qty"] / leg_lot, 2) if leg_lot else None
            if l["side"] == "SHORT" and l["stop_hit"]:
                alerts.append({"level": "EXIT", "type": "3× premium", "symbol": sym, "expiry": l["expiry"], "strike": l["strike"], "opt_type": l["type"],
                               "concern": f"Premium {l['ltp']:g} is {l['ltp'] / l['sell_avg']:.1f}x the {l['sell_avg']:g} sold", "action": "Close now (3x stop hit)",
                               "text": f"{sym} {l['expiry']} {l['strike']:g}{l['type']}: premium {l['ltp']} >= {mult}x sold {l['sell_avg']} - close it"})
            elif l["side"] == "SHORT" and l["ltp"] <= l["sell_avg"] * (1 - rules.get("profit_exit_decay_pct", 60) / 100):
                alerts.append({"level": "PROFIT", "type": "Profit Exit", "symbol": sym, "expiry": l["expiry"], "strike": l["strike"], "opt_type": l["type"],
                               "concern": f"Premium decayed {(1 - l['ltp'] / l['sell_avg']) * 100:.0f}% (sold {l['sell_avg']:g}, now {l['ltp']:g})", "action": "Book profit: buy back",
                               "text": f"{sym} {l['expiry']} {l['strike']:g}{l['type']}: premium decayed {(1 - l['ltp'] / l['sell_avg']) * 100:.0f}% (sold {l['sell_avg']:g}, now {l['ltp']:g}) - book the profit"})
        alerts.extend(a for a in strike_alerts(sym, my_legs, spot_now, rules.get("near_strike_pct", 2), None))
        alerts.extend(structure_alerts(sym, my_legs, held.get(sym, 0), None))   # ND: no GTT data, hedge check only

        def has_put_spread():
            sp = [l for l in my_legs if l["type"] == "PE" and l["side"] == "SHORT"]
            lp = [l for l in my_legs if l["type"] == "PE" and l["side"] == "LONG"]
            return any(s["expiry"] == b["expiry"] and b["strike"] < s["strike"] for s in sp for b in lp)

        has_call = any(l["type"] == "CE" and l["side"] == "SHORT" for l in my_legs)
        tag = tags.get(sym)
        flipped = bool(tag and tag.get("entry_colour") and tag["entry_colour"] != colour)
        if rsi is not None and rsi > rules["rsi_sell_call_above"]:
            desired, basis = "CALL", f"RSI {rsi:.1f} > {rules['rsi_sell_call_above']:g}"
        elif rsi is not None and rsi < rules["rsi_sell_put_below"]:
            desired, basis = "PUT_SPREAD", f"RSI {rsi:.1f} < {rules['rsi_sell_put_below']:g}"
        else:
            desired, basis = ("PUT_SPREAD" if colour == "green" else "CALL"), f"Supertrend {colour}"
        have = has_put_spread() if desired == "PUT_SPREAD" else has_call
        shorts = [l for l in my_legs if l["side"] == "SHORT"]
        col_rule = "PUT_SPREAD" if colour == "green" else "CALL"   # the Supertrend colour alone (the RSI override never triggers an Exit)
        opp_legs = [l for l in shorts if l["type"] == ("PE" if col_rule == "CALL" else "CE")]   # open legs of the structure the colour no longer wants
        opposite = bool(opp_legs)
        if opposite and not flipped:
            leg_txt = ", ".join(f"{l['strike']:g}{l['type']} {l['expiry']}" for l in opp_legs)
            opp_note = (f"Supertrend is {colour.upper()}: the open {'short put / put spread' if col_rule == 'CALL' else 'short call'} ({leg_txt}) is the opposite of the colour rule - close it and "
                        f"{'sell the call' if col_rule == 'CALL' else 'open the bull put spread'}.")
        def nearest(kind):
            c = [l for l in shorts if l["type"] == kind]
            if not c:
                return None
            l = min(c, key=lambda x: abs(x["dist_pct"]))
            return {"strike": l["strike"], "expiry": l["expiry"], "dist_pct": l["dist_pct"]}

        if flipped or opposite:
            status = "FLIP"
            note = opp_note if (opposite and not flipped) else (f"Supertrend turned {colour.upper()} since entry ({tag.get('entry_colour')}): close the "
                    f"{'put spread' if colour == 'red' else 'short call'} and open the "
                    f"{'short call' if colour == 'red' else 'bull put spread'}.")
            exit_concern = (f"Supertrend turned {colour.upper()} since entry" if flipped else f"Supertrend {colour.upper()} but the {'short put / put spread' if col_rule == 'CALL' else 'short call'} is still open")
            exit_action = "Close it and sell the call" if (col_rule == "CALL") else "Close it and open the bull put spread"
            leg_f = {"expiry": opp_legs[0]["expiry"], "strike": opp_legs[0]["strike"], "opt_type": opp_legs[0]["type"]} if opp_legs else {}
            if len(opp_legs) > 1:
                exit_concern += f" ({len(opp_legs)} legs)"
            alerts.append({**leg_f, "level": "EXIT", "type": "Exit", "symbol": sym, "concern": exit_concern, "action": exit_action, "text": f"{sym}: {note}"})
        elif have:
            status, note = "HOLD", f"Open structure matches the rule ({basis})."
        else:
            status = "ENTER"
            note = f"{basis} - no " + ("put spread" if desired == "PUT_SPREAD" else "short call") + " open"
        suggestions = []
        if status in ("ENTER", "FLIP"):
            for ex in show_exp:
                suggestions.append(suggest(desired, chains.get(sym, {}).get(ex), ex, today, rules, lot, spot))
            if status == "ENTER":
                alerts.append({"level": "ENTER", "type": "New trade", "symbol": sym, "flip_days": flip_days, "concern": f"{basis}{f', flipped {flip_days}d ago' if flip_days is not None else ''}, no {'put spread' if desired == 'PUT_SPREAD' else 'short call'} open", "action": "Open bull put spread" if desired == "PUT_SPREAD" else "Sell the call", "text": f"{sym}: {note} - {'bull put spread' if desired == 'PUT_SPREAD' else 'sell call'}"})
        # the shares themselves (Shares sub-tab)
        h = hold_rows.get(sym)
        if h and h.get("avg_cost"):
            pl_pct = (spot / h["avg_cost"] - 1) * 100
            la = last_add.get(sym)
            since = (today - date.fromisoformat(la)).days if la else None
            cool = rules["averaging_cooldown_days"]
            eligible = colour == "green" and pl_pct <= rules["averaging_loss_pct"]
            if not eligible:
                ast = "NO"
                anote = "Supertrend red" if colour != "green" else f"P&L {pl_pct:+.1f}% - needs a loss of {abs(rules['averaging_loss_pct']):g}% or more"
            elif since is not None and since < cool:
                ast, anote = "WAIT", f"added {since}d ago - once every {cool} days"
            else:
                ast, anote = "ADD", ("no earlier add recorded" if since is None else f"last add {since}d ago")
            add_qty = max(1, round(h["qty"] * rules["averaging_fraction"]))
            shares_rows.append({"symbol": sym, "spot": spot, "avg_cost": h["avg_cost"], "qty": h["qty"],
                                "invested": round(h["qty"] * h["avg_cost"], 2), "value": round(h["qty"] * spot, 2),
                                "pl_pct": round(pl_pct, 2), "pl_rs": round(h["qty"] * (spot - h["avg_cost"]), 2),
                                "colour": colour, "flip_date": flip_date, "flip_trading_days": flip_days, "rsi": rsi,
                                "avg_status": ast, "add_qty": add_qty,
                                "add_value_rs": round(add_qty * spot, 2), "last_add": la, "days_since_add": since,
                                "avg_note": anote})
            # share EXIT: Supertrend red AND the position is in profit -> sell the whole position
            if colour == "red" and pl_pct > 0:
                share_exits.append({"symbol": sym, "spot": spot, "qty": h["qty"], "avg_cost": h["avg_cost"],
                                    "invested": round(h["qty"] * h["avg_cost"], 2), "value": round(h["qty"] * spot, 2),
                                    "pl_pct": round(pl_pct, 2), "pl_rs": round(h["qty"] * (spot - h["avg_cost"]), 2),
                                    "colour": colour, "flip_date": flip_date, "flip_trading_days": flip_days, "rsi": rsi})
        # share ENTRY: a universe stock you do NOT hold whose Supertrend turned green within the window
        if held.get(sym, 0) == 0 and colour == "green" and flip_days is not None and flip_days <= rules["share_entry_window_trading_days"]:
            pt = prev_trade.get(sym)
            cap = round(pt["capital"] + pt["profit"], 2) if pt else None
            qty_buy = max(1, int(cap // spot)) if cap else None
            share_entries.append({"symbol": sym, "spot": spot, "colour": colour, "flip_date": flip_date,
                                  "flip_trading_days": flip_days, "rsi": rsi,
                                  "prev_capital": pt["capital"] if pt else None, "prev_profit": pt["profit"] if pt else None,
                                  "entry_capital": cap, "qty_to_buy": qty_buy,
                                  "sizing_note": (f"previous trade: capital {pt['capital']:,.0f} + profit {pt['profit']:,.0f}" if pt
                                                  else "no previous trade recorded for this stock - quantity must be set by you")})
        stocks.append({
            "symbol": sym, "spot": spot, "colour": colour, "flip_date": flip_date, "flip_trading_days": flip_days,
            "rsi": rsi, "basis": basis, "near_call": nearest("CE"), "near_put": nearest("PE"),
            "shares": shares, "lot": lot, "covered": (shares >= lot) if lot else None,
            "desired": desired, "status": status, "note": note,
            "tagged": bool(tag), "suggestions": suggestions, "legs": my_legs,
        })

    order = {"EXIT": 0, "BREACH": 1, "WARN": 2, "ENTER": 3}
    alerts.sort(key=lambda a: order.get(a["level"], 9))
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "market_data_date": market_date, "live_prices_at": live.get("fetched_at") if live_px else None, "as_of": today.isoformat(),
        "rules": rules, "show_expiries": show_exp, "stocks": stocks, "alerts": alerts,
        "shares": {"rows": shares_rows, "entries": share_entries, "exits": share_exits,
                   "exit_rule": "Supertrend red and the position is in profit: sell the whole position",
                   "entry_window": rules["share_entry_window_trading_days"]},
        "lots_source": "nse_lots.json" if lots else "cc_config.json (fallback)",
        "positions_fetched": Path(args.positions).exists(), "legs_count": len(legs),
        "chains_loaded": {s: sorted(v) for s, v in chains.items()},
        "other_positions": sorted({l["symbol"] for l in legs} - set(uni)),
        # option chains still to fetch (Dhan MCP optionchain) for stocks that have a signal
        "chains_needed": [{"symbol": s["symbol"], "security_id": uni[s["symbol"]]["security_id"], "expiry": g["expiry"]}
                          for s in stocks for g in s.get("suggestions", []) if g.get("missing_chain")],
    }
    Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False))
    n = lambda s: sum(1 for x in stocks if x.get("status") == s)
    n_add = sum(1 for a in shares_rows if a["avg_status"] == "ADD")
    n_ent = len(share_entries)
    print(f"shares: exits {len(share_exits)}, averaging due {n_add}, entry signals {n_ent} | {len(stocks)} stocks | ENTER {n('ENTER')} HOLD {n('HOLD')} WAIT {n('WAIT')} FLIP {n('FLIP')} | legs {len(legs)} | alerts {len(alerts)}")
    for a in alerts:
        print(f"  {a['level']:5} {a['text']}")
    if result["chains_needed"]:
        print("CHAINS NEEDED (Dhan MCP market_data optionchain; save raw text to data/cc_raw/chains/<SYMBOL>_<EXPIRY>.txt):")
        for c in result["chains_needed"]:
            print(f"  {c['symbol']} UnderlyingScrip={c['security_id']} Expiry={c['expiry']}")
    print("written", args.out)


if __name__ == "__main__":
    main()
