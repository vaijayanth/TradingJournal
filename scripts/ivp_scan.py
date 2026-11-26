"""IV percentile (IVP) ranking of the Nifty F&O stocks (read-only, informational: it never changes a rule, signal or order).

  python options-backtest/fetch_bhavcopy.py --start 2025-10-25 --end <last trading day> --symbols-file zerodha-live/data/fno_universe.json --outdir fo_ivp
  python scripts/ivp_scan.py [--top 25] [--json out.json]

IV history is rebuilt from the NSE F&O bhavcopy settlement prices (no broker IV history exists): for every stock and day, the ATM implied vol is the mean of the call and put
at the 2 strikes nearest the underlying price, from the expiry 20-60 days away (nearest to 35 days), inverted with Black-Scholes (same functions as the options backtest).
IVP = share of the previous 252 sessions with a LOWER ATM IV than today (the V2 definition in OPTIONS_STRATEGY_V2.md). IV rank = (IV - 1y low) / (1y high - 1y low).
Settlement prices are end-of-day; a stock with fewer than 60 days of history is left out. Delta, results dates and the Supertrend colour are NOT considered here.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "options-backtest"))
from backtest import implied_vol  # noqa: E402

FO = ROOT / "options-backtest" / "data" / "fo_ivp"


def load():
    frames = []
    for f in sorted(FO.glob("*.csv.gz")):
        df = pd.read_csv(f, dtype=str)
        if df.empty:
            continue
        frames.append(pd.DataFrame({"sym": df["TckrSymb"], "date": pd.to_datetime(df["TradDt"]), "expiry": pd.to_datetime(df["XpryDt"]), "strike": df["StrkPric"].astype(float),
                                    "typ": df["OptnTp"], "settle": df["SttlmPric"].astype(float), "vol": df["TtlTradgVol"].astype(float), "und": df["UndrlygPric"].astype(float)}))
    return pd.concat(frames, ignore_index=True)


def atm_iv_series(g):
    out = {}
    for d, gd in g.groupby("date"):
        S = float(gd["und"].iloc[0])
        gd = gd.assign(dte=(gd["expiry"] - d).dt.days)
        exps = gd[(gd["dte"] >= 20) & (gd["dte"] <= 60)]["expiry"].unique()
        if len(exps) == 0:
            continue
        e = min(exps, key=lambda x: abs((x - d).days - 35))
        ge = gd[gd["expiry"] == e]
        T = (e - d).days / 365.0
        strikes = sorted(ge["strike"].unique(), key=lambda k: abs(k - S))[:2]
        ivs = []
        for k in strikes:
            for typ in ("CE", "PE"):
                r = ge[(ge["strike"] == k) & (ge["typ"] == typ) & (ge["vol"] > 0)]
                if r.empty:
                    continue
                v = implied_vol(typ, S, k, T, float(r["settle"].iloc[0]))
                if v:
                    ivs.append(v)
        if ivs:
            out[d] = float(np.mean(ivs))
    return pd.Series(out).sort_index()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--json")
    a = ap.parse_args()
    df = load()
    last = df["date"].max()
    rows = []
    for sym, g in df.groupby("sym"):
        s = atm_iv_series(g)
        if len(s) < 60 or s.index[-1] != last:
            continue
        today = s.iloc[-1]
        hist = s.iloc[-253:-1]
        lo, hi = hist.min(), hist.max()
        rows.append({"symbol": sym, "iv_pct": round(today * 100, 1), "ivp": round(float((hist < today).mean() * 100), 0), "iv_rank": round(float((today - lo) / (hi - lo) * 100), 0) if hi > lo else None,
                     "iv_low": round(lo * 100, 1), "iv_high": round(hi * 100, 1), "days": len(hist)})
    rows.sort(key=lambda r: (-r["ivp"], -(r["iv_rank"] or 0)))
    print(f"IV percentile, {last.date()} close, {len(rows)} F&O stocks (history {min(r['days'] for r in rows)}-{max(r['days'] for r in rows)} sessions)")
    print(f"{'stock':12s} {'IV%':>6s} {'IVP':>5s} {'IVrank':>7s} {'1y low-high':>12s}")
    for r in rows[:a.top]:
        print(f"{r['symbol']:12s} {r['iv_pct']:6.1f} {r['ivp']:5.0f} {r['iv_rank']:7.0f} {r['iv_low']:5.1f}-{r['iv_high']:.1f}")
    if a.json:
        Path(a.json).write_text(json.dumps({"as_of": str(last.date()), "rows": rows}, indent=1))


if __name__ == "__main__":
    main()
