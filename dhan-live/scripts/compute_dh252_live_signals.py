"""dh252 Live Signal Engine - joins real dh252 positions (scoped by our own
trade log, NOT your whole Dhan account) against backtester's daily-published
signals to produce personalized entry/exit/add-on signals.

CORRECTED 2026-11-08: the first version of this script wrongly treated
EVERY Dhan holding as a dh252 position. Confirmed wrong by the user: 11 of
59 holdings (INFY, BPCL, CGPOWER, BANKINDIA, BSE, CUMMINSIND, SHRIRAMFIN,
MCX, HCLTECH, DIXON, LIQUIDCASE) are a separate, unrelated portfolio and
should never get dh252 exit/add-on signals. The ONLY source of truth for
"is this a dh252 position" is dh252_trade_log.json - Dhan's API has no
concept of which strategy a holding belongs to, so this has to be tracked
ourselves (seeded 2026-11-08 from the user's own real position export,
maintained going forward as orders actually get placed - see Phase 4).

Rules ported exactly from backtester's index.html (dh252RenderSignals /
dh252RenderPositions, confirmed read directly from source):

  EXIT:   Supertrend turns red -> exit unconditionally, regardless of P&L.
          Takes priority over an add-on signal the same day.
  ADD-ON: P&L <= -6% vs WAC AND Supertrend still green AND >=7 days since
          the last buy on that symbol. Add qty = round(qty * 0.10).
  ENTRY:  backtester's own universe-wide filter, minus symbols already in
          our dh252 position scope (NOT minus all Dhan holdings).

For symbols in scope, qty/WAC are taken from the live Dhan holdings
snapshot when present (holdings is ground truth, same "Holdings overrides
FIFO" principle already used elsewhere in this app) - the trade log's own
qty/wac is only a fallback if a position is somehow missing from the
holdings pull. A trade-log symbol with NO matching Dhan holding at all is
treated as already exited outside this system's tracking and dropped from
"open", not force-kept.

Open-position row shape matches dh252RenderPositions exactly: entry date,
symbol, qty, WAC, CMP, Supertrend color, Supertrend flip/streak label, %
away from 52-week high, notional P&L (Rs and %), add-on count, age (days).

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


def index_rsi(market_screens):
    return {strip_suffix(r["symbol"]): r["rsi14"] for r in market_screens.get("rsi_all", [])}


def tier_size(closed_trades_count):
    return BASE_POSITION_RS + (closed_trades_count // POSITION_INCREMENT_TRADES) * POSITION_INCREMENT_RS


def effective_tier_size(base_tier, total_positions_ever_opened, combined_pl_rs):
    if total_positions_ever_opened >= SIZE_DOUBLE_POSITIONS_THRESHOLD and combined_pl_rs >= 0:
        return base_tier * 2
    return base_tier


def build_dh252_positions(fills):
    """Group fills by symbol -> {symbol: {entry_date, last_fill_date, num_adds}}.
    First fill (by date) is the entry; any later fill is an add-on."""
    by_symbol = {}
    for f in fills:
        by_symbol.setdefault(f["symbol"], []).append(f)
    positions = {}
    for symbol, symbol_fills in by_symbol.items():
        symbol_fills.sort(key=lambda f: f["date"])
        # historical_num_adds covers add-ons known to have happened before
        # this log existed (seeded from a point-in-time export, exact fill
        # date unknown) - real fills recorded by this system add on top.
        historical_adds = max((f.get("historical_num_adds", 0) for f in symbol_fills), default=0)
        positions[symbol] = {
            "entry_date": symbol_fills[0]["date"],
            "last_fill_date": symbol_fills[-1]["date"],
            "num_adds": (len(symbol_fills) - 1) + historical_adds,
            "log_qty": sum(f["qty"] for f in symbol_fills),
            "log_wac": symbol_fills[0]["price"],  # entry price; qty/wac overridden by live holdings below
        }
    return positions


def days_since(date_str, today):
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    return max(0, (today - d).days)


def flip_label(st):
    """Port of index.html's stFlipLabel: 'Flipped to GREEN (Nd)' if a flip
    happened recently, else 'GREEN/RED Nd' for an ongoing streak, else None."""
    if not st:
        return None
    flip_days = st.get("recent_flip_trading_days_ago", st.get("recent_flip_days_ago"))
    if flip_days is not None:
        dir_label = "GREEN" if st.get("recent_flip_direction") == "up" else "RED"
        return f"Flipped to {dir_label} ({flip_days})"
    streak_days = st.get("current_streak_trading_days", st.get("current_streak_days"))
    if streak_days is not None and st.get("color"):
        return f"{st['color'].upper()} {streak_days}d"
    return None


def build_signals(holdings, week52, stmap, rsimap, entry_signals, trade_log, today):
    holdings_by_symbol = {h["symbol"]: h for h in holdings}
    dh252_positions = build_dh252_positions(trade_log.get("fills", []))
    dh252_symbols = set(dh252_positions)

    closed_trades_count = trade_log.get("closed_trades_count", 0)
    total_positions_ever_opened = trade_log.get("total_positions_ever_opened", 0)
    realized_pl_rs = trade_log.get("realized_pl_rs", 0.0)
    base_tier = tier_size(closed_trades_count)

    exits, addons, holds, no_data, exited_outside_tracking = [], [], [], [], []
    unrealized_pl_rs = 0.0

    for symbol, pos in sorted(dh252_positions.items()):
        h = holdings_by_symbol.get(symbol)
        if not h:
            exited_outside_tracking.append(symbol)
            continue
        qty, wac = h["qty"], h["avg_cost"]  # holdings is ground truth, same principle as Equity Journal

        w = week52.get(symbol)
        st = stmap.get(symbol)
        if not w or not st or not st.get("color"):
            no_data.append({"symbol": symbol, "reason": "no backtester price/Supertrend data today"})
            continue

        cmp_ = w["close"]
        pl_pct = round((cmp_ - wac) / wac * 100, 4)
        notional_pl = round((cmp_ - wac) * qty, 2)
        unrealized_pl_rs += notional_pl
        color = st["color"].lower()

        row = {
            "entry_date": pos["entry_date"], "symbol": symbol, "qty": qty, "avg_cost": wac, "cmp": cmp_,
            "pl_pct": pl_pct, "notional_pl_rs": notional_pl,
            "supertrend_color": color, "flip_label": flip_label(st),
            "pct_from_52w_high": w.get("pct_from_high"),
            "num_adds": pos["num_adds"], "age_days": days_since(pos["entry_date"], today),
            "rsi14": rsimap.get(symbol),
        }

        if color == "red":
            exits.append(row)
            continue  # exit takes priority over an add-on signal the same day

        if pl_pct <= ADD_TRIGGER_PCT:
            cooldown_days = days_since(pos["last_fill_date"], today)
            if cooldown_days >= ADD_COOLDOWN_DAYS:
                add_qty = max(1, round(qty * ADD_FRACTION))
                addons.append({**row, "add_qty": add_qty, "cooldown_days_since_last_buy": cooldown_days})
                continue

        holds.append(row)

    combined_pl_rs = round(realized_pl_rs + unrealized_pl_rs, 2)
    eff_tier = effective_tier_size(base_tier, total_positions_ever_opened, combined_pl_rs)

    entries = []
    for e in entry_signals.get("entries", []):
        symbol = e["symbol"]
        if symbol in dh252_symbols:
            continue  # already a dh252 position - not "any Dhan holding"
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
        "dh252_position_count": len(dh252_symbols),
        "dhan_holdings_count_total": len(holdings),
        "dhan_holdings_out_of_scope": len(holdings) - len(dh252_symbols & set(holdings_by_symbol)),
        "no_data": no_data,
        "exited_outside_tracking": exited_outside_tracking,
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
        holdings, index_week52(market_screens), index_supertrend(supertrend), index_rsi(market_screens),
        entry_signals, trade_log, today,
    )
    Path(args.out).write_text(json.dumps(result, indent=2))

    print(f"dh252 positions in scope: {result['dh252_position_count']} (of {result['dhan_holdings_count_total']} total Dhan holdings)")
    print(f"Entry signals (not in scope): {len(result['entries'])}")
    print(f"Exit signals: {len(result['exits'])}")
    print(f"Add-on signals: {len(result['addons'])}")
    if result["exited_outside_tracking"]:
        print(f"WARNING - in trade log but not in current holdings (exited outside tracking?): {result['exited_outside_tracking']}")
    print(f"Effective tier size: Rs{result['sizing']['effective_tier_rs']}")
    print(f"Written to {args.out}")


if __name__ == "__main__":
    main()
