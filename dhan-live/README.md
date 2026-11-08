# dh252 Live Signals (Dhan)

Phase 2 of replacing the hand-logged Google Sheet dh252 tracking with live
Dhan data. No Google Sheet anywhere in this chain.

## Files

- `scripts/compute_dh252_live_signals.py` - the comparison engine. Pure
  Python, no MCP dependency itself - takes a holdings snapshot + backtester's
  published signals + this folder's own trade log, produces
  `dhan_live_signals.json`.
- `data/holdings_snapshot.json` - normalized dump of your real Dhan
  holdings, overwritten on each run. Produced by a Claude Code session
  calling `mcp__claude_ai_dhan_mcp__portfolio_agent_tool` ("holdings") -
  that MCP call can only happen inside a Claude session, so it's not
  something this script does itself.
- `data/dh252_trade_log.json` - **the one persistent, hand-off-limits
  file, and the sole source of truth for "is this a dh252 position."**
  Dhan's holdings API has no concept of which strategy a position belongs
  to - it was wrongly assumed early on that "all Dhan holdings = dh252
  positions," which produced 6 wrong exit signals and several wrong
  add-on signals before the user caught it (2026-11-08). Re-seeded from
  the user's own real position export: 48 symbols with real entry dates,
  real add-on counts. Records every order this system places going
  forward (symbol, date, qty, price, action) - this is what makes the
  7-day add-on cooldown real over time, since Dhan's own MCP tools only
  expose today's trades/orders (confirmed empirically) - there is no
  other source for "when did I last buy this." A dh252 position present
  here with no matching current Dhan holding is treated as exited outside
  this system's tracking and dropped, not force-kept (surfaced in the
  output's `exited_outside_tracking` list).
- `data/dh252_positions_seed.json` - the raw parse of that real position
  export, kept for reference/re-seeding if the trade log ever needs
  rebuilding.
- `dhan_live_signals.json` - the output: entries (universe-wide candidates
  minus anything already a dh252 position, minus the permanent Dhan
  Option Hedge Portfolio exclusion below), exits (dh252 positions +
  Supertrend red, unconditional), add-ons (dh252 positions + P&L <= -6%
  + Supertrend green + cooldown satisfied), plus the current effective
  position-size tier. Overwritten on each run. This is what Phase 3's
  TradingJournal dashboard tab reads.

## Dhan Option Hedge Portfolio - permanent exclusion

**User's explicit instruction (2026-11-08, verbatim):** "keep this list as
Dhan Option Hedge Portfolio : INFY, BPCL, CGPOWER, BANKINDIA, BSE,
CUMMINSIND, SHRIRAMFIN, MCX, HCLTECH, DIXON, LIQUIDCASE and never include
in dh252 strategy .. both in entry and exit signals .. remember this."

These 11 symbols are a separate, unrelated portfolio sharing the same
Dhan account - never a dh252 position, never a dh252 entry candidate,
even if one of them later meets the 52-week-high + Supertrend-green
condition. Hardcoded as `DHAN_OPTION_HEDGE_PORTFOLIO` in
`compute_dh252_live_signals.py` and filtered out of entry signals
explicitly (exit/add-on are already scoped to `dh252_trade_log.json`'s
own positions, so these 11 never appear there by construction - the
entry filter is the one place they could otherwise leak back in).

## Running it today (on-demand, per the approved plan - not automated yet)

1. In a Claude Code session with the Dhan MCP tools available, call
   `portfolio_agent_tool` ("holdings") and update `data/holdings_snapshot.json`
   with the result.
2. Fetch backtester's latest `market_screens_full.json`, `supertrend_full.json`,
   `dh252_entry_signals.json` (from `raw.githubusercontent.com/vaijayanth/backtester/main/<file>`,
   or a local checkout).
3. Run:
   ```
   python scripts/compute_dh252_live_signals.py \
     --holdings data/holdings_snapshot.json \
     --market-screens <path to market_screens_full.json> \
     --supertrend <path to supertrend_full.json> \
     --entry-signals <path to dh252_entry_signals.json> \
     --trade-log data/dh252_trade_log.json \
     --out dhan_live_signals.json
   ```
   Sector + 🔥 hot-sector tagging uses `data/equity_sectors.json` (a copy of
   backtester's `data/equity_sectors.json`; re-copy it if sectors change).
4. Commit the updated `data/holdings_snapshot.json` and `dhan_live_signals.json`.

Promoting this to a scheduled cloud agent (instead of on-demand) is
explicitly deferred per the plan - not done yet.

## Not in scope yet

- No order placement (Phase 4) - this only reports, never executes.
- Position sizing stays the existing hardcoded tiering (Rs1,000 base);
  revisit later per the user's own stated intent.
- Zerodha - no MCP exists for it; this is Dhan-only.
