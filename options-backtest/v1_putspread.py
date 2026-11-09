"""V1 calls on a fresh red flip + bull put spreads on a fresh green flip (AZ, Nifty F&O, 30-45 DTE), with a results-date filter.

Usage: python options-backtest/v1_putspread.py [--flip 2] [--results-days 15] [--put-delta 0.10] [--hedge-strikes 2] [--capital 15000000] [--slip 0.03]
Calls: as v1_backtest (0.10 delta, stop 3x, profit 60% decay, strict strike exit). Put spread: sell the put nearest --put-delta, buy the put
--hedge-strikes listed strikes lower; exit when the spread value >= 3x the credit (stop), <= 40% of the credit (profit), or the stock closes at/below the short strike.
Margin: calls 13% of notional, spread = (width - credit) x lot. End-of-day settlement marks."""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import backtest as bt  # noqa: E402
import v1_backtest as v1  # noqa: E402

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"


def put_table(df_pe, d, e, S0):
    g = df_pe.get((d, e))
    if g is None:
        return []
    T = (e - d).days / 365.0
    rows = []
    for _, r in g[(g["strike"] < S0) & (g["oi"] > 0) & (g["settle"] > 0)].iterrows():
        v = bt.implied_vol("PE", S0, float(r["strike"]), T, float(r["settle"]))
        if v:
            rows.append((float(r["strike"]), bt.delta_abs("PE", S0, float(r["strike"]), T, v), float(r["settle"]), bool(r["vol"] > 0)))
    return sorted(rows)


def pser(sm, e, k):
    g = sm.df[(sm.df["expiry"] == e) & (sm.df["strike"] == k) & (sm.df["typ"] == "PE")]
    return g.drop_duplicates("date", keep="last").set_index("date")["settle"]


def sim_spread(sm, d, e, ks, kh, ps0, ph0, p):
    s = p["slip"]
    credit = ps0 * (1 - s) - ph0 * (1 + s)
    width = ks - kh
    if credit < 1.0 or credit < 0.10 * width or credit > 0.7 * width:
        return None
    cost = bt.leg_cost(ps0 * sm.lot, True) + bt.leg_cost(ph0 * sm.lot, False)
    a, b = pser(sm, e, ks), pser(sm, e, kh)
    la, lb = ps0, ph0
    path, res = [], None
    for t in [x for x in sm.dates if d < x <= e]:
        la, lb = float(a.get(t, la)), float(b.get(t, lb))
        spot = float(sm.und.loc[t])
        mid = la - lb
        path.append((t, (credit - mid) * sm.lot))
        if t == e:
            res = (min(max(ks - spot, 0) - max(kh - spot, 0), width), "expiry", t)
            break
        fill = min(la * (1 + s) - lb * (1 - s), width)
        if spot <= ks:
            res = (fill, "strike", t)
            break
        if mid >= p["stop"] * credit:
            res = (fill, "stop", t)
            break
        if mid <= (1 - p["profit"]) * credit:
            res = (fill, "profit", t)
            break
    if not res:
        return None
    ev, reason, xd = res
    if reason != "expiry":
        cost += bt.leg_cost(la * sm.lot, False) + bt.leg_cost(lb * sm.lot, True)
    pnl = (credit - ev) * sm.lot - cost
    spot0 = float(sm.und.loc[d])
    return {"sym": sm.name, "entry": d, "exit": xd, "expiry": e, "kind": "putspread", "reason": reason, "pnl": pnl, "cost": cost,
            "margin": max((width - credit) * sm.lot, 1.0), "path": path, "entry_cost": cost - 0, "lot": sm.lot}


def flip_signal(sm, d, colour_want, n):
    idx = sm.dates.index(d)
    if idx == 0:
        return False
    pd_ = sm.dates[idx - 1]
    if pd_ not in sm.colour.index:
        return False
    if sm.colour.get(pd_) != colour_want:
        return False
    k = list(sm.colour.index).index(pd_)
    other = "up" if colour_want == "down" else "down"
    return other in list(sm.colour.iloc[max(0, k - n):k + 1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--flip", type=int, default=2)
    ap.add_argument("--results-days", type=int, default=15)
    ap.add_argument("--put-delta", type=float, default=0.10)
    ap.add_argument("--hedge-strikes", type=int, default=2)
    ap.add_argument("--capital", type=float, default=15_000_000)
    ap.add_argument("--slip", type=float, default=0.03)
    a = ap.parse_args()
    v1.RES_DAYS = a.results_days
    if a.results_days:
        v1.RESULTS.update(json.loads((DATA / "results_dates.json").read_text()))
    excl = set(json.loads((HERE.parent / "zerodha-live" / "data" / "excluded_symbols.json").read_text())["symbols"])
    names = [n for n in json.loads((HERE.parent / "zerodha-live" / "data" / "fno_universe.json").read_text())["symbols"] if n not in excl]
    p = {"slip": a.slip, "stop": 3.0, "profit": 0.6, "margin_pct": 0.13, "strike_exit": True, "flip_exit": False}
    calls, puts = [], []
    for n in names:
        if not (DATA / "sym_all" / f"{n}.pkl").exists():
            continue
        sm = v1.S(n)
        if not sm.ok:
            continue
        pe = {k: v for k, v in sm.df[sm.df["typ"] == "PE"].groupby(["date", "expiry"])}
        for e in sm.expiries:
            ds = [d for d in sm.dates if 30 <= (e - d).days <= 45]
            did_c = did_p = False
            for d in ds:
                if v1.results_due(n, d):
                    continue
                if not did_c and flip_signal(sm, d, "down", a.flip):
                    tb = v1.call_table(sm, d, e)
                    pick = min(tb, key=lambda r: abs(r[1] - 0.10)) if tb else None
                    if pick and pick[2] >= 0.5:
                        tr = v1.simulate(sm, d, e, pick[0], pick[2], p)
                        if tr:
                            tr["kind"] = "call"
                            calls.append(tr)
                            did_c = True
                if not did_p and flip_signal(sm, d, "up", a.flip):
                    rows = put_table(pe, d, e, float(sm.und.loc[d]))
                    traded = [i for i in range(len(rows)) if rows[i][3]]
                    if traded:
                        i = min(traded, key=lambda j: abs(rows[j][1] - a.put_delta))
                        h = i - a.hedge_strikes
                        h = max(h, 0)
                        if h < i and rows[i][2] >= 0.5:
                            tr = sim_spread(sm, d, e, rows[i][0], rows[h][0], rows[i][2], rows[h][2], p)
                            if tr:
                                puts.append(tr)
                                did_p = True
    print(f"flip<={a.flip} days, results filter {a.results_days}d: {len(calls)} call signals, {len(puts)} put-spread signals", flush=True)
    for label, trades in (("calls only", calls), ("put spreads only", puts), ("calls + put spreads", calls + puts)):
        acc = v1.portfolio(trades, a.capital)
        m = v1.metrics(acc, a.capital, label, {"signals": len(trades)})
        keep = ["variant", "n", "win%", "avg_win", "avg_loss", "exp_Rs", "total_Rs", "ann_%cap", "worst_mo_%", "maxDD_%", "peak_margin_%", "avg_margin_%", "stop%", "strike%", "profit%", "worst_trade", "pos_months"]
        print({k: m.get(k) for k in keep}, flush=True)


if __name__ == "__main__":
    main()
