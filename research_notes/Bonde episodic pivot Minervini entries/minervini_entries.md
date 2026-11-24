# Mark Minervini entry methodology (SEPA, Trend Template, VCP, pivots)

Research limits: only WebSearch snippets were available. WebFetch failed (host resolution blocked for chartmill.com, substack), so no page was read in full and no Minervini primary text (books, minervini.com) was reached. Every figure below comes from secondary sources unless stated. Claims from my own background knowledge are NOT cited and are listed under Gaps/Inferences only.

## 1. Trend Template: the 8 criteria and thresholds

### Takeaway
Secondary sources agree on the MA stack, a rising 200MA (at least 1 month, 22 trading days in one script), a 52-week-high proximity of 25% and an RS floor of 70. The 52-week-low threshold is disputed (25% vs 30%).

### Cited Findings
- Price above 150MA and 200MA; 150MA above 200MA; 50MA above both 150MA and 200MA; price above 50MA — [TradingView search results / ChartMill](https://www.chartmill.com/documentation/stock-screener/technical-analysis-trading-strategies/496-Mark-Minervini-Trend-Template-A-Step-by-Step-Guide-for-Beginners)
- 200MA trending up for at least 1 month; one open-source implementation defaults to 22 trading days (`ma_200_month_ago = ma_200.iloc[-min_200ma_uptrend_days]`) — [TradingView Minervini Trend Template script](https://www.tradingview.com/script/zygjiw4C-Minervini-Trend-Template)
- Price at least 30% above 52-week low (ChartMill, "preferably 100% or more"); other sites and code use 25% (`low_52w * 1.25`). One source claims Minervini specifies 25% in "Think and Trade Like a Champion" and 30% in the earlier book — unverified against the books — [ChartMill](https://www.chartmill.com/documentation/stock-screener/technical-analysis-trading-strategies/496-Mark-Minervini-Trend-Template-A-Step-by-Step-Guide-for-Beginners); [TradingView script](https://www.tradingview.com/script/zygjiw4C-Minervini-Trend-Template)
- Price within 25% of 52-week high; closer is better — [ChartMill TTP](https://www.chartmill.com/trading-ideas/645-Mark-Minervinis-Trend-Template-TTP)
- RS rank at least 70, ideally 80-90+ — [ChartMill](https://www.chartmill.com/documentation/stock-screener/technical-analysis-trading-strategies/496-Mark-Minervini-Trend-Template-A-Step-by-Step-Guide-for-Beginners)
- Sources say all criteria must pass; the template is a screen, not a buy signal — [TradingView SEPA System](https://in.tradingview.com/script/kcihs4Hp-Minervini-SEPA-System)
- Some tools drop the RS criterion entirely (RS rank not buildable in some screeners) — [Trendlyne](https://trendlyne.com/fundamentals/stock-screener-history/401689)

### Inferences
- For encoding (e.g. an NSE universe), compute RS rank as a percentile of 12-month return across the universe; the exact RS formula is not documented in these sources.
- The repo's existing universe (above 200 EMA and 50 EMA) is a loose subset of this template; the template is stricter (SMA, ordering, rising 200MA, 52-week bounds).

### Gaps
- Minervini's own wording of the 8 criteria (book text) not reached; 25% vs 30% unresolved. Whether the 200MA slope threshold is "1 month" or "4-5 months" in his text is not confirmed here.

## 2. Volatility Contraction Pattern (VCP)

### Takeaway
VCP = a Stage 2 base with 2-4 (sometimes 5-6) successively shallower pullbacks and drying volume; pivot = high of the last tight contraction; buy on breakout through it. Exact depth sequences are conventions, not documented Minervini rules.

### Cited Findings
- Successive pullbacks shrink, volume dries up, ends in a tight pivot; typically 2-4 contractions, each often about half the prior depth — [ChartMill VCP article](https://www.chartmill.com/documentation/technical-analysis/chart-patterns/531-Volatility-Contraction-Pattern-VCP-How-to-Spot-and-Trade-It); [Trade Ideas](https://www.trade-ideas.com/learning-center/chart-patterns/volatility-contraction-pattern-vcp-explained/)
- Pivot is the high of the final contraction, not necessarily the base high — [ChartMill VCP guide](https://www.chartmill.com/images/uploads/The-Complete-ChartMill-VCP-Guide.pdf)
- Breakout volume at least 40-50% above the 50-day average (ChartMill); a community skill file uses 50%+ — [ChartMill](https://www.chartmill.com/documentation/technical-analysis/chart-patterns/531-Volatility-Contraction-Pattern-VCP-How-to-Spot-and-Trade-It); [skills.sh](https://skills.sh/copyleftdev/sk1llz/minervini-swing-trading)
- Buy zone from pivot to 5% above; do not chase more than 10% above the pivot (community skill file) — [skills.sh](https://skills.sh/copyleftdev/sk1llz/minervini-swing-trading)
- Contraction depth ranges given by that skill file: 1st 20-35%, 2nd 10-20%, 3rd 5-15%, 4th 3-8% (community summary, not Minervini) — [skills.sh](https://skills.sh/copyleftdev/sk1llz/minervini-swing-trading)
- Volume dry-up coded as volume below its 50-day average through the final contraction — [LuxAlgo](https://www.luxalgo.com/library/concept/volatility-contraction-pattern/)
- Stop under the last contraction low (one source's placement) — [ChartMill VCP guide](https://www.chartmill.com/images/uploads/The-Complete-ChartMill-VCP-Guide.pdf)
- Dissent: one trader argues against buying inside the pattern, waiting for the move out — [TradingView ideas](https://www.tradingview.com/ideas/minervini)

### Inferences
- The popular "25%, 12%, 6%" sequence is illustrative: no searched source documents it. Encode as rule "each contraction depth < prior" with a tolerance, plus last contraction under a tightness cap.

### Gaps
- Base length (weeks) and a numeric tightness definition were not found in any source read. Minervini's own breakout-volume rule was not found (sources say he stresses dry-up, not a fixed multiple).

## 3. Other entries: cheats, power play, catalysts, Code 33

### Takeaway
Only thin secondary descriptions found; no numeric rules for cheats or handle entries.

### Cited Findings
- Low cheat: an early entry inside a base, often a cup where the handle forms in the lower/middle third; taken where volume dries up in the last contraction; one source suggests a stop at the low of the entry candle — [Setup Factory](https://thesetupfactory.substack.com/p/mastering-the-minervini-low-cheat); [ChartMill VCP guide](https://www.chartmill.com/images/uploads/The-Complete-ChartMill-VCP-Guide.pdf)
- Power Play: a high-tight bull flag that should still show contracting range and falling volume — [TradingView Finpipe](https://br.tradingview.com/chart/FINPIPE/uU2Q8n2r-Finpipe-Power-play-structure-by-Mark-Minervini)
- Code 33: EPS growth, sales growth and net margin each rising for 3 straight reported quarters; fundamentals alone are not enough, Stage 2 price confirmation is also needed — [TradingView Code 33 Matrix](https://www.tradingview.com/script/z8bo5R1T-Minervini-Code-33-Matrix/)
- Earnings: a source says Minervini emphasizes having a profit cushion before earnings reports — [TraderLion](https://traderlion.com/?p=420003)

### Gaps
- Low-volatility cheat, undercut-and-rally, handle entry specifics and the SEPA fundamental thresholds (e.g. EPS growth %, sales growth %, ROE) were not found with numbers. Not stated here from memory.

## 4. Risk rules

### Takeaway
Max stop about 7-8% (often tighter) and 1.25-2.5% equity risk per trade appear across secondary sources; 3:1 and "never let a good profit turn into a loss" wording were not confirmed.

### Cited Findings
- Max loss per trade typically 7-8%, often tighter — [ChartMill sell rules](https://www.chartmill.com/documentation/trading-and-investing/methodologies/524-Sell-Rules-for-Growth-Stocks-When-to-Get-Out); [Finer Market Points](https://www.finermarketpoints.com/post/what-is-mark-minervini-s-trading-strategy-the-complete-sepa-vcp-guide)
- Risk 1.25-2.5% of equity per trade, stops capped at about 10% in one source; 7-8% in another — [TraderLion](https://traderlion.com/investing-champions/mark-minervinis-risk-management/); [Tintin Trading](https://tintintrading.substack.com/p/maximizing-profits-with-progressive?open=false)
- Pyramid into winners only, with decreasing add sizes — [Tintin Trading](https://tintintrading.substack.com/p/maximizing-profits-with-progressive?open=false)
- Raise the stop as the trade works; round-trip prevention via breakeven stop (a "2R breakeven rule" write-up) — [TradingView exit criteria](https://my.tradingview.com/chart/COIN/dRQXnzm3-Minervini-s-Specific-Exit-Criteria)
- Sells into strength at multiples of risk — [TraderLion](https://traderlion.com/investing-champions/mark-minervinis-risk-management/)
- Contrast: O'Neil's fixed 7-8% rule vs Minervini pricing the stop from account risk — [ChartMill sell rules](https://www.chartmill.com/documentation/trading-and-investing/methodologies/524-Sell-Rules-for-Growth-Stocks-When-to-Get-Out)

### Inferences
- Position size = (equity x risk%) / (entry - stop). This is standard arithmetic, not a cited Minervini formula.

### Gaps
- Average-loss target, 3:1 reward:risk and the exact phrase "never let a good profit turn into a loss" not found. Partial-profit scale-out percentages not found.

## 5. Stated performance and failure modes

### Takeaway
Only the headline 2021 return was verified; win rate and average win/loss are unverified.

### Cited Findings
- 2021 US Investing Championship: +334.8% in the $1M+ stock division, 338 entrants, prior record +119.1% (Tkaczuk, 2020) — [BusinessWire](https://www.businesswire.com/news/home/20220124005241/en/2021-United-States-Investing-Championship-Winners-%E2%80%94-Minervini-Smashes-Record)
- Trade-level data for 2021 appear not public — [studylib analysis](https://studylib.net/doc/27449227/how-mark-minervini-won-u.s.-investing-championship-2021-b...)

### Gaps
- Win rate "around 50%" and 2:1 gain/loss, 220% average annual return: not confirmed (the latter is only on secondary sites). Failure modes (chasing extended pivots, buying inside the base, ignoring market) are only hinted at; the "do not chase more than 10% above pivot" warning is from a community file.

## 6. Market-environment filters

### Takeaway
Nothing reliable found.

### Cited Findings
- No cited source in the searches tied Minervini's sizing or entries to a market-regime rule; the TradingView Minervini scripts are stock-level only — [TraderLion](https://traderlion.com/?p=421438)

### Gaps
- His index/leader-breakout health checks and exposure scaling are not documented in what was retrieved. Needs his books, or fetches after allowing chartmill.com / traderlion.com in the session network settings.

## Relevance note to the caller
Minervini's system (fixed 7-8% stop, VCP pivots) differs from the repo's SST design (no hard stop, 21-Day-High GTT entry); any encoding should be tested as a separate strategy, not merged into SST rules.
