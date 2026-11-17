"""AZ option EXIT signals, grouped by rule type (read-only; places nothing).

Reads the covered-call engine's alerts (covered_call_signals.json), the open legs (data/cc_positions.json) and, for the two GTT-related rules,
the option position scan (data/option_scan.json). Groups are ordered from the most urgent rule to the least:
  1 3x premium        the short's premium is at or above 3x what you sold it for: close now
  2 Through hedge     the stock is past the hedge as well: the spread is at maximum loss, close or roll now
  3 Beyond strike     in the money (past the short strike): roll, close or hold
  4 GTT fired, not fixed / stop not fired   from the option scan: a stop that fired without closing the position, or a stop whose trigger the premium already passed
  5 Expiry risk       in the money near expiry (physical settlement): close before expiry
  6 Event close       results / ex-dividend inside the close window (15 days before the event)
  7 Colour flip       Supertrend colour changed and the opposite structure is still open: close it and open the other one
  8 Profit exit       premium decayed 60% or more since it was sold: book the profit
  9 Near strike       price within 2% of a short strike: watch, plan the roll
 10 Orphaned long     a bought leg that hedges nothing: sell it or let it expire
Usage: python zerodha-live/scripts/option_exit_signals.py [--json] [--group 1,2] [--all]   (--all also lists Near strike and Orphaned long in full)
"""
import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IST = timezone(timedelta(hours=5, minutes=30))
GROUPS = [
    (1, "3x premium (close now)", lambda a: a["type"].startswith("3") and "premium" in a["type"]),
    (2, "Through the hedge (maximum loss)", lambda a: a["type"] == "Through hedge"),
    (3, "Beyond the strike (in the money)", lambda a: a["type"] == "Beyond strike"),
    (4, "Stop fired but not fixed / trigger passed (from the option scan)", None),
    (5, "Expiry risk (in the money near expiry)", lambda a: a["type"] == "Expiry risk"),
    (6, "Results / ex-dividend close window", lambda a: a["type"] == "Event close"),
    (7, "Supertrend colour flipped, old structure still open", lambda a: a["type"] == "Exit"),
    (8, "Profit exit (60% or more decayed)", lambda a: a["type"] == "Profit Exit"),
    (9, "Near the short strike (watch)", lambda a: a["type"] == "Near strike"),
    (10, "Orphaned long leg (hedges nothing)", lambda a: a["type"] == "Leftover hedge"),
]


def load(p):
    f = ROOT / p
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--group", default="")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    want = {int(x) for x in a.group.split(",") if x} or {g[0] for g in GROUPS}

    cc = load("covered_call_signals.json")
    pos = load("data/cc_positions.json") or {"legs": []}
    scan = load("data/option_scan.json")
    today = datetime.now(IST).date().isoformat()
    notes = []
    if str(cc.get("live_prices_at", ""))[:10] != today:
        notes.append(f"live prices are not from today (last {str(cc.get('live_prices_at'))[:16]}): near / beyond / 3x alerts may use the last close")
    if str(pos.get("fetched_at", ""))[:10] != today:
        notes.append(f"open legs are from {str(pos.get('fetched_at'))[:10]}, not today: a leg closed or opened since is not reflected")
    if scan is None or str(scan.get("fetched_at", ""))[:10] != today:
        notes.append("the option scan is not from today: group 4 may be missing or stale")

    legs = {(l["symbol"], l["expiry"], float(l["strike"]), l["type"]): l for l in pos["legs"]}

    def row(sym, expiry, strike, typ, concern, action, extra=None):
        l = legs.get((sym, expiry, float(strike), typ)) if strike is not None else None
        r = {"symbol": sym, "leg": (f"{strike:g}{typ}" if strike is not None else "-"), "expiry": expiry or "-", "side": l["side"] if l else "-", "qty": l["qty"] if l else None,
             "sold_or_bought": l["avg"] if l else None, "now": l["ltp"] if l else None, "pnl_rs": l["pnl_rs"] if l else None, "concern": concern, "action": action}
        if extra:
            r.update(extra)
        return r

    out = {}
    for no, title, test in GROUPS:
        rows = []
        if test is not None:
            for al in cc["alerts"]:
                if test(al):
                    rows.append(row(al["symbol"], al.get("expiry"), al.get("strike"), al.get("opt_type"), al.get("concern", ""), al.get("action", "")))
        elif scan:
            for f in scan["findings"]:
                if f["section"] in ("D", "E") and f["severity"] in ("HIGH", "WARN"):
                    ts = f.get("tradingsymbol")
                    l = next((x for x in pos["legs"] if x["tradingsymbol"] == ts), None)
                    rows.append(row(f["symbol"], l["expiry"] if l else None, l["strike"] if l else None, l["type"] if l else None, f["concern"], f["action"], {"severity": f["severity"]}))
        out[no] = {"title": title, "rows": rows}

    if a.json:
        print(json.dumps({"market_data_date": cc["market_data_date"], "notes": notes, "groups": out}, indent=1, default=str))
        return
    total = sum(len(g["rows"]) for g in out.values())
    per_leg = {}
    for no, g in out.items():
        for r in g["rows"]:
            per_leg.setdefault((r["symbol"], r["leg"], r["expiry"]), set()).add(no)
    multi = sorted(((k, v) for k, v in per_leg.items() if len(v) >= 3), key=lambda kv: -len(kv[1]))
    print(f"AZ option exit signals - market data {cc['market_data_date']}, live prices {str(cc.get('live_prices_at'))[:16]}, open legs {len(pos['legs'])}: {total} signals on {len(per_leg)} distinct legs.")
    if multi:
        print("  Legs in 3 or more groups (most urgent first): " + "; ".join(f"{k[0]} {k[1]} (groups {','.join(str(x) for x in sorted(v))})" for k, v in multi))
    for n in notes:
        print(f"  !! {n}")
    for no, g in out.items():
        if no not in want:
            continue
        rows = g["rows"]
        print(f"\n== {no}. {g['title']}: {len(rows)} ==")
        if not rows:
            print("   none")
            continue
        limit = None if a.all or no < 9 else 8
        shown = rows if limit is None else rows[:limit]
        for r in shown:
            qty = f"{r['qty']}" if r["qty"] is not None else "-"
            pnl = f"Rs{r['pnl_rs']:,.0f}" if r["pnl_rs"] is not None else "-"
            print(f"   {r['symbol']:<12} {r['leg']:<10} {r['expiry']:<11} {r['side']:<6} qty {qty:>6}  P&L {pnl:>10}  {r['concern'][:78]}  -> {r['action']}")
        if limit is not None and len(rows) > limit:
            print(f"   ... {len(rows) - limit} more (use --all)")


if __name__ == "__main__":
    main()
