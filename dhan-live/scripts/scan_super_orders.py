"""Scan the Dhan (ND) super order book for invalid or missing protective stop legs on the open option positions.

Usage: python dhan-live/scripts/scan_super_orders.py
Inputs (raw MCP text, saved verbatim by the dhan-superorder skill / refresh-dhan; both must be from TODAY):
  data/cc_raw/positions.txt        portfolio_agent_tool  action positions
  data/cc_raw/super_orders.txt     orderbook_agent_tool  action super_list
Writes data/super_scan.json {fetched_at, findings[...]} and prints a table.

The super order book shows a symbol and the entry price but NOT the strike or expiry, so an order is matched to a position by
symbol + entry price (sold average) + quantity. The match is therefore approximate: a leg whose average moved after several fills,
or two legs of one stock sold at the same price, can mismatch. Each finding says so; verify before cancelling anything.

Checks (the user's pattern: SELL entry, stop-loss leg at ~3x the sold price, optional target leg ~40%, trailing jump):
  S1 ORPHAN     a super order whose entry traded but no open short position matches it, while a stop/target leg is still PENDING.
                If that stop leg fires it BUYS a new long position (HIGH, "likely": matching is approximate).
  S2 NO STOP    an open short option leg with no matching super order stop leg, so nothing protects it.
  S3 OFF-RULE   the stop is not near stop_premium_multiple x the sold price (outside +-1x).
  S4 QUANTITY   the super order quantity differs from the open short quantity.
"""
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
IST = timezone(timedelta(hours=5, minutes=30))
sys.path.insert(0, str(ROOT / "scripts"))
from compute_covered_call import parse_positions  # noqa: E402  (same parser the covered-call engine uses)

HEAD = re.compile(r"^(\d+)\s*\|\s*(BUY|SELL)\s+(\S+)\s*\|\s*(\S+)")
ENTRY = re.compile(r"Qty:\s*(\d+)\s*\(remaining\s*(\d+)\)\s*@\s*₹([\d,.]+)")
LEG = re.compile(r"(STOP_LOSS_LEG|TARGET_LEG|ENTRY_LEG):\s*(\S+)\s+qty\s*(\S+)\s*@\s*₹([\d,.]+)\s*\(trail\s*([\d.]+)\)")
NAMES = {"S1": "ORPHAN", "S2": "NO STOP", "S3": "OFF-RULE", "S4": "QUANTITY"}


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
    cfg = json.loads((DATA / "cc_config.json").read_text(encoding="utf-8"))
    mult = cfg["rules"].get("stop_premium_multiple", 3)
    now_day = datetime.now(IST).strftime("%Y-%m-%d")
    for nm in ("positions.txt", "super_orders.txt"):
        f = DATA / "cc_raw" / nm
        if not f.exists() or datetime.fromtimestamp(f.stat().st_mtime, IST).strftime("%Y-%m-%d") != now_day:
            sys.exit(f"REFUSED: data/cc_raw/{nm} is missing or not from today. Pull it from the Dhan MCP first (portfolio positions / orderbook super_list).")
    exp = cfg.get("expiries", [])
    legs = parse_positions((DATA / "cc_raw" / "positions.txt").read_text(encoding="utf-8"), exp)
    shorts = [l for l in legs if l["side"] == "SHORT"]
    orders = [o for o in parse_super((DATA / "cc_raw" / "super_orders.txt").read_text(encoding="utf-8")) if o["side"] == "SELL"]
    findings, used = [], set()

    def add(check, sev, o, leg, concern, action):
        findings.append({"check": check, "name": NAMES[check], "severity": sev, "order_id": o["order_id"] if o else None,
                         "symbol": (o or leg)["symbol"], "expiry": leg.get("expiry") if leg else None, "strike": leg.get("strike") if leg else None,
                         "opt_type": leg.get("type") if leg else None, "concern": concern, "action": action})

    matched = {}
    for i, o in enumerate(orders):
        for j, l in enumerate(shorts):
            if j in used or l["symbol"] != o["symbol"] or abs(l["sell_avg"] - o["entry"]) > 0.0051:
                continue
            used.add(j)
            matched[i] = l
            break
    for i, o in enumerate(orders):
        pending = {k: v for k, v in o["legs"].items() if v["status"] == "PENDING" and k != "ENTRY_LEG"}
        l = matched.get(i)
        if l is None:
            if pending:
                legs_txt = " + ".join(f"{k.replace('_LEG', '').lower()} {v['price']:g}" for k, v in pending.items())
                add("S1", "HIGH", o, None, f"Likely orphaned: sold {o['qty']} @ {o['entry']:g} but no open short matches; {legs_txt} still pending: a stop firing would BUY a new long",
                    f"Check the position; if closed, cancel the legs (order {o['order_id']})")
            continue
        sl = o["legs"].get("STOP_LOSS_LEG")
        if sl and sl["status"] == "PENDING":
            r = sl["price"] / o["entry"]
            if not (mult - 1) <= r <= (mult + 1):
                add("S3", "WARN", o, l, f"Stop {sl['price']:g} is {r:.1f}x the sold {o['entry']:g} (rule {mult}x)", f"Move the stop leg to {mult * o['entry']:.2f}")
        else:
            add("S2", "WARN", o, l, "Super order has no pending stop leg", "Place a protective stop")
        if o["qty"] != l["qty"]:
            add("S4", "WARN", o, l, f"Super order covers {o['qty']} but {l['qty']} are open", "Check the legs")
    for j, l in enumerate(shorts):
        if j not in used:
            add("S2", "WARN", None, l, f"No super order matches this short ({l['qty']} @ {l['sell_avg']:g}): no stop protects it", "Close and re-enter as a super order, or use a daily stop order")
    order = {"HIGH": 0, "WARN": 1}
    findings.sort(key=lambda f: (order[f["severity"]], f["check"], f["symbol"]))
    (DATA / "super_scan.json").write_text(json.dumps({"fetched_at": datetime.now(IST).isoformat(timespec="seconds"), "orders_checked": len(orders), "shorts": len(shorts), "findings": findings}, indent=1))
    print(f"Super order scan: {len(orders)} SELL super orders vs {len(shorts)} open short option legs -> {len(findings)} findings ({sum(1 for f in findings if f['severity'] == 'HIGH')} high)")
    for f in findings:
        leg = f"{f['strike']:g}{f['opt_type']}" if f.get("strike") else ""
        print(f"  {f['severity']:<4} {f['check']} {f['name']:<9} {f['symbol']:<12} {leg:<9} order {f['order_id'] or '-':<17} {f['concern']}  -> {f['action']}")


if __name__ == "__main__":
    main()
