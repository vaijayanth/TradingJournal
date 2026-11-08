"""dh252 Live Signal Engine - joins real Dhan holdings against backtester's
daily-published signals to produce personalized entry/exit/add-on signals.

This is the Phase 2 piece of the plan: Phase 1 (backtester/scripts/
dh252_entry_screener.py) already produces a universe-wide entry candidate
list with no knowledge of what you actually hold. This script adds that
knowledge - excluding symbols already held from the entry list, and
computing EXIT/ADD-ON signals for symbols you do hold - using the exact
rules already implemented in backtester's index.html (dh252RenderSignals,
confirmed read directly from source):

  EXIT:   Supertrend turns red -> exit unconditionally, regardless of P&L.
          Takes priority over an add-on signal the same day.
  ADD-ON: P&L <= -6% vs avg cost AND Supertrend still green AND >=7 days
          since the last buy on that symbol. Add qty = round(qty * 0.10).
  ENTRY:  backtester's own universe-wide filter, minus symbols already held.

Position sizing (unchanged hardcoded rule, per 2026-11-08 session):
  tier_size = Rs1,000 + Rs1,000 per 100 closed trades (from our own trade
  log - no retroactive history exists via Dhan MCP, confirmed empirically).
  Doubles permanently once total_positions_ever_opened >= 100 AND combined
  P&L >= 0 (also from our own log).

Cooldown day-1 policy (confirmed 2026-11-08): a held symbol with no entry
in dh252_trade_log.json's fills is treated as cooldown-satisfied - the
7-day clock only starts once THIS system records a real buy on it.

No Google Sheet anywhere in this chain - inputs are:
  - a Dhan holdings snapshot (JSON you provide; produced by calling
    mcp__claude_ai_dhan_mcp__portfolio_agent_tool "holdings" and
    normalizing the result - that MCP call can only happen inside a
    Claude Code session, so it's not done by this script itself)
  - backtester's daily-published market_screens_full.json,
    supertrend_full.json, dh252_entry_signals.json (fetched from
    raw.githubusercontent.com/vaijayanth/backtester/main/<file>, or a
    local copy)
  - this repo's own dh252_trade_log.json (read AND rewritten here only to
    bump total_positions_ever_opened bookkeeping - fills themselves are
    only ever appended when an order actually gets placed, a later phase)

Usage:
  python compute_dh252_live_signals.py \
    --holdings data/holdings_snapshot.json \
    --market-screens market_screens_full.json \
    --supertrend supertrend_full.json \
    --entry-signals dh252_entry_signals.json \
    --trade-log data/dh252_trade_log.json \
    --out dhan_live_signals.json
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ADD_TRIGGER_PCT = -6.0
ADD_FRACTION = 0.10
ADD_COOLDOWN_DAYS = 7
BASE_POSITION_RS = 1000
POSITION_INCREMENT_RS = 1000
POSITION_INCREMENT_TRADES = 100
SIZE_DOUBLE_POSITIONS_THRESHOLD = 100


def strip_suffix(symbol):
    for suf in (".NS", ".BO"):
        if symbol.endswith(suf):
            return symbol[: -len(suf)]
    return symbol


def load_json(path):
    return json.loads(Path(path).read_text())


def index_week52(market_screens):
    return {strip_suffix(r["symbol"]): r for r in market_screens.get("week52_all", [])}


def index_supertrend(supertrend):
    return {strip_suffix(r["symbol"]): r for r in supertrend.get("entries", [])}


def tier_size(closed_trades_count):
    return BASE_POSITION_RS + (closed_trades_count // POSITION_INCREMENT_TRADES) * POSITION_INCREMENT_RS


def effective_tier_size(base_tier, total_positions_ever_opened, combined_pl_rs):
    if total_positions_ever_opened >= SIZE_DOUBLE_POSITIONS_THRESHOLD and combined_pl_rs >= 0:
        return base_tier * 2
    return base_tier


def last_fill_date(fills, symbol):
    dates = [f["date"] for f in fills if f["symbol"] == symbol and f["action"] in ("BUY", "ADDON")]
    return max(dates) if dates else None


def days_since(date_str, today):
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    return (today - d).days


def build_signals(holdings, week52, stmap, entry_signals, trade_log, today):
    held_symbols = {h["symbol"] for h in holdings}
    closed_trades_count = trade_log.get("closed_trades_count", 0)
    total_positions_ever_opened = trade_log.get("total_positions_ever_opened", 0)
    fills = trade_log.get("fills", [])

    base_tier = tier_size(closed_trades_count)

    exits, addons, holds, no_data = [], [], [], []
    realized_pl_rs = trade_log.get("realized_pl_rs", 0.0)
    unrealized_pl_rs = 0.0

    for h in holdings:
        symbol = h["symbol"]
        w = week52.get(symbol)
        st = stmap.get(symbol)
        if not w or not st or not st.get("color"):
            no_data.append({"symbol": symbol, "reason": "no backtester price/Supertrend data today"})
            continue

        cmp_ = w["close"]
        pl_pct = round((cmp_ - h["avg_cost"]) / h["avg_cost"] * 100, 4)
        notional_pl = round((cmp_ - h["avg_cost"]) * h["qty"], 2)
        unrealized_pl_rs += notional_pl
        color = st["color"].lower()

        row = {
            "symbol": symbol, "qty": h["qty"], "avg_cost": h["avg_cost"], "cmp": cmp_,
            "pl_pct": pl_pct, "notional_pl_rs": notional_pl,
            "supertrend_color": color, "pct_from_52w_high": w.get("pct_from_high"),
        }

        if color == "red":
            exits.append(row)
            continue  # exit takes priority over an add-on signal the same day

        if pl_pct <= ADD_TRIGGER_PCT:
            last_date = last_fill_date(fills, symbol)
            cooldown_days = days_since(last_date, today) if last_date else None
            cooldown_ok = last_date is None or cooldown_days >= ADD_COOLDOWN_DAYS
            if cooldown_ok:
                add_qty = max(1, round(h["qty"] * ADD_FRACTION))
                addons.append({**row, "add_qty": add_qty,
                               "cooldown_days_since_last_buy": cooldown_days,
                               "cooldown_basis": "pre-existing position, day-1 default" if last_date is None else "own trade log"})
                continue

        holds.append(row)

    combined_pl_rs = round(realized_pl_rs + unrealized_pl_rs, 2)
    eff_tier = effective_tier_size(base_tier, total_positions_ever_opened, combined_pl_rs)

    entries = []
    for e in entry_signals.get("entries", []):
        symbol = e["symbol"]
        if symbol in held_symbols:
            continue
        qty_to_buy = max(1, int(eff_tier // e["close"]))
        entries.append({**{k: v for k, v in e.items() if k != "qty_at_base_tier"}, "qty_to_buy": qty_to_buy})

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sizing": {
            "closed_trades_count": closed_trades_count,
            "base_tier_rs": base_tier,
            "total_positions_ever_opened": total_positions_ever_opened,
            "realized_pl_rs": realized_pl_rs,
            "unrealized_pl_rs": round(unrealized_pl_rs, 2),
            "combined_pl_rs": combined_pl_rs,
            "effective_tier_rs": eff_tier,
            "doubled": eff_tier != base_tier,
        },
        "holdings_count": len(holdings),
        "no_data": no_data,
        "entries": entries,
        "exits": exits,
        "addons": addons,
        "holds": holds,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--holdings", required=True)
    parser.add_argument("--market-screens", required=True)
    parser.add_argument("--supertrend", required=True)
    parser.add_argument("--entry-signals", required=True)
    parser.add_argument("--trade-log", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--as-of", default=None, help="Override today's date (YYYY-MM-DD), for testing against historical data")
    args = parser.parse_args()

    holdings = load_json(args.holdings)["holdings"]
    market_screens = load_json(args.market_screens)
    supertrend = load_json(args.supertrend)
    entry_signals = load_json(args.entry_signals)
    trade_log = load_json(args.trade_log)

    today = (datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of
             else datetime.now(timezone.utc).date())

    result = build_signals(
        holdings, index_week52(market_screens), index_supertrend(supertrend),
        entry_signals, trade_log, today,
    )
    Path(args.out).write_text(json.dumps(result, indent=2))

    print(f"Holdings: {result['holdings_count']} ({len(result['no_data'])} with no data today)")
    print(f"Entry signals (not held): {len(result['entries'])}")
    print(f"Exit signals: {len(result['exits'])}")
    print(f"Add-on signals: {len(result['addons'])}")
    print(f"Effective tier size: Rs{result['sizing']['effective_tier_rs']}")
    print(f"Written to {args.out}")


if __name__ == "__main__":
    main()
