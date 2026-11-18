"""Regression tests for the position parser and the premium derivation (run: python dhan-live/scripts/test_parse_positions.py).
Bug 2026-11-17: Dhan's P&L is realised + unrealised, and a contract closed and reopened the same day has a blended average.
The old code derived DIXON 11500PE's premium as 28.33 (real 94.20) and raised a false 81% profit exit, a false target-passed
alert and a false off-rule stop. These tests use the real rows of that day."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compute_covered_call as c

EXP = ["2026-11-24", "2026-12-29"]
TEXT = """📈 Open Positions (3)

DIXON-Dec2026-11500-PE [MARGIN] SHORT
  Net: -50 | Buy 50 @ ₹81.50 | Sell 100 @ ₹147.38
  P&L: ▲ ₹5,952.50 (Realized ₹3,293.75)

DIXON-Dec2026-11000-PE [MARGIN] LONG
  Net: 50 | Buy 100 @ ₹87.35 | Sell 50 @ ₹51.60
  P&L: ▼ ₹3,445.00 (Realized ₹-1,787.50)

INFY-Dec2026-1034-PE [MARGIN] SHORT
  Net: -400 | Buy 0 @ ₹0.00 | Sell 400 @ ₹11.50
  P&L: ▲ ₹100.00 (Realized ₹0.00)
"""
fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


legs = {(l["symbol"], l["strike"]): l for l in c.parse_positions(TEXT, EXP)}
d_short, d_long, infy = legs[("DIXON", 11500.0)], legs[("DIXON", 11000.0)], legs[("INFY", 1034.0)]
check("realised P&L is parsed (positive and negative)", d_short["realized_rs"] == 3293.75 and d_long["realized_rs"] == -1787.5 and infy["realized_rs"] == 0)
check("closed-and-reopened short premium = 94.20 (not 28.33)", c.leg_premium(d_short) == 94.2)
check("closed-and-reopened long premium = 54.20", c.leg_premium(d_long) == 54.2)
check("a clean short still derives sold - pnl/qty (11.50 - 0.25 = 11.25)", c.leg_premium(infy) == 11.25)
check("blended flag set only when there is realised P&L", d_short["blended"] and d_long["blended"] and not infy["blended"])
print("\nALL PARSE_POSITIONS TESTS PASSED" if not fails else f"\n{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
