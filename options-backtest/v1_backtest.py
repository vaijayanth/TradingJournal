"""Backtest of the user's V1 rules on AZ: sell OTM stock calls (about 0.10 delta) across all Nifty F&O stocks, one lot each.

Usage: python options-backtest/v1_backtest.py [--slip 0.03] [--margin-pct 0.13] [--capital 15000000]
V1 rules simulated (the user's, 2026-11-09):
  entry     entry rule variants: 'v1' = V1's call signal (RSI14 > 70, or Supertrend red with RSI >= 30), 'red' = Supertrend red, 'all' = every stock every cycle;
            signals are read at the PREVIOUS close; DTE window 30-45 days (AZ's >=30-day rule) or 14-28 days; one trade per stock per monthly expiry
  strike    traded OTM call whose Black-Scholes delta (implied vol from its settlement price) is nearest 0.10
  exits     STOP when the premium is >= 3x the premium sold; PROFIT when it has decayed 60% (premium <= 40% of sold); STRICT STRIKE EXIT when the stock closes at or
            above the strike (even if the stop has not triggered); optional exit when the Supertrend turns green; otherwise held to expiry (expires worthless if OTM)
  costs     Indian charges per leg + slippage max(slip x price, 1 tick = Rs0.05) on every fill
  margin    modelled as margin_pct x stock price x lot (Dhan quoted about 12-13% for far-OTM stock calls); portfolio capacity = capital x utilisation
Marks are NSE end-of-day settlement prices, spot = the daily underlying close, so intraday touches of the strike or the stop are not seen.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import backtest as bt  # noqa: E402

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
TICK = 0.05


def rsi14(c):
    c = np.asarray(c, float)
    out = np.full(len(c), np.nan)
    if len(c) < 15:
        return out
    d = np.diff(c)
    up, dn = np.where(d > 0, d, 0.0), np.where(d < 0, -d, 0.0)
    au, ad = up[:14].mean(), dn[:14].mean()
    out[14] = 100 - 100 / (1 + au / ad) if ad else 100
    for i in range(14, len(d)):
        au = (au * 13 + up[i]) / 14
        ad = (ad * 13 + dn[i]) / 14
        out[i + 1] = 100 - 100 / (1 + au / ad) if ad else 100
    return out


def load_ohlc(sym):
    p = DATA / "ohlc" / f"{sym}.pkl"
    p.parent.mkdir(exist_ok=True)
    if p.exists():
        return pd.read_pickle(p)
    import yfinance as yf
    try:
        df = yf.download(sym + ".NS", start="2023-06-01", end="2026-11-12", progress=False, auto_adjust=False)
    except Exception:
        return None
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["High", "Low", "Close"]].dropna()
    df.to_pickle(p)
    return df


class S:
    """One stock: option rows, daily underlying, signals."""

    def __init__(self, name):
        self.name = name
        self.df = pd.read_pickle(DATA / "sym_all" / f"{name}.pkl")
        self.df["typ"] = self.df["typ"].astype(str)
        self.und = self.df.groupby("date")["und"].median()
        self.dates = list(self.und.index)
        self.expiries = sorted(self.df["expiry"].unique())
        self.lot = int(self.df["lot"].iloc[-1])
        self.byde = {k: v for k, v in self.df[self.df["typ"] == "CE"].groupby(["date", "expiry"])}
        self._ser = {}
        oh = load_ohlc(name)
        self.ok = oh is not None and len(oh) > 60
        if self.ok:
            idx = pd.to_datetime(oh.index).tz_localize(None)
            dirs = bt.supertrend_dir(oh["High"].to_numpy(float), oh["Low"].to_numpy(float), oh["Close"].to_numpy(float))
            self.colour = pd.Series(dirs, index=idx)
            self.rsi = pd.Series(rsi14(oh["Close"].to_numpy(float)), index=idx)

    def series(self, exp, k):
        key = (exp, k)
        if key not in self._ser:
            g = self.df[(self.df["expiry"] == exp) & (self.df["strike"] == k) & (self.df["typ"] == "CE")]
            self._ser[key] = g.drop_duplicates("date", keep="last").set_index("date")["settle"]
        return self._ser[key]


def slip(price, s):
    return max(s * price, TICK)


def call_table(sm, d, e):
    g = sm.byde.get((d, e))
    if g is None:
        return []
    S0 = float(sm.und.loc[d])
    T = (e - d).days / 365.0
    out = []
    for _, r in g[(g["strike"] > S0) & (g["oi"] > 0) & (g["settle"] > 0) & (g["vol"] > 0)].iterrows():
        v = bt.implied_vol("CE", S0, float(r["strike"]), T, float(r["settle"]))
        if v:
            out.append((float(r["strike"]), bt.delta_abs("CE", S0, float(r["strike"]), T, v), float(r["settle"])))
    return sorted(out)


def signal(sm, d, rule):
    idx = sm.dates.index(d)
    if idx == 0:
        return False
    pd_ = sm.dates[idx - 1]
    if rule == "all":
        return True
    if pd_ not in sm.colour.index:
        return False
    col, rs = sm.colour.get(pd_), sm.rsi.get(pd_)
    if rule.startswith("flip"):      # Supertrend turned red within the last N sessions (flipN), and is red at the previous close
        n = int(rule[4:])
        if col != "down":
            return False
        k = list(sm.colour.index).index(pd_)
        recent = list(sm.colour.iloc[max(0, k - n):k + 1])    # the last n+1 bars up to the signal close
        return "up" in recent
    if rule == "red":
        return col == "down"
    return bool(rs is not None and not np.isnan(rs) and (rs > 70 or (col == "down" and rs >= 30)))   # V1 call signal


RESULTS = {}
RES_DAYS = 0


def results_due(sym, d):
    """True when a results date falls within RES_DAYS calendar days after d."""
    if not RES_DAYS:
        return False
    for x in RESULTS.get(sym, []):
        if 0 <= (pd.Timestamp(x) - d).days <= RES_DAYS:
            return True
    return False


def simulate(sm, d, e, K, prem, p):
    """Run one short call. Returns a trade dict with the MTM path."""
    s = p["slip"]
    credit = prem - slip(prem, s)
    cost = bt.leg_cost(credit * sm.lot, True)
    ser = sm.series(e, K)
    last = prem
    path = []
    exit_c, reason, exit_d = None, None, None
    for t in [x for x in sm.dates if d < x <= e]:
        mark = float(ser.get(t, last))
        last = mark
        spot = float(sm.und.loc[t])
        path.append((t, (credit - mark) * sm.lot))
        if t == e:
            exit_c, reason, exit_d = max(spot - K, 0.0), "expiry", t
            break
        if p["strike_exit"] and spot >= K:
            exit_c, reason, exit_d = mark + slip(mark, s), "strike", t
            break
        if mark >= p["stop"] * prem:
            exit_c, reason, exit_d = mark + slip(mark, s), "stop", t
            break
        if mark <= (1 - p["profit"]) * prem:
            exit_c, reason, exit_d = mark + slip(mark, s), "profit", t
            break
        if p["flip_exit"] and sm.colour.get(t) == "up":
            exit_c, reason, exit_d = mark + slip(mark, s), "flip", t
            break
    if exit_c is None:
        return None
    if reason != "expiry" or exit_c > 0:
        cost += bt.leg_cost(max(exit_c, 0.05) * sm.lot, False)
    pnl = (credit - exit_c) * sm.lot - cost
    spot0 = float(sm.und.loc[d])
    return {"sym": sm.name, "entry": d, "exit": exit_d, "expiry": e, "strike": K, "prem": prem, "reason": reason, "pnl": pnl, "cost": cost,
            "margin": p["margin_pct"] * spot0 * sm.lot, "path": path, "entry_cost": bt.leg_cost(credit * sm.lot, True), "lot": sm.lot}


def portfolio(trades, cap):
    """Accept trades in entry order while the margin of the open ones stays within cap. Returns accepted list."""
    acc = []
    for t in sorted(trades, key=lambda x: (x["entry"], x["margin"])):
        used = sum(a["margin"] for a in acc if a["entry"] <= t["entry"] < a["exit"])
        if used + t["margin"] <= cap:
            acc.append(t)
    return acc


def metrics(acc, capital, label, extra=None):
    if not acc:
        return {"variant": label, "n": 0}
    tr = pd.DataFrame([{k: v for k, v in a.items() if k != "path"} for a in acc])
    days = sorted({p[0] for a in acc for p in a["path"]} | {a["entry"] for a in acc})
    eq = pd.Series(0.0, index=pd.DatetimeIndex(days))
    for a in acc:
        pth = pd.Series({t: v for t, v in a["path"]})
        idx = eq.index
        live = (idx >= a["entry"]) & (idx < a["exit"])
        eq[live] += pth.reindex(idx[live]).ffill().fillna(0.0).to_numpy() - a["entry_cost"]
        eq[idx >= a["exit"]] += a["pnl"]
    dd = (eq - eq.cummax()).min()
    mon = eq.resample("ME").last().diff().fillna(eq.resample("ME").last())
    margin_used = []
    for t in eq.index[::5]:
        margin_used.append(sum(a["margin"] for a in acc if a["entry"] <= t < a["exit"]))
    yrs = (eq.index[-1] - eq.index[0]).days / 365.0
    w, l = tr[tr["pnl"] > 0], tr[tr["pnl"] <= 0]
    out = {"variant": label, "n": len(tr), "win%": round(100 * len(w) / len(tr), 1), "avg_win": round(w["pnl"].mean() if len(w) else 0), "avg_loss": round(l["pnl"].mean() if len(l) else 0),
           "exp_Rs": round(tr["pnl"].mean()), "total_Rs": round(tr["pnl"].sum()), "ann_%cap": round(100 * tr["pnl"].sum() / yrs / capital, 2),
           "avg_mo_%": round(100 * mon.mean() / capital, 2), "worst_mo_%": round(100 * mon.min() / capital, 2), "maxDD_%": round(100 * dd / capital, 2),
           "peak_margin_%": round(100 * max(margin_used) / capital, 1), "avg_margin_%": round(100 * np.mean(margin_used) / capital, 1),
           "stop%": round(100 * (tr["reason"] == "stop").mean(), 1), "strike%": round(100 * (tr["reason"] == "strike").mean(), 1),
           "profit%": round(100 * (tr["reason"] == "profit").mean(), 1), "expiry%": round(100 * (tr["reason"] == "expiry").mean(), 1),
           "worst_trade": round(tr["pnl"].min()), "pos_months": f"{int((mon > 0).sum())}/{len(mon)}"}
    if extra:
        out.update(extra)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slip", type=float, default=0.03)
    ap.add_argument("--margin-pct", type=float, default=0.13)
    ap.add_argument("--capital", type=float, default=15_000_000)
    ap.add_argument("--tag", default="")
    ap.add_argument("--results-days", type=int, default=0, help="skip entries when results fall within this many calendar days")
    ap.add_argument("--rules", default="v1,red,all")
    ap.add_argument("--windows", default="dte30-45,dte14-28")
    ap.add_argument("--exits", default="YN,NN,YY", help="strike_exit/flip_exit combos, e.g. YN,NN,YY")
    a = ap.parse_args()
    global RES_DAYS
    RES_DAYS = a.results_days
    if RES_DAYS:
        RESULTS.update(json.loads((DATA / "results_dates.json").read_text()))
    excl = set(json.loads((HERE.parent / "zerodha-live" / "data" / "excluded_symbols.json").read_text())["symbols"])
    names = [n for n in json.loads((HERE.parent / "zerodha-live" / "data" / "fno_universe.json").read_text())["symbols"] if n not in excl]
    stocks = []
    for n in names:
        if not (DATA / "sym_all" / f"{n}.pkl").exists():
            continue
        sm = S(n)
        if sm.ok:
            stocks.append(sm)
    print(len(stocks), "stocks with option and price data", flush=True)
    windows = {"dte30-45": (30, 45), "dte14-28": (14, 28)}
    delta = 0.10
    tabs = {}
    for sm in stocks:
        for wname, (lo, hi) in windows.items():
            for e in sm.expiries:
                ds = [d for d in sm.dates if lo <= (e - d).days <= hi]
                for d in ds:
                    tabs[(sm.name, wname, d, e)] = None   # filled lazily below
    results, store = [], {}
    base = {"slip": a.slip, "stop": 3.0, "profit": 0.6, "margin_pct": a.margin_pct}
    for rule in a.rules.split(","):
        for wname, (lo, hi) in windows.items():
            if wname not in a.windows.split(","):
                continue
            for strike_exit, flip_exit in [(c[0] == "Y", c[1] == "Y") for c in a.exits.split(",")]:
                p = dict(base, strike_exit=strike_exit, flip_exit=flip_exit)
                trades = []
                for sm in stocks:
                    for e in sm.expiries:
                        ds = [d for d in sm.dates if lo <= (e - d).days <= hi]
                        for d in ds:
                            if not signal(sm, d, rule):
                                continue
                            if results_due(sm.name, d):
                                continue
                            key = (sm.name, e, d)
                            if key not in store:
                                tb = call_table(sm, d, e)
                                store[key] = min(tb, key=lambda r: abs(r[1] - delta)) if tb else None
                            pick = store[key]
                            if not pick or pick[2] < 0.5:
                                continue
                            tr = simulate(sm, d, e, pick[0], pick[2], p)
                            if tr:
                                trades.append(tr)
                            break      # one trade per stock per expiry: the first day the signal holds
                for util in (1.0, 0.5):
                    acc = portfolio(trades, a.capital * util)
                    label = f"{rule} | {wname} | strike_exit={'Y' if strike_exit else 'N'} flip_exit={'Y' if flip_exit else 'N'} | margin cap {int(util * 100)}%"
                    m = metrics(acc, a.capital, label, {"signals": len(trades)})
                    results.append(m)
                    store[("acc", label)] = acc
                    print(m, flush=True)
    res = pd.DataFrame(results)
    res.to_csv(HERE / f"v1_results{a.tag}.csv", index=False)
    pd.to_pickle({k: v for k, v in store.items() if k[0] == "acc"}, DATA / f"v1_trades{a.tag}.pkl")
    pd.set_option("display.width", 300)
    print(res.drop(columns=["worst_trade"]).to_string())


if __name__ == "__main__":
    main()
