"""Tests for build_order_ticket.unsettled_sell_cap (run: python dhan-live/scripts/test_order_ticket.py)."""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_order_ticket import unsettled_sell_cap  # noqa: E402

TODAY = date(2026, 11, 19)
FAILS = 0


def check(name, got, want):
    global FAILS
    ok = got == want
    FAILS += 0 if ok else 1
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f" got {got} want {want}"))


f = [{"symbol": "X", "action": "BUY", "qty": 5, "date": "2026-11-10"},
     {"symbol": "X", "action": "SELL", "qty": 4, "date": "2026-11-19"}]
check("partial sell today leaves 1", unsettled_sell_cap(f, "X", TODAY), (1, 4))
check("old sell is not 'recent'", unsettled_sell_cap([{"symbol": "X", "action": "BUY", "qty": 5, "date": "2026-11-01"},
                                                       {"symbol": "X", "action": "SELL", "qty": 4, "date": "2026-11-05"}], "X", TODAY), (1, 0))
check("no fills for the symbol", unsettled_sell_cap(f, "Y", TODAY), (0, 0))
check("sell exceeding buys never goes negative", unsettled_sell_cap([{"symbol": "X", "action": "SELL", "qty": 3, "date": "2026-11-19"}], "X", TODAY), (0, 3))
check("full sell today leaves 0", unsettled_sell_cap([{"symbol": "X", "action": "BUY", "qty": 2, "date": "2026-11-01"},
                                                       {"symbol": "X", "action": "SELL", "qty": 2, "date": "2026-11-19"}], "X", TODAY), (0, 2))
check("bad date is ignored", unsettled_sell_cap([{"symbol": "X", "action": "BUY", "qty": 2, "date": "2026-11-01"},
                                                  {"symbol": "X", "action": "SELL", "qty": 1, "date": "oops"}], "X", TODAY), (1, 0))
print("ALL PASSED" if not FAILS else f"{FAILS} FAILED")
sys.exit(1 if FAILS else 0)
