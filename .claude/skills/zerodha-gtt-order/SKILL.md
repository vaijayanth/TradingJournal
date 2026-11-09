---
name: zerodha-gtt-order
description: Scan the user's existing Zerodha (AZ) option GTT orders for invalid ones, and place protective buy-back GTTs (profit target + 3x stop) on open short option legs that have none (the "No GTT placed" alert), after an explicit confirmation. User-invoked only; modifies or deletes a GTT only when asked. Use when the user says "place GTTs", "check my GTTs", "/zerodha-gtt-order", or wants the GTT alerts cleared.
---

# zerodha-gtt-order - scan and place protective GTT orders for open short options (AZ)

This works on REAL GTT orders on the user's Zerodha account through the Zerodha MCP. A GTT here is a buy-back on a short option you already hold. The user's own pattern is a TWO-LEG (one-cancels-other) GTT: a lower trigger = profit target (premium decayed 60%, i.e. 40% of the sold price) and an upper trigger = the 3x-premium stop (`stop_premium_multiple`, `profit_exit_decay_pct` in `zerodha-live/data/cc_config.json`). It never opens a new position. Dhan (ND) has no GTT tool; this skill is AZ only.

## Part 1 - scan the existing GTTs (always first)
1. **Login.** `mcp__claude_ai_Zerodha_Mcp__get_positions` with `limit: 1`; if it asks to log in, call `login`, show the warning and link, wait for the user.
2. **Fresh inputs (both from today; the scripts refuse stale ones).**
   - `get_positions` (no limit; saved to a file) -> `python zerodha-live/scripts/cc_positions.py <file>`.
   - `get_gtts` (no limit; saved to a file) -> `python zerodha-live/scripts/cc_gtts.py <file>`.
3. **Scan.** `python zerodha-live/scripts/scan_gtts.py`. It checks every ACTIVE option GTT (F&O stocks, expiries on/after `track_from`) against the open positions and writes `data/gtt_scan.json`. Checks: G1 STALE (no open position on the contract: if it triggers it BUYS a new long - HIGH), G2 WRONG SIDE (SELL GTT on a short, BUY GTT on a long: adds to the position - HIGH), G3 QUANTITY (above the open quantity = would leave you long, HIGH; below = partly protected), G4 DUPLICATE (several buy GTTs on one contract), G5 TRIGGER (a trigger on the wrong side of the price, or the stop's limit below its trigger), G6 OFF-RULE (stop far from 3x the sold price, or a profit target with no stop), G7 EXPIRES (the GTT lapses before the option does).
4. **Report** every finding in a table (severity, check, contract, GTT id, concern, suggested action), HIGH first, with the count per check. Say plainly that these are only suggestions: nothing is changed by the scan. Then run `python zerodha-live/scripts/compute_covered_call.py` and `python zerodha-live/scripts/guardrails.py` so the findings show on the Covered Call page (Alerts > Invalid GTT) and as guardrail P5.
5. **Fixing findings** only when the user asks, and only the GTTs they name (or "all STALE"): show the exact list (GTT id, contract, what it would buy), get an explicit "yes, delete these", then `delete_gtt_order` with each `trigger_id` one at a time (stop at the first error, verify with `get_gtts`). A wrong quantity, limit or trigger: show old and new values, get a yes, then `modify_gtt_order` (all required fields, same contract). Never delete or modify to "tidy up" without that yes.

## Part 2 - place missing protective GTTs
### Scope (hard limits)
- Only SHORT option legs that are open right now in `get_positions` (NFO stock options, NRML) and have no ACTIVE buy GTT on that exact contract. Never a stock, an index option, a long (hedge) leg, a SELL GTT, a new position, or a contract you do not hold.
- BUY to close, NRML; quantity = the open short quantity (never more). Numbers come only from `python zerodha-live/scripts/build_gtt_tickets.py`; never invent or change a trigger, limit or quantity. If the user names a leg that is not in the list, refuse and say why (already has a GTT, is not short, or its price is already at/above the stop).
- A leg whose price is already at or above its 3x stop is NOT ticketed (a GTT would fire at once): tell the user it needs closing now. A leg already decayed past the 60% profit target gets a stop-only ticket with a note (consider booking the profit now).
- Default ticket = two-leg: upper trigger = 3x sold, lower trigger = 40% of sold; each limit = its trigger + `gtt_limit_buffer_pct` (3%) rounded up to the 0.05 tick. `--single` builds stop-only GTTs if the user wants no profit target. The tool cannot create trailing GTTs (the user's older ones are trailing); say so if asked.
- One explicit confirmation for the exact batch shown; any change = show the table again and re-confirm. Never act on an implied or earlier "yes". Never retry a rejected GTT.
- `zerodha-live/data/trading_halt.json` with `halt: true` stops everything (the script refuses); do not flip it. A global guardrail block (e.g. F5, price-data mismatch) does NOT stop protective GTTs because they come from live positions, not the Supertrend signals; mention it if one is open. Maximum 40 GTTs per batch.

### Steps (after Part 1, with the same fresh inputs)
1. **List.** `python zerodha-live/scripts/build_gtt_tickets.py`. Print the FULL numbered list every time: number, contract, qty, sold average, LTP, profit trigger/limit, stop trigger/limit, plus the NOT TICKETED lines. Add the maximum buy-back cost at the stop limit (qty x limit). Ask once: "Reply with the numbers to place - e.g. `1,3-5` - or `all`." Echo the choice back. Never default to all. Do not ticket a leg that scan_gtts flagged for a bad existing GTT until that GTT is fixed (a second GTT would be a duplicate).
2. **Tickets.** `python zerodha-live/scripts/build_gtt_tickets.py --pick <numbers>` (add `--single` if asked); read `TICKETS_JSON=`.
3. **Confirm.** Table: contract, BUY, qty, profit trigger/limit, stop trigger/limit, LTP now, cost at the stop limit, and "Protective GTT: it buys back your short option if the premium reaches a trigger. Nothing is bought unless one triggers." Ask for "yes, place these" and wait.
4. **Place** one ticket first with `mcp__claude_ai_Zerodha_Mcp__place_gtt_order`: `exchange: "NFO"`, `tradingsymbol`, `transaction_type: "BUY"`, `product: "NRML"`, `last_price`, and for two-leg `trigger_type: "two-leg"`, `lower_trigger_value`, `lower_limit_price`, `lower_quantity`, `upper_trigger_value`, `upper_limit_price`, `upper_quantity` (for stop-only: `trigger_type: "single"`, `trigger_value`, `limit_price`, `quantity`). Check it with `get_gtts` (active, right contract, triggers, quantity). If correct place the rest one at a time; stop at the first error and report it verbatim (do not guess other fields or retry).
5. **Record.** `get_gtts` -> `cc_gtts.py`, `scan_gtts.py`, `compute_covered_call.py`, `guardrails.py`, so the alerts clear. Nothing is committed; "push" handles that.

## Reporting
Plain: scanned / placed / deleted / modified / failed (with the verbatim error). A GTT is active, not triggered or filled: never say a buy-back happened unless `get_gtts` shows it triggered and the position changed.
