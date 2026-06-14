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

## Trading Style (IMPORTANT)
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
- Setup Type breakdown table (col S) — win rate, avg P&L%, R-multiple, total P&L per setup
- Win Rate by Setup bar chart
- EMA analysis REMOVED (col F is live formula, not entry-time)
- Scatter: hold days vs P&L%
- Entry velocity by week
- Monthly P&L bar chart

## Recent Fixes Applied
- Drawdown Y-axis: `toFixed(2)` to prevent floating-point scientific notation
- Date parsing: `parseDate()` everywhere (Apps Script returns `dd-MMM-yyyy`)
- Period filter (30/90 days): actually filters closed trades and re-renders
- Config URL: auto-saves on blur (no need to click Save)
- `portfolioValue` from sheet cell AI26 is the source of truth for portfolio headline
