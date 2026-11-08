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

## Refreshing (Dhan)

Run the `refresh-dhan` skill (`.claude/skills/refresh-dhan/SKILL.md`, in this repo so it works on any
clone) in a Claude Code session with the Dhan MCP connected. It pulls holdings + today's fills over MCP,
then runs `python dhan-live/scripts/refresh_dhan.py`, which downloads backtester's published
`market_screens_full.json` / `supertrend_full.json`, derives entry signals with the vendored
`dh252_entry_screener.py`, rebuilds yfinance closes + SMA50/200 and regenerates `dhan_live_signals.json`.

The MCP tradebook returns today's trades only: run the refresh every trading day, or catch up from a Dhan
*Global Transaction Report* CSV with `scripts/import_dhan_transactions.py`. Sector + hot-sector tags use
`data/equity_sectors.json` (copy of backtester's; re-copy if sectors change). Scheduling is not set up.

## Covered Call Hedging page

`scripts/compute_covered_call.py` (run by `refresh_dhan.py`) writes `covered_call_signals.json` for the Covered Call
page. Config/rules: `data/cc_config.json` (universe, lot sizes, delta targets, 3x stop, expiry cut-off).
Optional `data/cc_tags.json` enables the Supertrend-flip stop per stock. Raw MCP text inputs live in
`data/cc_raw/` (`positions.txt`, `chains/<SYMBOL>_<EXPIRY>.txt`); the engine says which chains it still needs.

## Not in scope yet

- No order placement (Phase 4) - this only reports, never executes.
- Position sizing stays the existing hardcoded tiering (Rs1,000 base);
  revisit later per the user's own stated intent.
- Zerodha - no MCP exists for it; this is Dhan-only.
