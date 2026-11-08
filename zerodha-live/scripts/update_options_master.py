"""Download Zerodha's public NFO instrument list and keep what the covered-call engine needs for the Nifty F&O stocks:
lot size and the listed strikes (calls and puts) per monthly expiry -> data/nfo_options.json.

Source: https://api.kite.trade/instruments/NFO (public, no login). Option tradingsymbols are
<SYMBOL><YY><MON><STRIKE><CE|PE>, e.g. HCLTECH26NOV1440CE, so prices can be requested for exact contracts.
Usage: python zerodha-live/scripts/update_options_master.py
"""
import csv
import io
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
URL = "https://api.kite.trade/instruments/NFO"


def main():
    uni = set(json.loads((DATA / "fno_universe.json").read_text())["symbols"])
    req = urllib.request.Request(URL, headers={"X-Kite-Version": "3", "User-Agent": "Mozilla/5.0"})
    text = urllib.request.urlopen(req, timeout=90).read().decode("utf-8")
    out = {}
    for r in csv.DictReader(io.StringIO(text)):
        if r["instrument_type"] not in ("CE", "PE") or r["name"] not in uni:
            continue
        s = out.setdefault(r["name"], {"lot": {}, "strikes": {}})
        s["lot"][r["expiry"]] = int(r["lot_size"])
        s["strikes"].setdefault(r["expiry"], {"CE": [], "PE": []})[r["instrument_type"]].append(float(r["strike"]))
    for s in out.values():
        for e in s["strikes"].values():
            for k in e:
                e[k] = sorted(set(e[k]))
    missing = sorted(uni - set(out))
    (DATA / "nfo_options.json").write_text(json.dumps({"fetched_at": datetime.now(timezone.utc).isoformat(), "source": URL, "symbols": out}, separators=(",", ":")))
    print(f"option master: {len(out)} of {len(uni)} F&O stocks have listed options" + (f"; none listed for {missing}" if missing else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
