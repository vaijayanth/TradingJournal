"""Every check in the ND scan_options.py must still fire (and a clean book must raise nothing). Run: python dhan-live/scripts/test_scan_options.py"""
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
IST = timezone(timedelta(hours=5, minutes=30))
TS = datetime.now(IST).isoformat(timespec="seconds")


def leg(sym, strike, typ, side, qty, avg, ltp, exp="2026-12-29"):
    pnl = (avg - ltp) * qty if side == "SHORT" else (ltp - avg) * qty
    return {"symbol": sym, "expiry": exp, "strike": float(strike), "type": typ, "side": side, "qty": qty, "buy_avg": avg if side == "LONG" else 0.0,
            "sell_avg": avg if side == "SHORT" else 0.0, "pnl_rs": pnl, "ltp": ltp}


def sup(oid, sym, qty, entry, sl="PENDING", slp=None, tg="PENDING", tgp=0.0):
    slp = slp if slp is not None else round(entry * 3, 2)
    return (f"{oid} | SELL {sym} | TRADED\n  Qty: {qty} (remaining 0) @ ₹{entry:.2f} | LTP ₹1.00\n    STOP_LOSS_LEG: {sl} qty ? @ ₹{slp:.2f} (trail 0.05)\n"
            f"    TARGET_LEG: {tg} qty ? @ ₹{tgp:.2f} (trail 0.0)\n")


def run(legs, orders="", scan=()):
    d = Path(tempfile.mkdtemp())
    (d / "data" / "cc_raw").mkdir(parents=True)
    stocks = {}
    for l in legs:
        stocks.setdefault(l["symbol"], {"symbol": l["symbol"], "legs": []})["legs"].append(l)
    (d / "covered_call_signals.json").write_text(json.dumps({"generated_at": TS, "stocks": list(stocks.values())}))
    (d / "data" / "cc_config.json").write_text(json.dumps({"rules": {"stop_premium_multiple": 3}}))
    (d / "data" / "cc_raw" / "positions.txt").write_text("positions")
    (d / "data" / "cc_raw" / "super_orders.txt").write_text("\U0001F4CB Super Order Book\n\n" + orders, encoding="utf-8")
    (d / "data" / "super_scan.json").write_text(json.dumps({"fetched_at": TS, "findings": list(scan)}))
    out = subprocess.run([sys.executable, str(HERE / "scan_options.py"), "--data-dir", str(d), "--json"], capture_output=True, text=True, encoding="utf-8")
    if out.returncode:
        raise SystemExit(out.stderr or out.stdout)
    return json.loads(out.stdout)


fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


def has(res, sec, sev=None, text=None):
    return any(f["section"] == sec and (sev is None or f["severity"] == sev) and (text is None or text in f["concern"]) for f in res["findings"])


spread = [leg("AAA", 100, "PE", "SHORT", 100, 5.0, 4.0), leg("AAA", 90, "PE", "LONG", 100, 1.0, 1.0)]
good = sup("1", "AAA", 100, 5.0, tgp=2.0)   # stop 15 (3x) and target 2.0 (40% of the sold price)
r = run(spread, good)
check("clean spread with a pending stop raises nothing", not [f for f in r["findings"] if f["severity"] != "INFO"])
check("A orphaned long", has(run([leg("BBB", 50, "PE", "LONG", 100, 2.0, 1.0)]), "A", "WARN", "no short against it"))
check("A long put above the short is not a hedge", has(run([leg("BBB", 50, "PE", "SHORT", 100, 5.0, 4.0), leg("BBB", 60, "PE", "LONG", 100, 2.0, 3.0)], sup("2", "BBB", 100, 5.0)), "A", "WARN", "not on the protective side"))
check("A a real hedge is not flagged", not has(r, "A"))
check("B short put with no hedge = HIGH", has(run([leg("CCC", 100, "PE", "SHORT", 100, 5.0, 4.0)], sup("3", "CCC", 100, 5.0)), "B", "HIGH"))
check("B naked call is INFO only", has(run([leg("DDD", 100, "CE", "SHORT", 100, 5.0, 4.0)], sup("4", "DDD", 100, 5.0)), "B", "INFO"))
check("C short with no super order = WARN", has(run([leg("EEE", 100, "CE", "SHORT", 100, 5.0, 4.0)]), "C", "WARN"))
check("C short past 3x with no super order = HIGH", has(run([leg("EEE", 100, "CE", "SHORT", 100, 5.0, 20.0)]), "C", "HIGH"))
short_f = [leg("FFF", 100, "CE", "SHORT", 100, 5.0, 20.0)]
check("D stop leg TRADED while the short is still open = HIGH", has(run(short_f, sup("5", "FFF", 100, 5.0, sl="TRADED")), "D", "HIGH", "TRADED"))
check("D stop leg CANCELLED while the short is open = HIGH", has(run(short_f, sup("6", "FFF", 100, 5.0, sl="CANCELLED")), "D", "HIGH", "CANCELLED"))
check("D stop TRADED and position closed = fine, counted", run([], sup("7", "FFF", 100, 5.0, sl="TRADED"))["fired_cleanly"] == ["FFF @ 5"] and not has(run([], sup("7", "FFF", 100, 5.0, sl="TRADED")), "D"))
check("E premium past the stop price, stop still pending = HIGH", has(run(short_f, sup("8", "FFF", 100, 5.0, slp=15.0)), "E", "HIGH", "has not fired"))
check("E premium past the target price = WARN", has(run([leg("GGG", 100, "CE", "SHORT", 100, 5.0, 1.5)], sup("9", "GGG", 100, 5.0, tgp=2.0)), "E", "WARN"))
check("E premium between target and stop is fine", not has(run([leg("GGG", 100, "CE", "SHORT", 100, 5.0, 6.0)], sup("9", "GGG", 100, 5.0, tgp=2.0)), "E"))
r = run([], scan=[{"check": "S1", "name": "ORPHAN", "severity": "HIGH", "symbol": "HHH", "order_id": "9", "strike": None, "opt_type": None, "concern": "likely orphaned", "action": "cancel"}])
check("F stop hygiene findings are passed through", has(r, "F", "HIGH"))
check("G stop with the target leg pending at 0.00 = no profit target", has(run(spread, sup("11", "AAA", 100, 5.0)), "G", "WARN", "no profit target"))
check("G suggests 40% of the sold price", any("about 2" in f["action"] for f in run(spread, sup("11", "AAA", 100, 5.0))["findings"] if f["section"] == "G"))
check("G a real target is not flagged", not has(run(spread, sup("12", "AAA", 100, 5.0, tgp=2.0)), "G"))
check("G a fired target is not flagged", not has(run(spread, sup("13", "AAA", 100, 5.0, tg="TRADED", tgp=2.0)), "G"))
check("matching uses the sold average (a different average does not match)", has(run([leg("III", 100, "CE", "SHORT", 100, 5.0, 4.0)], sup("10", "III", 100, 7.0)), "C", "WARN"))

stale = [leg("JJJ", 100, "PE", "SHORT", 50, 94.2, 90.0), leg("JJJ", 90, "PE", "LONG", 50, 54.2, 55.0)]
r = run(stale, sup("14", "JJJ", 50, 147.38, slp=282.6, tgp=37.7))   # order book still shows the old blended entry price
check("stale order entry price still matches by qty + stop/target at 3x / 40% of the position's sold price", not has(r, "C") and not has(r, "E") and not has(r, "F"))
check("a stop at the wrong level does not match a stale-entry order", has(run(stale, sup("15", "JJJ", 50, 147.38, slp=500.0, tgp=70.0)), "C", "WARN"))

print("\nALL ND SCAN_OPTIONS TESTS PASSED" if not fails else f"\n{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
