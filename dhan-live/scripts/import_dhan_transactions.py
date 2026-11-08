"""Turn a Dhan "Global Transaction Report" CSV into the dh252 trade log's fills.

Scope rules (user decisions, 2026-11-08):
  * EQUITY ONLY - every row whose scrip name starts with "OPT " (index/stock options) is dropped.
  * The separate investment / option-hedge portfolio is excluded: the 11 named stocks, the liquid
    ETF that backs them, and every equity trade before the dh252 start date (those are sells of the
    old investment portfolio with no matching dh252 buy - e.g. Plastiblends, UCO Bank, Praj).
  * dh252 starts on --start (default 2026-10-21, the first day of its one-share-tier buys).

The report gives names, not NSE symbols. Symbols are resolved by (1) data/dhan_name_map.json,
(2) an unambiguous match of the name's net quantity + weighted-average cost to the live Dhan
holdings (holdings is the final reference), else the script stops and lists what to add to the
map - it never guesses.

Output replaces `fills` in the trade log with real dated BUY/SELL fills (exact add-on dates, real
exits). Closed trades, realised P&L, counts and the equity curve are all derived from these fills by
compute_dh252_live_signals.py, so there is a single source of truth.

Usage:
  python scripts/import_dhan_transactions.py --csv <report.csv> [--csv <older.csv> ...] \
    --holdings data/holdings_snapshot.json --trade-log data/dh252_trade_log.json
"""

import argparse
import csv
import json
from collections import OrderedDict
from pathlib import Path

# CSV scrip names of the investment / option-hedge portfolio (not dh252). Mirrors the symbol list in
# compute_dh252_live_signals.DHAN_OPTION_HEDGE_PORTFOLIO plus the liquid ETF behind it.
PORTFOLIO_NAMES = {
    "MCX", "Shriram Finance", "CG Power & Industrial Solutions", "BSE", "Dixon Technologies",
    "Zerodha Nifty 1D Rate Liquid ETF", "HCL Technologies", "Infosys",
    "Bank of India", "Bharat Petroleum Corporation", "BPCL", "Cummins India",
}


def iso(d):
    d = d.strip()[:10]
    if "-" in d and d[2] == "-":
        dd, mm, yy = d.split("-")
        return f"{yy}-{mm}-{dd}"
    return d


def read_rows(path):
    rows = list(csv.reader(open(path, encoding="utf-8-sig")))
    hi = next(i for i, r in enumerate(rows) if r and r[0] == "Date")
    return [r for r in rows[hi + 1:] if r and r[0][:2].isdigit()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", action="append", required=True)
    ap.add_argument("--holdings", required=True)
    ap.add_argument("--trade-log", required=True)
    ap.add_argument("--name-map", default=None)
    ap.add_argument("--start", default="2026-10-21")
    args = ap.parse_args()

    name_map_path = Path(args.name_map or Path(args.trade_log).parent / "dhan_name_map.json")
    name_map = json.loads(name_map_path.read_text()) if name_map_path.exists() else {}

    seen, fills = set(), []
    for path in args.csv:
        for r in read_rows(path):
            name = r[1]
            if name.startswith("OPT ") or name in PORTFOLIO_NAMES:
                continue
            key = tuple(r[:8])  # overlapping reports repeat identical rows - keep one
            if key in seen:
                continue
            seen.add(key)
            d = iso(r[0])
            if d < args.start:
                continue
            bq, bv, sq, sv = float(r[4]), float(r[5]), float(r[6]), float(r[7])
            if bq:
                fills.append({"name": name, "date": d, "action": "BUY", "qty": int(bq), "value": bv})
            if sq:
                fills.append({"name": name, "date": d, "action": "SELL", "qty": int(sq), "value": sv})
    fills.sort(key=lambda f: f["date"])

    by_name = OrderedDict()
    for f in fills:
        by_name.setdefault(f["name"], []).append(f)
    # A name with only SELLs inside the window is an old holding being sold, not a dh252 position.
    skipped_sell_only = [n for n, v in by_name.items() if all(x["action"] == "SELL" for x in v)]
    for n in skipped_sell_only:
        del by_name[n]

    holdings = {h["symbol"]: h for h in json.loads(Path(args.holdings).read_text())["holdings"]}
    used = set(name_map.values())
    unresolved = []
    for name, fl in by_name.items():
        if name in name_map:
            continue
        qty, wac = 0, 0.0
        for f in fl:
            if f["action"] == "BUY":
                wac = (wac * qty + f["value"]) / (qty + f["qty"]); qty += f["qty"]
            else:
                qty -= f["qty"]
        cand = [s for s, h in holdings.items() if qty > 0 and h["qty"] == qty and abs(h["avg_cost"] - wac) < 0.06 and s not in used]
        if len(cand) == 1:
            name_map[name] = cand[0]; used.add(cand[0])
        else:
            unresolved.append((name, qty, round(wac, 2), cand))
    if unresolved:
        print("UNRESOLVED names - add them to", name_map_path, "and re-run:")
        for u in unresolved:
            print("  ", u)
        raise SystemExit(1)

    out_fills = []
    for f in fills:
        if f["name"] not in name_map:
            continue
        out_fills.append({"symbol": name_map[f["name"]], "date": f["date"], "action": f["action"], "qty": f["qty"],
                          "price": round(f["value"] / f["qty"], 4), "value": round(f["value"], 2),
                          "source": "dhan_global_transaction_report"})

    log_path = Path(args.trade_log)
    log = json.loads(log_path.read_text())
    log["fills"] = out_fills
    log["fills_note"] = ("Real dated BUY/SELL fills imported from Dhan Global Transaction Report(s). Equity only; the option-hedge "
                         "portfolio and pre-" + args.start + " investment-portfolio sells are excluded. Closed trades, realised P&L "
                         "and counts are derived from these fills by compute_dh252_live_signals.py.")
    for k in ("closed_trades_count", "total_positions_ever_opened", "realized_pl_rs"):
        log.pop(k, None)  # derived from fills now
    log_path.write_text(json.dumps(log, indent=2, ensure_ascii=False))
    name_map_path.write_text(json.dumps(dict(sorted(name_map.items())), indent=2, ensure_ascii=False))

    syms = {f["symbol"] for f in out_fills}
    print(f"{len(out_fills)} equity fills for {len(syms)} symbols written to {log_path}")
    print(f"skipped (sell-only, old holdings): {skipped_sell_only or 'none'}")
    print(f"name map: {len(name_map)} entries -> {name_map_path}")


if __name__ == "__main__":
    main()
