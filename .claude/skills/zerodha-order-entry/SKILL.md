---
name: zerodha-order-entry
description: Place Zerodha (AZ) AFTER-MARKET (next trading day) BUY orders for the Nifty F&O Supertrend STOCK signals (entry signals and add-on signals) after showing an order ticket and getting an explicit yes. Stocks only, never options or GTTs. Use only when the user explicitly asks to place/execute AZ entry or add-on orders ("/zerodha-order-entry", "place AZ entry orders", "buy the Zerodha add-ons").
disable-model-invocation: true
---

# zerodha-order-entry - real-money after-market BUY orders for the AZ (Zerodha) signals

This skill places REAL orders on the user's Zerodha account through the Zerodha MCP (`mcp__claude_ai_Zerodha_Mcp__*`). The routine: signals are computed after the close and orders go in as AMO (after-market) orders for the NEXT trading day. It is the AZ twin of `dhan-order-entry`; the two share no code or data (ND and AZ are separate). Exits are the `zerodha-order-exit` skill; option GTTs are not part of this one (`zerodha-gtt-order` handles protective option GTTs).

## The AZ strategy these orders come from (user rules, 2026-11-09)
- Universe: Nifty F&O stocks (`zerodha-live/data/fno_universe.json`), minus `excluded_symbols.json` (BSE, BEL, RECLTD).
- **Entry:** Supertrend flipped to green within the last 3 trading days and NO holding in that stock anywhere in the account. Size = Rs20,000 per position (+Rs5,000 for every 100 trades, open + closed), floored to whole shares, minimum 1 (so a stock priced above the tier costs more than the tier).
- **Which flips are ordered (user, 2026-11-09):** only the FRESHEST flip day. If today's flips (age 0) have orderable signals, only those are listed; if there are none, only yesterday's (age 1), then the day before, and so on within the 3-day window. Older flips are hidden (`build_order_ticket.py --all-days` shows them, only when the user asks). Add-ons are not flip signals and are always listed. A blocked signal does not count as orderable, so if today's only flip is blocked the list falls back to the next day.
- **Add-on:** a position this dashboard tracks, Supertrend green and P&L at -6% or worse (same rule as ND, user 2026-11-09): buy 1/10 of the quantity (minimum 1), once every 7 days.
- Fixed capital base Rs30,00,000.

## Scope (hard limits)
- Stocks only. Never options, futures, ETFs, GTTs, SELLs or exits (`zerodha-order-exit` does those), or any excluded symbol.
- Only symbols in the current signal file (`zerodha-live/zerodha_live_signals.json`) as `entries` or `addons`, as listed by `python zerodha-live/scripts/build_order_ticket.py`. Quantity is whatever that script says, never a number the user or you make up. A stock with no signal is refused.
- AMO LIMIT orders only, CNC (delivery), exchange NSE (never BSE). Never market orders. Never during market hours (step 3).
- One explicit confirmation for the exact batch shown. Any change (stock, quantity, price) = show the ticket again and re-confirm. Never act on an implied or earlier "yes".
- Signals flagged by the cross-check (`zerodha-live/data/signal_crosscheck.json`, recomputed from complete Yahoo history) are BLOCKED: the builder lists them as BLOCKED and will not ticket them. Never work around it; `--override SYMBOL` exists but only the user may ask for it, naming the stock, after you have shown the reason.
- Never retry a rejected order; never modify or cancel without being asked; never place while a refresh is running.

## Guardrails (hard rules)
- Tickets come ONLY from the ticket builder, which refuses (exit code 2) unless `zerodha-live/data/guardrails.json` is current for the same signals. A GLOBAL block (trading halt, stale data, mass-exit anomaly, NaN, cross-broker import) means nothing may be ordered; per-stock blocks list the stock as BLOCKED. Never work around a block: tell the user the id and message and stop. Only the user can fix the cause or switch off `zerodha-live/data/trading_halt.json`.
- Show every guardrail WARN the builder prints in the ticket, before asking for the "yes".
- Batch caps (`data/guardrails_config.json`: 40 orders, 25% of the capital base per batch). A bigger batch is refused unless the user, after seeing it, explicitly asks for `--allow-big-batch`.
- Kill switch: if the user says stop/halt, set `"halt": true` in `zerodha-live/data/trading_halt.json`; set it back to false only when they say so.
- Re-run `python zerodha-live/scripts/guardrails.py` right before building tickets if more than a few hours have passed since the refresh.

## Steps
1. **Login.** `mcp__claude_ai_Zerodha_Mcp__get_margins`; if it asks to log in, call `login`, show the user the link and wait.
2. **Fresh data, after the close.** The signals must be the day's final ones: the backtester's Daily OHLC Update publishes after the close (16:00, 17:00 and 19:00 IST runs), then `/refresh-zerodha`. The builder refuses data older than 3 days but you must also check `market_data_date` is the session that just ended.
3. **Market must be closed.** NSE equity trades Mon-Fri 09:15-15:30 IST (plus announced special sessions). If it is open, stop: tell the user to run this after the close. (Weekend/holiday or after 15:30 IST = continue in AMO mode.)
4. **One-shot pick, every time.** Re-run `python zerodha-live/scripts/build_order_ticket.py buy` and print the FULL numbered table again, all rows, even if shown earlier (never "same as before"): number, stock, quantity, reference price, est. value, entry or add-on, reason (flip date / P&L). Directly under it ALWAYS show a **capital check** from `get_margins` (equity available cash, collateral, utilised) and `zerodha_live_signals.json` (`capital_base`, invested now in the dashboard's open positions, undeployed remainder): the est. value of ALL listed signals (entries and add-ons separately, +2% worst case) as a % of available cash and of the Rs30,00,000 base. Say plainly how much of the balance is collateral rather than cash. Then ask once: "Reply with the numbers to place - e.g. `3,7,25-27` - or `all entries`, `all add-ons`." Echo the choice back. Never default to everything. The user may name stocks instead; map them to numbers and refuse any stock not in the list.
5. **Tickets.** `python zerodha-live/scripts/build_order_ticket.py buy --pick <numbers>` (same list, same numbers); read the `TICKETS_JSON=` line and the total.
6. **Day range and guard.** `get_ohlc` with `["NSE:<SYMBOL>", ...]` for the batch (one call). NOTE: Zerodha's `ohlc.close` is the PREVIOUS session's close; after the close the finished session's close is `last_price`, and `ohlc.high` is the session high. Use `last_price` as the close. If a close differs from the ticket's `ref_price` by more than 3%, stop and ask.
7. **Limit price = the signal day's HIGH, capped at close + 2%** (the same rule as ND). Limit = min(high, close x 1.02), the cap rounded DOWN to the 0.05 tick. If the exchange rejects a price for tick size (some low-priced stocks trade in 0.01 steps), report it verbatim and show the corrected price for a fresh yes; never guess. Show close, high, cap and the limit side by side and mark rows where the cap applied. Say plainly that a limit order fills at the open when the stock opens at or below it, so you normally pay the opening price; on a gap-up it can fill up to the limit, and above the limit it does not fill. The user may override the price.
8. **Funds.** Compare the batch total at the limits (qty x limit) with `get_margins` equity available cash. Delivery needs the full value (collateral counts as margin for CNC buys only partly: say so if the balance is mostly collateral). Stop and tell the user if cash is short.
9. **Ticket + confirmation.** Table: symbol, BUY, kind, quantity, limit, est. value, reason; the batch total next to available cash and the capital base; the line "AFTER-MARKET order for the next trading day". Ask the user to reply "yes, place these" and wait. Nothing is placed before that.
10. **Place** one at a time with `mcp__claude_ai_Zerodha_Mcp__place_order`: `variety: "amo"`, `exchange: "NSE"`, `tradingsymbol`, `transaction_type: "BUY"`, `quantity`, `product: "CNC"`, `order_type: "LIMIT"`, `price: <limit>`, `validity: "DAY"`, `tag: "AZENTRY"` (entries) or `"AZADD"` (add-ons). Place ONE first, check it with `get_orders` (status like `AMO REQ RECEIVED`/open, no rejection), then place the rest. If the tool reports a validation or window error (for example AMO not accepted at this hour), STOP, report it verbatim and do not guess other fields. Stop at the first rejection and say which orders did and did not go through. Never retry.
11. **Verify.** `get_orders`: report order id and status per stock. Nothing has filled yet; never say it has. Rewrite `zerodha-live/data/orders_snapshot.json` with the open AMO orders (`fetched_at`, `source`, `orders[]` with `order_id, symbol, side, qty, order_type, price, status, amo, placed`) so the Dashboard and Live Trading show them as ordered.
12. **Record the fills NEXT trading day.** `/refresh-zerodha` step 4 reads the day's `get_trades`: for every BUY of an F&O stock it runs `zerodha_trades.py buy --symbol <SYM> --date <date>` (with `--entry` when the stock was not held before). That makes the position part of the dashboard and starts the weekly add cooldown. Orders that did not fill (limit not reached) are not recorded. Remind the user of this.

## Reporting
Plain: placed (as AMO), status, still pending, failed (verbatim error). Never describe a pending AMO as filled.
