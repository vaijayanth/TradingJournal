"""Build SHARE order tickets for the Dhan INVESTMENT portfolio (the 10 covered-call stocks) from covered_call_signals.json.

Separate from build_order_ticket.py, which is dh252 only and refuses these stocks. Shares only - never options.

Strategy (user, 2026-11-08):
  exit  : Supertrend red AND the position is in profit -> sell the WHOLE position. Quantity = shares held; never partial.
  entry : Supertrend flips red -> green on a stock you do not hold -> buy with the last position's capital PLUS the profit
          earned on that stock in the previous trade (data/invest_trades.json), floored to whole shares (minimum 1).
          If no previous trade is recorded for the stock, the rules give no size: --qty SYMBOL=N is REQUIRED, never guessed.
  add   : averaging - Supertrend green, loss worse than -6% vs average cost, once every 7 days. Quantity = 1/10 of the holding.

Usage:
  python dhan-live/scripts/build_share_ticket.py exit|entry|add               # numbered list
  python dhan-live/scripts/build_share_ticket.py exit --pick 1
  python dhan-live/scripts/build_share_ticket.py entry --pick 1 [--qty HCLTECH=5]   # --qty only when no previous trade exists
Exit code 2 = refuse (stale data, stock outside the universe, bad pick or quantity). Prints a final TICKETS_JSON= line.
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


def parse_qty(text):
    out = {}
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            print(f"REFUSED: --qty needs SYMBOL=N, got '{part}'.")
            sys.exit(2)
        k, v = part.split("=", 1)
        try:
            n = int(v)
        except ValueError:
            print(f"REFUSED: quantity for {k} must be a whole number, got '{v}'.")
            sys.exit(2)
        if n < 1:
            print(f"REFUSED: quantity for {k} must be at least 1.")
            sys.exit(2)
        out[k.strip().upper()] = n
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["add", "entry", "exit"])
    ap.add_argument("--pick", default="", help="numbers from the printed list, e.g. 1,3")
    ap.add_argument("--qty", default="", help="SYMBOL=N,... required for entry and exit")
    ap.add_argument("--signals", default=str(ROOT / "covered_call_signals.json"))
    args = ap.parse_args()

    cc = json.loads(Path(args.signals).read_text())
    md = cc.get("market_data_date")
    age = (date.today() - datetime.strptime(md, "%Y-%m-%d").date()).days if md else None
    if age is None or age > MAX_STALE_DAYS:
        print(f"REFUSED: covered-call data is {age} days old (market data {md}); run /refresh-dhan first.")
        sys.exit(2)

    universe = {s["symbol"] for s in cc.get("stocks", [])}
    rows = {r["symbol"]: r for r in cc.get("shares", {}).get("rows", [])}
    stocks = {s["symbol"]: s for s in cc.get("stocks", [])}
    qty_in = parse_qty(args.qty)
    bad = sorted(set(qty_in) - universe)
    if bad:
        print(f"REFUSED: {bad} are not in the investment-portfolio universe {sorted(universe)} - nothing is placed for other stocks.")
        sys.exit(2)

    cands = []
    sh = cc.get("shares", {})
    if args.kind == "add":
        for sym, r in rows.items():
            if r.get("avg_status") == "ADD":
                cands.append({"symbol": sym, "side": "BUY", "qty": int(r["add_qty"]), "ref_price": r["spot"], "held": r["qty"],
                              "reason": f"averaging: P&L {r['pl_pct']:.1f}% vs average cost, Supertrend green, {r.get('avg_note')}"})
    elif args.kind == "entry":
        for e in sh.get("entries", []):
            cands.append({"symbol": e["symbol"], "side": "BUY", "qty": e.get("qty_to_buy"), "ref_price": e["spot"], "held": 0,
                          "reason": f"red to green flip {e['flip_date']} ({e['flip_trading_days']} trading days ago); {e.get('sizing_note')}",
                          "entry_capital": e.get("entry_capital"), "sized_from_history": e.get("qty_to_buy") is not None})
    else:  # exit: Supertrend red and in profit -> the whole position
        for e in sh.get("exits", []):
            cands.append({"symbol": e["symbol"], "side": "SELL", "qty": int(e["qty"]), "ref_price": e["spot"], "held": e["qty"],
                          "avg_cost": e["avg_cost"], "capital": e["invested"], "profit_est": e["pl_rs"],
                          "reason": f"Supertrend red since {e['flip_date']}, in profit {e['pl_pct']:.1f}% ({e['pl_rs']:,.0f} Rs) - sell the whole position"})
    for i, c in enumerate(cands, 1):
        c["no"] = i

    chosen = cands
    if args.pick:
        nums = parse_pick(args.pick, len(cands))
        chosen = [c for c in cands if c["no"] in nums]

    tickets, warnings = [], []
    for c in chosen:
        sym = c["symbol"]
        if args.pick and args.kind == "entry":
            if c["qty"] is None:
                if sym not in qty_in:
                    print(f"REFUSED: no previous trade is recorded for {sym}, so the entry size is undefined - give --qty {sym}=N.")
                    sys.exit(2)
                c["qty"] = qty_in[sym]
            elif sym in qty_in and qty_in[sym] != c["qty"]:
                print(f"REFUSED: {sym} is sized by the rule at {c['qty']} shares (previous capital + profit); a different quantity is not allowed.")
                sys.exit(2)
        if args.kind == "exit" and args.pick:
            if sym in qty_in and qty_in[sym] != c["qty"]:
                print(f"REFUSED: exits are the whole position ({c['qty']} {sym}); partial sells are out of scope.")
                sys.exit(2)
            st = stocks.get(sym, {})
            short_ce = sum(l.get("qty", 0) for l in st.get("legs", []) if l.get("type") == "CE" and l.get("side") == "SHORT")
            c["short_call_qty"] = short_ce
            if short_ce and c["held"] >= short_ce:
                warnings.append(f"WARNING {sym}: the {short_ce} short call quantity is covered by your {c['held']} shares today; selling them all leaves the call uncovered. Check the option legs.")
            elif short_ce:
                warnings.append(f"NOTE {sym}: an open short call of {short_ce} shares already exceeds the {c['held']} shares held; check the option legs before selling.")
        if c["qty"] is not None:
            c["est_value"] = round(c["qty"] * c["ref_price"], 2)
        c["market_data_date"] = md
        tickets.append(c)

    label = "selected" if args.pick else "available"
    print(f"SHARE {args.kind.upper()} - investment portfolio, data {md} ({age}d old) - {len(tickets)} {label}" + ("" if args.pick else " (numbered):"))
    for c in tickets:
        q = f"x{c['qty']}" if c["qty"] is not None else "x?"
        v = f"~Rs{c['est_value']}" if c.get("est_value") is not None else ""
        print(f"  {c['no']:>2}) {c['side']:4} {c['symbol']:11} {q:<6} ref Rs{c['ref_price']:<9} {v:<12} held {c['held']:<5} {c['reason']}")
    for w in warnings:
        print("  " + w)
    if args.pick:
        print(f"  total ~Rs{sum(c.get('est_value') or 0 for c in tickets):,.2f}")
    print("TICKETS_JSON=" + json.dumps(tickets))


if __name__ == "__main__":
    main()
