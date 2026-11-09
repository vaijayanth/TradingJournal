"""Save live stock prices for the covered call's strike alerts.

Usage: python zerodha-live/scripts/cc_prices.py <raw get_ltp json file>
The raw file is the Zerodha MCP get_ltp output for NSE:<SYMBOL> of every stock with an open option leg (data/cc_positions.json).
Writes data/cc_live_prices.json {fetched_at, prices{SYMBOL: ltp}}. compute_covered_call.py uses these (when they are from the
same day) instead of the last close for 'near / breached' strike alerts; everything else keeps using the end-of-day signals.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def main(path):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    raw = raw.get("data", raw)
    prices = {k.split(":", 1)[1]: v["last_price"] for k, v in raw.items() if v.get("last_price")}
    ist = timezone(timedelta(hours=5, minutes=30))
    (DATA / "cc_live_prices.json").write_text(json.dumps({"fetched_at": datetime.now(ist).isoformat(timespec="seconds"), "prices": prices}, indent=1))
    print(f"cc_live_prices.json: {len(prices)} prices")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
