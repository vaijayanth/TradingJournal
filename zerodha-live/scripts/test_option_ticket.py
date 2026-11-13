"""Self-test for build_option_ticket.py: every refusal and warning must still fire. Run: python zerodha-live/scripts/test_option_ticket.py"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_option_ticket as b  # noqa: E402

fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


def refuses(fn, *a, **k):
    try:
        fn(*a, **k)
    except SystemExit as e:
        return e.code == 2
    return False


check("tradingsymbol monthly call", b.tradingsymbol("ABB", "2026-12-29", 6500, "CE") == "ABB26DEC6500CE")
check("tradingsymbol decimal strike", b.tradingsymbol("X", "2026-11-23", 87.5, "PE") == "X26NOV87.5PE")
check("tick rounds down", b.tick(49.52) == 49.5 and b.tick(49.53) == 49.55)
check("tick rounds up", b.tick(49.51, up=True) == 49.55)
check("distance rule: 10% this month, 15% later", b.default_otm("2026-11-23", __import__("datetime").date(2026, 11, 14)) == 10.0 and b.default_otm("2026-12-29", __import__("datetime").date(2026, 11, 14)) == 15.0)
ks = [100, 110, 120, 130, 140, 150, 160]
check("call strike is above the price", b.pick_strike(ks, 100.0, "CE", 20)[0] == 120)
check("put strike is below the price", b.pick_strike(ks, 150.0, "PE", 20)[0] == 120)
check("call tie goes to the farther strike", b.pick_strike([105, 115], 100.0, "CE", 10)[0] == 115)
check("put tie goes to the farther strike", b.pick_strike([85, 95], 100.0, "PE", 10)[0] == 85)
check("no out-of-the-money strike = refuse", refuses(b.pick_strike, [90, 95], 100.0, "CE", 10))
check("hedge is 2 listed strikes below", b.hedge_strike([100, 110, 120, 130], 130, 2) == 110)
check("no strike far enough below = refuse", refuses(b.hedge_strike, [100, 110], 110, 2))

good = {"last_price": 50, "oi": 100 * 125, "volume": 10, "depth": {"buy": [{"price": 49, "quantity": 125}], "sell": [{"price": 51, "quantity": 125}]}}
check("healthy quote has no warnings", b.quote_info(good, 125)["warn"] == [])
check("no bid is flagged", any("no bid" in w for w in b.quote_info({**good, "depth": {"buy": [], "sell": good["depth"]["sell"]}}, 125)["warn"]))
check("wide spread is flagged", any("wide" in w for w in b.quote_info({**good, "depth": {"buy": [{"price": 40, "quantity": 1}], "sell": [{"price": 60, "quantity": 1}]}}, 125)["warn"]))
check("thin open interest is flagged", any("thin" in w for w in b.quote_info({**good, "oi": 5 * 125}, 125)["warn"]))
check("no trades today is flagged", any("no trades" in w for w in b.quote_info({**good, "volume": 0}, 125)["warn"]))
check("suggested limit is inside the spread", b.suggest_price(b.quote_info(good, 125), "SELL") == 50.0)
check("no bid/ask = no suggestion", b.suggest_price({"bid": None, "ask": 51}, "SELL") is None)

# trading halt refuses
tmp = Path(tempfile.mkdtemp())
(tmp / "trading_halt.json").write_text(json.dumps({"halt": True, "reason": "test"}))
old = b.DATA
b.DATA = tmp
check("trading halt = refuse", refuses(b.read_hard_blocks))
(tmp / "trading_halt.json").write_text(json.dumps({"halt": False}))
(tmp / "guardrails.json").write_text(json.dumps({"findings": [{"level": "BLOCK", "id": "X1", "symbol": None, "msg": "x"}]}))
check("cross-broker import block = refuse", refuses(b.read_hard_blocks))
(tmp / "guardrails.json").write_text(json.dumps({"findings": [{"level": "BLOCK", "id": "F5", "symbol": None, "msg": "x"}]}))
g, ignored = b.read_hard_blocks()
check("F5 does not stop an option ticket", ignored == ["F5"])
b.DATA = old

# stale quotes file refuses
class A:  # noqa: D401
    pass


qf = tmp / "q.json"
qf.write_text("{}")
os.utime(qf, (time.time() - 3 * 86400, time.time() - 3 * 86400))
a = A()
a.symbol, a.structure, a.expiry, a.otm_pct, a.spot = "ABB", "put-spread", "2026-12-29", None, 7054.5
a.quotes, a.lots, a.target_credit, a.short_strike, a.short_limit, a.hedge_limit = str(qf), 1, None, None, None, None
check("quotes older than today = refuse", refuses(b.cmd_build, a))
a.lots = 9
check("more than 4 lots = refuse", refuses(b.cmd_build, a))
a.lots, a.symbol = 1, "BSE"
check("excluded stock = refuse", refuses(b.cmd_build, a))
a.symbol = "NOTASTOCK"
check("stock outside the F&O universe = refuse", refuses(b.cmd_build, a))
a.symbol, a.expiry = "ABB", "2026-11-17"
check("expiry week = refuse (or expiry not listed)", refuses(b.cmd_build, a))

print("\nALL OPTION TICKET TESTS PASSED" if not fails else f"\n{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
