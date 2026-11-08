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
5. **Rebuild.** `python dhan-live/scripts/refresh_dhan.py` (fetches backtester screens, derives entry signals, rebuilds yfinance closes + SMA50/200, regenerates `dhan_live_signals.json`).
6. **Verify before committing - report these to the user:**
   - The engine prints no `WARNING` (a drift warning means fills and holdings disagree: a missed fill, or a position that exited outside tracking).
   - Open positions in scope == holdings qty/WAC for every dh252 symbol (the engine's 48-style count; any `exited_outside_tracking` list must be empty or explained).
   - Market data date and SMA as-of date are the latest trading day (not older than the previous session).
   - Counts: exits / add-ons / entries / closed trades / realised + unrealised P&L. Flag anything surprising (an add-on with P&L > -6%, an exit that isn't Supertrend red, etc. means a bug - investigate, don't publish).
7. **Commit + push only after the user says push.** Stage only `dhan-live/` files (never `.playwright-mcp/`). Message: `Dhan refresh <market date>`.

## Rules (do not change without the user)
- Fixed capital base 20,00,000; deposits ignored. Closed-trade P&L is gross of charges.
- Equity only; the option-hedge portfolio and investment portfolio are never dh252.
- Never invent numbers; if a source is missing, say so.
- Zerodha / ICICI are out of scope for this skill.
