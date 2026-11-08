"""Build dh252 stock order tickets from dhan_live_signals.json - the single source of what may be traded.

Only stocks that currently have a signal can appear (no options, no hedge-portfolio symbols, nothing the
user types in by hand). Quantities come from the engine, never from the caller:
  entry : each entry signal, qty = qty_to_buy (>= 1 share, effective tier size), BUY
  addon : each add-on signal, qty = add_qty (1/10 of the open position), BUY
  exit  : each exit signal (Supertrend red), qty = the whole open position, SELL
The ticket is information for the order skills (dhan-order-entry / dhan-order-exit); this script places nothing.

Usage: python dhan-live/scripts/build_order_ticket.py entry|addon|exit [--symbols A,B] [--signals PATH] [--holdings PATH]
Prints a table and then the tickets as JSON (last block). Exit code 2 = refuse (stale data, bad signal file).
"""
import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_STALE_DAYS = 3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["entry", "addon", "exit"])
    ap.add_argument("--symbols", default="", help="comma list: restrict to these signal stocks (must already have a signal)")
    ap.add_argument("--signals", default=str(ROOT / "dhan_live_signals.json"))
    ap.add_argument("--holdings", default=str(ROOT / "data" / "holdings_snapshot.json"))
    args = ap.parse_args()

    sig = json.loads(Path(args.signals).read_text())
    held = {h["symbol"]: h for h in json.loads(Path(args.holdings).read_text())["holdings"]}
    hedge = set(sig.get("option_hedge_portfolio", []))
    md = sig.get("market_data_date")
    age = (date.today() - datetime.strptime(md, "%Y-%m-%d").date()).days if md else None
    if age is None or age > MAX_STALE_DAYS:
        print(f"REFUSED: signal data is {age} days old (market data {md}); run /refresh-dhan first.")
        sys.exit(2)

    src = {"entry": sig.get("entries", []), "addon": sig.get("addons", []), "exit": sig.get("exits", [])}[args.kind]
    want = {s.strip().upper() for s in args.symbols.split(",") if s.strip()}
    unknown = want - {r["symbol"] for r in src}
    if unknown:
        print(f"REFUSED: no current {args.kind} signal for {sorted(unknown)} - nothing is placed for stocks without a signal.")
        sys.exit(2)

    tickets, skipped = [], []
    for r in src:
        s = r["symbol"]
        if want and s not in want:
            continue
        if s in hedge:
            skipped.append((s, "hedge portfolio - never a dh252 trade")); continue
        h = held.get(s)
        if args.kind == "entry":
            qty = r.get("qty_to_buy") or 0
            if h and h["qty"] > 0:
                skipped.append((s, "already held")); continue
            side, ref, why = "BUY", r["close"], f"52-week high + Supertrend {r['supertrend_color']} ({r.get('flip_label')})"
        elif args.kind == "addon":
            qty = r.get("add_qty") or 0
            side, ref = "BUY", r["cmp"]
            why = f"P&L {r['pl_pct']:.1f}% <= {sig['rules']['add_trigger_pct']}%, cooldown ok ({r.get('cooldown_days_since_last_buy')}d since last buy)"
        else:
            if not h:
                skipped.append((s, "not in the Dhan holdings snapshot")); continue
            qty = r["qty"]
            if h["qty"] != qty:
                skipped.append((s, f"signal qty {qty} != holdings qty {h['qty']} - refresh holdings first")); continue
            side, ref, why = "SELL", r["cmp"], f"Supertrend red ({r.get('flip_label')}), P&L {r['pl_pct']:.1f}% - exit the whole position"
        if qty < 1:
            skipped.append((s, "quantity < 1 share")); continue
        tickets.append({"kind": args.kind, "symbol": s, "side": side, "qty": int(qty), "ref_price": ref,
                        "est_value": round(qty * ref, 2), "reason": why, "market_data_date": md})

    print(f"{args.kind.upper()} tickets from signals dated {md} ({age}d old): {len(tickets)}")
    for t in tickets:
        print(f"  {t['side']:4} {t['symbol']:12} x{t['qty']:<5} ref Rs{t['ref_price']:<9} ~Rs{t['est_value']:<10} {t['reason']}")
    for s, why in skipped:
        print(f"  skipped {s}: {why}")
    print("TICKETS_JSON=" + json.dumps(tickets))


if __name__ == "__main__":
    main()
