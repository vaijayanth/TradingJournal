"""Turn the manually keyed ICICIdirect option positions (data/positions_manual.json) into data/cc_positions.json (the format compute_covered_call.py reads).

ICICIdirect has no MCP connector, so the positions come from a screen paste the user shares; Claude keys the rows into positions_manual.json
([symbol, expiry, strike, CE/PE, LONG/SHORT, qty, avg price, ltp, stop trigger or null, P&L Rs]). The stop trigger is the 'Trigger Price' column of the screen.
Usage: python icici-live/scripts/import_positions.py
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
MONTH = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()


def main():
    src = json.loads((DATA / "positions_manual.json").read_text(encoding="utf-8"))
    track_from = json.loads((DATA / "cc_config.json").read_text(encoding="utf-8")).get("track_from", "1970-01-01")
    legs, ignored = [], 0
    for sym, exp, strike, typ, side, qty, avg, ltp, trig, pnl in src["rows"]:
        if exp < track_from:
            ignored += 1
            continue
        y, m, d = exp.split("-")
        leg = {"symbol": sym, "expiry": exp, "strike": float(strike), "type": typ, "side": side, "qty": qty, "avg": avg, "ltp": ltp, "pnl_rs": pnl,
               "tradingsymbol": f"{sym}{y[2:]}{MONTH[int(m) - 1]}{strike:g}{typ}"}
        if trig is not None:
            leg["stop_trigger"] = trig
        legs.append(leg)
    ist = timezone(timedelta(hours=5, minutes=30))
    out = {"_note": "Keyed by hand from the ICICIdirect positions screen (no MCP connector); see positions_manual.json.", "source": "manual ICICIdirect positions screen",
           "as_of": src.get("as_of"), "fetched_at": datetime.now(ist).isoformat(timespec="seconds"), "track_from": track_from, "ignored_legs": ignored, "legs": legs}
    (DATA / "cc_positions.json").write_text(json.dumps(out, indent=1))
    shorts = sum(1 for l in legs if l["side"] == "SHORT")
    print(f"cc_positions.json: {len(legs)} option legs ({shorts} short, {len(legs) - shorts} long) on {len({l['symbol'] for l in legs})} stocks")


if __name__ == "__main__":
    main()
