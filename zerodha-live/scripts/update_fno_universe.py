"""Download the current Nifty F&O stock list (NSE's official monthly lot file) -> zerodha-live/data/fno_universe.json.

Source: https://nsearchives.nseindia.com/content/fo/fo_mktlots.csv - one row per F&O underlying. Index underlyings (NIFTY,
BANKNIFTY, ...) are dropped; what is left is the stock universe for the Zerodha entry / exit signals. The list changes when
NSE adds or removes stocks, so /refresh-zerodha re-downloads it whenever the stored list is from a previous month.
Best effort: if the download fails the existing file stays in use and a warning is printed.

Usage: python zerodha-live/scripts/update_fno_universe.py [--force]
"""
import argparse
import csv
import io
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "fno_universe.json"
URL = "https://nsearchives.nseindia.com/content/fo/fo_mktlots.csv"
INDEX_UNDERLYINGS = {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50", "NIFTYIT", "NIFTYPVTBANK"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-download even if this month's list already exists")
    args = ap.parse_args()
    now = datetime.now(timezone.utc)
    month = now.strftime("%Y-%m")
    if OUT.exists() and not args.force:
        cur = json.loads(OUT.read_text())
        if cur.get("month") == month:
            print(f"F&O universe for {month} already stored ({len(cur['symbols'])} stocks) - nothing to do")
            return 0
    try:
        req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
        text = urllib.request.urlopen(req, timeout=30).read().decode("utf-8-sig")
    except Exception as e:  # noqa: BLE001
        print("WARNING: could not download the NSE F&O list (" + str(e) + ") - keeping the existing file")
        return 0
    rows = list(csv.reader(io.StringIO(text)))
    # The file has an index section first, then a section header row ("Derivatives on Individual Securities", "Symbol", ...)
    # followed by the stocks. Take only the rows after that header; that excludes every index (NIFTY, NIFTYFPI, ...) and the
    # header itself, which an earlier version wrongly kept as a stock called "Symbol".
    start = next((i for i, r in enumerate(rows) if len(r) > 2 and r[1].strip().lower() == "symbol" and "individual" in r[0].lower()), None)
    if start is None:
        print("WARNING: could not find the stock section of the NSE file - keeping the existing universe")
        return 0
    syms = sorted({r[1].strip() for r in rows[start + 1:] if len(r) > 2 and r[1].strip() and r[1].strip().upper() not in INDEX_UNDERLYINGS})
    old = set(json.loads(OUT.read_text()).get("symbols", [])) if OUT.exists() else set()
    OUT.write_text(json.dumps({"month": month, "fetched_at": now.isoformat(), "source": URL, "count": len(syms), "symbols": syms}, indent=1))
    print(f"F&O universe {month}: {len(syms)} stocks written" + (f"; added {sorted(set(syms) - old)} removed {sorted(old - set(syms))}" if old else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
