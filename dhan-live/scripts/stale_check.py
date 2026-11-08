"""Is /refresh-dhan overdue? Prints nothing when everything is fresh.

Run by the project's SessionStart hook so Claude Code can tell the user at the start of a session. The same rules as the
dashboard banner in index.html (dhStaleAlerts):
  - signals older than the last session whose close should be published (backtester posts ~16:00 IST; allowed until 16:30)
  - holdings snapshot older than that session
  - AMO orders in data/orders_snapshot.json that should have executed at a session open since they were placed, with no
    refresh on or after that day (Dhan's tradebook is today-only, so a missed day loses the fills)
Trading days are Mon-Fri; exchange holidays are not known here.

Usage: python dhan-live/scripts/stale_check.py          (set DHAN_NOW=2026-11-10T10:00 to simulate an IST time)
"""
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IST = timezone(timedelta(hours=5, minutes=30))


def now_ist():
    q = os.environ.get("DHAN_NOW")
    return datetime.strptime(q, "%Y-%m-%dT%H:%M").replace(tzinfo=IST) if q else datetime.now(IST)


def prev_weekday(d):
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def next_weekday(d):
    d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def load(p):
    try:
        return json.loads((ROOT / p).read_text())
    except Exception:
        return None


def alerts(now):
    out = []
    today = now.date()
    mins = now.hour * 60 + now.minute
    expected = today if (today.weekday() < 5 and mins >= 16 * 60 + 30) else prev_weekday(today)
    sig = load("dhan_live_signals.json")
    hold = load("data/holdings_snapshot.json")
    orders = load("data/orders_snapshot.json")
    if sig and sig.get("market_data_date") and date.fromisoformat(sig["market_data_date"]) < expected:
        out.append(f"signals are from {sig['market_data_date']} but the market has closed since ({expected})")
    if hold and hold.get("fetched_at") and date.fromisoformat(hold["fetched_at"][:10]) < expected:
        out.append(f"holdings were last pulled {hold['fetched_at'][:10]} (quantities and P&L may be wrong)")
    if orders:
        snap = (orders.get("fetched_at") or "")[:10]
        by_day = {}
        for o in orders.get("orders", []):
            if o.get("status") == "PENDING" and o.get("amo") is not False and o.get("placed"):
                by_day.setdefault(o["placed"], []).append(o)
        for placed in sorted(by_day):
            n = next_weekday(date.fromisoformat(placed))
            opened = today > n or (today == n and mins >= 9 * 60 + 30)
            if not opened or snap >= n.isoformat():
                continue
            k = len(by_day[placed])
            if today == n:
                out.append(f"{k} after-market orders placed {placed} have probably executed at today's open; the Dhan tradebook is today-only, so /refresh-dhan must run TODAY or the fills are not recorded")
            else:
                out.append(f"{k} orders placed {placed} filled at the {n} open and were NOT recorded (the tradebook only covers the current day); rebuild dh252 fills from a Global Transaction Report and ask the user for investment-share buy/sell dates and prices")
    return out


def main():
    a = alerts(now_ist())
    if not a:
        return
    print("DHAN DATA IS STALE - tell the user this in your first reply, before anything else, and offer to run /refresh-dhan now:")
    for x in a:
        print(f"  - {x}")


if __name__ == "__main__":
    main()
