---
name: dhan-order-exit
description: Place Dhan AFTER-MARKET (next trading day) SELL orders to exit dh252 STOCK positions whose Supertrend turned red, after showing an order ticket and getting an explicit yes. Stocks only, never options. Use only when the user explicitly asks to place/execute exit orders ("/dhan-order-exit", "exit ZYDUSLIFE", "sell the exit signals").
disable-model-invocation: true
---

# dhan-order-exit — real-money after-market SELL orders for dh252 exit signals

This skill places REAL orders on the user's Dhan account through the Dhan MCP. The user's routine: signals are computed after the close and orders go in as after-market orders (AMO) for the NEXT trading day. Zerodha will get its own `zerodha-order-exit`; keep Dhan specifics here.

## Scope (hard limits)
- Stocks only. Never options, the option-hedge / investment portfolio, or any stock without a current EXIT signal in `dhan-live/dhan_live_signals.json` (`exits`, i.e. Supertrend red). If the user names a stock with no exit signal, refuse and say why (partial sells and discretionary exits are out of scope).
- The whole open position is sold - quantity comes from `build_order_ticket.py`, which also checks it equals the Dhan holdings quantity. Never sell more than held.
- AFTER-MARKET (AMO) LIMIT orders only, CNC (delivery). Never market orders. Never during market hours (see step 3).
- One explicit user confirmation for the exact batch shown; any change = show again and re-confirm. Never place on an implied or earlier "yes".
- Never retry a rejected order, never modify or cancel without being asked.

## Steps
1. **Which stocks.** If the user did not name stocks, show the exit list and ask which.
2. **Fresh data - after the close.** Signals must be the day's final ones: the backtester's "Daily OHLC Update" publishes after the close (around 16:00 IST; run it from GitHub Actions if needed), then `/refresh-dhan`. Check `market_data_date` is the session that just ended. Run `portfolio_agent_tool` holdings and confirm each stock's quantity and that `avail` (not T1/pledged) covers the sale - if available qty < qty, stop and tell the user.
3. **Market must be closed.** NSE equity trades Mon-Fri 09:15-15:30 IST (plus announced special sessions). If the market is OPEN now, stop: tell the user to run this after the close.
4. **Tickets.** `python dhan-live/scripts/build_order_ticket.py exit [--symbols A,B]` -> read `TICKETS_JSON=`.
5. **Reference price + guard.** `search_agent_tool` `{"query":"<SYMBOL>-EQ"}` for the NSE `EQUITY` securityId, then `market_data_agent_tool` `ltp` `{"NSE_EQ":[<id>]}` (after the close this is the closing price). If it differs from the ticket's `ref_price` by more than 3%, stop and ask.
6. **Limit price.** SELL: reference price x 0.995, rounded DOWN to the 0.05 tick (a 0.5% buffer for tomorrow's opening gap). Say plainly that a bigger gap-down than that means the order will not fill and the position stays open. The user may override the price.
7. **Ticket + confirmation.** Table: symbol, SELL, qty, limit, est. proceeds, reason, P&L %, total, and the line "AFTER-MARKET order for the next trading day - the position will be fully closed if it fills". Ask the user to reply "yes, place these" and wait.
8. **Place.** For each ticket, `trading_agent_tool` action `place` with `{"exchangeSegment":"NSE_EQ","transactionType":"SELL","quantity":<q>,"productType":"CNC","securityId":"<id>","price":<limit>,"orderType":"LIMIT","validity":"DAY","afterMarketOrder":true,"amoTime":"OPEN"}` (Dhan's AMO options are PRE_OPEN / OPEN / OPEN_30 / OPEN_60; use OPEN unless the user says otherwise). These field names follow Dhan's API and have not yet been confirmed through this MCP: on any validation error STOP and report it verbatim - do not guess other fields. Stop at the first rejection and report what did and did not go through.
9. **Verify the order is accepted.** `orderbook_agent_tool` for each order's status (pending until the next session). Report order id and status. Nothing has filled yet - do not say it has.
10. **Record the fills NEXT trading day.** The MCP tradebook is today-only, so on the next trading day (after the open) run `/refresh-dhan`: its tradebook step records the SELL fills with `append_fills.py` and the position becomes a closed trade. Unfilled orders stay out of the trade log. Remind the user of this at the end of the placement.

## Reporting
Plain: placed (as AMO) / status / still pending / failed. Never call a pending AMO filled.
