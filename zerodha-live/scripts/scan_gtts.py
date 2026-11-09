"""Scan the ACTIVE option GTTs for invalid / dangerous orders (AZ).

Usage: python zerodha-live/scripts/scan_gtts.py          (after cc_positions.py and cc_gtts.py, both from today)
Writes data/gtt_scan.json {fetched_at, checked, findings[{check, severity, tradingsymbol, gtt_id, concern, action}]} and prints a table.
Checks (a GTT here is a buy-back on a short option: lower trigger = profit target, upper trigger = the 3x stop):
  G1 STALE       no open position on the contract any more (closed / expired) -> delete it
  G2 WRONG SIDE  a SELL GTT on a short leg or a BUY GTT on a long leg adds to the position instead of protecting it
  G3 QUANTITY    GTT quantity above the open quantity (would flip the position) = HIGH; below it = partly protected
  G4 DUPLICATE   more than one active BUY GTT on the contract (together they can buy back more than you hold)
  G5 TRIGGER     a trigger on the wrong side of the current price (it would fire at once or never), or the stop's limit below its trigger
  G6 OFF-RULE    the stop trigger is not near stop_premium_multiple x the sold average, or there is no stop at all (profit target only)
  G7 EXPIRES     the GTT lapses before the option expires, leaving the leg unprotected for the last days
Only contracts of F&O-universe stocks expiring on/after track_from are checked (the same scope as the covered call); stock GTTs are ignored.
"""
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
IST = timezone(timedelta(hours=5, minutes=30))
RX = re.compile(r"^(.+?)(\d\d)([A-Z]{3})(\d+(?:\.\d+)?)(CE|PE)$")
MON = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
NAMES = {"G1": "STALE", "G2": "WRONG SIDE", "G3": "QUANTITY", "G4": "DUPLICATE", "G5": "TRIGGER", "G6": "OFF-RULE", "G7": "EXPIRES"}


def load(n):
    return json.loads((DATA / n).read_text(encoding="utf-8"))


def main():
    cfg = load("cc_config.json")
    rules, track_from = cfg["rules"], cfg["track_from"]
    mult = rules.get("stop_premium_multiple", 3)
    uni = set(load("fno_universe.json")["symbols"])
    master = load("nfo_options.json")["symbols"]
    exp_by = {e[2:4] + MON[int(e[5:7]) - 1]: e for s in master.values() for e in s["lot"]}
    pos = {l["tradingsymbol"]: l for l in load("cc_positions.json")["legs"]}
    gd = load("cc_gtts.json")
    findings, checked, by_contract = [], 0, {}
    for g in gd.get("gtts", []):
        m = RX.match(g["tradingsymbol"])
        if not m or m.group(1) not in uni:
            continue
        exp = exp_by.get(m.group(2) + m.group(3))
        if not exp or exp < track_from:
            continue
        checked += 1
        by_contract.setdefault(g["tradingsymbol"], []).append((g, exp))

    def add(check, sev, t, g, concern, action):
        m = RX.match(t)
        findings.append({"check": check, "name": NAMES[check], "severity": sev, "tradingsymbol": t, "gtt_id": g["id"], "symbol": m.group(1),
                         "expiry": exp_by.get(m.group(2) + m.group(3)), "strike": float(m.group(4)), "opt_type": m.group(5),
                         "concern": concern, "action": action})

    for t, items in by_contract.items():
        leg = pos.get(t)
        buys = [(g, e) for g, e in items if any(o["side"] == "BUY" for o in g["orders"])]
        for g, exp in items:
            if leg is None:
                add("G1", "HIGH", t, g, "No open position on this contract (closed or expired): if it triggers it BUYS a new long position", "Delete this GTT")
                continue
            sides = {o["side"] for o in g["orders"]}
            if leg["side"] == "SHORT" and "SELL" in sides:
                add("G2", "HIGH", t, g, "SELL GTT on a short leg: it would add to the short, not protect it", "Delete it")
            if leg["side"] == "LONG" and "BUY" in sides:
                add("G2", "HIGH", t, g, "BUY GTT on a long (hedge) leg: it would add to the position", "Check it; delete if unintended")
            if leg["side"] == "SHORT" and "BUY" in sides:
                q = max(o["qty"] for o in g["orders"])
                if q > leg["qty"]:
                    add("G3", "HIGH", t, g, f"GTT quantity {q} is above the open {leg['qty']}: it would leave you long", "Modify quantity to " + str(leg["qty"]))
                elif q < leg["qty"]:
                    add("G3", "WARN", t, g, f"GTT covers {q} of {leg['qty']} qty", "Modify quantity to " + str(leg["qty"]))
                ltp, trig = leg["ltp"], sorted(g["triggers"])
                up, lo = trig[-1], (trig[0] if len(trig) > 1 else None)
                if up <= ltp:
                    add("G5", "HIGH", t, g, f"Stop trigger {up:g} is at or below the price {ltp:g}: it fires at once or is invalid", "Delete or re-set it")
                if lo is not None and lo >= ltp:
                    add("G5", "HIGH", t, g, f"Profit trigger {lo:g} is at or above the price {ltp:g}", "Delete or re-set it")
                prices = [o["price"] or 0 for o in g["orders"]]
                if max(prices) < up:
                    add("G5", "WARN", t, g, f"Stop limit {max(prices):g} is below its trigger {up:g}: it may not fill", "Raise the limit above the trigger")
                ratio = up / leg["avg"]
                if len(trig) == 1 and up < leg["avg"]:
                    add("G6", "WARN", t, g, f"Profit target only ({up:g} vs {leg['avg']:g} sold): no stop", f"Add a {mult}x stop GTT")
                elif not (mult - 1.0) <= ratio <= (mult + 1.0):
                    add("G6", "WARN", t, g, f"Stop is {ratio:.1f}x the sold price (rule {mult}x)", f"Re-set to {mult * leg['avg']:.2f}")
            if g["expires_at"] and g["expires_at"][:10] < exp:
                add("G7", "WARN", t, g, f"GTT expires {g['expires_at'][:10]}, before the option expires {exp}", "Re-place it")
        if leg is not None and leg["side"] == "SHORT" and len(buys) > 1:
            tot = sum(max(o["qty"] for o in g["orders"]) for g, _ in buys)
            add("G4", "HIGH" if tot > leg["qty"] else "WARN", t, buys[0][0], f"{len(buys)} active buy GTTs ({tot} qty in total vs {leg['qty']} open)", "Keep one, delete the others")
    order = {"HIGH": 0, "WARN": 1}
    findings.sort(key=lambda f: (order[f["severity"]], f["check"], f["tradingsymbol"]))
    (DATA / "gtt_scan.json").write_text(json.dumps({"fetched_at": datetime.now(IST).isoformat(timespec="seconds"), "gtts_fetched_at": gd.get("fetched_at"),
                                                    "checked": checked, "findings": findings}, indent=1))
    print(f"GTT scan: {checked} active option GTTs checked, {len(findings)} findings ({sum(1 for f in findings if f['severity'] == 'HIGH')} high)")
    for f in findings:
        print(f"  {f['severity']:<4} {f['check']} {f['name']:<10} {f['tradingsymbol']:<24} id {f['gtt_id']}  {f['concern']}  -> {f['action']}")


if __name__ == "__main__":
    main()
