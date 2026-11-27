---
name: zerodha-option-entry-signal
description: Read-only scan of the AZ (Zerodha) option ENTRY signals, in 5 tiers by how recently the Supertrend flipped (Tier 1 flipped on the latest session, Tier 2 within the last trading week, Tier 3 within 30 days, Tier 4 within 90 days, Tier 5 older than 90 days), Supertrend only (no RSI), stocks with open option legs left out, with a clear results / ex-dividend alert on every row. Places nothing. Use when the user says "option entry signals", "/zerodha-option-entry-signal", "what options should I open", or wants the Zerodha option signals before placing. Placing is the separate user-invoked skill zerodha-option-order, currently ON HOLD (never suggest it).
---

# zerodha-option-entry-signal - AZ option entry signals in tiers (read-only)

This skill only READS and REPORTS. It never places, modifies or cancels an order and never writes a GTT. Placing a trade is `/zerodha-option-order` (user-invoked only, ON HOLD: never suggest it); protecting it is `/zerodha-gtt-order`. AZ only: ND (Dhan) has its own signals and shares no code or data with this skill; never read from `dhan-live/`.

## The rules (user, 2026-11-16)
- **Price floor (user, 2026-11-26): no option entry suggestions on stocks whose CMP is below Rs50** (`zerodha-live/data/cc_config.json` `rules.min_entry_price`; the script drops them and prints how many). Never add one back by hand.
- **Supertrend only. RSI is NOT used** (the old RSI > 70 / < 30 override is ignored here). Green = BULL PUT SPREAD (sell a put, buy the hedge put 2 listed strikes lower); red = SELL CALL (no hedge on the call side, by the user's choice).
- **Tiers** (by when the CURRENT Supertrend colour began; each stock appears once, in the freshest tier it fits):
  - **Tier 1:** flipped on the latest published session ("today").
  - **Tier 2:** flipped 1 to 5 trading days ago (the last trading week).
  - **Tier 3:** flipped within the last 30 calendar days (older than Tier 2).
  - **Tier 4:** flipped within the last 90 calendar days (older than Tier 3).
  - **Tier 5:** flipped more than 90 days ago (the oldest and weakest signal, added 2026-11-16). Every stock without open option legs now sits in one of the five tiers.
- **Open positions are excluded:** any stock with a tracked open option leg (expiry on/after `track_from` in `zerodha-live/data/cc_config.json`) is left out, so a stock needing its old structure closed (a FLIP) never appears here; close it first, then it can show up on a later run. (Option legs with an expiry before `track_from` are not tracked and cannot be excluded.)
- **Universe:** Nifty F&O stocks (`data/fno_universe.json`) minus `data/excluded_symbols.json` (BSE, BEL, RECLTD). Expiry = the engine's first monthly expiry at least 30 days away; if only a nearer one is listed the row says SHORT EXPIRY. Expiry week is never placed (guardrail P1).
- **Results / ex-dividend alert on every row:** options are closed 15 days (`event_close_days`) before a stock's results or ex-dividend date. `!!` = the event is inside that 15-day window NOW (a new option would have to be closed immediately: do not open); `!` = the window opens before the expiry (the trade must be closed early on the stated date); plain text = an event within 60 days; `(est.)` = the date is an estimate. This is a warning, never a block (user rule 2026-11-09), but say it plainly.

## Steps
1. **Freshness (read-only).** Read `zerodha-live/covered_call_signals.json` (`market_data_date`) and `zerodha-live/data/cc_positions.json` (`fetched_at`), and say both in one line. If the open-legs file is not from today (IST) the exclusion list may be wrong (a leg opened or closed since); if the market data is older than the previous session the tiers are wrong. Fix = `/refresh-zerodha`, or pull positions (`mcp__claude_ai_Zerodha_Mcp__portfolio` `mode: "positions"` -> `python zerodha-live/scripts/cc_positions.py <file>` -> `python zerodha-live/scripts/compute_covered_call.py`; these only refresh local data files). Never present stale data as current.
2. **Run** `python zerodha-live/scripts/option_entry_tiers.py` (add `--max-per-tier N`, `--tier 1,2`, or `--json`). It prints one table per tier: number, stock, structure, price, flip date, flip age (trading days / calendar days), expiry, lot, ALERT.
3. **Open today FIRST (user, 2026-11-27).** The script prints an `Open today` list before the tiers (JSON key `open_today`): the best 10 entry rows that pass every gate (no F&O ban, no event alert or short expiry, not within 1.5% of a Supertrend flip, IV percentile 50 or more), best IV grade (A first, structural IV rank, not the Tier 1-5 flip age) on top. Show it as the first table, with each row's grade, structure, IVP, flip age, expiry and lot; the gates always outrank the grade, and say plainly when the list is empty. The Covered Call Entry tab shows the same card.
3a. **Stop cool-off and spike flips (user, 2026-11-27).** Rows whose alert says `STOP COOL-OFF` (a 3x stop fired on that stock: the same direction is blocked for 5 trading days and until the Supertrend is 6% from flipping) are NOT candidates: name them and say until when. Rows with `SPIKE FLIP` followed a 6%+ 3-day move: say to put the strike 3-4 points further out (put, about 15% below) or 6-8 (call, about 18-20% above). Evidence: `swing-backtest/RESULTS.md` (stop re-entry study).
3b. **Then the Supertrend table and the tiers (user, 2026-11-19).** Show the table of stocks with open option legs as printed (stock, Supertrend colour, since, age, price, what the rule wants, HOLD / FLIP status derived from the open legs, open legs), FLIP rows first: a stock whose colour changed while the old structure is still open needs that structure closed before a new one. If the table is long, show the FLIP rows in full and the HOLD rows as a count plus the first few. Then report the tiers as the script printed them (full tables for Tier 1 and 2; for Tier 3 and 4 show the top rows and the count, and offer the rest). Then call out in short lines:
   - Rows with `!!` (do not open now) and `!` (close early), grouped by date.
   - Any stock in Tier 1 or 2 that the AZ stock strategy entered today (an AZ stock position bought on the same signal), as a fact, not a judgement.
   - Rows with SHORT EXPIRY.
4. **Say what is not known:** premium, credit and margin are not available here (no option quotes are pulled); the (ON HOLD) `/zerodha-option-order` would show them from live quotes. Never invent a number.
5. **Hand-off.** `/zerodha-option-order` is ON HOLD (see `.claude/skills/_shared/holds.md`): do NOT suggest it and do not hand off to it. End with the list; the user decides and places in the Kite app.

## Rules
- Read-only: no order, GTT, cancel, modify or file edit other than refreshing the local data files named in step 1, and only if the user agrees to a data pull.
- Facts, alerts and the next command only; the user chooses the stocks. Never call a stock a certain winner.
- ND and AZ stay separate: do not mention Dhan stocks or signals unless asked.


## Re-sell PE rows (user, 2026-11-23)
Also list, above the tiers, every stock whose short put was closed (GTT target / profit exit) but whose long PE hedge is still open while the Supertrend is green and the stock is not in the F&O ban: the stock is moving up, so a new PE sell above the hedge strike can be opened (the Covered Call Entry tab shows these as `Re-sell PE`). Show Stock | Long hedge | Expiry | P&L | Results / ex-dividend alert. Read-only; placing is the separate order skill.
