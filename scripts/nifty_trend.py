"""Nifty 50 direction from the Supertrend(10,3) (user, 2026-11-28: 'in the dashboard I need nifty direction based on supertrend').

  python scripts/nifty_trend.py            writes dhan-live/data/nifty_trend.json and zerodha-live/data/nifty_trend.json (one separate copy per broker, like ivp.json)

Daily candles of ^NSEI from Yahoo, Supertrend(10,3) on completed sessions only (today's bar is dropped until 15:45 IST), the same indicator the stock signals use.
Information only: no rule, signal or order reads it. The dashboard's 'Nifty direction' strip draws it.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "swing-backtest"))
from indicators import compute_supertrend  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
OUT = ["dhan-live/data/nifty_trend.json", "zerodha-live/data/nifty_trend.json"]


def main():
    url = "https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEI?range=2y&interval=1d"
    d = json.loads(urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read())["chart"]["result"][0]
    q = d["indicators"]["quote"][0]
    rows = [(datetime.fromtimestamp(t, IST), o, h, l, c) for t, o, h, l, c in zip(d["timestamp"], q["open"], q["high"], q["low"], q["close"]) if None not in (o, h, l, c)]
    now = datetime.now(IST)
    if rows and rows[-1][0].date() == now.date() and (now.hour, now.minute) < (15, 45):
        rows = rows[:-1]                                   # today's bar is still forming
    dates = [r[0].strftime("%Y-%m-%d") for r in rows]
    h, l, c = [r[2] for r in rows], [r[3] for r in rows], [r[4] for r in rows]
    dirs, up, lo = compute_supertrend(h, l, c, 10, 3.0)
    green = dirs[-1] == "up"
    line = lo[-1] if green else up[-1]
    k = len(dirs) - 1
    while k > 0 and dirs[k - 1] == dirs[-1]:
        k -= 1
    sma50, sma200 = sum(c[-50:]) / 50, sum(c[-200:]) / 200
    out = {
        "generated_at": now.isoformat(timespec="seconds"), "as_of": dates[-1], "source": "Yahoo ^NSEI daily candles, Supertrend(10,3), completed sessions only",
        "close": round(c[-1], 2), "prev_close": round(c[-2], 2), "chg_pct": round((c[-1] / c[-2] - 1) * 100, 2),
        "st": "GREEN" if green else "RED", "since": dates[k], "age_td": len(dirs) - 1 - k,
        "line": round(line, 2), "to_flip_pct": round(abs(c[-1] / line - 1) * 100, 2),
        "vs_sma50_pct": round((c[-1] / sma50 - 1) * 100, 2), "vs_sma200_pct": round((c[-1] / sma200 - 1) * 100, 2),
        "ret_20d_pct": round((c[-1] / c[-21] - 1) * 100, 2),
        "recent": [{"date": dates[i], "close": round(c[i], 2), "st": "GREEN" if dirs[i] == "up" else "RED"} for i in range(len(c) - 30, len(c))],
        "flips": [{"date": dates[i], "to": "GREEN" if dirs[i] == "up" else "RED", "close": round(c[i], 2)} for i in range(1, len(dirs)) if dirs[i] != dirs[i - 1]][-6:],
    }
    for p in OUT:
        (ROOT / p).write_text(json.dumps(out, indent=1))
    print(f"Nifty 50 {out['as_of']}: close {out['close']} ({out['chg_pct']:+.2f}%), Supertrend {out['st']} since {out['since']} ({out['age_td']} sessions), "
          f"line {out['line']} ({out['to_flip_pct']}% away), vs 200-day {out['vs_sma200_pct']:+.1f}%")


if __name__ == "__main__":
    main()
