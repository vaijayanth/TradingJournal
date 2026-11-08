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
  file**. Records every order this system places going forward (symbol,
  date, qty, price, action). This is what makes the 7-day add-on cooldown
  real over time, since Dhan's own MCP tools only expose today's
  trades/orders (confirmed empirically 2026-11-08) - there is no other
  source for "when did I last buy this." Starts empty; a pre-existing
  Dhan position with no entry here is treated as cooldown-satisfied
  (confirmed policy) until this log records a real buy on it.
- `dhan_live_signals.json` - the output: entries (universe-wide candidates
  minus anything already held), exits (held + Supertrend red,
  unconditional), add-ons (held + P&L <= -6% + Supertrend green + cooldown
  satisfied), plus the current effective position-size tier. Overwritten
  on each run. This is what Phase 3's TradingJournal dashboard tab reads.

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
4. Commit the updated `data/holdings_snapshot.json` and `dhan_live_signals.json`.

Promoting this to a scheduled cloud agent (instead of on-demand) is
explicitly deferred per the plan - not done yet.

## Not in scope yet

- No order placement (Phase 4) - this only reports, never executes.
- Position sizing stays the existing hardcoded tiering (Rs1,000 base);
  revisit later per the user's own stated intent.
- Zerodha - no MCP exists for it; this is Dhan-only.
