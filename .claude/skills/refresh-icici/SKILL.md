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
1b. **Positions intake (user, 2026-11-19).** DI has no connector: option positions come from the ICICIdirect positions screen, keyed by hand into `icici-live/data/positions_manual.json`. If the user pasted a screen (or its recording) with this request, re-key it BEFORE the refresh; if not, say the positions are as of `cc_positions.json` `as_of` and ask for a fresh paste when that is not today.
   - Row format: `[SYMBOL, "YYYY-MM-DD" expiry, strike, "CE"|"PE", "LONG"|"SHORT", qty, avg price, ltp, trigger or null, pnl]`; set `as_of` to today. The screen shows 6-letter codes: BANBAR=BANKBARODA, BHAPET=BPCL, COALIN=COALINDIA, COMAGE=CAMS, HDFAMC=HDFCAMC, HINAER=HAL, HINZIN=HINDZINC, ICIBAN=ICICIBANK, INDHOT=INDHOTEL, INDOIL=IOC, LIC=LICI, NATALU=NATIONALUM, NATMIN=NMDC, POWFIN=PFC, RURELE=RECLTD, STABAN=SBIN (others are the NSE symbol; if a code is unknown ask, never guess).
   - Leave out NIFTY index options (note their unrealised P&L in the report), rows with no position but a pending order, and expiries before `track_from` (2026-11-01).
   - Before overwriting, diff old vs new by (symbol, expiry, strike, type, side) and keep the lists of NEW and CLOSED legs for the report. Then `python icici-live/scripts/import_positions.py` (check the leg and stock counts against the screen).
2. **Refresh.** `python icici-live/scripts/refresh_icici.py`. It runs, in order: `update_options_master.py` (lots and expiries), `build_icici_data.py` (prices, 52-week lows, dividends, Supertrend, RSI, entry signals -> `icici_live_signals.json`), `fetch_option_events.py` (results / ex-dividend dates; a failure keeps the old file), `compute_covered_call.py` (-> `covered_call_signals.json`).
3. **Verify.** Market data date is the latest trading day; `failed` and `stale` lists are empty (a stale stock never raises a signal). Data caveats that stay true until fixed: NIFTYIETF has too little Yahoo history (price only, no signal); NSDL is priced from BSE (`NSDL.BO`); a very high yield (PTC 22.7%) is probably a one-off dividend; next ex-dividend dates are estimates (last year + 1 year). Option prices on the screen are the user's keyed LTP, not live.
4. **After the user buys shares:** set `last_buy[SYMBOL] = YYYY-MM-DD` in `icici-live/data/di_trades.json` (ask for the date) so the weekly cooldown works.
5. **Plan first, then report (tables only, short; same layout as AZ/ND).** Run `python icici-live/scripts/option_entry_tiers.py` first, then show:
   - Heading `DI refresh: <date>`, then Check | Result: market data date, positions as of (keyed time), legs and stocks, pushed commit.
   - **1 Share entries:** ENTRY rows (price, qty, cost, yield, last buy); if none, say so and name the 5 nearest a 52-week low. COOLDOWN rows = new low inside 7 days, no buy.
   - **2 Option legs to close now** (type Exit / Event close / Profit Exit / Through hedge / Beyond strike / Expiry risk): one row per structure with BOTH legs (short, hedge, each P&L, net) | Reason | Action.
   - **3 Hedge gaps** (No hedge / Partly hedged / orphaned long): Stock | Uncovered qty | Action.
   - **4 Option entry signals: Supertrend by stock** (the `option_entry_tiers.py` table: Supertrend, since, age, price, rule wants, status NONE/HOLD/FLIP, open legs), then the Tier 1 to 5 counts and any `!!` / `!` event alerts.
   - **5 Positions changes** since the last paste (new / closed legs from step 1b) and the untracked NIFTY P&L.
   - Never repeat a leg in two sections.
   - End with ONE numbered `Next step:` list of every remaining step: **A. skills** (DI has none to run besides `/refresh-icici` again after the next close; there is no order skill) and **B. manual steps in ICICIdirect** (closes, hedges, share buys), never mixed.
6. **Commit + push the data refresh automatically (standing permission, user 2026-11-16: data refreshes may be pushed without asking; any ACTION or code/skill edit needs permission).** Stage only the refreshed `icici-live/` data files (`positions_manual.json`, `cc_positions.json`, `covered_call_signals.json`, `icici_live_signals.json`, `data/*`; never `.playwright-mcp/`, never code or skill edits). Message `DI refresh <market date>`; push to BOTH `claude/beautiful-hamilton-fwa55n` (Pages) and the session branch. If verify found something surprising, report and ask first. Say in the report that it was pushed.

## Rules (do not change without the user)
- Never invent numbers; if a source is missing, say so. Never place an order from this skill.
- Closing-low signal only; the intraday-low touch is shown for information, it never triggers.
- ND, AZ and DI share no code or data: edit DI's copy only.
