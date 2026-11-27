"""Daily IV percentile (IVP) update for the Nifty F&O stocks (user, 2026-11-26). Informational only: it never changes a rule, signal or order.

  python scripts/ivp_update.py            # fetch the NSE F&O bhavcopy days not yet stored, update the IV history, write the per-broker ivp.json files
  python scripts/ivp_update.py --rebuild  # recompute every cached day (after a change to the IV method)

History: market-data/iv_history.json {"days": {YYYY-MM-DD: {SYMBOL: ATM IV}}, "holidays": [...]} (about 1 MB, committed, so a fresh cloud session only downloads the new days).
Method (same as the options backtest): per stock and day, ATM IV = mean of the call and put at the 2 strikes nearest the underlying (settlement prices, traded contracts only) from the expiry 20-60 days away
(nearest 35), Black-Scholes inversion. IVP = share of the previous 252 sessions with a LOWER ATM IV than today (OPTIONS_STRATEGY_V2.md definition); IV rank = (IV - 1y low) / (1y high - 1y low), clamped to 0-100.
Outputs (one copy per broker; ND, AZ and DI stay separate and each engine reads only its own file): dhan-live/data/ivp.json, zerodha-live/data/ivp.json, icici-live/data/ivp.json.
Source: NSE archive bhavcopy (public). The newest file appears after the close (evening IST); a missing newest day is retried on the next run and never blocks a refresh.
"""
import argparse
import csv
import gzip
import io
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "options-backtest"))
from backtest import implied_vol  # noqa: E402
from fetch_bhavcopy import KEEP, get, rows_of  # noqa: E402

HIST = ROOT / "market-data" / "iv_history.json"
CACHE = ROOT / "options-backtest" / "data" / "fo_ivp"
OUTS = [ROOT / b / "data" / "ivp.json" for b in ("dhan-live", "zerodha-live", "icici-live")]
KEEP_DAYS = 300
WINDOW = 252


def read_day(path):
    df = pd.read_csv(path, dtype=str)
    return pd.DataFrame({"sym": df["TckrSymb"], "expiry": pd.to_datetime(df["XpryDt"]), "strike": df["StrkPric"].astype(float), "typ": df["OptnTp"],
                         "settle": df["SttlmPric"].astype(float), "vol": df["TtlTradgVol"].astype(float), "und": df["UndrlygPric"].astype(float), "date": pd.to_datetime(df["TradDt"])})


def day_iv(path):
    """{symbol: ATM IV} for one cached day file."""
    df = read_day(path)
    if df.empty:
        return str(path.name)[:8], {}
    d = df["date"].iloc[0]
    out = {}
    for sym, g in df.groupby("sym"):
        S = float(g["und"].iloc[0])
        dte = (g["expiry"] - d).dt.days
        exps = g[(dte >= 20) & (dte <= 60)]["expiry"].unique()
        if len(exps) == 0:
            continue
        e = min(exps, key=lambda x: abs((x - d).days - 35))
        ge = g[g["expiry"] == e]
        T = (e - d).days / 365.0
        ivs = []
        for k in sorted(ge["strike"].unique(), key=lambda k: abs(k - S))[:2]:
            for typ in ("CE", "PE"):
                r = ge[(ge["strike"] == k) & (ge["typ"] == typ) & (ge["vol"] > 0)]
                if r.empty:
                    continue
                v = implied_vol(typ, S, k, T, float(r["settle"].iloc[0]))
                if v:
                    ivs.append(v)
        if ivs:
            out[sym] = round(float(np.mean(ivs)), 4)
    return str(path.name)[:8], out


def download(d8):
    """Save the stock-option rows of one bhavcopy day to the cache; returns 'saved', 'have' or 'none' (holiday / not published yet)."""
    f = CACHE / f"{d8}.csv.gz"
    if f.exists():
        return "have"
    blob = get(d8)
    if blob is None:
        return "none"
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(KEEP)
    for r in rows_of(blob):
        if r["FinInstrmTp"] == "STO":
            w.writerow([r[k] for k in KEEP])
    CACHE.mkdir(parents=True, exist_ok=True)
    with gzip.open(f, "wt", encoding="utf-8") as g:
        g.write(out.getvalue())
    return "saved"


def stats(days):
    """Per-symbol IV, IVP and rank at the latest day that symbol has."""
    dates = sorted(days)
    last = dates[-1]
    series = {}
    for d in dates:
        for s, v in days[d].items():
            series.setdefault(s, []).append((d, v))
    rows = {}
    for s, pairs in series.items():
        if pairs[-1][0] != last:
            continue            # no option data on the latest day: not current
        vals = [v for _, v in pairs]
        today, hist = vals[-1], np.array(vals[-WINDOW - 1:-1])
        if len(hist) < 60:
            continue
        lo, hi = float(hist.min()), float(hist.max())
        rows[s] = {"iv": round(today * 100, 1), "ivp": int(round(float((hist < today).mean() * 100))), "ivr": int(round(min(100, max(0, (today - lo) / (hi - lo) * 100)))) if hi > lo else None,
                   "lo": round(lo * 100, 1), "hi": round(hi * 100, 1), "n": len(hist)}
    return last, rows


TIER_CUTS = (("A", 25), ("B", 60), ("C", 100), ("D", 150))      # rank bands of the structural-IV ranking; everything below is E


def tiers(days, min_days=150):
    """Structural IV tier per stock (user, 2026-11-27): score = 0.6 x median ATM IV + 0.4 x the 20th-percentile IV (the floor) over the whole stored history,
    so stocks that are CONSISTENTLY rich rank above one-off spikes. Needs min_days of history; others get no tier. Returns {symbol: {tier, tier_rank, iv_med, iv_floor}}."""
    series = {}
    for d in sorted(days):
        for s, v in days[d].items():
            if v:
                series.setdefault(s, []).append(v * 100)
    sc = []
    for s, xs in series.items():
        if len(xs) < min_days:
            continue
        ys = sorted(xs)
        med, p20 = ys[len(ys) // 2], ys[int(len(ys) * 0.2)]
        sc.append((0.6 * med + 0.4 * p20, s, med, p20))
    sc.sort(reverse=True)
    out = {}
    for i, (_, s, med, p20) in enumerate(sc, 1):
        t = next((n for n, cut in TIER_CUTS if i <= cut), "E")
        out[s] = {"tier": t, "tier_rank": i, "iv_med": round(med, 1), "iv_floor": round(p20, 1)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true")
    a = ap.parse_args()
    hist = json.loads(HIST.read_text()) if HIST.exists() and not a.rebuild else {"days": {}, "holidays": []}
    days, hol = hist["days"], set(hist.get("holidays", []))
    today = date.today()
    last = max(days) if days else None
    start = datetime.strptime(last, "%Y-%m-%d").date() + timedelta(days=1) if last else today - timedelta(days=int(KEEP_DAYS * 1.45))
    want = []
    d = start
    while d <= today:
        if d.weekday() < 5 and d.strftime("%Y%m%d") not in hol:
            want.append(d.strftime("%Y%m%d"))
        d += timedelta(days=1)
    if a.rebuild:
        want = sorted({p.name[:8] for p in CACHE.glob("*.csv.gz")} | set(want))
    fetched = 0
    for d8 in want:
        try:
            st = download(d8)
        except Exception as e:  # noqa: BLE001
            print(f"  {d8}: fetch failed ({e}); will retry next run")
            continue
        if st == "none":
            if (today - datetime.strptime(d8, "%Y%m%d").date()).days >= 3:
                hol.add(d8)        # an old day with no file is a holiday; today / yesterday may just be unpublished
            continue
        fetched += st == "saved"
    new = [p for p in sorted(CACHE.glob("*.csv.gz")) if datetime.strptime(p.name[:8], "%Y%m%d").strftime("%Y-%m-%d") not in days]
    if new:
        t0 = time.time()
        with ProcessPoolExecutor() as ex:
            for d8, iv in ex.map(day_iv, new):
                if iv:
                    days[datetime.strptime(d8, "%Y%m%d").strftime("%Y-%m-%d")] = iv
        print(f"IV computed for {len(new)} new day(s) in {time.time() - t0:.0f}s ({fetched} downloaded)")
    if not days:
        sys.exit("no IV history and no bhavcopy could be fetched")
    keep = sorted(days)[-KEEP_DAYS:]
    days = {k: days[k] for k in keep}
    HIST.parent.mkdir(parents=True, exist_ok=True)
    HIST.write_text(json.dumps({"as_of": keep[-1], "method": "ATM IV from NSE F&O bhavcopy settlement prices, expiry 20-60d, BS inversion", "holidays": sorted(hol), "days": days}, separators=(",", ":")))
    asof, rows = stats(days)
    for s_, t_ in tiers(days).items():
        if s_ in rows:
            rows[s_].update(t_)
    payload = json.dumps({"as_of": asof, "window_sessions": WINDOW, "source": "NSE F&O bhavcopy (end-of-day settlement prices)", "rows": rows}, indent=0, separators=(",", ":"))
    for p in OUTS:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(payload)
    age = (today - datetime.strptime(asof, "%Y-%m-%d").date()).days
    print(f"IVP as of {asof} for {len(rows)} stocks (written to {', '.join(p.parent.parent.name for p in OUTS)})" + (f"; newest bhavcopy is {age} days old (weekend/holiday or not published yet)" if age > 1 else ""))


if __name__ == "__main__":
    main()
