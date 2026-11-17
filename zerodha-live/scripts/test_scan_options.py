"""Every check in scan_options.py must still fire (and a clean book must raise nothing). Run: python zerodha-live/scripts/test_scan_options.py"""
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
IST = timezone(timedelta(hours=5, minutes=30))
NOW = datetime.now(IST)
TS = NOW.isoformat(timespec="seconds")
EARLIER = (NOW - timedelta(days=3)).isoformat(timespec="seconds")


def leg(sym, strike, typ, side, qty, avg, ltp, exp="2026-12-29"):
    mon = {"12": "DEC", "11": "NOV"}[exp[5:7]]
    return {"symbol": sym, "expiry": exp, "strike": float(strike), "type": typ, "side": side, "qty": qty, "avg": avg, "ltp": ltp,
            "pnl_rs": (avg - ltp) * qty if side == "SHORT" else (ltp - avg) * qty, "tradingsymbol": f"{sym}{exp[2:4]}{mon}{strike}{typ}"}


def gtt(i, ts, trig, side="BUY", qty=100, price=None):
    return {"id": i, "type": "two-leg", "created_at": TS, "expires_at": None, "tradingsymbol": ts, "last_price": 1, "triggers": trig,
            "orders": [{"side": side, "qty": qty, "price": price or max(trig), "product": "NRML", "order_type": "LIMIT"}]}


def run(legs, gtts=(), triggered=(), orders=(), scan=(), stale_orders=False):
    d = Path(tempfile.mkdtemp())
    (d / "cc_config.json").write_text(json.dumps({"rules": {"stop_premium_multiple": 3}, "track_from": "2026-11-01"}))
    (d / "cc_positions.json").write_text(json.dumps({"fetched_at": TS, "legs": legs}))
    active = {}
    for g in gtts:
        active.setdefault(g["tradingsymbol"], []).append({"id": g["id"]})
    (d / "cc_gtts.json").write_text(json.dumps({"fetched_at": TS, "active": active, "gtts": list(gtts), "triggered": list(triggered)}))
    (d / "cc_orders_today.json").write_text(json.dumps({"fetched_at": EARLIER if stale_orders else TS, "orders": list(orders)}))
    (d / "gtt_scan.json").write_text(json.dumps({"fetched_at": TS, "gtts_fetched_at": TS, "findings": list(scan)}))
    out = subprocess.run([sys.executable, str(HERE / "scan_options.py"), "--data-dir", str(d), "--json"], capture_output=True, text=True)
    if out.returncode:
        raise SystemExit(out.stderr or out.stdout)
    return json.loads(out.stdout)


def order(ts, status, filled=0, qty=100, gtt_=True, msg=""):
    return {"order_id": "9", "tradingsymbol": ts, "side": "BUY", "qty": qty, "filled": filled, "pending": qty - filled, "price": 2.0, "avg": 0, "status": status, "message": msg, "gtt": gtt_, "time": TS}


fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


def has(res, sec, sev=None, text=None):
    return any(f["section"] == sec and (sev is None or f["severity"] == sev) and (text is None or text in f["concern"]) for f in res["findings"])


# clean bull put spread with a GTT: nothing
spread = [leg("AAA", 100, "PE", "SHORT", 100, 5, 4), leg("AAA", 90, "PE", "LONG", 100, 1, 1)]
ok_gtt = [gtt(1, "AAA26DEC100PE", [2, 15])]
r = run(spread, ok_gtt)
check("clean spread with a GTT raises nothing but nothing else", not [f for f in r["findings"] if f["severity"] != "INFO"])
# A orphaned long
r = run([leg("BBB", 50, "PE", "LONG", 100, 2, 1)])
check("A orphaned long (no short at all)", has(r, "A", "WARN", "no short against it"))
r = run([leg("BBB", 50, "PE", "SHORT", 100, 5, 4), leg("BBB", 60, "PE", "LONG", 100, 2, 3)])
check("A long put ABOVE the short is not a hedge", has(r, "A", "WARN", "not on the protective side"))
check("A a real hedge is not flagged", not has(run(spread, ok_gtt), "A"))
# B unhedged short put / naked call
check("B short put with no hedge = HIGH", has(run([leg("CCC", 100, "PE", "SHORT", 100, 5, 4)], [gtt(2, "CCC26DEC100PE", [2, 15])]), "B", "HIGH"))
check("B naked call is INFO only", has(run([leg("DDD", 100, "CE", "SHORT", 100, 5, 4)], [gtt(3, "DDD26DEC100CE", [2, 15])]), "B", "INFO") and not has(run([leg("DDD", 100, "CE", "SHORT", 100, 5, 4)], [gtt(3, "DDD26DEC100CE", [2, 15])]), "B", "HIGH"))
# C no stop GTT
check("C short with no GTT = WARN", has(run([leg("EEE", 100, "CE", "SHORT", 100, 5, 4)]), "C", "WARN"))
check("C short past 3x with no GTT = HIGH", has(run([leg("EEE", 100, "CE", "SHORT", 100, 5, 20)]), "C", "HIGH"))
# D fired GTTs
fired = [{"id": 7, "type": "two-leg", "tradingsymbol": "FFF26DEC100CE", "triggers": [2, 15], "triggered_at": TS, "orders": [{"side": "BUY", "qty": 100, "price": 15}]}]
short_f = [leg("FFF", 100, "CE", "SHORT", 100, 5, 20)]
check("D fired + order REJECTED + short open = HIGH", has(run(short_f, triggered=fired, orders=[order("FFF26DEC100CE", "REJECTED", msg="margin")]), "D", "HIGH", "REJECTED"))
check("D fired + order still OPEN = HIGH", has(run(short_f, triggered=fired, orders=[order("FFF26DEC100CE", "OPEN")]), "D", "HIGH", "still OPEN"))
check("D fired + no order found + short still open = HIGH", has(run(short_f, triggered=fired, orders=[]), "D", "HIGH", "no buy-back order"))
check("D fired + order COMPLETE + position closed = fine", not has(run([], triggered=fired, orders=[order("FFF26DEC100CE", "COMPLETE", filled=100)]), "D"))
check("D fired + order COMPLETE but short still open = HIGH", has(run(short_f, triggered=fired, orders=[order("FFF26DEC100CE", "COMPLETE", filled=60)]), "D", "HIGH", "still open"))
old = [dict(fired[0], triggered_at=EARLIER)]
check("D fired days ago and short still open = WARN", has(run(short_f, triggered=old), "D", "WARN", "still open"))
# E trigger passed but GTT still active
check("E premium past the stop trigger, GTT still active = HIGH", has(run([leg("GGG", 100, "CE", "SHORT", 100, 5, 16)], [gtt(8, "GGG26DEC100CE", [2, 15])]), "E", "HIGH"))
check("E premium past the profit trigger = WARN", has(run([leg("GGG", 100, "CE", "SHORT", 100, 5, 1.5)], [gtt(8, "GGG26DEC100CE", [2, 15])]), "E", "WARN"))
check("E premium between the triggers is fine", not has(run([leg("GGG", 100, "CE", "SHORT", 100, 5, 6)], [gtt(8, "GGG26DEC100CE", [2, 15])]), "E"))
# F hygiene passthrough
r = run([], scan=[{"check": "G1", "name": "STALE", "severity": "HIGH", "symbol": "HHH", "tradingsymbol": "HHH26DEC100CE", "gtt_id": 5, "concern": "no position", "action": "Delete"}])
check("F stale-GTT findings are passed through", has(r, "F", "HIGH"))
# stale inputs are called out
check("an order list from another day is reported as stale", any("cc_orders" in s for s in run(spread, ok_gtt, stale_orders=True)["stale_inputs"]))

print("\nALL SCAN_OPTIONS TESTS PASSED" if not fails else f"\n{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
