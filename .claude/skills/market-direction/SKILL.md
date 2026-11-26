---
name: market-direction
description: Read-only pre-open market direction read for the Indian market from GIFT Nifty plus global cues (S&P and Nasdaq futures, Nikkei, Hang Seng, Brent, USD/INR, US 10y, India VIX) and the Nifty 50 Supertrend / 200-day regime, with what a gap means for the next-open AMO orders and the open option positions. Informational only: it never changes a rule, signal or order. Use when the user says "market direction", "check GIFT Nifty", "/market-direction", "will we gap up or down", or before the open / before placing orders.
---

# market-direction - pre-open read (read-only, informational only)

Runs `python scripts/market_direction.py [--gift <level> --gift-prev <previous close>]`. It places nothing, writes nothing and never changes a rule: ND and AZ stay rule-based (Supertrend colour, the stated entries and exits), this is only context for the user's own judgment.

## GIFT Nifty: read it from the broker MCPs (found 2026-11-25)
Both brokers list it. Zerodha is the source to use; the Dhan listing gave no live level.
1. **Zerodha (primary):** `market` with `mode: "quote"` and `instruments: ["NSEIX:GIFT NIFTY"]` (instrument token 291849). `last_price` is the live level, `timestamp` says when (IST) and `ohlc.close` is GIFT's own previous close. Pass them as `--gift <last_price> --gift-prev <ohlc.close>`. If the quote is missing or the timestamp is older than about 30 minutes before the open, say so.
2. **Dhan (fallback, weak):** symbol `GIFTNIFTY-INDEX`, `IDX_I` securityId 5024 (`search_agent_tool`, then `market_data_agent_tool` `ohlc` with `{"IDX_I": [5024, 13]}`). On 2026-11-25 it returned only the previous close (25,807.50, the same as Zerodha's `ohlc.close`) with no live level: do not use it as a live reading.
3. If neither MCP is signed in (run `/check-connectors`), ask the user once for the level (NSE IX / Kotak / Angel One / broker app); if they decline, run without it and label the read **global cues only, LOW confidence**. Never guess or quote a level from search snippets (web search only returns old snapshots).
4. The gap is measured against the **Nifty 50 cash close**, not GIFT's own previous close. Report both: when they differ by more than 0.5% the cash market was shut (holiday) or GIFT carries a futures premium (it is a near-month future, typically a few tenths of a percent), so the headline gap overstates the likely open by that basis. State that in one line.

## Steps
1. Fetch GIFT Nifty as above, then run the script. Note the Nifty bar date it prints: if the latest bar is older than the previous trading day, say there has been no new Indian session yet (holiday or no data).
2. **Report in ONE small table** plus one line each for flags and implications:

   | Item | Reading |
   |---|---|
   | GIFT gap vs Nifty close | `+0.4% (+100 pts)` or "not provided" |
   | Global cues | S&P fut, Nasdaq fut, Nikkei, Hang Seng, Brent, USD/INR, US 10y: only the moves worth noting |
   | India VIX | level and change |
   | Nifty regime | Supertrend colour and age, % vs 200-day average |
   | **Open bias** | UP / FLAT / DOWN, confidence |

3. **What it means for the books (one short line each, only the ones that apply; informational):**
   - **AMO BUY limits** (ND and AZ entries and, until 2026-11-30, add-ons, limit = signal-day high capped at close +2%): a gap-up through the limit simply does not fill; the rule is never to chase. A gap-down fills at or below the limit.
   - **AMO exits** (MARKET sell at the open): they fill at the open price whatever the gap.
   - **Open short options** (bull put spreads, short calls): a gap-down pressures the short puts, a gap-up the short calls. Name the covered-call stocks whose short strike is within the gap size of the last close only if `covered_call_signals.json` is fresh for that broker (read-only); otherwise say "run /refresh-dhan or /refresh-zerodha after the open for live strike alerts".
   - Never turn this into a rule change, a skipped signal or a changed order size. If a bias is DOWN with a rising VIX, say it is a reason to look at the option strikes, not to override the system.
4. Close with `Next step: <the one command>`: normally `/refresh-zerodha` / `/refresh-dhan` after the 09:15 open for live prices.

## Rules
- Read-only; one script run; no commits.
- Data is Yahoo's, delayed or partial before the open: say so when a cue looks stale (the script shows each cue's change vs the previous daily close).
- Keep the output to one table and a few short lines (the user's table-size rule).
