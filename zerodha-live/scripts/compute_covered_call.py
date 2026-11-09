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
from datetime import datetime, timedelta, timezone
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
        if l["side"] == "SHORT" and l["touched"]:
            hedges = [h for h in my_legs if h["side"] == "LONG" and h["type"] == l["type"] and h["expiry"] == l["expiry"]
                      and ((h["type"] == "CE" and h["strike"] > l["strike"]) or (h["type"] == "PE" and h["strike"] < l["strike"]))]
            thru = [h for h in hedges if h["touched_h"]]
            base = (f"{sym} {l['expiry']}: price {spot:g} is {abs(l['beyond_pct']):.1f}% {'above' if l['type']=='CE' else 'below'} the short "
                    f"{l['strike']:g}{l['type']} (in the money, intrinsic Rs{l['intrinsic_rs']:,} on {l['qty']} qty)")
            if thru:
                out.append({"level": "EXIT", "symbol": sym, "text": base + f"; it is also through the {thru[0]['strike']:g}{thru[0]['type']} hedge - the spread is at maximum loss, decide now"})
            else:
                out.append({"level": "BREACH", "symbol": sym, "text": base + "; decide: roll, close, or hold"})
        elif l["side"] == "SHORT" and l["near"]:
            out.append({"level": "WARN", "symbol": sym, "text": f"{sym} {l['expiry']}: price {spot:g} is within {abs(l['beyond_pct']):.1f}% of the short {l['strike']:g}{l['type']}"})
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
    stocks, no_data, alerts, new_tags = [], [], [], False
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
                    alerts.append({"level": "EXIT", "symbol": sym, "text": f"{sym} {l['expiry']} {l['strike']:g}{l['type']}: premium {l['ltp']} >= {mult}x sold {l['avg']} - close it"})
            strike_zone(l, spot_now, rules.get("near_strike_pct", 2))
            l["touched_h"] = l["touched"] if l["side"] == "LONG" else False
        alerts.extend(strike_alerts(sym, my, spot_now, rules.get("near_strike_pct", 2), None))
        shorts = [l for l in my if l["side"] == "SHORT"]
        has_call = any(l["type"] == "CE" for l in shorts)
        has_put_spread = any(s["type"] == "PE" and any(b["type"] == "PE" and b["side"] == "LONG" and b["expiry"] == s["expiry"] and b["strike"] < s["strike"] for b in my) for s in shorts)
        if my and sym not in tags:  # first time legs are seen: the Supertrend colour now is the entry colour
            tags[sym] = {"entry_colour": colour, "first_seen": market_date, "source": "first_seen"}
            new_tags = True
        tag = tags.get(sym)
        flipped = bool(my and tag and tag.get("entry_colour") and tag["entry_colour"] != colour)
        have = has_put_spread if kind == "PUT_SPREAD" else has_call
        if flipped:
            status = "FLIP"
            note = (f"Supertrend turned {colour.upper()} since entry ({tag['entry_colour']}): close the "
                    f"{'put spread' if colour == 'red' else 'short call'} and open the {'short call' if colour == 'red' else 'bull put spread'}.")
            alerts.append({"level": "EXIT", "symbol": sym, "text": f"{sym}: {note}"})
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
    result = {"generated_at": datetime.now(timezone.utc).isoformat(), "market_data_date": market_date, "live_prices_at": live.get("fetched_at") if live_px else None, "rules": rules,
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
