"""ND universe test of Minervini / Bonde style filters and sleeves against the live ND (dh252) rules (user request 2026-11-24).

  python swing-backtest/bonde_minervini_test.py --data /tmp/claude-0/bt/checkpoints [--start 2016-11-07]

Part 1 - ENTRY FILTERS on the live ND strategy (252-day closing high + Supertrend green, same engine, costs, ladder, 6% idle cash). A filter only blocks
         NEW entries; exits (Supertrend red) and add-ons are untouched. Variants: Trend Template (25% / 30% above the 52-week low, RS >= 70),
         signal-day volume filters, Bonde 2014 EP surge (close +4% on 3x the 50-day average volume and >= 300,000 shares) and its complement.
Part 2 - STANDALONE EVENT STUDY (no portfolio): Momentum Burst (c/c1 >= 1.04, v > v1, v >= 100,000, not up 3 days running, prior day narrow-range or
         down) and EP-2014 events, entered at the next open, exited after N sessions at the open or on Supertrend red; costs and slippage as the engine.
Caveats as in swing_backtest.py (survivorship, dividend-adjusted prices, no circuit limits). Volume is as Yahoo reports it. RS rank = percentile of the
252-session return across the universe on that day (Minervini's own RS formula is not public in his words).
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import swing_backtest as sw  # noqa: E402

ROOT = HERE.parent


def live_symbols(data_dir):
    man = pd.read_csv(data_dir / "manifest.csv")
    symbols = man[man["status"] == "VALIDATED"]["symbol"].tolist()
    ex = json.loads((ROOT / "dhan-live" / "data" / "excluded_universe.json").read_text())
    sfx = tuple(x.upper() for x in ex.get("suffixes", []))
    perm = {x.upper() for x in ex.get("symbols", [])}
    etf_extra = {"LIQUIDCASE", "GOLDBEES", "MIDCAPETF", "NIFTYIETF", "MON100", "MASPTOP50", "MAFANG", "MOM100", "SILVERBEES"}

    def keep(sym):
        b = sym.split(".")[0].upper()
        return not (b in perm or b in etf_extra or b.endswith(("ETF", "IETF", "BEES")) or (sfx and b.endswith(sfx)))
    return [s for s in symbols if keep(s)]


def features(data_dir, symbols):
    """Per symbol DataFrame of the flags used by the filters."""
    feats, closes = {}, {}
    for sym in symbols:
        p = data_dir / "raw" / f"{sym.replace('.', '_')}.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        df.index = pd.to_datetime(df.index).tz_localize(None)
        df = df.sort_index()
        df = df[~df.index.duplicated()]
        if len(df) < 260:
            continue
        c, v, lo, hi = df["Close"], df["Volume"], df["Low"], df["High"]
        f = pd.DataFrame(index=df.index)
        f["close"] = c
        f["ret1"] = c.pct_change()
        f["vol"] = v
        f["vol50"] = v.rolling(50).mean().shift(1)
        f["sma50"], f["sma150"], f["sma200"] = c.rolling(50).mean(), c.rolling(150).mean(), c.rolling(200).mean()
        f["sma200_up"] = f["sma200"] > f["sma200"].shift(22)
        f["low52"] = lo.rolling(252).min()
        f["high52"] = hi.rolling(252).max()
        f["ret252"] = c / c.shift(252) - 1
        f["rng"] = (hi - lo) / c.shift(1)
        f["open"], f["high"], f["low"] = df["Open"], hi, lo
        feats[sym] = f
        closes[sym] = c
    rs = pd.DataFrame({s: f["ret252"] for s, f in feats.items()}).rank(axis=1, pct=True) * 100
    for s, f in feats.items():
        f["rs"] = rs[s]
    return feats


def flags(f, kind):
    tt = (f["close"] > f["sma50"]) & (f["sma50"] > f["sma150"]) & (f["sma150"] > f["sma200"]) & f["sma200_up"] & (f["close"] >= 0.75 * f["high52"]) & (f["rs"] >= 70)
    if kind == "tt25":
        return tt & (f["close"] >= 1.25 * f["low52"])
    if kind == "tt30":
        return tt & (f["close"] >= 1.30 * f["low52"])
    if kind == "vol15":
        return f["vol"] >= 1.5 * f["vol50"]
    if kind == "vol2":
        return f["vol"] >= 2.0 * f["vol50"]
    if kind == "ep14":
        return (f["ret1"] >= 0.04) & (f["vol"] >= 3 * f["vol50"]) & (f["vol"] >= 300000)
    if kind == "not_ep14":
        return ~((f["ret1"] >= 0.04) & (f["vol"] >= 3 * f["vol50"]) & (f["vol"] >= 300000))
    if kind == "up4":
        return f["ret1"] >= 0.04
    raise ValueError(kind)


def filtered(raw, feats, kind):
    """Copy of the engine data with the 252-day-high level blanked where the filter is False (blocks entries only)."""
    out = {}
    for sym, bars in raw.items():
        f = feats.get(sym)
        ok = flags(f, kind).fillna(False) if f is not None else None
        nb = {}
        for dt, t in bars.items():
            if ok is not None and dt in ok.index and ok.at[dt]:
                nb[dt] = t
            else:
                nb[dt] = (t[0], t[1], None, t[3], t[4])
        out[sym] = nb
    return out


def run_variant(data_dir, symbols, start, raw, label):
    orig = sw.load
    sw.load = lambda *a, **k: raw
    try:
        res = sw.run("dhan", data_dir, symbols, start, 0.001, cash_rate=0.06)
    finally:
        sw.load = orig
    out, cv, tr = sw.summarise(res, label)
    keys = ["cagr%", "max_dd%", "closed", "win%", "avg_win%", "avg_loss%", "pf", "avg_hold_win_d", "avg_hold_loss_d", "final_equity", "missed_entries_no_cash"]
    row = {"variant": label, **{k: out[k] for k in keys}}
    row["ret/dd"] = round(out["cagr%"] / abs(out["max_dd%"]), 2)
    return row


def event_study(feats, start, kind, hold, slip=0.001):
    """Standalone: enter next open after a signal day, exit after `hold` sessions at the open (or None = Supertrend red, approximated by SMA-free fixed hold only)."""
    rows = []
    for sym, f in feats.items():
        f = f[f.index >= start]
        if len(f) < hold + 3:
            continue
        c, v, r1 = f["close"].values, f["vol"].values, f["ret1"].values
        if kind == "mb":
            sig = (r1 >= 0.04) & (v > np.roll(v, 1)) & (v >= 100000)
            up3 = (np.roll(r1, 1) > 0) & (np.roll(r1, 2) > 0) & (np.roll(r1, 3) > 0)
            prev_quiet = (np.roll(r1, 1) <= 0) | (np.roll(f["rng"].values, 1) <= np.nanpercentile(f["rng"].values, 40))
            sig = sig & ~up3 & prev_quiet
        else:
            sig = (r1 >= 0.04) & (v >= 3 * f["vol50"].values) & (v >= 300000)
        if kind == "ep8":
            sig = (r1 >= 0.08) & (v >= 3 * f["vol50"].values) & (v >= 100000)
        idx = np.where(sig)[0]
        last_exit = -1
        o = f["open"].values
        for i in idx:
            if i + 1 + hold >= len(f) or i <= last_exit or i < 5:
                continue
            e, x = o[i + 1] * (1 + slip), o[i + 1 + hold] * (1 - slip)
            val = 20000.0
            q = max(1, int(val // e))
            pl = (x - e) * q - sw.charges(q * e, "buy") - sw.charges(q * x, "sell")
            rows.append({"sym": sym, "date": f.index[i], "pct": (pl / (q * e)) * 100})
            last_exit = i + 1 + hold
    d = pd.DataFrame(rows)
    if d.empty:
        return {"kind": kind, "hold": hold, "n": 0}
    w, l = d[d["pct"] > 0], d[d["pct"] <= 0]
    return {"kind": kind, "hold": hold, "n": len(d), "win%": round(100 * len(w) / len(d), 1), "avg%": round(d["pct"].mean(), 2), "median%": round(d["pct"].median(), 2),
            "avg_win%": round(w["pct"].mean(), 1), "avg_loss%": round(l["pct"].mean(), 1), "pf": round(w["pct"].sum() / abs(l["pct"].sum()), 2),
            "per_year": round(len(d) / max(1, (d["date"].max() - d["date"].min()).days / 365.25), 0)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--start", default="2016-11-07")
    ap.add_argument("--out", default=str(HERE / "results" / "bonde_minervini"))
    a = ap.parse_args()
    data_dir = Path(a.data)
    start = pd.Timestamp(a.start)
    symbols = live_symbols(data_dir)
    print(f"universe {len(symbols)} symbols", flush=True)
    feats = features(data_dir, symbols)
    print(f"features for {len(feats)} symbols", flush=True)
    raw = sw.load(data_dir, symbols, start, True)
    rows = [run_variant(data_dir, symbols, start, raw, "baseline: 252d closing high + ST green")]
    print(rows[-1], flush=True)
    for kind, label in [("tt25", "+ Trend Template (25% above low, RS>=70)"), ("tt30", "+ Trend Template (30% above low, RS>=70)"), ("vol15", "+ signal-day volume >= 1.5x 50d avg"),
                        ("vol2", "+ signal-day volume >= 2x 50d avg"), ("up4", "+ signal-day close up >= 4%"), ("ep14", "only EP-2014 surge days (+4%, 3x vol, 300k)"),
                        ("not_ep14", "excluding EP-2014 surge days")]:
        rows.append(run_variant(data_dir, symbols, start, filtered(raw, feats, kind), label))
        print(rows[-1], flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(a.out + "_filters.csv", index=False)
    print("\n" + df.to_string(index=False), flush=True)
    ev = []
    for kind in ("mb", "ep14", "ep8"):
        for hold in (3, 5, 10, 20):
            ev.append(event_study(feats, start, kind, hold))
    edf = pd.DataFrame(ev)
    edf.to_csv(a.out + "_events.csv", index=False)
    print("\nEVENT STUDY (standalone, next-open entry, fixed-hold exit at open, costs + 0.1% slippage)\n" + edf.to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
