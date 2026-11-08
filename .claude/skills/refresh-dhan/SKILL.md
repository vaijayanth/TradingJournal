---
name: refresh-dhan
description: Refresh the VJ TradeIQ Dhan (dh252) workspace - pull holdings and today's fills from the Dhan MCP, rebuild closes/SMAs/signals, verify, and (after confirmation) commit and push. Use when the user says "refresh dhan", "/refresh-dhan", or wants the Dhan pages updated with latest data.
---

# Refresh Dhan (dh252)

Run from the repo root of TradingJournal on branch `claude/beautiful-hamilton-fwa55n`. Needs Python 3.10+ with pandas + yfinance, and the Dhan MCP connector (claude.ai account). Everything lives under `dhan-live/`.

## Steps

1. **Prep.** `git status`, `git pull --ff-only` on the branch. Stop and tell the user if the tree has unrelated uncommitted changes.
2. **Dhan login check.** Call `mcp__claude_ai_dhan_mcp__portfolio_agent_tool` (action `holdings`). If it reports not logged in / expired, call the MCP `login` tool, give the user the link, wait for them to approve (`complete_login` if it asks for a code - never ask the user to paste tokens into chat beyond what that flow requires).
3. **Holdings.** Write the result to `dhan-live/data/holdings_snapshot.json` as
   `{"fetched_at": <ISO now, +05:30>, "source": "mcp__claude_ai_dhan_mcp__portfolio_agent_tool (holdings)", "holdings": [{"symbol","qty","avg_cost","invested"}, ...]}`. Keep ALL holdings (the hedge portfolio is filtered by the engine).
4. **Today's fills.** `mcp__claude_ai_dhan_mcp__tradebook_agent_tool` action `list`. The MCP returns **today's trades only**, so this must run every trading day or fills are lost. If there are equity trades, build a JSON list `[{"symbol","date":"YYYY-MM-DD","action":"BUY|SELL","qty","price","order_id"}]` in the scratchpad (equity only - drop any option/F&O rows) and run
   `python dhan-live/scripts/append_fills.py <that file>`.
   If days were missed: ask the user for a Dhan *Global Transaction Report* CSV and run
   `python dhan-live/scripts/import_dhan_transactions.py --csv <csv> --holdings dhan-live/data/holdings_snapshot.json --trade-log dhan-live/data/dh252_trade_log.json` (full replace of fills; equity only, excludes the investment/option-hedge portfolio and pre-21-Oct-2026 sells). It stops and lists unresolved names - add them to `data/dhan_name_map.json`, never guess.
4a. **Share averaging record.** From the same tradebook output, for any BUY of a Covered Call universe stock (keys of `dhan-live/data/cc_config.json` -> `universe`: MCX, SHRIRAMFIN, CGPOWER, BSE, DIXON, HCLTECH, INFY, BANKINDIA, BPCL, CUMMINSIND) set `last_add[SYMBOL] = <trade date>` in `dhan-live/data/cc_adds.json`. The averaging rule (green Supertrend, loss >= 6%, 1/10 of open qty, once every 7 days) uses this; the MCP tradebook is today-only, so a missed day means a missed add. If the user says they averaged a stock earlier, record that date too.
4a2. **Investment-share SELL fills.** For any SELL of a Covered Call universe stock in the same tradebook output, check `dhan-live/data/invest_trades.json` `pending_exits` for that symbol (written by `dhan-invest-order-exit` when the order was placed). If one exists and the SELL fully filled, compute the average fill price and run `python dhan-live/scripts/invest_trades.py fill --symbol <SYM> --qty <qty> --price <avg fill price> --date <fill date>`; this books the profit (gross of charges) that sizes the next entry. If a universe SELL has no pending record, do NOT guess its capital: tell the user and ask for the position's average cost before recording. If a pending exit did not fill, leave it and say so.
4a3. **Order snapshot.** `mcp__claude_ai_dhan_mcp__orderbook_agent_tool` action `list`; rewrite `dhan-live/data/orders_snapshot.json` (`fetched_at`, `source`, and `orders[]` with `order_id, symbol, side, qty, order_type, price (null for market), status, amo`) with the orders still PENDING; drop orders that filled, were rejected or lapsed. The Dashboard and Live Trading read this file for the "Ordered / Not ordered" status; if it is stale the page shows old status.
4b. **Covered Call page inputs.** (a) `mcp__claude_ai_dhan_mcp__portfolio_agent_tool` action `positions` -> save the raw text result **verbatim** to `dhan-live/data/cc_raw/positions.txt` (overwrite). Option positions are never copied anywhere else. (b) Chains are fetched in step 5b only for stocks that need a suggestion.
5. **Rebuild.** `python dhan-live/scripts/refresh_dhan.py` (fetches backtester screens, derives entry signals, rebuilds yfinance closes + SMA50/200, regenerates `dhan_live_signals.json`).
5b. **Option chains (only if the run printed `CHAINS NEEDED`).** For each listed symbol call `mcp__claude_ai_dhan_mcp__market_data_agent_tool` action `optionchain` with payload `{"UnderlyingScrip": <security_id>, "UnderlyingSeg": "NSE_EQ", "Expiry": "<expiry>"}` and save the raw text to `dhan-live/data/cc_raw/chains/<SYMBOL>_<EXPIRY>.txt` (delete older chain files first; rows that are all zeros may be omitted, nothing else edited). Then `python dhan-live/scripts/refresh_dhan.py --cc-only`. Expiry dates come from `expirylist` (update `expiries` in `data/cc_config.json` when a new series appears). Lot sizes in `cc_config.json` come from open positions; if a stock has `lot: null`, say so rather than guessing.
6. **Verify before committing - report these to the user:**
   - The engine prints no `WARNING` (a drift warning means fills and holdings disagree: a missed fill, or a position that exited outside tracking).
   - Open positions in scope == holdings qty/WAC for every dh252 symbol (the engine's 48-style count; any `exited_outside_tracking` list must be empty or explained).
   - Market data date and SMA as-of date are the latest trading day (not older than the previous session).
   - Signal cross-check (`data/signal_crosscheck.json`, printed by the refresh): list every FLAG with its reason. Flags mean the published signal disagrees with a recompute on complete Yahoo history (stale/holey backtester prices, a different closing high, or a missing bar) - such signals are blocked from orders. If many flags appear at once, suspect the backtester's price history (missing bars) before blaming the stocks.
   - Counts: exits / add-ons / entries / closed trades / realised + unrealised P&L. Flag anything surprising (an add-on with P&L > -6%, an exit that isn't Supertrend red, etc. means a bug - investigate, don't publish).
   - Covered Call: report the Options alerts (EXIT / WARN / ENTER) and the Shares tab signals (entry signals, averaging due), that the options MTM ties to Dhan's "Unrealized P&L" in the positions output, and which stocks still have no chain or lot size. Deltas are Black-Scholes estimates from the chain's IV (no dividends) - say so.
7. **Commit + push only after the user says push.** Stage only `dhan-live/` files (never `.playwright-mcp/`). Message: `Dhan refresh <market date>`.

## Rules (do not change without the user)
- Fixed capital base 20,00,000; deposits ignored. Closed-trade P&L is gross of charges.
- Equity only; the option-hedge portfolio and investment portfolio are never dh252.
- Never invent numbers; if a source is missing, say so.
- Zerodha / ICICI are out of scope for this skill.
