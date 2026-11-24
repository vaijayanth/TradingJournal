# Pradeep Bonde (Stockbee) Episodic Pivot (EP) and related setups

**Access caveat (read first):** WebFetch could not reach stockbee.blogspot.com, traderlion.com, substack.com or medium.com in this session (DNS failure, hosts not in the session's allowed network domains). All findings below come from WebSearch result summaries, not full page reads. Quotes and numbers are therefore second-hand to the page text and must be verified against the primary posts before encoding. Re-run once those hosts are allowed.

## 1. What exactly is an Episodic Pivot (catalyst, gap size, volume, filters)?

### Takeaway
Bonde's own 2010 blog post carries an EP scan built on an ~8% price move plus a volume surge vs the 100-day average. Third-party write-ups say 8-10%+ gap, 2-4x+ volume, a catalyst and a strong close. Price/liquidity floors and neglect/prior-base criteria were not verifiable.

### Cited Findings
- Stockbee Feb 2010 post "what are episodic pivots and how to..." contains a scan: close up at least 8% vs prior close, volume at least 3x the 100-day average, plus a minimum volume floor (floor value not captured). Source is the search summary of the primary post; exact formula unverified. — [Stockbee 2010](https://stockbee.blogspot.com/2010/02/what-are-episodic-pivots-and-how-to.html?m=0)
- Third-party: gap "8-10% or more", attributed to Qullamaggie and Bonde; volume a multiple of average (2x, 3x, 4x+); close near high of day; a catalyst. Not Bonde's own statement. — [Tradingsim](https://tradingsim.com/blog/episodic-pivot-power-earnings-gap-buyable-gap-up-explained/), [TheRightTrader](https://therighttrader.com/learn/trading-strategies/episodic-pivot)
- A TradingView script based on Bonde (protected source, third party) describes a 10%+ gap on 2x+ average volume. — [TradingView Momentum Pro](https://il.tradingview.com/script/njlDpagc-Pradeep-Bonde-Stockbee-Momentum-Pro)
- TraderLion material (Bonde interviews/podcasts) frames EP as catalyst-driven and advises understanding general market conditions and the stock's character. Catalyst-type lists (earnings surprise, guidance, news) not captured at text level. — [TraderLion EP page](https://traderlion.com/profile/pradeep-bonde/episodic-pivots/)
- One blog says 10-12 classic EP opportunities a year in bull markets (third-party, unverified). — [Finer Market Points](https://www.finermarketpoints.com/post/episodic-pivot-trading-complete-guide)

### Inferences
- A defensible encoding baseline: close/prior close >= 1.08, volume >= 3x 100-day average, close in upper part of range, liquidity floor of your own choosing. Treat 8% / 3x / 100-day as the best-sourced numbers, not as confirmed final rules.
- For an Indian-market encoding, price/volume floors must be set by the user; none documented here.

### Gaps
- Prior-base / neglect criteria (e.g. no prior run-up), price floor, dollar-volume floor: not found (search for "neglect" returned nothing).
- Official catalyst taxonomy in Bonde's words: not verified.
- Book/course (his paid material) content: not accessible.

## 2. Entry mechanics, stops, sizing, risk

### Takeaway
Sources agree on entering on gap day after an opening-range break and stopping at low of day; opening-range-low is mentioned by some. Delayed Reaction EP waits for a later consolidation breakout. Sizing guidance is generic fixed-fractional, not a documented Bonde rule.

### Cited Findings
- Opening range: wait roughly 5-30 minutes, mark high/low, enter on break of the range high (third-party description). — [Tradezella](https://www.tradezella.com/strategies/episode-pivot-strategy), [TraderLion entry page](https://traderlion.com/?p=405537)
- Stop commonly = low of day (same day); one source mentions below the opening-range low; one intraday variant uses the opening bar's low. Third-party; not clearly Bonde's own. — [TheRightTrader](https://therighttrader.com/learn/trading-strategies/episodic-pivot), [Tradezella](https://www.tradezella.com/strategies/episode-pivot-strategy)
- Delayed Reaction EP (Bonde via TraderLion): because day-one moves are large and noisy, wait for a secondary move: a red-to-green day after consolidation or a breakout from a tight range after the catalyst day, avoiding buying at inflated prices. Stop placement for this variant was not consistently documented. — [TraderLion delayed reaction](https://traderlion.com/profile/pradeep-bonde/episodic-pivots-delayed-reaction/)
- Sizing: a guide describes fixed fraction of equity divided by distance from entry to gap-day low (generic, third-party). — [Finer Market Points](https://www.finermarketpoints.com/post/episodic-pivot-trading-complete-guide)
- A failed gap that closes weak is a failed EP, not a second buy chance (third-party). — same source.

### Inferences
- Encodable rule: buy on break of the N-minute opening-range high (daily-bar systems can approximate with entry above gap-day high next session), stop at gap-day low, risk % / (entry - stop) for qty.

### Gaps
- Bonde's own stated risk % per trade and exposure rules: not found (a Bonde-related doc was found whose snippet only showed a table of contents with position sizing/progressive exposure).
- Whether Bonde himself uses opening-range-low vs day low as primary stop: unresolved.

## 3. Exits, trailing, hold duration

### Takeaway
Bonde's momentum-burst material says exit in 3-5 days; EP-specific exit rules from Bonde were not verified. A 10-day MA trail is NOT found in Bonde sources.

### Cited Findings
- Momentum burst: lasts 3-5 days, gains typically 8-20% (lower-priced stocks up to 40%); after that momentum dies and holding gives gains back (Stockbee blog 2013-2016, via summary). — [Stockbee 2013](https://stockbee.blogspot.com/2013/12/stocks-move-in-short-term-momentum.html), [Stockbee 2015](https://stockbee.blogspot.com/2015/05/how-do-stock-move-on-3-to-5-day-time.html)
- A third-party Bonde-based TradingView script lists exits: first down day after 3+ up days; close below 5-day MA; typical hold 2-5 days for 8-40%. Script author's summary, not Bonde. — [TradingView](https://il.tradingview.com/script/njlDpagc-Pradeep-Bonde-Stockbee-Momentum-Pro)
- Another page (credits later traders, not Bonde, for rules): keep stop until +2R then trail under the latest pullback low; exit on a close below gap-day open. — [TheRightTrader](https://therighttrader.com/learn/trading-strategies/episodic-pivot)

### Inferences
- EPs probably allow longer holds than 3-5 day bursts (neglected stocks can re-rate), but Bonde's own numeric trail rule is undocumented here. Candidate encodings to backtest: 5-day MA close, 10/20-day MA close, close below gap-day open.

### Gaps
- Partial-profit rules, time stops, 10/20-day MA trails from Bonde: not found.
- Typical EP hold duration in Bonde's words: not found.

## 4. Stockbee scanner definitions (Momentum Burst, 4%, anticipation, range expansion)

### Takeaway
4% breakout on volume expansion above prior day is the core burst scan; thresholds vary by transcription.

### Cited Findings
- 2014 post: burst begins with a 4% breakout, volume well above the preceding 8-10 days, narrow-range day just before. — [Stockbee 2014](https://stockbee.blogspot.com/2014/01/swing-trading-using-momentum-bursts.html)
- Later guidelines: breakout-day volume > prior day, close at/near high preferred, stock not extended, first or second breakout early in an uptrend. — [Stockbee 2016](https://stockbee.blogspot.com/2016/07/guidelines-to-find-good-momentum-burst.html)
- Substack transcription: (C/C1 > 1.04 or < 0.96) with minimum volume and price floors (floor values not captured; secondary). — [Retail Traders Repository](https://retailtradersrepository.substack.com/p/pradeep-bonde-momentum-bursts)
- Another scan form: 8%+ or $5+ gain in 5 days (and mirror), not up 3 days in a row, volume > yesterday (summary; conflicting versions possible). — [Stockbee 2013](https://stockbee.blogspot.com/2013/12/stocks-move-in-short-term-momentum.html)
- Anticipation: quiet base, consolidation 3-20 days before expansion day, narrow-range or negative bar before breakout. — Stockbee posts above.
- TradingView/LuxAlgo indicators use 4%+ move with volume 40%+ above average: third party. — [LuxAlgo](https://www.luxalgo.com/library/indicator/aUbyMkHj-stockbee-screener-momentum-burst-episodic-pivot-scanner/)

### Gaps
- Exact official minimum volume/price values in scans; range-expansion scan code; a verified 4% scan with numbers.

## 5. Win rate, expectancy, mistakes, market filters

### Takeaway
No reliable Bonde-published win rate or expectancy was found.

### Cited Findings
- One blog cites 60-70% win rates when conditions favour breakouts, attributed to secondary analysis, not Bonde; another guide says no reliable published win rate exists. Conflicting; treat as unverified. — [Finer Market Points](https://www.finermarketpoints.com/post/episodic-pivot-trading-complete-guide); [TheRightTrader](https://therighttrader.com/learn/trading-strategies/episodic-pivot)
- Market-condition awareness stressed (TraderLion); Bonde's "situational awareness" breadth work is referenced but specific thresholds not captured. — [TraderLion](https://traderlion.com/profile/pradeep-bonde/episodic-pivots/)

### Gaps
- Bonde's own stats, common-mistake list, breadth/market filter numbers: not retrieved.

## 6. EP vs Momentum Burst vs breakout/VCP

### Takeaway
Supported distinction only at a conceptual level.

### Cited Findings
- EP = catalyst-driven gap, large price and volume surge, often on neglected stock; Momentum Burst = 4%+ range-expansion day from a quiet base, 3-5 day hold; Delayed EP = later entry after digestion. (Synthesis of sources above.)

### Inferences
- EP needs an event/gap and wide-ranging first day; burst/VCP-style setups need a pre-breakout contraction. Anticipation setups buy the contraction before expansion.

### Gaps
- No direct Bonde comparison to VCP/Minervini found.
