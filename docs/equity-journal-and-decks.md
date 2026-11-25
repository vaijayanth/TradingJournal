# Equity Trading Journal data model and strategy slide decks

> ARCHIVE (moved out of CLAUDE.md on 2026-11-25). The Journal tab is dormant (removed from the nav 2026-11-08); the rules below matter only if it is revived.
> Not loaded automatically. Read it only when the task touches this area. Where it contradicts the dated notes in CLAUDE.md, CLAUDE.md wins.

## Equity Trading Journal — Data Model (CRITICAL)

### Tradebook upload = full replace, not append (2026-10-19)
Every Tradebook export the user uploads covers their COMPLETE trade history from account inception — confirmed explicitly, never a partial window. Because of that, `_postFills` in the Apps Script (and `eqUploadFile()`/`eqPostFills()` in index.html) treat each upload as a full REPLACE of the FILLS sheet, exactly like Holdings already worked — clear + rewrite the whole tab, not append+dedupe. This permanently retired the old composite-key dedup logic and the Date-vs-string Sheets coercion bug that came with it (twice, in practice, a deployed Apps Script dedup fix silently failed to take effect because editing+saving a script doesn't update an already-published web app — only "New version" under Manage Deployments does — and every re-upload re-duplicated the whole sheet). There is no longer any existing-vs-incoming comparison to get wrong: the sheet becomes exactly what's in the uploaded file, every time. A lightweight within-file dedup (`eqRawFillKey`) still guards against a literal duplicate row inside one export.

**Do NOT reintroduce append+dedupe** unless the user explicitly says a future Tradebook upload will be a partial window — that's the one condition that makes full-replace unsafe (it would silently delete real older trades).

### Holdings is the final reference — Open Positions auto-corrects (2026-10-19)
**On any mismatch between FIFO (computed from Tradebook fills) and the uploaded Holdings snapshot, Holdings is always the final reference**, by the user's own explicit standing instruction. Holdings reflects what Zerodha actually shows the user holds right now; FIFO is a derived computation from fill history and can be wrong for reasons the Tradebook alone can never reveal (splits/demergers/mergers not yet modeled, off-market transfers, gifts, pledge invocations, fractional-share cash settlements).

The Open Positions table does NOT merely flag this — it auto-corrects. `eqApplyHoldingsOverride(fifoOpen, holdings)` (in both repos' index.html, search for it near `eqReconcile`) runs right after `eqBuildPositions` and before `eqRenderOpen`:
- Wherever a FIFO open position has a Holdings match (exact symbol, or series-suffix-stripped), the DISPLAYED qty/avgEntry become Holdings' own numbers, not FIFO's. FIFO's entryDate/fills are kept (Holdings has no history).
- A FIFO open position with **no** Holdings match at all is **dropped** from Open Positions — Holdings says the user doesn't actually hold it, so don't show a stale row (this is what "you don't need to worry about mismatch, fix it with holdings" means in practice).
- A Holdings position with **no** FIFO match (a gap in the uploaded Tradebook) is still **added** to Open Positions, qty/avgEntry from Holdings, entryDate shown as "—" and tagged "(Holdings only)".
- If Holdings hasn't been uploaded at all yet, Open Positions falls back to showing FIFO's own numbers untouched.

This means **a mismatch no longer requires any action to fix what's displayed** — the Reconciliation panel is now purely informational (diagnostic/curiosity), not an action list. You never need to ask the user to confirm a mismatch before the app shows correct numbers.

### When diagnosing a mismatch is still worth doing
`EQ_SPLIT_ADJUSTMENTS` and `EQ_MANUAL_FILLS` (same file, search `EQ_LONGTERM_EXCLUDE` for the whole block) still exist and still matter — but now ONLY for **closed-trade historical accuracy** (realized P&L on a stock once it's eventually sold), since Holdings has no historical record and the override above only affects the live Open Positions display. Don't feel obligated to chase every mismatch down anymore; only dig in if the user asks, or if getting a specific stock's eventual realized P&L right matters to them. When you do:
- A clean integer/near-integer qty ratio (2.00×, 0.50×, 4.00×, 0.25×...) → likely an unadjusted stock split/bonus/demerger. Research the actual corporate action (record date, ratio) and add it to `EQ_SPLIT_ADJUSTMENTS`. Demerger/scheme cost basis is NOT simply price÷ratio (fair-value apportionment, not proportional) — see the `costApportionPct` adjustment shape, back-solved from Holdings' own reported avg cost when the official apportionment % isn't published.
- A non-clean ratio with no public corporate action found → likely an off-market transfer/gift/pledge the Tradebook can't capture. **Ask the user to confirm** which number is real before touching anything — never guess. Once confirmed, add a same-cost manual "sell" to `EQ_MANUAL_FILLS` (zero artificial realized P&L).
- A full merger (company A delisted, becomes company B at a swap ratio) → **never** do a blanket per-fill symbol rewrite keyed only on the old symbol — that silently relabels any of that stock's OWN earlier, already-closed trades (that closed out before the merger) as the new company's trades, corrupting real realized P&L that has nothing to do with the merger. Instead add a manual close-then-open pair to `EQ_MANUAL_FILLS`: close the surviving open lot in the old symbol at cost (zero P&L), open the converted quantity in the new symbol at the equivalent per-share cost (price ÷ ratio). Floor fractional share counts (real corporate actions round down with cash for the fraction) — verify the floor against the user's own subsequent real trading in the new symbol if there is any (a sell with no matching real buy is strong evidence of the true post-merger share count).

The same fixes must always be mirrored into `vaijayanth/backtester`'s `index.html`, which hosts a synced copy of the same Equity Trading Journal feature.

## Strategy Summary Slide Decks (2026-10-30 session)

Three Claude Artifact slide decks were built summarizing the trading strategies covered in this project — private artifacts, not files in either repo:

1. **"SST Strategy Summary"** — the general SST (Sharegenius Swing Trading) philosophy as documented at the top of this file: 21-Day High entry, 200+50 EMA universe filter, two-state risk management, EMA-based add-on (50% qty), ₹20k base size capped at ₹1,00,000 over 16 tiers. **No backtest has ever been run or documented for this general framework.**
2. **"Dhan 52W High Swing Strategy"** — the actual live dh252 implementation: 252-day high + Supertrend-green entry (no EMA filter), WAC-based 6% add-on (10% qty, 7-day cooldown), single-rule exit on Supertrend red, ₹1,000 base size uncapped, plus the position-size-doubling milestone (100+ positions ever opened AND combined P&L positive → double effective tier size, re-evaluated every render — see `dh252EffectiveTierSize()` in backtester's index.html).
3. **"SST vs Dhan 52W High — Strategy Comparison"** — merges both of the above into one deck (Section 1 = SST, Section 2 = Dhan 52W High, Section 3 = backtest results + risks/positives comparison). This is the canonical merged deck; the first two are superseded by it but were kept rather than deleted.

### dh252 backtest — what is and isn't documented
The live dh252 journal has ONE documented 10-year backtest (252-day window, ₹1,000 base tiered uncapped, ₹5L capital, qty floored to 1 share), hardcoded as constants in backtester's index.html:
- `DH252_BACKTEST_CLOSED_TRADES = 5203`
- `DH252_BACKTEST_WIN_RATE = 42.05` (%)
- `DH252_BACKTEST_AVG_PLPCT = 8.45` (% across all closed trades)
- `DH252_BACKTEST_CAGR = 34.29` (% — "full 10yr equity curve: (final combined value / initial capital)^(1/years) - 1")

**XIRR, Calmar Ratio, and Max Drawdown for this specific run are NOT documented anywhere** and must never be fabricated for it. `backtester/scripts/backtest_252dh_supertrend.py` does compute `max_drawdown_pct` for whatever run it's given, but the actual output file for this exact 10yr/252d/₹1,000-tiered run isn't saved in the repo (`backtester/results/` only has two unrelated runs — different params, 24 and 4,551 closed trades, neither matching 5,203). If asked for these three numbers again: either ask the user if they have them from the original run, or re-run `backtest_252dh_supertrend.py` with these exact parameters to generate a fresh result file (Calmar can then be computed as CAGR ÷ max drawdown; XIRR needs actual cash-flow dates, which may or may not be in that script's output — check before promising it).

---

