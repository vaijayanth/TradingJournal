"""Record Zerodha trades made AFTER the baseline cut-off (the baseline itself is frozen from the sheet, see freeze_baseline.py).

The Zerodha MCP tradebook only returns today's trades, so what has to be remembered is kept here:
  buy     : a BUY fill (new entry or an add). Sets the position's last-buy date (the weekly add cooldown) and, for a stock not
            held at the cut-off, its entry date.
  pending : at exit PLACEMENT - captures the position's average cost while the holdings snapshot still has it.
  fill    : after the SELL fills - books the closed trade, profit = (exit price - average cost) x qty, gross of charges.
Data file: zerodha-live/data/zerodha_trades.json

Usage:
  python zerodha-live/scripts/zerodha_trades.py buy --symbol INFY --date 2026-11-10 [--entry]
  python zerodha-live/scripts/zerodha_trades.py pending --symbol INFY --qty 21 --avg-cost 1569.99 --date 2026-11-10 [--entry-date 2026-08-04]
  python zerodha-live/scripts/zerodha_trades.py fill --symbol INFY --qty 21 --price 1710.5 --date 2026-11-11
  python zerodha-live/scripts/zerodha_trades.py show
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

FILE = Path(__file__).resolve().parent.parent / "data" / "zerodha_trades.json"
EMPTY = {"_note": "Zerodha trades after the baseline cut-off. closed[] feeds the dashboard's realised P&L and trade count; last_buy{} drives the weekly add cooldown; entry_dates{} = entry date of positions opened after the cut-off.",
         "closed": [], "last_buy": {}, "entry_dates": {}, "pending_exits": []}


def load():
    return json.loads(FILE.read_text()) if FILE.exists() else json.loads(json.dumps(EMPTY))


def save(d):
    FILE.write_text(json.dumps(d, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["buy", "pending", "fill", "show"])
    ap.add_argument("--symbol")
    ap.add_argument("--qty", type=int)
    ap.add_argument("--avg-cost", type=float)
    ap.add_argument("--price", type=float)
    ap.add_argument("--date")
    ap.add_argument("--entry", action="store_true", help="buy: this opens a NEW position (not an add)")
    ap.add_argument("--entry-date", help="pending: the position's entry date (from the dashboard)")
    a = ap.parse_args()
    d = load()
    if a.cmd == "show":
        print(json.dumps(d, indent=1))
        return
    if not (a.symbol and a.date):
        print("REFUSED: --symbol and --date are required.")
        sys.exit(2)
    sym = a.symbol.upper()
    if a.cmd == "buy":
        d["last_buy"][sym] = max(a.date, d["last_buy"].get(sym, ""))
        if a.entry:
            d["entry_dates"][sym] = a.date
        save(d)
        print(f"buy recorded: {sym} {a.date}{' (new position)' if a.entry else ''}")
        return
    if a.cmd == "pending":
        if a.avg_cost is None or not a.qty or a.qty < 1:
            print("REFUSED: pending needs --qty and --avg-cost.")
            sys.exit(2)
        d["pending_exits"] = [p for p in d["pending_exits"] if p["symbol"] != sym]
        d["pending_exits"].append({"symbol": sym, "qty": a.qty, "avg_cost": a.avg_cost, "placed": a.date,
                                   "entry_date": a.entry_date or d["entry_dates"].get(sym)})
        save(d)
        print(f"pending exit recorded: {sym} x{a.qty} @ avg cost {a.avg_cost}")
        return
    pend = next((p for p in d["pending_exits"] if p["symbol"] == sym), None)
    if not pend:
        print(f"REFUSED: no pending exit recorded for {sym}; the average cost cannot be reconstructed after the holdings refresh. Record it with 'pending' first.")
        sys.exit(2)
    if a.price is None or a.qty != pend["qty"]:
        print(f"REFUSED: fill needs --price and a quantity equal to the pending {pend['qty']} (exits are whole-position).")
        sys.exit(2)
    pl = round((a.price - pend["avg_cost"]) * a.qty, 2)
    ent = pend.get("entry_date")
    d["closed"].append({"symbol": sym, "entry_date": ent, "exit_date": a.date, "qty": a.qty, "entry": pend["avg_cost"], "exit": a.price,
                        "pl_rs": pl, "pl_pct": round((a.price / pend["avg_cost"] - 1) * 100, 2),
                        "hold_days": (datetime.strptime(a.date, "%Y-%m-%d") - datetime.strptime(ent, "%Y-%m-%d")).days if ent else None})
    d["pending_exits"] = [p for p in d["pending_exits"] if p["symbol"] != sym]
    d["last_buy"].pop(sym, None)
    d["entry_dates"].pop(sym, None)
    save(d)
    print(f"closed trade recorded: {sym} P&L Rs{pl:,.2f}")


if __name__ == "__main__":
    main()
