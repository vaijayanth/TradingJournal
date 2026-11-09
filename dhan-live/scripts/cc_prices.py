"""Save live stock prices for the covered call's strike alerts (ND).

Usage: python dhan-live/scripts/cc_prices.py <raw market_data ltp text file>
Raw = the Dhan MCP market_data_agent_tool `ltp` result for {"NSE_EQ": [<security_id of every covered-call universe stock>]}
(ids in data/cc_config.json -> universe). Writes data/cc_live_prices.json {fetched_at, prices{SYMBOL: ltp}}.
compute_covered_call.py uses them (same IST day only) for the near/breached strike alerts and leg distances.
"""
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def main(path):
    uni = json.loads((DATA / "cc_config.json").read_text())["universe"]
    by_id = {str(v["security_id"]): k for k, v in uni.items()}
    prices = {}
    for sid, px in re.findall(r"(\d+):\s*LTP\s*₹?([\d,]+(?:\.\d+)?)", Path(path).read_text(encoding="utf-8")):
        if sid in by_id:
            prices[by_id[sid]] = float(px.replace(",", ""))
    ist = timezone(timedelta(hours=5, minutes=30))
    (DATA / "cc_live_prices.json").write_text(json.dumps({"fetched_at": datetime.now(ist).isoformat(timespec="seconds"), "prices": prices}, indent=1))
    miss = sorted(set(uni) - set(prices))
    print(f"cc_live_prices.json: {len(prices)} prices" + (f"; MISSING {miss}" if miss else ""))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
