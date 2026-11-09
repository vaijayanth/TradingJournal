---
name: refresh-zerodha
description: Refresh the VJ TradeIQ Zerodha workspace (Nifty F&O stocks, Supertrend strategy) - pull holdings, orders and today's trades from the Zerodha MCP, rebuild the signals, verify, and (after confirmation) commit and push. Use when the user says "refresh zerodha", "/refresh-zerodha", or wants the Zerodha pages updated with the latest data.
---

# Refresh Zerodha (Nifty F&O Supertrend strategy)

Run from the repo root of TradingJournal on branch `claude/beautiful-hamilton-fwa55n`. Needs Python 3.10+ and the Zerodha MCP connector (claude.ai account). Everything lives under `zerodha-live/`. The OLD Google-Sheet dashboard (the "Sheet Dashboard" tab) is separate and untouched by this skill.

## The strategy this skill feeds (user, 2026-11-09)
- Universe: Nifty F&O stocks (`data/fno_universe.json`, re-downloaded from NSE whenever the stored list is from an earlier month). Holdings in any other stock are ignored completely.
- Entry: Supertrend flipped to green within the last 3 trading days and no open position in the stock. Size Rs 20,000 per position, +Rs 5,000 for every 100 trades (open + closed), floored to whole shares (min 1).
- Exit: Supertrend red, any profit or loss, whole position. Grandfathered: a position held at the baseline cut-off (`baseline_from_sheet.json` -> `cutoff_date`) only gets an exit signal once its Supertrend turns red AFTER that date.
- Add: Supertrend green and the position down 6% or more (P&L <= -6%, same as ND) -> 1/10 of the current quantity (min 1), once every 7 days.
- Fixed capital base Rs 30,00,000. Closed-trade P&L is gross of charges.

## Scope (user, 2026-11-09)
- The dashboard's open positions are ONLY the stocks in `data/moved_from_sheet.json` plus positions opened through it later (`zerodha_trades.py buy --entry`). All other Zerodha holdings are ignored, but any holding still blocks a new entry in that stock. `data/excluded_symbols.json` (BSE, BEL, RECLTD) is excluded entirely. The sheet's closed trades are not part of this dashboard.
- When the user moves more trades from the sheet, add the symbols to `moved_from_sheet.json` (and tell them to delete the rows from the sheet); never re-run `freeze_baseline.py`.

## Steps
1. **Prep.** `git status`, `git pull --ff-only`. Stop and tell the user if the tree has unrelated uncommitted changes. If `data/baseline_from_sheet.json` does not exist, run `python zerodha-live/scripts/freeze_baseline.py` ONCE (never again; re-freezing double counts).
2. **Zerodha login.** Call `mcp__claude_ai_Zerodha_Mcp__get_holdings` with `limit: 1`. If it says to log in (or "Failed to execute"), call `mcp__claude_ai_Zerodha_Mcp__login`, show the user the warning text it returns plus the link, and wait for them to confirm they authorised it.
3. **Holdings.** Call `get_holdings` with no limit (the result is large; the tool saves it to a file and prints the path - read it with Python, never paste it). Write `zerodha-live/data/holdings_snapshot.json` as `{"fetched_at": <ISO now, +05:30>, "source": "...get_holdings (quantity + t1_quantity)", "holdings": [{"symbol": tradingsymbol, "qty": quantity + t1_quantity, "avg_cost": average_price, "invested": qty*average_price, "exchange", "product"}]}` keeping only rows with qty > 0. Keep ALL holdings; the engine drops stocks outside the F&O universe.
4. **Today's trades.** `get_trades` (today only - run this every trading day or the fills are lost). For each BUY of an F&O-universe stock: `python zerodha-live/scripts/zerodha_trades.py buy --symbol <SYM> --date <YYYY-MM-DD> [--entry]` (`--entry` only when it OPENS a new position, i.e. the stock was not held before today). SELL fills of a position that has a `pending_exits` record: `python zerodha-live/scripts/zerodha_trades.py fill --symbol <SYM> --qty <qty> --price <avg fill price> --date <date>` (whole-position exits only). A SELL with no pending record: tell the user and ask for the position's average cost and entry date before recording; never guess.
5. **Order snapshot.** `get_orders`; rewrite `zerodha-live/data/orders_snapshot.json` (`fetched_at`, `source`, `orders[]` with `order_id, symbol, side, qty, order_type, price (null for market), status, amo, placed`) with the orders still pending/open; drop filled, rejected or cancelled ones. The Dashboard and Live Trading read this for the "Ordered / Not ordered" status.
5b. **Option positions (covered call).** Call `mcp__claude_ai_Zerodha_Mcp__get_positions` (no limit; the result is large and is saved to a file - never paste it) and run `python zerodha-live/scripts/cc_positions.py <that file>`. It keeps only stock-option legs with an expiry on/after `track_from` in `data/cc_config.json` (November 2026 onwards since 2026-11-09; earlier expiries are ignored; the positions call returns a day list then a net list, cc_positions.py keeps the net row). No option quotes are pulled.
5c. **Live prices for the strike alerts (MANDATORY every refresh, do not skip).** After 5b, call `mcp__claude_ai_Zerodha_Mcp__get_ltp` with `NSE:<SYMBOL>` for every symbol in `data/cc_positions.json` legs (one call), save the raw output to a scratch file and run `python zerodha-live/scripts/cc_prices.py <file>`. The covered-call engine then uses these (same day only) for near/breached strike alerts; with no same-day file it falls back to the last close, which can be wrong by hours or a day. Always say in the report whether live prices were pulled and at what time.
5d. **GTT list (for the 'No GTT placed' alert).** Call `mcp__claude_ai_Zerodha_Mcp__get_gtts` (large; saved to a file), then `python zerodha-live/scripts/cc_gtts.py <that file>`. Then run `python zerodha-live/scripts/scan_gtts.py`: it checks every active option GTT for invalid ones (stale GTT on a closed contract, wrong side, wrong quantity, duplicates, bad triggers, off-rule stop, early expiry) and the result shows as 'Invalid GTT' alerts and guardrail P5. Report the count and the HIGH ones in the verify step; fixing them is the `zerodha-gtt-order` skill, only when the user asks. A short option leg with no ACTIVE buy-back GTT on its contract raises 'No GTT placed'; without a same-day GTT file that check is skipped (and the page says so), never reported as passed.
6. **Rebuild.** `python zerodha-live/scripts/refresh_zerodha.py` (monthly F&O list refresh, backtester screens, signal engine, covered-call signals; it appends today's point to `data/equity_history.json`, which is what the Performance equity curve is built from).
7. **Verify before committing - report these to the user:**
   - Market data date is the latest trading day (not older than the previous session).
   - Counts: holdings in scope vs total, exits / add-ons / entries, trades -> tier size, realised + unrealised P&L. Flag anything surprising (an exit that is not Supertrend red, an add-on that is not at -6% or worse, an entry with a flip older than 3 trading days = a bug; investigate, do not publish).
   - The reconciliation line: stocks whose Zerodha holdings quantity differs from the sheet's open quantity at the cut-off (`reconciliation.differences`) - informational; the holdings are the truth.
   - `no_data` stocks (no backtester price/Supertrend) and whether the F&O list changed this month (added/removed names).
   - If many entry signals appear at once, say how much capital they would need versus the Rs 30,00,000 base and how much is already deployed.
8. **Commit + push only after the user says push.** Stage only `zerodha-live/` files (never `.playwright-mcp/`). Message: `Zerodha refresh <market date>`.

## Guardrails (hard rules, added 2026-11-09)
- The rebuild now ends with `guardrails.py (zerodha-live)` (checks and balances: freshness, fill ledger vs holdings, signal logic re-derived, capital/concentration, orders, options, broker separation, kill switch) and `test_guardrails.py (zerodha-live)` (every check must still fire). Report the line `GUARDRAILS <broker>: OK|WARN|BLOCK` and every BLOCK/WARN it prints in the verify step. The same result drives the banner on the pages and refuses order tickets.
- Settlement timing: Zerodha has no fill ledger (holdings from the MCP are the truth), so there is no I3 check; Dhan holdings can lag the day's fills; the engine then warns (I3 WARN) and the positions/P&L exclude those stocks until holdings catch up. That is expected; a BLOCK (I3 with no recent buy) is a real missed fill.
- Never commit/push while a BLOCK is open without telling the user and getting their explicit go-ahead.
- `data/trading_halt.json` is the user's kill switch; do not flip it without being asked.

## Rules (do not change without the user)
- Nifty F&O stocks only. Never invent numbers; if a source is missing, say so.
- The Google Sheet is NEVER re-read after the baseline is frozen.
- Orders are not placed by this skill.
