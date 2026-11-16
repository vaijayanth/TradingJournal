---
name: refresh-icici
description: Refresh the VJ TradeIQ ICICI (DI) workspace - the dividend portfolio's universe, 52-week-low ENTRY signals, dividend data and covered-call option signals - from Yahoo Finance and the public options list, verify, and (after confirmation) commit and push. Use when the user says "refresh icici", "/refresh-icici", "refresh DI", or wants the DI Dashboard / Covered Call pages updated.
---

# Refresh ICICI (DI)

Run from the repo root of TradingJournal on branch `claude/beautiful-hamilton-fwa55n`. Needs Python 3.10+ with `yfinance` and `pandas`. Everything lives under `icici-live/` and imports nothing from `dhan-live/` or `zerodha-live/` (ND, AZ and DI stay fully separate). No broker connector is needed yet: prices and dividends come from Yahoo, lot sizes and expiries from the public NFO instrument list.

**Tool names.** If the session exposes an ICICI connector later, use it for holdings; today there is none.

## The DI strategy (user, 2026-11-16)
- A dividend-focused portfolio; the universe is `icici-live/data/icici_universe.json` (29 stocks, given by the user).
- **Entry signal:** a stock's close is a new 52-week (252-session) CLOSING low (unadjusted prices). The user then adds a Rs20,000 position (whole shares, minimum 1), **at most once a week per stock**: averaging in at the bottom lifts the dividend yield. There is no other stock trading and no Live Trading page; there is no order skill (the user buys in ICICIdirect).
- **Options (Covered Call page):** the ND rules: Supertrend colour only, green = bull put spread (hedge 2 listed strikes lower), red = sell the call; only the stocks with listed options (23 of 29). No RSI override. Results/ex-dividend within 15 days is a warning.
- Pages: Dashboard (universe, dividend yield, ex-dividend dates, entry signals highlighted) and Covered Call. Live Trading, Performance and Analysis are not available for DI.

## Steps
1. **Prep.** `git status`, `git pull --ff-only`. Stop and tell the user if the tree has unrelated uncommitted changes.
2. **Refresh.** `python icici-live/scripts/refresh_icici.py`. It runs, in order: `update_options_master.py` (lots and expiries), `build_icici_data.py` (prices, 52-week lows, dividends, Supertrend, RSI, entry signals -> `icici_live_signals.json`), `fetch_option_events.py` (results / ex-dividend dates; a failure keeps the old file), `compute_covered_call.py` (-> `covered_call_signals.json`).
3. **Verify and report to the user:**
   - Market data date is the latest trading day; `failed` and `stale` lists are empty (a stock whose last bar is older than the others never raises a signal).
   - **ENTRY signals:** list each stock (price, qty to buy, cost, yield, last buy). Say plainly if there are none and name the 5 nearest to a 52-week low. A COOLDOWN row is a new low inside the 7-day window (no buy).
   - Data caveats that stay true until fixed: NIFTYIETF has too little Yahoo history (price only, no signal); NSDL is priced from BSE (`NSDL.BO`); a very high yield (PTC 22.7% on 2026-11-16) is probably a one-off dividend, never treat it as run-rate; next ex-dividend dates are estimates (last year's date + 1 year).
   - Covered call: signal counts (call / BPS), stocks without options, events that block or warn. No positions are tracked yet, so there are no option alerts.
4. **After the user buys:** record it so the weekly cooldown works: set `last_buy[SYMBOL] = YYYY-MM-DD` in `icici-live/data/di_trades.json` (ask for the date). The ICICIdirect holdings/tradebook upload is not connected yet; when it is, it fills this file and `holdings_snapshot.json` / `cc_positions.json`.
5. **Next skill to tell the user:** DI has no order skill. Say that the signals are for them to act on in ICICIdirect, and that `/refresh-icici` should be run again after the close the next trading day.
6. **Commit + push only after the user says push.** Stage only `icici-live/` files (and `index.html`/`.claude/skills` if they changed; never `.playwright-mcp/`). Message: `DI refresh <market date>`.

## Rules (do not change without the user)
- Never invent numbers; if a source is missing, say so. Never place an order from this skill.
- Closing-low signal only; the intraday-low touch is shown for information, it never triggers.
- ND, AZ and DI share no code or data: edit DI's copy only.
