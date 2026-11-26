"""12-month equity projection for the ND book (user, 2026-11-26). Information only: it never changes a rule, signal or order.

  python dhan-live/scripts/compute_projection.py [--runs 1500]      -> dhan-live/data/projection.json (read by the Performance page)

Method (a trade-level Monte Carlo):
  - start point = today's P&L from dhan_live_signals.json (realised + unrealised);
  - every OPEN position gets an outcome over its remaining life, drawn from the 10-year ND backtest trades (swing-backtest/results/dhan_10y_trades.csv),
    with the loss from today's mark capped at the distance to its own Supertrend(10,3) line (fetched from Yahoo; red or missing lines are not capped);
  - NEW entries arrive at the backtest's yearly rate (Poisson), each sized by the live ladder (rules.json: base + increment per 100 closed trades, doubled while the
    live tier is doubled), outcome = a random backtest trade (% on cost, holding days), marked linearly over its hold;
  - two trade pools: all 10 years and 2022 onward (the post-2022 regime is the conservative base case).
Bands: P10 / median / P90 of the simulated total P&L at 13 monthly points. Caveats written into the file: trades are drawn independently (real losses cluster by regime, so P10 is
a normal bad year, not a floor), survivorship bias in the backtest, no tax, the ladder doubling is held at today's state.
Also reports the stop-out floor: today's P&L if every open position closed on its Supertrend line.
ND and AZ keep separate copies of this script (zerodha-live/scripts/compute_projection.py); nothing is shared.
"""
import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent
DATA = ROOT / "data"
SIGNALS = ROOT / "dhan_live_signals.json"
TRADES = REPO / "swing-backtest" / "results" / "dhan_10y_trades.csv"
OUT = DATA / "projection.json"
H = 252
LADDER_TXT = "closed"
GRID = [0, 21, 42, 63, 84, 105, 126, 147, 168, 189, 210, 231, 252]
IST = timezone(timedelta(hours=5, minutes=30))


def supertrend_lower(highs, lows, closes, period=10, mult=3.0):
    """Supertrend(10,3) as in the backtester: returns (direction of the last bar, final lower band of the last bar)."""
    n = len(closes)
    if n <= period:
        return None, None
    tr = [highs[0] - lows[0]] + [max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])) for i in range(1, n)]
    atr = [None] * n
    atr[period - 1] = sum(tr[:period]) / period
    for i in range(period, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    s = period - 1
    mid = (highs[s] + lows[s]) / 2
    fu, fl = mid + mult * atr[s], mid - mult * atr[s]
    d = "down" if closes[s] <= fu else "up"
    for i in range(s + 1, n):
        mid = (highs[i] + lows[i]) / 2
        bu, bl = mid + mult * atr[i], mid - mult * atr[i]
        fu = bu if (bu < fu or closes[i - 1] > fu) else fu
        fl = bl if (bl > fl or closes[i - 1] < fl) else fl
        d = ("up" if closes[i] > fu else "down") if d == "down" else ("down" if closes[i] < fl else "up")
    return d, fl


def stop_distances(holds):
    """{symbol: (mark value, fractional distance from the mark down to the Supertrend line)} for positions with a green line; others are uncapped."""
    try:
        import yfinance as yf
    except Exception:  # noqa: BLE001
        return {}
    syms = sorted({h["symbol"] for h in holds})
    out = {}
    try:
        df = yf.download([s + ".NS" for s in syms], period="1y", interval="1d", auto_adjust=False, progress=False, group_by="ticker", threads=True)
    except Exception:  # noqa: BLE001
        return {}
    for h in holds:
        s = h["symbol"]
        try:
            x = df[s + ".NS"].dropna(subset=["Close"])
            d, fl = supertrend_lower(x["High"].tolist(), x["Low"].tolist(), x["Close"].tolist())
        except Exception:  # noqa: BLE001
            continue
        if d == "up" and fl and h["cmp"] > 0:
            out[s] = max(0.0, (h["cmp"] - fl) / h["cmp"])
    return out


def tier_fn(rules, doubled):
    base, inc, per = rules["base_position_rs"], rules["position_increment_rs"], rules["position_increment_trades"]
    mult = 2 if doubled else 1
    return lambda closed, openn: (base + inc * (closed // per)) * mult   # ND: the ladder steps on CLOSED trades


def simulate(rng, pct, days, rate, runs, n_open0, mark_i, dist_i, closed0, tier, pnl0, cap):
    """Cash-limited like the backtest: a new entry is skipped when the invested capital plus its size would exceed `cap` (base capital + P&L so far)."""
    import heapq
    res = np.zeros((runs, len(GRID)))
    last_tier, n_new, deployed, skipped, peak = (np.zeros(runs) for _ in range(5))
    grid = np.array(GRID, dtype=float)
    for r in range(runs):
        i0 = rng.integers(0, len(pct), n_open0)
        ex_old = np.maximum(1, days[i0] // 2).astype(float)
        n = rng.poisson(rate * H)
        ed = np.sort(rng.integers(0, H, n)).astype(float)
        i1 = rng.integers(0, len(pct), n)
        heap = [(float(ex_old[j]), float(mark_i[j])) for j in range(n_open0)]
        heapq.heapify(heap)
        invested, closed, openn, pk = float(mark_i.sum()), closed0, n_open0, float(mark_i.sum())
        acc_t, acc_c, acc_l, acc_p, sk, lt = [], [], [], [], 0, tier(closed0, n_open0)
        for k in range(n):
            t = ed[k]
            while heap and heap[0][0] <= t:
                _, c = heapq.heappop(heap); invested -= c; closed += 1; openn -= 1
            sz = float(tier(closed, openn))
            if invested + sz > cap:
                sk += 1
                continue
            life = float(days[i1[k]])
            heapq.heappush(heap, (t + life, sz)); invested += sz; openn += 1; pk = max(pk, invested); lt = sz
            acc_t.append(t); acc_c.append(sz); acc_l.append(life); acc_p.append(pct[i1[k]])
        ent = np.concatenate([np.zeros(n_open0), np.array(acc_t)])
        life = np.concatenate([ex_old, np.array(acc_l)])
        cost = np.concatenate([mark_i, np.array(acc_c)])
        pp = np.concatenate([np.maximum(pct[i0] * 0.5, -100.0 * dist_i), np.array(acc_p)]) / 100.0
        frac = np.clip((grid[None, :] - ent[:, None]) / life[:, None], 0, 1)
        res[r] = pnl0 + (cost[:, None] * pp[:, None] * frac).sum(axis=0)
        last_tier[r], n_new[r], deployed[r], skipped[r], peak[r] = lt, len(acc_t), float(np.sum(acc_c)), sk, pk
    return res, last_tier, n_new, deployed, skipped, peak


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=1500)
    a = ap.parse_args()
    sig = json.loads(SIGNALS.read_text(encoding="utf-8"))
    rules = json.loads((DATA / "rules.json").read_text(encoding="utf-8"))
    holds = sig["holds"]
    eq = sig["equity_curve"][-1]
    sz = sig["sizing"]
    base = sig["capital_base"]["initial_capital"]
    pnl0 = float(eq["pnl"])
    LADDER_BASIS = "closed trades" if LADDER_TXT == "closed" else "open + closed trades"
    TRADES_COUNTED = int(sz["closed_trades_count"]) if LADDER_BASIS == "closed trades" else int(sz["closed_trades_count"]) + len(holds)
    dist = stop_distances(holds)
    mark_i = np.array([h["qty"] * h["cmp"] for h in holds], dtype=float)
    dist_i = np.array([dist.get(h["symbol"], 1.0) for h in holds], dtype=float)      # no green line = uncapped (distance 100%)
    capped = int(sum(1 for h in holds if h["symbol"] in dist))
    stop_value = float(sum(m * (1 - d) for m, d in zip(mark_i, dist_i) if d < 1.0))
    floor_extra = float(sum(-m * d for m, d in zip(mark_i, dist_i) if d < 1.0))        # further loss from the mark if every capped position closes on its line
    tr = pd.read_csv(TRADES, parse_dates=["entry"])
    tier = tier_fn(rules, bool(sz.get("doubled")))
    rng = np.random.default_rng(11)
    scenarios = {}
    start = datetime.strptime(sig["market_data_date"], "%Y-%m-%d")
    dates = [(pd.Timestamp(start) + pd.tseries.offsets.BDay(g)).strftime("%Y-%m-%d") for g in GRID]
    for key, label, pool in (("since_2022", "Trades from 2022 onward (base case)", tr[tr["entry"] >= "2022-01-01"]), ("all_10y", "Trades from all 10 years", tr)):
        yrs = (pool["entry"].max() - pool["entry"].min()).days / 365.25
        rate = len(pool) / yrs / 252.0
        r, lt, nn, dep, skp, pkv = simulate(rng, pool["pct"].values, np.maximum(pool["days"].values, 1), rate, a.runs, len(holds), mark_i, dist_i, int(sz["closed_trades_count"]), tier, pnl0, base + max(pnl0, 0.0))
        p10, p50, p90 = (np.percentile(r, q, axis=0) for q in (10, 50, 90))
        scenarios[key] = {"label": label, "entries_per_year": round(rate * 252), "p10": [round(float(x)) for x in p10], "p50": [round(float(x)) for x in p50], "p90": [round(float(x)) for x in p90],
                          "prob_loss_12m_pct": round(float((r[:, -1] < 0).mean() * 100), 1),
                          "new_trades_12m_median": int(np.median(nn)), "new_capital_12m_median": round(float(np.median(dep))), "tier_at_12m_median": round(float(np.median(lt))), "entries_skipped_no_cash_12m_median": int(np.median(skp)), "peak_invested_median": round(float(np.median(pkv))), "peak_invested_pct_of_base": round(float(np.median(pkv)) / base * 100)}
    out = {"generated_at": datetime.now(IST).isoformat(timespec="seconds"), "market_data_date": sig["market_data_date"], "workspace": "ND", "runs": a.runs, "dates": dates,
           "base": base, "pnl_now": round(pnl0), "realised_now": round(float(eq["realised"])), "open_positions": len(holds), "positions_with_stop_line": capped,
           "stop_out": {"extra_loss_if_all_hit_line": round(floor_extra), "pnl_if_all_hit_line": round(pnl0 + floor_extra)},
           "tier_now": sz.get("effective_tier_rs"),
           "sizing": {"base_tier_rs": rules["base_position_rs"], "increment_rs": rules["position_increment_rs"], "increment_per_trades": rules["position_increment_trades"],
                      "ladder_basis": LADDER_BASIS, "doubled": bool(sz.get("doubled")), "effective_tier_rs": sz.get("effective_tier_rs"), "closed_trades_now": int(sz["closed_trades_count"]),
                      "trades_counted_now": TRADES_COUNTED, "next_step_at_trades": (TRADES_COUNTED // rules["position_increment_trades"] + 1) * rules["position_increment_trades"],
                      "invested_now": round(float(eq["invested"])), "avg_position_now": round(float(eq["invested"]) / max(len(holds), 1))},
           "scenarios": scenarios,
           "caveats": ["New entries are skipped when the invested capital would exceed the base capital plus P&L (cash-limited, like the backtest); idle cash earns nothing here.", "Trades are drawn independently; real losses cluster by market regime, so P10 is a normal bad year, not a floor.", "The backtest has survivorship bias; no tax is modelled.",
                       "The first 3 to 6 months can stay flat: losers are cut early, winners are held about 100 days, and the position size steps up only per 100 closed trades.",
                       "Existing positions use the distance to their own Supertrend line as the loss cap; a gap through the line loses more."]}
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    s = scenarios["since_2022"]
    print(f"ND projection ({a.runs} runs): 12-month total P&L P10 {s['p10'][-1]:,} / median {s['p50'][-1]:,} / P90 {s['p90'][-1]:,}; stop-out floor {out['stop_out']['pnl_if_all_hit_line']:,}; {capped}/{len(holds)} positions capped")


if __name__ == "__main__":
    main()
