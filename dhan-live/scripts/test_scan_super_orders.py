"""Self-test for the super order matcher (scan_super_orders.match_orders). Run: python dhan-live/scripts/test_scan_super_orders.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from scan_super_orders import match_orders  # noqa: E402

bad = 0


def check(name, cond):
    global bad
    print(("PASS " if cond else "FAIL ") + name)
    bad += 0 if cond else 1


def sh(sym, qty, avg):
    return {"symbol": sym, "qty": qty, "sell_avg": avg, "side": "SHORT"}


def od(i, sym, qty, entry, sl, tg):
    return {"order_id": i, "symbol": sym, "qty": qty, "entry": entry, "side": "SELL", "legs": {"STOP_LOSS_LEG": {"status": "PENDING", "price": sl, "trail": 0.01}, "TARGET_LEG": {"status": "PENDING", "price": tg, "trail": 0}}}


# 1. two orders add up to one averaged short (BANKINDIA 2026-11-23): both matched, no orphan left
s = [sh("BANKINDIA", 15600, 1.02)]
o = [od("a", "BANKINDIA", 10400, 1.05, 3.15, 0.4), od("b", "BANKINDIA", 5200, 1.02, 2.88, 0.38)]
m, u = match_orders(s, o, 3)
check("two orders covering one averaged short are both matched", set(m) == {0, 1} and u == {0})

# 2. quantities that do NOT add up stay unmatched (never invent coverage)
s = [sh("BANKINDIA", 15000, 1.02)]
m, u = match_orders(s, [od("a", "BANKINDIA", 10400, 1.05, 3.15, 0.4), od("b", "BANKINDIA", 5200, 1.02, 2.88, 0.38)], 3)
check("orders that do not sum to the short are not grouped", m.get(0) is None or m.get(1) is None or len(set(id(x) for x in m.values())) == 1 and False or not ({0, 1} <= set(m)))

# 3. one exact order keeps the normal path (no group flag)
s = [sh("BPCL", 7900, 2.15)]
o = [od("c", "BPCL", 7900, 2.15, 6.45, 0.85)]
m, u = match_orders(s, o, 3)
check("a single exact order matches normally", m == {0: s[0]} and not o[0].get("group"))

# 4. an order with an entry 20% away is not pulled into a group
s = [sh("X", 300, 10.0)]
o = [od("d", "X", 100, 12.5, 30, 4), od("e", "X", 200, 10.0, 30, 4)]
m, u = match_orders(s, o, 3)
check("an order far from the short's average is not grouped", 0 not in m or o[0].get("group") is not True)

# 5. a different stock's orders are never used
s = [sh("A", 300, 1.0)]
m, u = match_orders(s, [od("f", "B", 100, 1.0, 3, 0.4), od("g", "B", 200, 1.0, 3, 0.4)], 3)
check("orders of another stock never cover a short", not m)
print("ALL PASSED" if not bad else f"{bad} FAILED")
sys.exit(1 if bad else 0)
