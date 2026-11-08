"""Append new equity fills (from the Dhan MCP tradebook) to the dh252 trade log.

The MCP tradebook only returns *today's* trades, so run the refresh each trading day (or the day's
fills are lost and you must fall back to a Global Transaction Report CSV + import_dhan_transactions.py).

Input is a JSON list the refresh-dhan skill builds from the tradebook output:
  [{"symbol": "TBZ", "date": "2026-11-09", "action": "BUY", "qty": 1, "price": 211.5,
    "order_id": "1234"}]            # "value" may be given instead of "price"; order_id is optional
Rules: equity only (no options), hedge-portfolio symbols are skipped, exact duplicates are skipped
(order_id + symbol + action + qty + value when present, else symbol + date + action + qty + value).

Usage: python dhan-live/scripts/append_fills.py <fills.json> [--trade-log dhan-live/data/dh252_trade_log.json]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from compute_dh252_live_signals import DHAN_OPTION_HEDGE_PORTFOLIO  # noqa: E402

DEFAULT_LOG = Path(__file__).resolve().parent.parent / "data" / "dh252_trade_log.json"


def key(f):
    return (f.get("order_id") or f["date"], f["symbol"], f["action"], f["qty"], round(f["value"], 2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fills_json")
    ap.add_argument("--trade-log", default=str(DEFAULT_LOG))
    args = ap.parse_args()

    new = json.loads(Path(args.fills_json).read_text())
    log_path = Path(args.trade_log)
    log = json.loads(log_path.read_text())
    fills = log.setdefault("fills", [])
    seen = {key(f) for f in fills}
    added, skipped = [], []
    for n in new:
        act = n["action"].upper()
        if act not in ("BUY", "SELL") or not n["qty"]:
            raise SystemExit(f"bad fill: {n}")
        value = n["value"] if "value" in n else n["price"] * n["qty"]
        f = {"symbol": n["symbol"], "date": n["date"], "action": act, "qty": int(n["qty"]),
             "price": round(value / n["qty"], 4), "value": round(value, 2),
             "source": "dhan_mcp_tradebook"}
        if n.get("order_id"):
            f["order_id"] = str(n["order_id"])
        if f["symbol"] in DHAN_OPTION_HEDGE_PORTFOLIO:
            skipped.append((f["symbol"], "hedge portfolio")); continue
        if key(f) in seen:
            skipped.append((f["symbol"], "duplicate")); continue
        seen.add(key(f)); fills.append(f); added.append(f)
    fills.sort(key=lambda f: f["date"])
    log_path.write_text(json.dumps(log, indent=2, ensure_ascii=False))
    print(f"added {len(added)} fills: {[(a['symbol'], a['action'], a['qty']) for a in added]}")
    print(f"skipped {len(skipped)}: {skipped}")


if __name__ == "__main__":
    main()
