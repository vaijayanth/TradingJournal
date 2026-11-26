"""ND insight FACTS: every number the daily insights box may quote, computed in code (user, 2026-11-26).

  python dhan-live/scripts/compute_insights_facts.py            # writes dhan-live/data/insights_facts.json and updates insights_history.json / option_ledger.json

The insights box (`insights.json`) is written by Claude from THIS file only: the model selects and narrates, it never computes. Each fact has a stable id
(flat key like `leak.entry.fill_rate`), so `verify_insights.py` can check that every number in the box text traces to a fact.
ND only: reads dhan-live/ files and the shared 10-year backtest trade list; imports nothing from zerodha-live/ or icici-live/ (the helpers are vendored below).

Sections (ranked by the research report, `Systematic trader insight metrics`):
  adherence   signal ledger from the git history of dhan_live_signals.json matched to the fills ledger: filled / missed / pending, slippage, delay
  leakage     fill rate, slippage and the move of missed signals since they fired
  bootstrap   live closed trades vs equal-sized samples from the post-2022 backtest pool (percentile of mean return and of win rate), with the evidence tier
  openrisk    open book: positions below -6% (add-on exposure), loss if every open position exits on its Supertrend line, sector concentration
  trend       share of holdings green, fresh signals today, own-history percentile once 10 days exist
  options     realised options P&L for the day (stock options, no Nifty index), stress grid (market and single-stock shocks), spread stop that cannot bind,
              structure-vs-colour mismatches, breakeven win rate of the 3x stop / 60% target, cumulative closed-contract ledger by structure
Evidence tiers (code-assigned, the LLM must not change them): n < 10 anecdote, 10-29 weak, >= 30 moderate.
"""
import json
import math
import re
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent          # dhan-live/
REPO = ROOT.parent
DATA = ROOT / "data"
SIG_REL = "dhan-live/dhan_live_signals.json"
POOL_CSV = REPO / "swing-backtest" / "results" / "dhan_10y_trades.csv"
IST = timezone(timedelta(hours=5, minutes=30))
MATCH_DAYS = 6                    # a signal counts as filled when the same-side fill is within this many calendar days after it


def load(p, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default


def tier(n):
    return "anecdote" if n < 10 else ("weak" if n < 30 else "moderate")


def r2(x, k=2):
    return None if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))) else round(float(x), k)


# --------------------------------------------------------------------------- adherence and leakage
def git_signal_history():
    """{market_data_date: signals dict} using the newest commit of each date (empty when the clone has no history)."""
    try:
        hashes = subprocess.run(["git", "-C", str(REPO), "log", "--format=%H", "--", SIG_REL], capture_output=True, text=True, check=True).stdout.split()
    except Exception:  # noqa: BLE001
        return {}
    by = {}
    for h in hashes:                                   # newest first
        try:
            raw = subprocess.run(["git", "-C", str(REPO), "show", f"{h}:{SIG_REL}"], capture_output=True, text=True, check=True).stdout
            d = json.loads(raw)
        except Exception:  # noqa: BLE001
            continue
        md = d.get("market_data_date")
        if md and md not in by:
            by[md] = d
    return dict(sorted(by.items()))


def signal_ledger(hist, fills, last_date):
    """One row per signal's FIRST appearance (a signal that stays listed on later days is not a new signal)."""
    first_fill = min((f["date"] for f in fills), default=None)
    prev, rows = set(), []
    for md, d in hist.items():
        cur = set()
        for kind, key, side, refk, qk in (("entry", "entries", "BUY", "close", "qty_to_buy"), ("exit", "exits", "SELL", "cmp", "qty"), ("addon", "addons", "BUY", "cmp", "qty")):
            for s in d.get(key, []):
                tag = (kind, s["symbol"]); cur.add(tag)
                if tag in prev or (first_fill and md < first_fill):
                    continue
                ref = s.get(refk)
                lim = (datetime.strptime(md, "%Y-%m-%d") + timedelta(days=MATCH_DAYS)).strftime("%Y-%m-%d")
                m = next((f for f in sorted(fills, key=lambda f: f["date"]) if f["symbol"] == s["symbol"] and f["action"] == side and md < f["date"] <= lim), None)
                row = {"date": md, "kind": kind, "symbol": s["symbol"], "side": side, "ref_price": ref, "signal_qty": s.get(qk)}
                if m:
                    slip = ((m["price"] - ref) / ref * 100) if side == "BUY" else ((ref - m["price"]) / ref * 100)
                    row.update(outcome="filled", fill_date=m["date"], fill_price=m["price"], fill_qty=m["qty"], slip_pct=r2(slip),
                               delay_days=(datetime.strptime(m["date"], "%Y-%m-%d") - datetime.strptime(md, "%Y-%m-%d")).days)
                else:
                    row["outcome"] = "pending" if md >= last_date else ("pending" if (datetime.strptime(last_date, "%Y-%m-%d") - datetime.strptime(md, "%Y-%m-%d")).days < 2 else "missed")
                rows.append(row)
        prev = cur
    return rows


def adherence_leakage(sig, hist, fills):
    last = sig["market_data_date"]
    led = signal_ledger(hist, fills, last)
    closes = load(DATA / "dh252_daily_closes.json", {}) or {}
    last_px = {h["symbol"]: h["cmp"] for h in sig.get("holds", [])}

    def move(row):
        s = row["symbol"]
        px = last_px.get(s)
        if px is None:
            c = closes.get(s) or closes.get(s + ".NS")
            if isinstance(c, dict) and c:
                px = c[sorted(c)[-1]]
        return None if px is None or not row.get("ref_price") else r2((px / row["ref_price"] - 1) * 100)

    out = {"first_ledger_date": min((r["date"] for r in led), default=None), "signals_total": len(led), "by_kind": {}, "ledger_tail": led[-15:]}
    for kind in ("entry", "exit", "addon"):
        g = [r for r in led if r["kind"] == kind]
        fl, ms, pe = [r for r in g if r["outcome"] == "filled"], [r for r in g if r["outcome"] == "missed"], [r for r in g if r["outcome"] == "pending"]
        decided = len(fl) + len(ms)
        mv = [move(r) for r in ms]
        mv = [x for x in mv if x is not None]
        out["by_kind"][kind] = {"signals": len(g), "filled": len(fl), "missed": len(ms), "pending": len(pe), "fill_rate_pct": r2(len(fl) / decided * 100, 1) if decided else None,
                                "decided_n": decided, "tier": tier(decided), "avg_slippage_pct": r2(np.mean([r["slip_pct"] for r in fl])) if fl else None,
                                "median_delay_days": r2(float(np.median([r["delay_days"] for r in fl])), 1) if fl else None,
                                "missed_symbols": [r["symbol"] for r in ms][:8], "missed_avg_move_since_signal_pct": r2(np.mean(mv)) if mv else None}
    dec = sum(v["decided_n"] for v in out["by_kind"].values()); fl = sum(v["filled"] for v in out["by_kind"].values())
    out["overall_fill_rate_pct"] = r2(fl / dec * 100, 1) if dec else None
    out["overall_decided_n"] = dec
    out["note"] = ("Signals come from the git history of the signals file; a fill is a same-side fill within %d calendar days after the signal date; slippage is positive when the fill was worse than the signal close. "
                   "A 'missed' signal can also be a fill the ledger never captured (a day the refresh did not run), so check the symbol before calling it an execution miss." % MATCH_DAYS)
    return out


# --------------------------------------------------------------------------- bootstrap vs the backtest
def bootstrap(sig, fills):
    """Live closed trades vs equal-sized samples of backtest trades that ALSO closed within the live window (a live book this young has only closed its early losers,
    so comparing with the full 10-year outcome distribution, where every trade has closed, would flag normal behaviour as decay)."""
    closed = sig.get("closed_trades", [])
    pl = np.array([c["pl_pct"] for c in closed if c.get("pl_pct") is not None], float)
    out = {"n_live_closed": int(len(pl)), "tier": tier(len(pl))}
    pool_all = pd.read_csv(POOL_CSV, parse_dates=["entry"])
    pool_all = pool_all[pool_all["entry"] >= "2022-01-01"]
    first = min((f["date"] for f in fills), default=None) or min((c["entry_date"] for c in closed), default=None)
    window = (datetime.strptime(sig["market_data_date"], "%Y-%m-%d") - datetime.strptime(first, "%Y-%m-%d")).days if first else None
    matched = pool_all[pool_all["days"] <= window]["pct"].values if window else pool_all["pct"].values
    out.update(pool_n_all=int(len(pool_all)), pool_n_matched=int(len(matched)), window_days=window,
               pool_note="post-2022 ND backtest trades (the walk-forward base case); matched pool = trades that closed within %s days, like the live ones" % window)
    if len(pl) < 3 or len(matched) < 30:
        out["note"] = "fewer than 3 closed trades (or too small a matched pool): no bootstrap"
        return out
    rng = np.random.default_rng(7)
    B = 10000
    idx = rng.integers(0, len(matched), (B, len(pl)))
    means, wins = matched[idx].mean(axis=1), (matched[idx] > 0).mean(axis=1) * 100
    lm, lw = float(pl.mean()), float((pl > 0).mean() * 100)
    pm = float((means <= lm).mean())
    out.update(live_mean_pct=r2(lm), live_win_rate_pct=r2(lw, 1), matched_pool_mean_pct=r2(matched.mean()), matched_pool_win_rate_pct=r2((matched > 0).mean() * 100, 1),
               full_pool_mean_pct=r2(pool_all["pct"].mean()), full_pool_win_rate_pct=r2((pool_all["pct"] > 0).mean() * 100, 1),
               mean_percentile=r2(pm * 100, 1), win_rate_percentile=r2((wins <= lw).mean() * 100, 1), draws=B,
               flag="below_5th_percentile" if pm < 0.05 else ("above_95th_percentile" if pm > 0.95 else "within_normal_range"))
    op = [h["pl_pct"] for h in sig.get("holds", []) if h.get("pl_pct") is not None]
    if op:
        out["open_book"] = {"n": len(op), "in_profit_pct": r2(np.mean(np.array(op) > 0) * 100, 1), "avg_gain_pct": r2(np.mean([x for x in op if x > 0])) if any(x > 0 for x in op) else None,
                            "avg_loss_pct": r2(np.mean([x for x in op if x <= 0])) if any(x <= 0 for x in op) else None}
    out["note"] = "Matched comparison removes the young-book bias but still ignores that live trades are early exits only; bootstrap measures sampling noise only."
    return out


# --------------------------------------------------------------------------- open-book risk
def open_risk(sig):
    h = sig.get("holds", [])
    inv = sum(x["avg_cost"] * x["qty"] for x in h)
    below = [x for x in h if x["pl_pct"] is not None and x["pl_pct"] <= -6]
    sec = {}
    for x in h:
        sec[x.get("sector") or "?"] = sec.get(x.get("sector") or "?", 0) + x["avg_cost"] * x["qty"]
    top = sorted(sec.items(), key=lambda kv: -kv[1])[:3]
    prj = load(DATA / "projection.json", {}) or {}
    so = prj.get("stop_out") or {}
    return {"open_positions": len(h), "invested_rs": r2(inv, 0), "below_minus6_count": len(below), "below_minus6_invested_rs": r2(sum(x["avg_cost"] * x["qty"] for x in below), 0),
            "below_minus6_share_pct": r2(sum(x["avg_cost"] * x["qty"] for x in below) / inv * 100, 1) if inv else None, "below_minus6_symbols": [x["symbol"] for x in below][:8],
            "worst_positions": [{"symbol": x["symbol"], "pl_pct": r2(x["pl_pct"], 1)} for x in sorted(h, key=lambda x: x["pl_pct"])[:5]],
            "pnl_if_all_hit_line_rs": so.get("pnl_if_all_hit_line"), "extra_loss_if_all_hit_line_rs": so.get("extra_loss_if_all_hit_line"),
            "top_sectors": [{"sector": k, "share_pct": r2(v / inv * 100, 1)} for k, v in top] if inv else [],
            "note": "Stop-out figure = projection.json: loss if every open position exited on its own Supertrend line today."}


# --------------------------------------------------------------------------- trend supply
def trend(sig):
    h = sig.get("holds", [])
    green = sum(1 for x in h if x.get("supertrend_color") == "green")
    t = {"holds": len(h), "green": green, "green_share_pct": r2(green / len(h) * 100, 1) if h else None, "entries_today": len(sig.get("entries", [])),
         "exits_today": len(sig.get("exits", [])), "addons_today": len(sig.get("addons", []))}
    p = DATA / "insights_history.json"
    hist = load(p, {}) or {}
    hist[sig["market_data_date"]] = {k: t[k] for k in ("green_share_pct", "entries_today", "exits_today", "addons_today")}
    p.write_text(json.dumps(dict(sorted(hist.items())), indent=0))
    if len(hist) >= 10:
        for k in ("green_share_pct", "entries_today", "exits_today"):
            vals = [v[k] for v in hist.values() if v.get(k) is not None]
            t[k + "_own_percentile"] = r2((np.array(vals) <= t[k]).mean() * 100, 0)
    t["history_days"] = len(hist)
    t["note"] = "ND universe is the 1,495-stock backtester set, so breadth here is the share of YOUR holdings that are green plus today's signal counts; percentiles appear after 10 days of own history."
    return t


# --------------------------------------------------------------------------- options (vendored Black-Scholes)
def _ncdf(x):
    return 0.5 * math.erfc(-x / math.sqrt(2))


def bs_price(typ, S, K, T, r, sig):
    if T <= 0 or sig <= 0:
        return max(0.0, (S - K) if typ == "CE" else (K - S))
    d1 = (math.log(S / K) + (r + 0.5 * sig * sig) * T) / (sig * math.sqrt(T)); d2 = d1 - sig * math.sqrt(T)
    return S * _ncdf(d1) - K * math.exp(-r * T) * _ncdf(d2) if typ == "CE" else K * math.exp(-r * T) * _ncdf(-d2) - S * _ncdf(-d1)


def implied_vol(typ, S, K, T, r, px):
    intrinsic = max(0.0, (S - K) if typ == "CE" else (K - S))
    if px <= intrinsic + 0.01 or T <= 0:
        return None
    lo, hi = 0.01, 3.0
    if bs_price(typ, S, K, T, r, hi) < px:
        return None
    for _ in range(60):
        mid = (lo + hi) / 2
        if bs_price(typ, S, K, T, r, mid) > px:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def parse_closed_from_positions():
    """Closed option contracts (net quantity 0) from the saved raw Dhan positions text: [{contract, pnl, buy, sell, qty}]."""
    p = DATA / "cc_raw" / "positions.txt"
    if not p.exists():
        return []
    txt = p.read_text(encoding="utf-8")
    out = []
    for m in re.finditer(r"^(\S+)-(\w{3}\d{4})-(\d+(?:\.\d+)?)-(CE|PE) \[\w+\] CLOSED\n\s+Net: 0 \| Buy (\d+) @ ₹([\d,\.]+) \| Sell (\d+) @ ₹([\d,\.]+)\n\s+P&L: [▲▼] ₹([\d,\.]+) \(Realized ₹([\-\d,\.]+)\)", txt, re.M):
        sym, expm, k, typ, bq, bp, sq, sp, _, real = m.groups()
        out.append({"contract": f"{sym}-{expm}-{k}-{typ}", "symbol": sym, "type": typ, "strike": float(k), "qty": int(bq), "buy_price": float(bp.replace(",", "")),
                    "sell_price": float(sp.replace(",", "")), "pnl_rs": float(real.replace(",", ""))})
    return out


def _by_stock(closed):
    d = {}
    for c in closed:
        d[c["symbol"]] = d.get(c["symbol"], 0.0) + c["pnl_rs"]
    return d


def options(sig, cc):
    stocks = cc.get("stocks", {})
    stocks = stocks if isinstance(stocks, dict) else {x["symbol"]: x for x in stocks}
    rules = cc.get("rules", {}) or {}
    r = float(rules.get("risk_free_rate", 0.065)); today = date.today()
    legs = []
    for s, v in stocks.items():
        for lg in v.get("legs") or []:
            legs.append({**lg, "symbol": s, "spot": v.get("spot"), "colour": v.get("st_colour") or v.get("colour"), "stock_iv": (v.get("iv") or 0) / 100.0 or None})
    out = {"open_legs": len(legs), "short_legs": sum(1 for l in legs if l["side"] == "SHORT"), "long_legs": sum(1 for l in legs if l["side"] == "LONG")}
    # ---- realised today (stock options only: the ND book has no index options) and the cumulative ledger
    closed = parse_closed_from_positions()
    out["realised_today"] = {"contracts_closed": len(closed), "pnl_rs": r2(sum(c["pnl_rs"] for c in closed), 0), "contracts": [{"contract": c["contract"], "pnl_rs": r2(c["pnl_rs"], 0)} for c in sorted(closed, key=lambda c: c["pnl_rs"])],
                             "by_stock": {k: r2(v, 0) for k, v in sorted(_by_stock(closed).items(), key=lambda kv: kv[1])},
                             "note": "Stock options only (Nifty index options are outside the insights by decision), gross of charges."}
    ledger_p = DATA / "option_ledger.json"
    led = load(ledger_p, {"entries": []}) or {"entries": []}
    seen = {(e["date"], e["contract"]) for e in led["entries"]}
    for c in closed:
        k = (sig["market_data_date"], c["contract"])
        if k not in seen:
            colour = (stocks.get(c["symbol"]) or {}).get("st_colour")
            led["entries"].append({"date": k[0], "contract": c["contract"], "symbol": c["symbol"], "type": c["type"], "pnl_rs": c["pnl_rs"], "colour_at_close": colour})
    ledger_p.write_text(json.dumps(led, indent=0))
    ent = led["entries"]
    out["ledger"] = {"closed_contracts": len(ent), "total_pnl_rs": r2(sum(e["pnl_rs"] for e in ent), 0), "tier": tier(len(ent)),
                     "puts": {"n": sum(1 for e in ent if e["type"] == "PE"), "pnl_rs": r2(sum(e["pnl_rs"] for e in ent if e["type"] == "PE"), 0)},
                     "calls": {"n": sum(1 for e in ent if e["type"] == "CE"), "pnl_rs": r2(sum(e["pnl_rs"] for e in ent if e["type"] == "CE"), 0)},
                     "first_date": min((e["date"] for e in ent), default=None),
                     "note": "Ledger of closed contracts accumulates from the first run of this script; no earlier history is stored by the brokers. Put-vs-call comparison needs about 30 closed contracts per side."}
    # ---- stress grid: full Black-Scholes repricing, implied vol solved per leg from its live price, spots shocked together (beta 1)
    base = []
    for l in legs:
        S, K = l.get("spot"), l["strike"]
        if not S or not l.get("ltp"):
            base.append(None); continue
        T = max((datetime.strptime(l["expiry"], "%Y-%m-%d").date() - today).days, 1) / 365.0
        iv = implied_vol(l["type"], S, K, T, r, l["ltp"]) or l.get("stock_iv") or 0.30
        base.append((S, K, T, iv, bs_price(l["type"], S, K, T, r, iv)))

    def pnl(shock_fn, iv_mult=1.0, only=None):
        tot = 0.0
        for l, b in zip(legs, base):
            if b is None or (only and l["symbol"] != only):
                continue
            S, K, T, iv, p0 = b
            p1 = bs_price(l["type"], S * (1 + shock_fn(l["symbol"])), K, T, r, iv * iv_mult)
            sign = -1 if l["side"] == "SHORT" else 1
            tot += sign * l["qty"] * (p1 - p0)
        return tot
    grid = {}
    for sh in (-8, -5, -3, 3, 5, 10):
        grid[f"market_{sh:+d}pct"] = r2(pnl(lambda s, sh=sh: sh / 100.0), 0)
    grid["market_-5pct_iv_x1.25"] = r2(pnl(lambda s: -0.05, 1.25), 0)
    grid["market_-8pct_iv_x1.5"] = r2(pnl(lambda s: -0.08, 1.5), 0)
    worst = []
    for s in {l["symbol"] for l in legs}:
        down = pnl(lambda x, s=s: -0.20 if x == s else 0.0, only=s)
        up = pnl(lambda x, s=s: 0.20 if x == s else 0.0, only=s)
        worst.append((min(down, up), s, "down 20%" if down < up else "up 20%"))
    worst.sort()
    cap = (sig.get("capital_base") or {}).get("initial_capital")
    out["stress"] = {"capital_base_rs": cap, "grid_pct_of_capital": {k: r2(v / cap * 100, 2) for k, v in grid.items() if v is not None} if cap else None, "grid_pnl_rs": grid, "single_stock_gap_worst": [{"symbol": s, "move": m, "pnl_rs": r2(v, 0)} for v, s, m in worst[:3]],
                     "method": "Black-Scholes repricing of every open leg, implied vol solved from the live option price (fallback stock IV or 30%%), all underlyings shocked together (beta 1), expiry unchanged, risk-free %.3f." % r,
                     "limits": "Beta 1 is an assumption; a gap through a stop fills at the gap price, not at 3x."}
    # ---- defined-risk put side, naked calls, stops that cannot bind, structure vs colour
    by = {}
    for l in legs:
        by.setdefault((l["symbol"], l["expiry"]), []).append(l)
    put_max, naked_calls, nobind, mism = 0.0, 0, [], []
    for (s, e), g in by.items():
        sp = [x for x in g if x["type"] == "PE" and x["side"] == "SHORT"]; lp = [x for x in g if x["type"] == "PE" and x["side"] == "LONG"]
        avg = lambda x: x.get("sell_avg") if x["side"] == "SHORT" and x.get("sell_avg") else (x.get("buy_avg") if x["side"] == "LONG" and x.get("buy_avg") else x.get("avg", 0))
        if sp:
            credit = sum(avg(x) * x["qty"] for x in sp) - sum(avg(x) * x["qty"] for x in lp)
            put_max += sum(x["strike"] * x["qty"] for x in sp) - sum(x["strike"] * x["qty"] for x in lp) - credit
            if len(sp) == 1 and len(lp) == 1 and sp[0]["qty"] == lp[0]["qty"]:
                cps = avg(sp[0]) - avg(lp[0]); width = sp[0]["strike"] - lp[0]["strike"]
                if width > 0 and 3 * cps >= width:
                    nobind.append({"symbol": s, "width": width, "credit": r2(cps), "qty": sp[0]["qty"]})
        sc = [x for x in g if x["type"] == "CE" and x["side"] == "SHORT"]; lc = [x for x in g if x["type"] == "CE" and x["side"] == "LONG"]
        if sc and sum(x["qty"] for x in lc) < sum(x["qty"] for x in sc):
            naked_calls += 1
        colour = g[0].get("colour")
        if colour == "red" and sp:
            mism.append({"symbol": s, "colour": colour, "structure": "short put against a red stock", "pnl_rs": r2(sum(x.get("pnl_rs", 0) for x in g if x["type"] == "PE"), 0)})
        if colour == "green" and sc:
            mism.append({"symbol": s, "colour": colour, "structure": "short call against a green stock", "pnl_rs": r2(sum(x.get("pnl_rs", 0) for x in g if x["type"] == "CE"), 0)})
    out["defined_risk"] = {"put_side_max_loss_if_stocks_to_zero_rs": r2(put_max, 0), "naked_call_stocks": naked_calls, "spreads_where_3x_stop_cannot_bind": nobind[:6], "spreads_where_3x_stop_cannot_bind_count": len(nobind),
                           "note": "Put-side max loss = sum(short strikes x qty) - sum(long strikes x qty) - net credit, the loss if every stock went to zero (an upper bound, not a forecast). A spread's 3x stop cannot bind when 3 x credit >= width."}
    out["structure_vs_colour"] = {"mismatches": mism, "count": len(mism), "pnl_rs": r2(sum(m["pnl_rs"] for m in mism), 0), "rule": "put spread on green, short call on red"}
    m_, d_ = float(rules.get("stop_premium_multiple", 3)), float(rules.get("profit_exit_decay_pct", 60)) / 100.0
    out["breakeven_win_rate_pct"] = r2((m_ - 1) / ((m_ - 1) + d_) * 100, 1)
    out["breakeven_note"] = "Loss at the stop = (multiple - 1) x credit, gain at the target = decay x credit, before gaps, slippage and costs."
    return out


def main():
    sig = load(ROOT / "dhan_live_signals.json")
    cc = load(ROOT / "covered_call_signals.json", {}) or {}
    fills = (load(DATA / "dh252_trade_log.json", {}) or {}).get("fills", [])
    facts = {"broker": "ND", "generated_at": datetime.now(IST).isoformat(timespec="seconds"), "as_of": sig["market_data_date"], "scope": "ND swing shares and ND stock options; Nifty index options are outside by decision"}
    for name, fn in (("adherence_leakage", lambda: adherence_leakage(sig, git_signal_history(), fills)), ("bootstrap", lambda: bootstrap(sig, fills)), ("openrisk", lambda: open_risk(sig)),
                     ("trend", lambda: trend(sig)), ("options", lambda: options(sig, cc))):
        try:
            facts[name] = fn()
        except Exception as e:  # noqa: BLE001
            facts[name] = {"error": f"{type(e).__name__}: {e}"}
            print(f"WARNING {name}: {facts[name]['error']}", file=sys.stderr)
    try:
        av = pd.read_csv(REPO / "swing-backtest" / "results" / "addon_variants.csv").set_index("variant")
        facts["edge_tests"] = {"addon_nd_backtest": {"tested_on": "ND universe, 10 years (AZ and the investment-share averaging are untested)", "cagr_without_addons_pct": r2(av.loc["trig:off", "cagr%"]), "cagr_live_rule_pct": r2(av.loc["trig:-6", "cagr%"]),
                                                      "max_dd_without_addons_pct": r2(av.loc["trig:off", "max_dd%"]), "max_dd_live_rule_pct": r2(av.loc["trig:-6", "max_dd%"]),
                                                      "max_dd_doubling_pct": r2(av.loc["frac:1.0", "max_dd%"]), "pf_without_addons": r2(av.loc["trig:off", "pf"]), "pf_doubling": r2(av.loc["frac:1.0", "pf"])}}
    except Exception as e:  # noqa: BLE001
        facts["edge_tests"] = {"error": f"{type(e).__name__}: {e}"}
    facts["backtest_reference"] = {"cagr_pct": 28.0, "max_drawdown_pct": -15.4, "profit_factor": 2.01, "win_rate_pct": 41.0, "slippage_assumption_pct": 0.1, "avg_win_pct": 33.1, "avg_loss_pct": -9.0, "source": "CLAUDE.md backtest reference (10 years, 6% idle cash, costs + 0.1% slippage; walk-forward since 2022 about 20-23% CAGR)"}
    (DATA / "insights_facts.json").write_text(json.dumps(facts, indent=1, default=str))
    a, b, o = facts["adherence_leakage"], facts["bootstrap"], facts["options"]
    print(f"insights facts ND as of {facts['as_of']}: signals {a.get('signals_total')} (fill rate {a.get('overall_fill_rate_pct')}% of {a.get('overall_decided_n')} decided), "
          f"bootstrap n={b.get('n_live_closed')} mean percentile {b.get('mean_percentile')}, realised options today Rs{(o.get('realised_today') or {}).get('pnl_rs')}, "
          f"stress -5% Rs{((o.get('stress') or {}).get('grid_pnl_rs') or {}).get('market_-5pct')}")


if __name__ == "__main__":
    main()
