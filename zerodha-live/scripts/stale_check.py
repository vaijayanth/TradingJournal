"""Is /refresh-zerodha overdue? Prints nothing when everything is fresh.
(2026-11-09: also overdue when the market is open and the last refresh is more than 60 minutes old.)

Run by the project's SessionStart hook so Claude Code can tell the user at the start of a session. The same rules as the
dashboard banner in index.html (dhStaleAlerts):
  - signals older than the last session whose close should be published (backtester posts ~16:00 IST; allowed until 16:30)
  - holdings snapshot older than that session
  - AMO orders in data/orders_snapshot.json that should have executed at a session open since they were placed, with no
    refresh on or after that day (Zerodha's tradebook is today-only, so a missed day loses the fills)
Trading days are Mon-Fri; exchange holidays are not known here.

Usage: python dhan-live/scripts/stale_check.py          (set ZERODHA_NOW=2026-11-10T10:00 to simulate an IST time)
"""
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IST = timezone(timedelta(hours=5, minutes=30))


def now_ist():
    q = os.environ.get("ZERODHA_NOW")
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


def last_refresh():
    """Latest of: holdings pull, signals computed, live prices pulled (all done by /refresh-zerodha)."""
    ts = []
    for path, key in (("data/holdings_snapshot.json", "fetched_at"), ("zerodha_live_signals.json", "generated_at"), ("data/cc_live_prices.json", "fetched_at")):
        d = load(path)
        try:
            t = datetime.fromisoformat(d[key])
            ts.append(t if t.tzinfo else t.replace(tzinfo=IST))
        except Exception:
            pass
    return max(ts).astimezone(IST) if ts else None


def alerts(now):
    out = []
    today = now.date()
    mins = now.hour * 60 + now.minute
    expected = today if (today.weekday() < 5 and mins >= 16 * 60 + 30) else prev_weekday(today)
    last = last_refresh()
    if last and today.weekday() < 5 and 9 * 60 + 15 <= mins <= 15 * 60 + 30 and now - last > timedelta(minutes=60):
        m = int((now - last).total_seconds() // 60)
        out.append(f"the market is open and the last refresh was {m // 60}h {m % 60}m ago ({last.strftime('%H:%M')} IST): prices, positions and the strike alerts are out of date - run /refresh-zerodha")
    sig = load("zerodha_live_signals.json")
    hold = load("data/holdings_snapshot.json")
    if sig and sig.get("market_data_date") and date.fromisoformat(sig["market_data_date"]) < expected:
        out.append(f"signals are from {sig['market_data_date']} but the market has closed since ({expected})")
    if hold and hold.get("fetched_at") and date.fromisoformat(hold["fetched_at"][:10]) < expected:
        out.append(f"holdings were last pulled {hold['fetched_at'][:10]} (quantities and P&L may be wrong)")
    return out


def main():
    a = alerts(now_ist())
    if not a:
        return
    print("ZERODHA (AZ) DATA IS STALE - tell the user this in your first reply, before anything else, and offer to run /refresh-zerodha now:")
    for x in a:
        print(f"  - {x}")


if __name__ == "__main__":
    main()
