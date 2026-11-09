"""Backtest of the two live swing strategies on the backtester's 10-year daily history (checkpoints/raw/*.parquet).

  python swing-backtest/swing_backtest.py --data <dir with raw/ and manifest.csv> --strategy dhan|az [--start 2017-11-01] [--slip 0.001]

Shared mechanics (same as the backtester's own engine): signals are read at a completed day's CLOSE, every order fills at the symbol's NEXT bar's
OPEN, one position per stock, whole-position Supertrend(10,3)-red exit at any profit or loss, WAC-based add-on (price <= -6% below the CURRENT
weighted-average cost and Supertrend green, at least 7 calendar days since the last fill), cash-limited (no leverage, no margin), quantity floored
to whole shares with a minimum of 1, equity = initial capital + realised + open P&L (idle cash earns nothing, deposits ignored).

  dhan : ND / dh252. Universe = every validated symbol. Entry = close above the highest CLOSE of the previous 252 sessions AND Supertrend green.
         Size Rs1,000 +Rs1,000 per 100 closed trades (uncapped). Add-on = int(qty x 0.10), min 1. Capital Rs20,00,000.
         Entries are served biggest breakout first when cash is short.
  az   : AZ / Nifty F&O Supertrend. Universe = current Nifty F&O stocks minus BSE, BEL, RECLTD. Entry = Supertrend turned green within the last 3 sessions
         and green now, not held; ONLY the freshest flip day that has candidates is ordered (today's flips, else 1 day old, ...).
         Size Rs20,000 +Rs5,000 per 100 trades opened (uncapped). Add-on = round(qty x 0.10), min 1. Capital Rs30,00,000.
Costs (Indian delivery): STT 0.1% each side, exchange 0.00297%, SEBI 0.0001%, GST 18% on those two, stamp 0.015% on buys, DP charge Rs15.93 per sale,
brokerage 0, plus slippage (default 0.1% against you on every fill). Caveats: survivorship bias (today's index/F&O lists), dividend-adjusted prices,
no circuit/liquidity limits (1 lot-size positions are tiny so impact is ignored), no tax.
"""
import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from indicators import compute_supertrend  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
WINDOW = 252
ADD_TRIGGER, ADD_COOLDOWN = -6.0, 7
CFG = {
    "dhan": {"capital": 2_000_000, "base": 1000, "step": 1000, "every": 100, "count": "closed", "add": "int", "flip_window": None},
    "az": {"capital": 3_000_000, "base": 20000, "step": 5000, "every": 100, "count": "opened", "add": "round", "flip_window": 3},
}


def charges(value, side):
    exch = value * 0.0000297 + value * 0.000001
    c = value * 0.001 + exch + 0.18 * exch
    if side == "buy":
        c += value * 0.00015
    else:
        c += 15.93
    return c


def load(data_dir, symbols, start, with_high_window):
    raw = {}
    for sym in symbols:
        p = data_dir / "raw" / f"{sym.replace('.', '_')}.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        df.index = pd.to_datetime(df.index).tz_localize(None)
        df = df.sort_index()
        df = df[~df.index.duplicated()]
        if len(df) < 60:
            continue
        o, h, l, c = (df[k].tolist() for k in ("Open", "High", "Low", "Close"))
        dirs, _, _ = compute_supertrend(h, l, c, 10, 3.0)
        roll = df["Close"].rolling(WINDOW).max().shift(1).tolist() if with_high_window else [None] * len(df)
        age, last_up_flip = [], None
        for i, d in enumerate(dirs):
            if d == "up" and i > 0 and dirs[i - 1] == "down":
                last_up_flip = i
            age.append((i - last_up_flip) if (d == "up" and last_up_flip is not None) else None)
        raw[sym] = {dt: (o[i], c[i], roll[i], dirs[i], age[i]) for i, dt in enumerate(df.index) if dt >= start - pd.Timedelta(days=400)}
    return raw


def run(strategy, data_dir, symbols, start, slip, seed=0, fresh_only=True, cash_rate=0.0):
    cfg = CFG[strategy]
    data = load(data_dir, symbols, start, strategy == "dhan")
    dates = sorted({d for s in data.values() for d in s if d >= start})
    cash = float(cfg["capital"])
    cap0 = cash
    pos, pending, closed = {}, {}, []
    realised = fees = 0.0
    opened = 0
    curve, missed = [], {"entry": 0, "add": 0}
    invested_series = []
    last_seen = {}
    prev_dt = None
    for dt in dates:
        if prev_dt is not None and cash_rate:
            cash *= (1 + cash_rate) ** ((dt - prev_dt).days / 365.0)     # idle cash sits in a liquid ETF (LIQUIDBEES) and accrues daily
        prev_dt = dt
        # 1. fills at today's open (sales first so they free cash)
        order = sorted(pending.items(), key=lambda kv: (kv[1]["a"] != "sell", random.Random(f"{seed}|{dt.date()}|{kv[0]}").random()))
        for sym, od in order:
            bar = data[sym].get(dt)
            if bar is None:
                continue
            pending.pop(sym)
            o = bar[0]
            if od["a"] == "sell" and sym in pos:
                p = pos.pop(sym)
                px = o * (1 - slip)
                val = p["qty"] * px
                ch = charges(val, "sell")
                cash += val - ch
                fees += ch
                pl = (px - p["avg"]) * p["qty"] - p["fees"] - ch
                realised += (px - p["avg"]) * p["qty"] - ch
                closed.append({"sym": sym, "entry": p["entry"], "exit": dt, "pl": pl, "pct": (px / p["avg"] - 1) * 100, "adds": p["adds"], "days": (dt - p["entry"]).days, "qty": p["qty"], "cost": p["avg"] * p["qty"]})
            elif od["a"] == "buy" and sym not in pos:
                n = len(closed) if cfg["count"] == "closed" else opened
                tier = cfg["base"] + (n // cfg["every"]) * cfg["step"]
                px = o * (1 + slip)
                qty = max(1, int(tier // px))
                val = qty * px
                ch = charges(val, "buy")
                if cash >= val + ch:
                    cash -= val + ch
                    fees += ch
                    opened += 1
                    pos[sym] = {"entry": dt, "avg": px, "qty": qty, "last": dt, "adds": 0, "fees": ch}
                else:
                    missed["entry"] += 1
            elif od["a"] == "add" and sym in pos:
                p = pos[sym]
                px = o * (1 + slip)
                qty = od["q"]
                val = qty * px
                ch = charges(val, "buy")
                if cash >= val + ch:
                    cash -= val + ch
                    fees += ch
                    tot = p["avg"] * p["qty"] + val
                    p["qty"] += qty
                    p["avg"] = tot / p["qty"]
                    p["last"] = dt
                    p["adds"] += 1
                    p["fees"] += ch
                else:
                    missed["add"] += 1
        # 2. signals at today's close
        cands = []
        for sym, bars in data.items():
            bar = bars.get(dt)
            if bar is None:
                continue
            _, c, roll, d, age = bar
            last_seen[sym] = c
            if d is None:
                continue
            if sym in pos:
                p = pos[sym]
                if d == "down":
                    pending[sym] = {"a": "sell"}
                    continue
                pl = (c / p["avg"] - 1) * 100
                if pl <= ADD_TRIGGER and d == "up" and (dt - p["last"]).days >= ADD_COOLDOWN and sym not in pending:
                    q = p["qty"] * 0.10
                    pending[sym] = {"a": "add", "q": max(1, int(q) if cfg["add"] == "int" else round(q))}
            elif sym not in pending and d == "up":
                if strategy == "dhan":
                    if roll is not None and not pd.isna(roll) and c > roll:
                        cands.append((c / roll - 1, sym))
                else:
                    if age is not None and age <= cfg["flip_window"]:
                        cands.append((age, sym))
        if cands:
            if strategy == "dhan":
                for _, sym in cands:
                    pending[sym] = {"a": "buy"}
            else:
                fresh = min(a for a, _ in cands)
                for a, sym in cands:
                    if a == fresh or not fresh_only:
                        pending[sym] = {"a": "buy"}
        mv = sum(p_["qty"] * (data[s_][dt][1] if dt in data[s_] else last_seen.get(s_, p_["avg"])) for s_, p_ in pos.items())
        inv = sum(p_["avg"] * p_["qty"] for p_ in pos.values())
        curve.append((dt, cash + mv, inv, len(pos)))
    return {"curve": curve, "closed": closed, "open": pos, "fees": fees, "missed": missed, "cap0": cap0, "opened": opened, "universe": len(data), "start": dates[0], "end": dates[-1]}


def summarise(res, label):
    cv = pd.DataFrame(res["curve"], columns=["date", "eq", "inv", "n"]).set_index("date")
    cap0 = res["cap0"]
    yrs = (cv.index[-1] - cv.index[0]).days / 365.25
    final = cv["eq"].iloc[-1]
    cagr = ((final / cap0) ** (1 / yrs) - 1) * 100
    dd = ((cv["eq"] / cv["eq"].cummax()) - 1).min() * 100
    tr = pd.DataFrame(res["closed"])
    w, l = tr[tr["pl"] > 0], tr[tr["pl"] <= 0]
    pf = w["pl"].sum() / abs(l["pl"].sum()) if len(l) else float("nan")
    yr = cv["eq"].resample("YE").last()
    yr = pd.concat([pd.Series([cap0], index=[cv.index[0] - pd.Timedelta(days=1)]), yr])
    yret = (yr.pct_change().dropna() * 100).round(1)
    out = {"label": label, "universe": res["universe"], "period": f"{cv.index[0].date()} to {cv.index[-1].date()} ({yrs:.1f}y)", "capital": cap0,
           "final_equity": round(final), "total_pnl": round(final - cap0), "cagr%": round(cagr, 2), "max_dd%": round(dd, 2),
           "closed": len(tr), "win%": round(100 * len(w) / len(tr), 1), "avg_win%": round(w["pct"].mean(), 1), "avg_loss%": round(l["pct"].mean(), 1),
           "pf": round(pf, 2), "avg_hold_win_d": round(w["days"].mean()), "avg_hold_loss_d": round(l["days"].mean()), "adds/trade": round(tr["adds"].mean(), 2),
           "open_positions_now": len(res["open"]), "peak_invested": round(cv["inv"].max()), "peak_invested%": round(100 * cv["inv"].max() / cap0, 1),
           "avg_invested%": round(100 * cv["inv"].mean() / cap0, 1), "max_positions": int(cv["n"].max()), "fees_rs": round(res["fees"]),
           "missed_entries_no_cash": res["missed"]["entry"], "missed_adds_no_cash": res["missed"]["add"], "yearly_%": {str(k.year): v for k, v in yret.items()}}
    return out, cv, tr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--strategy", choices=["dhan", "az"], required=True)
    ap.add_argument("--start", default="2017-11-01")
    ap.add_argument("--slip", type=float, default=0.001)
    ap.add_argument("--out", default="")
    ap.add_argument("--cash-rate", type=float, default=0.0, help="annual yield earned by idle cash (liquid ETF), e.g. 0.06")
    ap.add_argument("--all-days", action="store_true", help="az: order every flip in the 3-day window, not only the freshest day")
    a = ap.parse_args()
    data_dir = Path(a.data)
    man = pd.read_csv(data_dir / "manifest.csv")
    valid = man[man["status"] == "VALIDATED"]["symbol"].tolist()
    if a.strategy == "az":
        uni = json.loads((ROOT / "zerodha-live" / "data" / "fno_universe.json").read_text())["symbols"]
        ex = set(json.loads((ROOT / "zerodha-live" / "data" / "excluded_symbols.json").read_text())["symbols"])
        want = {s + ".NS" for s in uni if s not in ex}
        symbols = [s for s in valid if s in want]
    else:
        symbols = valid
    res = run(a.strategy, data_dir, symbols, pd.Timestamp(a.start), a.slip, fresh_only=not a.all_days, cash_rate=a.cash_rate)
    out, cv, tr = summarise(res, f"{a.strategy} start={a.start} slip={a.slip} cash={a.cash_rate}{' all-days' if a.all_days else ''}")
    print(json.dumps(out, indent=1, default=str))
    if a.out:
        cv.to_csv(a.out + "_equity.csv")
        tr.to_csv(a.out + "_trades.csv", index=False)


if __name__ == "__main__":
    main()
