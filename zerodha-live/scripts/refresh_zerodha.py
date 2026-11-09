"""One-command refresh of the Zerodha (Nifty F&O) snapshot - everything except the MCP pulls.

Steps (run from anywhere; paths are resolved relative to this repo):
  1. refresh the Nifty F&O stock list when the stored one is from a previous month (NSE's official lot file)
  2. download the backtester's latest market_screens_full / supertrend_full (Supertrend, closes, RSI for ~1,500 stocks)
  3. rebuild zerodha_live_signals.json from the holdings snapshot + frozen sheet baseline + trades since the cut-off
  4. cross-check every signal against complete Yahoo history (data/signal_crosscheck.json)

The MCP-fed inputs must already be current before this runs (the refresh-zerodha skill does that):
  data/holdings_snapshot.json   <- Zerodha MCP get_holdings (quantity + t1_quantity, average_price)
  data/zerodha_trades.json      <- trades since the cut-off (zerodha_trades.py)

Usage:  python zerodha-live/scripts/refresh_zerodha.py [--branch main]
Needs:  python 3.10+.
"""
import argparse
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # zerodha-live/
SCRIPTS = ROOT / "scripts"
DATA = ROOT / "data"
RAW = "https://raw.githubusercontent.com/vaijayanth/backtester/{branch}/{name}"
FILES = ["market_screens_full.json", "supertrend_full.json"]


def run(cmd):
    print("\n$", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--branch", default="main", help="backtester branch to read screens from")
    args = ap.parse_args()
    py = sys.executable
    cache = DATA / "cache"
    cache.mkdir(exist_ok=True)
    run([py, SCRIPTS / "update_fno_universe.py"])                      # no-op unless the stored list is from an earlier month
    for name in FILES:
        url = RAW.format(branch=args.branch, name=name)
        print("fetching", url)
        urllib.request.urlretrieve(url, cache / name)
    run([py, SCRIPTS / "compute_zerodha_live_signals.py",
         "--holdings", DATA / "holdings_snapshot.json",
         "--market-screens", cache / "market_screens_full.json",
         "--supertrend", cache / "supertrend_full.json",
         "--out", ROOT / "zerodha_live_signals.json"])
    # recompute every signal on complete Yahoo data (flip mode); flagged signals are blocked from orders
    run([py, SCRIPTS / "crosscheck_signals.py", "--mode", "flip",
         "--signals", ROOT / "zerodha_live_signals.json", "--out", DATA / "signal_crosscheck.json"])
    # covered call (signals only): lot sizes / expiries from Zerodha's public instrument list, then the rule per stock
    run([py, SCRIPTS / "update_options_master.py"])
    run([py, SCRIPTS / "compute_covered_call.py"])
    run([py, SCRIPTS / "guardrails.py"])          # checks and balances over everything above
    run([py, SCRIPTS / "test_guardrails.py"])     # the checks themselves must still fire
    print("\nDone. Review `git diff --stat`, then commit zerodha-live/ if the numbers look right.")


if __name__ == "__main__":
    main()
