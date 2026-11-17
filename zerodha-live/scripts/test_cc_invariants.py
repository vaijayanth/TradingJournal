"""Invariants of covered_call_signals.json (AZ). Run after compute_covered_call.py: python zerodha-live/scripts/test_cc_invariants.py
  1. Every 'Exit' alert names the leg to close (strike, type, expiry): an Exit with nothing to close is a stale colour tag (fixed 2026-11-16).
  2. A stock whose stored entry colour differs from today's colour must still have an open short of the structure the colour no longer wants.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
c = json.loads((ROOT / "covered_call_signals.json").read_text(encoding="utf-8"))
tags = json.loads((ROOT / "data" / "cc_tags.json").read_text(encoding="utf-8"))["tags"]
fails = []
for a in c["alerts"]:
    if a["type"] == "Exit" and (a.get("strike") is None or not a.get("expiry")):
        fails.append(f"Exit alert with no leg: {a['symbol']} ({a.get('concern')})")
for s in c["stocks"]:
    t = tags.get(s["symbol"])
    if s["legs"] and t and t.get("entry_colour") and t["entry_colour"] != s["colour"]:
        opp = "PE" if s["colour"] == "red" else "CE"
        if not any(l["side"] == "SHORT" and l["type"] == opp for l in s["legs"]):
            fails.append(f"stale entry colour tag on {s['symbol']}: tag {t['entry_colour']}, colour {s['colour']}, no opposite short open")
exits = sum(1 for a in c["alerts"] if a["type"] == "Exit")
print(f"{exits} Exit alerts checked, {len(c['stocks'])} stocks")
for f in fails:
    print("FAIL", f)
print("ALL CC INVARIANTS HOLD" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
