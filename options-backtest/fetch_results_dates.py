"""Fetch historical quarterly-results dates per Nifty F&O stock from Yahoo (yfinance get_earnings_dates) into data/results_dates.json.
Usage: python options-backtest/fetch_results_dates.py
Coverage is uneven (older history is thin for some stocks); the backtest reports how many entries had usable coverage."""
import json
from pathlib import Path

import pandas as pd
import yfinance as yf

HERE = Path(__file__).resolve().parent
excl = set(json.loads((HERE.parent / "zerodha-live" / "data" / "excluded_symbols.json").read_text())["symbols"])
names = [n for n in json.loads((HERE.parent / "zerodha-live" / "data" / "fno_universe.json").read_text())["symbols"] if n not in excl]
out = {}
for i, n in enumerate(names, 1):
    try:
        d = yf.Ticker(n + ".NS").get_earnings_dates(limit=30)
        out[n] = sorted({x.tz_convert("Asia/Kolkata").strftime("%Y-%m-%d") for x in d.index}) if d is not None and len(d) else []
    except Exception as e:
        out[n] = []
    if i % 20 == 0:
        print(i, len(names), flush=True)
(HERE / "data").mkdir(exist_ok=True)
(HERE / "data" / "results_dates.json").write_text(json.dumps(out))
have = sum(1 for v in out.values() if v)
print("stocks with dates:", have, "of", len(out))
