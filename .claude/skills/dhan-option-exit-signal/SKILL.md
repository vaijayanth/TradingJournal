---
name: dhan-option-exit-signal
description: Read-only list of the ND (Dhan) option EXIT signals for every open option leg, grouped by rule type and ordered most urgent first - 3x premium stop hit, through the hedge, beyond the strike, stop problems (a stop that fired or was cancelled while the short is open, a pending stop the premium already passed, a short with no stop, an orphaned or off-rule stop leg), expiry risk, results / ex-dividend close window, Supertrend colour flipped with the old structure still open, profit exit (60% decayed), near the strike, hedge gaps. Places nothing. Use when the user says "Dhan option exit signals", "/dhan-option-exit-signal", "what should I close on Dhan", or wants the ND exit list before closing legs in the Dhan app. Cancelling or fixing stop legs is dhan-superorder.
---

# dhan-option-exit-signal - which open ND option legs to close (read-only)

This skill only READS and REPORTS. It never places, modifies, cancels or closes anything; no skill closes an option leg, so every close is done by the user in the Dhan app. Cancelling or fixing stop legs and placing new option super orders is `/dhan-superorder` (user-invoked only, with its own per-order confirmation). It is the ND twin of `/zerodha-option-exit-signal` and the exit-side partner of `/dhan-option-entry-signal`: it uses the same data as the Covered Call page's Alerts tab and the ND option scan, grouped by rule type. ND only: AZ (Zerodha) has its own and shares no code or data with this skill; never read from `zerodha-live/`.

## The rule types (most urgent first)
1. **3x premium - close now:** a short's premium is at or above 3x what you sold it for (`stop_premium_multiple` in `dhan-live/data/cc_config.json`). The stop leg of its super order should have fired; if the book still shows it pending, group 4 says so.
2. **Through the hedge:** the stock is past the long hedge as well, so the spread is at its maximum loss: close or roll now.
3. **Beyond the strike:** the stock is past the short strike (in the money): roll, close or hold.
4. **Stop problems (from the option scan):** a stop leg that fired (or was cancelled / rejected) while the short is still open; a pending stop whose price the premium has already passed; a short with no stop super order; an orphaned stop leg that could BUY a new long; an off-rule stop or a quantity mismatch. The super order book has no strike or expiry, so a stop is matched to a short by symbol and sold average: verify in the Dhan app before acting.
5. **Expiry risk:** an in-the-money leg within 7 days of expiry; stock options settle by physical delivery, so close it before expiry.
6. **Results / ex-dividend close window:** every open option is closed 15 days before the stock's next results or ex-dividend date (`event_close_days`).
7. **Colour flipped, old structure open:** the Supertrend colour changed (or the open structure is the opposite of the colour: a short call while green, a short put or put spread while red). Close it and open the other structure. No RSI. Short calls are covered by the shares held, so a profitable call on a green stock is the user's call.
8. **Profit exit:** the short's premium has decayed 60% or more since it was sold (`profit_exit_decay_pct`): book the profit by buying it back.
9. **Near the strike (watch):** price within 2% of a short strike: plan the roll.
10. **Hedge gaps:** an orphaned long leg (hedges nothing: sell it or let it expire; in profit, book it or let it run) or a short that is not fully hedged (buy the hedge or close the short).

A leg can appear in several groups at once; the script prints a line naming the legs in three or more groups, the most urgent first, so each is dealt with once, at its most urgent group.

## Steps
1. **Freshness (read-only).** The script prints a `!!` line when the live prices, the covered-call signals, the raw positions file or the option scan are not from today. If any is stale, say so plainly and that the 3x, strike and stop groups may be wrong; the fix is `/refresh-dhan` (it refreshes all of them and runs the option scan), or the pulls in `/dhan-option-scan-signal` step 1. Never present stale data as current.
2. **Run** `python dhan-live/scripts/option_exit_signals.py` (add `--group 1,2` to see only some groups, `--all` for every row of groups 9 and 10, `--json` for the raw result). It reads `covered_call_signals.json` (alerts and open legs with quantity, sold or bought price, current price, P&L) and `data/option_scan.json`.
3. **Report group by group, most urgent first.** Groups 1 to 8 in full (contract, quantity, P&L, concern, action); groups 9 and 10 as the top rows and the count. Lead with the one-line total, the number of distinct legs and any leg in three or more groups. Name the P&L at stake for groups 1 and 2. A group with nothing is named as clean: with a small book (22 legs) most groups are empty, and that is a good answer.
4. **Say what to do, in this order:** (a) close in the Dhan app now: groups 1, 2 and 4 (a stop that failed); (b) close before expiry or inside the event window: groups 3, 5 and 6; (c) flip the structure: group 7 (close the old leg, then `/dhan-option-entry-signal` and `/dhan-superorder` for the new one); (d) book profit: group 8; (e) watch and decide: groups 9 and 10. A leg in several groups is dealt with once, at its most urgent group.
5. **Hand-off, always.** ND only: closes are done in the Dhan app; `/dhan-superorder` cancels a stop leg left behind on a closed position, fixes an off-rule stop, and places the replacement option as a new super order; `/refresh-dhan` after the close records what changed and re-runs the scan.

## Rules
- Read-only: no order, cancel or file edit. A data pull is refreshed only through `/refresh-dhan` or the scan skill, and only if the user agrees.
- Facts and the next command only; never tell the user a close is certain to be right.
- Never invent a number: quantity, prices and P&L come from the engine and the positions file.
- ND and AZ stay separate: do not mention Zerodha positions unless asked.
