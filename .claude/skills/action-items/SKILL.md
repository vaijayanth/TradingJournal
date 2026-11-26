---
name: action-items
description: One prioritized, read-only list of everything pending across the ND (Dhan) and AZ (Zerodha) accounts - refresh status and guardrail blocks, legs to close now in the broker app, skills to run next with their counts, and decisions that are the user's call. Places and changes nothing. Use when the user says "action items", "/action-items", "what is pending", "what do I need to do", or asks how to know what is outstanding.
---

# action-items - what is pending, in one list (read-only)

This skill only READS and REPORTS. It never places, modifies, cancels or closes anything, and it never refreshes data by itself. It is the ONE deliberate place that shows both brokers together, and only to display: `scripts/action_items.py` reads each broker from its own folder's files in separate code (`dhan-live/` for ND, `zerodha-live/` for AZ); no logic or data is shared between them, and nothing is imported from either folder. DI (ICICI) has no orders or positions yet, so it is not included.

## Steps
1. **Run** `python scripts/action_items.py` (add `--json` for the raw result). Do not paste its output: read it and report it in your own short sections.
2. **Section 0, refresh status first.** Say when each broker was last refreshed and the market data date. If the market is open and a refresh is over an hour old, or the latest close has been published and the data is older, the rest of the list may be out of date: say so and name the refresh command (`/refresh-dhan` or `/refresh-zerodha`) before anything else. Name any guardrail BLOCK (it stops all stock orders for that broker until it clears).
3. **Section 1, close now (in the broker app).** One line per leg with the reasons joined: 3x stop hit, through the hedge, a stop that fired or did not fire, or inside the results / ex-dividend close window. These are the most urgent; no skill closes a leg, so every one is the user's action in Kite or Dhan.
4. **Add-ons end 2026-11-30 (swing shares, ND and AZ; investment-share averaging stays):** from that date report `0 add-ons (off)` and no add-on step.
4. **Section 2, run a skill.** The order skill and its counts (exits, add-ons, entries; investment-share stages for ND), the GTT or stop skill for shorts with no stop, and any pending order to record after the next open. An entry signal already bought today is not counted as pending. If a guardrail BLOCK is open, the line says orders are blocked until a refresh clears it.
5. **Section 3, decide.** The user's calls: unhedged short puts, orphaned long legs (and which are in profit), Supertrend colour flips with the old structure open, profit exits, and an unrecorded split.
6. **Section 4, housekeeping.** Uncommitted files in the repo. Data refreshes are pushed under the standing rule; code, skill and docs edits wait for the user's "push".
7. **End with the single most urgent next step** (for example "close the 5 legs past 3x in Kite, then run `/refresh-zerodha` after the close"), and offer the broker-specific detail skills: `/dhan-option-exit-signal`, `/zerodha-option-exit-signal`, `/dhan-option-scan-signal`, `/zerodha-option-scan-signal`.

## Rules
- Read-only. Never close, place, cancel or push anything from here.
- The list is only as fresh as the last refresh of each broker; never present it as live.
- Never invent a number: every count and name comes from the script's output.
- Facts and the next command only; the user decides.
