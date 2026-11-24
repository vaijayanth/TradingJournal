"""Gold-futures hedge overlay on the stored ND / AZ backtest equity curves (user request, 2026-11-24).

  python swing-backtest/gold_hedge_overlay.py

Idea: while the market is in a downtrend, hold a long INR-gold position sized as a % of the book's equity; the book's own curve is unchanged,
the hedge P&L is added day by day. The regime is read at a completed day's close and applies to the NEXT day's return (no look-ahead).
  trigger A  Nifty Supertrend(10,3) red
  trigger B  Nifty Supertrend red AND Nifty close below its 200-day average (a deeper downtrend)
  size       10 / 25 / 50 % of the book's equity (re-set every day, so the hedge scales with the book)
Gold = COMEX gold futures (GC=F, back-adjusted continuous) x USD/INR from Yahoo: a proxy for MCX gold, not the MCX contract itself. Cost = 0.05% of the
hedge notional every time it is switched on or off. Not modelled: futures margin (capital tied up), contract rolls, MCX lot size, tax.
Inputs: results/az_10y_cash0.06_equity.csv and results/dhan_10y_cash0.06_equity.csv (6% on idle cash, as in RESULTS.md).
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


def regimes():
    n = get("^NSEI")
    d, _, _ = compute_supertrend(n["High"].tolist(), n["Low"].tolist(), n["Close"].tolist())
    red = pd.Series(d, index=n.index).eq("down")
    below200 = n["Close"] < n["Close"].rolling(200).mean()
    return {"A": red, "B": red & below200}, n


def gold_inr():
    g, fx = get("GC=F"), get("INR=X")
    j = g[["Close"]].join(fx[["Close"]].rename(columns={"Close": "fx"}), how="inner")
    return (j["Close"] * j["fx"]).pct_change()


def metrics(eq):
    eq = eq.dropna()
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1
    dd = (eq / eq.cummax() - 1)
    return cagr * 100, dd.min() * 100, (cagr * 100) / abs(dd.min() * 100), dd


def overlay(eq, reg, gret, size):
    r = eq.pct_change().fillna(0)
    on = reg.reindex(eq.index).shift(1).fillna(False).astype(float)   # decided at yesterday's close
    g = gret.reindex(eq.index).fillna(0)
    switch = on.diff().abs().fillna(0)
    ret = r + size * on * g - COST * size * switch
    return (1 + ret).cumprod() * eq.iloc[0], on


def main():
    regs, nifty = regimes()
    g = gold_inr()
    out = []
    for book, f in (("ND", "dhan_10y_cash0.06_equity.csv"), ("AZ", "az_10y_cash0.06_equity.csv")):
        eq = pd.read_csv(HERE / "results" / f, index_col=0, parse_dates=True)["eq"]
        c0, d0, m0, dd0 = metrics(eq)
        print(f"\n{book}: {eq.index[0].date()} .. {eq.index[-1].date()}   base: CAGR {c0:5.1f}%  maxDD {d0:6.1f}%  CAGR/DD {m0:4.2f}")
        for tname in ("A", "B"):
            for size in (0.10, 0.25, 0.50):
                h, on = overlay(eq, regs[tname], g, size)
                c, d, m, dd = metrics(h)
                out.append({"book": book, "trigger": tname, "size_pct": int(size * 100), "cagr": round(c, 2), "maxdd": round(d, 2), "cagr_dd": round(m, 2), "base_cagr": round(c0, 2), "base_maxdd": round(d0, 2), "days_on_pct": round(on.mean() * 100, 1)})
                print(f"  trigger {tname} size {int(size*100):2d}%  on {on.mean():4.0%} of days  CAGR {c:5.1f}% ({c-c0:+4.1f})  maxDD {d:6.1f}% ({d-d0:+5.1f})  CAGR/DD {m:4.2f}")
        # worst equity drawdown episodes of the base book and what the hedge did there
        h, on = overlay(eq, regs["A"], g, 0.25)
        peak = eq.cummax(); trough = (eq / peak - 1).idxmin(); start = eq.loc[:trough].idxmax()
        print(f"  worst base drawdown {start.date()} -> {trough.date()}: base {eq.loc[trough]/eq.loc[start]-1:6.1%}, with A/25% {h.loc[trough]/h.loc[start]-1:6.1%}")
        for a, b in (("2018-09-01", "2018-11-30"), ("2020-02-15", "2020-04-30"), ("2022-04-15", "2022-07-15")):
            e = eq.loc[a:b]; hh = h.loc[a:b]
            if len(e) > 5:
                print(f"    {a}..{b}: base {e.iloc[-1]/e.iloc[0]-1:6.1%}  hedged(A,25%) {hh.iloc[-1]/hh.iloc[0]-1:6.1%}")
    pd.DataFrame(out).to_csv(HERE / "results" / "gold_hedge_overlay.csv", index=False)


if __name__ == "__main__":
    main()
