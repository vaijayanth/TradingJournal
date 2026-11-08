"""Compact the raw Zerodha MCP get_positions output into the covered call's open option legs.

Usage: python zerodha-live/scripts/cc_positions.py <raw get_positions json file>
Keeps only stock-option legs (NFO, non-index, non-zero net quantity) in F&O universe stocks whose expiry is on/after
`track_from` in data/cc_config.json (user, 2026-11-09: only December-onwards options count; earlier ones are ignored).
Writes data/cc_positions.json {fetched_at, track_from, legs[], ignored_legs}. Prices come from the positions call itself
(last_price, pnl); no option quotes are pulled.
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
RX = re.compile(r"^(.+?)(\d\d)([A-Z]{3})(\d+(?:\.\d+)?)(CE|PE)$")
INDEX = ("NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY")
MON = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def main(path):
    cfg = json.loads((DATA / "cc_config.json").read_text())
    track_from = cfg["track_from"]
    uni = set(json.loads((DATA / "fno_universe.json").read_text())["symbols"])
    master = json.loads((DATA / "nfo_options.json").read_text())["symbols"]
    exp_by = {e[2:4] + MON[int(e[5:7]) - 1]: e for s in master.values() for e in s["lot"]}
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    raw = raw.get("data", raw) if isinstance(raw, dict) else raw
    legs, ignored = [], 0
    for x in raw:
        if x.get("exchange") != "NFO" or not x.get("quantity"):
            continue
        m = RX.match(x["tradingsymbol"])
        if not m or m.group(1).startswith(INDEX) or m.group(1) not in uni:
            ignored += 1
            continue
        sym, yy, mon, strike, typ = m.groups()
        exp = exp_by.get(yy + mon)
        if not exp:  # an expiry the instrument list no longer has: the contract is past, not tracked
            ignored += 1
            continue
        if exp < track_from:
            ignored += 1
            continue
        legs.append({"symbol": sym, "expiry": exp, "strike": float(strike), "type": typ,
                     "side": "SHORT" if x["quantity"] < 0 else "LONG", "qty": abs(x["quantity"]),
                     "avg": x["average_price"], "ltp": x["last_price"], "pnl_rs": x["pnl"], "tradingsymbol": x["tradingsymbol"]})
    (DATA / "cc_positions.json").write_text(json.dumps({"fetched_at": datetime.now(timezone.utc).isoformat(), "track_from": track_from,
                                                        "legs": legs, "ignored_legs": ignored}, indent=1))
    print(f"cc_positions.json: {len(legs)} option legs from {track_from} onwards tracked, {ignored} other option legs ignored")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
