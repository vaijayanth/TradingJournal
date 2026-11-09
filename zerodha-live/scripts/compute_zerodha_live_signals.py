"""Zerodha signals for the Nifty F&O stock universe -> zerodha_live_signals.json (same shape as dhan_live_signals.json, so the
common pages render it through the same adapter).

Rules (user, 2026-11-09):
  universe : Nifty F&O stocks (data/fno_universe.json, refreshed every month from NSE's lot file). Holdings outside it are
             ignored completely - not counted, not shown.
  scope    : the dashboard's OPEN POSITIONS are only the stocks the user moved from the old sheet (data/moved_from_sheet.json)
             plus positions it opened itself since (zerodha_trades.json). Every other Zerodha holding - including the other
             old-sheet trades - is ignored, but still blocks a new ENTRY in that stock (you cannot enter what you already hold).
  entry    : Supertrend flipped to GREEN within the last 6 trading days, currently green, and no open position in the stock.
             Quantity = floor(position size / close), minimum 1.
  exit     : Supertrend RED, whatever the profit or loss -> sell the whole position. GRANDFATHERED: a position held at the
             baseline cut-off only gets an exit signal once its Supertrend turns red AFTER the cut-off (a stock that was
             already red at the cut-off needs a green flip and then a new red one).
  add      : Supertrend green AND the position in loss -> 1/10 of the current quantity (min 1), at most once every 7 days.
             Applies to existing holdings immediately.
  sizing   : Rs 20,000 per position, +Rs 5,000 for every 100 trades (open + closed). Fixed capital base Rs 30,00,000.

Inputs: Zerodha MCP holdings (snapshot), the backtester's market_screens_full / supertrend_full, the frozen sheet baseline
(closed trades, trade count) and zerodha_trades.json (trades since the cut-off). The Zerodha holdings are the ground truth for
what is held. Closed-trade P&L is gross of charges.

Usage: python zerodha-live/scripts/compute_zerodha_live_signals.py --holdings ... --market-screens ... --supertrend ... --out ...
"""
import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
sys.path.insert(0, str(HERE))
from zerodha_common import (compute_hot_sectors, days_since, entry_flip_label, flip_label,  # noqa: E402
                                        index_rsi, index_supertrend, index_week52, load_json)

STARTING_CAPITAL = 3_000_000
BASE_POSITION_RS = 20_000
POSITION_INCREMENT_RS = 5_000
POSITION_INCREMENT_TRADES = 100
ENTRY_WINDOW_TRADING_DAYS = 6
ADD_FRACTION = 0.10
ADD_COOLDOWN_DAYS = 7


def tier_for(trades):
    return BASE_POSITION_RS + (trades // POSITION_INCREMENT_TRADES) * POSITION_INCREMENT_RS


def build(holdings, uni, week52, stmap, rsimap, baseline, trades, today, market_date, sectors, history, aliases=None, moved=None):
    aliases = aliases or {}
    moved = moved or {"symbols": None, "include_baseline_closed": True}
    # renamed stocks: NSE's current symbol -> the symbol the backtester data is keyed by
    for new, old in aliases.items():
        for m in (week52, stmap, rsimap, sectors):
            if old in m and new not in m:
                m[new] = m[old]
    all_held = {h["symbol"] for h in holdings if h.get("qty", 0) > 0}          # anything held in the account blocks a new entry
    scope = None if moved["symbols"] is None else set(moved["symbols"]) | set(trades.get("entry_dates", {}))
    held = {h["symbol"]: h for h in holdings if h["symbol"] in uni and h.get("qty", 0) > 0 and (scope is None or h["symbol"] in scope)}
    cutoff = baseline["cutoff_date"]
    closed = [c for c in (list(baseline["closed"]) if moved.get("include_baseline_closed", True) else []) + list(trades.get("closed", [])) if c["symbol"] in uni]
    closed.sort(key=lambda c: c.get("exit_date") or "")
    closed_norm = [{"symbol": c["symbol"], "entry_date": c.get("entry_date"), "exit_date": c.get("exit_date"), "qty": c.get("qty"),
                    "entry_price": c.get("entry"), "exit_price": c.get("exit"), "pl_rs": c["pl_rs"], "pl_pct": c.get("pl_pct"),
                    "hold_days": c.get("hold_days")} for c in closed]
    realised = round(sum(c["pl_rs"] for c in closed), 2)
    trade_count = len(closed) + len(held)          # open + closed
    tier = tier_for(trade_count)

    exits, addons, holds, no_data = [], [], [], []
    unrealised = invested = 0.0
    for sym in sorted(held):
        h = held[sym]
        qty, avg = h["qty"], h["avg_cost"]
        w, st = week52.get(sym), stmap.get(sym)
        if not w or not st or not st.get("color"):
            no_data.append({"symbol": sym, "reason": "no backtester price/Supertrend data"})
            continue
        cmp_ = w["close"]
        pl_pct = round((cmp_ / avg - 1) * 100, 4)
        pl_rs = round((cmp_ - avg) * qty, 2)
        unrealised += pl_rs
        invested += qty * avg
        colour = st["color"].lower()
        entry_date = trades.get("entry_dates", {}).get(sym) or moved.get("entry_dates", {}).get(sym) or baseline["open_dates"].get(sym)
        last_buy = trades.get("last_buy", {}).get(sym) or moved.get("last_buy", {}).get(sym) or baseline["last_buy"].get(sym)
        streak_start = st.get("current_streak_start_date")
        row = {"entry_date": entry_date, "symbol": sym, "qty": qty, "avg_cost": avg, "cmp": cmp_, "pl_pct": pl_pct,
               "notional_pl_rs": pl_rs, "supertrend_color": colour, "flip_label": flip_label(st), "flip_date": streak_start,
               "pct_from_52w_high": w.get("pct_from_high"), "num_adds": 0,
               "age_days": days_since(entry_date, today) if entry_date else None,
               "rsi14": rsimap.get(sym), "sector": sectors.get(sym)}
        if colour == "red":
            if streak_start and streak_start > cutoff:
                exits.append(row)
            else:
                row["note"] = f"red since {streak_start} (before the {cutoff} cut-off): held under the grandfather rule until the trend flips green and then red again"
                holds.append(row)
            continue
        if pl_pct < 0:
            since = days_since(last_buy, today) if last_buy else None
            if since is None or since >= ADD_COOLDOWN_DAYS:
                addons.append({**row, "add_qty": max(1, round(qty * ADD_FRACTION)), "cooldown_days_since_last_buy": since})
                continue
        holds.append(row)

    entries = []
    for sym in sorted(uni):
        if sym in held or sym in all_held:
            continue
        st, w = stmap.get(sym), week52.get(sym)
        if not st or not w or (st.get("color") or "").lower() != "green":
            continue
        d = st.get("recent_bullish_flip_trading_days_ago")
        if d is None or d > ENTRY_WINDOW_TRADING_DAYS:
            continue
        entries.append({"symbol": sym, "close": w["close"], "high_52w": w.get("high_52w"), "pct_from_high": w.get("pct_from_high"),
                        "date": market_date, "supertrend_color": "green", "flipped_today": d == 0,
                        "recent_bullish_flip_days_ago": d, "qty_to_buy": max(1, int(tier // w["close"])),
                        "sector": sectors.get(sym), "flip_label": entry_flip_label(st),
                        "flip_date": st.get("current_streak_start_date")})
    # Hot sector = top-3 sector by Supertrend turnarounds among the Nifty F&O stocks only (the strategy's universe), not the
    # backtester's whole 1,500-stock universe; 52-week-high counts do not apply to this strategy.
    fno_stmap = {k: v for k, v in stmap.items() if k in uni}
    turn, _entry_count, hot_turn, _hot_entry = compute_hot_sectors(fno_stmap, entries, sectors)
    hot_entry = set()
    for e in entries:
        sec = e["sector"]
        e["sector_52wh_count"] = 0
        e["sector_turn_count"] = turn.get(sec, 0) if sec else 0
        e["hot_52wh"] = False
        e["hot_turn"] = bool(sec and sec in hot_turn)

    combined = round(realised + unrealised, 2)
    # Equity history accumulates one point per market date (flow-neutral: base + realised + unrealised)
    pt = {"date": market_date, "pnl": combined, "realised": realised, "invested": round(invested, 2), "equity": round(STARTING_CAPITAL + combined, 2)}
    history = [p for p in history if p["date"] != market_date] + [pt]
    history.sort(key=lambda p: p["date"])
    nxt = ((trade_count // POSITION_INCREMENT_TRADES) + 1) * POSITION_INCREMENT_TRADES
    tier_note = f"{trade_count} trades (open + closed) · next +{POSITION_INCREMENT_RS:,} at {nxt}"

    reco = {}
    sq = {**baseline.get("sheet_open_qty", {}), **moved.get("sheet_qty", {})}
    for sym in sorted(held):                       # in-scope positions only (the rest are not this dashboard's)
        hq, sh = held[sym]["qty"] if sym in held else 0, sq.get(sym, 0)
        if hq != sh:
            reco[sym] = {"holdings_qty": hq, "sheet_qty_at_cutoff": sh}
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(), "market_data_date": market_date, "source_generated_at": None,
        "sizing": {"closed_trades_count": len(closed), "base_tier_rs": tier, "total_positions_ever_opened": trade_count,
                   "realized_pl_rs": realised, "unrealized_pl_rs": round(unrealised, 2), "combined_pl_rs": combined,
                   "effective_tier_rs": tier, "doubled": False, "tier_note": tier_note},
        "dh252_position_count": len(held), "option_hedge_portfolio": [],
        "holdings_count_total": len(holdings), "holdings_out_of_scope": len(holdings) - len(held),
        "no_data": no_data, "exited_outside_tracking": [],
        "rules": {"add_trigger_pct": 0, "add_fraction": ADD_FRACTION, "add_cooldown_days": ADD_COOLDOWN_DAYS,
                  "entry_window_trading_days": ENTRY_WINDOW_TRADING_DAYS, "exit": "Supertrend red, any profit or loss",
                  "grandfather_cutoff": cutoff},
        "capital_base": {"initial_capital": STARTING_CAPITAL, "note": "fixed capital base; equity = base + realised + unrealised (Nifty F&O stocks only)"},
        "equity_curve": history, "closed_trades": closed_norm,
        "hot_sectors": {"by_52wh_entries": sorted(hot_entry), "by_supertrend_turns": sorted(hot_turn)},
        "entries": entries, "exits": exits, "addons": addons, "holds": holds,
        "reconciliation": {"note": "in-scope positions: Zerodha holdings (MCP) vs the sheet's open quantity at the cut-off; informational", "differences": reco},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdings", required=True)
    ap.add_argument("--market-screens", required=True)
    ap.add_argument("--supertrend", required=True)
    ap.add_argument("--universe", default=str(DATA / "fno_universe.json"))
    ap.add_argument("--baseline", default=str(DATA / "baseline_from_sheet.json"))
    ap.add_argument("--trades", default=str(DATA / "zerodha_trades.json"))
    ap.add_argument("--history", default=str(DATA / "equity_history.json"))
    ap.add_argument("--excluded", default=str(DATA / "excluded_symbols.json"))
    ap.add_argument("--moved", default=str(DATA / "moved_from_sheet.json"))
    ap.add_argument("--sectors", default=str(DATA / "equity_sectors.json"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--as-of", default=None)
    ap.add_argument("--no-history", action="store_true", help="do not write the equity history (testing)")
    a = ap.parse_args()
    if not Path(a.baseline).exists():
        print("REFUSED: no baseline - run zerodha-live/scripts/freeze_baseline.py once first.")
        return 2
    hdoc = load_json(a.holdings)
    ms, sup = load_json(a.market_screens), load_json(a.supertrend)
    uni = set(load_json(a.universe)["symbols"])
    excluded = set(load_json(a.excluded)["symbols"]) if Path(a.excluded).exists() else set()
    uni -= excluded                                   # investment-portfolio stocks: out of the F&O dashboard entirely
    base = load_json(a.baseline)
    trades = load_json(a.trades) if Path(a.trades).exists() else {"closed": [], "last_buy": {}, "entry_dates": {}}
    hist = load_json(a.history) if Path(a.history).exists() else []
    sectors = {k: v for k, v in (load_json(a.sectors) if Path(a.sectors).exists() else {}).items() if v and v.strip() not in ("—", "-")}
    alias_path = DATA / "symbol_aliases.json"
    aliases = load_json(alias_path)["aliases"] if alias_path.exists() else {}
    today = date.fromisoformat(a.as_of) if a.as_of else datetime.now(timezone.utc).date()
    md = sup.get("latest_market_date")
    out = build(hdoc["holdings"], uni, index_week52(ms), index_supertrend(sup), index_rsi(ms), base, trades, today, md, sectors, hist, aliases, load_json(a.moved) if Path(a.moved).exists() else None)
    out["holdings_fetched_at"] = hdoc.get("fetched_at")
    out["source_generated_at"] = {"supertrend": sup.get("generated_at"), "market_screens": ms.get("generated_at")}   # when the backtester published the prices behind these signals
    out["universe"] = {"month": load_json(a.universe)["month"], "count": len(uni), "excluded": sorted(excluded)}
    out["scope"] = {"moved_from_sheet": load_json(a.moved)["symbols"] if Path(a.moved).exists() else None, "moved_at": load_json(a.moved).get("moved_at") if Path(a.moved).exists() else None}
    out["excluded_holdings"] = [{"symbol": h["symbol"], "qty": h["qty"], "invested": round(h["qty"] * h["avg_cost"], 2)} for h in hdoc["holdings"] if h["symbol"] in excluded and h.get("qty", 0) > 0]
    Path(a.out).write_text(json.dumps(out, indent=2))
    if not a.no_history:
        Path(a.history).write_text(json.dumps(out["equity_curve"], indent=1))
    z = out["sizing"]
    print(f"universe {len(uni)} F&O stocks | holdings in scope {out['dh252_position_count']} of {out['holdings_count_total']} | "
          f"exits {len(out['exits'])}, add-ons {len(out['addons'])}, entries {len(out['entries'])} | trades {z['total_positions_ever_opened']} -> tier Rs{z['effective_tier_rs']:,} | "
          f"P&L realised {z['realized_pl_rs']:,.0f} unrealised {z['unrealized_pl_rs']:,.0f}")
    if out["reconciliation"]["differences"]:
        print(f"note: {len(out['reconciliation']['differences'])} stocks differ between holdings and the sheet's open quantity at the cut-off")
    return 0


if __name__ == "__main__":
    sys.exit(main())
