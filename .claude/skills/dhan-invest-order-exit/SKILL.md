---
name: dhan-invest-order-exit
description: Place Dhan AFTER-MARKET (next trading day) SELL orders to exit INVESTMENT-portfolio SHARES (the 10 covered-call stocks) whose Supertrend turned red while the position is in profit, after showing an order ticket and getting an explicit yes. Shares only, never options, never dh252 stocks. Use only when the user explicitly asks ("/dhan-invest-order-exit", "exit the investment-portfolio profit exits").
disable-model-invocation: true
---

# dhan-invest-order-exit - real-money after-market SELL orders for investment-portfolio shares

This places REAL orders on the user's Dhan account through the Dhan MCP. It covers only the investment-portfolio shares in `dhan-live/data/cc_config.json` (`universe`; currently MCX, SHRIRAMFIN, CGPOWER, BSE, DIXON, HCLTECH, INFY, BANKINDIA, BPCL, CUMMINSIND). dh252 exits use `dhan-order-exit`; option orders have their own skill. Orders go in after the close as AFTER-MARKET (AMO) orders for the NEXT trading day.

## Strategy (user, 2026-11-08)
**Exit when the Supertrend is red AND the position is profitable.** The whole position is sold. A red stock that is in loss is HELD, not sold. The profit made here is reinvested: the next entry in the same stock is sized at this position's capital plus this profit (see `dhan-invest-order-entry`), which is why the capital and profit are recorded in steps 8 and 12.

## Scope (hard limits)
- Shares only. Never options, futures, ETFs, any stock outside the universe, or any dh252 stock.
- Only stocks in `shares.exits` of `dhan-live/covered_call_signals.json`, listed by `python dhan-live/scripts/build_share_ticket.py exit` (red and in profit). If the user names a stock with no exit signal, refuse and say why (red but in loss = hold; green = no exit; partial sells and discretionary sells are out of scope).
- The whole open position: quantity comes from the script (shares held). Never sell more than held, never a partial quantity.
- AMO MARKET orders, CNC (the same convention as the dh252 exit skill: when the exit rule fires, the position is sold at the next open whatever the price). No limit price unless the user explicitly gives one. Never during market hours.
- One explicit user confirmation for the exact batch shown; any change = show again and re-confirm. Never place on an implied or earlier "yes".
- Never retry a rejected order, never modify or cancel without being asked.

## Steps
1. **List, every time.** EVERY invocation, re-run the script and print the FULL numbered table again, all rows, even if it was shown earlier - never write "same as before". Columns: number, stock, qty, reference price, est. proceeds, profit (Rs and %), red since. If the list is empty, say so and show the red-but-in-loss stocks as "held, no exit" for context. Ask once: "Reply with the numbers to exit - e.g. `1,2` - or `all`." Echo the choice back. Never default to everything. Refuse any stock not in the list.
2. **Fresh data, after the close; live holdings.** `/refresh-dhan` must have run for the session that just ended (the script refuses data older than 3 days). Run `portfolio_agent_tool` action `holdings` and confirm each stock's quantity and that `avail` (not T1 or pledged) covers the sale. If available quantity < quantity, stop and tell the user.
3. **Market must be closed.** NSE equity trades Mon-Fri 09:15-15:30 IST (plus announced special sessions). If it is open, stop.
4. **Ticket.** `python dhan-live/scripts/build_share_ticket.py exit --pick <numbers>`. Read `TICKETS_JSON=` (it carries `avg_cost`, `capital`, `profit_est`) and any `WARNING` / `NOTE` lines.
5. **Option-leg check.** The script reports the open short-call quantity for the stock. A WARNING means the sale uncovers a call that is covered today: show it prominently and require the user to acknowledge it in their confirmation. A NOTE (call already larger than the holding) is information. Never touch the option legs.
6. **Conflicting orders.** `orderbook_agent_tool` list: if an open SELL for the same stock already exists (for example a manual order from a special session), stop and tell the user: the combined quantity could exceed the holding. Let them decide whether to cancel it (never cancel it yourself).
7. **Reference price.** `search_agent_tool` `{"query":"<SYMBOL>-EQ","exchange":"NSE"}` for the NSE EQUITY securityId (also in `cc_config.json`), then `market_data_agent_tool` `ohlc` `{"NSE_EQ":[<ids>]}` (the finished session). If the close differs from the ticket's reference by more than 3%, show a warning (it does not stop the order). Say plainly the fill is whatever the market gives at the open, which can be far from the close on a gap-down, and that a gap-down could turn the profit into a loss.
8. **Ticket + confirmation.** Table: symbol, SELL, qty, MARKET (AMO), est. proceeds at the close, capital (qty x average cost), estimated profit this books, any short-call warning, and the line "AFTER-MARKET order for the next trading day - the position will be fully closed at the opening price". Ask the user to reply "yes, place these" and wait.
9. **Record the capital BEFORE placing.** For each ticket run `python dhan-live/scripts/invest_trades.py pending --symbol <SYM> --qty <qty> --avg-cost <avg_cost> --date <today>`. This captures the position's capital while the holdings snapshot still has it (the next `/refresh-dhan` replaces it).
10. **Place.** `trading_agent_tool` action `place` with `{"exchangeSegment":"NSE_EQ","transactionType":"SELL","quantity":<q>,"productType":"CNC","securityId":"<id>","price":0,"orderType":"MARKET","validity":"DAY","afterMarketOrder":true,"amoTime":"OPEN"}`. The MCP's own pre-trade funds check is BROKEN: it can block a SELL (which needs no margin) with a bogus "shortfall" equal to the whole balance. If `place` is blocked that way, tell the user once, show the message, and only after their yes add `"preflight": false`. On any other error STOP and report it verbatim; do not guess fields. Place one order first, check it, then place the rest, stopping at the first rejection. If an order is rejected, remove its pending record: `invest_trades.py` keeps only the latest pending per stock, so re-run the correct one or tell the user.
11. **Verify.** `orderbook_agent_tool` list/get: report order id and status per order. Nothing has filled - never say it has.
12. **After the open, record the fill.** On the next trading day, once the SELLs have filled, get the average fill price from `tradebook_agent_tool` (list, today's trades) and run `python dhan-live/scripts/invest_trades.py fill --symbol <SYM> --qty <qty> --price <avg fill price> --date <fill date>`. This books the profit (gross of charges) and is what sizes the next entry. THEN run `/refresh-dhan` so holdings and signals update. If the order did not fill, do not record a fill; tell the user the pending record stays until it does or is cleared. Remind the user of this at the end of the placement.

## Reporting
Plain: placed (as AMO) / status / still pending / failed. Never call a pending AMO filled.
