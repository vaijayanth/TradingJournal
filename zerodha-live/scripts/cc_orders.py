"""Compact today's Zerodha MCP order list to the option orders (NFO) for the position scan.

Usage: python zerodha-live/scripts/cc_orders.py <raw orders list json file>
Writes data/cc_orders_today.json {fetched_at, orders[{order_id, tradingsymbol, side, qty, filled, pending, price, avg, status, message, gtt, time}]}.
scan_options.py uses it to see whether a GTT that fired produced a buy-back order and whether that order filled (COMPLETE) or failed (REJECTED / CANCELLED / still OPEN).
The Zerodha order list is today-only, so run this on the day you scan.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def main(path):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    raw = raw.get("data", raw) if isinstance(raw, dict) else raw
    out = []
    for o in raw:
        if o.get("exchange") != "NFO":
            continue
        out.append({"order_id": o.get("order_id"), "tradingsymbol": o.get("tradingsymbol"), "side": o.get("transaction_type"), "qty": o.get("quantity"),
                    "filled": o.get("filled_quantity"), "pending": o.get("pending_quantity"), "price": o.get("price"), "avg": o.get("average_price"),
                    "status": o.get("status"), "message": o.get("status_message") or o.get("status_message_raw") or "", "gtt": bool((o.get("meta") or {}).get("gtt")),
                    "time": o.get("order_timestamp")})
    ist = timezone(timedelta(hours=5, minutes=30))
    (DATA / "cc_orders_today.json").write_text(json.dumps({"fetched_at": datetime.now(ist).isoformat(timespec="seconds"), "orders": out}, indent=1))
    print(f"cc_orders_today.json: {len(out)} option orders ({sum(1 for o in out if o['gtt'])} placed by a GTT)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
