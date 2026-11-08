---
name: dhan-invest-order-entry
description: Place Dhan AFTER-MARKET (next trading day) BUY orders for the INVESTMENT portfolio SHARES (the 10 covered-call stocks) - new entries after a Supertrend red-to-green flip, and weekly averaging - after showing an order ticket and getting an explicit yes. Shares only, never options, never dh252 stocks. Use only when the user explicitly asks ("/dhan-invest-order-entry", "average INFY", "buy the investment-portfolio entries").
disable-model-invocation: true
---

# dhan-invest-order-entry - real-money after-market BUY orders for the investment-portfolio shares

This places REAL orders on the user's Dhan account through the Dhan MCP. It covers only the investment-portfolio shares in `dhan-live/data/cc_config.json` (`universe`; currently MCX, SHRIRAMFIN, CGPOWER, BSE, DIXON, HCLTECH, INFY, BANKINDIA, BPCL, CUMMINSIND). The dh252 stocks use `dhan-order-entry`; option orders have their own skill. Orders go in after the close as AFTER-MARKET (AMO) orders for the NEXT trading day.

## Strategy (user, 2026-11-08)
- **Entry:** when a stock's Supertrend flips from red to green and you do not hold it, buy with **the last position's capital plus the profit earned on that same stock in the previous trade** (profit is reinvested). Quantity = that amount divided by the close, floored to whole shares, minimum 1 (computed by `compute_covered_call.py` from `dhan-live/data/invest_trades.json`, written by the exit skill).
- **Averaging:** once a week per stock, when the Supertrend is green and the open position's loss is worse than -6% vs average cost. Quantity = 1/10 of the holding, minimum 1.
- **Exit** (for context): Supertrend red AND in profit, whole position (`dhan-invest-order-exit`).

## Scope (hard limits)
- Shares only. Never options, futures, ETFs, any stock outside the universe, or any dh252 stock.
- Only what `python dhan-live/scripts/build_share_ticket.py` lists: `entry` (red-to-green flips, sized by the rule) and `add` (averaging due). Quantities come from the script; never suggest, change or invent one. Exception: if a flipped stock has NO previous trade recorded in `invest_trades.json`, the rule gives no size and the script requires `--qty SYMBOL=N` from the user; ask for it, never default it. If the user names a stock with no signal, refuse.
- AMO LIMIT orders, CNC. Never market orders. Never during market hours.
- One explicit user confirmation for the exact batch shown; any change = show the ticket again and re-confirm. Never place on an implied or earlier "yes".
- Never retry a rejected order, never modify or cancel without being asked, never place while a refresh is running.

## Steps
1. **List, every time.** EVERY invocation, re-run the script and print the FULL numbered tables again, all rows, even if shown earlier - never write "same as before". Run `python dhan-live/scripts/build_share_ticket.py entry` and `python dhan-live/scripts/build_share_ticket.py add` (after steps 2-3). Show: number, stock, kind (entry / add), qty, reference price, est. value, held qty, reason (for entries: the previous capital + profit it is sized from). Directly under the tables show a **capital check**: from `portfolio_agent_tool` action `funds` the available balance, withdrawable cash and collateral; the est. value of ALL listed buys; and that as a % of available balance and of withdrawable cash. Say plainly that most of the balance is collateral, not cash. Then ask once: "Reply with the numbers to place - e.g. `1,3` - or `all entries`, `all adds`." (Entries and adds are numbered separately; say which list.) Echo the choice back. Never default to everything. Refuse any stock not in the list.
2. **Fresh data, after the close.** `/refresh-dhan` must have run for the session that just ended; check `market_data_date`. The script refuses data older than 3 days.
3. **Market must be closed.** NSE equity trades Mon-Fri 09:15-15:30 IST (plus announced special sessions). If it is open, stop. (Weekend/holiday/after 15:30 IST = continue in AMO mode.)
4. **Tickets.** `build_share_ticket.py entry --pick <n> [--qty SYMBOL=N]` and/or `build_share_ticket.py add --pick <n>`. Read `TICKETS_JSON=`.
5. **Day range + guard.** `search_agent_tool` `{"query":"<SYMBOL>-EQ","exchange":"NSE"}` for the NSE EQUITY securityId (also in `cc_config.json`), then `market_data_agent_tool` `ohlc` `{"NSE_EQ":[<ids>]}` (one call for the batch). If the close differs from the ticket's reference price by more than 3%, stop and ask.
6. **Limit price = the signal day's HIGH, capped at close + 2%** (the user's rule for the dh252 skills, reused here). Limit = min(high, close x 1.02), the cap rounded DOWN to the 0.05 tick. Show close, high, cap and the limit side by side, and mark rows where the cap applied. Say plainly that a limit order fills at the open when the stock opens at or below it, so you normally pay the open; on a gap-up it can fill up to the limit, and above the limit it will not fill. For an entry sized from capital + profit, the share count is fixed by the rule; the limit only caps the price. The user may override the price.
7. **Funds.** `margin_agent_tool` action `single` (NOT `multi`, which returned 0) with `{"exchangeSegment":"NSE_EQ","transactionType":"BUY","quantity":<q>,"productType":"CNC","securityId":"<id>","price":<limit>}` for each order; CNC needs the full order value. Compare the batch total with Available Balance and withdrawable cash. Ignore its "Insufficient Balance" line (nonsense). Stop if funds are short.
8. **Ticket + confirmation.** Table: symbol, BUY, kind, qty, limit, est. value, reason; the batch total next to available balance and withdrawable cash; the line "AFTER-MARKET order for the next trading day". Ask the user to reply "yes, place these" and wait.
9. **Place.** For each ticket, `trading_agent_tool` action `place` with `{"exchangeSegment":"NSE_EQ","transactionType":"BUY","quantity":<q>,"productType":"CNC","securityId":"<id>","price":<limit>,"orderType":"LIMIT","validity":"DAY","afterMarketOrder":true,"amoTime":"OPEN"}`. The MCP's own pre-trade funds check is BROKEN (it blocked a 1-share order with a sign-flipped "shortfall" while the account had 30 lakh available). If `place` is blocked as "insufficient funds" and step 7 shows the funds are fine, tell the user once, show the message, and only after their yes add `"preflight": false`. On any other error STOP and report it verbatim; do not guess fields. Place one order first, check it with `orderbook_agent_tool` (PENDING, no error), then place the rest, stopping at the first rejection.
10. **Verify.** `orderbook_agent_tool` list: report order id and status per stock. Nothing has filled - never say it has.
11. **After the open.** Run `/refresh-dhan` on the next trading day: the tradebook BUYs update `dhan-live/data/cc_adds.json` (the weekly averaging cooldown) and the holdings. Orders that did not fill do not count. Remind the user of this.

## Reporting
Plain: placed (as AMO) / status / still pending / failed. Never call a pending AMO filled.
