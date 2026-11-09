"""Guardrails for the Zerodha / AZ (Nifty F&O Supertrend + covered call) pipeline (own copy; shares no code with the Dhan one): checks and balances that run after every
refresh and before any order ticket is built. Writes zerodha-live/data/guardrails.json.

Levels
  BLOCK : an order for the named stock (symbol set) - or every order (symbol None) - must NOT be placed until it is fixed.
  WARN  : proceed only with the user's eyes on it (shown on the pages and in the order skills' tickets).
  INFO  : context.

Groups (ids)
  F  freshness     F1 market data lag, F2 holdings age, F3 signals older than holdings, F4 order snapshot age,
                   F5 cross-check (independent Yahoo recompute) disagrees with most signals = suspect prices / partial same-day bar
  I  integrity     I1 NaN/inf/None numerics, I2 position rows sane, I3 holdings vs fill ledger (settlement lag vs real drift),
                   I4 a stock in two signal lists, I5 hedge / out-of-scope stock in a signal list, I6 fills sanity,
                   I7 bought in the last days but not yet in holdings -> never re-enter / add
  S  signal logic  S1 exits are red, S2 add-ons are green + in loss + cooled down, S3 entries are green + at the high / fresh
                   flip + not held, S4 min-1-share overspend, S5 signal-count spikes (mass-exit = suspect data)
  C  capital       C1 deployed vs base, C2 single-stock / sector concentration, C3 planned + pending buys vs base
  O  orders        O1 pending SELL > held (oversell), O2 duplicate pending orders, O3 pending order with no signal
  P  options       P1 expiry week, P2 no lot size, P3 exit alerts open, P4 short call not covered by shares
  X  separation    X1 no code shared with the Dhan (ND) workspace
  H  halt          H1 data/trading_halt.json {"halt": true} blocks everything (the kill switch)

Usage: python zerodha-live/scripts/guardrails.py [--strict]   (--strict: exit code 2 when any BLOCK exists)
evaluate(ctx, today) is a pure function (used by test_guardrails.py).
"""
import argparse
import json
import math
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "guardrails.json"
BROKER = {"id": "zerodha", "label": "AZ", "other_dir": "dhan-live", "base": 3_000_000, "tier_key": "effective_tier_rs"}
DEFAULTS = {
    "max_market_lag_warn_days": 1, "max_market_lag_block_days": 3, "max_holdings_age_warn_days": 1, "max_holdings_age_block_days": 3,
    "settlement_window_days": 3, "crosscheck_block_ratio": 0.25, "crosscheck_min_signals": 4, "pl_tolerance_pct": 0.05, "fill_price_dev_warn_pct": 25,
    "max_entries_warn": 60, "mass_exit_min": 5, "mass_exit_pct_of_positions": 20, "overspend_x_tier": 3,
    "single_stock_warn_pct": 20, "sector_warn_pct": 40, "deployed_warn_pct_of_base": 100, "pending_buy_warn_pct_of_base": 25,
    "expiry_week_days": 5, "add_trigger_pct": 0.0, "add_cooldown_days": 7, "entry_max_pct_below_high": 0.5,
    "require_high": False, "entry_window_days": 3,   # AZ entry = Supertrend flipped to green within 3 trading days (no 52-week-high rule)
}
IST = timezone(timedelta(hours=5, minutes=30))


# ---------------- helpers ----------------
def f(level, gid, msg, symbol=None):
    return {"id": gid, "level": level, "symbol": symbol, "msg": msg}


def bdays_between(a, b):
    """Business days (Mon-Fri) from date a to date b, 0 if b <= a."""
    n, d = 0, a
    while d < b:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


def expected_session(now):
    """Latest session whose closing data should already be published (backtester posts ~16:00 IST; allow until 16:30)."""
    d = now.date()
    if d.weekday() < 5 and (now.hour, now.minute) >= (16, 30):
        return d
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def to_date(s):
    return datetime.strptime(str(s)[:10], "%Y-%m-%d").date() if s else None


def walk_bad_numbers(o, path=""):
    out = []
    if isinstance(o, dict):
        for k, v in o.items():
            out += walk_bad_numbers(v, f"{path}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o[:5000]):
            out += walk_bad_numbers(v, f"{path}[{i}]")
    elif isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        out.append(path)
    return out


# ---------------- the checks ----------------
def evaluate(ctx, now):
    cfg = {**DEFAULTS, **ctx.get("config", {})}
    sig, hold, orders, fills = ctx["signals"], ctx["holdings"], ctx.get("orders") or [], ctx.get("fills")
    base = (sig.get("capital_base") or {}).get("initial_capital") or BROKER["base"]
    tier = (sig.get("sizing") or {}).get(BROKER["tier_key"]) or (sig.get("sizing") or {}).get("effective_tier_rs") or 0
    out = []
    held = {h["symbol"]: h for h in hold}
    hedge = set(sig.get("option_hedge_portfolio", []))
    forbidden = hedge | set(ctx.get("excluded", []))
    exp = expected_session(now)

    # H1 kill switch
    halt = ctx.get("halt") or {}
    if halt.get("halt"):
        out.append(f("BLOCK", "H1", f"TRADING HALT is on: {halt.get('reason') or 'no reason given'} (data/trading_halt.json)"))

    # F freshness
    md = to_date(sig.get("market_data_date"))
    if md is None:
        out.append(f("BLOCK", "F1", "signals have no market_data_date"))
    else:
        lag = bdays_between(md, exp)
        if lag >= cfg["max_market_lag_block_days"]:
            out.append(f("BLOCK", "F1", f"market data {md} is {lag} sessions behind the last published session ({exp}) - run the refresh"))
        elif lag >= cfg["max_market_lag_warn_days"]:
            out.append(f("WARN", "F1", f"market data {md} is {lag} session behind the last published session ({exp})"))
    hf = to_date(sig.get("holdings_fetched_at") or ctx.get("holdings_fetched_at"))
    if hf is None:
        out.append(f("WARN", "F2", "holdings snapshot has no fetched_at"))
    else:
        age = bdays_between(hf, exp)
        if age >= cfg["max_holdings_age_block_days"]:
            out.append(f("BLOCK", "F2", f"holdings were pulled {hf}, {age} sessions ago - positions and P&L may be wrong"))
        elif age >= cfg["max_holdings_age_warn_days"]:
            out.append(f("WARN", "F2", f"holdings were pulled {hf}, {age} session ago"))
    gen, hfa = ctx.get("signals_generated_at"), ctx.get("holdings_fetched_at")
    try:
        if gen and hfa and datetime.fromisoformat(str(gen)) < datetime.fromisoformat(str(hfa)):
            out.append(f("WARN", "F3", "signals were built before the latest holdings pull - re-run the refresh"))
    except ValueError:
        pass
    of = to_date(ctx.get("orders_fetched_at"))
    if orders and of and hf and of < hf:
        out.append(f("WARN", "F4", f"order snapshot ({of}) is older than the holdings ({hf}): order status may be stale"))

    # F5 independent cross-check
    xc = ctx.get("crosscheck")
    if xc is None:
        out.append(f("WARN", "F5", "no signal cross-check result: signals have not been verified against complete Yahoo history"))
    else:
        res = xc.get("results", [])
        bad = [r for r in res if not r.get("ok")]
        if xc.get("market_data_date") != sig.get("market_data_date"):
            out.append(f("BLOCK", "F5", f"cross-check is for market data {xc.get('market_data_date')} but the signals are {sig.get('market_data_date')}"))
        elif len(res) >= cfg["crosscheck_min_signals"] and len(bad) / len(res) >= cfg["crosscheck_block_ratio"]:
            out.append(f("BLOCK", "F5", f"the cross-check disagrees with {len(bad)} of {len(res)} signals - prices are suspect (a partial same-day bar while the market is open, "
                                        "a hole in the price history, or a bad feed). Do not order until the close-of-day data is published and the refresh re-run."))
        elif bad:
            out.append(f("WARN", "F5", f"the cross-check flagged {len(bad)} of {len(res)} signals (they are blocked from orders): " + ", ".join(sorted({r['symbol'] for r in bad})[:12])))

    # I1 numerics
    for name in ("signals", "cc"):
        bad = walk_bad_numbers(ctx.get(name) or {})
        if bad:
            out.append(f("BLOCK", "I1", f"{name}: NaN/inf in {len(bad)} field(s), e.g. {bad[0]}"))

    lists = {"exit": sig.get("exits", []), "addon": sig.get("addons", []), "entry": sig.get("entries", []), "hold": sig.get("holds", [])}
    positions = lists["exit"] + lists["addon"] + lists["hold"]

    # I2 position rows
    for p in positions:
        s = p["symbol"]
        if not (p.get("qty", 0) >= 1 and p.get("avg_cost", 0) > 0 and p.get("cmp", 0) > 0):
            out.append(f("BLOCK", "I2", f"{s}: qty/avg cost/price is not a positive number", s)); continue
        pl = (p["cmp"] / p["avg_cost"] - 1) * 100
        if abs(pl - p.get("pl_pct", pl)) > max(cfg["pl_tolerance_pct"], 0.01 * abs(pl)):
            out.append(f("BLOCK", "I2", f"{s}: P&L% {p.get('pl_pct')} does not match cmp/avg ({pl:.2f})", s))
        h = held.get(s)
        if h and (h["qty"] != p["qty"] or abs(h["avg_cost"] - p["avg_cost"]) > 0.05):
            out.append(f("BLOCK", "I2", f"{s}: signal qty/avg {p['qty']}@{p['avg_cost']} differs from holdings {h['qty']}@{h['avg_cost']}", s))

    # I4 / I5 membership
    seen = {}
    for k in ("exit", "addon", "entry"):
        for r in lists[k]:
            seen.setdefault(r["symbol"], []).append(k)
    for s, ks in seen.items():
        if len(ks) > 1:
            out.append(f("BLOCK", "I4", f"{s} is in more than one signal list: {ks}", s))
        if s in forbidden:
            out.append(f("BLOCK", "I5", f"{s} is a hedge / excluded / out-of-scope stock and must never be a signal", s))

    # I3 + I6 + I7 fills ledger
    recent_buy, led = {}, {}
    if fills is not None:
        for fl in sorted(fills, key=lambda x: x["date"]):
            s, q, pr = fl["symbol"], fl["qty"], fl.get("price") or (fl.get("value", 0) / fl["qty"] if fl.get("qty") else 0)
            if q <= 0 or pr <= 0:
                out.append(f("BLOCK", "I6", f"{s}: fill on {fl['date']} has qty {q} / price {pr}", s)); continue
            a = fl.get("action", "BUY")
            led[s] = led.get(s, 0) + (q if a == "BUY" else -q)
            if led[s] < 0:
                out.append(f("BLOCK", "I6", f"{s}: sells exceed buys in the fill ledger (fill {fl['date']})", s)); led[s] = 0
            if a == "BUY" and (now.date() - to_date(fl["date"])).days <= cfg["settlement_window_days"]:
                recent_buy[s] = recent_buy.get(s, 0) + q
        lag_syms = []
        px = {p["symbol"]: p["cmp"] for p in positions}
        for fl in fills[-400:]:
            c = px.get(fl["symbol"])
            if c and fl.get("price") and abs(fl["price"] / c - 1) * 100 > cfg["fill_price_dev_warn_pct"] and (now.date() - to_date(fl["date"])).days <= 10:
                out.append(f("WARN", "I6", f"{fl['symbol']}: fill price {fl['price']} is {abs(fl['price'] / c - 1) * 100:.0f}% away from the current price {c} (typo / split?)", fl["symbol"]))
        for s, q in led.items():
            if s in hedge:
                continue
            hq = held.get(s, {}).get("qty", 0)
            if q == hq:
                continue
            if q > hq and q - hq <= recent_buy.get(s, 0):
                lag_syms.append(f"{s} ({hq}->{q})")
            else:
                out.append(f("BLOCK", "I3", f"{s}: fill ledger says {q} but Zerodha holdings say {hq} - a missed fill or an exit outside tracking", s))
    if fills is not None and lag_syms:
        out.append(f("WARN", "I3", f"{len(lag_syms)} stocks were bought in the last {cfg['settlement_window_days']} days and are not in Zerodha holdings yet (settlement timing); "
                                   "positions and P&L exclude them until holdings catch up: " + ", ".join(lag_syms[:12]) + (" ..." if len(lag_syms) > 12 else "")))
    # I7: bought recently but absent from (or short in) holdings: never re-enter / add on top of an unsettled buy
    for k in ("entry", "addon"):
        for r in lists[k]:
            s = r["symbol"]
            if recent_buy.get(s) and held.get(s, {}).get("qty", 0) < led.get(s, 0):
                out.append(f("BLOCK", "I7", f"{s}: bought in the last {cfg['settlement_window_days']} days but not yet in holdings - do not {k} again until it settles", s))
        # (entries are also excluded by the engine; this guards the ticket builder, which only sees holdings)

    # S signal logic
    for r in lists["exit"]:
        if r.get("supertrend_color") != "red":
            out.append(f("BLOCK", "S1", f"{r['symbol']}: exit signal but Supertrend is {r.get('supertrend_color')}", r["symbol"]))
    for r in lists["addon"]:
        s = r["symbol"]
        if r.get("supertrend_color") != "green":
            out.append(f("BLOCK", "S2", f"{s}: add-on but Supertrend is {r.get('supertrend_color')}", s))
        if r.get("pl_pct", 0) >= cfg["add_trigger_pct"] and cfg["add_trigger_pct"] >= 0:
            out.append(f("BLOCK", "S2", f"{s}: add-on but the position is not in loss (P&L {r.get('pl_pct')}%)", s))
        elif cfg["add_trigger_pct"] < 0 and r.get("pl_pct", 0) > cfg["add_trigger_pct"]:
            out.append(f("BLOCK", "S2", f"{s}: add-on but P&L {r.get('pl_pct')}% is not at or beyond {cfg['add_trigger_pct']}%", s))
        cd = r.get("cooldown_days_since_last_buy")
        if cd is not None and cd < cfg["add_cooldown_days"]:
            out.append(f("BLOCK", "S2", f"{s}: add-on inside the {cfg['add_cooldown_days']}-day cooldown ({cd}d)", s))
        if (r.get("add_qty") or 0) < 1:
            out.append(f("BLOCK", "S2", f"{s}: add-on quantity < 1", s))
    big = []
    for r in lists["entry"]:
        s = r["symbol"]
        if r.get("supertrend_color") != "green":
            out.append(f("BLOCK", "S3", f"{s}: entry but Supertrend is {r.get('supertrend_color')}", s))
        if r.get("pct_from_high") is not None and r["pct_from_high"] < -cfg["entry_max_pct_below_high"] and cfg.get("require_high", True):
            out.append(f("BLOCK", "S3", f"{s}: entry but close is {r['pct_from_high']}% below the 52-week high", s))
        if s in held and held[s]["qty"] > 0:
            out.append(f("BLOCK", "S3", f"{s}: entry signal for a stock already held", s))
        w = cfg.get("entry_window_days")
        if w is not None:
            d = r.get("recent_bullish_flip_days_ago")
            if d is None or d > w:
                out.append(f("BLOCK", "S3", f"{s}: entry but the Supertrend flip is {d} trading days old (window {w})", s))
        if (r.get("qty_to_buy") or 0) < 1:
            out.append(f("BLOCK", "S3", f"{s}: entry quantity < 1", s))
        elif tier and r["qty_to_buy"] * r["close"] > cfg["overspend_x_tier"] * tier:
            big.append((s, r["qty_to_buy"] * r["close"]))
    if big:
        big.sort(key=lambda x: -x[1])
        out.append(f("WARN", "S4", f"{len(big)} entries cost more than {cfg['overspend_x_tier']}x the tier (Rs{tier:,.0f}) because the minimum is 1 share; largest "
                                   f"{big[0][0]} Rs{big[0][1]:,.0f}. Check before ordering."))
    if len(lists["entry"]) > cfg["max_entries_warn"]:
        out.append(f("WARN", "S5", f"{len(lists['entry'])} entry signals at once (limit {cfg['max_entries_warn']}) - a market-wide surge or a data problem"))
    npos = max(1, len(positions))
    if len(lists["exit"]) >= cfg["mass_exit_min"] and len(lists["exit"]) * 100 / npos >= cfg["mass_exit_pct_of_positions"]:
        out.append(f("BLOCK", "S5", f"{len(lists['exit'])} of {npos} positions flipped to exit at once - confirm the prices are right before selling anything"))

    # C capital / concentration
    deployed = sum(p["qty"] * p["avg_cost"] for p in positions if p.get("qty") and p.get("avg_cost"))
    if base and deployed > base * cfg["deployed_warn_pct_of_base"] / 100:
        out.append(f("WARN", "C1", f"deployed capital Rs{deployed:,.0f} exceeds {cfg['deployed_warn_pct_of_base']}% of the Rs{base:,.0f} base"))
    pending_buy = sum((o.get("price") or 0) * o["qty"] for o in orders if o.get("side") == "BUY" and o.get("status") == "PENDING")
    planned = sum((r.get("qty_to_buy") or 0) * r.get("close", 0) for r in lists["entry"])
    if base and (pending_buy + planned + deployed) > base:
        out.append(f("WARN", "C3", f"deployed Rs{deployed:,.0f} + pending buys Rs{pending_buy:,.0f} + all entry signals Rs{planned:,.0f} would exceed the Rs{base:,.0f} base"))
    elif base and pending_buy > base * cfg["pending_buy_warn_pct_of_base"] / 100:
        out.append(f("WARN", "C3", f"pending buy orders Rs{pending_buy:,.0f} are over {cfg['pending_buy_warn_pct_of_base']}% of the base"))
    if deployed:
        for p in positions:
            share = p["qty"] * p["avg_cost"] / deployed * 100
            if share > cfg["single_stock_warn_pct"] and len(positions) > 3:
                out.append(f("WARN", "C2", f"{p['symbol']} is {share:.0f}% of deployed capital", p["symbol"]))
        sec = {}
        for p in positions:
            sc = (ctx.get("sectors") or {}).get(p["symbol"])
            if sc:
                sec[sc] = sec.get(sc, 0) + p["qty"] * p["avg_cost"]
        for sc, v in sec.items():
            if v / deployed * 100 > cfg["sector_warn_pct"]:
                out.append(f("WARN", "C2", f"sector {sc} is {v / deployed * 100:.0f}% of deployed capital (limit {cfg['sector_warn_pct']}%)"))

    # O orders
    pend = [o for o in orders if o.get("status") == "PENDING"]
    by = {}
    for o in pend:
        by.setdefault((o["symbol"], o["side"]), []).append(o)
    for (s, side), os_ in by.items():
        q = sum(o["qty"] for o in os_)
        if side == "SELL" and q > held.get(s, {}).get("qty", 0):
            out.append(f("BLOCK", "O1", f"{s}: pending SELL {q} exceeds the {held.get(s, {}).get('qty', 0)} held (oversell)", s))
        if len(os_) > 1:
            out.append(f("WARN", "O2", f"{s}: {len(os_)} pending {side} orders (total {q}) - duplicates?", s))
        if s not in seen and s not in hedge and not ctx.get("is_inv_stock", lambda x: False)(s):
            out.append(f("WARN", "O3", f"{s}: pending {side} order but no current signal for it", s))

    # P options
    cc = ctx.get("cc")
    if cc:
        hot = [a for a in cc.get("alerts", []) if a.get("level") in ("EXIT", "BREACH") and a.get("type") != "Invalid GTT"]
        if hot:   # one line here; the per-leg detail is in the Covered Call page's strike-alert table
            names = sorted({a.get("symbol") for a in hot})
            out.append(f("WARN", "P3", f"{len(hot)} open option exit / strike-breach alerts on {len(names)} stocks ({', '.join(names[:8])}{'...' if len(names) > 8 else ''}) - see the Covered Call alerts", None))
        bad = [a for a in cc.get("alerts", []) if a.get("type") == "Invalid GTT"]
        if bad:   # P5: the GTT scan (scan_gtts.py) found invalid orders; a stale GTT on a closed contract buys a NEW long if it triggers
            hi = sum(1 for a in bad if a.get("level") == "BREACH")
            out.append(f("WARN", "P5", f"{len(bad)} invalid GTT orders ({hi} high: e.g. buy GTTs on contracts you no longer hold) - see Covered Call > Alerts > Invalid GTT; the zerodha-gtt-order skill can delete them", None))
        for s in cc.get("stocks", []):
            for g in s.get("suggestions", []):
                if g.get("expiry_week") and s.get("status") in ("ENTER", "FLIP"):
                    out.append(f("WARN", "P1", f"{s['symbol']}: {g['expiry']} is in expiry week - do not open a new option structure", s["symbol"]))
            if "lot" in s and s.get("status") in ("ENTER", "FLIP") and not s.get("lot"):
                out.append(f("WARN", "P2", f"{s['symbol']}: no lot size known - cannot size the option trade", s["symbol"]))
            for ex in s.get("expiries", []):
                dte = (to_date(ex["expiry"]) - (to_date(cc.get("market_data_date")) or now.date())).days
                if dte <= cfg["expiry_week_days"]:
                    out.append(f("WARN", "P1", f"{s['symbol']}: expiry {ex['expiry']} is {dte} days away (expiry week) - do not open a new option structure", s["symbol"]))
                if not ex.get("lot"):
                    out.append(f("WARN", "P2", f"{s['symbol']}: no lot size for {ex['expiry']} - cannot size the option trade", s["symbol"]))
            if s.get("covered") is False and s.get("desired") == "CALL":
                out.append(f("WARN", "P4", f"{s['symbol']}: a short call would not be covered by the shares held (lot {s.get('lot')}, held {s.get('shares')})", s["symbol"]))

    # X separation
    for v in ctx.get("import_violations", []):
        out.append(f("BLOCK", "X1", v))
    return out


def separation_violations():
    bad = []
    other = BROKER["other_dir"]
    for p in ROOT.joinpath("scripts").glob("*.py"):
        if p.name in ("guardrails.py", "test_guardrails.py"):
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if re.search(r"^\s*(from|import)\s", line) and re.search(other.replace("-", "[-_]"), line):
                bad.append(f"{p.name}:{i} imports from {other}")
            if re.search(r"sys\.path\.insert", line) and other in line:
                bad.append(f"{p.name}:{i} adds {other} to the import path")
    return bad


def load(p, default=None):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def build_ctx():
    sig = load(ROOT / "zerodha_live_signals.json")
    hs = load(DATA / "holdings_snapshot.json", {"holdings": []})
    osn = load(DATA / "orders_snapshot.json", {"orders": []})
    ex = load(DATA / "excluded_symbols.json", {"symbols": []})
    cfg = load(DATA / "guardrails_config.json", {})
    return {
        "signals": sig, "signals_generated_at": sig.get("generated_at"), "holdings": hs["holdings"], "holdings_fetched_at": hs.get("fetched_at"),
        "orders": osn.get("orders", []), "orders_fetched_at": osn.get("fetched_at"), "fills": None,   # no fill ledger: holdings (MCP) are the truth
        "crosscheck": load(DATA / "signal_crosscheck.json"), "cc": load(ROOT / "covered_call_signals.json"), "config": cfg, "halt": load(DATA / "trading_halt.json", {}),
        "sectors": load(DATA / "equity_sectors.json", {}), "excluded": ex.get("symbols", []), "is_inv_stock": lambda s: False,
        "import_violations": separation_violations(),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()
    now = datetime.now(IST)
    ctx = build_ctx()
    findings = evaluate(ctx, now)
    blocks = [x for x in findings if x["level"] == "BLOCK"]
    status = "BLOCK" if any(x["symbol"] is None for x in blocks) else ("BLOCK_SYMBOLS" if blocks else ("WARN" if any(x["level"] == "WARN" for x in findings) else "OK"))
    per_symbol = {}
    for x in blocks:
        if x["symbol"]:
            per_symbol.setdefault(x["symbol"], []).append(f"{x['id']}: {x['msg']}")
    out = {"generated_at": now.isoformat(timespec="seconds"), "broker": BROKER["id"], "market_data_date": ctx["signals"].get("market_data_date"),
           "signals_generated_at": ctx["signals_generated_at"], "status": status, "global_block": any(x["symbol"] is None for x in blocks),
           "counts": {"block": len(blocks), "warn": sum(1 for x in findings if x["level"] == "WARN"), "info": sum(1 for x in findings if x["level"] == "INFO")},
           "per_symbol_blocks": per_symbol, "findings": findings}
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"GUARDRAILS {BROKER['label']}: {status} | BLOCK {out['counts']['block']} | WARN {out['counts']['warn']} | market data {out['market_data_date']}")
    for x in findings:
        if x["level"] != "INFO":
            print(f"  {x['level']:5} {x['id']:3} {x['msg']}")
    return 2 if (args.strict and blocks) else 0


if __name__ == "__main__":
    sys.exit(main())
