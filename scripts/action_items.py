"""One prioritized list of what is pending for ND (Dhan) and AZ (Zerodha) (read-only; places and changes nothing).

This is the ONE deliberate place that looks at both brokers, and only to display: each broker is read by its own function from its own folder's files
(no code or data is shared between them, and nothing is imported from dhan-live/ or zerodha-live/).
Usage: python scripts/action_items.py [--json]
Sections: 0 Refresh status | 1 Close now (in the broker app) | 2 Run a skill | 3 Decide | 4 Housekeeping.
Everything is as of the last refresh of each broker; section 0 says how old that is and whether a refresh is due.
"""
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
IST = timezone(timedelta(hours=5, minutes=30))
NOW = datetime.now(IST)


def jload(p):
    f = Path(p)
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def ts(x):
    try:
        return datetime.fromisoformat(str(x)).astimezone(IST)
    except Exception:
        return None


def market_open(n=NOW):
    return n.weekday() < 5 and (9, 15) <= (n.hour, n.minute) <= (15, 30)


def last_session(n=NOW):
    """Date of the last session whose close is published (after 16:30 IST on a weekday = today, else the previous weekday)."""
    d = n.date()
    if not (n.weekday() < 5 and (n.hour, n.minute) >= (16, 30)):
        d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.isoformat()


def broker(folder, name, cmd, order_cmd, orders_label):
    """Read ONE broker's files and return its items. folder = 'dhan-live' or 'zerodha-live'."""
    b = REPO / folder
    sig = jload(b / f"{folder.split('-')[0]}_live_signals.json") or {}
    cc = jload(b / "covered_call_signals.json") or {}
    g = jload(b / "data" / "guardrails.json") or {}
    scan = jload(b / "data" / "option_scan.json") or {"findings": []}
    hold = jload(b / "data" / "holdings_snapshot.json") or {}
    r = {"name": name, "refresh": [], "close": [], "skill": [], "decide": []}

    # 0 refresh status
    stamps = [t for t in (ts(hold.get("fetched_at")), ts(cc.get("generated_at")), ts(cc.get("live_prices_at"))) if t]
    last = max(stamps) if stamps else None
    md = sig.get("market_data_date") or cc.get("market_data_date")
    age = int((NOW - last).total_seconds() // 60) if last else None
    line = f"{name}: last refresh {last:%d %b %H:%M} IST ({age} min ago), market data {md}" if last else f"{name}: no refresh data found"
    r["refresh"].append(line)
    if age is None or (market_open() and age > 60):
        r["refresh"].append(f"  STALE: the market is open and the refresh is over an hour old: run {cmd}")
    elif md and md < last_session():
        r["refresh"].append(f"  Market data is {md} but the latest published close is {last_session()}: run {cmd} after 16:30 IST" if not (NOW.hour, NOW.minute) >= (16, 30) or NOW.weekday() >= 5 else f"  Market data is {md}, the close of {last_session()} is published: run {cmd} now")
    # guardrails
    blk = g.get("status") == "BLOCK"
    gf = g.get("findings", [])
    glob = [f for f in gf if f.get("level") == "BLOCK" and not f.get("symbol")]
    if glob:
        r["refresh"].append(f"  Guardrail BLOCK (no stock orders until it clears): {glob[0]['id']} {str(glob[0].get('msg'))[:110]}")

    # 1 close now (option exit groups 1, 2, 4 and the event window): one line per leg, reasons joined
    legs = {}

    def add_leg(key, label, why):
        legs.setdefault(key, [label, []])[1].append(why)

    for a in cc.get("alerts", []):
        k = (a["symbol"], a.get("expiry"), a.get("strike"), a.get("opt_type"))
        lab = f"{a['symbol']} {a.get('strike', 0):g}{a.get('opt_type', '')} {a.get('expiry', '')}".strip()
        if str(a.get("type", "")).startswith("3") and "premium" in a["type"]:
            add_leg(k, lab, f"premium {a['concern'].split(' is ')[1].split(' the ')[0]} the sold price: 3x stop hit" if " is " in a["concern"] else "3x stop hit")
        elif a.get("type") == "Through hedge":
            add_leg(k, lab, "through the hedge (maximum loss)")
        elif a.get("type") == "Event close" and a.get("level") == "BREACH":
            add_leg(k, lab, "inside the results / ex-dividend close window")
    for f in scan.get("findings", []):
        if f.get("section") in ("D", "E") and f.get("severity") == "HIGH":   # (section C HIGH = already past 3x: the 3x alert above covers it)
            lab = f.get("tradingsymbol") or f.get("leg")
            add_leg(("scan", lab), lab, f["concern"][:90])
    r["close"] = [f"{lab}: " + "; ".join(dict.fromkeys(why)) for lab, why in legs.values()]

    # 2 run a skill
    today = NOW.date().isoformat()
    bought_today = set()
    if folder.startswith("zerodha"):   # AZ records buys in zerodha_trades.json: an entry already bought today is no longer pending
        zt = jload(b / "data" / "zerodha_trades.json") or {}
        bought_today = {s for s, d in (zt.get("entry_dates") or {}).items() if d == today} | {s for s, d in (zt.get("last_buy") or {}).items() if d == today}
    orders_snap = jload(b / "data" / "orders_snapshot.json") or {}
    pending = len(orders_snap.get("orders", []))
    # a signal that already has a pending order on the same side is not "to do" any more (the order builders skip it too)
    pend = {(o.get("symbol"), (o.get("side") or "").upper()) for o in orders_snap.get("orders", [])}
    sym = lambda e: e.get("symbol") if isinstance(e, dict) else e
    md = sig.get("market_data_date")
    def stale_entry(e):   # an entry whose signal day is not the latest session is a missed day and is never ordered
        return isinstance(e, dict) and md and e.get("date") and e["date"] != md
    ent = [e for e in sig.get("entries", []) if sym(e) not in bought_today and (sym(e), "BUY") not in pend and not stale_entry(e)]
    done = len(sig.get("entries", [])) - len(ent)
    ex = len([e for e in sig.get("exits", []) if (sym(e), "SELL") not in pend])
    ad = len([e for e in sig.get("addons", []) if (sym(e), "BUY") not in pend])
    en = len(ent)
    if ex or ad or en:
        why = " (blocked until the guardrail clears: refresh first)" if blk else ""
        r["skill"].append(f"{order_cmd}: {ex} exits, {ad} add-ons, {en} entries{why}")
    elif done:
        r["skill"].append(f"No stock orders to place ({done} entry signal(s) already ordered, bought today or a missed day)")
    sh = cc.get("shares") or {}
    sh_e, sh_x = len(sh.get("entries", [])), len(sh.get("exits", []))
    sh_a = sum(1 for x in sh.get("rows", []) if x.get("avg_status") == "ADD")
    if sh_e or sh_x or sh_a:
        r["skill"].append(f"{order_cmd} (investment-share stages): {sh_x} exits, {sh_e} entries, {sh_a} averaging due")
    gtt_missing = [f for f in scan.get("findings", []) if f.get("section") == "C" and f.get("severity") == "WARN"]
    gtt_hyg = [f for f in scan.get("findings", []) if f.get("section") == "F"]
    if gtt_missing or gtt_hyg:
        tool = "/zerodha-gtt-order" if folder.startswith("zerodha") else "/dhan-superorder"
        r["skill"].append(f"{tool}: {len(gtt_missing)} shorts with no stop, {len(gtt_hyg)} stale / off-rule stop findings")
    if pending:
        r["skill"].append(f"{pending} order(s) still pending in the order snapshot: after the next open, {cmd} records the fills")

    # 3 decide
    for f in scan.get("findings", []):
        if f.get("section") == "B" and f.get("severity") == "HIGH":
            r["decide"].append(f"Unhedged short put: {f.get('tradingsymbol') or f.get('leg')}: {f['concern']}")
    orph = [f for f in scan.get("findings", []) if f.get("section") == "A"]
    if orph:
        win = [f for f in orph if "In profit" in f.get("action", "")]
        r["decide"].append(f"{len(orph)} orphaned long leg(s) (sell or let expire)" + (f"; in profit: {', '.join((x.get('tradingsymbol') or x.get('leg')) for x in win)}" if win else ""))
    flips = [a for a in cc.get("alerts", []) if a.get("type") == "Exit"]
    if flips:
        r["decide"].append(f"{len(flips)} Supertrend colour flip(s) with the old structure still open: {', '.join(a['symbol'] for a in flips[:10])}" + (" ..." if len(flips) > 10 else ""))
    prof = [a for a in cc.get("alerts", []) if a.get("type") == "Profit Exit"]
    if prof:
        r["decide"].append(f"{len(prof)} profit exit(s) (60%+ decayed): book the profit")
    for f in gf:
        if f.get("id") == "I8":
            r["decide"].append(f"Split not recorded: {str(f.get('msg'))[:100]}")
    return r


def housekeeping():
    out = []
    try:
        st = subprocess.run(["git", "status", "--short"], cwd=REPO, capture_output=True, text=True).stdout.strip().splitlines()
        st = [x for x in st if ".playwright-mcp" not in x]
        if st:
            out.append(f"{len(st)} uncommitted file(s) in the repo (say 'push' to commit data; code and skill edits wait for your push): " + ", ".join(x.strip().split()[-1] for x in st[:4]) + (" ..." if len(st) > 4 else ""))
    except Exception:
        pass
    return out


def main():
    nd = broker("dhan-live", "ND (Dhan)", "/refresh-dhan", "/dhan-order", "ND")
    az = broker("zerodha-live", "AZ (Zerodha)", "/refresh-zerodha", "/zerodha-order", "AZ")
    hk = housekeeping()
    if "--json" in sys.argv:
        print(json.dumps({"as_of": NOW.isoformat(timespec="seconds"), "ND": nd, "AZ": az, "housekeeping": hk}, indent=1))
        return
    print(f"Pending action items - {NOW:%a %d %b %Y %H:%M} IST (market {'OPEN' if market_open() else 'closed'})\n")
    print("0. REFRESH STATUS")
    for b in (nd, az):
        for ln in b["refresh"]:
            print("   " + ln)
    for title, key in (("1. CLOSE NOW (in the broker app)", "close"), ("2. RUN A SKILL", "skill"), ("3. DECIDE (your call)", "decide")):
        print(f"\n{title}")
        any_ = False
        for b in (nd, az):
            for ln in b[key]:
                any_ = True
                print(f"   [{b['name'].split()[0]}] {ln}")
        if not any_:
            print("   nothing")
    print("\n4. HOUSEKEEPING")
    for ln in hk or ["nothing uncommitted"]:
        print("   " + ln)


if __name__ == "__main__":
    main()
