"""Cross-check every dh252 signal against an independent calculation on complete Yahoo price history.

Why: the backtester's stored OHLC once had an 11-trading-day hole (21 Oct - 4 Nov 2026), which silently changed
Supertrend colours (3 of 28 signal stocks disagreed with a recompute on complete data, incl. an EXIT). Signals
are only as good as that history, so before any order every signal stock is recomputed here and compared.

Rules checked (same as dh252, entry on the CLOSING high as decided by the user):
  entry : Supertrend(10, 3) GREEN  AND  last close >= highest close of the last 252 sessions
  add-on: Supertrend GREEN         (the P&L / cooldown part of the rule uses holdings, not prices)
  exit  : Supertrend RED
Calculation: Wilder ATR(10) (SMA-seeded) and the standard band-ratchet Supertrend - identical to TradingView's
default and to backtester/scripts/indicators.py - on 5 years of UNADJUSTED daily bars from Yahoo (TradingView's
default also does not adjust for dividends). The intraday 52-week high is reported for reference only.

Output: data/signal_crosscheck.json (read by build_order_ticket.py, which blocks flagged signals).
Usage:  python dhan-live/scripts/crosscheck_signals.py [--signals PATH] [--out PATH] [--mode dh252|flip]
  --mode flip (Zerodha, Nifty F&O): an entry needs Supertrend GREEN and a red->green flip within the last 6 trading bars
  (recomputed from Yahoo); the 252-session closing-high test is not applied. Add-ons and exits are checked as above.
"""
import argparse
import json
import warnings
from datetime import datetime, timezone
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
PERIOD, MULT, WINDOW = 10, 3.0, 252


def supertrend(h, l, c, period=PERIOD, mult=MULT):
    n = len(c)
    tr = [h[0] - l[0]] + [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, n)]
    atr = [None] * n
    atr[period - 1] = sum(tr[:period]) / period
    for i in range(period, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    fu, fl, d = [None] * n, [None] * n, [None] * n
    s0 = period - 1
    m = (h[s0] + l[s0]) / 2
    fu[s0], fl[s0] = m + mult * atr[s0], m - mult * atr[s0]
    d[s0] = "down" if c[s0] <= fu[s0] else "up"
    for i in range(s0 + 1, n):
        m = (h[i] + l[i]) / 2
        bu, bl = m + mult * atr[i], m - mult * atr[i]
        fu[i] = bu if (bu < fu[i - 1] or c[i - 1] > fu[i - 1]) else fu[i - 1]
        fl[i] = bl if (bl > fl[i - 1] or c[i - 1] < fl[i - 1]) else fl[i - 1]
        d[i] = ("up" if c[i] > fu[i] else "down") if d[i - 1] == "down" else ("down" if c[i] < fl[i] else "up")
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--signals", default=str(ROOT / "dhan_live_signals.json"))
    ap.add_argument("--out", default=str(ROOT / "data" / "signal_crosscheck.json"))
    ap.add_argument("--mode", choices=["dh252", "flip"], default="dh252")
    args = ap.parse_args()

    import numpy as np
    import yfinance as yf

    sig = json.loads(Path(args.signals).read_text())
    md = sig.get("market_data_date")
    todo = ([("entry", r) for r in sig.get("entries", [])] + [("addon", r) for r in sig.get("addons", [])]
            + [("exit", r) for r in sig.get("exits", [])])
    syms = sorted({r["symbol"] for _, r in todo})
    df = yf.download([s + ".NS" for s in syms], period="5y", progress=False, auto_adjust=False, threads=True)

    results, last_bars, dropped = [], set(), set()
    # Dhan daily bars (data/dhan_bars_overlay.json, pulled over the Dhan MCP) fill sessions Yahoo has not published yet; they are only
    # ever APPENDED after Yahoo's last bar (never overwrite Yahoo) and never past the signals' market_data_date.
    overlay_path = ROOT / "data" / "dhan_bars_overlay.json"
    overlay = json.loads(overlay_path.read_text()).get("bars", {}) if overlay_path.exists() else {}
    for kind, r in todo:
        s = r["symbol"]
        res = {"symbol": s, "kind": kind, "ok": False, "reasons": []}
        try:
            x = df.xs(s + ".NS", axis=1, level=1).dropna(subset=["Close"])
        except Exception:
            x = None
        if x is not None and md:
            # a bar dated after the signals is not what they were built on (while the market is open it is also unfinished): leave it out
            later = [d for d in x.index if str(d.date()) > md]
            if later:
                dropped.update(str(d.date()) for d in later)
                x = x[[str(d.date()) <= md for d in x.index]]
        if x is not None and md and overlay.get(s):
            import pandas as pd
            # Dhan's own prices are final (user, 2026-11-13): a Dhan bar REPLACES Yahoo's bar for the same date, and fills later dates
            add = [o for o in overlay[s] if o["date"] <= md]
            if add:
                rows = pd.DataFrame([{"Open": o["open"], "High": o["high"], "Low": o["low"], "Close": o["close"], "Volume": o["volume"]} for o in add],
                                    index=pd.to_datetime([o["date"] for o in add]))
                x = x[["Open", "High", "Low", "Close", "Volume"]]
                x = pd.concat([x[~x.index.isin(rows.index)], rows]).sort_index()
                res["dhan_bars_added"] = [o["date"] for o in add]
        if x is None or len(x) < PERIOD + 2:
            res["reasons"].append("not enough Yahoo history to verify")
            results.append(res)
            continue
        if len(x) < WINDOW:
            res["note"] = f"recent listing: only {len(x)} sessions of history (closing high taken over those)"
        h, l, c = x["High"].tolist(), x["Low"].tolist(), x["Close"].tolist()
        dirs = supertrend(h, l, c)
        colour = "green" if dirs[-1] == "up" else "red"
        flip_bars = None                       # bars since the last red -> green flip (0 = flipped on the last bar)
        for k in range(len(dirs) - 1, 0, -1):
            if dirs[k] == "up" and dirs[k - 1] == "down":
                flip_bars = len(dirs) - 1 - k
                break
        win = x.tail(WINDOW)
        close = c[-1]
        hi_close, hi_intra = float(win["Close"].max()), float(win["High"].max())
        last_bar = str(x.index[-1].date())
        last_bars.add(last_bar)
        published = r.get("supertrend_color")
        pub_close = r.get("close") if kind == "entry" else r.get("cmp")
        res.update({
            "published_colour": published, "recomputed_colour": colour, "yahoo_last_bar": last_bar,
            "close": round(close, 2), "published_close": pub_close, "closing_high_252": round(hi_close, 2),
            "intraday_high_252": round(hi_intra, 2), "flip_bars_ago": flip_bars, "pct_from_intraday_high": round((close / hi_intra - 1) * 100, 2),
        })
        if md and np.busday_count(np.datetime64(last_bar) + 1, np.datetime64(md) + 1) > 0:   # a session between the last bar (Yahoo, plus any Dhan overlay) and the signal date is missing (a weekend signal date is fine)
            res["reasons"].append(f"last bar is {last_bar}" + (" (Yahoo + Dhan)" if res.get("dhan_bars_added") else " (Yahoo)") + f", signals are dated {md}")
        if pub_close and abs(close / pub_close - 1) > 0.005:
            res["reasons"].append(f"close {close:.2f} differs from the signal's {pub_close}")
        if kind in ("entry", "addon") and colour != "green":
            res["reasons"].append(f"Supertrend is {colour.upper()} on complete data (signal says {published})")
        if kind == "exit" and colour != "red":
            res["reasons"].append(f"Supertrend is {colour.upper()} on complete data (signal says {published}) - not an exit")
        if kind == "entry" and args.mode == "dh252" and round(close, 2) < round(hi_close, 2):
            res["reasons"].append(f"close {close:.2f} is below the 252-session closing high {hi_close:.2f}")
        if kind == "entry" and args.mode == "flip" and (flip_bars is None or flip_bars > 6):
            res["reasons"].append(f"no red-to-green Supertrend flip in the last 6 trading bars on complete data (last flip {flip_bars} bars ago)")
        res["ok"] = not res["reasons"]
        results.append(res)

    bad = [x for x in results if not x["ok"]]
    out = {"generated_at": datetime.now(timezone.utc).isoformat(), "market_data_date": md, "yahoo_last_bars": sorted(last_bars), "bars_after_signal_date_ignored": sorted(dropped),
           "checked": len(results), "flagged": len(bad), "results": results}
    Path(args.out).write_text(json.dumps(out, indent=1))
    print(f"cross-check of {len(results)} signals (market data {md}): {len(results) - len(bad)} agree, {len(bad)} flagged")
    for x in bad:
        print(f"  FLAG {x['kind']:5} {x['symbol']:12} " + "; ".join(x["reasons"]))


if __name__ == "__main__":
    main()
