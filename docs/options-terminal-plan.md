# Options Terminal plan and watchlist (not built)

> ARCHIVE (moved out of CLAUDE.md on 2026-11-25). A planned separate project; the live option rules for ND, AZ and DI are in CLAUDE.md and OPTIONS_STRATEGY_V2.md.
> Not loaded automatically. Read it only when the task touches this area. Where it contradicts the dated notes in CLAUDE.md, CLAUDE.md wins.

## Options Terminal — Separate Project (planned, not started)

### Decision: Build completely separate site
- Separate repo, separate GitHub Pages URL, separate Google Sheet
- Current F&O tab in TradingJournal stays as lightweight watchlist only
- Options terminal is a decision-support tool, NOT another Sensibull/Zerodha

### User's Options Strategy (SST Options — Volatility Selling)

#### Core Identity
- **Pure option seller** — all trades viewed from selling POV. Option writing is a probability game, not a prediction game; the "predict then pray/hope" cycle is for option buyers.
- **Probabilistic mindset** — not prediction, not hope. Probability game.
- **"Profit is inversely proportional to ego"** — nimble adjustments, no fixation. Biggest losses come from unyielding/unbending responses to a specific trade — but constant churning/flipping isn't the fix either; adjustments are driven by revised risk assessment, not emotion.
- **Avoid fixation with a particular stock/trade.**
- **Consistent low-return simple setups > high-return "bets."** Focus on higher probability of winning over winning big. Diversification (sector + strategy) is the mechanism that makes this work.
- **Avoid revenge trades and overtrading.**
- **Continuous learner** — "always a student of the markets... even if you're a profitable trader," but mastery is useless without returns to show for it.
- **Riding profits is the hard part** — especially when a trade turns from a big loss back to green. Needs a fresh assessment each time: keep riding, or book the (possibly small/zero) profit and move on.

#### Default Trade Structure: Bidirectional Strangle (naked both legs — NOT a defined-risk spread)
**Correction (2026-09-27): earlier notes here described the PE side as a Bull Put Spread with a bought hedge leg. The source strategy document does not describe a hedge leg anywhere — both CE and PE legs are sold naked, and downside protection comes from adjustment technique (strike rolling, new strangles, multi-platform hedging — see below), not a pre-built spread. Corrected below; flag if this doesn't match actual practice.**
- **Bias**: sell CE first, then sell PE lots based on subsequent stock movement/premium/breakeven — not always simultaneous.
- **CE side**: naked sell — call premiums are generally richer for a given breakeven range, so CE is the primary/first leg.
- **PE side**: naked sell — added based on movement after the CE leg, or as part of the same setup when conditions are already clear.
- **Bidirectional (both legs on) ~80% of the time.** Pure single-side (naked CE only, or naked PE only) is the other ~20%.
- **CE/PE ratio**: majority of trades run CE-heavy (ratio > 1, e.g. 5CE:4PE, 3CE:2PE) since call premiums support it; occasionally 1:1.
- **PE-first / PE-only trades are rare** — reserved for a stock with a clear, strong support level and a news-driven downside break already priced in. Only done on stocks with trading history (never a new or infrequently-traded name).
- **Breakeven range target**: >10% on each side.
- **Profit target on margin**: ~10-15% per expiry cycle.
- **Other variants used**: naked CE/PE selling on breakout stocks (single leg, not a strangle); straddle trades specifically to capture IV/premium crush (typically earnings-related, see below) — distinct from the default strangle.

#### Entry Rules
- **Primary signal**: IVP > 70% (fat premium — market overpaying for fear). Sensibull Screener used to screen for high-IV candidates; IVP tracked in real time — higher IVP, better premium.
- **RSI modifier**:
  - RSI > 70 → increase CE lots, sell CE further OTM (stock extended)
  - RSI < 30 → widen PE spread protection, move toward equal ratio
  - RSI 40-60 → standard strangle, default CE bias
- **Timing**: mid-month entry for next month expiry, subject to liquidity.
- **Never enter expiry week** (gamma risk not worth residual premium).
- **Strike selection**: OI concentration = support/resistance. Sell CE above max CE OI, sell PE below max PE OI. Ichimoku indicator used alongside OI for a higher-level support/resistance read (harder to apply when the stock is at ATH in a bull market — no overhead resistance to read).
- **Sharp-movement signal**: stocks with elevated IV and sharp/gamma-heavy movement are the ideal premium-capture candidates. Breakout candidates carry more risk, so strikes there are sold farther OTM.
- **Consolidation rule**: for ATH/breakout stocks, wait 4-5 days of sideways before entering (selling calls into a fresh breakout without consolidation is a trap risk, though also higher reward).

#### Preferred Universe
- **Preferred sectors**: Steel, Pharma, NBFC, Hospitals, Auto
- **Less preferred**: IT, Banks (SBI ok), Oil & Gas, PSUs, wild midcaps
- **Preferred stocks**: JSW Steel, Tata Motors, Bajaj Auto, M&M, Bajaj Finserv, Sun Pharma, Cipla, Divislab, Apollo Hospitals, Tata Steel, ICICI PRULI, HDFCAMC, NMDC
- **Liquidity**: mostly Nifty50, rarely beyond
- **"Boring" stocks**: stable stocks with temporarily elevated IV. Avoid flashy/wild movers.

#### Portfolio Rules
- Minimum 4 different setups from 4 different sectors per expiry
- Typical: 5-10 stocks per expiry cycle
- Neutral is default — directional bias needs strong conviction
- Diversify across both sectors AND strategy type (strangle / naked single-leg / straddle) as much as possible — diversification is the primary risk management, not stop-losses or defined-risk spreads.
- Consider liquidity, volatility, and stock movement character before entry, not just sector/IVP.

#### Exit Rules
- **Profit exit**: 60-70% of max premium collected (lower for infrequent/volatile, higher for stable/frequently traded)
- **Expiry week**: strictly exit or don't enter — experienced 25% of annual profit wiped in 2 sessions
- **Loss exit**: see adjustment strategies below

#### Earnings Season — Volatility Crush Trades
- Enter a few days BEFORE quarterly results (volatility-crush trade, not directional).
- Stock movement mostly happens before the announcement; IV crush happens after. Premiums stay lower even when the stock moves sharply post-results.
- Some stocks are far more earnings-sensitive than others (e.g. Infosys vs TCS) — factor that into which stock, not just which sector.
- Benefit beyond premium: a spread-out results calendar across stocks helps margin circulation (capital freed from one expiring/closed trade funds the next).
- Track record: 1-2 individual trades may go wrong each season, but the approach has worked out overall — this is a probabilistic bet across several names, not a guaranteed per-trade win.
- Entry timing: if results before 15th → current expiry; if after 15th → next month expiry.
- RSI > 70 + earnings in 5 days → single CE leg only (pure vega/theta play, not directional)
- RSI < 30 + strong support + earnings → single PE leg, short duration

#### 4 Adjustment Strategies (when breakeven breached or approached)
Decision framework: "Do I believe the stock will reverse, and do I have margin to wait?" Each strategy comes at a cost — there is no single/simple answer, and managing a loss-making trade is explicitly called out as the hardest part of this approach.

**A1 — Strike Roll** (Yes to reversal, constrained margin)
- Close the ITM strike at a loss. Open 2 lots of new OTM strikes to match/recover the ITM strike's premium, and add a counter lot on the other side (CE roll adds a PE lot, or vice versa) to keep the setup bidirectional.
- Cost: near-zero net premium on the roll itself, but margin requirement goes up.
- Works when: stock is consolidating at the new level.

**A2 — New Strangle** (Yes to reversal, margin available)
- Keep the original position as-is, add a fresh strangle/bidirectional trade with wider strikes around the new CMP, aiming for a wider breakeven range.
- Cost: significant additional margin blocked.
- Works when: stock reverses back into the original range. Real example — HDFCAMC broke out past its breakeven high (5090) around its ex-dividend date in late May, M2M loss hit −₹2.75L by 9-Jun as the stock ran to 5217. A new strangle was opened on a separate platform (Angel) on 9-Jun with a higher CE-side breakeven (5432 vs the original 5138), based on an OI-concentration read (heaviest OI at 5000 despite spot at 5200) plus Ichimoku, judging the move as overextended vs its 9-day/26-day averages. The stock retraced; by 13-Jun the original position had recovered from −₹2.75L to a loss of only −₹7.5K, and the new-platform position was up ₹22.4K — net small profit of ~₹14K across both legs of the adjustment.

**A3 — Book Loss and Exit** (No to reversal)
- Close all legs, accept the loss, free the margin. Cut losses and move on.
- No revenge trades, no re-entry in same stock same expiry.
- Works when: strong trend, no reversal signal.

**A4 — Second Platform Hedge** (No to reversal but want to offset)
- Keep original on Platform A (Zerodha), open a new trade biased toward the stock's actual direction on Platform B (Angel/Upstox) — simpler to manage than trying to unwind or flip the original.
- Track as single consolidated P&L across both platforms.
- Margin benefit: two separate margin pools.
- Works when: stock is trending — Platform B profits offset Platform A loss (see HDFCAMC example under A2, which combined A2 + A4).

**A5 — Convert CE to Bear Call Spread** (supplementary idea, not confirmed in live practice — verify before building)
- When CE is threatened: buy a higher CE to cap upside loss, converting the naked CE to a defined-risk spread.
- Frees margin for recovery trades elsewhere.
- Note: unlike A1-A4, this isn't described in the source strategy document — it was added as a hypothetical extra. Confirm with the user before treating it as a real, used strategy in the terminal.

**Adjustment trigger**: CMP approaches/breaches BREAKEVEN RANGE — not individual strike going ITM. Every case is different; sometimes the only real options left are booking the loss or flipping the position (CE↔PE) rather than any of the above cleanly applying.

#### What the Terminal Must Do (4 decisions only)
1. **Morning Scan**: which stocks have high IVP + right sector + not expiry week + no imminent earnings conflict
2. **Trade Setup**: OI levels → breakeven calculator → CE/PE ratio → margin estimate
3. **Position Monitor**: live breakeven range health per strangle, MTM across platforms consolidated, exit alert at 60-70% profit, breach alert
4. **Expiry Close**: total premium collected, realized P&L, return on margin, what went wrong

#### What the Terminal Must NOT do
- Replicate full options chain (broker terminal handles this)
- Show Greeks dashboard (user doesn't trade Greeks)
- Algo execution (manual order placement)
- Backtesting engine

#### Data Sources (planned)
- **IVP**: NSE Bhavcopy nightly via Apps Script → Google Sheet IV history → computed IVP
- **Earnings calendar**: NSE event calendar weekly via Apps Script
- **OI levels**: NSE options chain via Apps Script proxy (on demand)
- **Live chain/Greeks**: Broker API (Dhan or Upstox) — Phase 2
- **NIFTY price**: Broker API — Phase 2

#### Build Phases (when started)
- Phase 1: Google Sheet structure (6 tabs: WATCHLIST, IV_HISTORY, IVP, EARNINGS, POSITIONS, CONFIG)
- Phase 2: Apps Script — IVP builder (NSE Bhavcopy nightly)
- Phase 3: Apps Script — Earnings calendar (NSE event calendar weekly)
- Phase 4: Scanner page (IVP table, sector filter, earnings flag, RSI modifier)
- Phase 5: Position logger (strangles as units, adjustments, multi-platform P&L)
- Phase 6: Expiry summary
- Phase 7: Live broker API layer

#### Status: PLANNING ONLY — no code written yet

---

## Options Terminal — Stock Watchlist (5 Core Sectors)

Portfolio rule: minimum 4 of these 5 sectors active per expiry cycle. Typical: 5-10 stocks.

### Steel
| Tier | Stock |
|---|---|
| Core | JSW Steel |
| Core | Tata Steel |
| Core | NMDC |
| Secondary | Hindalco |
| Secondary | Vedanta |

### Pharma
| Tier | Stock |
|---|---|
| Core | Sun Pharma |
| Core | Cipla |
| Core | Divislab |
| Secondary | Dr Reddy's |
| Situational | Aurobindo (earnings plays only) |

### NBFC
| Tier | Stock |
|---|---|
| Core | Bajaj Finserv |
| Core | Bajaj Finance |
| Secondary | ICICI Prudential Life |
| Secondary | HDFC AMC |
| Secondary | Muthoot Finance |

### Hospitals
| Tier | Stock |
|---|---|
| Core | Apollo Hospitals |
| Secondary | Max Healthcare |

Note: Hospitals is thin — only 2 liquid F&O stocks. Skip this sector and run other 4 when both look unfavourable.

### Auto
| Tier | Stock |
|---|---|
| Core | Tata Motors |
| Core | Bajaj Auto |
| Core | M&M |
| Secondary | Maruti |
| Secondary | Hero MotoCorp |

### Outside Core Sectors — Situational Only
| Stock | Sector | When to trade |
|---|---|---|
| ITC | FMCG | High IVP, non-results months |
| SBI | PSU Bank | User confirmed SBI is acceptable |
| Infosys | IT | Non-results months only |
| HUL | FMCG | Very stable, low beta, high IVP only |

### Stocks to Avoid
| Stock | Reason |
|---|---|
| Adani group | Regulatory/news risk — unpredictable wild swings |
| Zomato / Nykaa | High beta, insufficient earnings history |
| ONGC / IOC | PSU + crude oil policy risk |
| Yes Bank | Too volatile, thin options |
| Any stock < ₹20k crore mcap | Liquidity too thin for safe selling |
| Reliance | Too many moving factors, expensive options |

Total watchlist: 19 stocks across 5 sectors + 4 situational

---

