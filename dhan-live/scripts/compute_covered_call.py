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
from datetime import date, datetime, timezone
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

    legs = parse_positions(Path(args.positions).read_text(encoding="utf-8"), expiries) if Path(args.positions).exists() else []
    chains = {}
    for f in Path(args.chains_dir).glob("*_*.txt") if Path(args.chains_dir).exists() else []:
        sym, exp = f.stem.rsplit("_", 1)
        chains.setdefault(sym, {})[exp] = parse_chain(f.read_text(encoding="utf-8"))

    # expiries shown for new suggestions: current month, plus next month after the cut-off day
    future = sorted(e for e in expiries if date.fromisoformat(e) >= today)
    show_exp = future[:1] + (future[1:2] if today.day > rules["show_next_month_after_day"] else [])

    stocks, alerts, shares_rows = [], [], []
    mult = rules["stop_premium_multiple"]
    for sym, u in uni.items():
        e = st_by.get(sym)
        if not e:
            stocks.append({"symbol": sym, "status": "NO_DATA", "note": "not in the Supertrend universe file"})
            continue
        spot, colour = e["close"], e["color"]
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
                l["touched"] = spot >= l["strike"] if l["type"] == "CE" else spot <= l["strike"]
            else:
                l["ltp"] = round(l["buy_avg"] + l["pnl_rs"] / l["qty"], 2)
            l["dist_pct"] = round((l["strike"] / spot - 1) * 100, 2)
            leg_lot = lot_for(sym, l["expiry"], lots, uni)
            l["lot"] = leg_lot
            l["lots"] = round(l["qty"] / leg_lot, 2) if leg_lot else None
            if l["side"] == "SHORT" and l["stop_hit"]:
                alerts.append({"level": "EXIT", "symbol": sym, "text": f"{sym} {l['expiry']} {l['strike']:g}{l['type']}: premium {l['ltp']} >= {mult}x sold {l['sell_avg']} - close it"})
            elif l["side"] == "SHORT" and l["touched"]:
                alerts.append({"level": "WARN", "symbol": sym, "text": f"{sym} spot {spot:g} has reached the short {l['strike']:g}{l['type']} ({l['expiry']})"})

        def has_put_spread():
            sp = [l for l in my_legs if l["type"] == "PE" and l["side"] == "SHORT"]
            lp = [l for l in my_legs if l["type"] == "PE" and l["side"] == "LONG"]
            return any(s["expiry"] == b["expiry"] and b["strike"] < s["strike"] for s in sp for b in lp)

        has_call = any(l["type"] == "CE" and l["side"] == "SHORT" for l in my_legs)
        tag = tags.get(sym)
        flipped = bool(tag and tag.get("entry_colour") and tag["entry_colour"] != colour)
        if rsi is not None and rsi > rules["rsi_sell_call_above"]:
            desired, basis = "CALL", f"RSI {rsi:.0f} > {rules['rsi_sell_call_above']:g}"
        elif rsi is not None and rsi < rules["rsi_sell_put_below"]:
            desired, basis = "PUT_SPREAD", f"RSI {rsi:.0f} < {rules['rsi_sell_put_below']:g}"
        else:
            desired, basis = ("PUT_SPREAD" if colour == "green" else "CALL"), f"Supertrend {colour}"
        have = has_put_spread() if desired == "PUT_SPREAD" else has_call
        shorts = [l for l in my_legs if l["side"] == "SHORT"]

        def nearest(kind):
            c = [l for l in shorts if l["type"] == kind]
            if not c:
                return None
            l = min(c, key=lambda x: abs(x["dist_pct"]))
            return {"strike": l["strike"], "expiry": l["expiry"], "dist_pct": l["dist_pct"]}
        if flipped:
            status = "FLIP"
            note = (f"Supertrend turned {colour.upper()} since entry ({tag.get('entry_colour')}): close the "
                    f"{'put spread' if colour == 'red' else 'short call'} and open the "
                    f"{'short call' if colour == 'red' else 'bull put spread'}.")
            alerts.append({"level": "EXIT", "symbol": sym, "text": f"{sym}: {note}"})
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
                alerts.append({"level": "ENTER", "symbol": sym, "text": f"{sym}: {note} - {'bull put spread' if desired == 'PUT_SPREAD' else 'sell call'}"})
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
            entry_sig = colour == "green" and flip_days is not None and flip_days <= rules["share_entry_window_trading_days"]
            shares_rows.append({"symbol": sym, "spot": spot, "avg_cost": h["avg_cost"], "qty": h["qty"],
                                "invested": round(h["qty"] * h["avg_cost"], 2), "value": round(h["qty"] * spot, 2),
                                "pl_pct": round(pl_pct, 2), "pl_rs": round(h["qty"] * (spot - h["avg_cost"]), 2),
                                "colour": colour, "flip_date": flip_date, "flip_trading_days": flip_days, "rsi": rsi,
                                "entry_signal": entry_sig, "avg_status": ast, "add_qty": add_qty,
                                "add_value_rs": round(add_qty * spot, 2), "last_add": la, "days_since_add": since,
                                "avg_note": anote})
        stocks.append({
            "symbol": sym, "spot": spot, "colour": colour, "flip_date": flip_date, "flip_trading_days": flip_days,
            "rsi": rsi, "basis": basis, "near_call": nearest("CE"), "near_put": nearest("PE"),
            "shares": shares, "lot": lot, "covered": (shares >= lot) if lot else None,
            "desired": desired, "status": status, "note": note,
            "tagged": bool(tag), "suggestions": suggestions, "legs": my_legs,
        })

    order = {"EXIT": 0, "WARN": 1, "ENTER": 2}
    alerts.sort(key=lambda a: order.get(a["level"], 9))
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "market_data_date": market_date, "as_of": today.isoformat(),
        "rules": rules, "show_expiries": show_exp, "stocks": stocks, "alerts": alerts,
        "shares": {"rows": shares_rows, "exit_rule": None, "entry_window": rules["share_entry_window_trading_days"]},
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
    n_ent = sum(1 for a in shares_rows if a["entry_signal"])
    print(f"shares: averaging due {n_add}, entry signals {n_ent} | {len(stocks)} stocks | ENTER {n('ENTER')} HOLD {n('HOLD')} WAIT {n('WAIT')} FLIP {n('FLIP')} | legs {len(legs)} | alerts {len(alerts)}")
    for a in alerts:
        print(f"  {a['level']:5} {a['text']}")
    if result["chains_needed"]:
        print("CHAINS NEEDED (Dhan MCP market_data optionchain; save raw text to data/cc_raw/chains/<SYMBOL>_<EXPIRY>.txt):")
        for c in result["chains_needed"]:
            print(f"  {c['symbol']} UnderlyingScrip={c['security_id']} Expiry={c['expiry']}")
    print("written", args.out)


if __name__ == "__main__":
    main()
