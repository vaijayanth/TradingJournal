"""Scan every open ND (Dhan) option position (read-only; places nothing).

Usage: python dhan-live/scripts/scan_options.py [--json] [--all]   (--all also lists every naked call, which are INFO only)
Inputs, all from the SAME day (a stale one is reported):
  covered_call_signals.json   the open option legs (qty, average, current price, P&L) as the covered-call engine built them
  data/cc_raw/super_orders.txt  the raw Dhan super order book (stop and target legs with their status)
  data/super_scan.json         the stop-order hygiene findings (scan_super_orders.py)
Dhan has no GTT tool: the user's stop is the STOP_LOSS leg of a SELL super order (about 3x the sold price, trailing jump 0.05), sometimes with a TARGET leg (about 40%).
The super order book shows a symbol and the entry price but NOT the strike or expiry, so an order is matched to a short by symbol + sold average (+ quantity when
two match): the match is approximate, and every finding says so.
Sections:
  A  ORPHANED LONG       a bought leg that hedges no short (same stock / expiry / type; protective side: a put below the short, a call above it)
  B  UNHEDGED SHORT PUT  a short put with no long put below it. Short CALLS are naked by design (covered by the shares you hold): INFO only
  C  NO STOP ORDER       a short with no matching super order (HIGH when its premium is already at 3x the sold price)
  D  STOP FIRED, NOT FIXED  the stop leg fired (TRADED / TRIGGERED) but a short is still open, or the stop leg is CANCELLED / REJECTED while the short is open
  E  TRIGGER PASSED      the premium is at or above the stop price but the stop leg is still PENDING (or at / below the target price with the target pending)
  F  STOP HYGIENE        the scan_super_orders.py findings: orphaned stop legs, off-rule stops, quantity mismatches
Writes data/option_scan.json {fetched_at, inputs, findings[...]}.
"""
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
if "--data-dir" in sys.argv:   # used by test_scan_options.py: a folder holding covered_call_signals.json, super_scan.json, cc_config.json and cc_raw/super_orders.txt
    ROOT = Path(sys.argv[sys.argv.index("--data-dir") + 1])
    DATA = ROOT / "data"
IST = timezone(timedelta(hours=5, minutes=30))
TITLES = {"A": "ORPHANED LONG (bought leg that hedges nothing)", "B": "UNHEDGED SHORT PUT / NAKED CALL", "C": "SHORT WITH NO STOP ORDER", "D": "STOP FIRED BUT NOT FIXED",
          "E": "TRIGGER ALREADY PASSED, STOP STILL PENDING", "F": "STOP-ORDER HYGIENE (orphaned / off-rule / quantity)"}
HEAD = re.compile(r"^(\d+)\s*\|\s*(BUY|SELL)\s+(\S+)\s*\|\s*(\S+)")
ENTRY = re.compile(r"Qty:\s*(\d+)\s*\(remaining\s*(\d+)\)\s*@\s*₹([\d,.]+)")
LEG = re.compile(r"(STOP_LOSS_LEG|TARGET_LEG|ENTRY_LEG):\s*(\S+)\s+qty\s*(\S+)\s*@\s*₹([\d,.]+)\s*\(trail\s*([\d.]+)\)")


def num(x):
    return float(str(x).replace(",", ""))


def parse_super(text):
    orders, cur = [], None
    for line in text.splitlines():
        m = HEAD.match(line.strip())
        if m:
            cur = {"order_id": m.group(1), "side": m.group(2), "symbol": m.group(3), "status": m.group(4), "legs": {}}
            orders.append(cur)
            continue
        if not cur:
            continue
        e = ENTRY.search(line)
        if e:
            cur["qty"], cur["remaining"], cur["entry"] = int(e.group(1)), int(e.group(2)), num(e.group(3))
        for lg in LEG.finditer(line):
            cur["legs"][lg.group(1)] = {"status": lg.group(2), "price": num(lg.group(4)), "trail": float(lg.group(5))}
    return [o for o in orders if "entry" in o]


def main():
    as_json = "--json" in sys.argv
    today = datetime.now(IST).date().isoformat()
    cfg = json.loads((DATA / "cc_config.json").read_text(encoding="utf-8")) if (DATA / "cc_config.json").exists() else {"rules": {}}
    mult = cfg["rules"].get("stop_premium_multiple", 3)
    cc = json.loads((ROOT / "covered_call_signals.json").read_text(encoding="utf-8"))
    so_file = DATA / "cc_raw" / "super_orders.txt"
    scan_file = DATA / "super_scan.json"
    stale = []
    pos_file = DATA / "cc_raw" / "positions.txt"   # the raw positions the engine built the legs from
    if not pos_file.exists():
        stale.append("open positions (cc_raw/positions.txt): missing")
    elif datetime.fromtimestamp(pos_file.stat().st_mtime, IST).date().isoformat() != today:
        stale.append(f"open positions: from {datetime.fromtimestamp(pos_file.stat().st_mtime, IST).date().isoformat()}, not today ({today})")
    if str(cc.get("generated_at", ""))[:10] != today:
        stale.append(f"covered-call signals built {str(cc.get('generated_at'))[:10]}, not today")
    if not so_file.exists():
        stale.append("super order book: missing")
    elif datetime.fromtimestamp(so_file.stat().st_mtime, IST).date().isoformat() != today:
        stale.append(f"super order book: from {datetime.fromtimestamp(so_file.stat().st_mtime, IST).date().isoformat()}, not today")
    scan = json.loads(scan_file.read_text(encoding="utf-8")) if scan_file.exists() else None
    if scan is None or str(scan.get("fetched_at", ""))[:10] != today:
        stale.append("stop-order scan (scan_super_orders.py): missing or not from today")

    legs = [l for s in cc["stocks"] for l in s.get("legs", [])]
    shorts = [l for l in legs if l["side"] == "SHORT"]
    orders = [o for o in parse_super(so_file.read_text(encoding="utf-8")) if o["side"] == "SELL"] if so_file.exists() else []
    findings = []

    def label(l):
        return f"{l['symbol']} {l['strike']:g}{l['type']} {l['expiry']}"

    def add(sec, sev, sym, lab, concern, action):
        findings.append({"section": sec, "severity": sev, "symbol": sym, "leg": lab, "concern": concern, "action": action})

    groups = {}
    for l in legs:
        groups.setdefault((l["symbol"], l["expiry"], l["type"]), []).append(l)
    for (sym, exp, typ), ls in groups.items():
        sh = [l for l in ls if l["side"] == "SHORT"]
        lo = [l for l in ls if l["side"] == "LONG"]
        for lg in lo:
            covers = [s for s in sh if (lg["strike"] < s["strike"] if typ == "PE" else lg["strike"] > s["strike"])]
            if not covers:
                why = "no short against it" if not sh else "not on the protective side of any short"
                add("A", "WARN", sym, label(lg), f"Long {lg['strike']:g}{typ} ({lg['qty']} qty) {why}; P&L Rs{lg['pnl_rs']:,.0f}, expiry {exp}",
                    "In profit: book it or let it run" if lg["pnl_rs"] > 0 else "Sell it or let it expire")
        for s in sh:
            if typ == "PE":
                cover = sum(l["qty"] for l in lo if l["strike"] < s["strike"])
                if cover < s["qty"]:
                    add("B", "WARN" if cover else "HIGH", sym, label(s), f"Short {s['strike']:g}PE: {s['qty'] - cover} of {s['qty']} qty has no put hedge below it (expiry {exp})", "Buy the hedge put or close the short")
            else:
                add("B", "INFO", sym, label(s), f"Short {s['strike']:g}CE ({s['qty']} qty) is a naked call (by design; covered by shares you hold)", "Watch the 3x stop and the Supertrend colour")

    # match each SELL super order to an open short: same symbol, same sold average, same quantity first
    used, matched = set(), {}
    for pass_qty in (True, False):
        for i, o in enumerate(orders):
            if i in matched:
                continue
            for j, s in enumerate(shorts):
                if j in used or s["symbol"] != o["symbol"] or abs(s["sell_avg"] - o["entry"]) > 0.0051 or (pass_qty and s["qty"] != o["qty"]):
                    continue
                used.add(j)
                matched[i] = s
                break
    fired_ok = []
    for i, o in enumerate(orders):
        sl, tg = o["legs"].get("STOP_LOSS_LEG"), o["legs"].get("TARGET_LEG")
        s = matched.get(i)
        if s is None:
            if sl and sl["status"] in ("TRADED", "TRIGGERED") or tg and tg["status"] == "TRADED":
                fired_ok.append(f"{o['symbol']} @ {o['entry']:g}")
            continue
        lab = label(s)
        if sl and sl["status"] in ("TRADED", "TRIGGERED"):
            add("D", "HIGH", s["symbol"], lab, f"Stop leg of order {o['order_id']} is {sl['status']} but a short of {s['qty']} qty is still open on a contract that matches it", "Check the order book; close it by hand in Dhan if the buy-back did not fill")
        elif sl and sl["status"] in ("CANCELLED", "REJECTED", "EXPIRED") and not (tg and tg["status"] == "TRADED"):
            add("D", "HIGH", s["symbol"], lab, f"Stop leg of order {o['order_id']} is {sl['status']}: the short of {s['qty']} qty has no stop", "Place a new stop (close and re-enter as a super order, or a daily stop order)")
        if sl and sl["status"] == "PENDING" and s["ltp"] >= sl["price"] > 0:
            add("E", "HIGH", s["symbol"], lab, f"Premium {s['ltp']:g} is at or above the stop price {sl['price']:g} (order {o['order_id']}) but the stop leg is still PENDING: it has not fired", "Close it by hand in Dhan now")
        elif tg and tg["status"] == "PENDING" and 0 < tg["price"] and s["ltp"] <= tg["price"]:
            add("E", "WARN", s["symbol"], lab, f"Premium {s['ltp']:g} is at or below the target price {tg['price']:g} (order {o['order_id']}) but the target is still PENDING", "Book the profit or check the order")
    for j, s in enumerate(shorts):
        if j not in used:
            hit = s["ltp"] >= mult * s["sell_avg"]
            add("C", "HIGH" if hit else "WARN", s["symbol"], label(s), f"No super order matches this short ({s['qty']} @ {s['sell_avg']:g}, premium {s['ltp']:g}" + (f", already {s['ltp'] / s['sell_avg']:.1f}x)" if hit else ")"),
                "Close it now" if hit else "Close and re-enter as a super order, or place a daily stop order")
    for f in (scan or {}).get("findings", []):
        leg = f"{f['symbol']} {f['strike']:g}{f['opt_type']} {f.get('expiry')}" if f.get("strike") else f["symbol"]
        add("F", f["severity"], f["symbol"], leg, f"{f['check']} {f['name']}: {f['concern']}" + (f" (order {f['order_id']})" if f.get("order_id") else ""), f["action"])

    order = {"HIGH": 0, "WARN": 1, "INFO": 2}
    findings.sort(key=lambda f: (f["section"], order[f["severity"]], f["symbol"], f["leg"]))
    out = {"fetched_at": datetime.now(IST).isoformat(timespec="seconds"), "stale_inputs": stale, "open_legs": len(legs), "shorts": len(shorts), "super_orders": len(orders),
           "fired_cleanly": fired_ok, "findings": findings}
    if "--data-dir" not in sys.argv:
        (DATA / "option_scan.json").write_text(json.dumps(out, indent=1))
    if as_json:
        print(json.dumps(out, indent=1))
        return
    print(f"ND option position scan: {len(legs)} open legs, {len(shorts)} short, {len(legs) - len(shorts)} long; {len(orders)} SELL super orders in the book.")
    for s in stale:
        print(f"  !! STALE INPUT - {s}")
    print("  (the super order book has no strike or expiry: matching to a short is by symbol + sold average, so verify before acting)")
    for sec in "ABCDEF":
        rows = [f for f in findings if f["section"] == sec]
        high = sum(1 for f in rows if f["severity"] == "HIGH")
        info = [f for f in rows if f["severity"] == "INFO"]
        if info and "--all" not in sys.argv:
            rows = [f for f in rows if f["severity"] != "INFO"]
        print(f"\n== {sec}  {TITLES[sec]}: {len(rows)}" + (f" ({high} high)" if high else "") + (f" + {len(info)} naked calls (by design, INFO; --all lists them)" if info and "--all" not in sys.argv else "") + " ==")
        for f in rows:
            print(f"  {f['severity']:<4} {f['leg']:<34} {f['concern']}  -> {f['action']}")
        if sec == "D":
            print(f"  stops that fired and closed cleanly (order book): {len(fired_ok)}" + (f" ({', '.join(fired_ok)})" if fired_ok else ""))
        if not rows:
            print("  none")


if __name__ == "__main__":
    main()
