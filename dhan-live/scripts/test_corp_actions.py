"""Fractional-share settlement after a split. Run: python dhan-live/scripts/test_corp_actions.py (PASHUPATI 2026-11-13: 9 x 2.5 = 22.5 -> 22 shares, 13 after selling 9)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import corp_actions as c

A = [{"symbol": "PASHUPATI", "ex_date": "2026-11-13", "ratio": 2.5, "type": "split"}]
F = [{"symbol": "PASHUPATI", "date": "2026-10-26", "action": "BUY", "qty": 9, "price": 109.05, "value": 981.45},
     {"symbol": "PASHUPATI", "date": "2026-11-13", "action": "SELL", "qty": 9, "price": 35.15, "value": 316.35}]
fails = []


def check(n, ok):
    print(("PASS " if ok else "FAIL ") + n)
    if not ok:
        fails.append(n)


out = c.adjust_fills(F, A)
net = sum(f["qty"] if f["action"] == "BUY" else -f["qty"] for f in out)
check("PASHUPATI nets to 13 whole shares (22 credited - 9 sold)", abs(net - 13) < 1e-9)
check("buy is in post-split units (22.5 @ 43.62)", abs(out[0]["qty"] - 22.5) < 1e-9 and abs(out[0]["price"] - 43.62) < 1e-6)
fr = [f for f in out if f.get("source") == "fractional_cash_settlement"]
check("one synthetic SELL of 0.5 dated the ex-date at the ex-date fill price", len(fr) == 1 and abs(fr[0]["qty"] - 0.5) < 1e-6 and fr[0]["date"] == "2026-11-13" and fr[0]["price"] == 35.15)
check("a whole-number result adds nothing", not [f for f in c.adjust_fills([dict(F[0], qty=8, value=872.4)], A) if f.get("source") == "fractional_cash_settlement"])
check("no recorded action = fills untouched", c.adjust_fills(F, []) == F)
print("\nALL CORP_ACTIONS TESTS PASSED" if not fails else f"\n{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
