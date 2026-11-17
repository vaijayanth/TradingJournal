---
name: zerodha-option-scan-signal
description: Read-only scan of every open AZ (Zerodha) option position - orphaned long (buy) legs that hedge nothing, unhedged short puts and naked calls, shorts with no active stop GTT, GTTs that FIRED but did not fix the position (buy-back order rejected, unfilled, missing, or the short still open), active GTTs whose trigger the premium has already passed, and stale / wrong / off-rule GTTs. Places and changes nothing. Use when the user says "scan my options", "/zerodha-option-scan-signal", "any orphaned hedges", "did my GTTs trigger", or wants a health check of the open option book. Fixing is the separate user-invoked skill zerodha-gtt-order; opening new trades is zerodha-option-order.
---

# zerodha-option-scan-signal - health scan of the open AZ option book (read-only)

This skill only READS and REPORTS. It never places, modifies, cancels or deletes anything. Closing a leg is done by the user in the Kite app; GTT clean-up and new protective GTTs are `/zerodha-gtt-order` (user-invoked only); new trades are `/zerodha-option-order`. AZ only: ND (Dhan) has its own scan inside `dhan-superorder` and shares no code or data with this skill; never read from `dhan-live/`.

## Steps
1. **Login and pulls (all three, same day; the scan flags any input that is not from today).** Each large result is saved to a file by the tool: never paste it.
   - `mcp__claude_ai_Zerodha_Mcp__portfolio` `mode: "positions"` (`limit: 500`) -> `python zerodha-live/scripts/cc_positions.py <file>`.
   - `mcp__claude_ai_Zerodha_Mcp__gtt` `mode: "list"` (`limit: 500`) -> `python zerodha-live/scripts/cc_gtts.py <file>` (it now keeps the TRIGGERED GTTs as well as the active ones).
   - `mcp__claude_ai_Zerodha_Mcp__orders` `mode: "list"` (`limit: 500`) -> `python zerodha-live/scripts/cc_orders.py <file>` (today's option orders; the order list is today-only, so a GTT that fired on an earlier day can only be checked against the position, not its order).
   If the connector says to log in, call its `login` tool, show the link and wait. These pulls only refresh local data files.
2. **GTT hygiene first.** `python zerodha-live/scripts/scan_gtts.py` (stale, wrong side, wrong quantity, duplicate, bad trigger, off-rule stop, early expiry: checks G1-G7). Its findings feed section F below.
3. **Scan.** `python zerodha-live/scripts/scan_options.py` (add `--all` to also list every naked call; `--json` for the raw result). It writes `data/option_scan.json`. Sections:
   - **A ORPHANED LONG:** a bought leg that hedges no short (same stock / expiry / type, protective side: a put below the short, a call above it). Says its P&L and whether to book it (in profit) or sell / let it expire.
   - **B UNHEDGED SHORT PUT / NAKED CALL:** a short put with no long put below it (HIGH when nothing covers it, WARN when only part is covered). Short CALLS are naked by the user's design: counted as INFO, listed only with `--all`.
   - **C SHORT WITH NO ACTIVE STOP GTT:** WARN normally; HIGH when the premium is already past the 3x stop (a GTT would fire at once: close it in Kite).
   - **D GTT FIRED BUT NOT FIXED:** a GTT that triggered where the buy-back order was REJECTED / CANCELLED, is still OPEN (limit not reached), or is missing from today's orders, or where a short is still open on that contract (HIGH), or a GTT that fired on an earlier day and a short is still open (WARN). It also prints how many GTTs fired today and bought back cleanly.
   - **E TRIGGER ALREADY PASSED:** a short whose premium is at or above its ACTIVE stop trigger (HIGH: the stop did not fire) or at or below the profit trigger (WARN).
   - **F GTT HYGIENE:** the scan_gtts.py findings.
   - **G STOP GTT BUT NO PROFIT TARGET (user, 2026-11-17, same as ND):** a short whose active GTT has only a stop trigger (a single or trailing GTT, one trigger) and no profit (lower) trigger; WARN with the suggested target at the 60%-decay rule (40% of the sold price). Many of your own older GTTs are trailing single GTTs: the Zerodha tool cannot create or modify a trailing GTT, so replacing one with a two-leg GTT loses the trailing behaviour. Report them, and change one only on the user's explicit yes (delete the old GTT, then `/zerodha-gtt-order` places the two-leg one).
4. **Report.** Start with the one-line total and any `STALE INPUT` line (say plainly if an input is not from today and that the affected sections may be wrong). Then, per section, a compact table (contract, concern, action) with HIGH first; sections with no findings are named as clean. Do not list every naked call; give the count. Then a short "what to do now" list in this order: (1) legs to close in Kite now (C HIGH, D HIGH, E HIGH), (2) orphaned longs to sell or let expire (A), (3) unhedged puts (B), (4) GTT clean-up and missing GTTs (F, C WARN).
5. **Refresh the page data (read-only, local files only).** `python zerodha-live/scripts/compute_covered_call.py` and `python zerodha-live/scripts/guardrails.py`, so the Covered Call page alerts match the scan. Commits and pushes are the user's call ("push"); data refreshes of `zerodha-live/` files may be pushed under the standing rule, but this skill does not commit.
6. **Hand-off, always.** AZ only: `/zerodha-gtt-order` for the GTT deletions and re-sets (F) and the missing protective GTTs (C WARN); closing legs (C, D, E HIGH; orphaned longs A) is done by the user in Kite; `/zerodha-option-order` for any replacement trade; `/refresh-zerodha` after the close so the dashboard and fills pick up what changed.

## Rules
- Read-only. Never close, sell, cancel, delete, modify or place anything; never flip `data/trading_halt.json`.
- Never invent a status: if the order list or GTT list is missing or from another day, say so instead of calling a section clean.
- A GTT that "fired" is not proof the position was bought back: only a COMPLETE buy-back order (or the position being gone) is. Say which you checked.
- Excluded stocks (BSE, BEL, RECLTD) still appear here because their option legs are open positions; say so if one is flagged (for example BEL's unhedged put).
- Self-test: `python zerodha-live/scripts/test_scan_options.py` (every check must still fire).
