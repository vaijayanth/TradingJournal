"""ICICI (DI) data engine: the dividend portfolio's universe view and its ENTRY signals. Reads/writes only icici-live/ (nothing from ND or AZ).

Strategy (user, 2026-11-16): a dividend-focused portfolio. Whenever a stock in the DI universe hits a 52-week low, add a Rs20,000 position,
at most once a week per stock: averaging in at the bottom improves the dividend yield. No live trading of the stocks beyond that signal.

What it builds (icici_live_signals.json), per universe stock, from Yahoo daily bars (UNADJUSTED, the TradingView convention):
  price, 52-week (252-session) closing low / closing high / intraday low, % above the low,
  ENTRY signal = today's close is the lowest close of the last 252 sessions (a NEW 52-week closing low), unless a buy was recorded in the last
  7 days (data/di_trades.json last_buy); qty_to_buy = Rs20,000 / price floored to whole shares (minimum 1),
  dividends: trailing-12-month dividend per share, yield = TTM / price, last ex-date and amount, next ex-date (the same date a year later, an ESTIMATE),
  Supertrend(10,3) colour and flip date, RSI(14), whether the stock has listed options.
A stock whose latest bar is older than the newest bar in the batch is flagged stale and never raises a signal.

Usage: python icici-live/scripts/build_icici_data.py
"""
import json
import math
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
IST = timezone(timedelta(hours=5, minutes=30))


def load(p, default=None):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def supertrend(h, l, c, period=10, mult=3.0):
    """Supertrend with Wilder ATR. Returns (direction list: +1 green / -1 red, per bar; None before the ATR exists)."""
    n = len(c)
    tr = [None] * n
    for i in range(n):
        tr[i] = (h[i] - l[i]) if i == 0 else max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    atr = [None] * n
    if n < period:
        return [None] * n
    atr[period - 1] = sum(tr[:period]) / period
    for i in range(period, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    fu, fl, dr = [None] * n, [None] * n, [None] * n
    for i in range(period - 1, n):
        hl2 = (h[i] + l[i]) / 2
        bu, bl = hl2 + mult * atr[i], hl2 - mult * atr[i]
        if i == period - 1:
            fu[i], fl[i], dr[i] = bu, bl, 1 if c[i] >= hl2 else -1
            continue
        fu[i] = bu if (bu < fu[i - 1] or c[i - 1] > fu[i - 1]) else fu[i - 1]
        fl[i] = bl if (bl > fl[i - 1] or c[i - 1] < fl[i - 1]) else fl[i - 1]
        if dr[i - 1] == -1 and c[i] > fu[i - 1]:
            dr[i] = 1
        elif dr[i - 1] == 1 and c[i] < fl[i - 1]:
            dr[i] = -1
        else:
            dr[i] = dr[i - 1]
    return dr


def rsi(c, period=14):
    if len(c) <= period:
        return None
    gains = [max(c[i] - c[i - 1], 0) for i in range(1, len(c))]
    losses = [max(c[i - 1] - c[i], 0) for i in range(1, len(c))]
    ag, al = sum(gains[:period]) / period, sum(losses[:period]) / period
    for i in range(period, len(gains)):
        ag, al = (ag * (period - 1) + gains[i]) / period, (al * (period - 1) + losses[i]) / period
    return 100.0 if al == 0 else round(100 - 100 / (1 + ag / al), 1)


def trading_days_between(d0, d1):
    n, d = 0, d0
    while d < d1:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


def next_exdiv_estimate(divs, today):
    """Dividends already paid in the last ~15 months, moved one year ahead: the first one still in the future is the estimate."""
    cands = []
    for d, _ in divs:
        for k in (1, 2):
            try:
                x = d.replace(year=d.year + k)
            except ValueError:
                x = d + timedelta(days=365 * k)
            if x > today:
                cands.append(x)
    return min(cands) if cands else None


def main():
    import yfinance as yf

    cfg = load(DATA / "di_config.json")
    uni = load(DATA / "icici_universe.json")["symbols"]
    trades = load(DATA / "di_trades.json", {"last_buy": {}}) or {"last_buy": {}}
    opts = load(DATA / "nfo_options.json", {"symbols": {}}).get("symbols", {})
    now = datetime.now(IST)
    today = now.date()
    window, tier, cool = cfg["window_sessions"], cfg["position_rs"], cfg["cooldown_days"]

    over = cfg.get("yahoo_overrides", {})   # a symbol Yahoo only has on another exchange (NSDL: BSE)
    rows, failed = [], []
    for s in uni:
        t = over.get(s, s + ".NS")
        try:
            d = yf.Ticker(t).history(period="2y", interval="1d", auto_adjust=False).dropna(subset=["Close"])
        except Exception:
            d = None
        if d is not None and 0 < len(d) < 30:
            # too little history to judge a 52-week low (NIFTYIETF has only a few days on Yahoo): show the price, never raise a signal
            lb0 = trades.get("last_buy", {}).get(s)
            rows.append({"symbol": s, "yahoo_symbol": t, "last_bar": str(d.index[-1].date()), "price": round(float(d["Close"].iloc[-1]), 2), "short_history_days": len(d),
                         "has_options": s in opts, "lot": None, "colour": None, "rsi": None, "new_low_today": False, "touched_low_today": False,
                         "div_ttm": 0, "div_yield_pct": None, "last_buy": lb0, "qty_to_buy": max(1, math.floor(tier / float(d["Close"].iloc[-1])))})
            continue
        if d is None or len(d) < 30:
            failed.append(s)
            continue
        idx = [x.date() for x in d.index]
        o, h, l, c = (d[k].astype(float).tolist() for k in ("Open", "High", "Low", "Close"))
        last = c[-1]
        win_c, win_l, win_h = c[-window:], l[-window:], h[-window:]
        low_c, high_c, low_i = min(win_c), max(win_c), min(win_l)
        prev_low = min(c[-window:-1]) if len(c) > window else min(c[:-1])
        new_low_today = last <= prev_low
        touched_low = l[-1] <= min(l[-window:-1] if len(l) > window else l[:-1])
        # Supertrend
        dr = supertrend(h, l, c)
        colour = "green" if dr[-1] == 1 else "red" if dr[-1] == -1 else None
        flip_i = None
        if dr[-1] is not None:
            i = len(dr) - 1
            while i > 0 and dr[i - 1] == dr[-1]:
                i -= 1
            flip_i = i
        flip_date = idx[flip_i] if flip_i is not None else None
        # dividends
        try:
            dv = yf.Ticker(t).dividends
            divs = [(x.date(), float(v)) for x, v in dv.items()]
        except Exception:
            divs = []
        ttm = sum(v for d_, v in divs if d_ > today - timedelta(days=365))
        last_div = max(divs, key=lambda x: x[0]) if divs else None
        nxt = next_exdiv_estimate([x for x in divs if x[0] > today - timedelta(days=460)], today)
        lb = trades.get("last_buy", {}).get(s)
        since = (today - date.fromisoformat(lb)).days if lb else None
        rows.append({
            "symbol": s, "yahoo_symbol": t, "last_bar": str(idx[-1]), "price": round(last, 2), "change_pct": round((last / c[-2] - 1) * 100, 2) if len(c) > 1 else None,
            "low_52w_close": round(low_c, 2), "high_52w_close": round(high_c, 2), "low_52w_intraday": round(low_i, 2),
            "pct_above_low": round((last / low_c - 1) * 100, 2), "pct_below_high": round((last / high_c - 1) * 100, 2),
            "new_low_today": bool(new_low_today), "touched_low_today": bool(touched_low),
            "div_ttm": round(ttm, 2), "div_yield_pct": round(ttm / last * 100, 2) if last else None,
            "last_exdiv": str(last_div[0]) if last_div else None, "last_div_amount": round(last_div[1], 2) if last_div else None,
            "next_exdiv_est": str(nxt) if nxt else None, "div_count_12m": sum(1 for d_, _ in divs if d_ > today - timedelta(days=365)),
            "colour": colour, "flip_date": str(flip_date) if flip_date else None,
            "flip_trading_days": trading_days_between(flip_date, idx[-1]) if flip_date else None, "rsi": rsi(c),
            "has_options": s in opts, "lot": (min(opts[s]["lot"].items())[1] if s in opts and opts[s].get("lot") else None),
            "last_buy": lb, "days_since_buy": since, "qty_to_buy": max(1, math.floor(tier / last)),
        })
    newest = max(r["last_bar"] for r in rows) if rows else None
    for r in rows:
        r["stale"] = r["last_bar"] != newest
        if r.get("short_history_days"):
            r["signal"] = ""
            continue
        cooldown_ok = r["days_since_buy"] is None or r["days_since_buy"] >= cool
        r["signal"] = "ENTRY" if (r["new_low_today"] and not r["stale"] and cooldown_ok) else ("COOLDOWN" if (r["new_low_today"] and not r["stale"]) else "")
        r["cost_at_signal"] = round(r["qty_to_buy"] * r["price"], 2)
    entries = [r["symbol"] for r in rows if r["signal"] == "ENTRY"]
    out = {
        "generated_at": now.isoformat(timespec="seconds"), "market_data_date": newest, "source": "Yahoo Finance daily bars (unadjusted) and dividend history",
        "rules": {"position_rs": tier, "cooldown_days": cool, "window_sessions": window, "signal": "today's close is the lowest close of the last 252 sessions"},
        "universe_count": len(uni), "failed": failed, "entries": entries,
        "summary": {"stocks": len(rows), "entry_signals": len(entries), "touched_low_today": sum(1 for r in rows if r["touched_low_today"]),
                    "with_options": sum(1 for r in rows if r["has_options"]), "stale": [r["symbol"] for r in rows if r["stale"]], "short_history": [r["symbol"] for r in rows if r.get("short_history_days")],
                    "avg_yield_pct": round(sum(r["div_yield_pct"] or 0 for r in rows if not r.get("short_history_days")) / max(1, sum(1 for r in rows if not r.get("short_history_days"))), 2)},
        "stocks": rows,
    }
    (ROOT / "icici_live_signals.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"DI data: {len(rows)} of {len(uni)} stocks, market data {newest}; entry signals today: {entries or 'none'}; failed: {failed or 'none'}; stale: {out['summary']['stale'] or 'none'}")


if __name__ == "__main__":
    main()
