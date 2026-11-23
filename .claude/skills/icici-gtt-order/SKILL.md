---
name: icici-gtt-order
description: List the stop-loss (SL) and profit-target GTT levels for every open short option leg of the DI (ICICI) book, in the same pattern as the Zerodha GTTs, so the user can place them by hand in ICICIdirect. Read-only: DI has no broker connector, so nothing is placed. User-invoked only. Use when the user says "icici gtt order", "/icici-gtt-order", "DI GTT levels", or wants the stop and target numbers for the ICICI shorts.
disable-model-invocation: true
---

# icici-gtt-order - SL and profit GTT levels for the DI (ICICI) shorts

DI has **no broker connector and no GTT list**, so this skill places and checks nothing. It works out the numbers from the keyed positions (`icici-live/data/cc_positions.json`) with the same rules as AZ and ND (`icici-live/data/cc_config.json` -> `rules`) so the user can create the GTTs by hand in ICICIdirect. DI shares no code or data with ND or AZ.

## Rules (same pattern as the Zerodha GTTs)
- Short option legs only (BUY to close). Hedge (long) legs never get a GTT.
- **Stop (SL):** trigger = 2.75x the sold average, limit = 3x the sold average.
- **Profit target:** trigger = 40% of the sold average (the premium decayed 60%), limit = trigger + 3% rounded up to the 0.05 tick.
- Prices are on the 0.05 tick. One two-leg (stop + target) GTT per short leg where ICICIdirect offers it; otherwise two separate GTTs.

## Steps
1. **Freshness.** Read `icici-live/data/cc_positions.json` `as_of`. If it is not today, say so and offer `/refresh-icici` (upload a fresh positions screen) before listing; do not list stale quantities as if current.
2. **Levels.** `python icici-live/scripts/build_gtt_levels.py` (self-contained, read-only; `--json` for JSON). It lists every short leg with its stop and target and these flags: `PAST STOP` (price already at/above the stop: close it now, a GTT would fire at once), `PAST TARGET` (already decayed past the target: book the profit, stop-only), `ALERT: <type> - close instead of placing` (the leg has an Exit / Event close / Profit Exit / Through hedge / Beyond strike alert in `covered_call_signals.json`), and the screen's own Trigger Price when it differs from the rule.
3. **Show it in TWO tiny tables (user's table-size rule):**
   - **Close or book first** (legs flagged PAST STOP, PAST TARGET or ALERT): 2 columns: leg, reason. No GTT for these.
   - **GTTs to place by hand:** 3 columns: `Leg (qty)` | `Stop trig (limit)` | `Target trig (limit)`. Sorted by stock. One line under the tables for any screen trigger that is off the rule (the user's existing trigger is not changed; say which differ).
4. **Close with the two-part next-step format:** **A. Run a skill** (usually `/refresh-icici` after the next close) and **B. Manual steps in ICICIdirect** (close the flagged legs, create the GTTs listed), then one line `Next step: ...`.

## Hard rules
- Never place, modify or cancel anything: there is no tool for it. Never claim a GTT exists; the skill cannot see ICICIdirect.
- Never invent a number: all levels come from the script. If the script says the positions are stale, say so.
- Concise: short cells, no recap of earlier steps, no sold/LTP columns in the place table unless the user asks.
