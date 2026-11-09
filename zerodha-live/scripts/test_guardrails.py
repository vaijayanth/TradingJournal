"""Self-test for the Zerodha (AZ) guardrails.py: every check must FIRE on a deliberately bad input and stay quiet on a clean one.
Run: python zerodha-live/scripts/test_guardrails.py   (exit code 1 on any failure). No network, no repo data needed.
"""
import copy
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import guardrails as g  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
NOW = datetime(2026, 11, 10, 18, 0, tzinfo=IST)          # Tue 18:00 IST -> expected session = 2026-11-10
TODAY = "2026-11-10"


def pos(sym, qty=10, avg=100.0, cmp=110.0, color="green", **kw):
    r = {"symbol": sym, "qty": qty, "avg_cost": avg, "cmp": cmp, "pl_pct": round((cmp / avg - 1) * 100, 4), "supertrend_color": color, "num_adds": 0}
    r.update(kw)
    return r


def base():
    holds = [pos(x) for x in ("AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "III")]
    return {
        "signals": {"market_data_date": TODAY, "capital_base": {"initial_capital": 3_000_000}, "sizing": {"effective_tier_rs": 20000},
                    "option_hedge_portfolio": ["HHH"], "holds": holds, "exits": [], "addons": [], "entries": []},
        "signals_generated_at": "2026-11-10T12:00:00+00:00", "holdings": [{"symbol": p["symbol"], "qty": p["qty"], "avg_cost": p["avg_cost"]} for p in holds],
        "holdings_fetched_at": "2026-11-10T17:00:00+05:30", "orders": [], "orders_fetched_at": "2026-11-10T17:00:00+05:30",
        "fills": None,   # AZ has no fill ledger: Zerodha holdings are the truth
        "crosscheck": {"market_data_date": TODAY, "results": [{"kind": "exit", "symbol": "AAA", "ok": True}] * 6}, "cc": None, "config": {}, "halt": {}, "sectors": {}, "excluded": [], "import_violations": [], "is_inv_stock": lambda s: False,
    }


def run(ctx):
    return g.evaluate(ctx, NOW)


def has(findings, gid, level=None, symbol=None):
    return any(x["id"] == gid and (level is None or x["level"] == level) and (symbol is None or x["symbol"] == symbol) for x in findings)


fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


# ---- clean input must be silent
c = base()
check("clean input: no BLOCK/WARN", [x for x in run(c) if x["level"] in ("BLOCK", "WARN")] == [])

# H1
c = base(); c["halt"] = {"halt": True, "reason": "test"}
check("H1 halt blocks everything", has(run(c), "H1", "BLOCK") and [x for x in run(c) if x["id"] == "H1"][0]["symbol"] is None)
# F1
c = base(); c["signals"]["market_data_date"] = "2026-11-09"
check("F1 one session behind = WARN", has(run(c), "F1", "WARN"))
c = base(); c["signals"]["market_data_date"] = "2026-11-04"
check("F1 4 sessions behind = BLOCK", has(run(c), "F1", "BLOCK"))
# F2
c = base(); c["holdings_fetched_at"] = "2026-11-04T10:00:00+05:30"; c["signals"]["holdings_fetched_at"] = "2026-11-04T10:00:00+05:30"
check("F2 old holdings = BLOCK", has(run(c), "F2", "BLOCK"))
# F3
c = base(); c["signals_generated_at"] = "2026-11-10T01:00:00+00:00"; c["holdings_fetched_at"] = "2026-11-10T17:00:00+05:30"
check("F3 signals older than holdings = WARN", has(run(c), "F3", "WARN"))
# F5
c = base(); c["crosscheck"]["results"] = [{"kind": "entry", "symbol": f"S{i}", "ok": i > 3} for i in range(8)]
check("F5 half the signals flagged = global BLOCK", has(run(c), "F5", "BLOCK") and [x for x in run(c) if x["id"] == "F5"][0]["symbol"] is None)
c = base(); c["crosscheck"]["results"] = [{"kind": "entry", "symbol": "S0", "ok": False}] + [{"kind": "entry", "symbol": f"T{i}", "ok": True} for i in range(9)]
check("F5 one flagged signal = WARN only", has(run(c), "F5", "WARN") and not has(run(c), "F5", "BLOCK"))
c = base(); c["crosscheck"]["market_data_date"] = "2026-11-01"
check("F5 cross-check for another date = BLOCK", has(run(c), "F5", "BLOCK"))
c = base(); c["crosscheck"] = None
check("F5 no cross-check = WARN", has(run(c), "F5", "WARN"))
# I1
c = base(); c["signals"]["x"] = float("nan")
check("I1 NaN = BLOCK", has(run(c), "I1", "BLOCK"))
# I2
c = base(); c["signals"]["holds"][0]["pl_pct"] = 50.0
check("I2 wrong P&L% = BLOCK for the stock", has(run(c), "I2", "BLOCK", "AAA"))
c = base(); c["holdings"][1]["qty"] = 99
check("I2 qty differs from holdings = BLOCK", has(run(c), "I2", "BLOCK", "BBB"))
# I4 / I5
c = base(); c["signals"]["exits"] = [pos("AAA", color="red")]; c["signals"]["addons"] = [pos("AAA", avg=130, cmp=100, num_adds=0, add_qty=1, cooldown_days_since_last_buy=20)]
check("I4 stock in two lists = BLOCK", has(run(c), "I4", "BLOCK", "AAA"))
c = base(); c["signals"]["entries"] = [{"symbol": "HHH", "close": 100, "supertrend_color": "green", "pct_from_high": 0, "qty_to_buy": 1, "recent_bullish_flip_days_ago": 2}]
check("I5 hedge stock as signal = BLOCK", has(run(c), "I5", "BLOCK", "HHH"))
# S1..S5
c = base(); c["signals"]["exits"] = [pos("AAA", color="green")]
check("S1 exit that is not red = BLOCK", has(run(c), "S1", "BLOCK", "AAA"))
c = base(); c["signals"]["addons"] = [pos("AAA", avg=100, cmp=120, add_qty=1, cooldown_days_since_last_buy=20)]
check("S2 add-on in profit = BLOCK (AZ: needs a loss)", has(run(c), "S2", "BLOCK", "AAA"))
c = base(); c["signals"]["addons"] = [pos("AAA", avg=100, cmp=99, add_qty=1, cooldown_days_since_last_buy=3)]
check("S2 add-on inside cooldown = BLOCK", has(run(c), "S2", "BLOCK", "AAA"))
c = base(); c["signals"]["addons"] = [pos("AAA", avg=100, cmp=90, color="red", add_qty=1, cooldown_days_since_last_buy=20)]
check("S2 add-on on a red stock = BLOCK", has(run(c), "S2", "BLOCK", "AAA"))
c = base(); c["signals"]["entries"] = [{"symbol": "AAA", "close": 100, "supertrend_color": "green", "pct_from_high": 0, "qty_to_buy": 1, "recent_bullish_flip_days_ago": 2}]
check("S3 entry in a held stock = BLOCK", has(run(c), "S3", "BLOCK", "AAA"))
c = base(); c["signals"]["entries"] = [{"symbol": "NEW", "close": 100, "supertrend_color": "red", "pct_from_high": 0, "qty_to_buy": 1, "recent_bullish_flip_days_ago": 2}]
check("S3 entry on red = BLOCK", has(run(c), "S3", "BLOCK", "NEW"))
c = base(); c["signals"]["entries"] = [{"symbol": "NEW", "close": 100, "supertrend_color": "green", "pct_from_high": -30, "qty_to_buy": 5, "recent_bullish_flip_days_ago": 3}]
check("S3 entry far below the 52-week high is fine for AZ (no high rule)", not has(run(c), "S3", "BLOCK", "NEW"))
c = base(); c["signals"]["entries"] = [{"symbol": "NEW", "close": 100, "supertrend_color": "green", "pct_from_high": 0, "qty_to_buy": 5, "recent_bullish_flip_days_ago": 9}]
check("S3 entry whose flip is 9 trading days old = BLOCK (window 6)", has(run(c), "S3", "BLOCK", "NEW"))
c = base(); c["signals"]["entries"] = [{"symbol": "BIG", "close": 90000, "supertrend_color": "green", "pct_from_high": 0, "qty_to_buy": 1, "recent_bullish_flip_days_ago": 2}]
check("S4 1-share overspend = WARN", has(run(c), "S4", "WARN"))
c = base(); c["signals"]["entries"] = [{"symbol": f"E{i}", "close": 10, "supertrend_color": "green", "pct_from_high": 0, "qty_to_buy": 1, "recent_bullish_flip_days_ago": 2} for i in range(70)]
check("S5 70 entries = WARN", has(run(c), "S5", "WARN"))
c = base(); c["signals"]["exits"] = [pos(f"X{i}", color="red") for i in range(3)]
c["signals"]["holds"] = [pos("AAA")]; c["holdings"] = [{"symbol": s["symbol"], "qty": 10, "avg_cost": 100} for s in c["signals"]["exits"] + c["signals"]["holds"]]
c["config"] = {"mass_exit_min": 3}
check("S5 mass exit = BLOCK", has(run(c), "S5", "BLOCK"))
# C
c = base(); c["signals"]["holds"][0] = pos("AAA", qty=1000, avg=100); c["holdings"][0]["qty"] = 1000
check("C2 one stock > 20% = WARN", has(run(c), "C2", "WARN", "AAA"))
c = base(); c["sectors"] = {"AAA": "Tech", "BBB": "Tech", "CCC": "Tech", "DDD": "Tech", "EEE": "Bank"}
check("C2 sector > 40% = WARN", has(run(c), "C2", "WARN"))
c = base(); c["signals"]["capital_base"]["initial_capital"] = 3000
check("C1 deployed > base = WARN", has(run(c), "C1", "WARN"))
c = base(); c["orders"] = [{"symbol": "ZZZ", "side": "BUY", "qty": 10000, "price": 100, "status": "PENDING"}]
check("C3 pending buys over 25% of base = WARN", has(run(c), "C3", "WARN"))
# O
c = base(); c["orders"] = [{"symbol": "AAA", "side": "SELL", "qty": 99, "price": 100, "status": "PENDING"}]
check("O1 oversell order = BLOCK", has(run(c), "O1", "BLOCK", "AAA"))
c = base(); c["orders"] = [{"symbol": "AAA", "side": "SELL", "qty": 5, "price": 100, "status": "PENDING"}] * 2
check("O2 duplicate pending orders = WARN", has(run(c), "O2", "WARN", "AAA"))
c = base(); c["orders"] = [{"symbol": "QQQ", "side": "BUY", "qty": 1, "price": 100, "status": "PENDING"}]
check("O3 pending order without a signal = WARN", has(run(c), "O3", "WARN", "QQQ"))
# P
c = base(); c["cc"] = {"market_data_date": TODAY, "alerts": [{"level": "EXIT", "symbol": "AAA", "text": "premium 3x"}],
                       "stocks": [{"symbol": "AAA", "status": "ENTER", "expiries": [{"expiry": "2026-11-12", "lot": None}], "desired": "CALL"}]}
r = run(c)
check("P1 expiry week = WARN", has(r, "P1", "WARN", "AAA"))
check("P2 no lot size = WARN", has(r, "P2", "WARN", "AAA"))
check("P3 open option exit alert = WARN", has(r, "P3", "WARN"))
c = base(); c["cc"] = {"market_data_date": TODAY, "alerts": [{"level": "BREACH", "type": "Invalid GTT", "symbol": "AAA", "text": "stale"}], "stocks": []}
r = run(c)
check("P5 invalid GTT = WARN", has(r, "P5", "WARN"))
check("P3 ignores Invalid GTT findings", not has(r, "P3", "WARN"))
c = base(); c["cc"] = {"market_data_date": TODAY, "alerts": [], "stocks": [{"symbol": "AAA", "status": "ENTER", "lot": 500, "shares": 10, "covered": False, "desired": "CALL", "suggestions": []}]}
check("P4 uncovered short call = WARN", has(run(c), "P4", "WARN", "AAA"))
# X1
c = base(); c["import_violations"] = ["x.py:1 imports from other"]
check("X1 cross-broker import = BLOCK", has(run(c), "X1", "BLOCK"))
check("X1 real repo scan finds no cross-broker import", g.separation_violations() == [])

print(f"\n{len(fails)} failure(s)" if fails else "\nALL GUARDRAIL TESTS PASSED")
sys.exit(1 if fails else 0)
