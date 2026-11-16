"""ND (Dhan) option EXIT signals, grouped by rule type (read-only; places nothing).

Reads the covered-call engine's alerts and open legs (covered_call_signals.json) and the option position scan (data/option_scan.json).
Groups are ordered from the most urgent rule to the least:
  1 3x premium         the short's premium is at or above 3x what you sold it for: close now
  2 Through hedge      the stock is past the hedge as well (the spread is at maximum loss): close or roll now
  3 Beyond strike      in the money (past the short strike): roll, close or hold
  4 Stop problems      from the option scan: a stop that fired (or was cancelled / rejected) while the short is still open, a stop whose price the premium
                       already passed but is still pending, a short with no stop order, an orphaned / off-rule stop leg
  5 Expiry risk        in the money near expiry (physical settlement): close before expiry
  6 Event close        results / ex-dividend inside the close window (15 days before the event)
  7 Colour flip        Supertrend colour changed and the opposite structure is still open: close it and open the other one
  8 Profit exit        premium decayed 60% or more since it was sold: book the profit
  9 Near strike        price within 2% of a short strike: watch, plan the roll
 10 Hedge gaps         an orphaned long leg (hedges nothing) or a short that is not fully hedged
Usage: python dhan-live/scripts/option_exit_signals.py [--json] [--group 1,2] [--all]   (--all also lists every row of groups 9 and 10)
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
    (4, "Stop problems (from the option scan)", None),
    (5, "Expiry risk (in the money near expiry)", lambda a: a["type"] == "Expiry risk"),
    (6, "Results / ex-dividend close window", lambda a: a["type"] == "Event close"),
    (7, "Supertrend colour flipped, old structure still open", lambda a: a["type"] == "Exit"),
    (8, "Profit exit (60% or more decayed)", lambda a: a["type"] == "Profit Exit"),
    (9, "Near the short strike (watch)", lambda a: a["type"] == "Near strike"),
    (10, "Hedge gaps (orphaned long / not fully hedged)", lambda a: a["type"] in ("Leftover hedge", "Partly hedged", "No hedge")),
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
    scan = load("data/option_scan.json")
    today = datetime.now(IST).date().isoformat()
    notes = []
    if str(cc.get("live_prices_at", ""))[:10] != today:
        notes.append(f"live prices are not from today (last {str(cc.get('live_prices_at'))[:16]}): near / beyond / 3x alerts may use the last close")
    if str(cc.get("generated_at", ""))[:10] != today:
        notes.append(f"the covered-call signals were built {str(cc.get('generated_at'))[:10]}, not today: open legs and alerts may be out of date (run /refresh-dhan)")
    pos_file = ROOT / "data" / "cc_raw" / "positions.txt"
    if not pos_file.exists() or datetime.fromtimestamp(pos_file.stat().st_mtime, IST).date().isoformat() != today:
        notes.append("the raw positions file is not from today: a leg closed or opened since is not reflected")
    if scan is None or str(scan.get("fetched_at", ""))[:10] != today:
        notes.append("the option scan is not from today: group 4 may be missing or stale")

    legs = {(s["symbol"], l["expiry"], float(l["strike"]), l["type"]): l for s in cc["stocks"] for l in s.get("legs", [])}

    def row(sym, expiry, strike, typ, concern, action, extra=None):
        l = legs.get((sym, expiry, float(strike), typ)) if strike is not None else None
        px = (l["sell_avg"] if l["side"] == "SHORT" else l["buy_avg"]) if l else None
        r = {"symbol": sym, "leg": (f"{strike:g}{typ}" if strike is not None else "-"), "expiry": expiry or "-", "side": l["side"] if l else "-", "qty": l["qty"] if l else None,
             "sold_or_bought": px, "now": l["ltp"] if l else None, "pnl_rs": l["pnl_rs"] if l else None, "concern": concern, "action": action}
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
                if f["section"] in ("C", "D", "E", "F") and f["severity"] in ("HIGH", "WARN"):
                    # the scan names a leg as "SYMBOL STRIKEtype EXPIRY" (F may carry only the symbol)
                    parts = f["leg"].split()
                    strike = typ = expiry = None
                    if len(parts) == 3:
                        expiry = parts[2]
                        typ = parts[1][-2:]
                        try:
                            strike = float(parts[1][:-2])
                        except ValueError:
                            strike = None
                    rows.append(row(f["symbol"], expiry, strike, typ, f"[{f['section']}] {f['concern']}", f["action"], {"severity": f["severity"]}))
        out[no] = {"title": title, "rows": rows}

    if a.json:
        print(json.dumps({"market_data_date": cc["market_data_date"], "notes": notes, "groups": out}, indent=1, default=str))
        return
    total = sum(len(g["rows"]) for g in out.values())
    per_leg = {}
    for no, g in out.items():
        for r in g["rows"]:
            per_leg.setdefault((r["symbol"], r["leg"], r["expiry"]), set()).add(no)
    multi = sorted(((k, v) for k, v in per_leg.items() if len(v) >= 3 and k[1] != "-"), key=lambda kv: -len(kv[1]))
    n_legs = sum(len(s.get("legs", [])) for s in cc["stocks"])
    print(f"ND option exit signals - market data {cc['market_data_date']}, live prices {str(cc.get('live_prices_at'))[:16]}, open legs {n_legs}: {total} signals on {len(per_leg)} distinct legs.")
    if multi:
        print("  Legs in 3 or more groups (most urgent first): " + "; ".join(f"{k[0]} {k[1]} (groups {','.join(str(x) for x in sorted(v))})" for k, v in multi))
    for n in notes:
        print(f"  !! {n}")
    print("  (the super order book has no strike or expiry: group 4 matches a stop to a short by symbol + sold average, so verify in the Dhan app before acting)")
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
