"""Download NSE's daily F&O ban list (securities in the ban period) and save it.

Usage: python zerodha-live/scripts/fetch_fno_ban.py
Source: https://nsearchives.nseindia.com/content/fo/fo_secban.csv (published each evening for the next trade date).
Writes data/fno_ban.json {fetched_at, trade_date, symbols[], source, ok}. A failure keeps the old file and says so (ok false);
it never raises, so a refresh is never blocked by it. Each broker folder has its own copy (no shared code).
Ban period = open interest above 95% of the market-wide position limit: no NEW positions in the stock, only reducing trades.
"""
import json
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

URL = "https://nsearchives.nseindia.com/content/fo/fo_secban.csv"
OUT = Path(__file__).resolve().parent.parent / "data" / "fno_ban.json"
IST = timezone(timedelta(hours=5, minutes=30))


def parse(text):
    """-> (trade_date 'DD-MMM-YYYY' or None, [symbols])"""
    m = re.search(r"Trade Date\s+(\d{1,2}-[A-Za-z]{3}-\d{4})", text)
    syms = []
    for line in text.splitlines():
        p = [x.strip() for x in line.split(",")]
        if len(p) >= 2 and p[0].isdigit() and p[1]:
            syms.append(p[1].upper())
    return (m.group(1) if m else None), syms


def main():
    now = datetime.now(IST).isoformat(timespec="seconds")
    try:
        req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.nseindia.com/"})
        text = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
        date, syms = parse(text)
        out = {"ok": True, "fetched_at": now, "trade_date": date, "symbols": syms, "source": URL}
        OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
        print(f"F&O ban list for {date}: {', '.join(syms) if syms else 'none'}")
    except Exception as e:  # noqa: BLE001 - never block a refresh
        old = {}
        try:
            old = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
        old.update({"ok": False, "error": str(e)[:160], "checked_at": now})
        OUT.write_text(json.dumps(old, indent=1), encoding="utf-8")
        print(f"WARNING: could not fetch the F&O ban list ({str(e)[:100]}); keeping the previous file", file=sys.stderr)


if __name__ == "__main__":
    main()
