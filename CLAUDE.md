# TradingJournal — Project Context for Claude

## What this is
Single-file HTML trading journal (`index.html`) hosted on GitHub Pages at `https://vaijayanth.github.io/TradingJournal`.
Connected to a Google Sheet via Apps Script as a JSON middleware.

## Repo & Branch
- Repo: `vaijayanth/TradingJournal`
- Active branch: `claude/beautiful-hamilton-fwa55n`
- Always push to this branch. GitHub Pages serves from it directly.

## Apps Script URL
`https://script.google.com/macros/s/AKfycbwh85dD1AlNlMFRk4M4A8yCA5YAs5gvnCIMgq6ixQUhdxmes-CqU3OYOdxtzDRLRgLq/exec`

## Google Sheet
- Sheet name: `TRADES`
- Portfolio value cell: `AK26` (live combined value including open positions at market price)
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
| Setup Type | S (static label at entry — use this for analysis) |
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

## Critical Data Facts
- **Column Y (notionalPl)**: mark-to-market, only populated for OPEN positions. Zero/blank for closed trades.
- **Column X (plPct)**: also blank for closed trades in this sheet.
- **Column F (ema21)**: live formula showing current EMA position — NOT entry-time value. Do NOT use for analysis.
- **Setup Type (col S)**: static label entered at trade open — correct for analysis.
- **portfolioValue (AI26)**: already reflects full portfolio including open positions at market price. `portfolioValue - initialCapital` = true combined P&L.
- **Date format from Apps Script**: `dd-MMM-yyyy` (e.g., `21-Apr-2026`) — NOT parseable by `new Date()`. Use `parseDate()` helper everywhere.

## Trading Strategy (IMPORTANT — Minervini momentum style)
- **Entry**: 52-week high breakouts, VCP (Volatility Contraction Pattern) style
- **Stop Loss — 3 triggers (all active simultaneously):**
  1. 7-day low (col I) — always the base trail
  2. Manual stop col J — user sets this; moves to entry price (breakeven) once trade reaches +5% profit
  3. 21 EMA breach (col F = "Below") — exit signal for profitable trades
  - **Effective stop = MAX(J, I)** — whichever is tighter. Once J is moved to entry price at +5%, MAX naturally enforces the breakeven floor
- **Profit taking**: 50% partial exit at +10%, remainder trailed via 7-day low
- **Risk sizing progression**:
  - Start: ₹1,000 risk per trade
  - Increase: +₹500 every 100 closed trades
  - Cap: 0.8% of portfolio (at ₹50L initial = ₹40,000 max)
  - Formula in code: `Math.min(1000 + Math.floor(closed.length / 100) * 500, initialCapital * 0.008)`
- **Initial capital**: ₹50,00,000 (₹50L)
- **Cut losses fast, run profits**: stops are taken quickly → closed trades are mostly small losses
- **Winners held open for a long time** → unrealized MTM (col Y) is where real gains sit
- **True performance picture = realized + unrealized combined**
- Notional P&L = open trade unrealized P&L (col Y sum), NOT a "what-if held longer" calculation on closed trades

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

## Effective Stop Logic
```javascript
const effStop = Math.max(t.stopLoss || 0, t.sevenDayLow || 0);
const effPct = (t.cmp && effStop) ? ((t.cmp - effStop) / t.cmp * 100) : t.pctFromStop;
```
- Used everywhere for alerts, sort order, and table display
- Positions table header: "Eff Stop ₹" (not "Stop ₹")
- Expand row shows: Manual Stop (J), 7-Day Low (I), Effective Stop separately

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
- Analysis tab: added Current Streak, Learning Curve, Setup Type WR (Last 30), Monthly P&L chart (see Analysis Tab section above) — completed 2026-06-16

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
| 5 | F | DATE | date |
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
| 23 | X | SPREAD ACTIVE | spreadActive (bool) |

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
function fnoAction(s) {
  const trend = fnoTrend(s);
  const haRed = s.haColour.toLowerCase() === 'red';
  const haRedToday = haRed && s.haChanged;
  if (s.spreadActive && haRedToday) return 'add-call';
  if (trend === 'bullish' && !haRed) return 'put-spread';
  if (trend === 'bearish' || (haRedToday && !s.spreadActive)) return 'call-spread';
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
