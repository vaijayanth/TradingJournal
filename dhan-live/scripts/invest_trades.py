"""Ledger of INVESTMENT-portfolio share trades (the covered-call universe), used to size the next entry.

Strategy (user, 2026-11-08):
  exit  : Supertrend red AND the position is in profit -> sell the whole position.
  entry : Supertrend flips red -> green (not held) -> buy with the LAST entry position's capital PLUS the profit earned
          on that same stock from the previous trade (profit is reinvested).
  avg   : once a week, Supertrend green and the open position's loss is worse than -6% (1/10 of the holding).

A closed trade needs two facts: the capital that was in the position and the profit it made. They are recorded here:
  pending : at exit PLACEMENT - captures the capital (qty x average cost) while the holdings snapshot still has it.
  fill    : after the SELL fills (next trading day) - captures the real exit price and books profit = (price - avg cost) x qty.
Profit is gross of charges. Data file: dhan-live/data/invest_trades.json

Usage:
  python dhan-live/scripts/invest_trades.py pending --symbol INFY --qty 21 --avg-cost 1569.99 --date 2026-11-09
  python dhan-live/scripts/invest_trades.py fill --symbol INFY --qty 21 --price 1710.50 --date 2026-11-10
  python dhan-live/scripts/invest_trades.py show
"""
import argparse
import json
import sys
from pathlib import Path

FILE = Path(__file__).resolve().parent.parent / "data" / "invest_trades.json"
EMPTY = {"_note": "Investment-portfolio share trades. closed[] feeds the next entry's size (capital + profit of the previous trade on the same stock); pending_exits[] = exit orders placed but not yet filled. Profit is gross of charges. Written by scripts/invest_trades.py.",
         "closed": [], "pending_exits": []}


def load():
    return json.loads(FILE.read_text()) if FILE.exists() else json.loads(json.dumps(EMPTY))


def save(d):
    FILE.write_text(json.dumps(d, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["pending", "fill", "show"])
    ap.add_argument("--symbol")
    ap.add_argument("--qty", type=int)
    ap.add_argument("--avg-cost", type=float)
    ap.add_argument("--price", type=float)
    ap.add_argument("--date")
    a = ap.parse_args()
    d = load()
    if a.cmd == "show":
        print(json.dumps(d, indent=1))
        return
    if not (a.symbol and a.qty and a.date):
        print("REFUSED: --symbol, --qty and --date are required.")
        sys.exit(2)
    sym = a.symbol.upper()
    if a.cmd == "pending":
        if a.avg_cost is None or a.qty < 1:
            print("REFUSED: pending needs --avg-cost and a quantity of at least 1.")
            sys.exit(2)
        d["pending_exits"] = [p for p in d["pending_exits"] if p["symbol"] != sym]
        d["pending_exits"].append({"symbol": sym, "qty": a.qty, "avg_cost": a.avg_cost, "capital": round(a.qty * a.avg_cost, 2), "placed": a.date})
        save(d)
        print(f"pending exit recorded: {sym} x{a.qty} capital Rs{a.qty * a.avg_cost:,.2f}")
        return
    # fill
    pend = next((p for p in d["pending_exits"] if p["symbol"] == sym), None)
    if not pend:
        print(f"REFUSED: no pending exit recorded for {sym}; the capital cannot be reconstructed after the holdings refresh. Record it with 'pending' first.")
        sys.exit(2)
    if a.price is None:
        print("REFUSED: fill needs --price (the actual average exit price).")
        sys.exit(2)
    if a.qty != pend["qty"]:
        print(f"REFUSED: filled quantity {a.qty} differs from the pending {pend['qty']}; exits are whole-position - check the tradebook.")
        sys.exit(2)
    profit = round((a.price - pend["avg_cost"]) * a.qty, 2)
    d["closed"].append({"symbol": sym, "exit_date": a.date, "qty": a.qty, "avg_cost": pend["avg_cost"], "exit_price": a.price,
                        "capital": pend["capital"], "profit": profit})
    d["pending_exits"] = [p for p in d["pending_exits"] if p["symbol"] != sym]
    save(d)
    print(f"closed trade recorded: {sym} capital Rs{pend['capital']:,.2f} profit Rs{profit:,.2f} -> next entry sized at Rs{pend['capital'] + profit:,.2f}")


if __name__ == "__main__":
    main()
