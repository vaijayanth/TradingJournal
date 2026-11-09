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
    active, gtts, other = {}, [], 0
    for g in raw:
        if g.get("status") != "active":
            continue
        c = g.get("condition", {})
        if c.get("exchange") != "NFO":
            other += 1   # stock GTTs (NSE / BSE) are not part of the option checks
            continue
        orders = [{"side": o.get("transaction_type"), "qty": o.get("quantity"), "price": o.get("price"), "product": o.get("product"), "order_type": o.get("order_type")} for o in g.get("orders", [])]
        gtts.append({"id": g["id"], "type": g.get("type"), "created_at": g.get("created_at"), "expires_at": g.get("expires_at"), "tradingsymbol": c["tradingsymbol"],
                     "last_price": c.get("last_price"), "triggers": c.get("trigger_values"), "orders": orders})
        for o in g.get("orders", []):
            if o.get("transaction_type") == "BUY":
                active.setdefault(c["tradingsymbol"], []).append({"id": g["id"], "type": g.get("type"), "trigger_values": c.get("trigger_values"), "qty": o.get("quantity")})
    ist = timezone(timedelta(hours=5, minutes=30))
    (DATA / "cc_gtts.json").write_text(json.dumps({"fetched_at": datetime.now(ist).isoformat(timespec="seconds"), "active": active, "gtts": gtts, "non_option_gtts": other}, indent=1))
    print(f"cc_gtts.json: active buy GTTs on {len(active)} option contracts")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
