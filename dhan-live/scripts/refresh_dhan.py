"""One-command refresh of the Dhan (dh252) snapshot - everything except the MCP pulls.

Steps (run from anywhere; paths are resolved relative to this repo):
  1. download backtester's latest market_screens_full / supertrend_full, then derive entry signals
     with the vendored copy of backtester's scripts/dh252_entry_screener.py
  2. rebuild daily closes + SMA50/200 from fresh yfinance history   (build_dh252_daily_closes.py)
  3. rebuild dhan_live_signals.json from holdings + trade log + the above (compute_dh252_live_signals.py)

It also runs crosscheck_signals.py (data/signal_crosscheck.json): Supertrend + closing high recomputed from complete Yahoo
history for every signal stock; build_order_ticket.py refuses to order a flagged signal.

The MCP-fed inputs must already be current before this runs (the refresh-dhan skill does that):
  data/holdings_snapshot.json   <- Dhan MCP holdings
  data/dh252_trade_log.json     <- fills (append_fills.py from MCP tradebook, or import_dhan_transactions.py from a CSV)

It also rebuilds covered_call_signals.json (Covered Call page) from data/cc_raw/*. If that prints CHAINS NEEDED,
save those option chains and re-run with --cc-only (reuses the cached Supertrend file, no re-download).

Usage:  python dhan-live/scripts/refresh_dhan.py [--skip-closes] [--cc-only] [--branch main]
Needs:  python 3.10+, pandas, yfinance.
"""

import argparse
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # dhan-live/
SCRIPTS = ROOT / "scripts"
DATA = ROOT / "data"
RAW = "https://raw.githubusercontent.com/vaijayanth/backtester/{branch}/{name}"
FILES = ["market_screens_full.json", "supertrend_full.json"]   # entry signals are derived locally below


def run(cmd):
    print("\n$", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--branch", default="main", help="backtester branch to read screens from")
    ap.add_argument("--skip-closes", action="store_true", help="reuse existing data/dh252_daily_closes.json")
    ap.add_argument("--cc-only", action="store_true", help="only rebuild covered_call_signals.json from the cached screens")
    args = ap.parse_args()

    py = sys.executable
    tmp = DATA / "cache"          # gitignored; keeps the last download so --cc-only can reuse it
    tmp.mkdir(exist_ok=True)
    cc = [py, SCRIPTS / "compute_covered_call.py", "--supertrend", tmp / "supertrend_full.json"]
    if args.cc_only:
        run(cc)
        return
    for name in FILES:
        url = RAW.format(branch=args.branch, name=name)
        print("fetching", url)
        urllib.request.urlretrieve(url, tmp / name)

    run([py, SCRIPTS / "dh252_entry_screener.py", "--market-screens", tmp / "market_screens_full.json",
         "--supertrend", tmp / "supertrend_full.json", "--out", tmp / "dh252_entry_signals.json"])
    if not args.skip_closes:
        run([py, SCRIPTS / "build_dh252_daily_closes.py",
             "--trade-log", DATA / "dh252_trade_log.json", "--out", DATA / "dh252_daily_closes.json"])
    run([py, SCRIPTS / "compute_dh252_live_signals.py",
         "--holdings", DATA / "holdings_snapshot.json",
         "--market-screens", tmp / "market_screens_full.json",
         "--supertrend", tmp / "supertrend_full.json",
         "--entry-signals", tmp / "dh252_entry_signals.json",
         "--trade-log", DATA / "dh252_trade_log.json",
         "--out", ROOT / "dhan_live_signals.json"])
    run([py, SCRIPTS / "crosscheck_signals.py"])   # recompute every signal on complete Yahoo data; flagged signals are blocked from orders
    run([py, SCRIPTS / "update_lot_sizes.py"])   # NSE's official lot file (best effort)
    run(cc)
    print("\nDone. Review `git diff --stat`, then commit dhan-live/ if the numbers look right.")


if __name__ == "__main__":
    main()
