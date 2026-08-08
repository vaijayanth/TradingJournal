# TradingJournal — Project Context for Claude

## What this is
Single-file HTML trading journal (`index.html`) hosted on GitHub Pages at `https://vaijayanth.github.io/TradingJournal`.
Connected to a Google Sheet via Apps Script as a JSON middleware.

## SYSTEM DESIGN — READ BEFORE SUGGESTING ANYTHING

This is an **SST (Sharegenius Swing Trading) high-WR momentum system**. It is fundamentally different from Minervini/O'Neil fixed-stop systems. Read every point below before making any suggestion.

### Core System Philosophy
- **Target ≥70% win rate** — this is a HIGH win rate system, not a low-WR large-winner system. A 30-40% WR would be a sign something is wrong.
- **NO hard stop loss** — losses are held, not cut. Risk is managed via diversification (up to 200 positions) and the add-on rule (below).
- **GTT (Good Till Triggered) orders** handle both entries and exits — fully automated, no screen-watching needed.
- **Losers are HELD until recovery** — this is intentional system design, not a mistake. Do NOT suggest cutting losses fast.
- **Winners are HELD indefinitely** via GTT trailing — as long as the trend and fundamentals are intact.
- **True performance = realised + unrealised combined** — closed-only P&L looks misleadingly bad because losses sit open. Never judge system health from closed trades alone.

### Entry Rules
- **Universe**: Fundamentally strong stocks above 200 EMA AND 50 EMA
- **Signal**: Stock touches 21-Day High (21DH) — breakout candidate
- **Action**: Place GTT order at the 21DH price — entry triggers automatically when price breaks out
- **Setup types** (col S): Breakout, Pullback, 21 EMA Pullback, 10 EMA Pullback
- **Never chase** — if GTT misses the breakout, wait for the next 21DH signal

### Stop / Hold Rules (TWO STATES — no fixed stop)
**In Profit (P&L > 0):**
- Hold — do nothing unless at lock-in or target zone
- At 6% profit: trailing SL activates — verify GTT is set 6% below CMP
- At 7%+: raise GTT further to lock in more profit
- Hold indefinitely while fundamentals are intact

**In Loss (P&L < 0):**
- If stock is **above 200 EMA AND 50 EMA**: place a NEW GTT at 21DH for **50% add-on qty** — average into the position, the stock is still fundamentally intact
- If stock drops **below 50 EMA**: HOLD, do nothing — wait for structure to return. No exit.
- **Never exit on a loss** unless there is genuine fundamental deterioration (earnings collapse, fraud, sector disruption)

### Profit Taking
- Lock-in at **6%**: trailing SL activates, minimum 6% profit protected
- At **7%+**: raise trailing SL higher to capture more of the move
- Continue trailing as long as stock holds above support
- **No fixed profit target** — let the trailing GTT SL do the exiting
- Hold for weeks or months if the trend is intact

### Position Sizing
- Base position: **₹20,000 per trade**
- Increases: **+₹5,000 every 100 closed trades** → ₹20k → ₹25k → ₹30k → ... → ₹1,00,000 cap
- Hard cap: **₹1,00,000 per trade** (16 tiers of 100 trades each)
- Add-on size: **50% of current position size** (when averaging into a losing trade above 200+50 EMA)
- Max open positions: **200**

### Exit Rules
- Exit ONLY when trailing GTT SL is hit (fires automatically)
- In profit: GTT trailing SL at 6%+ handles exit
- In loss above 200+50 EMA: wait, consider adding — SST expects recovery on fundamentally strong stocks
- In loss below 50 EMA: hold indefinitely, no exit
- Full exit only on fundamental company issue

### What NOT to suggest for this system
- ❌ Do NOT suggest "cut losses fast" — losses are held by design
- ❌ Do NOT flag a 30-40% WR as bad — target is ≥70%, anything below signals a problem
- ❌ Do NOT suggest stop-loss slippage metrics
- ❌ Do NOT suggest position count limits — 200 is the intended max
- ❌ Do NOT suggest loss streak alerts — losers held open don't count as a streak
- ❌ Do NOT suggest R-multiple analysis — this system doesn't use fixed risk per trade

### The right health checks for this system
1. Win rate on closed trades ≥ 70%?
2. Are losses being held (not cut) — avg loss hold time should be long?
3. Are add-ons being taken correctly (above 200+50 EMA only)?
4. Is the combined P&L (realised + open MTM) positive?
5. Are GTT trailing SLs set on all profitable positions?

### "Init Risk ₹" (col K) / "Init Risk %" (col L)
These columns may be partially populated or irrelevant for SST. Never assume every trade has initRiskRs. Position size metric = `entryPrice × qty`, not initRiskRs.

## Repo & Branch
- Repo: `vaijayanth/TradingJournal`
- Active branch: `claude/beautiful-hamilton-fwa55n`
- Always push to this branch. GitHub Pages serves from it directly.

## Apps Script URL
`https://script.google.com/macros/s/AKfycbwh85dD1AlNlMFRk4M4A8yCA5YAs5gvnCIMgq6ixQUhdxmes-CqU3OYOdxtzDRLRgLq/exec`

## Google Sheet
- Sheet name: `TRADES`
- Portfolio value cell: `AK26` (realised only — initial capital + closed trade P&L. Does NOT include open position MTM from col Y)
- Initial capital cell: `AK20`

## Column Mapping (DEFAULT_CONFIG)
| Field | Column |
|---|---|
| Flag | B |
| Stock | E |
| Open Date | C |
| Close Date | D |
| EMA21 context | F (LIVE formula — not reliable for analysis) |
| CMP | H |
| 7-Day Low | I |
| Stop Loss | J |
| Init Risk ₹ | K |
| Init Risk % | L |
| Entry Price | R |
| Setup Type | S (plain label: "Breakout" or "Pullback" — see below) |
| % From Stop | W |
| Notional P&L% | X (plPct — blank for closed trades) |
| Notional P&L ₹ | Y (notionalPl — MTM, only filled for OPEN positions) |
| Partial Qty | Z |
| Partial Price | AA |
| Partial P&L | AB |
| Final Exit Price | AC |
| Final P&L ₹ | AD |
| Final P&L % | AE |
| Age (days) | AF |
| MAE% | AL |
| MFE% | AM |

## Critical Data Facts
- **Column Y (notionalPl)**: mark-to-market, only populated for OPEN positions. Zero/blank for closed trades.
- **Column X (plPct)**: also blank for closed trades in this sheet.
- **Column F (ema21)**: live formula showing current EMA position — NOT entry-time value. Do NOT use for analysis.
- **Setup Type (col S)**: SIMPLIFIED — plain text label only. Four valid values:
  - `"Breakout"` — smooth breakout of 52-week high
  - `"Pullback"` — generic pullback entry
  - `"21 EMA Pullback"` — clear pullback to 21 EMA on a breakout stock
  - `"10 EMA Pullback"` — tight pullback to 10 EMA on a strongly trending stock
  - Old compound codes (BKT/VCP/VCL_SL_LT10 etc.) are fully retired.
  - `parseSetupType(code)` is a direct passthrough: `{ label: code.trim(), pattern: code.trim() }`. No SETUP_PATTERN_LABELS, SETUP_TIER_LABELS, or patternMap. Any new setup type added to the sheet automatically appears in Analysis breakdown with no code changes needed.
- **portfolioValue (AK26)**: realised only — does NOT include open position unrealized P&L. True combined P&L = `(portfolioValue - initialCapital) + sum(notionalPl)` = `totalFinalPl + totalUnrealisedPl`.
- **Date format from Apps Script**: `dd-MMM-yyyy` (e.g., `21-Apr-2026`) — NOT parseable by `new Date()`. Use `parseDate()` helper everywhere.

## Trading Strategy (IMPORTANT — read SYSTEM DESIGN section above first)

The canonical strategy is stored in `STRAT_DEFAULT_RULES` in index.html (around line 9209). That is the source of truth. Summary:

- **Entry**: GTT at 21-Day High — auto-triggers on breakout. Universe = above 200 EMA + 50 EMA.
- **In profit**: Trail via GTT. Lock-in at 6%, raise at 7%+. Hold indefinitely.
- **In loss, above 200+50 EMA**: Hold + add 50% qty via new GTT at 21DH.
- **In loss, below 50 EMA**: Hold. Do nothing. Wait for structure.
- **Exit**: Only when GTT trailing SL fires, or fundamental collapse.
- **Sizing**: ₹20,000 base, +₹5k per 100 closed trades (₹25k → ₹30k → ... → ₹1L cap), max 200 positions.
- **Initial capital**: ₹50,00,000 (₹50L)
- **Notional P&L** = open trade unrealized MTM from col Y — NOT a what-if on closed trades.
- **True performance** = realised + unrealised combined.

## SST Health Metrics (what to show and track)
| Metric | Target | Note |
|---|---|---|
| Win rate (closed) | ≥ 70% | High-WR system — below 60% signals a problem |
| Combined P&L (realised + MTM) | Positive | Closed-only always looks bad — don't use alone |
| Open portfolio profitable | ≥ 60% | Portfolio breadth health |
| GTT coverage | 100% of profitable positions | Every in-profit trade should have active GTT |
| Add-ons executed | When eligible | Loss above 200+50 EMA → 50% add-on should be placed |
| Combined profit factor | ≥ 2.0 | High WR system should have high PF |

## UI Changes Made (2026-08-03 session)
- **Performance tab**: SST System Health Banner (5 checks), renamed R-Multiple → Win:Loss Ratio, removed "planned risk" language, added avg win/loss ₹, Copy Summary button
- **Analysis tab**: SST Analysis Health Banner (5 checks), replaced all stop-loss/risk-tier language with SST framing, Loss:Winner Ratio replaces Stop Slippage, "If WR improves to 40%" projection replaces "full risk cap" projection, Open Portfolio Quality replaces Risk Tier card

## UI Changes Made (2026-08-07 session)

### Re-entry Watchlist (Dashboard)
- Card `#dash-reentry-card` shows stocks eligible for re-entry consideration
- **Logic**: group all closed trades by stock → exclude any stock currently in open positions → keep only stocks where most recent close was **≥ 6 trading days ago** (Mon–Fri only, not calendar days)
- Shows one row per stock: #, Stock, Last Closed, Days Since (trading days), Last P&L%, Times Traded, W/L history
- Sorted by days since close (ascending — most recently eligible first)
- If a stock has been traded multiple times, uses the MOST RECENT close date to check eligibility
- JS: IIFE inside `renderDashboard`, uses `tradingDaysBetween(from, to)` helper (counts Mon–Fri only)
- Collapsed by default, toggled via `toggleReentryList()`

### Equity Curve (Dashboard) — `_renderDashEqChart()`
- **Default mode changed**: `window._dashEqMode = '₹'` (absolute portfolio value, not % return)
- **Aggregated by date**: trades grouped by close date before plotting — one data point per unique date. Multiple trades closing same day merge into one point. Tooltip lists all stocks for that date.
- **X-axis**: sparse labels formatted as "Aug 26" style, max 8 labels, duplicates suppressed
- **Y-axis**: compact format — ₹50.2L, ₹1.5k etc. Dynamic decimals for % mode (3dp if range <0.5%, 2dp if <5%, 1dp otherwise)
- **Simplified style**: thin line (2px), very light fill (opacity 0.01–0.2), subtle horizontal grid lines, no Break-even annotation, legend top-right only when combined series visible
- Toggle button still available to switch to % Return mode

## Key Helpers in index.html
```javascript
// Date parsing — MUST use this everywhere, not new Date()
function parseDate(s) {
  if (!s) return new Date(0);
  const m = s.match(/^(\d{1,2})-([A-Za-z]{3})-(\d{4})$/);
  if (m) return new Date(`${m[2]} ${parseInt(m[1])}, ${m[3]}`);
  return new Date(s);
}

// Config
const CONFIG_KEY = 'tj_config_v1';
function loadConfig() { ... }
function saveConfig(cfg) { localStorage.setItem(CONFIG_KEY, JSON.stringify(cfg)); }
```

## Architecture
- `fetchData()` — calls Apps Script, returns `{ open, closed, portfolioValue, initialCapital }`
- `renderDashboard(data, cfg)` — Dashboard tab
- `renderPerfStats(closed, open, portfolioValue, initialCapital)` — Performance tab stats
- `initPerfCharts(closed, initialCapital, open)` — Performance tab charts
- `renderPositionsReal(open, cfg)` — Positions tab
- `renderClosedTradesReal(closed)` — closed trades table
- `initAnalysisCharts(open, closed)` — Analysis tab
- `populateConfigPage()` — fills Config form from localStorage
- `saveAllConfig()` — saves Config form to localStorage
- `setPeriod(btn, period)` — filters Performance tab by 30/90/all days

## What "Notional" means to the user
Open trades only — unrealized mark-to-market P&L from col Y. NOT a what-if calculation on closed trades.

## What drives KPIs
All KPIs (expectancy, win rate, RoP, equity curve) must show **combined realized + unrealized** picture, not closed-only. Closed-only looks like a losing system because stops are taken fast.

## Expectancy Card (3 lines)
1. Realised: avg finalPlPct% across closed trades
2. Unrealised: avg notionalPl ₹ per open trade (not % — too small)
3. Combined: (totalFinalPl + totalNotionalPl) / totalTrades / initialCapital × 100

## Equity Curve
- Main series: cumulative realised P&L from closed trades (area chart)
- Dashed amber series: extends to "Today" = realised + total open MTM
- Drawdown chart: closed trades only (no Today point — unrealised MTM is not a true drawdown)

## Analysis Tab
`initAnalysisCharts(open, closed)` reads `BE_TRIGGER`/`PARTIAL_TRIGGER` from Config and `window._data.initialCapital` (NOT a function param — must read from global, `destroyAndReinitAnalysis()` calls this fn standalone). All 8+ ApexCharts calls wrapped in try-catch so one bad chart doesn't abort the rest of the function.

Sections, top to bottom:
1. **Setup Type breakdown table** (col S) — win rate, **WR (Last 30)** recency column with ↑↓ arrow vs all-time WR, R-multiple, Expectancy R, avg P&L%/win%/loss%, total P&L per setup
2. **Win Rate by Setup** + **Avg P&L% by Setup** bar charts
3. **Trade Management** — ₹ Risk per Trade distribution, Winner vs Loser Hold Duration, Closed Winner Size Distribution, Loss Size Distribution. KPI cards: avg risk, avg actual loss, **Stop Slippage** (negative/saved = green, positive/over-stop = red/amber), median winner
4. **Partial Exit Analysis** — comparison of trades that took partial at trigger vs those that reached trigger but held full position; "Action Now" card lists pending partials
5. **Behavioural Patterns**:
   - After 3+ Consecutive Losses — next-trade WR vs overall WR
   - Risk per Trade vs Recommended Tier
   - **Current Streak** — live win/loss streak count, colour-coded (red 🚨 at 3+ losses, green ✓ on hot streak)
   - **Learning Curve** — first 30 vs last 30 closed trades: WR + avg P&L% with improving/declining/stable verdict
6. **Pattern Analysis** — "Cut Fast, Run Long?" scatter (hold days vs P&L%, red/green/amber for loss/win/open), Entry Velocity by week (with high-velocity-week performance comparison), **Monthly P&L bar chart** (realised + current-month unrealised MTM — same chart as Performance tab, now also here)
7. Unlock Advanced Analytics (collapsible) — MAE/MFE, entry time, trade quality tag, sector: all need new sheet columns, see Pending Backlog

EMA analysis REMOVED (col F is live formula, not entry-time — never use for analysis).

## Authentication
- Password gate is hardcoded in source — works on ALL devices without setup
- Password: `test1234`
- Hash (SHA-256): `937e8d5fbb48bd4949536cd65b8d35c426b80d2f830c5c308e2cdec422ae2244`
- Stored in `AUTH_HASH` constant in index.html
- To change password globally: update `AUTH_HASH` in source with new SHA-256 hash and push
- localStorage override still works — setting password via Config tab overrides for that browser only
- Reset URL: append `?reset=1` to clear localStorage auth

## Apps Script — Key Rules
- Flag col B: `YES` = open trade, `NO` = closed trade or watchlist
- **Closed trade filter**: `flag === 'NO' && trade.finalPl !== 0` — excludes watchlist rows (NO flag but blank col AD)
- Col AH (haChanged): sheet stores TRUE/FALSE boolean — Apps Script converts to `'Y'`/`'N'` string
- Portfolio cell: `AK26`, Initial capital cell: `AK20` (shifted when AG/AH columns were added)

## Heikin-Ashi Columns (AG/AH)
- Col AG: current HA candle colour ("Red"/"Green") — `haColour`
- Col AH: did colour change today? (TRUE/FALSE boolean in sheet) — `haChanged` = 'Y'/'N'
- `haWarn`: profit ≥ 5% AND haColour = "red" — momentum fading on a winner

## Alert Groups (Dashboard) — priority order
1. 🔴 Exit Triggered — effPct ≤ 0
2. 📉 Below 21 EMA — ema21 = "Below" AND plPct > 0
3. 🛡 Move Stop to Breakeven — plPct ≥ 5% AND stopLoss < entryPrice
4. ⚠ Profit at Risk — HA Red — plPct ≥ 5% AND haColour = "red"
5. 🔄 HA Momentum Shift — haChanged = 'Y'
6. 🟡 Near Stop / Review — effPct ≤ stopProximity
7. 🟢 Partial Exit Pending — plPct ≥ partialTrigger AND partialTaken = 'N'

## Stop Logic
```javascript
const effStop = t.stopLoss || 0;  // col J only — 7DL is NOT a mechanical stop
const effPct = (t.cmp && effStop) ? ((t.cmp - effStop) / t.cmp * 100) : t.pctFromStop;
```
- `effStop = t.stopLoss` (col J) — never MAX(J,I). 7-day low is informational only.
- "Exit Triggered" alert fires only when CMP ≤ col J
- 7DL breach renders as a grey `info` group alert — "watch 21 EMA, no action required"
- Positions table header: "Stop ₹" (col J mechanical stop)
- Expand row shows: col J stop, 7-Day Low (informational), separately labelled

## Risk Tier Card (Dashboard)
- Shows current recommended risk per trade based on closed trade count
- `riskTierRs = Math.min(1000 + Math.floor(closed.length / 100) * 500, riskCapRs)`
- `riskCapRs = initialCapital * 0.008`
- Badge shows "Next tier in N trades" or "At cap"

## Recent Fixes Applied
- Drawdown Y-axis: `toFixed(2)` to prevent floating-point scientific notation
- Date parsing: `parseDate()` everywhere (Apps Script returns `dd-MMM-yyyy`)
- Period filter (30/90 days): actually filters closed trades and re-renders
- Config URL: auto-saves on blur (no need to click Save)
- `portfolioValue` from sheet cell AK26 is the source of truth for portfolio headline
- `alertCount` badge uses effective stop MAX(J,I) not col W
- Closed trade count: Apps Script filters `flag === 'NO' && finalPl !== 0` to exclude watchlist
- Analysis tab: `initialCapital` read from `window._data` (was crashing on standalone re-init)
- Analysis tab: all chart instantiations wrapped in try-catch (one bad chart no longer aborts KPI population)
- Analysis tab: Stop Slippage colour fixed (negative/saved = green, was backwards)
- Analysis tab: added Current Streak, Learning Curve, Setup Type WR (Last 30), Monthly P&L chart — completed 2026-06-16
- **Setup type SIMPLIFIED** (2026-07-25): `parseSetupType(code)` now does direct passthrough — label = raw col S value. Sheet values changed to plain "Breakout" / "Pullback". All old compound-code parsing removed (no SETUP_PATTERN_LABELS, patternMap etc.). Analysis setup breakdown now shows Breakout vs Pullback head-to-head.
- Position count limit alert REMOVED — system scales by 0.8% portfolio risk cap (not a fixed 15-position limit). Do NOT add a position count alert.

## Changes — 2026-07-04 Session

### Edge Diagnostics (Analysis tab) — Key Bug Fixes
- **R-Multiple**: was using `finalPlPct / initRiskPct` (different denominators). Fixed to `finalPl / initRiskRs` (₹ ÷ ₹ = true R).
- **Hold Duration**: filter was `&& t.age` (passes negative/0, truthy). Fixed to `parseInt(t.age||0) > 0` everywhere.
- **Partial Execution %**: was counting all closed 'Y' trades, not just eligible ones. Fixed to scope to `partialEligible.filter(...)`.
- **`t.ageDays`**: field doesn't exist — it's `t.age`. Fixed across all Edge Diagnostic code.
- **Dead `slippage` variable**: removed (was subtracting `initRiskPct` from `finalPlPct` — meaningless cross-denominator).

### MAR Ratio Card (Performance tab, line ~4053)
- Always shows all-time MAR as headline (short periods give inflated/misleading CAGR)
- `calcMAR(sliceClosed, ic, openMTM)` helper — computes CAGR + max drawdown from closed dates
- Trend bar compares all-time vs 90d vs 30d — shows direction without implying short-period is comparable
- Plain-English explanation + "short-period inflation warning" for < 6-month windows

### Edge Diagnostics — 7 New Charts Added (Analysis tab)
All in `initAnalysisCharts`, section `asec-edge`. Uses `_chartQ` async queue. Charts:
1. **R-Multiple Distribution** — histogram of `finalPl/initRiskRs`, reference lines at 0R and 2R
2. **Rolling Profit Factor** (last 20 trades) — line chart, reference at PF=1.0
3. **Cumulative R by Trade #** — running sum of R across all closed trades
4. **Win Rate by Hold Duration** — bucketed (1–5d, 6–10d, 11–20d, 21–40d, 40d+), WR per bucket
5. **Risk-Reward Scatter** — `initRiskPct` vs `finalPlPct`, coloured by win/loss
6. **Trade Frequency by Month** — bar chart of entry count per month
7. **Drawdown Recovery** — days to recover from each drawdown trough (closed equity curve)

### Stop Trigger Calibration (Analysis tab, replaces "2% vs 5% comparison")
Section id: `asec-be-impact`. Renamed and rebuilt forward-looking:
- **Card 1**: trades reaching +`beTrigger`% that became big winners (>+15%)
- **Card 2**: trades that reversed to ~0% (BE stop caught them)
- **Card 3**: full outcome breakdown bar
- **Chart 1**: final P&L distribution for all trades that hit the trigger
- **Chart 2**: MFE (peak) distribution — shows runway for 21 EMA trail
- All labels dynamically read from `cfg.beTrigger` — adapts if user changes Config
- Removed "Old BE Trigger" Config field (no longer needed)

### `calcStats` Helper (Analysis tab, line ~5703)
True R-multiple computation — canonical version for all setup-breakdown calculations:
```javascript
const winsR = wins.filter(t => t.initRiskRs > 0);
const lossR = losses.filter(t => t.initRiskRs > 0);
const useRs = winsR.length > 0 && lossR.length > 0;
const avgWinR  = useRs ? winsR.reduce((s,t) => s + t.finalPl/t.initRiskRs, 0)/winsR.length : aw;
const avgLossR = useRs ? Math.abs(lossR.reduce((s,t) => s + t.finalPl/t.initRiskRs, 0)/lossR.length) : al;
```

### Changes — 2026-07-25 Session

#### Setup Type Simplification
- Removed all compound-code parsing (BKT/VCP/VCL_SL_LT10 etc.)
- Sheet col S now contains plain `"Breakout"` or `"Pullback"` — user updated sheet directly
- `parseSetupType()` is now a 3-line passthrough
- Analysis breakdown compares Breakout vs Pullback head-to-head (no more pattern/tier sub-groups)
- Positions table, closed trades table, and all analysis charts updated

#### Strategy Tab Updated
- Entry: four setup types — Breakout, Pullback, 21 EMA Pullback, 10 EMA Pullback
- Stop: Phase 1 = hold initial risk-defined stop (col J fixed). Phase 2 at ≥7% profit = move col J ONCE to breakeven. After BE, watch 21 EMA support manually and trail/exit there.
- 7-day low is NOT a mechanical stop — informational only
- Profit: 50% at +10%, trail rest watching 21 EMA support

#### Market Regime / Portfolio Breadth (Today Tab)
- **Portfolio Breadth Panel** (`#today-breadth-panel`) — collapsible panel in Today tab above action sections
- Shows open position health bars: above 21 EMA %, profitable %, risk-free %
- **Market Regime section** — inside breadth panel, fetches from NSEFO sheet (F&O watchlist) silently in background
  - Three ETFs tracked: NIFTYBEES (`/NIFTY.*BEES|NIFTYBEES/i`), MIDCAPETF (`/MIDCAP/i`), SMALLCAP (`/SMALLCAP/i`)
  - `haColour` normalised: `typeof v === 'string' ? v : (v === true ? 'Green' : v === false ? 'Red' : '')`
  - Combined regime score = avg of [ema200, ema50, ema20, haGreen] across all found ETFs (0–4 range)
  - Bull ≥ 3, Bear < 2, Neutral in between
- **`window._breadthData`** — cached F&O watchlist for swing breadth panel (set after silent background fetch in `refreshData()`)
- Silent F&O fetch in `refreshData()`:
  ```javascript
  if (cfg.url && !window._breadthData) {
    fetchFnoData().then(d => {
      if (d && d.watchlist) {
        window._breadthData = d.watchlist;
        if (window._data) renderTodayActions(window._data.open, loadConfig());
      }
    }).catch(() => {});
  }
  ```

#### F&O Breadth Section Extended
- `fnoRenderBreadth(watchlist)` rewritten with INDEX_ETFS array
- F&O breadth now shows NIFTYBEES + MIDCAPETF + SMALLCAP ETF cards with EMA/HA status
- Divergence note shown when ETFs disagree on direction
- Stock breadth bars exclude ETF rows (filtered by name regex)

#### 5 Minervini-Standard Improvements (2026-07-25)
1. **Market Direction toggle** (`#mkt-direction-bar`) — top of Today tab, 3 states:
   - 📈 Confirmed Uptrend → full size, seek breakouts
   - ⚠ Under Pressure → 50% size, no new breakouts, tighten stops
   - 📉 In Correction → no new entries, protect profits, raise all stops to BE
   - Persists in `localStorage` key `MKT_DIR_KEY = 'tj_mkt_direction'`
   - Functions: `setMktDirection(state)`, `renderMktDirection()` — called at start of every `renderTodayActions()`
   - Bar colour and background change to match active state

2. **No-winner-in-30-days alert** (`#dash-no-winner-alert`) — Dashboard
   - Amber pill shown when `daysSinceWin > 30`
   - Asks: "is your system still producing? Review open positions and market conditions"
   - Hidden (display:none) when daysSinceWin ≤ 30 or no closed trades

3. **Edge Diagnostics jump link** — Analysis sub-nav
   - Added `<a href="#asec-edge">Edge Diagnostics</a>` after MAE/MFE link

4. **Entry Precision proxy card** — Trade Management section (spans 2 columns)
   - Splits closed trades by `initRiskPct ≤ 5%` (tight, near pivot) vs `> 5%` (extended)
   - Shows WR and avg P&L% for each tier — O'Neil entry discipline check
   - Elements: `#ep-tight-wr`, `#ep-tight-sub`, `#ep-wide-wr`, `#ep-wide-sub`, `#ep-insight`
   - Wrapped in try-catch

5. **Init Risk ₹ column** — Positions table
   - New `<th>Risk ₹</th>` after Entry ₹
   - Shows `t.initRiskRs` formatted as ₹ amount (or "—")
   - Expand row colspan bumped from 12 → 13

### Pending — Next Logical Enhancements
- **Position Concentration Risk card (Dashboard)** — top-3 positions as % of portfolio notional. No new sheet columns needed, can implement immediately.
- **Market Timing / Tape Health** — NIFTY trend status on Dashboard (needs data feed decision; Market Direction toggle is manual workaround for now).
- **Alpha vs NIFTY** — monthly return overlay on equity curve (needs NIFTY monthly data).
- **Equity curve red/green gradient** — indexed colorStops based on cumulative P&L direction.

## Performance Tab — Calibrated Metric Rules (CRITICAL)

These metrics were audited 2026-06-19 and corrected for trailing-stop system behaviour. Do NOT revert these calibrations:

### Combined vs Closed-only
- **Profit Factor**: numerator = closed wins ₹ + open unrealised MTM; denominator = closed losses ₹. NOT closed-only. Closed-only PF shown as footnote.
- **R-Expectancy**: uses **combined WR** (closed wins + open profitable / all trades), not closed WR. Closed-only WR of ~25% gives false negative (-0.38R); combined WR gives true edge (+0.19R). Footnote shows closed-only for context.
- **MAR Ratio CAGR**: uses combined equity (realised + open MTM), not AK26 alone. Max DD still uses realised-only equity path (documented in card footnote).
- **Combined Expectancy**: shown as ₹/trade (not % — rounds to 0.0% and is meaningless).

### Win Rate Colour Thresholds (calibrated for this system)
- **Closed WR**: green ≥40%, amber ≥20%, red <20% — (25-30% is NORMAL and HEALTHY)
- **Combined WR**: green ≥40%, amber ≥28%, red <28%
- **Win Rate Trend chart / Win Rate by Entry Day / Setup WR chart**: reference line at **30%** (not 50%). Bar colours: green ≥40%, amber ≥20%, red <20%.

### Cards with "expected negative / closed-only" context
- **Expectancy headline**: labelled "Realised (closed stops — expected negative)" — do not make it green
- **Sharpe ratio**: closed-only, expected negative for this system → amber (not red) unless below -0.5. Label: "Closed trades only — expected negative; open winners excluded"
- **Max Streaks**: loss count shown in amber (not red), with note "open winners not counted here"

### Equity Curve
- Main solid series: cumulative realised P&L (red/green area)
- **Second dashed amber series**: all null for closed dates, connects from last closed value, extends to "Today" = realised + total open MTM. Renders as dashed amber with legend. **This is the true portfolio value line.**
- Drawdown: closed trades only (no Today point)

### Closed Trades Table
- Column shows **"Final P&L ₹"** (actual exit P&L in ₹) — NOT "Notional P&L%" which is blank for all closed trades
- Setup column shows parsed friendly label (e.g. "Breakout · <10% SL") not raw code

### Alert System
- No position count limit alert — user scales by 0.8% risk cap
- Exit Triggered alerts only show genuine stop/EMA breaches

---

## F&O Module

### Overview
Second strategy module — NSE credit spreads watchlist. Toggled via top-level strategy switcher.
- Sheet: `NSEFO` (same Google Sheet, different tab)
- Apps Script: same URL, pass `?mode=fno` (or body param `mode=fno`)
- No trading journal — just a watchlist with signal scoring and spread recommendation

### Strategy
- **Uptrend** → open **Put Spread** (sell 0.2 delta PE, buy hedge 2 strikes lower)
- **Downtrend** → open **Call Spread** (sell 0.2 delta CE, buy hedge 2 strikes higher)
- **Exit sell leg** if premium doubles (risk management)
- **Add Call Spread** when HA turns Red on an existing spread position (downtrend accelerates profit)

### NSEFO Sheet Column Mapping
Cols A–E are empty. Data starts at col F (index 5).

| Index | Column | Field | JS key |
|---|---|---|---|
| 5 | F | BROKER | broker (string, e.g. "Zerodha"/"Upstox" — used to split risk across brokers) |
| 6 | G | STOCK | stock |
| 7 | H | CMP | cmp |
| 8 | I | 200 EMA ABOVE | ema200 (bool) |
| 9 | J | 50 EMA ABOVE | ema50 (bool) |
| 10 | K | 20 EMA ABOVE | ema20 (bool) |
| 11 | L | HK COLOR | haColour ("Red"/"Green") |
| 12 | M | HK CHANGED TODAY? | haChanged (bool) |
| 13 | N | ATH | ath (bool) |
| 14 | O | 52WH | wk52h (bool) |
| 15 | P | 21DH | dh21 (bool) |
| 16 | Q | 7DH | dh7 (bool) |
| 17 | R | GAPUP | hasGapUp (bool) |
| 18 | S | 200 EMA CROSS | ema200cross (bool) |
| 19 | T | 50 EMA CROSS | ema50cross (bool) |
| 20 | U | 21 EMA CROSS | ema21cross (bool) |
| 21 | V | 7DL | sevenDayLow |
| 22 | W | %FROM 7DL | pctFrom7DL |
| 23 | X | SPREAD ACTIVE | spreadActive — string: `'CALL'` \| `'PUT'` \| `'CALLPUT'` \| `''` (empty = no spread active) |

### Signal Scoring
```javascript
function fnoScore(s) {
  const bull = [s.ema200, s.ema50, s.ema20, s.haColour.toLowerCase()==='green',
    s.ath||s.wk52h||s.dh21||s.dh7, s.hasGapUp].filter(Boolean).length; // max 6
  const bear = [!s.ema200, !s.ema50, !s.ema20, s.haColour.toLowerCase()==='red'].filter(Boolean).length; // max 4
  return { bull, bear };
}
function fnoTrend(s) {
  const { bull, bear } = fnoScore(s);
  if (bull >= 4) return 'bullish';
  if (bear >= 3) return 'bearish';
  return 'mixed';
}
// Helpers for spreadActive string type
function fnoHasSpread(s)    { return s.spreadActive === 'CALL' || s.spreadActive === 'PUT' || s.spreadActive === 'CALLPUT'; }
function fnoHasPutSpread(s) { return s.spreadActive === 'PUT'  || s.spreadActive === 'CALLPUT'; }
function fnoHasCallSpread(s){ return s.spreadActive === 'CALL' || s.spreadActive === 'CALLPUT'; }
function fnoSpreadLabel(s)  { return s.spreadActive === 'CALLPUT' ? 'CALL+PUT' : s.spreadActive || ''; }

function fnoAction(s) {
  const trend = fnoTrend(s);
  const haRed = s.haColour.toLowerCase() === 'red';
  const haRedToday = haRed && s.haChanged;
  if (fnoHasPutSpread(s) && haRedToday) return 'add-call'; // only when PUT active
  if (trend === 'bullish' && !haRed) return 'put-spread';
  if (trend === 'bearish' || (haRedToday && !fnoHasSpread(s))) return 'call-spread';
  return 'wait';
}
```

### Apps Script — F&O Mode
When `mode=fno`, Apps Script reads NSEFO sheet and returns:
```json
{ "success": true, "watchlist": [...], "fetchedAt": "..." }
```
Each watchlist item maps NSEFO columns using row indices 5–23 (0-based).

**CRITICAL**: Apps Script must use `row[6]` for STOCK (col G), not `row[0]`. All column offsets are 5+ from 0.

**CRITICAL**: Apps Script must map `row[5]` (col F) to JS key **`broker`** (not `date` — col F header is BROKER, the doc previously said DATE which was wrong/stale). The front-end (`fnoRenderBrokerPills`, `renderFnoWatchlist`, `fnoRenderActiveSpreads`, `fnoRenderTopCandidates`, `fnoRenderAlerts`) reads `s.broker` directly and will show "—" for every row until the Apps Script returns it under that key. Also confirm the Apps Script actually populates `ema200cross`/`ema50cross`/`ema21cross` (cols S/T/U) and `sevenDayLow` (col V) in the response — the front-end now consumes all of these (`fnoFreshCross()` for the "Fresh Cross" badge, raw 7DL value as a tooltip on the "% from 7DL" column) but they were previously fetched-and-unused, so it's unverified whether the script was ever actually wired to return them.

### Code Structure (F&O Isolation)
- All F&O JS functions prefixed `fno*`
- `window._fnoData` stores F&O data (never mixed with `window._data`)
- `window._strategy` = `'swing'` | `'fno'`
- HTML: `#fno-pages` (hidden by default), `#fno-nav-tabs` (hidden by default)
- HTML: `#swing-pages` (visible by default)
- Boundary comments in index.html mark SWING MODULE END / F&O MODULE START

### Strategy Switcher
```html
<div class="strategy-bar">
  <button class="sw-btn active" id="sw-swing" onclick="switchStrategy('swing')">📈 Swing</button>
  <button class="sw-btn" id="sw-fno" onclick="switchStrategy('fno')">📊 F&amp;O</button>
</div>
```
`switchStrategy(mode)` toggles visibility of `#swing-pages`/`#fno-pages` and `#fno-nav-tabs`, sets `window._strategy`, triggers data fetch for the selected module.

### F&O Entry Points
- `refreshFnoData()` — fetches from Apps Script with `mode=fno`, stores in `window._fnoData`
- `renderFnoDashboard(data)` — summary cards for F&O tab
- `renderFnoWatchlist(data)` — watchlist table with signal badges and action recommendation

---

## Pending Backlog (Guru Audit — Minervini / O'Neil)

These were identified in a guru-perspective audit and deferred. Implement when ready.

**Status as of 2026-06-16**: Analysis tab UI audit fully implemented (bugs + 4 features). MAE/MFE Analysis (item 2 below) also fully implemented and verified live — see below. All changes pushed, working tree clean. Next logical step: item 7 (Position Concentration Risk — no new sheet columns needed, can implement immediately) or item 1 (Market Timing — highest strategic value but needs a NIFTY data feed decision first).

### ✅ Done

**MAE / MFE Analysis** — completed 2026-06-16.
- Sheet: cols `AL` (MAE%) / `AM` (MFE%) added — chosen because `O`/`P`/`M`/`N`/`T`/`U`/`V`/`G` were all already in use for other calcs, and `AI`/`AK` border the existing summary block. `AL`/`AM` were the first genuinely free columns past the summary section.
- Formula (per row, drag down): `=IFERROR((R2-MIN(INDEX(GOOGLEFINANCE("NSE:"&E2,"low",C2,IF(D2="",TODAY(),D2)),0,2)))/R2*100,"")` for MAE, mirrored with `MAX`/`"high"` for MFE.
  - **Critical gotcha**: `GOOGLEFINANCE(...,"low"/"high",start,end)` returns a 2-column `{Date, Price}` array. Wrapping the whole thing in `MIN()`/`MAX()` without `INDEX(...,0,2)` lets the numeric date serials (e.g. ~46200 for 2026) leak into the comparison — `MAX()` picks the date instead of the price, producing absurd values like `57127`. `MIN()` looked fine by coincidence (date serials are always bigger than any stock low), `MAX()` broke visibly. Always use `INDEX(...,0,2)` to extract just the price column.
  - Cell format: plain **Number**, not Percentage — the formula already multiplies by 100, so the value is e.g. `5.49` meaning 5.49%.
- Config: `maeCol: 'AL'`, `mfeCol: 'AM'` added to `DEFAULT_CONFIG`, `fetchData()` params, and Config page column-mapping UI (optional fields).
- Apps Script (hosted on Google, not in this repo): patched to add `mae`/`mfe` to the column index map (`c.mae`/`c.mfe`) and the per-trade response object, using `toNum()` not `toPct()` (sheet already stores the percentage directly, not a fraction).
- Analysis tab: new "How Your Trades Behave Before They Resolve" section (between Pattern Analysis and Unlock Advanced Analytics). Simplified 2026-06-16 from two bucketed histograms + jargon insight cards down to 3 plain-language cards ("Pain Before It Works", "Profit You Give Back", "Early Tell — Does This One Look Like a Winner?") plus a single "Best Point Reached vs Where You Ended Up" bar chart (winners vs losers, MFE peak vs final P&L). Verified live: ≥3x MFE:MAE ratio trades win 94% vs 7% below, n=16/58 — phrased as a plain win-rate comparison, not raw ratio jargon. Explicitly states this is informational and never overrides the stop-loss.
- Positions tab: each open trade's expand row shows a live "Early Read (MAE/MFE)" tag — "Tracking like a winner" (green, ratio ≥3x) vs "Tracking like a struggler" (amber) vs "Too early to tell" (age < 3 days). Always paired with the disclaimer "does not override your 7-day-low / 21-EMA stop" — added 2026-06-16 per explicit safety requirement (this signal must never be used to skip or delay an actual stop-loss exit).
- "Unlock Advanced Analytics" collapsible: MAE/MFE cards removed (now live above), renamed to "Unlock **More** Advanced Analytics" — Entry Time / Trade Quality Tag / Sector remain as pending columns there.

### 🔴 High Priority (needs external data or new sheet columns)

1. **Market Timing / Tape Health signal**
   - NIFTY trend status on Dashboard: "Confirmed Uptrend / Under Pressure / Correction"
   - Distribution day count (NIFTY close lower on higher volume = 1 distribution day)
   - % of NIFTY500 stocks above 200-day MA (breadth gauge)
   - *Needs: NIFTY OHLCV data feed or manual input cell in sheet*

3. **Relative Performance vs NIFTY**
   - Monthly return overlay vs NIFTY on equity curve
   - Alpha = your return − NIFTY return for the same period
   - *Needs: NIFTY monthly return data (can be a static lookup table or sheet column)*

4. **Trade Grade (A/B/C Setup Quality)**
   - Grade entered at time of trade (A = perfect VCP/pivot, B = good, C = marginal)
   - Analysis tab breakdown: win rate, avg P&L, R-multiple by grade
   - Minervini data: A-grade ~70% WR, C-grade ~35% WR
   - *Needs: new column in TRADES sheet — setup grade*

### 🟡 Medium Priority (mostly computation, minimal new data)

5. **Pivot Entry Precision**
   - % extended at entry = (entryPrice − pivotPrice) / pivotPrice
   - O'Neil rule: never buy more than 5% above pivot
   - *Needs: pivot price column in TRADES sheet*

6. **Base Stage Count**
   - 1st-stage base success ~65%, 3rd-stage ~25%
   - Track which stage breakout this was
   - *Needs: base count column in TRADES sheet*

7. **Position Concentration Risk card (Dashboard)**
   - Top-3 positions as % of total portfolio notional
   - Sector concentration (if sector column added)
   - *Can be computed from existing open positions data*

8. **Pyramid / Add-on Entry Tracking**
   - Minervini adds to winners at first pullback/flag
   - Track initial entries vs add-on entries separately
   - *Needs: entry type column (Initial / Add-on) in TRADES sheet*

### 🟢 Lower Priority

9. **Win Rate in first 10 days vs after** — most breakout failures resolve quickly; compute from age column
10. **Peak MTM "gave back" metric** — requires MFE column (see item 2)
11. **Sector rotation view** — requires sector column in sheet
12. **Psychology / discipline log** — free-text note per trade; *needs notes column in sheet*
