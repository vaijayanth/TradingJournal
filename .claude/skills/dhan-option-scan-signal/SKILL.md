---
name: dhan-option-scan-signal
description: Read-only scan of every open ND (Dhan) option position - orphaned long (bought) legs that hedge nothing, unhedged short puts and naked calls, shorts with no stop super order, stops that FIRED but did not fix the position (or whose stop leg was cancelled / rejected), stops whose trigger the premium already passed but are still pending, and orphaned / off-rule / wrong-quantity stop legs. Places and changes nothing. Use when the user says "scan my Dhan options", "/dhan-option-scan-signal", "any orphaned hedges on Dhan", "did my Dhan stops fire", or wants a health check of the ND option book. Fixing stops and placing new options is the separate user-invoked skill dhan-superorder.
---

# dhan-option-scan-signal - health scan of the open ND option book (read-only)

This skill only READS and REPORTS. It never places, modifies, cancels or closes anything. Closing a leg is done by the user in the Dhan app; cancelling or fixing stop legs and placing new option super orders is `/dhan-superorder` (user-invoked only, with its own per-order confirmation). It is the ND twin of `/zerodha-option-scan-signal`: ND has no GTTs, so the user's stop is the STOP_LOSS leg of a SELL super order (about 3x the sold price, trailing jump 0.05, sometimes a TARGET leg at about 40%). ND only: AZ (Zerodha) has its own scan and shares no code or data with this skill; never read from `zerodha-live/`.

## Steps
1. **Login and pulls (same day; the scan flags any input that is not from today).** Each is saved verbatim; never paste a large result.
   - `mcp__dhan__portfolio_agent_tool` (or `mcp__claude_ai_dhan_mcp__portfolio_agent_tool`) action `positions` -> save the raw text to `dhan-live/data/cc_raw/positions.txt` (overwrite).
   - `orderbook_agent_tool` action `super_list` -> save the raw text to `dhan-live/data/cc_raw/super_orders.txt` (overwrite). This book carries the status of every stop and target leg, which is what sections D and E read.
   - `market_data_agent_tool` action `ltp` with `{"NSE_EQ": [<security_id of every stock in dhan-live/data/cc_config.json universe>]}` -> save to a scratch file -> `python dhan-live/scripts/cc_prices.py <file>` (live prices for the premium checks).
   If the connector says not logged in, call its `login` tool, show the link and wait. These pulls only refresh local data files.
2. **Stop-order hygiene.** `python dhan-live/scripts/scan_super_orders.py` (orphaned stop legs, shorts with no stop, off-rule stops, quantity mismatches). Its findings feed section F.
3. **Rebuild the legs.** `python dhan-live/scripts/compute_covered_call.py --supertrend dhan-live/data/cache/supertrend_full.json` so each leg carries its current premium and P&L.
4. **Scan.** `python dhan-live/scripts/scan_options.py` (add `--all` to also list every naked call; `--json` for the raw result). It writes `data/option_scan.json`. Sections:
   - **A ORPHANED LONG:** a bought leg that hedges no short (same stock / expiry / type, protective side: a put below the short, a call above it). It says its P&L and whether to book it (in profit) or sell / let it expire.
   - **B UNHEDGED SHORT PUT / NAKED CALL:** a short put with no long put below it (HIGH when nothing covers it, WARN when only part is covered). Short CALLS are naked by design (covered by shares): counted as INFO.
   - **C SHORT WITH NO STOP ORDER:** a short with no matching super order (WARN; HIGH when its premium is already at 3x the sold price).
   - **D STOP FIRED, NOT FIXED:** the stop leg is TRADED / TRIGGERED but a matching short is still open (HIGH), or the stop leg is CANCELLED / REJECTED / EXPIRED while the short is open (HIGH: the short has no stop). It also lists how many stops fired and closed cleanly.
   - **E TRIGGER PASSED:** the premium is at or above the stop price but the stop leg is still PENDING (HIGH: it has not fired), or at or below the target price with the target pending (WARN).
   - **F STOP HYGIENE:** the scan_super_orders.py findings (S1 orphaned stop legs that could BUY a new long, S3 off-rule stops, S4 quantity mismatches).
5. **Say plainly that the match is approximate.** The super order book shows the symbol and the entry price but no strike or expiry, so an order is matched to a short by symbol + sold average (+ quantity): two legs of one stock sold at the same price, or an average that moved after several fills, can mismatch. Verify in the Dhan app before cancelling or closing anything.
6. **Report.** Start with the one-line total and any `STALE INPUT` line (an input not from today means those sections may be wrong). Then, per section, a compact table (leg, concern, action) with HIGH first; sections with no findings are named as clean. Do not list every naked call; give the count. End with the "what to do now" list in this order: (1) legs to close in Dhan now: C HIGH, D HIGH, E HIGH; (2) section B unhedged puts; (3) section A orphaned longs; (4) stop clean-up and missing stops: F and C WARN.
7. **Refresh the page data (read-only, local files only).** `python dhan-live/scripts/guardrails.py` so the Covered Call alerts and guardrail P5 match the scan. This skill does not commit; data refreshes of `dhan-live/` are pushed only under the standing rule (never while a guardrail BLOCK is open), otherwise on the user's "push".
8. **Hand-off, always.** ND only: `/dhan-superorder` for cancelling orphaned stop legs, fixing off-rule stops and placing a new option as a super order; closing legs and selling orphaned longs is the user's action in the Dhan app; `/refresh-dhan` after the close so the page, P&L and fills pick up what changed.

## Rules
- Read-only. Never close, sell, cancel, modify or place anything; never flip `dhan-live/data/trading_halt.json`.
- Never invent a status: a missing or stale input is reported, not called clean.
- A stop leg showing TRADED / TRIGGERED is not proof the position closed: only the position being gone (or the buy-back filling in the order book) is. Say which you checked.
- A stop cannot be attached to a position you already hold (the MCP offers no way): the honest options for a short with no stop are a daily stop order, closing and re-entering it as a super order, or leaving it; the user chooses.
- Self-test: `python dhan-live/scripts/test_scan_options.py` (every check must still fire).
