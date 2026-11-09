"""Build buy-back (stop) GTT tickets for open SHORT option legs that have none (the 'No GTT placed' alert).

Usage:
  python zerodha-live/scripts/build_gtt_tickets.py            list the legs that need a GTT (numbered)
  python zerodha-live/scripts/build_gtt_tickets.py --pick 1,3-5|all   build the tickets for those numbers (prints TICKETS_JSON=...)
Inputs (all must be from TODAY, IST; the zerodha-gtt-order skill pulls them first):
  data/cc_positions.json   <- get_positions via cc_positions.py   (the open legs, quantities, sold average, LTP)
  data/cc_gtts.json        <- get_gtts via cc_gtts.py             (which contracts already have an active buy GTT)
Rules: SHORT option legs only; BUY to close, NRML, quantity = the open short quantity. Default = a TWO-LEG (one-cancels-other) GTT like
the user's own: upper trigger = the stop, stop_premium_multiple x the sold average (3), lower trigger = the profit target, the premium
decayed by profit_exit_decay_pct (60%), i.e. 40% of the sold average. Each limit = its trigger + gtt_limit_buffer_pct (3%) rounded up to
the 0.05 tick. `--single` builds the stop only. If the premium has already decayed past the profit target the ticket is stop-only (book
the profit now: see the Profit Exit alert). A leg whose LTP is already at/above the stop is NOT ticketed (it needs closing now). Refuses when
data/trading_halt.json says halt, when the inputs are not from today, or for a batch over 40 orders.
"""
import argparse
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
IST = timezone(timedelta(hours=5, minutes=30))
TICK = 0.05
MAX_BATCH = 40


def tick(x, up=False):
    n = x / TICK
    return round((math.ceil(n - 1e-9) if up else math.floor(n + 0.5)) * TICK, 2)


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def today_ist():
    return datetime.now(IST).strftime("%Y-%m-%d")


def parse_pick(txt, n):
    if txt.strip().lower() == "all":
        return list(range(1, n + 1))
    out = []
    for part in txt.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            out += list(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    bad = [i for i in out if i < 1 or i > n]
    if bad:
        sys.exit(f"REFUSED: numbers {bad} are not in the list (1-{n}).")
    return sorted(set(out))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pick")
    ap.add_argument("--single", action="store_true", help="stop-only single-trigger GTTs (no profit target)")
    a = ap.parse_args()
    halt = load("trading_halt.json")
    if halt.get("halt"):
        sys.exit(f"REFUSED: trading halt is ON ({halt.get('reason', 'no reason given')}). Nothing may be placed.")
    pos, gtt = load("cc_positions.json"), load("cc_gtts.json")
    for nm, d in (("positions", pos), ("GTT list", gtt)):
        if str(d.get("fetched_at", ""))[:10] != today_ist():
            sys.exit(f"REFUSED: the {nm} were not pulled today ({d.get('fetched_at')}). Pull get_positions / get_gtts first, otherwise a leg that already has a GTT could get a second one.")
    cfg = load("cc_config.json")["rules"]
    mult, buf = cfg.get("stop_premium_multiple", 3), cfg.get("gtt_limit_buffer_pct", 3)
    decay = cfg.get("profit_exit_decay_pct", 60)
    active = gtt.get("active", {})
    need, skipped = [], []
    for l in sorted(pos["legs"], key=lambda x: (x["symbol"], x["expiry"], x["strike"])):
        if l["side"] != "SHORT" or l["tradingsymbol"] in active:
            continue
        trig = tick(mult * l["avg"])
        if l["ltp"] >= trig:
            skipped.append((l, trig))
            continue
        lim = tick(trig * (1 + buf / 100), up=True)
        t = {"tradingsymbol": l["tradingsymbol"], "symbol": l["symbol"], "exchange": "NFO", "product": "NRML", "transaction_type": "BUY",
             "quantity": l["qty"], "sold_avg": l["avg"], "last_price": l["ltp"], "est_value": round(lim * l["qty"])}
        prof = tick(l["avg"] * (1 - decay / 100))
        if a.single or prof <= 0 or l["ltp"] <= prof:
            t.update({"trigger_type": "single", "trigger_value": trig, "limit_price": lim})
            if not a.single and prof > 0:
                t["note"] = f"already decayed past the {decay}% profit target (LTP {l['ltp']:g} <= {prof:g}): stop-only; consider booking the profit now"
        else:
            t.update({"trigger_type": "two-leg", "upper_trigger_value": trig, "upper_limit_price": lim, "upper_quantity": l["qty"],
                      "lower_trigger_value": prof, "lower_limit_price": tick(prof * (1 + buf / 100), up=True), "lower_quantity": l["qty"]})
        need.append(t)
    if a.pick is None:
        print(f"{len(need)} short option legs with no active buy-back GTT (stop = {mult}x sold, profit target = {decay}% decay, limits = trigger + {buf}%):")
        for i, t in enumerate(need, 1):
            if t["trigger_type"] == "two-leg":
                trg = f"profit {t['lower_trigger_value']:>7} (lim {t['lower_limit_price']:>7}) | stop {t['upper_trigger_value']:>8} (lim {t['upper_limit_price']:>8})"
            else:
                trg = f"stop only {t['trigger_value']:>8} (lim {t['limit_price']:>8})" + (f"  NOTE: {t['note']}" if t.get("note") else "")
            print(f"  {i:>3}. {t['tradingsymbol']:<24} qty {t['quantity']:>6}  sold {t['sold_avg']:>8}  LTP {t['last_price']:>8}  {trg}")
        for l, trig in skipped:
            print(f"  NOT TICKETED {l['tradingsymbol']}: LTP {l['ltp']} is already at/above the {trig} trigger - close it now (3x premium alert), a GTT would fire immediately")
        return
    pick = parse_pick(a.pick, len(need))
    if len(pick) > MAX_BATCH:
        sys.exit(f"REFUSED: {len(pick)} GTTs in one batch (limit {MAX_BATCH}).")
    tickets = [need[i - 1] for i in pick]
    print(f"{len(tickets)} GTT tickets")
    print("TICKETS_JSON=" + json.dumps(tickets))


if __name__ == "__main__":
    main()
