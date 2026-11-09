"""Summarise backtest runs: per-variant results scaled to a risk budget (default Rs50k max loss per position, Rs50 lakh capital)."""
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
CAP, RISK = 5_000_000, 50_000


def scaled(tr):
    tr = tr.copy()
    tr["scaled"] = tr["pnl"] / tr["margin"] * RISK
    tr["mon"] = tr["exit"].dt.to_period("M")
    m = tr.groupby("mon")["scaled"].sum()
    allm = pd.period_range(tr["entry"].min().to_period("M"), tr["exit"].max().to_period("M"), freq="M")
    m = m.reindex(allm, fill_value=0)
    eq = m.cumsum()
    return m, (eq - eq.cummax()).min()


def row(label, tr):
    m, dd = scaled(tr)
    return {"variant": label, "n": len(tr), "win%": round((tr["pnl"] > 0).mean() * 100, 1), "exp_Rs/trade": round(tr["pnl"].mean()),
            "pnl/margin%": round(tr["pnl"].sum() / tr["margin"].sum() * 100, 1), "avg_mo_%cap": round(m.mean() / CAP * 100, 2),
            "worst_mo_%": round(m.min() / CAP * 100, 2), "maxDD_%": round(dd / CAP * 100, 2), "+months": f"{int((m > 0).sum())}/{len(m)}"}


def main():
    files = sorted(HERE.glob("data/trades_slip*.pkl"))
    for f in files:
        T = pd.read_pickle(f)
        rows = [row(f"d{k[0]} {k[1]} ivp>={k[2]}", tr) for k, tr in T.items() if len(tr)]
        df = pd.DataFrame(rows)
        print("\n==", f.name)
        print(df.to_string(index=False))


if __name__ == "__main__":
    main()
