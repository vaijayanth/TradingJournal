"""Upcoming results (earnings) and ex-dividend dates for the ND covered-call universe -> data/option_events.json.

Rule (user, 2026-11-09): every open option on a stock is closed 15 days before its next results date or ex-dividend date, and no new option is opened whose life
overlaps that window. compute_covered_call.py reads this file (rules.event_close_days).
Source: Yahoo (yfinance). Results: the calendar's earnings date, else the next future row of get_earnings_dates. Ex-dividend: the calendar's declared date when it is
still ahead, otherwise an ESTIMATE (the last 400 days' ex-dividend dates + 1 year, earliest that is still ahead), flagged estimated. Companies confirm results dates only
1-2 weeks ahead, so a future date can be an estimate too (`source`). A stock with no date at all is listed in `missing` and gets no event alert (say so; never guessed).
Usage: python dhan-live/scripts/fetch_option_events.py [--force]   (skipped when the file is under 2 days old unless --force)
"""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "option_events.json"
YAHOO_ALIAS = {}   # NSE symbol -> Yahoo symbol when they differ


def universe():
    return sorted(json.loads((DATA / "cc_config.json").read_text(encoding="utf-8"))["universe"])


def to_date(x):
    """Any Yahoo date-like value -> plain datetime.date (Timestamps are converted to IST first)."""
    if x is None:
        return None
    if hasattr(x, "tz_convert"):
        x = x.tz_convert("Asia/Kolkata")
    if hasattr(x, "to_pydatetime"):
        x = x.to_pydatetime()
    if isinstance(x, datetime):
        return x.date()
    return x if isinstance(x, date) else None


def one(sym, today):
    t = yf.Ticker(YAHOO_ALIAS.get(sym, sym) + ".NS")
    res = {"earnings": None, "earnings_source": None, "ex_div": None, "ex_div_estimated": None, "last_ex_div": None}
    try:
        cal = t.calendar or {}
    except Exception:
        cal = {}
    ed = [d for d in (to_date(x) for x in (cal.get("Earnings Date") or [])) if d and d >= today]
    if ed:
        res["earnings"], res["earnings_source"] = min(ed).isoformat(), "yahoo calendar"
    else:
        try:
            df = t.get_earnings_dates(limit=12)
            fut = sorted({to_date(i) for i in df.index} if df is not None and len(df) else [])
            fut = [d for d in fut if d and d >= today]
            if fut:
                res["earnings"], res["earnings_source"] = fut[0].isoformat(), "yahoo earnings dates"
        except Exception:
            pass
    xd = to_date(cal.get("Ex-Dividend Date"))
    try:
        divs = [to_date(i) for i in t.dividends.index]
    except Exception:
        divs = []
    divs = sorted(d for d in divs if d)
    past = [d for d in divs if d < today]
    if past:
        res["last_ex_div"] = past[-1].isoformat()
    if xd and xd >= today:
        res["ex_div"], res["ex_div_estimated"] = xd.isoformat(), False
    else:
        est = sorted(d + timedelta(days=365) for d in divs if today - timedelta(days=400) <= d < today + timedelta(days=0))
        est = [d for d in est if d >= today]
        if est:
            res["ex_div"], res["ex_div_estimated"] = est[0].isoformat(), True
    return sym, res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    if OUT.exists() and not args.force:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(json.loads(OUT.read_text(encoding="utf-8"))["generated_at"])
        if age < timedelta(days=2):
            print(f"option_events.json is {age.total_seconds() / 3600:.0f}h old - kept (use --force to refetch)")
            return
    today = datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
    syms = universe()
    with ThreadPoolExecutor(max_workers=8) as ex:
        got = dict(ex.map(lambda s: one(s, today), syms))
    missing = sorted(s for s, v in got.items() if not v["earnings"] and not v["ex_div"])
    OUT.write_text(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(), "as_of": today.isoformat(), "source": "yfinance (Yahoo)", "stocks": got,
                               "missing": missing}, indent=1), encoding="utf-8")
    print(f"option events for {len(got)} stocks; with results date {sum(1 for v in got.values() if v['earnings'])}, "
          f"with ex-dividend {sum(1 for v in got.values() if v['ex_div'])}; no date at all: {missing or 'none'}")


if __name__ == "__main__":
    sys.exit(main())
