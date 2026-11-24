"""Standalone positional gold backtest with the swing Supertrend (user request, 2026-11-24).

  python swing-backtest/gold_supertrend.py

Gold = COMEX gold futures (GC=F, Yahoo continuous) x USD/INR, a proxy for MCX gold. Signals are read at a completed day's CLOSE and fill at the NEXT bar's
OPEN (same convention as swing_backtest.py). One position, all-in (no leverage in the equity curve: 1x notional). Cost 0.05% of notional per side
(brokerage + slippage; futures have no STT-style delivery charges). Variants: long-only (flat in a downtrend) and long/short (short while red).
Robustness: Supertrend period x multiplier grid, split by decade, and buy-and-hold on the same dates.
Not modelled: margin (capital tied up earns the cash rate in reality), contract-roll gaps in the continuous series, MCX lot size, tax.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from indicators import compute_supertrend  # noqa: E402

COST = 0.0005


def get(t):
    d = yf.download(t, period="max", progress=False, auto_adjust=False)
    d.columns = [c[0] for c in d.columns]
    return d.dropna()


def gold_inr():
    g, fx = get("GC=F"), get("INR=X")
    j = g.join(fx[["Close"]].rename(columns={"Close": "fx"}), how="inner")
    for c in ("Open", "High", "Low", "Close"):
        j[c] = j[c] * j["fx"]
    return j[["Open", "High", "Low", "Close"]]


def backtest(df, period=10, mult=3.0, short=False):
    d, _, _ = compute_supertrend(df["High"].tolist(), df["Low"].tolist(), df["Close"].tolist(), period, mult)
    d = pd.Series(d, index=df.index)
    target = pd.Series(0.0, index=df.index)
    target[d == "up"] = 1.0
    if short:
        target[d == "down"] = -1.0
    pos = target.shift(1).fillna(0.0)            # decided at yesterday's close, held from today's open
    prev = pos.shift(1).fillna(0.0)
    o, c = df["Open"], df["Close"]
    pc = c.shift(1)
    held = pos == prev
    ret = np.where(held, pos * (c / pc - 1), prev * (o / pc - 1) + pos * (c / o - 1))
    ret = pd.Series(ret, index=df.index).fillna(0.0) - COST * (pos - prev).abs()
    eq = (1 + ret).cumprod()
    # trades: runs of constant non-zero position
    tr = []
    chg = (pos != prev)
    ent = None
    for t in df.index:
        if chg[t]:
            if ent is not None:
                tr.append((ent[0], t, ent[1], o[t] / ent[2] - 1))
                ent = None
            if pos[t] != 0:
                ent = (t, pos[t], o[t])
    if ent is not None:
        tr.append((ent[0], df.index[-1], ent[1], c.iloc[-1] / ent[2] - 1))
    return eq, ret, tr


def stats(eq, tr, label, base_eq=None):
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    dd = (eq / eq.cummax() - 1).min()
    t = [(s * r) if s != 0 else 0 for _, _, s, r in tr]
    t = pd.Series([s * r for _, _, s, r in tr]) if tr else pd.Series(dtype=float)
    wins, loss = t[t > 0], t[t <= 0]
    pf = wins.sum() / abs(loss.sum()) if len(loss) and loss.sum() != 0 else float("nan")
    inmkt = np.nan
    return {"label": label, "cagr": round(cagr * 100, 1), "maxdd": round(dd * 100, 1), "cagr_dd": round(cagr / abs(dd), 2), "trades": len(t),
            "win%": round(len(wins) / len(t) * 100, 0) if len(t) else 0, "avg_win%": round(wins.mean() * 100, 1) if len(wins) else 0,
            "avg_loss%": round(loss.mean() * 100, 1) if len(loss) else 0, "pf": round(pf, 2), "final_x": round(eq.iloc[-1], 1)}


def show(rows):
    print(pd.DataFrame(rows).to_string(index=False))


def main():
    df = gold_inr()
    print(f"INR gold (GC=F x USDINR): {df.index[0].date()} .. {df.index[-1].date()}  {len(df)} days")
    bh = (df["Close"] / df["Close"].iloc[0])
    bh_row = stats(bh, [(None, None, 1.0, df["Close"].iloc[-1] / df["Close"].iloc[0] - 1)], "Buy and hold")
    rows = [bh_row]
    for short in (False, True):
        eq, ret, tr = backtest(df, 10, 3.0, short)
        rows.append(stats(eq, tr, "Supertrend(10,3) " + ("long/short" if short else "long-only")))
    print("\n== Full period =="); show(rows)
    print("\n== By decade (Supertrend 10,3) ==")
    rows = []
    for a, b in (("2007-09-01", "2016-12-31"), ("2017-01-01", "2026-12-31")):
        sub = df.loc[a:b]
        rows.append(stats(sub["Close"] / sub["Close"].iloc[0], [(None, None, 1.0, sub["Close"].iloc[-1] / sub["Close"].iloc[0] - 1)], f"B&H {a[:4]}-{b[:4]}"))
        for short in (False, True):
            eq, ret, tr = backtest(sub, 10, 3.0, short)
            rows.append(stats(eq, tr, f"ST {a[:4]}-{b[:4]} " + ("L/S" if short else "long")))
    show(rows)
    print("\n== Parameter grid, long-only (CAGR % / maxDD % / CAGR-DD) ==")
    res = []
    for p in (7, 10, 14, 20):
        row = {"period": p}
        for m in (2.0, 3.0, 4.0):
            eq, ret, tr = backtest(df, p, m, False)
            s = stats(eq, tr, "")
            row[f"x{m:g}"] = f"{s['cagr']:.1f}/{s['maxdd']:.0f}/{s['cagr_dd']:.2f}"
        res.append(row)
    print(pd.DataFrame(res).to_string(index=False))
    eq, ret, tr = backtest(df, 10, 3.0, False)
    inm = (eq.pct_change().fillna(0) != 0).mean()
    print(f"\nLong-only (10,3): in the market {inm:.0%} of days; longest trade {max((t[1]-t[0]).days for t in tr)} days; median {int(np.median([(t[1]-t[0]).days for t in tr]))} days")
    pd.DataFrame(rows).to_csv(HERE / "results" / "gold_supertrend_decades.csv", index=False)


if __name__ == "__main__":
    main()
