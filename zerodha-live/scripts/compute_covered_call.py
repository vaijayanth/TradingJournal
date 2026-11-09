"""Zerodha covered call / option-selling signals -> zerodha-live/covered_call_signals.json.

Rules (user, 2026-11-09; same logic as Dhan's covered call, universe = every Nifty F&O stock):
  * RSI(14) > 70 -> sell a call (0.10 delta); RSI(14) < 30 -> bull put spread (0.10 delta put, hedge 2 listed strikes lower).
  * Otherwise Supertrend GREEN -> bull put spread; Supertrend RED -> sell a call only.
  * Exits: the short option reaches 3x the premium sold (EXIT), the stock reaches the short strike (WARN), or the Supertrend
    colour changes against the colour at entry (FLIP: close the structure and open the opposite one).
No option quotes or chains are pulled, so strikes/premiums for NEW trades are not computed: each signal says which structure to
sell, the basis, the lot size and the expiry (Zerodha's public instrument list, data/nfo_options.json). Open option legs come
from the Zerodha MCP get_positions call (scripts/cc_positions.py -> data/cc_positions.json): only expiries on/after
`track_from` count (user: from 2026-11-01, i.e. the November options too); older ones are ignored. Their price/P&L is the positions call's own.
Entry colour for the FLIP exit is the Supertrend colour when a stock's legs were first seen (data/cc_tags.json, written here).

Usage: python zerodha-live/scripts/compute_covered_call.py   (run after refresh_zerodha.py has fetched the screens)
"""
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from zerodha_common import load_json, strip_suffix  # noqa: E402

DATA = HERE.parent / "data"
OUT = HERE.parent / "covered_call_signals.json"


def desired_structure(colour, rsi, rules):
    if rsi is not None and rsi > rules["rsi_sell_call_above"]:
        return "CALL", f"RSI {rsi:.1f} > {rules['rsi_sell_call_above']:g}"
    if rsi is not None and rsi < rules["rsi_sell_put_below"]:
        return "PUT_SPREAD", f"RSI {rsi:.1f} < {rules['rsi_sell_put_below']:g}"
    return ("PUT_SPREAD" if colour == "green" else "CALL"), f"Supertrend {colour}"


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


def expiry_alerts(sym, my_legs, spot, shares_held, rules):
    """Stock options are settled by physical delivery at expiry: an in-the-money leg close to expiry means shares to deliver (short call, long put)
    or to buy and pay for (short put, long call). Flag every in-the-money leg within expiry_risk_days of expiry; closing it earlier avoids the delivery."""
    out = []
    window = rules.get("expiry_risk_days", 7)
    today = datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
    for l in my_legs:
        if not l.get("touched"):
            continue
        days = (date.fromisoformat(l["expiry"]) - today).days
        if days < 0 or days > window:
            continue
        side = "short" if l["side"] == "SHORT" else "long"
        delivers = (l["side"] == "SHORT") == (l["type"] == "CE")      # short call / long put: you deliver shares; short put / long call: you take delivery
        value = l["qty"] * l["strike"]
        what = (f"deliver {l['qty']} shares" + (f" (you hold {shares_held})" if shares_held is not None and l["type"] == "CE" else "")) if delivers else f"buy {l['qty']} shares (about Rs{value / 100000:.1f} lakh)"
        out.append({"level": "BREACH" if days <= 3 else "WARN", "type": "Expiry risk", "symbol": sym, "expiry": l["expiry"], "strike": l["strike"], "opt_type": l["type"], "qty": l["qty"],
                    "concern": f"{side.title()} {l['strike']:g}{l['type']} is in the money {days}d before expiry: physical settlement, you would {what}",
                    "action": "Close it before expiry" if days > 1 else "Close it today",
                    "text": f"{sym} {l['expiry']} {side} {l['strike']:g}{l['type']} in the money, {days} days to expiry: physical settlement"})
    return out


def main():
    cfg = load_json(DATA / "cc_config.json"); rules = cfg["rules"]
    st_file = load_json(DATA / "cache" / "supertrend_full.json")
    st = {strip_suffix(e["symbol"]): e for e in st_file["entries"]}
    aliases = load_json(DATA / "symbol_aliases.json").get("aliases", {}) if (DATA / "symbol_aliases.json").exists() else {}
    market_date = st_file.get("latest_market_date")
    rsi = {strip_suffix(r["symbol"]): r["rsi14"] for r in load_json(DATA / "cache" / "market_screens_full.json").get("rsi_all", []) if r.get("rsi14") is not None}
    master = load_json(DATA / "nfo_options.json")["symbols"] if (DATA / "nfo_options.json").exists() else {}
    excluded = set(load_json(DATA / "excluded_symbols.json")["symbols"])
    uni = [s for s in load_json(DATA / "fno_universe.json")["symbols"] if s not in excluded]
    # Expiry shown on each signal: the first monthly expiry at least `expiry_min_days` away (user's book trades the next-month
    # contract: on 9 Nov that is December). Rolls forward by itself; a stock without that expiry listed falls back to its
    # nearest later listed expiry, else its last one.
    mdate = datetime.strptime(market_date, "%Y-%m-%d").date()
    min_days = rules.get("expiry_min_days", 30)

    def pick_expiry(listed):
        ok = [e for e in sorted(listed) if (datetime.strptime(e, "%Y-%m-%d").date() - mdate).days >= min_days]
        return ok[0] if ok else (sorted(listed)[-1] if listed else None)
    all_exp = sorted({e for m in master.values() for e in m["lot"]})
    expiries = [pick_expiry(all_exp)] if all_exp else []
    pos_file = DATA / "cc_positions.json"
    pos = load_json(pos_file) if pos_file.exists() else {"legs": [], "ignored_legs": 0, "fetched_at": None}
    legs_by = {}
    for l in pos["legs"]:
        if l["symbol"] in uni:
            legs_by.setdefault(l["symbol"], []).append(l)
    tags_file = DATA / "cc_tags.json"
    tags = load_json(tags_file).get("tags", {}) if tags_file.exists() else {}
    mult = rules["stop_premium_multiple"]
    lp_file = DATA / "cc_live_prices.json"
    live = load_json(lp_file) if lp_file.exists() else {}
    ist_today = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%Y-%m-%d")
    live_px = live.get("prices", {}) if str(live.get("fetched_at", ""))[:10] == ist_today else {}   # only same-day live prices count
    hs = DATA / "holdings_snapshot.json"
    held_qty = {h["symbol"]: h["qty"] for h in load_json(hs).get("holdings", [])} if hs.exists() else {}
    gf = DATA / "cc_gtts.json"
    gtt_active = load_json(gf).get("active", {}) if gf.exists() and str(load_json(gf).get("fetched_at", ""))[:10] == ist_today else None   # None = no same-day GTT list: the check is skipped, not failed
    sf = DATA / "gtt_scan.json"
    scan = load_json(sf) if sf.exists() else {}
    scan_ok = str(scan.get("fetched_at", ""))[:10] == ist_today   # a scan from an earlier day is not shown as current
    stocks, no_data, alerts, new_tags = [], [], [], False
    if scan_ok:
        for f in scan.get("findings", []):
            alerts.append({"level": "BREACH" if f["severity"] == "HIGH" else "WARN", "type": "Invalid GTT", "symbol": f["symbol"], "expiry": f.get("expiry"), "strike": f.get("strike"),
                           "opt_type": f.get("opt_type"), "concern": f"{f['name'].title()}: {f['concern']}", "action": f["action"] + f" (GTT {f['gtt_id']})",
                           "text": f"{f['symbol']} {f['tradingsymbol']}: {f['concern']}"})
    for sym in uni:
        px = aliases.get(sym, sym)  # NSE renames: only the data lookup is aliased
        e = st.get(px)
        if not e:
            no_data.append(sym)
            continue
        spot, colour = e["close"], e["color"]
        kind, basis = desired_structure(colour, rsi.get(px), rules)
        flip_days = e.get("current_streak_trading_days", e.get("recent_flip_trading_days_ago"))
        lots = (master.get(sym) or {}).get("lot", {})
        my = [dict(l) for l in legs_by.get(sym, [])]
        spot_now = live_px.get(sym, spot)   # live price when it was pulled today, else the last close
        for l in my:
            l["lot"] = lots.get(l["expiry"])
            l["lots"] = round(l["qty"] / l["lot"], 2) if l["lot"] else None
            l["dist_pct"] = round((l["strike"] / spot_now - 1) * 100, 2)
            if l["side"] == "SHORT":
                l["stop_at"] = round(mult * l["avg"], 2)
                l["stop_hit"] = l["ltp"] >= l["stop_at"]
                if l["stop_hit"]:
                    alerts.append({"level": "EXIT", "type": "3× premium", "symbol": sym, "expiry": l["expiry"], "strike": l["strike"], "opt_type": l["type"], "text": f"{sym} {l['expiry']} {l['strike']:g}{l['type']}: premium {l['ltp']} >= {mult}x sold {l['avg']} - close it",
                                   "expiry": l["expiry"], "strike": l["strike"], "opt_type": l["type"], "concern": f"Premium {l['ltp']:g} is {l['ltp'] / l['avg']:.1f}x the {l['avg']:g} sold", "action": "Close now (3x stop hit)"})
                elif l["ltp"] <= l["avg"] * (1 - rules.get("profit_exit_decay_pct", 60) / 100):
                    alerts.append({"level": "PROFIT", "type": "Profit Exit", "symbol": sym, "expiry": l["expiry"], "strike": l["strike"], "opt_type": l["type"],
                                   "concern": f"Premium decayed {(1 - l['ltp'] / l['avg']) * 100:.0f}% (sold {l['avg']:g}, now {l['ltp']:g})", "action": "Book profit: buy back",
                                   "text": f"{sym} {l['expiry']} {l['strike']:g}{l['type']}: premium decayed {(1 - l['ltp'] / l['avg']) * 100:.0f}% (sold {l['avg']:g}, now {l['ltp']:g}) - book the profit"})
            strike_zone(l, spot_now, rules.get("near_strike_pct", 2))
            l["touched_h"] = l["touched"] if l["side"] == "LONG" else False
        alerts.extend(strike_alerts(sym, my, spot_now, rules.get("near_strike_pct", 2), None))
        alerts.extend(structure_alerts(sym, my, held_qty.get(sym, 0), gtt_active))
        alerts.extend(expiry_alerts(sym, my, spot_now, held_qty.get(sym, 0), rules))
        shorts = [l for l in my if l["side"] == "SHORT"]
        has_call = any(l["type"] == "CE" for l in shorts)
        has_put_spread = any(s["type"] == "PE" and any(b["type"] == "PE" and b["side"] == "LONG" and b["expiry"] == s["expiry"] and b["strike"] < s["strike"] for b in my) for s in shorts)
        if my and sym not in tags:  # first time legs are seen: the Supertrend colour now is the entry colour
            tags[sym] = {"entry_colour": colour, "first_seen": market_date, "source": "first_seen"}
            new_tags = True
        tag = tags.get(sym)
        flipped = bool(my and tag and tag.get("entry_colour") and tag["entry_colour"] != colour)
        have = has_put_spread if kind == "PUT_SPREAD" else has_call
        col_rule = "PUT_SPREAD" if colour == "green" else "CALL"   # the Supertrend colour alone (the RSI override never triggers an Exit)
        opp_legs = [l for l in shorts if l["type"] == ("PE" if col_rule == "CALL" else "CE")]   # open legs of the structure the colour no longer wants
        opposite = bool(opp_legs)
        if opposite and not flipped:
            leg_txt = ", ".join(f"{l['strike']:g}{l['type']} {l['expiry']}" for l in opp_legs)
            opp_note = (f"Supertrend is {colour.upper()}: the open {'short put / put spread' if col_rule == 'CALL' else 'short call'} ({leg_txt}) is the opposite of the colour rule - close it and "
                        f"{'sell the call' if col_rule == 'CALL' else 'open the bull put spread'}.")
        if flipped or opposite:
            status = "FLIP"
            note = opp_note if (opposite and not flipped) else (f"Supertrend turned {colour.upper()} since entry ({tag['entry_colour']}): close the "
                    f"{'put spread' if colour == 'red' else 'short call'} and open the {'short call' if colour == 'red' else 'bull put spread'}.")
            exit_concern = (f"Supertrend turned {colour.upper()} since entry" if flipped else f"Supertrend {colour.upper()} but the {'short put / put spread' if col_rule == 'CALL' else 'short call'} is still open")
            exit_action = "Close it and sell the call" if (col_rule == "CALL") else "Close it and open the bull put spread"
            leg_f = {"expiry": opp_legs[0]["expiry"], "strike": opp_legs[0]["strike"], "opt_type": opp_legs[0]["type"]} if opp_legs else {}
            if len(opp_legs) > 1:
                exit_concern += f" ({len(opp_legs)} legs)"
            alerts.append({**leg_f, "level": "EXIT", "type": "Exit", "symbol": sym, "concern": exit_concern, "action": exit_action, "text": f"{sym}: {note}"})
        elif have:
            status, note = "HOLD", f"Open structure matches the rule ({basis})."
        else:
            status, note = "ENTER", f"{basis}: {'bull put spread' if kind == 'PUT_SPREAD' else 'sell call'}" + (" (you hold other legs in this stock)" if my else "")
        stocks.append({
            "symbol": sym, "spot": spot, "colour": colour, "rsi": rsi.get(px), "basis": basis, "desired": kind,
            "flip_date": e.get("current_streak_start_date") or e.get("recent_flip_date"), "flip_trading_days": flip_days,
            "expiries": [{"expiry": pick_expiry(list(lots)), "lot": lots.get(pick_expiry(list(lots)))}] if lots else [], "rsi_override": basis.startswith("RSI"),
            "status": status, "note": note, "legs": my,
        })
    if new_tags:
        tags_file.write_text(json.dumps({"_note": "Supertrend colour when a stock's tracked option legs were first seen = the entry colour for the FLIP exit. Edit by hand if the real entry colour differed.", "tags": tags}, indent=1))
    order = {"EXIT": 0, "BREACH": 1, "WARN": 2}
    alerts.sort(key=lambda a: order.get(a["level"], 9))
    calls = sum(1 for s in stocks if s["desired"] == "CALL")
    n = lambda k: sum(1 for s in stocks if s["status"] == k)
    result = {"generated_at": datetime.now(timezone.utc).isoformat(), "market_data_date": market_date, "live_prices_at": live.get("fetched_at") if live_px else None, "gtt_scan_at": scan.get("fetched_at") if scan_ok else None, "gtt_checked_at": load_json(gf).get("fetched_at") if gtt_active is not None else None, "rules": rules,
              "show_expiries": expiries, "stocks": stocks, "alerts": alerts, "no_data": no_data, "excluded": sorted(excluded),
              "positions": {"fetched_at": pos.get("fetched_at"), "track_from": cfg.get("track_from"), "legs": sum(len(s["legs"]) for s in stocks),
                            "ignored_legs": pos.get("ignored_legs", 0)},
              "counts": {"call": calls, "put_spread": len(stocks) - calls, "rsi_override": sum(1 for s in stocks if s["rsi_override"]),
                         "enter": n("ENTER"), "hold": n("HOLD"), "flip": n("FLIP")}}
    OUT.write_text(json.dumps(result, indent=1))
    print(f"covered call: {len(stocks)} F&O stocks | sell call {calls} | bull put spread {len(stocks) - calls} | RSI overrides {result['counts']['rsi_override']} | "
          f"open legs tracked {result['positions']['legs']} (from {cfg.get('track_from')}; {pos.get('ignored_legs', 0)} other legs ignored) | alerts {len(alerts)} | market data {market_date}")
    for a in alerts:
        print(f"  {a['level']:5} {a['text']}")


if __name__ == "__main__":
    main()
