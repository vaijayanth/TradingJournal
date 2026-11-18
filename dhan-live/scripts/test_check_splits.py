"""Auto-record of splits (check_splits.py). Run: python dhan-live/scripts/test_check_splits.py"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_splits as cs
import corp_actions as ca

F = [{"symbol": "PASHUPATI", "date": "2026-10-26", "action": "BUY", "qty": 9, "price": 109.05, "value": 981.45},
     {"symbol": "PASHUPATI", "date": "2026-11-13", "action": "SELL", "qty": 9, "price": 35.15, "value": 316.35}]
fails = []


def check(n, ok):
    print(("PASS " if ok else "FAIL ") + n)
    if not ok:
        fails.append(n)


m = lambda q, fills=F, acts=(): cs.match_holdings(fills, list(acts), "PASHUPATI", "2026-11-13", 2.5, q)
check("holdings 13 = floor(9 x 2.5) - 9 sold -> match", m(13)[0] == "match")
check("holdings 0 is never auto-recorded (here it equals the unadjusted 9 - 9)", m(0)[0] != "match")
check("expected quantity is reported (13)", m(13)[1] == 13)
check("holdings = unadjusted quantity (9 - 9 = 0 here, 5 for 14-9): not credited", cs.match_holdings([dict(F[0], qty=14), dict(F[1])], [], "PASHUPATI", "2026-11-13", 2.5, 5)[0] == "uncredited")
check("any other quantity is a mismatch", m(20)[0] == "mismatch")
check("nothing held on the ex-date -> 'none' (ledger unaffected)", cs.match_holdings([dict(F[0]), dict(F[1], date="2026-11-01")], [], "PASHUPATI", "2026-11-13", 2.5, 0)[0] == "none")
d = Path(tempfile.mkdtemp()) / "corporate_actions.json"
d.write_text(json.dumps({"_note": "keep me", "actions": [{"symbol": "OLD", "ex_date": "2026-01-01", "ratio": 2.0, "type": "split"}]}))
cs.record_action(d, "PASHUPATI", "2026-11-13", 2.5, 13, "2026-11-18")
j = json.loads(d.read_text())
check("record_action appends, keeps the note and earlier actions", j["_note"] == "keep me" and len(j["actions"]) == 2 and j["actions"][1]["symbol"] == "PASHUPATI" and j["actions"][1]["auto_recorded"] == "2026-11-18")
check("the recorded action loads and adjusts the ledger", len(ca.load_actions(d)) == 2)
print("\nALL CHECK_SPLITS TESTS PASSED" if not fails else f"\n{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
