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
1b. **Positions: ask first (user, 2026-11-19).** BEFORE running anything else, read `icici-live/data/cc_positions.json` and ask the user one question (AskUserQuestion), quoting what is on file: positions keyed as of `<date time IST>` (`<N>` hours/days ago), `<legs>` legs on `<stocks>` stocks, shorts/longs. Options: **(1) Upload new positions** (the user pastes the ICICIdirect positions screen; re-key it, below) or **(2) Go ahead with the existing positions** (use the file as is; say so in the report and mark every option P&L as "as of <keyed time>", not live; the user is often travelling, so this is a normal choice). Do not guess; wait for the answer. Option prices on file are the keyed LTP, never live.
   - Row format: `[SYMBOL, "YYYY-MM-DD" expiry, strike, "CE"|"PE", "LONG"|"SHORT", qty, avg price, ltp, trigger or null, pnl]`; set `as_of` to today. The screen shows 6-letter codes: BANBAR=BANKBARODA, BHAPET=BPCL, COALIN=COALINDIA, COMAGE=CAMS, HDFAMC=HDFCAMC, HINAER=HAL, HINZIN=HINDZINC, ICIBAN=ICICIBANK, INDHOT=INDHOTEL, INDOIL=IOC, LIC=LICI, NATALU=NATIONALUM, NATMIN=NMDC, POWFIN=PFC, RURELE=RECLTD, STABAN=SBIN (others are the NSE symbol; if a code is unknown ask, never guess).
   - Leave out NIFTY index options (note their unrealised P&L in the report), rows with no position but a pending order, and expiries before `track_from` (2026-11-01).
   - Before overwriting, diff old vs new by (symbol, expiry, strike, type, side) and keep the lists of NEW and CLOSED legs for the report. Then `python icici-live/scripts/import_positions.py` (check the leg and stock counts against the screen).
2. **Refresh.** `python icici-live/scripts/refresh_icici.py`. It runs, in order: `update_options_master.py` (lots and expiries), `build_icici_data.py` (prices, 52-week lows, dividends, Supertrend, RSI, entry signals -> `icici_live_signals.json`), `fetch_option_events.py` (results / ex-dividend dates; a failure keeps the old file), `compute_covered_call.py` (-> `covered_call_signals.json`).
3. **Verify.** Market data date is the latest trading day; `failed` and `stale` lists are empty (a stale stock never raises a signal). Data caveats that stay true until fixed: NIFTYIETF has too little Yahoo history (price only, no signal); NSDL is priced from BSE (`NSDL.BO`); a very high yield (PTC 22.7%) is probably a one-off dividend; next ex-dividend dates are estimates (last year + 1 year). Option prices on the screen are the user's keyed LTP, not live.
4. **After the user buys shares:** set `last_buy[SYMBOL] = YYYY-MM-DD` in `icici-live/data/di_trades.json` (ask for the date) so the weekly cooldown works.
5. **Plan first, then report (tables only, short; same layout as ND/AZ).** Run `python icici-live/scripts/option_entry_tiers.py` first, then show:
   - Heading `DI refresh: <date>`, then Check | Result: market data date, positions as of (keyed time, and "existing" or "new upload"), legs and stocks, guardrail-free note (DI has no guardrails), pushed commit.
   - **1 Entries:** (a) Share entries - ENTRY rows from `icici_live_signals.json` (52-week closing low): Stock | Price | Qty to buy | Cost | Yield | Last buy; none = say so and name the 5 nearest a 52-week low; COOLDOWN rows = new low inside 7 days, no buy. (b) Option entries - the Tier 1 to 5 table of `option_entry_tiers.py` (Stock | Supertrend | Since | Age | Price | Rule wants | event alert), stocks with open legs left out.
   - **2 Exits: stopped-out / flagged spreads to close now** (Exit, Through hedge, Beyond strike, Expiry risk, Event close, Profit Exit with a structure): one row per spread with BOTH legs: Stock | Short leg + P&L | Hedge leg + P&L | Net | Reason | Action.
   - **3 Other legs that need a decision** (event close, unhedged short, profit exit on a single leg): Stock | Leg | Reason | P&L | Action.
   - **4 Supertrend flipped but the old structure is still open** (status FLIP: green with a short call, red with a short put): Stock | Colour since | Open legs | Action.
   - **5 Orphaned long legs** (a long that hedges nothing): Stock | Leg | P&L | Action.
   - **6 Watch list** (HOLD structures near the strike or inside 7 days of expiry) and **Position changes** since the last paste (new / closed legs, only when a new upload was made) plus the untracked NIFTY P&L.
   - **7 Skills:** one row per skill: `/refresh-icici` (Done / run again after the next close); no DI order skill (Nothing to run).
   - **8 Your steps in ICICIdirect (manual):** numbered table of every close, hedge and share buy.
   - Never repeat a leg in two sections (point to the section that covers it). End with ONE numbered `Next step:` list of every remaining step, skills (A) and manual (B) never mixed.
6. **Commit + push the data refresh automatically (standing permission, user 2026-11-16: data refreshes may be pushed without asking; any ACTION or code/skill edit needs permission).** Stage only the refreshed `icici-live/` data files (`positions_manual.json`, `cc_positions.json`, `covered_call_signals.json`, `icici_live_signals.json`, `data/*`; never `.playwright-mcp/`, never code or skill edits). Message `DI refresh <market date>`; push to BOTH `claude/beautiful-hamilton-fwa55n` (Pages) and the session branch. If verify found something surprising, report and ask first. Say in the report that it was pushed.

## One-screen report (user, 2026-11-19; overrides every longer report layout in this skill)
The final report must fit one screen with no scrolling (about 35 lines). Working notes (verify details, scans, data fixes) are NOT printed; only what needs a decision.
1. **Status table** (Check | Result, one line each, at most 6 rows: market data, live prices / positions time, guardrails, positions, P&L, pushed commit). Add a row only for something abnormal.
2. **ONE action table**: `# | Type | Stock / leg | Why (max 6 words) | P&L | Do`, sorted by urgency (exits and stopped-out spreads first, then other legs, flipped calls, orphaned longs, entries). A spread is one row (both legs, net P&L). Stock orders (exits / add-ons / entries) are rows too. No empty sections: if a group has nothing, leave it out and put "none: <group>" in the status table only when that is news.
3. **Supertrend / entry signals:** show only FLIP rows and new-entry tiers 1 to 2 in full; everything else is a count in one line.
4. **Skills + manual steps:** ONE numbered `Next step:` list, each item tagged `[skill]` or `[manual]`, no separate tables.
5. Cell text is a short phrase (no sentences, no repeated explanations). The long per-section tables of the older layout are produced only if the user says "details" or names a section.

## Rules (do not change without the user)
- Never invent numbers; if a source is missing, say so. Never place an order from this skill.
- Closing-low signal only; the intraday-low touch is shown for information, it never triggers.
- ND, AZ and DI share no code or data: edit DI's copy only.
