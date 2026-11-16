---
name: zerodha-option-exit-signal
description: Read-only list of the AZ (Zerodha) option EXIT signals for every open option leg, grouped by rule type and ordered most urgent first - 3x premium stop hit, through the hedge, beyond the strike, a stop that fired but did not fix the position, expiry risk, results / ex-dividend close window, Supertrend colour flipped with the old structure still open, profit exit (60% decayed), near the strike, orphaned long legs. Places nothing. Use when the user says "option exit signals", "/zerodha-option-exit-signal", "what should I close", or wants the exit list before closing legs in Kite. Closing a leg is done by the user in the Kite app; GTT clean-up is zerodha-gtt-order.
---

# zerodha-option-exit-signal - which open AZ option legs to close (read-only)

This skill only READS and REPORTS. It never places, modifies, cancels or deletes anything; no skill closes an option leg, so every close is done by the user in the Kite app. It is the exit-side twin of `/zerodha-option-entry-signal` and uses the same data as the Covered Call page's Alerts tab and the option scan, grouped by rule type. AZ only: ND (Dhan) has its own signals and shares no code or data with this skill; never read from `dhan-live/`.

## The rule types (most urgent first; user's grouping choice, 2026-11-16)
1. **3x premium - close now:** a short's premium is at or above 3x what you sold it for (`stop_premium_multiple` in `zerodha-live/data/cc_config.json`). A GTT cannot protect it any more (it would fire at once).
2. **Through the hedge:** the stock is past the long hedge as well, so the spread is at its maximum loss: close or roll now.
3. **Beyond the strike:** the stock is past the short strike (in the money): roll, close or hold.
4. **Stop fired but not fixed / trigger passed:** from the option position scan: a GTT that fired without closing the position (buy-back rejected, unfilled, missing, or the short still open), or an active GTT whose trigger the premium has already passed. Needs today's option scan.
5. **Expiry risk:** an in-the-money leg within 7 days of expiry; stock options settle by physical delivery, so close it before expiry (urgent in the last 3 days).
6. **Results / ex-dividend close window:** every open option is closed 15 days before the stock's next results or ex-dividend date (`event_close_days`).
7. **Colour flipped, old structure open:** the Supertrend colour changed (or the open structure is the opposite of the colour: a short call while green, a short put or put spread while red). Close it and open the other structure. The RSI is not used.
8. **Profit exit:** the short's premium has decayed 60% or more since it was sold (`profit_exit_decay_pct`): book the profit by buying it back.
9. **Near the strike (watch):** price within 2% of a short strike: plan the roll.
10. **Orphaned long:** a bought leg that hedges nothing (no short against it, or not on the protective side of one): sell it, or let it expire; if it is in profit, book it or let it run.

A leg can appear in several groups at once (for example a short call that is past 3x, through its hedge, in the money and on the wrong side of a green Supertrend); the script prints a line naming the legs in three or more groups, the most urgent first.

## Steps
1. **Freshness (read-only).** The script prints a `!!` line when live prices, the open legs or the option scan are not from today. If any is stale, say so plainly and that the 3x, strike and "stop fired" groups may be wrong; the fix is `/refresh-zerodha` (which refreshes all of them), or the pulls in `/zerodha-option-scan-signal` step 1. Never present stale data as current.
2. **Run** `python zerodha-live/scripts/option_exit_signals.py` (add `--group 1,2` to see only some groups, `--all` for every row of groups 9 and 10, `--json` for the raw result). It reads `covered_call_signals.json` (the engine's alerts), `data/cc_positions.json` (quantity, sold or bought price, current price, P&L per leg) and `data/option_scan.json`.
3. **Report group by group, most urgent first.** Groups 1 to 4 in full (contract, quantity, P&L, concern, action); groups 5 to 8 in full; group 9 and 10 as the top rows and the count. Lead with the one-line total, the number of distinct legs and the legs that sit in three or more groups. Name the P&L at stake for group 1 and 2 (the sum of those legs' P&L).
4. **Say what to do, in this order:** (a) close in Kite now: groups 1, 2 and 4; (b) close before expiry or inside the event window: groups 3, 5 and 6; (c) flip the structure: group 7 (close the old leg, then `/zerodha-option-entry-signal` and `/zerodha-option-order` for the new one); (d) book profit: group 8; (e) watch and decide: groups 9 and 10. A leg in several groups is dealt with once, at its most urgent group.
5. **Hand-off, always.** AZ only: closes are done in the Kite app; `/zerodha-gtt-order` removes the GTT left behind on a contract you closed and protects any new short; `/refresh-zerodha` after the close records what changed and re-runs the scan; `/zerodha-option-entry-signal` and `/zerodha-option-order` for the replacement trade on a colour flip.

## Rules
- Read-only: no order, GTT, cancel or file edit. A data pull is refreshed only through `/refresh-zerodha` or the scan skill, and only if the user agrees.
- Facts and the next command only; never tell the user a close is certain to be right. A colour flip with a profitable short is the user's call.
- Never invent a number: quantity, prices and P&L come from the engine and the positions file.
- Excluded stocks (BSE, BEL, RECLTD) still appear when their legs are open; say so if one is listed.
- ND and AZ stay separate: do not mention Dhan positions unless asked.
