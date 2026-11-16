---
name: zerodha-option-entry-signal
description: Read-only scan of the AZ (Zerodha) option ENTRY signals, in 4 tiers by how recently the Supertrend flipped (Tier 1 flipped on the latest session, Tier 2 within the last trading week, Tier 3 within 30 days, Tier 4 within 90 days), Supertrend only (no RSI), stocks with open option legs left out, with a clear results / ex-dividend alert on every row. Places nothing. Use when the user says "option entry signals", "/zerodha-option-entry-signal", "what options should I open", or wants the Zerodha option signals before placing. Placing is the separate user-invoked skill zerodha-option-order.
---

# zerodha-option-entry-signal - AZ option entry signals in tiers (read-only)

This skill only READS and REPORTS. It never places, modifies or cancels an order and never writes a GTT. Placing a trade is `/zerodha-option-order` (user-invoked only); protecting it is `/zerodha-gtt-order`. AZ only: ND (Dhan) has its own signals and shares no code or data with this skill; never read from `dhan-live/`.

## The rules (user, 2026-11-16)
- **Supertrend only. RSI is NOT used** (the old RSI > 70 / < 30 override is ignored here). Green = BULL PUT SPREAD (sell a put, buy the hedge put 2 listed strikes lower); red = SELL CALL (no hedge on the call side, by the user's choice).
- **Tiers** (by when the CURRENT Supertrend colour began; each stock appears once, in the freshest tier it fits):
  - **Tier 1:** flipped on the latest published session ("today").
  - **Tier 2:** flipped 1 to 5 trading days ago (the last trading week).
  - **Tier 3:** flipped within the last 30 calendar days (older than Tier 2).
  - **Tier 4:** flipped within the last 90 calendar days (older than Tier 3). Anything older than 90 days is not listed.
- **Open positions are excluded:** any stock with a tracked open option leg (expiry on/after `track_from` in `zerodha-live/data/cc_config.json`) is left out, so a stock needing its old structure closed (a FLIP) never appears here; close it first, then it can show up on a later run. (Option legs with an expiry before `track_from` are not tracked and cannot be excluded.)
- **Universe:** Nifty F&O stocks (`data/fno_universe.json`) minus `data/excluded_symbols.json` (BSE, BEL, RECLTD). Expiry = the engine's first monthly expiry at least 30 days away; if only a nearer one is listed the row says SHORT EXPIRY. Expiry week is never placed (guardrail P1).
- **Results / ex-dividend alert on every row:** options are closed 15 days (`event_close_days`) before a stock's results or ex-dividend date. `!!` = the event is inside that 15-day window NOW (a new option would have to be closed immediately: do not open); `!` = the window opens before the expiry (the trade must be closed early on the stated date); plain text = an event within 60 days; `(est.)` = the date is an estimate. This is a warning, never a block (user rule 2026-11-09), but say it plainly.

## Steps
1. **Freshness (read-only).** Read `zerodha-live/covered_call_signals.json` (`market_data_date`) and `zerodha-live/data/cc_positions.json` (`fetched_at`), and say both in one line. If the open-legs file is not from today (IST) the exclusion list may be wrong (a leg opened or closed since); if the market data is older than the previous session the tiers are wrong. Fix = `/refresh-zerodha`, or pull positions (`mcp__claude_ai_Zerodha_Mcp__portfolio` `mode: "positions"` -> `python zerodha-live/scripts/cc_positions.py <file>` -> `python zerodha-live/scripts/compute_covered_call.py`; these only refresh local data files). Never present stale data as current.
2. **Run** `python zerodha-live/scripts/option_entry_tiers.py` (add `--max-per-tier N`, `--tier 1,2`, or `--json`). It prints one table per tier: number, stock, structure, price, flip date, flip age (trading days / calendar days), expiry, lot, ALERT.
3. **Report the tiers** as the script printed them (full tables for Tier 1 and 2; for Tier 3 and 4 show the top rows and the count, and offer the rest). Then call out in short lines:
   - Rows with `!!` (do not open now) and `!` (close early), grouped by date.
   - Any stock in Tier 1 or 2 that the AZ stock strategy entered today (an AZ stock position bought on the same signal), as a fact, not a judgement.
   - Rows with SHORT EXPIRY.
4. **Say what is not known:** premium, credit and margin are not available here (no option quotes are pulled); `/zerodha-option-order` shows them from live quotes. Never invent a number.
5. **Hand-off, always.** "To place any of these, run `/zerodha-option-order` and name up to 4 stocks (market hours only). It picks the strike (about 10% away this month, 15% for a later month), sizes to about Rs2,000 credit, quotes live, places the hedge first and then the short, and offers the protective GTT separately." Because this list uses colour only and `zerodha-option-order` takes its structure from the engine (which still applies RSI), tell the user to name the structure when it could differ: **pass `--structure put-spread` for a green stock and `--structure call` for a red one** in the order skill, so the placed trade matches this list. If the market is closed, say placing waits for the next session.

## Rules
- Read-only: no order, GTT, cancel, modify or file edit other than refreshing the local data files named in step 1, and only if the user agrees to a data pull.
- Facts, alerts and the next command only; the user chooses the stocks. Never call a stock a certain winner.
- ND and AZ stay separate: do not mention Dhan stocks or signals unless asked.
