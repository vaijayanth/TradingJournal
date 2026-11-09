"""Compact the Zerodha MCP get_gtts output: which option contracts already have an ACTIVE buy-back GTT (the 3x-premium stop).

Usage: python zerodha-live/scripts/cc_gtts.py <raw get_gtts json file>
Writes data/cc_gtts.json {fetched_at, active{tradingsymbol: [{id, type, trigger_values, qty}]}}; compute_covered_call.py raises
'No GTT placed' for every short option leg with no active BUY GTT on its contract.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def main(path):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    raw = raw.get("data", raw) if isinstance(raw, dict) else raw
    active = {}
    for g in raw:
        if g.get("status") != "active":
            continue
        c = g.get("condition", {})
        for o in g.get("orders", []):
            if o.get("transaction_type") == "BUY" and c.get("exchange") == "NFO":
                active.setdefault(c["tradingsymbol"], []).append({"id": g["id"], "type": g.get("type"), "trigger_values": c.get("trigger_values"), "qty": o.get("quantity")})
    ist = timezone(timedelta(hours=5, minutes=30))
    (DATA / "cc_gtts.json").write_text(json.dumps({"fetched_at": datetime.now(ist).isoformat(timespec="seconds"), "active": active}, indent=1))
    print(f"cc_gtts.json: active buy GTTs on {len(active)} option contracts")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
