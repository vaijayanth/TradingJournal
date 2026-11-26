"""List the stop (SL) and profit-target GTT levels for every open SHORT option leg of the DI (ICICI) book, to place BY HAND in ICICIdirect.

Usage: python icici-live/scripts/build_gtt_levels.py            numbered list of every short leg with its levels
       python icici-live/scripts/build_gtt_levels.py --json     the same as JSON (for the skill)
DI has no broker connector and no GTT list, so nothing can be placed or checked from here: this only works out the numbers from the keyed
positions (data/cc_positions.json, from the ICICIdirect screen) using the same rules as ND and AZ (data/cc_config.json -> rules):
  stop trigger = gtt_stop_trigger_multiple (2.75, default if the DI config has none) x the sold average, stop limit = stop_premium_multiple (3) x the sold average;
  profit target trigger = (100 - profit_exit_decay_pct)% = 40% of the sold average, its limit = trigger + gtt_limit_buffer_pct (3%) rounded up to the 0.05 tick.
Flags: PAST STOP (LTP at/above the stop trigger: close it now, a GTT would fire at once), PAST TARGET (LTP at/below the target: book the profit,
stop-only), HAS TRIGGER (the screen already shows a Trigger Price for the leg: compared with the rule level), STALE (positions not keyed today).
Own copy for DI: imports nothing from dhan-live/ or zerodha-live/.
"""
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
IST = timezone(timedelta(hours=5, minutes=30))
TICK = 0.05


def tick(x, up=False):
    n = x / TICK
    return round((math.ceil(n - 1e-9) if up else math.floor(n + 0.5)) * TICK, 2)


def levels(avg, ltp, rules):
    smult = rules.get("gtt_stop_trigger_multiple", 2.75)   # same as AZ (user, 2026-11-18): trigger 2.75x, limit 3x
    lmult = rules.get("stop_premium_multiple", 3)
    decay = rules.get("profit_exit_decay_pct", 60)
    buf = rules.get("gtt_limit_buffer_pct", 3)
    stop, slim = tick(smult * avg), tick(lmult * avg)
    tgt = tick(avg * (1 - decay / 100))
    tlim = tick(tgt * (1 + buf / 100), up=True) if tgt > 0 else None
    flag = ""
    if ltp is not None and ltp >= stop:
        flag = "PAST STOP"
    elif ltp is not None and tgt > 0 and ltp <= tgt:
        flag = "PAST TARGET"
    return {"stop": stop, "stop_limit": slim, "target": tgt if tgt > 0 else None, "target_limit": tlim, "flag": flag}


def build():
    pos = json.loads((DATA / "cc_positions.json").read_text(encoding="utf-8"))
    rules = json.loads((DATA / "cc_config.json").read_text(encoding="utf-8"))["rules"]
    close_types = {"Exit", "Event close", "Profit Exit", "Through hedge", "Beyond strike", "3× premium", "Expiry risk", "F&O ban"}
    alerts = {}
    try:
        for a in json.loads((ROOT / "covered_call_signals.json").read_text(encoding="utf-8")).get("alerts", []):
            if a.get("type") in close_types:
                alerts.setdefault(a["symbol"], []).append(a)
    except Exception:
        pass
    rows = []
    for l in sorted(pos["legs"], key=lambda x: (x["symbol"], x["expiry"], x["strike"])):
        if l["side"] != "SHORT":
            continue
        lv = levels(l["avg"], l.get("ltp"), rules)
        r = {"symbol": l["symbol"], "contract": f"{l['symbol']} {l['expiry']} {l['strike']:g}{l['type']}", "qty": l["qty"], "sold": l["avg"], "ltp": l.get("ltp"), **lv}
        hit = {a["type"] for a in alerts.get(l["symbol"], []) if a.get("strike") is None or (float(a["strike"]) == float(l["strike"]) and a.get("opt_type") == l["type"])}
        if hit:
            r["close_alert"] = ", ".join(sorted(hit))
        if l.get("stop_trigger") is not None:
            r["screen_trigger"] = l["stop_trigger"]
            off = abs(l["stop_trigger"] - lv["stop"]) > 0.35 * lv["stop"]
            r["trigger_note"] = f"screen trigger {l['stop_trigger']:g}" + (f" is off the rule ({lv['stop']:g})" if off else " (near the rule)")
        rows.append(r)
    keyed = pos.get("as_of") or str(pos.get("fetched_at", ""))[:10]
    stale = keyed != datetime.now(IST).strftime("%Y-%m-%d")
    return rows, keyed, stale, rules


def main():
    rows, keyed, stale, rules = build()
    if "--json" in sys.argv:
        print(json.dumps({"keyed": keyed, "stale": stale, "rows": rows}))
        return
    print(f"DI GTT levels for {len(rows)} short option legs (positions keyed {keyed}{', NOT today: upload a fresh screen first' if stale else ''}).")
    print("Stop = trigger 2.75x sold (limit 3x); profit target = trigger 40% of sold (limit +3%). Prices on the 0.05 tick. Place by hand in ICICIdirect.")
    for i, r in enumerate(rows, 1):
        tgt = f"{r['target']:g} ({r['target_limit']:g})" if r["target"] else "-"
        note = f"  [{r['flag']}]" if r["flag"] else ""
        note += f"  [{r['trigger_note']}]" if r.get("trigger_note") else ""
        note += f"  [ALERT: {r['close_alert']} - close instead of placing]" if r.get("close_alert") else ""
        print(f"  {i:>2}. {r['contract']:<28} qty {r['qty']:>6}  sold {r['sold']:>7g}  ltp {r['ltp']:>7g}  stop {r['stop']:g} ({r['stop_limit']:g})  target {tgt}{note}")


if __name__ == "__main__":
    main()
