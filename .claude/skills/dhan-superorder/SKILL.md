---
name: dhan-superorder
description: Scan the user's Dhan (ND) super orders against the open option positions (orphaned stop legs, shorts with no stop, off-rule stops), fix them only with the user's yes, and place a new option position as a super order (entry + 40% target + 3x stop + trailing) only when the user names the contract. User-invoked only. Use when the user says "check my super orders", "/dhan-superorder", "Dhan GTT", or wants stop-loss cover on Dhan options.
---

# dhan-superorder - scan, fix and place protective super orders for Dhan options (ND)

This works on REAL orders on the user's Dhan account through the Dhan MCP. Dhan has no GTT / Forever-order tool; the user's equivalent is a SUPER ORDER on each short option: a SELL entry plus a STOP_LOSS leg (about 3x the sold price, trailing jump 0.05) and sometimes a TARGET leg (about 40% of the sold price). Facts about the MCP (read 2026-11-09): `trading_agent_tool` has `place`, `modify`, `cancel`, `super_place`, `super_modify`, `super_cancel`; `orderbook_agent_tool` `super_list` shows the super order book (symbol and entry price only, no strike or expiry); the alerts tool is equities and indices only (no option premiums); a plain STOP_LOSS order is DAY validity only; a super order's legs belong to its entry, so a stop cannot be attached to a position you already hold. Zerodha (AZ) has its own skill, `zerodha-gtt-order`.

## Part 1 - scan (always first, read-only)
1. **Pull, same day (the script refuses stale files).**
   - `mcp__claude_ai_dhan_mcp__portfolio_agent_tool` action `positions` -> save the text to `dhan-live/data/cc_raw/positions.txt` (overwrite; the option rows are what the scan uses).
   - `mcp__claude_ai_dhan_mcp__orderbook_agent_tool` action `super_list` -> save the raw text verbatim to `dhan-live/data/cc_raw/super_orders.txt`.
   If the MCP says not logged in, call its `login` tool, give the user the link and wait.
2. **Scan.** `python dhan-live/scripts/scan_super_orders.py`. It matches each SELL super order to an open short leg by symbol + sold average + quantity and writes `data/super_scan.json`. S1 ORPHAN (a stop/target leg still PENDING but no open short matches: if the stop fires it BUYS a new long; HIGH), S2 NO STOP (an open short with no matching super order), S3 OFF-RULE (stop not near 3x the sold price), S4 QUANTITY (order quantity differs from the open quantity).
3. **Say plainly that the match is approximate** (the book has no strike): a leg whose average changed after several fills, or two legs of one stock sold at the same price, can mismatch. Report every finding in a table (severity, check, stock, leg, order id, concern, action), HIGH first, with counts. Then run `python dhan-live/scripts/compute_covered_call.py --supertrend dhan-live/data/cache/supertrend_full.json` and `python dhan-live/scripts/guardrails.py` so the findings show on the Covered Call page (Alerts > Invalid stop order / No stop placed) and as guardrail P5.

## Part 2 - fix findings (only when the user asks, one order at a time)
- **Orphaned stop (S1).** First re-check that the position is really gone: call `positions` again and confirm no short of that stock has that quantity and sold price (the order's entry price). Show the exact list (order id, stock, entry price, stop and target prices, what the stop would buy) and get an explicit "yes, cancel these". Then `trading_agent_tool` action `super_cancel` with `{"orderId": "<id>", "legName": "STOP_LOSS_LEG"}` and again with `"TARGET_LEG"` when that leg is PENDING; stop at the first error and report it verbatim; verify with `super_list`. Never cancel a leg of an order whose position is still open.
- **Wrong stop level or quantity (S3 / S4).** Show old and new values, get a yes, then `super_modify` with `{"orderId", "legName", ...leg fields}`. The exact leg field names are not confirmed through this MCP: on a validation error STOP and report it verbatim, do not guess other fields.
- **Short with no stop (S2).** A stop cannot be attached to an existing position. Offer only these, the user chooses: (a) a plain `place` STOP_LOSS BUY order for the quantity (`exchangeSegment: "NSE_FNO"`, `productType: "MARGIN"`, `orderType: "STOP_LOSS"`, `triggerPrice` = 3x sold, `price` = trigger + 3%, `validity: "DAY"`), which lapses at the end of the day and must be re-placed daily; (b) close the short and re-enter it as a super order (Part 3), which changes the trade; (c) leave it. Never do (a) or (b) without the user's explicit yes naming the leg.

## Part 3 - place a new option as a super order (only on the user's explicit instruction)
Real money, opens a short. Do it only when the user names the contract(s) in this session (for example from the Covered Call Signals tab); never from a signal alone, never "all".
- **Refuse** if `dhan-live/data/trading_halt.json` has `halt: true`, or `dhan-live/data/guardrails.json` has a global block (prices suspect), or the contract is in expiry week (guardrail P1), or the stock is not in the covered-call universe (`dhan-live/data/cc_config.json`).
- **Hedge first.** A bull put spread = BUY the lower-strike put (the hedge) as a normal LIMIT order, confirm it filled, then the super order for the short put. A short call is covered by the shares held (see guardrail P4); say plainly if it is not.
- **Contract and price.** `search_agent_tool` / `market_data_agent_tool` `optionchain` for the `securityId`, strike, expiry and the current bid/ask; lot size from `dhan-live/data/nse_lots.json`; quantity = a whole number of lots (never a free-form quantity).
- **Super order.** `trading_agent_tool` `super_place`: `transactionType: "SELL"`, `exchangeSegment: "NSE_FNO"`, `securityId`, `quantity`, `orderType: "LIMIT"`, `productType: "MARGIN"`, `price` = the limit the user approves, `stopLossPrice` = 3x the price, `targetPrice` = 40% of the price (the 60% profit rule), `trailingJump` 0.05 (the user's usual; ask if different). Show the full ticket first: contract, qty, price, stop, target, trailing jump, margin from `margin_agent_tool` `single`, and the line "This OPENS a short option position." Wait for "yes, place this". The MCP's own pre-trade funds check has been wrong before (sign-flipped shortfall): if it blocks and the margin check shows the funds are fine, tell the user and only after their yes add `"preflight": false`.
- Place one at a time; after it, check `orderbook_agent_tool` `super_list` (entry traded or pending, both legs PENDING with the right prices). Report plainly; a pending order is not a fill.
- Maximum 4 contracts per instruction. Never retry a rejected order.

## After any change
Re-run Part 1 steps 1-3 so the alerts clear; nothing is committed ("push" handles that). Record fills the next trading day through `/refresh-dhan` as usual (the Dhan tradebook is today-only).

## Reporting
Plain: scanned / cancelled / modified / placed / failed (with the verbatim error). A pending order is not a fill; an unconfirmed leg field name is reported, not guessed.
