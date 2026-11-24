# Evidence and critique: Bonde Episodic Pivot / Momentum Burst and Minervini SEPA/VCP vs a 52-week-closing-high + Supertrend-green system

Research limits: web search returned summaries only. Several pages (tradingqna.com, marketinout.com, stonkscapital.substack.com) could not be fetched because they are outside the session's allowed network domains, so those figures come only from search-result summaries and are flagged as unverified. No exact numbers are given where I could not find them.

## 1. Academic and practitioner evidence: PEAD / earnings-gap continuation, 52-week-high momentum, breakout / pattern evidence, and published backtests of Minervini and Stockbee

### Takeaway
52-week-high momentum has real academic support, including international and Indian evidence on momentum. PEAD is real in the classic literature but is contested and probably much weaker in large stocks since the mid-2000s. I found no independent, out-of-sample backtest of Bonde's EP or Momentum Burst rules, and none of Minervini's SEPA/VCP; only vendor or blog tests of the Trend Template filter, with unverified methodology.

### Cited Findings
**52-week-high momentum**
- George and Hwang (2004), Journal of Finance 59(5), 2145-2176: nearness to the 52-week high predicts returns better than past returns and explains much of momentum profits; the 52-week-high strategy earns roughly 0.45% per month, similar to Jegadeesh-Titman momentum. Anchoring explanation; no long-run reversal reported. — [Search summary of George & Hwang](https://academicnewsletter.sufe.edu.cn/info/361244); paper at [bauer.uh.edu](https://www.bauer.uh.edu/tgeorge/papers/gh5-paper.pdf)
- International replication: one study of 20 international markets reports the strategy profitable in 18 of 20 and significant in 10; Gupta, Locke and Scrimgeour (2010) report significant profits in 10 of 16 markets. India was not clearly confirmed among them in the snippets. — [NAU record](https://experts.nau.edu/en/publications/the-52-week-high-and-momentum-investing-in-international-stock-in/) (sources differ on 16 vs 20 markets; probably different papers)
- A different paper argues momentum and reversals co-exist in international stock indexes, disputing the separation claim. — same search results as above
- Small NSE-specific thesis: 2006-2010, 25 high / 25 low 52-week stocks; 90-day and 180-day momentum worked for the 52-week-high stocks but not the low side. Small sample, one period, treat as suggestive only. — [krishikosh thesis](https://krishikosh.egranth.ac.in/server/api/core/bitstreams/92fa6d6d-cb50-415e-a4ec-d381b33a5283/content)

**Post-earnings-announcement drift (relevant to EP)**
- Bernard and Thomas (1989), Journal of Accounting Research 27, 1-36, test whether drift is delayed price response or risk premium; I could not retrieve their decile magnitudes. — [RePEc](https://econpapers.repec.org/RePEc:bla:joares:v:27:y:1989:i::p:1-36)
- Martineau (2022, Critical Finance Review): drift disappeared for non-microcap stocks from 2001 and is gone by 2006; microcaps later. Prices fully reflect surprises on the announcement day. — [Martineau paper](https://cfr.ivo-welch.info/published/papers/martineau2021rest.pdf)
- Counter-evidence: a 2025 UCLA Anderson summary says two accepted papers find PEAD alive and well, and a working paper argues the disagreement reflects research-design choices. Zhao (2022) attributes the decline to less persistent earnings news rather than arbitrage. — [UCLA Anderson Review](https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again)
- Recent S&P 500 working paper: rapid price discovery around releases leaves only limited, fragile short-horizon predictability, closer to mild mean reversion than continuation. — [arXiv 2512.00280](https://arxiv.org/pdf/2512.00280v2)
- Aboody et al. (Springer): small average pre-announcement abnormal returns (0.17% and 0.34%), about -0.01% post-announcement, with continuation of post-announcement returns over a longer period. — [Springer](https://link.springer.com/content/pdf/10.1007/s11142-009-9104-9.pdf)
- I found no academic study isolating "large earnings gap-up with huge volume" continuation, which is the actual EP trigger. The search tool itself said none surfaced.

**Pattern / breakout evidence**
- Lo, Mamaysky and Wang (2000, Journal of Finance 55(4)): algorithmic recognition of patterns (e.g., head-and-shoulders, double bottoms) on US stocks 1962-1996 finds several patterns give incremental information, possibly some practical value; a CFA digest notes patterns that are statistically informative need not be trading-profitable. — [NBER w7613](https://www.nber.org/papers/w7613), [CFA digest](https://rpc.cfainstitute.org/-/media/documents/article/cfa-digest/2001/dig-v31-n1-811-pdf.pdf)
- I found no academic test of the VCP (volatility contraction) pattern specifically.

**Minervini Trend Template / VCP tests found**
- MarketInOut (screener vendor) ran the 8-rule Trend Template as an entry filter over up to 26 years on 14 universes in 7 countries vs local index funds; where it worked, drawdowns were much smaller than the index (e.g., 35% vs 82% for QQQ); the vendor warns some edges may be chance and that Nasdaq-100 depends heavily on 2000-2002. Trade counts, costs and exact rules not verified. — [MarketInOut multi-market](https://www.marketinout.com/blog/minervini-trend-template-backtest-markets) (could not fetch; summary only)
- Same vendor, TSX, 25 years: entry rules worked but exit rule drove results; a quick exit trailed a simple index fund, a patient exit beat it by about 1.3 percentage points a year. Entry filter only, not VCP. — [MarketInOut TSX](https://www.marketinout.com/blog/minervini-trend-template-backtest-tsx) (summary only)
- A TradingQnA forum post claims a 25-year, 2.35M-data-point VCP study and that the template avoided trades in 2008; unverified forum content. — [TradingQnA](https://tradingqna.com/t/a-25-year-empirical-study-on-minervinis-volatility-contraction-pattern-vcp-what-2-35m-data-points-reveal-about-market-crashes/198732) (could not fetch)
- A personal backtest blog reportedly found most chart patterns, VCP included, showed near-zero big winners over 36 years of US data and often negative expectancy, with the caveat that Minervini's claim is about asymmetric payoff via tight stops, so the test may not capture his method; not peer-reviewed. — surfaced via [Minervini search results](https://moeasymmetry.netlify.app/articles/charts-are-risk-maps) (unverified attribution to this page)
- Minervini's own record: won the US Investing Championship with 155% in 1997 and 334.8% in 2021 per one source; a "220% per year for five years" figure is an interviewer's framing, not verified. Competition results are self-selected, not an audited strategy backtest. — [Wall Street Trader Substack](https://wallstreettrader.substack.com/p/how-mark-minervini-won-us-investing), [Stockopedia](https://stockopedia.com/content/the-us-investing-championship-mark-minervini-up-182-825863)

**Stockbee / Bonde tests found**
- No independent, rigorous backtest of EP or Momentum Burst found. Stockbee's statements (bursts of 3-5 days as a structural tendency) are assertions. — [Retail Traders Repository on Bonde](https://retailtradersrepository.substack.com/p/pradeep-bonde-momentum-bursts)
- A Substack test of buying every stock on earnings-announcement day and exiting on a 20 SMA trailing stop reported about 50k instances and "0 edge"; this is a generic earnings-day test, not Bonde's EP (which requires a big gap, volume and a neglected stock). Details not verified. — [Stonks Capital](https://stonkscapital.substack.com/p/modeling-kullamagi-part-3-episodic) (could not fetch)
- TraderLion conference write-up: when Momentum Burst works is a judgment call that is hard to backtest, and EPs have been less frequent in recent years. — [Retail Traders Repository on EP](https://retailtradersrepository.substack.com/p/pradeep-bonde-episodic-pivots)

**Supertrend (the exit leg of the user's system)**
- Weekly S&P 500 test since 1960: 68% win rate over 41 trades, $100k to $5.4M (index-level, thin sample). — [Quantified Strategies](https://quantifiedstrategies.substack.com/p/the-supertrend-indicator-backtested)
- Nifty 500, 2012-2025, daily, parameter grid: low win rate across settings, expected value varies widely with parameters; about 6 of 10 trades lose. — [Share.Market](https://www.share.market/buzz/insights/i-backtested-200000-trades-using-the-supertrend-indicator-here-is-what-actually-works)
- Dow 30 stocks daily swings: 43% win rate, -39% max drawdown (TrendSpider-hosted). — via [Quantified Strategies / search results](https://www.liberatedstocktrader.com/supertrend-indicator/) (attribution uncertain)

### Inferences
- The strongest academic support is for the user's own signal family (proximity to 52-week high plus trend), not for EP or VCP. Note the academic strategy is a monthly-rebalanced cross-sectional portfolio, not a daily breakout entry with a trailing exit.
- EP's thesis (earnings drift) rests on the weakest-evidenced anomaly for liquid stocks (PEAD fading since about 2006), though EP targets neglected, huge-surprise names where Martineau's large-cap result may not apply; this is untested in the sources found.
- All Minervini/Stockbee "evidence" located is anecdotal, vendor-made or non-peer-reviewed; the user's own backtest (41-42% win rate, PF about 1.75-2.0 per CLAUDE.md) is, by comparison, more transparent than any public Minervini/Bonde test found.
- A ~41% win rate with large average wins is consistent with the generic Supertrend finding of low-win-rate trend following, so the system's profile resembles trend following more than the high-win-rate profile its SST sibling claims.

### Gaps
- Primary numbers for Bernard-Thomas drift (decile spreads), George-Hwang table values, and the MarketInOut trade counts were not retrieved.
- No study of earnings gap-up plus volume continuation (the actual EP trigger) was found.
- No open-source GitHub backtest repo for VCP/Trend Template with numbers was found in these searches (search did not target GitHub directly; the GitHub MCP was unavailable).
- Evidence quality for the three unfetchable pages (tradingqna, marketinout, stonkscapital) is unverified.

## 2. Known criticisms: survivorship and selection bias, discretion, gap slippage, capacity

### Takeaway
Criticisms are mostly structural and I found few sources quantifying them. Selection and discretion issues are the main ones for Minervini and Bonde; gap slippage matters most for EP.

### Cited Findings
- Competition winners and stock-market-wizard track records are self-selected and the 220% figure is unverified; no independent test of survivorship bias in Minervini's record exists in what I found. — [Wall Street Trader](https://wallstreettrader.substack.com/p/how-mark-minervini-won-us-investing)
- Vendor backtests of the Trend Template themselves warn some edges may be chance and that results depend on specific episodes (Nasdaq-100 on 2000-2002) and on the exit rule. — [MarketInOut](https://www.marketinout.com/blog/minervini-trend-template-backtest-markets)
- Knowing when Momentum Burst will or will not work is described as a judgment call, hard to backtest; the TradingView/LuxAlgo scripts only mark candidates. — [Retail Traders Repository](https://retailtradersrepository.substack.com/p/pradeep-bonde-momentum-bursts), [LuxAlgo](https://www.luxalgo.com/library/indicator/aUbyMkHj-stockbee-screener-momentum-burst-episodic-pivot-scanner/)
- The 5paisa piece notes history supports investigating stocks near highs, not that buying every fresh high will reliably beat the benchmark; NSE momentum research flags transaction costs as a viability question. — [5paisa](https://www.5paisa.com/blog/what-if-you-bought-every-stock-hitting-a-52-week-high), [NSE research paper](https://nsearchives.nseindia.com/content/research/res_paperfinal223.pdf)

### Inferences
- Gap-up slippage is inherent to EP (entry is the gap day itself, often at the open or intraday breakout) and none of the sources quantify it; a close-based signal bought next day (the user's system) pays the gap on the day after the signal but not the earnings-day gap itself.
- Capacity: EP names are typically small/neglected, so capacity is lower; no source quantified it. At the user's sizes (Rs20k-1L per trade) this is not binding.
- Backtests of discretionary methods typically over-credit them because the screener leaves out the discretionary filtering; this is a general point, not sourced here.

### Gaps
- No quantified slippage, capacity or survivorship numbers for Minervini or Bonde methods were found.

## 3. Side-by-side comparison: EP vs Momentum Burst vs Minervini VCP/pivot vs 52-week-high + Supertrend

### Takeaway
Only the 52-week-high + Supertrend system is fully mechanical. Stockbee's 4% breakout is mechanically codable as a candidate scan; EP and VCP need judgment or non-price data. Expected win rates for the Bonde and Minervini styles are not independently documented.

### Cited Findings
- Momentum Burst "4% breakout" as coded by third parties: volume above previous bar, close above 4% over previous close, close within top 30% of the candle's range; some versions add a minimum 100,000 volume. Stockbee's own original rules were not found. — [TradingView StockBee 4% Breakout](https://in.tradingview.com/script/YNH3Dy2j-StockBee-4-Breakout), [StockBee MB Bullish](https://in.tradingview.com/script/Rf67M40u-StockBee-MB-Bullish)
- Bonde's own description: bursts last 3 to 5 days. — [Retail Traders Repository](https://retailtradersrepository.substack.com/p/pradeep-bonde-momentum-bursts)
- EP scripts detect 10%+ gaps on massive volume. — [TradingView Momentum Pro](https://cn.tradingview.com/script/njlDpagc-Pradeep-Bonde-Stockbee-Momentum-Pro)
- User's own system, 10-year backtest (repo notes): win rate about 41%, avg win/loss about +33%/-9%, PF about 2.0 (ND) and 1.75 (AZ). — `/home/user/TradingJournal/CLAUDE.md` (internal, `swing-backtest/RESULTS.md`)
- Supertrend on Nifty 500 (2012-2025): about 40% win rate regime. — [Share.Market](https://www.share.market/buzz/insights/i-backtested-200000-trades-using-the-supertrend-indicator-here-is-what-actually-works)

| Item | Episodic Pivot (EP) | Momentum Burst (4% breakout) | Minervini SEPA / VCP pivot | 52-wk closing high + Supertrend green (user) |
|---|---|---|---|---|
| Trigger | Big gap (about 10%+ per coded scripts) on very high volume, usually on news/earnings | Close >4% above prior close, volume above prior day, strong close (third-party coding) | Breakout above a pivot after contracting pullbacks, on volume expansion | New 252-session closing high with Supertrend green; buy next day |
| Filter | Catalyst / earnings surprise, neglected base (fundamental/news; not in OHLCV) | Liquidity and range-expansion; Stockbee also uses prior-range context | Trend Template (8 rules: stage 2, above 150/200 MA, near highs, RS) plus fundamentals (EPS growth) | Universe only (ND: all non-ETF NSE; AZ: Nifty F&O) |
| Stop | Discretionary, typically low of gap/entry day (from practitioner descriptions, not sourced here) | Discretionary, tight | Tight, about 7-8% max per Minervini's teaching (not sourced here) | No stop; exit on Supertrend red |
| Hold time | Days to weeks, then trail | 3-5 days (per Bonde) | Weeks to months, trail | Open-ended, trend-following |
| Expected win rate | No independent figure found | No independent figure found | No independent figure found; Minervini describes about 50% or less in his teaching (not verified here) | About 41% (own 10-yr backtest) |
| Frequency | Rare (TraderLion: EPs less frequent recently) | High | Low, regime-dependent | High (thousands of trades in 10 years) |
| Mechanical? | No (needs news/earnings and judgment) | Mostly (scan is codable; Bonde says timing of when it works is judgment) | Partly (Trend Template codable, VCP pattern fuzzy) | Fully |

### Inferences
- The unsourced cells (stops, Minervini win rate) come from general knowledge of these methods and should be verified against Bonde and Minervini primary material before publication.
- The user's system and Minervini's template share the "near 52-week high, above long MAs" element; the difference is the exit (Supertrend vs tight stop) and the absence of fundamental or pattern filters.
- The MarketInOut finding that the exit dominated outcomes suggests the user's exit design matters more than the entry style.

### Gaps
- No independent win-rate or expectancy figures for EP, Momentum Burst or VCP.
- Bonde's original rule text (Stockbee blog) was not retrieved; only third-party codings.

## 4. What is mechanically codable from daily OHLCV and what carries over

### Takeaway
From OHLCV alone you can code the Trend Template, 4%-breakout scan, gap/volume-multiple scans and a rough contraction measure; you cannot code the EP catalyst, earnings quality or EPS acceleration. Liquidity/price/volume-multiple filters carry over directly.

### Cited Findings
- Third-party scripts implement the 4% breakout and the EP gap scan purely from price and volume (gap size, volume vs prior bar, close location). — [TradingView StockBee 4% Breakout](https://in.tradingview.com/script/YNH3Dy2j-StockBee-4-Breakout), [LuxAlgo EP scanner](https://www.luxalgo.com/library/indicator/aUbyMkHj-stockbee-screener-momentum-burst-episodic-pivot-scanner/)
- Lo-Mamaysky-Wang show pattern detection can be automated with kernel regression on price data, but only for the patterns they test, not VCP. — [NBER w7613](https://www.nber.org/papers/w7613)
- Indicator authors say scans only identify candidates and users must apply their own analysis. — [LuxAlgo](https://www.luxalgo.com/library/indicator/aUbyMkHj-stockbee-screener-momentum-burst-episodic-pivot-scanner/)
- The Martineau PEAD result depends on earnings-surprise data (SUE or announcement returns), which is not in plain OHLCV. — [Martineau](https://cfr.ivo-welch.info/published/papers/martineau2021rest.pdf)

### Inferences
- Codable from OHLCV: Trend Template (price vs 50/150/200 SMA, 200 SMA slope, within 25% of 52-week high and 30%+ above the low, RS rank vs universe); 4% breakout; gap % vs prior close; volume multiple vs 50-day average; ATR/range contraction as a VCP proxy; 52-week closing high; Supertrend.
- Gap-day "earnings proxy": a gap of 8-10%+ on 3-5x volume is a usable proxy for a catalyst day, but cannot separate earnings from news or from a one-off spike; the earnings calendar (results dates already fetched via Yahoo in the repo's option-events script) could supply a flag.
- Needs non-OHLCV: EPS/revenue growth and acceleration, surprise size, neglect, guidance, news content, float/ownership.
- Filters that carry over unchanged: minimum price and traded value, volume multiple on signal day, above 200/50 SMA, exclusion of ETFs, circuit-prone illiquid names.
- Exact thresholds (e.g. 3x volume) are my suggestions, not sourced.

### Gaps
- No source gave tested thresholds for volume multiple or gap size.

## 5. Evidence in Indian (NSE/BSE) and other emerging markets: circuit limits, T+1, liquidity

### Takeaway
Indian studies support medium-horizon (3-12 month) momentum and some PEAD, but all located studies are older (data through about 2015) and mostly monthly-portfolio tests; nothing found tests EP, Momentum Burst or VCP in India. Price bands create real gap and execution distortions for breakout trading.

### Cited Findings
- Ansari and Khan (2012): strong momentum profits in India 1995-2006, strongest for 3- and 6-month winners; not explained by CAPM or Fama-French. — [Emerald](https://emerald.com/insight/content/doi/10.1108/03074351211193730/full/html)
- Joshipura (NSE paper): monthly data 1995-2008, momentum at 6-month and 1-year horizons, with contrarian profits in the long run. — [NSE paper](https://nsearchives.nseindia.com/research/content/RP_2_Feb2012.pdf)
- Garg and Varshney (2015): sector momentum, 2000-2013. — [EconPapers](https://econpapers.repec.org/RePEc:sae:globus:v:16:y:2015:i:3:p:494-510)
- NSE research paper on CNX 100 constituents 2003-2011 consistent with Jegadeesh-Titman; notes transaction costs must be checked. — [NSE paper](https://nsearchives.nseindia.com/content/research/res_paperfinal223.pdf)
- Mohapatra and Misra (2005-2015): medium-horizon abnormal returns, no momentum reversal found (snippet truncated). — same search results
- PEAD in India: NSE studies show some drift, partly anticipated before announcements and concentrated in specific investor groups (insiders, FIIs); Gupta and Dhusia (2021) use 100 NSE firms 2014-2018; Sehgal and Bijoy (2015) 469 companies 2002-2011. Magnitudes not retrieved. — [NSE-IGIDR WP](https://nsearchives.nseindia.com/research/content/NSE-IGIDR-WP4-14-15.pdf), [Gupta & Dhusia](https://journals.lib.vutbr.cz/index.php/trends/article/view/541)
- NSE daily price bands: 2%, 5%, 10%, 20%, none for scrips with derivatives (F&O stocks get a dynamic 10% band); bands measured from prior close and the exchange can change them. A secondary report dated 22 May 2026 says about 230 stocks had bands revised (128 to 20%); unverified against an NSE circular. — [NSE price bands](https://www.nseindia.com/static/products-services/equity-market-price-bands), [Kotak Neo](https://www.kotakneo.com/news/market-news/nse-price-band-revision-stock-volatility-update/)

### Inferences
- A stock locked at an upper circuit on the earnings day cannot be bought at the gap; the continuation move often happens across several locked sessions, so EP-style entries in band-limited names are partly unfillable, and a next-day AMO limit may not fill. In F&O stocks (the AZ universe) the dynamic 10% band bounds this.
- Because the user's entry is the next session after a closing-high signal, circuit locks matter mainly for small-cap ND names; the AMO limit at the signal-day high capped at close +2% already prevents chasing.
- T+1 settlement and delivery (CNC) trading changes nothing about signal logic; no source found discussing it.
- The Indian momentum literature ends before the retail-participation surge post-2020, so its current relevance is uncertain.

### Gaps
- No NSE/BSE study of EP, Momentum Burst, Minervini/VCP or a 52-week-high-plus-trend-filter daily system with costs.
- No data on T+1 effects, upper-circuit continuation behaviour or emerging-market PEAD magnitudes beyond India.
- Exact PEAD magnitudes for India not retrieved.
