"""AZ option ENTRY signals in tiers, from Supertrend flips only (read-only; places nothing).

Rules (user, 2026-11-16):
  * Supertrend only - RSI is NOT used. Green = bull put spread, red = sell call.
  * Tier 1 = the current Supertrend colour began on the latest session (flipped "today", i.e. the last published session).
    Tier 2 = flipped 1-5 trading days ago (the last trading week). Tier 3 = flipped within the last 30 calendar days.
    Tier 4 = flipped within the last 90 calendar days. Tier 5 = flipped more than 90 days ago (oldest, weakest signal). Each stock appears once, in the freshest tier it fits.
  * Stocks with ANY tracked open option leg (expiry on/after track_from in cc_config.json) are left out, so FLIP stocks never appear here.
  * Every row carries a results / ex-dividend ALERT (event_close_days before an event = the window in which an option must be closed).

Reads: covered_call_signals.json (stocks, flip_date, flip_trading_days, expiry, lot, events), data/cc_positions.json (open legs).
Usage: python zerodha-live/scripts/option_entry_tiers.py [--max-per-tier 40] [--tier 1,2] [--json]
"""
import argparse
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TIER_NAMES = {1: "Tier 1 - flipped on the latest session", 2: "Tier 2 - flipped 1-5 trading days ago (last trading week)",
              3: "Tier 3 - flipped within 30 days", 4: "Tier 4 - flipped within 90 days", 5: "Tier 5 - flipped more than 90 days ago (oldest, weakest)"}


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def ist_today():
    return datetime.now(timezone(timedelta(hours=5, minutes=30))).date()


def tier_of(trading_days, cal_days):
    if trading_days == 0:
        return 1
    if trading_days <= 5:
        return 2
    if cal_days <= 30:
        return 3
    if cal_days <= 90:
        return 4
    return 5   # older than 90 days: the weakest entry signal, kept in its own tab


def event_alert(events, expiry, today, close_days):
    """Return (alert text, level) for the nearest upcoming results / ex-dividend. level: 3 = inside window now, 2 = window opens before expiry, 1 = within 60 days, 0 = none."""
    best = (None, 0)
    parts = []
    for ev in sorted(events or [], key=lambda e: e["date"]):
        d = date.fromisoformat(ev["date"])
        if d < today:
            continue
        days = (d - today).days
        start = d - timedelta(days=close_days)
        est = " (est.)" if ev.get("estimated") else ""
        label = "RESULTS" if ev["label"].lower().startswith("result") else "EX-DIV"
        if start <= today:
            lvl, txt = 3, f"!! {label} {d:%d %b}{est} in {days}d - INSIDE the {close_days}-day close window now"
        elif expiry and start < date.fromisoformat(expiry):
            lvl, txt = 2, f"! {label} {d:%d %b}{est} in {days}d - must close by {start:%d %b}, before expiry"
        elif days <= 60:
            lvl, txt = 1, f"{label} {d:%d %b}{est} in {days}d"
        else:
            continue
        parts.append(txt)
        if lvl > best[1]:
            best = (txt, lvl)
    return "; ".join(parts), best[1]


def held_row(s, legs, mdate):
    """One row per stock with open option legs: Supertrend signal, what the colour rule wants, what is open, and whether they agree."""
    legs = sorted(legs, key=lambda l: (str(l.get("expiry")), str(l.get("type")), l.get("strike") or 0))
    opened = " ".join(f"{'S' if l.get('side') == 'SHORT' else 'L'}{l.get('strike'):g}{l.get('type')}" for l in legs)
    td, fd = s.get("flip_trading_days"), s.get("flip_date")
    cal = (mdate - date.fromisoformat(fd)).days if fd else None
    want = "bull put spread" if s.get("colour") == "green" else "sell call"
    # derived from the open legs themselves (covered_call_signals.json can be older than the positions): green wants puts only, red wants calls only
    short_call = any(l.get("side") == "SHORT" and l.get("type") == "CE" for l in legs)
    short_put = any(l.get("side") == "SHORT" and l.get("type") == "PE" for l in legs)
    wrong = short_call if s.get("colour") == "green" else short_put
    status = "FLIP" if wrong else "HOLD"
    verdict = "colour changed: close the old structure first, then re-enter" if wrong else "matches the colour rule"
    return {"symbol": s["symbol"], "colour": s.get("colour"), "flip_date": fd, "flip_trading_days": td, "flip_calendar_days": cal, "spot": s.get("spot"),
            "rule": want, "open_legs": opened, "status": status, "verdict": verdict}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-per-tier", type=int, default=40)
    ap.add_argument("--tier", default="1,2,3,4,5")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    want = {int(x) for x in a.tier.split(",")}

    c = load(ROOT / "covered_call_signals.json")
    pos = load(ROOT / "data" / "cc_positions.json")
    cfg = load(ROOT / "data" / "cc_config.json")
    close_days = cfg["rules"].get("event_close_days", 15)
    held = {l.get("symbol") or l.get("stock") for l in pos.get("legs", [])}   # tracked legs (expiry on/after track_from); ignored_legs is only a count
    held |= {s["symbol"] for s in c["stocks"] if s.get("legs")}
    held.discard(None)
    mdate = date.fromisoformat(c["market_data_date"])
    today = ist_today()

    tiers = {1: [], 2: [], 3: [], 4: [], 5: []}
    legs_by = {}
    for l in pos.get("legs", []):
        legs_by.setdefault(l.get("symbol") or l.get("stock"), []).append(l)
    held_rows = []
    for s in c["stocks"]:
        lg = legs_by.get(s["symbol"]) or s.get("legs") or []
        if lg:
            held_rows.append(held_row(s, lg, mdate))
    held_rows.sort(key=lambda r: (r["status"] != "FLIP", r["symbol"]))
    min_px = cfg["rules"].get("min_entry_price")      # user, 2026-11-26: AZ does not suggest option entries on stocks priced below Rs50
    skipped = {"open option legs": 0, "no expiry/lot": 0, "price below minimum": 0}
    for s in c["stocks"]:
        if s["symbol"] in held:
            skipped["open option legs"] += 1
            continue
        fd, td = s.get("flip_date"), s.get("flip_trading_days")
        if fd is None or td is None:
            continue
        if min_px and (s.get("spot") or 0) < min_px:
            skipped["price below minimum"] += 1
            continue
        cal = (mdate - date.fromisoformat(fd)).days
        t = tier_of(td, cal)
        if not s.get("expiries") or not s["expiries"][0].get("lot"):
            skipped["no expiry/lot"] += 1
            continue
        e = s["expiries"][0]
        structure = "bull put spread" if s["colour"] == "green" else "sell call"
        alert, lvl = event_alert(s.get("events"), e["expiry"], today, close_days)
        dte = (date.fromisoformat(e["expiry"]) - today).days
        if dte < cfg["rules"].get("expiry_min_days", 30):   # only a near expiry is listed for this stock: say so
            alert = f"SHORT EXPIRY: only {dte}d to {e['expiry']}" + (f"; {alert}" if alert else "")
            lvl = max(lvl, 2)
        tiers[t].append({"symbol": s["symbol"], "iv_grade": s.get("iv_tier"), "ivp": s.get("ivp"), "st_dist_pct": s.get("st_dist_pct"), "structure": structure, "colour": s["colour"], "spot": s["spot"], "flip_date": fd, "flip_trading_days": td,
                         "flip_calendar_days": cal, "expiry": e["expiry"], "lot": e["lot"], "alert": alert or "-", "alert_level": lvl})
    for t in tiers:
        tiers[t].sort(key=lambda r: (r["flip_trading_days"], r["symbol"]))

    # Open today (user, 2026-11-27): the best entry rows that pass EVERY gate, best structural IV grade first. Same rule as the page's 'Open today' card:
    # no F&O ban, no event alert or short expiry (alert_level < 2), not within 1.5% of a Supertrend flip, IV percentile 50 or more.
    try:
        ban = set(load(ROOT / "data" / "fno_ban.json").get("symbols", []))
    except Exception:  # noqa: BLE001
        ban = set()
    GRADE = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5}
    allrows = [r for t in tiers for r in tiers[t]]
    clean = [r for r in allrows if r["symbol"] not in ban and r["alert_level"] < 2 and (r.get("st_dist_pct") is None or r["st_dist_pct"] > 1.5) and (r.get("ivp") or -1) >= 50]
    clean.sort(key=lambda r: (GRADE.get(r.get("iv_grade"), 6), -(r.get("ivp") or 0), r["flip_trading_days"], r["symbol"]))
    open_today = clean[:10]

    if a.json:
        print(json.dumps({"market_data_date": c["market_data_date"], "positions_fetched_at": pos.get("fetched_at"), "open_today": open_today, "tiers": tiers, "skipped": skipped, "held_stocks": sorted(held), "held_table": held_rows}, indent=1))
        return
    print(f"AZ option entry signals - Supertrend flips only (no RSI). Market data {c['market_data_date']}; open option legs fetched {pos.get('fetched_at')}.")
    print(f"Left out: {len(held)} stocks with open option legs; {skipped['no expiry/lot']} with no listed expiry/lot" + (f"; {skipped['price below minimum']} priced below Rs{min_px:g}." if min_px else "."))
    print(f"ALERT: '!!' = event inside the {close_days}-day close window now; '!' = window opens before the expiry (close early); plain = event within 60 days. (est.) = date estimated.\n")
    if held_rows:
        print("== Stocks with open option legs: Supertrend signal and whether the open structure still matches it ==")
        print(f"   {'stock':<12} {'Supertrend':<10} {'since':<11} {'age':<8} {'price':>9} {'rule wants':<16} {'status':<6} open legs (S = short, L = long)")
        for r in held_rows:
            age = "today" if r["flip_trading_days"] == 0 else f"{r['flip_trading_days']}td/{r['flip_calendar_days']}d"
            print(f"   {r['symbol']:<12} {str(r['colour']).upper():<10} {str(r['flip_date']):<11} {age:<8} {r['spot']:>9g} {r['rule']:<16} {r['status']:<6} {r['open_legs']}  -> {r['verdict']}")
        print()
    print(f"== Open today: the best {len(open_today)} of {len(allrows)} entry rows that pass every gate (no F&O ban, no event alert, not on a flip knife-edge, IV percentile 50 or more); IV grade A first ==")
    for i, r in enumerate(open_today, 1):
        print(f"   {i:>2} {r['symbol']:<12} grade {r.get('iv_grade') or '-'}  {r['structure']:<16} IVP {r.get('ivp')}  flipped {r['flip_trading_days']}d ago  expiry {r['expiry']}  lot {r['lot']}")
    if not open_today:
        print("   (none: every entry row has an alert or a low IV percentile)")
    print()
    for t in (1, 2, 3, 4, 5):
        rows = tiers[t]
        if t not in want:
            continue
        print(f"== {TIER_NAMES[t]}: {len(rows)} stocks ==")
        if not rows:
            print("   (none)\n")
            continue
        n_shown = rows[: a.max_per_tier]
        print(f"   {'#':>3} {'stock':<12} {'structure':<16} {'price':>9} {'IVP':>4} {'toflip':>7} {'flip':<11} {'age':<8} {'expiry':<11} {'lot':>5}  alert")
        for i, r in enumerate(n_shown, 1):
            age = "today" if r["flip_trading_days"] == 0 else f"{r['flip_trading_days']}td/{r['flip_calendar_days']}d"
            print(f"   {i:>3} {r['symbol']:<12} {r['structure']:<16} {r['spot']:>9g} {(r['ivp'] if r.get('ivp') is not None else '-'):>4} {(('%.1f%%' % r['st_dist_pct']) if r.get('st_dist_pct') is not None else '-'):>7} {r['flip_date']:<11} {age:<8} {r['expiry']:<11} {r['lot']:>5}  {r['alert']}")
        if len(rows) > len(n_shown):
            print(f"   ... {len(rows) - len(n_shown)} more in this tier (use --max-per-tier)")
        print()


if __name__ == "__main__":
    main()
