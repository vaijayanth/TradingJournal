"""Fetch daily closes for every dh252 position, from the earliest entry date to today, so the
engine can rebuild the equity curve day by day (market value - cost for each open position).

Why this exists: backtester's OHLC cache lags the real market date, and the Dhan MCP tradebook only
returns today's trades - neither can reconstruct how the P&L developed between entry and today.
Source is Yahoo Finance (the same source the backtester's own price cache is built from); NSE
symbols are fetched as <SYMBOL>.NS. Output is a small committed file the engine reads offline.

Usage:
  python scripts/build_dh252_daily_closes.py \
    --trade-log data/dh252_trade_log.json --out data/dh252_daily_closes.json
"""

import argparse
import json
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path

warnings.filterwarnings("ignore")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trade-log", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    import yfinance as yf

    log = json.loads(Path(args.trade_log).read_text())
    fills = log.get("fills", [])
    symbols = sorted({f["symbol"] for f in fills})
    first_entry = min(f["date"] for f in fills)
    # start a few days before the first entry so the curve opens flat at the starting capital
    start = (datetime.strptime(first_entry, "%Y-%m-%d") - timedelta(days=5)).strftime("%Y-%m-%d")

    df = yf.download([s + ".NS" for s in symbols], start=start, progress=False, auto_adjust=False, threads=True)["Close"]
    # Weekend rows can appear as a copy of Friday - keep real trading days only
    df = df[df.index.dayofweek < 5].dropna(how="all")

    closes = {}
    for s in symbols:
        col = s + ".NS"
        if col not in df or df[col].isna().all():
            continue
        closes[s] = [None if v != v else round(float(v), 2) for v in df[col].tolist()]

    out = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": "yfinance (NSE, unadjusted close)",
        "dates": [d.strftime("%Y-%m-%d") for d in df.index],
        "closes": closes,
        "missing_symbols": [s for s in symbols if s not in closes],
    }
    Path(args.out).write_text(json.dumps(out, indent=1))
    print(f"{len(closes)}/{len(symbols)} symbols, {len(out['dates'])} trading days "
          f"({out['dates'][0]} -> {out['dates'][-1]}); missing: {out['missing_symbols'] or 'none'}")


if __name__ == "__main__":
    main()
