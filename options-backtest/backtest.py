"""Backtest of the v2 stock-option credit-spread rules on real NSE end-of-day prices (bhavcopy settlement prices).

Run build_tables.py first. Usage:  python options-backtest/backtest.py [--quick]
What is simulated (one position per stock per monthly expiry):
  entry   first trading day 30-45 calendar days before the monthly expiry; colour = Supertrend(10,3) at the PREVIOUS close (from Yahoo OHLC)
  short   the OTM strike whose Black-Scholes delta (implied vol from its settlement price) is nearest the target; hedge = 2 listed strikes further out
  filters live strikes only (open interest and volume > 0), credit >= 1.0 and >= 10% of the width, optional IV percentile >= x
  exits   buy back at 50% of the credit (profit), at a loss when the spread costs 2x the credit (stop), time exit at 21 days left; marks = daily settlement prices
  costs   Indian charges (brokerage Rs20/leg, STT 0.1% on sells, exchange 0.0355%, GST, stamp, SEBI) + slippage as a % of each leg's premium
Margin proxy = (width - credit) x lot (defined risk). Everything is per ONE lot per trade.
This is end-of-day data: intraday stop/target touches and real bid/ask are not captured, and prices of illiquid strikes are settlement marks.
"""
import argparse
import itertools
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
RF = 0.065


# ---------------- Black-Scholes helpers (no scipy) ----------------
def ncdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bs_price(kind, S, K, T, v):
    if T <= 0 or v <= 0:
        return max(S - K, 0) if kind == "CE" else max(K - S, 0)
    d1 = (math.log(S / K) + (RF + v * v / 2) * T) / (v * math.sqrt(T))
    d2 = d1 - v * math.sqrt(T)
    if kind == "CE":
        return S * ncdf(d1) - K * math.exp(-RF * T) * ncdf(d2)
    return K * math.exp(-RF * T) * ncdf(-d2) - S * ncdf(-d1)


def implied_vol(kind, S, K, T, price):
    lo, hi = 0.01, 3.0
    intrinsic = max(S - K * math.exp(-RF * T), 0) if kind == "CE" else max(K * math.exp(-RF * T) - S, 0)
    if price <= intrinsic + 1e-6 or price <= 0:
        return None
    if bs_price(kind, S, K, T, hi) < price:
        return None
    for _ in range(45):
        mid = (lo + hi) / 2
        if bs_price(kind, S, K, T, mid) > price:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def delta_abs(kind, S, K, T, v):
    d1 = (math.log(S / K) + (RF + v * v / 2) * T) / (v * math.sqrt(T))
    return ncdf(d1) if kind == "CE" else ncdf(-d1)


# ---------------- Supertrend ----------------
def supertrend_dir(h, l, c, period=10, mult=3.0):
    n = len(c)
    tr = np.zeros(n)
    tr[0] = h[0] - l[0]
    for i in range(1, n):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    atr = np.full(n, np.nan)
    if n < period + 1:
        return [None] * n
    atr[period] = tr[1:period + 1].mean()
    for i in range(period + 1, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    up = [None] * n
    dn = [None] * n
    d = [None] * n
    for i in range(period, n):
        mid = (h[i] + l[i]) / 2
        bu, bl = mid + mult * atr[i], mid - mult * atr[i]
        if i == period or up[i - 1] is None:
            up[i], dn[i], d[i] = bu, bl, "up"
            continue
        up[i] = bu if (bu < up[i - 1] or c[i - 1] > up[i - 1]) else up[i - 1]
        dn[i] = bl if (bl > dn[i - 1] or c[i - 1] < dn[i - 1]) else dn[i - 1]
        d[i] = "up" if c[i] > up[i] else "down" if c[i] < dn[i] else d[i - 1]
    return d


def load_colours(sym, days):
    """Supertrend direction per trading day from Yahoo daily OHLC (cached); None if unavailable."""
    p = DATA / "ohlc" / f"{sym}.pkl"
    p.parent.mkdir(exist_ok=True)
    if p.exists():
        df = pd.read_pickle(p)
    else:
        import yfinance as yf
        try:
            df = yf.download(sym.replace("&", "%26") + ".NS", start="2023-06-01", end="2026-11-12", progress=False, auto_adjust=False)
        except Exception:
            return None
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[["High", "Low", "Close"]].dropna()
        df.to_pickle(p)
    if len(df) < 60:
        return None
    dirs = supertrend_dir(df["High"].to_numpy(float), df["Low"].to_numpy(float), df["Close"].to_numpy(float))
    ser = pd.Series(dirs, index=pd.to_datetime(df.index).tz_localize(None))
    return ser


# ---------------- costs ----------------
def leg_cost(value, sell):
    """Indian charges for one option leg trade of premium value `value` (rupees)."""
    brok = 20.0
    txn = 0.000355 * value
    sebi = 0.000001 * value
    gst = 0.18 * (brok + txn + sebi)
    stt = 0.001 * value if sell else 0.0
    stamp = 0.00003 * value if not sell else 0.0
    return brok + txn + sebi + gst + stt + stamp


# ---------------- data per symbol ----------------
class Sym:
    def __init__(self, name):
        self.name = name
        df = pd.read_pickle(DATA / "sym" / f"{name}.pkl")
        self.df = df
        self.dates = sorted(pd.to_datetime(df["date"].unique()))
        und = df.groupby("date")["und"].median()
        self.und = und
        self.price = df.set_index(["expiry", "strike", "typ", "date"])["settle"].sort_index()
        self.price = self.price[~self.price.index.duplicated(keep="last")]
        self.lot = int(df["lot"].iloc[-1])
        self.expiries = sorted(pd.to_datetime(df["expiry"].unique()))
        self.byde = {k: v for k, v in df.groupby(["date", "expiry"])}
        self.colour = None
        self._chain_cache = {}
        self.atm_iv = None

    def px(self, exp, k, typ, d):
        try:
            return float(self.price.loc[(exp, k, typ, d)])
        except KeyError:
            return None

    def chain(self, d, exp):
        return self.byde.get((d, exp), self.df.iloc[0:0])

    def compute_atm_iv(self):
        """Daily ATM implied vol (mean of call and put at the strike nearest the price) from the expiry 20-60 days away; used for IV percentile."""
        out = {}
        for d in self.dates:
            S = float(self.und.loc[d])
            exps = [e for e in self.expiries if 20 <= (e - d).days <= 60]
            if not exps:
                continue
            e = min(exps, key=lambda x: abs((x - d).days - 35))
            g = self.chain(d, e)
            if g.empty:
                continue
            strikes = sorted(g["strike"].unique(), key=lambda k: abs(k - S))[:3]
            ivs = []
            for k in strikes[:2]:
                for typ in ("CE", "PE"):
                    r = g[(g["strike"] == k) & (g["typ"] == typ) & (g["vol"] > 0)]
                    if r.empty:
                        continue
                    v = implied_vol(typ, S, k, (e - d).days / 365.0, float(r["settle"].iloc[0]))
                    if v:
                        ivs.append(v)
            if ivs:
                out[d] = float(np.mean(ivs))
        self.atm_iv = pd.Series(out).sort_index()

    def ivp(self, d):
        if self.atm_iv is None or d not in self.atm_iv.index:
            return None
        hist = self.atm_iv.loc[:d].iloc[-253:-1]
        if len(hist) < 60:
            return None
        return float((hist < self.atm_iv.loc[d]).mean() * 100)


# ---------------- the trade simulation ----------------
def entry_candidates(sym):
    """(entry_date, expiry) pairs: first trading day with 30-45 calendar days to the expiry."""
    out = []
    for e in sym.expiries:
        ds = [d for d in sym.dates if 30 <= (e - d).days <= 45]
        if ds:
            out.append((ds[0], e))
    return out


def strike_table(sym, d, e, typ):
    """Sorted live OTM strikes (oi>0, vol>0) as (strike, |delta|, settle)."""
    g = sym.chain(d, e)
    S = float(sym.und.loc[d])
    T = (e - d).days / 365.0
    gg = g[(g["typ"] == typ) & (g["oi"] > 0) & (g["settle"] > 0)]
    gg = gg[gg["strike"] > S] if typ == "CE" else gg[gg["strike"] < S]
    if gg.empty:
        return []
    rows = []
    for _, r in gg.iterrows():
        v = implied_vol(typ, S, float(r["strike"]), T, float(r["settle"]))
        if v:
            rows.append((float(r["strike"]), delta_abs(typ, S, float(r["strike"]), T, v), float(r["settle"]), bool(r["vol"] > 0)))
    rows.sort()
    return rows


def pick(rows, typ, target_delta):
    """(short_strike, hedge_strike, short_delta): nearest delta, hedge two listed strikes further out."""
    if not rows:
        return None
    traded = [i for i in range(len(rows)) if rows[i][3]]     # the short must have traded that day; the hedge only needs open interest and a price
    if not traded:
        return None
    best = min(traded, key=lambda i: abs(rows[i][1] - target_delta))
    step = 1 if typ == "CE" else -1
    hi = best + 2 * step
    hi = min(max(hi, 0), len(rows) - 1)      # up to two listed strikes further out; if fewer exist (thin far strikes) use the furthest one
    if hi == best:
        return None
    return rows[best][0], rows[hi][0], rows[best][1]


def run_trade(sym, d, e, legs, p):
    """Simulate one position. legs = [(typ, k_short, k_hedge)]. Returns dict or None."""
    s = p["slip"]
    credit = 0.0
    width = 0.0
    cost = 0.0
    for typ, ks, kh in legs:
        ps, ph = sym.px(e, ks, typ, d), sym.px(e, kh, typ, d)
        if not ps or not ph:
            return None
        credit += ps * (1 - s) - ph * (1 + s)
        width += abs(ks - kh)
        cost += leg_cost(ps * sym.lot, True) + leg_cost(ph * sym.lot, False)
    if credit < p["min_credit"] or credit < p["min_ratio"] * width or credit > 0.7 * width:
        return None      # too thin, or implausibly rich (a data/strike-adjustment artefact)
    last = {}
    exit_v, reason, exit_d = None, None, None
    for t in [x for x in sym.dates if x > d and x <= e]:
        val_mid, val_fill = 0.0, 0.0
        for typ, ks, kh in legs:
            ps, ph = sym.px(e, ks, typ, t), sym.px(e, kh, typ, t)
            ps = ps if ps is not None else last.get((typ, ks))
            ph = ph if ph is not None else last.get((typ, kh))
            if ps is None or ph is None:
                ps, ph = (ps or 0.0), (ph or 0.0)
            last[(typ, ks)], last[(typ, kh)] = ps, ph
            val_mid += ps - ph
            val_fill += ps * (1 + s) - ph * (1 - s)
        dte = (e - t).days
        c0 = credit  # credit after entry slippage
        if val_mid <= (1 - p["profit"]) * c0:
            exit_v, reason, exit_d = min(val_fill, width), "profit", t
            break
        if p["stop"] and val_mid >= p["stop"] * c0:
            exit_v, reason, exit_d = min(val_fill, width), "stop", t
            break
        if dte <= p["time_dte"]:
            exit_v, reason, exit_d = min(val_fill, width), "time", t
            break
        if t == e:
            exit_v, reason, exit_d = min(val_mid, width), "expiry", t
            break
    if exit_v is None:
        return None
    # exit costs: buy back shorts, sell hedges at the exit marks
    for typ, ks, kh in legs:
        ps, ph = last[(typ, ks)], last[(typ, kh)]
        cost += leg_cost(ps * sym.lot, False) + leg_cost(ph * sym.lot, True)
    pnl = (credit - exit_v) * sym.lot - cost
    margin = max((width - credit) * sym.lot, 1.0)
    return {"sym": sym.name, "entry": d, "exit": exit_d, "expiry": e, "reason": reason, "credit": credit, "width": width, "exit_value": exit_v,
            "pnl": pnl, "margin": margin, "roi": pnl / margin, "lot": sym.lot, "cost": cost, "days": (exit_d - d).days}


def summarise(tr):
    if not len(tr):
        return {"n": 0}
    w = tr[tr["pnl"] > 0]
    l = tr[tr["pnl"] <= 0]
    tr = tr.sort_values("exit")
    eq = tr["pnl"].cumsum()
    dd = (eq - eq.cummax()).min()
    monthly = tr.groupby(tr["exit"].dt.to_period("M"))["pnl"].sum()
    return {"n": len(tr), "win%": round(100 * len(w) / len(tr), 1), "avg_win": round(w["pnl"].mean() if len(w) else 0), "avg_loss": round(l["pnl"].mean() if len(l) else 0),
            "expect_Rs": round(tr["pnl"].mean()), "avg_roi%": round(100 * tr["roi"].mean(), 2), "tot_Rs": round(tr["pnl"].sum()), "maxDD_Rs": round(dd),
            "stop%": round(100 * (tr["reason"] == "stop").mean(), 1), "profit%": round(100 * (tr["reason"] == "profit").mean(), 1),
            "worst": round(tr["pnl"].min()), "pos_months": f"{int((monthly > 0).sum())}/{len(monthly)}"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--slip", type=float, default=0.03)
    ap.add_argument("--deltas", default="")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    universe = json.loads((DATA / "universe.json").read_text())["symbols"]
    syms = []
    for name in universe:
        if not (DATA / "sym" / f"{name}.pkl").exists():
            continue
        sm = Sym(name)
        sm.colour = load_colours(name, sm.dates)
        if sm.colour is None:
            print("no price history for", name)
            continue
        sm.compute_atm_iv()
        syms.append(sm)
        print("loaded", name, len(sm.dates), "days", flush=True)

    # entries per stock; strikes are chosen per (delta, side) and cached
    deltas = [float(x) for x in a.deltas.split(",")] if a.deltas else ([0.15, 0.30] if a.quick else [0.15, 0.20, 0.25, 0.30])
    structures = ["directed", "put", "call", "condor"]
    filters = [None, 50]
    results, all_trades = [], {}
    cache = {}
    for sm in syms:
        for d, e in entry_candidates(sm):
            tabs = {typ: strike_table(sm, d, e, typ) for typ in ("CE", "PE")}
            for dl in deltas:
                for typ in ("CE", "PE"):
                    cache[(sm.name, d, e, dl, typ)] = pick(tabs[typ], typ, dl)
    print("strike picks done", len(cache), flush=True)
    base = {"slip": a.slip, "min_credit": 1.0, "min_ratio": 0.10, "profit": 0.5, "stop": 2.0, "time_dte": 21}
    for dl, st, ivf in itertools.product(deltas, structures, filters):
        trades = []
        for sm in syms:
            for d, e in entry_candidates(sm):
                idx = sm.dates.index(d)
                if idx == 0:
                    continue
                col = sm.colour.get(sm.dates[idx - 1])
                ivp = sm.ivp(d)
                if ivp is None:
                    continue   # compare every variant on the same entries: those where IV history exists
                if ivf and ivp < ivf:
                    continue
                ce, pe = cache.get((sm.name, d, e, dl, "CE")), cache.get((sm.name, d, e, dl, "PE"))
                legs = []
                if st == "directed":
                    if col == "down" and ce:
                        legs = [("CE", ce[0], ce[1])]
                    elif col == "up" and pe:
                        legs = [("PE", pe[0], pe[1])]
                elif st == "put" and pe:
                    legs = [("PE", pe[0], pe[1])]
                elif st == "call" and ce:
                    legs = [("CE", ce[0], ce[1])]
                elif st == "condor" and ce and pe:
                    legs = [("CE", ce[0], ce[1]), ("PE", pe[0], pe[1])]
                if not legs:
                    continue
                r = run_trade(sm, d, e, legs, base)
                if r:
                    trades.append(r)
        tr = pd.DataFrame(trades)
        s = summarise(tr)
        s.update({"delta": dl, "structure": st, "ivp>=": ivf or 0})
        results.append(s)
        all_trades[(dl, st, ivf or 0)] = tr
        print(s, flush=True)
    res = pd.DataFrame(results)
    cols = ["delta", "structure", "ivp>=", "n", "win%", "avg_win", "avg_loss", "expect_Rs", "avg_roi%", "tot_Rs", "maxDD_Rs", "stop%", "profit%", "worst", "pos_months"]
    res = res[cols]
    res.to_csv(HERE / f"results_slip{int(a.slip * 100)}{a.tag}.csv", index=False)
    pd.to_pickle(all_trades, HERE / "data" / f"trades_slip{int(a.slip * 100)}{a.tag}.pkl")
    print(res.to_string())


if __name__ == "__main__":
    main()
