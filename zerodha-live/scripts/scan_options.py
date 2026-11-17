"""Scan every open AZ option position (read-only; places nothing).

Usage: python zerodha-live/scripts/scan_options.py [--json] [--all]   (--all also lists every naked call, which are INFO only)
Needs, from the SAME day (the script says so when one is stale):
  data/cc_positions.json (cc_positions.py)   data/cc_gtts.json (cc_gtts.py: active + triggered GTTs)   data/cc_orders_today.json (cc_orders.py)
  data/gtt_scan.json (scan_gtts.py)          data/cc_config.json
Sections (A-G):
  A  ORPHANED LONG       a long (bought) leg that hedges no short: same stock / expiry / type, protective side (put: below the short, call: above it)
  B  UNHEDGED SHORT PUT  a short put with no long put below it (a bull put spread is the user's put structure). Short CALLS are naked by design: listed as INFO
  C  NO ACTIVE STOP GTT  a short leg with no active buy-back GTT on its contract
  D  GTT FIRED, NOT FIXED a GTT that triggered but the position is still open / its buy-back order was rejected, cancelled or is unfilled / no order is found
  E  TRIGGER PASSED      a short leg whose premium is already at or above its active GTT's stop trigger (or at / below the profit trigger) but the GTT is still active
  F  GTT HYGIENE         stale / wrong-side / wrong-quantity / duplicate / off-rule GTTs from scan_gtts.py (G1-G7)
  G  NO PROFIT TARGET    a short whose active GTT has only a stop trigger (single / trailing GTT), no profit (lower) trigger; suggests the target at the profit_exit_decay_pct rule
Writes data/option_scan.json {fetched_at, inputs, findings[{section, severity, symbol, tradingsymbol, concern, action}]}.
"""
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
if "--data-dir" in sys.argv:   # used by test_scan_options.py
    DATA = Path(sys.argv[sys.argv.index("--data-dir") + 1])
IST = timezone(timedelta(hours=5, minutes=30))
RX = re.compile(r"^(.+?)(\d\d)([A-Z]{3})(\d+(?:\.\d+)?)(CE|PE)$")
TITLES = {"A": "ORPHANED LONG (bought leg that hedges nothing)", "B": "UNHEDGED SHORT PUT / NAKED CALL", "C": "SHORT WITH NO ACTIVE STOP GTT", "D": "GTT FIRED BUT NOT FIXED",
          "E": "TRIGGER ALREADY PASSED, GTT STILL ACTIVE", "F": "GTT HYGIENE (stale / wrong / off-rule)", "G": "STOP GTT BUT NO PROFIT TARGET"}


def load(n, default=None):
    p = DATA / n
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def day(ts):
    return str(ts)[:10] if ts else None


def main():
    as_json = "--json" in sys.argv
    today = datetime.now(IST).date().isoformat()
    cfg = load("cc_config.json")
    mult = cfg["rules"].get("stop_premium_multiple", 3)
    pos_d, gtt_d, ord_d, scan_d = load("cc_positions.json"), load("cc_gtts.json"), load("cc_orders_today.json"), load("gtt_scan.json")
    stale = []
    for name, d, key in (("positions (cc_positions.py)", pos_d, "fetched_at"), ("GTT list (cc_gtts.py)", gtt_d, "fetched_at"), ("order list (cc_orders.py)", ord_d, "fetched_at"), ("GTT scan (scan_gtts.py)", scan_d, "fetched_at")):
        if d is None:
            stale.append(f"{name}: missing")
        elif day(d.get(key)) != today:
            stale.append(f"{name}: from {day(d.get(key))}, not today ({today})")
    if pos_d is None or gtt_d is None:
        sys.exit("Missing positions or GTT data: pull positions and GTTs first.\n" + "\n".join(stale))
    legs = pos_d["legs"]
    findings = []

    def add(sec, sev, leg_or_sym, ts, concern, action):
        m = RX.match(ts) if ts else None
        findings.append({"section": sec, "severity": sev, "symbol": (m.group(1) if m else leg_or_sym), "tradingsymbol": ts, "concern": concern, "action": action})

    groups = {}
    for l in legs:
        groups.setdefault((l["symbol"], l["expiry"], l["type"]), []).append(l)

    # A / B: hedge structure per stock + expiry + type
    for (sym, exp, typ), ls in groups.items():
        shorts = [l for l in ls if l["side"] == "SHORT"]
        longs = [l for l in ls if l["side"] == "LONG"]
        for lg in longs:
            if typ == "PE":
                covers = [s for s in shorts if lg["strike"] < s["strike"]]
            else:
                covers = [s for s in shorts if lg["strike"] > s["strike"]]
            if not covers:
                why = "no short against it" if not shorts else "not on the protective side of any short"
                gain = lg["pnl_rs"]
                add("A", "WARN", sym, lg["tradingsymbol"], f"Long {lg['strike']:g}{typ} ({lg['qty']} qty) {why}; P&L Rs{gain:,.0f}, expiry {exp}",
                    "In profit: book it or let it run" if gain > 0 else "Sell it or let it expire")
        for s in shorts:
            if typ == "PE":
                cover = sum(l["qty"] for l in longs if l["strike"] < s["strike"])
                if cover < s["qty"]:
                    miss = s["qty"] - cover
                    add("B", "WARN" if cover else "HIGH", sym, s["tradingsymbol"], f"Short {s['strike']:g}PE: {miss} of {s['qty']} qty has no put hedge below it (expiry {exp})", "Buy the hedge put or close the short")
            else:
                add("B", "INFO", sym, s["tradingsymbol"], f"Short {s['strike']:g}CE ({s['qty']} qty) is a naked call (by design; covered only by shares you hold)", "Watch the 3x stop and the Supertrend colour")

    # C: shorts without an active buy-back GTT
    active = gtt_d.get("active", {})
    for l in legs:
        if l["side"] == "SHORT" and l["tradingsymbol"] not in active:
            hit = l["ltp"] >= mult * l["avg"]
            add("C", "HIGH" if hit else "WARN", l["symbol"], l["tradingsymbol"], f"No active buy-back GTT (premium {l['ltp']:g}, sold {l['avg']:g}" + (f", already {l['ltp'] / l['avg']:.1f}x: a GTT would fire at once)" if hit else ")"),
                "Close it now (a GTT would fire at once)" if hit else "Place the protective GTT (zerodha-gtt-order)")

    # D: GTTs that fired
    orders = (ord_d or {}).get("orders", [])
    open_short = {l["tradingsymbol"]: l for l in legs if l["side"] == "SHORT"}
    for g in gtt_d.get("triggered", []):
        t = g["tradingsymbol"]
        when = day(g.get("triggered_at"))
        mine = [o for o in orders if o["tradingsymbol"] == t and o["side"] == "BUY" and o["gtt"]]
        short = open_short.get(t)
        if when == today:
            if mine:
                bad = [o for o in mine if o["status"] in ("REJECTED", "CANCELLED")]
                openo = [o for o in mine if o["status"] not in ("COMPLETE", "REJECTED", "CANCELLED")]
                if bad:
                    o = bad[0]
                    add("D", "HIGH", t, t, f"GTT {g['id']} fired at {str(g['triggered_at'])[11:16]} but its buy-back order {o['order_id']} was {o['status']}" + (f" ({o['message']})" if o["message"] else "") + (f"; the short ({short['qty']} qty) is still open" if short else ""), "Close it by hand in Kite now" if short else "Check the position")
                elif openo:
                    o = openo[0]
                    add("D", "HIGH", t, t, f"GTT {g['id']} fired but its buy-back order {o['order_id']} is still {o['status']} (limit {o['price']:g} not reached; {o['filled']} of {o['qty']} filled)" + (f"; the short ({short['qty']} qty) is still open" if short else ""), "Modify the limit or close it by hand in Kite")
                elif short:
                    filled = sum(o["filled"] or 0 for o in mine)
                    add("D", "HIGH", t, t, f"GTT {g['id']} fired and bought back {filled}, but a short of {short['qty']} qty is still open on this contract", "Check whether the quantity matched; close the rest in Kite")
            else:
                add("D", "WARN" if not short else "HIGH", t, t, f"GTT {g['id']} fired today ({str(g['triggered_at'])[11:16]}) but no buy-back order from a GTT is in today's order list" + (f"; the short ({short['qty']} qty) is still open" if short else ""),
                    "Check the order book in Kite" if not short else "Close it by hand in Kite now")
        elif short:
            add("D", "WARN", t, t, f"GTT {g['id']} fired on {when} but a short of {short['qty']} qty is still open on this contract (re-sold, or the buy-back failed)", "Confirm in Kite; add a new GTT if it is a new position")

    d_bad = {f["tradingsymbol"] for f in findings if f["section"] == "D"}
    fired_today = [g for g in gtt_d.get("triggered", []) if day(g.get("triggered_at")) == today]
    fired_ok = [g["tradingsymbol"] for g in fired_today if g["tradingsymbol"] not in d_bad]

    # E: trigger already passed on an active GTT
    for g in gtt_d.get("gtts", []):
        t = g["tradingsymbol"]
        s = open_short.get(t)
        if not s or not any(o["side"] == "BUY" for o in g["orders"]):
            continue
        trig = sorted(g.get("triggers") or [])
        if not trig:
            continue
        up, lo = trig[-1], (trig[0] if len(trig) > 1 else None)
        if s["ltp"] >= up:
            add("E", "HIGH", t, t, f"Premium {s['ltp']:g} is at or above the stop trigger {up:g} (GTT {g['id']}) but it is still ACTIVE: the stop has not fired (limit not reached, delayed, or invalid)", "Close it by hand in Kite now")
        elif lo is not None and s["ltp"] <= lo:
            add("E", "WARN", t, t, f"Premium {s['ltp']:g} is at or below the profit trigger {lo:g} (GTT {g['id']}) but it is still ACTIVE", "Book the profit or check the GTT")

    # G: a short with active GTT(s) but no profit target (user, 2026-11-17, same check as ND): a two-leg GTT has a lower (profit) and an upper (stop) trigger;
    # a single or trailing GTT has only the stop. The Zerodha tool cannot create trailing GTTs, so the fix is a two-leg GTT (zerodha-gtt-order) or the Kite app.
    decay = cfg.get("rules", {}).get("profit_exit_decay_pct", 60) if isinstance(cfg, dict) else 60
    by_contract = {}
    for g in gtt_d.get("gtts", []):
        if any(o["side"] == "BUY" for o in g["orders"]):
            by_contract.setdefault(g["tradingsymbol"], []).append(g)
    for t, gs in by_contract.items():
        s = open_short.get(t)
        if s and all(len(g.get("triggers") or []) < 2 for g in gs) and gs:
            want = round(s["avg"] * (1 - decay / 100), 2)
            kinds = ", ".join(sorted({str(g.get("type")) for g in gs}))
            add("G", "WARN", s["symbol"], t, f"Active GTT {gs[0]['id']} ({kinds}) has a stop but no profit target; sold {s['avg']:g}, premium {s['ltp']:g}",
                f"Add a profit target at about {want:g} (a two-leg GTT: /zerodha-gtt-order or the Kite app)")

    # F: GTT hygiene findings
    for f in (scan_d or {}).get("findings", []):
        add("F", f["severity"], f["symbol"], f["tradingsymbol"], f"{f['check']} {f['name']}: {f['concern']} (GTT {f['gtt_id']})", f["action"])

    order = {"HIGH": 0, "WARN": 1, "INFO": 2}
    findings.sort(key=lambda f: (f["section"], order[f["severity"]], f["symbol"], f["tradingsymbol"] or ""))
    out = {"fired_ok_today": fired_ok, "fetched_at": datetime.now(IST).isoformat(timespec="seconds"), "inputs": {"positions": (pos_d or {}).get("fetched_at"), "gtts": (gtt_d or {}).get("fetched_at"),
           "orders": (ord_d or {}).get("fetched_at"), "gtt_scan": (scan_d or {}).get("gtts_fetched_at")}, "stale_inputs": stale, "open_legs": len(legs),
           "triggered_gtts": len(gtt_d.get("triggered", [])), "findings": findings}
    (DATA / "option_scan.json").write_text(json.dumps(out, indent=1))
    if as_json:
        print(json.dumps(out, indent=1))
        return
    print(f"Option position scan: {len(legs)} open legs, {sum(1 for l in legs if l['side'] == 'SHORT')} short, {sum(1 for l in legs if l['side'] == 'LONG')} long; {len(gtt_d.get('triggered', []))} fired GTTs in the list.")
    for s in stale:
        print(f"  !! STALE INPUT - {s}")
    for sec in "ABCDEFG":
        rows = [f for f in findings if f["section"] == sec]
        high = sum(1 for f in rows if f["severity"] == "HIGH")
        info = [f for f in rows if f["severity"] == "INFO"]
        if info and "--all" not in sys.argv:
            rows = [f for f in rows if f["severity"] != "INFO"]   # naked calls are by design: counted, not listed
        print(f"\n== {sec}  {TITLES[sec]}: {len(rows)}" + (f" ({high} high)" if high else "") + (f" + {len(info)} naked calls (by design, INFO; --all lists them)" if info and "--all" not in sys.argv else "") + " ==")
        for f in rows:
            print(f"  {f['severity']:<4} {f['tradingsymbol'] or f['symbol']:<24} {f['concern']}  -> {f['action']}")
        if sec == "D":
            print(f"  fired today and bought back cleanly: {len(fired_ok)}" + (f" ({', '.join(fired_ok)})" if fired_ok else "") + f"; fired earlier: {len(gtt_d.get('triggered', [])) - len(fired_today)}")
        if not rows:
            print("  none")


if __name__ == "__main__":
    main()
