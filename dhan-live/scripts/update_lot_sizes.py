"""Download NSE's official F&O lot-size file and store per-expiry-month lots for the Covered Call universe.

Source: https://nsearchives.nseindia.com/content/fo/fo_mktlots.csv (one row per underlying, one column per
expiry month; lot sizes can change between series - e.g. INFY 400 -> 500 from Jan-27 - so they are kept per month).
Output: data/nse_lots.json  {"fetched_at", "lots": {"INFY": {"2026-11": 400, "2026-12": 400, "2027-01": 500}, ...}}
Best effort: if the download fails the existing file (and cc_config.json's fallback lots) stay in use.

Usage: python dhan-live/scripts/update_lot_sizes.py
"""
import csv
import io
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
URL = "https://nsearchives.nseindia.com/content/fo/fo_mktlots.csv"
MONTHS = {m: i for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}


def main():
    cfg = json.loads((DATA / "cc_config.json").read_text())
    want = set(cfg["universe"])
    try:
        req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
        text = urllib.request.urlopen(req, timeout=30).read().decode("utf-8-sig")
    except Exception as e:  # noqa: BLE001
        print("WARNING: could not download NSE lot sizes (" + str(e) + ") - keeping the existing file / config fallback")
        return 0
    rows = list(csv.reader(io.StringIO(text)))
    head = [h.strip() for h in rows[0]]
    cols = {}
    for i, h in enumerate(head[2:], 2):          # "NOV-26" -> "2026-11"
        mon, yy = h.split("-")
        cols[i] = f"20{yy}-{MONTHS[mon]:02d}"
    lots = {}
    for r in rows[1:]:
        if len(r) > 2 and r[1].strip() in want:
            lots[r[1].strip()] = {cols[i]: int(r[i]) for i in cols if i < len(r) and r[i].strip().isdigit()}
    missing = sorted(want - set(lots))
    (DATA / "nse_lots.json").write_text(json.dumps(
        {"fetched_at": datetime.now(timezone.utc).isoformat(), "source": URL, "lots": lots}, indent=1))
    print(f"lot sizes for {len(lots)}/{len(want)} symbols written to data/nse_lots.json" + (f"; missing: {missing}" if missing else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
