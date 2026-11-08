"""Build dh252 stock order tickets from dhan_live_signals.json - the single source of what may be traded.

Only stocks that currently have a signal can appear (no options, no hedge-portfolio symbols, nothing the
user types in by hand). Quantities come from the engine, never from the caller:
  entry : each entry signal, qty = qty_to_buy (>= 1 share, effective tier size), BUY
  addon : each add-on signal, qty = add_qty (1/10 of the open position), BUY
  buy   : entry + add-on signals in ONE numbered list (what /dhan-order-entry shows for one-shot picking)
  exit  : each exit signal (Supertrend red), qty = the whole open position, SELL
The ticket is information for the order skills (dhan-order-entry / dhan-order-exit); this script places nothing.

Usage:
  python dhan-live/scripts/build_order_ticket.py buy|entry|addon|exit            # numbered list
  python dhan-live/scripts/build_order_ticket.py buy --pick 3,7,12-15            # tickets for those numbers
  python dhan-live/scripts/build_order_ticket.py buy --symbols A,B               # or by symbol (must have a signal)
Numbers are stable for a given signal file (entries in file order, then add-ons). Prints a table and a final
TICKETS_JSON= line. Exit code 2 = refuse (stale data, stock without a signal, bad pick).
"""
import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_STALE_DAYS = 3


def parse_pick(text, n):
    nums = set()
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            nums.update(range(int(a), int(b) + 1))
        else:
            nums.add(int(part))
    bad = sorted(x for x in nums if x < 1 or x > n)
    if bad:
        print(f"REFUSED: pick numbers {bad} are not in the list (1-{n}).")
        sys.exit(2)
    return nums


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["buy", "entry", "addon", "exit"])
    ap.add_argument("--pick", default="", help="numbers from the printed list, e.g. 3,7,12-15")
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

    srcs = {"entry": sig.get("entries", []), "addon": sig.get("addons", []), "exit": sig.get("exits", [])}
    kinds = ["entry", "addon"] if args.kind == "buy" else [args.kind]
    all_symbols = {(k, r["symbol"]) for k in kinds for r in srcs[k]}
    want = {s.strip().upper() for s in args.symbols.split(",") if s.strip()}
    unknown = want - {s for _, s in all_symbols}
    if unknown:
        print(f"REFUSED: no current {'/'.join(kinds)} signal for {sorted(unknown)} - nothing is placed for stocks without a signal.")
        sys.exit(2)

    tickets, skipped = [], []
    for kind in kinds:
        for r in srcs[kind]:
            s = r["symbol"]
            if s in hedge:
                skipped.append((s, "hedge portfolio - never a dh252 trade")); continue
            h = held.get(s)
            if kind == "entry":
                qty = r.get("qty_to_buy") or 0
                if h and h["qty"] > 0:
                    skipped.append((s, "already held")); continue
                side, ref, why = "BUY", r["close"], f"52-week high + Supertrend {r['supertrend_color']} ({r.get('flip_label')})"
            elif kind == "addon":
                qty = r.get("add_qty") or 0
                side, ref = "BUY", r["cmp"]
                why = f"add-on: P&L {r['pl_pct']:.1f}% <= {sig['rules']['add_trigger_pct']}%, {r.get('cooldown_days_since_last_buy')}d since last buy"
            else:
                if not h:
                    skipped.append((s, "not in the Dhan holdings snapshot")); continue
                qty = r["qty"]
                if h["qty"] != qty:
                    skipped.append((s, f"signal qty {qty} != holdings qty {h['qty']} - refresh holdings first")); continue
                side, ref, why = "SELL", r["cmp"], f"Supertrend red ({r.get('flip_label')}), P&L {r['pl_pct']:.1f}% - exit the whole position"
            if qty < 1:
                skipped.append((s, "quantity < 1 share")); continue
            tickets.append({"kind": kind, "symbol": s, "side": side, "qty": int(qty), "ref_price": ref,
                            "est_value": round(qty * ref, 2), "reason": why, "market_data_date": md})
    for i, t in enumerate(tickets, 1):
        t["no"] = i

    chosen = tickets
    if args.pick:
        nums = parse_pick(args.pick, len(tickets))
        chosen = [t for t in tickets if t["no"] in nums]
    if want:
        chosen = [t for t in chosen if t["symbol"] in want]

    label = "selected" if (args.pick or want) else "available"
    print(f"{args.kind.upper()} signals dated {md} ({age}d old) - {len(chosen)} {label}" + ("" if (args.pick or want) else " (numbered):"))
    for t in chosen:
        print(f"  {t['no']:>2}) {t['side']:4} {t['symbol']:12} x{t['qty']:<4} ref Rs{t['ref_price']:<9} ~Rs{t['est_value']:<9} [{t['kind']}] {t['reason']}")
    for s, why in skipped:
        print(f"  skipped {s}: {why}")
    if args.pick or want:
        print(f"  total ~Rs{sum(t['est_value'] for t in chosen):,.2f}")
    print("TICKETS_JSON=" + json.dumps(chosen))


if __name__ == "__main__":
    main()
