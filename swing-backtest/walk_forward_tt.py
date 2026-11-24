"""Walk-forward check of the Minervini Trend Template overlay on the live ND strategy (user request 2026-11-24).

  python swing-backtest/walk_forward_tt.py --data /tmp/claude-0/bt/checkpoints

The overlay only blocks NEW entries (see bonde_minervini_test.py); exits and add-ons are the live ND rules. Variants differ only in the RS cut-off:
base (no overlay), TT with RS >= 70 (the published threshold, the version tested earlier), RS >= 80, RS >= 50, and TT without any RS condition.
Periods: FIRST = 2016-11-07 to 2021-12-31 (selection period), SECOND = 2022-01-01 to the last bar (untouched test period).
Two views of the second period: (a) the same continuous run sliced at 2022-01-01 (ladder and open positions carried over), (b) a fresh run restarted on
2022-01-01 with Rs20L and the ladder reset (the cleanest out-of-sample start, 252-day history is loaded from before the start).
Metrics for a slice: CAGR of the equity curve inside the slice, max drawdown inside the slice, year-by-year returns. Costs / slippage / 6% idle cash as RESULTS.md.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import swing_backtest as sw  # noqa: E402
from bonde_minervini_test import features, live_symbols  # noqa: E402


def tt_flag(f, rs_min, low_mult=1.25):
    tt = (f["close"] > f["sma50"]) & (f["sma50"] > f["sma150"]) & (f["sma150"] > f["sma200"]) & f["sma200_up"] & (f["close"] >= 0.75 * f["high52"]) & (f["close"] >= low_mult * f["low52"])
    if rs_min is not None:
        tt = tt & (f["rs"] >= rs_min)
    return tt


def filtered(raw, feats, rs_min):
    out = {}
    for sym, bars in raw.items():
        f = feats.get(sym)
        ok = tt_flag(f, rs_min).fillna(False) if f is not None else None
        out[sym] = {dt: (t if (ok is not None and dt in ok.index and ok.at[dt]) else (t[0], t[1], None, t[3], t[4])) for dt, t in bars.items()}
    return out


def run(data_dir, symbols, start, raw):
    orig = sw.load
    sw.load = lambda *a, **k: raw
    try:
        return sw.run("dhan", data_dir, symbols, start, 0.001, cash_rate=0.06)
    finally:
        sw.load = orig


def slice_stats(cv, a, b=None):
    s = cv.loc[a:b] if b else cv.loc[a:]
    yrs = (s.index[-1] - s.index[0]).days / 365.25
    cagr = ((s.iloc[-1] / s.iloc[0]) ** (1 / yrs) - 1) * 100
    dd = ((s / s.cummax()) - 1).min() * 100
    return round(cagr, 2), round(dd, 2), round(cagr / abs(dd), 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default=str(HERE / "results" / "walk_forward_tt"))
    a = ap.parse_args()
    data_dir = Path(a.data)
    symbols = live_symbols(data_dir)
    feats = features(data_dir, symbols)
    t0, t1 = pd.Timestamp("2016-11-07"), pd.Timestamp("2022-01-01")
    raw0 = sw.load(data_dir, symbols, t0, True)
    variants = [("base (live ND)", None, False), ("TT RS>=70", 70, True), ("TT RS>=80", 80, True), ("TT RS>=50", 50, True), ("TT no RS", None, True)]
    rows, yearly = [], {}
    for label, rs, on in variants:
        data = filtered(raw0, feats, rs) if on else raw0
        res = run(data_dir, symbols, t0, data)
        cv = pd.DataFrame(res["curve"], columns=["date", "eq", "inv", "n"]).set_index("date")["eq"]
        tr = pd.DataFrame(res["closed"])
        h1 = slice_stats(cv, "2016-11-07", "2021-12-31")
        h2 = slice_stats(cv, "2022-01-01")
        # fresh restart on 2022-01-01
        raw1 = sw.load(data_dir, symbols, t1, True)
        data1 = filtered(raw1, feats, rs) if on else raw1
        res1 = run(data_dir, symbols, t1, data1)
        cv1 = pd.DataFrame(res1["curve"], columns=["date", "eq", "inv", "n"]).set_index("date")["eq"]
        h2r = slice_stats(cv1, cv1.index[0].strftime("%Y-%m-%d"))
        tr1 = pd.DataFrame(res1["closed"])
        pf1 = tr1[tr1["pl"] > 0]["pl"].sum() / abs(tr1[tr1["pl"] <= 0]["pl"].sum())
        yr = cv.resample("YE").last()
        yr = pd.concat([pd.Series([cv.iloc[0]], index=[cv.index[0] - pd.Timedelta(days=1)]), yr]).pct_change().dropna() * 100
        yearly[label] = {str(k.year): round(v, 1) for k, v in yr.items()}
        rows.append({"variant": label, "FIRST cagr": h1[0], "FIRST dd": h1[1], "FIRST r/dd": h1[2], "SECOND(cont) cagr": h2[0], "SECOND(cont) dd": h2[1], "SECOND(cont) r/dd": h2[2],
                     "SECOND(restart) cagr": h2r[0], "SECOND(restart) dd": h2r[1], "SECOND(restart) r/dd": h2r[2], "SECOND(restart) PF": round(pf1, 2), "SECOND(restart) closed": len(tr1)})
        print(rows[-1], flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(a.out + ".csv", index=False)
    yd = pd.DataFrame(yearly).T
    yd.to_csv(a.out + "_yearly.csv")
    print("\n" + df.T.to_string(), flush=True)
    print("\nYEARLY RETURNS % (continuous run)\n" + yd.to_string(), flush=True)


if __name__ == "__main__":
    main()
