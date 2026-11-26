"""ND (Dhan) option ENTRY signals in tiers, from Supertrend flips only (read-only; places nothing).

Rules (user, 2026-11-16, same tiers as AZ; ND's own universe and expiries):
  * Universe = the covered-call stocks in data/cc_config.json (the investment-portfolio stocks that have listed options).
  * Supertrend only - no RSI (rules.rsi_override is false for ND). Green = bull put spread (sell the 0.15-delta put, buy the hedge 2 listed strikes lower),
    red = sell the 0.10-delta call (covered by the shares held).
  * Tier 1 = the current colour began on the latest session. Tier 2 = flipped 1-5 trading days ago. Tier 3 = within 30 calendar days.
    Tier 4 = within 90 days. Tier 5 = more than 90 days ago (oldest, weakest signal). Each stock appears once, in the freshest tier it fits.
  * Stocks with ANY open option leg are left out (so a FLIP, where the old structure is still open, never appears here: close it first).
  * Expiry = the first expiry in cc_config.json at least 15 days away (never expiry week); lot size from data/nse_lots.json for that expiry's month.
  * Every row carries a results / ex-dividend ALERT (event_close_days before an event = the window in which an option must be closed).
Reads: covered_call_signals.json (stocks, colour, flip dates, events, open legs), data/cc_config.json, data/nse_lots.json.
Usage: python dhan-live/scripts/option_entry_tiers.py [--tier 1,2] [--json] [--ignore-legs]   (--ignore-legs previews who would qualify if the open legs were closed)
"""
import argparse
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IST = timezone(timedelta(hours=5, minutes=30))
TIER_NAMES = {1: "Tier 1 - flipped on the latest session", 2: "Tier 2 - flipped 1-5 trading days ago (last trading week)", 3: "Tier 3 - flipped within 30 days",
              4: "Tier 4 - flipped within 90 days", 5: "Tier 5 - flipped more than 90 days ago (oldest, weakest)"}
MIN_DAYS = 15   # an expiry nearer than this is skipped (expiry week is never placed)


def load(p):
    return json.loads((ROOT / p).read_text(encoding="utf-8"))


def held_row(s, mdate):
    """One row per stock with open option legs: its Supertrend signal, what the colour rule wants, what is open, and whether they agree."""
    legs = sorted(s.get("legs") or [], key=lambda l: (l["expiry"], l["type"], l["strike"]))
    opened = " ".join(f"{'S' if l['side'] == 'SHORT' else 'L'}{l['strike']:g}{l['type']}" for l in legs)
    td, fd = s.get("flip_trading_days"), s.get("flip_date")
    cal = (mdate - date.fromisoformat(fd)).days if fd else None
    want = "bull put spread" if s.get("colour") == "green" else "sell call"
    status = s.get("status") or "-"
    verdict = {"FLIP": "colour changed: close the old structure first, then re-enter", "HOLD": "matches the colour rule"}.get(status, status)
    return {"symbol": s["symbol"], "colour": s.get("colour"), "flip_date": fd, "flip_trading_days": td, "flip_calendar_days": cal, "spot": s.get("spot"),
            "rule": want, "open_legs": opened, "status": status, "verdict": verdict}


def tier_of(td, cal):
    return 1 if td == 0 else 2 if td <= 5 else 3 if cal <= 30 else 4 if cal <= 90 else 5


def event_alert(events, expiry, today, close_days):
    """(text, level): 3 = inside the close window now, 2 = the window opens before the expiry, 1 = an event within 60 days, 0 = none."""
    parts, best = [], 0
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
        best = max(best, lvl)
    return "; ".join(parts), best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="1,2,3,4,5")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--ignore-legs", action="store_true")
    a = ap.parse_args()
    want = {int(x) for x in a.tier.split(",")}
    cc = load("covered_call_signals.json")
    cfg = load("data/cc_config.json")
    lots = load("data/nse_lots.json")["lots"]
    close_days = cfg["rules"].get("event_close_days", 15)
    week = cfg["rules"].get("expiry_week_days", 5)
    mdate = date.fromisoformat(cc["market_data_date"])
    today = datetime.now(IST).date()
    exp = next((e for e in cfg["expiries"] if (date.fromisoformat(e) - today).days >= MIN_DAYS), None)
    notes = []
    if str(cc.get("generated_at", ""))[:10] != today.isoformat():
        notes.append(f"the covered-call signals were built {str(cc.get('generated_at'))[:10]}, not today: open legs and flips may be out of date (run /refresh-dhan)")
    if exp is None:
        notes.append("no expiry in cc_config.json is at least 15 days away: add the next series to `expiries` before placing")

    tiers = {k: [] for k in TIER_NAMES}
    held, skipped, held_rows = [], [], []
    for s in cc["stocks"]:
        if s.get("legs") and not a.ignore_legs:
            held.append(s["symbol"])
            held_rows.append(held_row(s, mdate))
            continue
        fd, td = s.get("flip_date"), s.get("flip_trading_days")
        if fd is None or td is None:
            skipped.append(s["symbol"])
            continue
        lot = (lots.get(s["symbol"]) or {}).get(exp[:7]) if exp else None
        cal = (mdate - date.fromisoformat(fd)).days
        t = tier_of(td, cal)
        alert, lvl = event_alert(s.get("events"), exp, today, close_days)
        tiers[t].append({"symbol": s["symbol"], "ivp": s.get("ivp"), "structure": "bull put spread" if s["colour"] == "green" else "sell call", "colour": s["colour"], "spot": s["spot"],
                         "flip_date": fd, "flip_trading_days": td, "flip_calendar_days": cal, "expiry": exp, "lot": lot, "alert": alert or "-", "alert_level": lvl})
    for t in tiers:
        tiers[t].sort(key=lambda r: (r["flip_trading_days"], r["symbol"]))
    if a.json:
        print(json.dumps({"market_data_date": cc["market_data_date"], "notes": notes, "expiry": exp, "tiers": tiers, "held_stocks": held, "held_table": held_rows, "no_flip_data": skipped}, indent=1))
        return
    print(f"ND option entry signals - Supertrend flips only (no RSI). Market data {cc['market_data_date']}; expiry used {exp}.")
    for n in notes:
        print(f"  !! {n}")
    print(f"Universe {len(cc['stocks'])} stocks; left out (open option legs): {len(held)}" + (f" ({', '.join(held)})" if held else "") + ".")
    print(f"ALERT: '!!' = event inside the {close_days}-day close window now; '!' = window opens before the expiry (close early); plain = event within 60 days.\n")
    if held_rows:
        print("== Stocks with open option legs: Supertrend signal and whether the open structure still matches it ==")
        print(f"   {'stock':<12} {'Supertrend':<10} {'since':<11} {'age':<8} {'price':>9} {'rule wants':<16} {'status':<6} open legs (S = short, L = long)")
        for r in held_rows:
            age = "today" if r["flip_trading_days"] == 0 else f"{r['flip_trading_days']}td/{r['flip_calendar_days']}d"
            print(f"   {r['symbol']:<12} {str(r['colour']).upper():<10} {str(r['flip_date']):<11} {age:<8} {r['spot']:>9g} {r['rule']:<16} {r['status']:<6} {r['open_legs']}  -> {r['verdict']}")
        print()
    for t in (1, 2, 3, 4, 5):
        if t not in want:
            continue
        rows = tiers[t]
        print(f"== {TIER_NAMES[t]}: {len(rows)} stocks ==")
        if not rows:
            print("   (none)\n")
            continue
        print(f"   {'#':>3} {'stock':<12} {'structure':<16} {'price':>9} {'IVP':>4} {'flip':<11} {'age':<8} {'expiry':<11} {'lot':>5}  alert")
        for i, r in enumerate(rows, 1):
            age = "today" if r["flip_trading_days"] == 0 else f"{r['flip_trading_days']}td/{r['flip_calendar_days']}d"
            print(f"   {i:>3} {r['symbol']:<12} {r['structure']:<16} {r['spot']:>9g} {(r['ivp'] if r.get('ivp') is not None else '-'):>4} {r['flip_date']:<11} {age:<8} {r['expiry'] or '-':<11} {r['lot'] or '-':>5}  {r['alert']}")
        print()


if __name__ == "__main__":
    main()
