# Pradeep Bonde (Stockbee) Episodic Pivot and Momentum Burst: primary-source rules

**Access note.** WebFetch could NOT resolve stockbee.blogspot.com or traderlion.com (DNS ENOTFOUND). `curl` through the session proxy DID reach stockbee.blogspot.com (HTTP 200), so every Stockbee quote below is read from the full page HTML, not snippets. traderlion.com returned HTTP 403 to curl; I did not try to bypass it, so TraderLion is NOT READ at all this pass. chartmill, marketinout, substack, tradingqna were not attempted (budget spent on primary Stockbee posts). All quotes are Bonde's own words from his blog unless marked.

## 1. The exact EP scan (Feb 2010 post and later versions)

### Takeaway
The Feb 12, 2010 post gives a verbatim Telechart formula (an OR of a dollar-move branch and an 8% / 3x-avg-volume branch). Bonde's 2014 process flow gives a later, simpler intraday EP scan (4% / 3x 50-day average volume / 300k volume). The earlier note's "8%, 3x 100-day average" is CONFIRMED; the volume floor of 3,000 is now found.

### Cited Findings
- Feb 12, 2010 verbatim scan: "((C - C1) >= 5 AND V > 10000 AND C >= 62.50 AND V > V1) OR ((( 100 * (C - C1) / C1) >= 8 AND V > 3000 AND (100 * V / AVGV100) >= 300) AND C > 1)". Reading: branch A = up at least $5, volume > 10,000, price >= 62.50, volume > prior day; branch B = up at least 8%, volume > 3,000, volume >= 300% of 100-day average volume, price > 1. (Telechart volume units are in hundreds in some setups, unit NOT stated in the post, so the 3,000 / 10,000 floors' real share counts are NOT confirmed.) — [Stockbee, Feb 12 2010](https://stockbee.blogspot.com/2010/02/what-are-episodic-pivots-and-how-to.html)
- Same post, how he describes it: "It should basically looks for a out-sized price move on high volume post earnings." and "So a stock appearing in such a scan has a volume surge and the price surge. We then investigate what caused this price and volume surge or what was 'the surprise'". — same URL
- Later EP scan, July 30, 2014: "During the day Run EP scan c/c1>1.04 and v>3*avgv50.1 and v>=300000 multiple times , see if there is stock with neglect+ game changing earnings". Also: after-hours "up 4% plus on 50k volume"; pre-market "IB scanner to find stock up on 50k plus volume and up at least 2%". — [Stockbee, Jul 30 2014](https://stockbee.blogspot.com/2014/07/my-process-flow-for-episodic-pivots-ep.html)
- Sept 2, 2014: "A stock up in pre market on below 50 k volume is not what you want to focus on. Similarly a large cap up on 50k volume is also not important." — [Stockbee, Sep 2 2014](https://stockbee.blogspot.com/2014/09/everyday-hunt-for-stocks-with-big.html)
- Volume as a signal (Feb 2010): "If volume is very high, you can assume move has legs... most earnings breakouts which go on to make really big (like say 100% plus kind of) moves in next 1 to 2 months post an earnings, will have huge volume surge, typically of 10 times or more compared to average volume. In many cases the volume on earnings day might be the highest volume in the history of the stock or multi year high volume." — Feb 2010 URL above
- Float (Feb 2010): "Float below 25 million is ideal for this. The best moves happen on float below 10 million. Earnings breakouts on companies with 100 million plus float tend to have pullbacks. Earnings breakout on stock with 500 million plus float is something which I not really very enthusiastic about unless they are trading near their historic lows or are in single digits." — Feb 2010 URL above
- Third-party scans (TradingView/LuxAlgo etc.) were NOT re-checked; ignore them in favour of the above.

### Inferences
- Encodable Bonde-literal EP trigger (daily bars): close/prior close >= 1.08 AND volume >= 3x 100-day average (2010), or close/prior close > 1.04 AND volume > 3x 50-day average AND volume >= 300,000 (2014). A "gap" is not in either formula; both are close-to-close.
- For India, the 300,000 / 10,000 / 62.50 floors are US-share numbers and need user-set rupee/volume floors; none exist in Bonde's text.

### Gaps
- Whether Telechart's volume in the 2010 formula is in shares or hundreds: NOT FOUND.
- Any newer (2020s) EP scan formula: NOT FOUND this pass (Sept 1 2025 post only lists MarketSurge scan buckets "IBD Growth 250", "Funds 5000/2500/1000" for delayed-reaction EP, no formulas; [Stockbee, Sep 1 2025](https://stockbee.blogspot.com/2025/09/scans-irun-in-marketsurge-to-find.html)).

## 2. Prior neglect / base criteria, catalyst taxonomy, delayed-reaction, market filters

### Takeaway
Bonde defines "neglect" explicitly (financial, price, volume, news/attention, ownership) and ranks it the single most important criterion. He lists ~20 catalyst types. Delayed-reaction EP rules in his own words were NOT found (the May 15, 2024 post is a YouTube video only).

### Cited Findings
- Nov 2, 2010: "Prior neglect. This is the single most important criteria. Unknown stocks make big moves. Stocks with prior neglect/sideways move/consolidation prior to breakout make big move." Forms: "Financial neglect: A long period of time where stock had no growth." "Price Neglect: A long period of time where stock had no meaningful price rally." "Volume/liquidity neglect: Long period of time where stock had below average daily volume." "News/attention neglect: No analyst coverage. No major news for months /years." "Ownership: low funds ownership". — [Stockbee, Nov 2 2010](https://stockbee.blogspot.com/2010/11/what-makes-stock-go-up-25-plus-in-month.html)
- Same post (monthly-mover study, not EP-specific): all 25%+ monthly moves start with range expansion, "most of the time this range expansion is 4% plus and is accompanied by volume surge"; "65% or more ... will have less than 30 million float"; "70 to 75% ... priced below 20"; "Bulk of the 25% move in a month happens only in 4 or 5 days"; "Large gaps are not good... Stocks with gaps below 10% or no gap are better"; "What does not matter: Earnings, Sales growth, Margin, IBD ratings, P/E, Distance from 52 week high". NOTE: this contradicts the "big gap = good EP" third-party claim and the earnings-matters EP view; it is a study of 25%/month movers, not EP. — same URL
- Sept 3, 2013: "Earnings surprises for longer term holding works best on a stock that has multi month or multi year neglect. Neglect will reflect in no big rally pre earnings. A extended sideways trading period or a down move coming in to earnings." "Often stock might be trading below our liquidity threshold of 100000 per day pre the earnings catalyst." "Best type of neglect is when a stock since its IPO has never had a big rally ... 'virgin' stock". "No analyst coverage and no news flow for months". — [Stockbee, Sep 3 2013](https://stockbee.blogspot.com/2013/09/night-time-is-right-time.html)
- Same post, surprise count: "look for first or second big earnings surprise... Third and fourth earnings surprise most of the time are priced in or are tricky as they often lead to big gap and then reversal." Also "Neglect+surprise+low float = explosive move"; after-hours focus on "stocks that are up 2% plus on 50000 plus volume". — same URL
- Feb 2010 earnings criteria: for stocks with no analyst coverage "I like to look for companies which had earnings acceleration of 100% plus"; analyst-covered stocks: "Earnings breakout on companies with significant analyst coverage do not do as well as the first kinds." Investigation checklist: "Is this a first major earnings acceleration. What caused this acceleration. Is it one time or likely to persist. Does this earnings trend represent a structural change... Is this surprise reflected in current price level." — Feb 2010 URL
- PEAD framing: earnings EP "lead to a rally lasting 2 to 3 months" (Feb 2010); "EP is a very specific pattern post earnings that shows up on stocks with years of neglect... going up 100 to 500% in few weeks or months. On large cap stocks it takes few quarters for them to go up 50% plus." and "Best Episodic Pivos are on low priced stocks with months or years of neglect and that have very low volume leading in to EP." — [Stockbee, Sep 2 2014](https://stockbee.blogspot.com/2014/09/everyday-hunt-for-stocks-with-big.html)
- Catalyst taxonomy, Feb 12 2010 list (verbatim headings): Earnings Growth 100% plus; Earnings 40% plus; Earnings Beats by wide margin; Earnings Other; Sales 100% plus but no earnings; IPO Breakout; Retail; Top Sector; New order or contract /new order rumor; Buyout/buyout rumor/mergers/ tie ups/division sale; New product launch/news; Regulatory Changes; Drug Approval; Drug /marketing Tie Up; Natural disaster/ war/ disease; Shortages; Rate Increase; Media Mention; Analyst upgrade/downgrade; Declares Dividend; Financial Engineering; Junk of the bottom rally. He says "On a daily basis I monitor around 20 types of Episodic Catalyst." — Feb 2010 URL
- Earlier list (Jul 11, 2007): Earnings acceleration; Sales Acceleration; New Contracts or new orders; New Product Launch; Sector Runaway move; Biotech/drug approvals; Biotech tie ups; Earnings guidance raised; Inside buying>1 million; IBD rating mentions; "Barron's / Business Week mention ( low success rate)"; "James Crammer mention ( one day phenomenon)". — [Stockbee, Jul 11 2007](https://stockbee.blogspot.com/2007/07/episodic-pivot-catalysts.html)
- Other catalysts (Sep 2013): CEO change, activist investor stake, biotech drug approval/rejection, new product launch, retail sales trends, IBD front-page mention, Seeking Alpha mentions (with pump-and-dump warning, RSOL "up 700% in 2 days"). He says to prioritise earnings: "focusing bulk of effort on earnings EP is good strategy as they are easier to understand". — Sep 3 2013 and Sep 2 2014 URLs
- Personal selection weights (Reader Questions, 2007; exact date header NOT captured, URL path 2007/03): "The most important factors ... are EPS growth, momentum and neglect/virginity." — [Stockbee, Reader Questions](https://stockbee.blogspot.com/2007/03/reader-questions.html)
- Market-condition filter (momentum bursts, Jan 28 2014): "There are periods in market where these kind of setups are prone to failure. This happens near market turns where in short period lot of breakouts fail. The bullish breakout trade needs to be avoided during fast selling phases in market." — [Stockbee, Jan 28 2014](https://stockbee.blogspot.com/2014/01/swing-trading-using-momentum-bursts.html)
- Market Monitor (breadth model) purpose, Aug 1 2010: "I use it primarily to decide which market phase is favorable for my style of breakout trading and which period should be avoided." Numeric thresholds not in the part read. — [Stockbee, Aug 1 2010](https://stockbee.blogspot.com/2010/08/understanding-market-monitor-part1.html)
- Risk post: "I avoid bad conditions to trade in and sit in cash while others get whipsawed." — [Stockbee, Aug 8 2014](https://stockbee.blogspot.com/2014/08/how-i-control-my-risk.html)

### Inferences
- A defensible "neglect" test for encoding: no big rally in prior months (sideways/down into the event), below-average volume, first or second big earnings surprise. Bonde gives no numeric lookback for "months/years" of neglect.

### Gaps
- Delayed-reaction EP rules in Bonde's words: NOT FOUND. [Stockbee, May 15 2024](https://stockbee.blogspot.com/2024/05/delayed-reaction-episodic-pivots.html) contains only an embedded YouTube video (youtube.com/embed/uW95Cj44cLk) with no text; its content not transcribed. The earlier note's TraderLion delayed-reaction description (red-to-green after consolidation) remains third-party and unverified (TraderLion returned 403).
- Numeric market-condition filter thresholds (Market Monitor numbers): NOT FOUND in part read (only Part 1 intro fetched).

## 3. Entry timing, stop, sizing, exit and trailing for EP

### Takeaway
Bonde's EP entry is "buy immediately", often pre-market, on the day of the catalyst. His stop for day-of entries is the low of the day (in his swing examples). His EP profit target is 40-50% with partial sells in quarters, per a 2011 interview. No EP trailing-MA rule from Bonde was found.

### Cited Findings
- Entry: "If I find a good EP I buy immediately in pre or post market. Most EP where I made big money I bought in pre market." — [Stockbee, Jul 30 2014](https://stockbee.blogspot.com/2014/07/my-process-flow-for-episodic-pivots-ep.html)
- Example sizes/entries: "I bought 50000 shares in pre market between 33 and 33.40 and in few months closed it near 60" (FB). USLB: bought "with entire capital I had at that time plus some margin", added near 9, sold "between 14.50 and 14" (11 weeks). Another: bought around 14 on margin, sold at 38 after 13 days "as it gaps and started reversing". — [Sep 2 2014](https://stockbee.blogspot.com/2014/09/everyday-hunt-for-stocks-with-big.html); [Jul 8 2014](https://stockbee.blogspot.com/2014/07/few-good-earnings-trade-can-change-your.html)
- Stop and risk formula (general, shown with a swing example): "risk=entry price-stop"; RH example "entered ... around 83. The low of the day is 81.50. That will be my stop." Position size "100000/100/(c-l)" for 1% risk "assumes your stop is low of the day". "I risk anywhere from .25 to 4% on a trade and in rare very high conviction trade higher than 4%. But most trades are around .25% to 1% risk." "Overall 60% of trades are positive" and "only 1 trade where I lost .59% of equity" (his 2014 year). "The basic assumption ... is that you will be able to get out at stop price and stock will not gap down significantly below your stop." — [Stockbee, Aug 8 2014](https://stockbee.blogspot.com/2014/08/how-i-control-my-risk.html)
- Older, different risk statement on EP (Reader Questions, 2007): "Episodic Pivots ... I risk 5 to 10% per trade on such ideas." and (for EPS/momentum breakouts) "I mostly risk 1% on these ideas." Unclear whether "risk" means account risk or position size; conflicts with the 2014 ".25 to 4%". — [Stockbee, Reader Questions](https://stockbee.blogspot.com/2007/03/reader-questions.html)
- Sizing conviction: "The objective of finding game changing catalyst stock is to find a stock that will increase your overall account by 15 to 20% in one trade." "3 to 5 big 50% plus movers post Episodic Pivots can make your year if you risk sufficiently on them." IDSA: "25% position" in a thin stock. — [Sep 2 2014](https://stockbee.blogspot.com/2014/09/everyday-hunt-for-stocks-with-big.html)
- Exits, Q&A with Kirk Report, Jun 27 2011: "the best exit is into strength... I operate on profit targets. I am typically looking at 8 to 20% profit target on my swing trades and 40 to 50% target on my Episodic Pivots trade. I sell when stock reaches my profit objective. I sell in parts so most of the time I peel off positions in units of 1/4th." "exit a position into 10% plus move after entry ... exit at least 50 to 75% of my position". "I also exit my trades after 3 days if it does not move in intended direction after." Same interview: "I sold half my position around 74.26 and moved stop on rest to 73.75" (swing example); "I exited the trade before it hit stop as overall market started showing weakness." — [Stockbee, Q&A Jun 27 2011](https://stockbee.blogspot.com/2011/06/q-with-pradeep-bonde.html)
- EP expected move: "EP candidate is likely to make 20% or more move in comparable period" vs 10% for a 4% breakout over 20 days (Jul 11 2007). Holding: PEAD "rally lasting 2 to 3 months" (2010); IDSA +800% in 17 days, BOOM +400% in 10 days (2014). — [Jul 11 2007](https://stockbee.blogspot.com/2007/07/episodic-pivot-catalysts.html); [Sep 2 2014](https://stockbee.blogspot.com/2014/09/everyday-hunt-for-stocks-with-big.html)
- Concentration of profit: "14 big trades like these have contributed to 80% of my profit in last 14 years." "On an average I find one good trade like this in a year. Some years you find 10 to 12 such trades, some years you find only 1 or 2." — Sep 2 2014 URL; [Jul 8 2014](https://stockbee.blogspot.com/2014/07/few-good-earnings-trade-can-change-your.html)
- Exit philosophy: "Exits are inbuilt in to setup idea." Trend-following exits mirror entries; "Trend following methods have 20 to 25% success rates in terms of % of trades." (general, not EP-specific). — [Stockbee, Dec 2 2010](https://stockbee.blogspot.com/2010/12/exits-are-inherent-to-setups-part1.html)

### Inferences
- Bonde-literal EP rule set for a backtest: buy on catalyst day (pre-market or at open), initial stop = day-of low (his stop convention in worked examples), size = risk% / (entry - stop), sell in quarter units into strength toward 40-50%, no trailing-MA rule documented.
- The wide spread in his stated risk (0.25-4% in 2014 vs 5-10% in 2007) means "Bonde's risk %" should not be encoded as a single number.

### Gaps
- Bonde's own stop specifically for EP (as opposed to swing examples): NOT FOUND stated explicitly. Low-of-day is from his generic risk post and swing examples.
- 10-day MA / trailing-MA exit from Bonde: NOT FOUND.
- Opening-range-break entry (5-30 minutes) in Bonde's words: NOT FOUND (his own text says buy immediately, pre-market).

## 4. Momentum Burst: the 4% scan, range expansion, 3-5 day hold

### Takeaway
Bonde's own 4% breakout scan is quoted exactly: c/c1>=1.04 and v>v1 and v>=100000 (May 21, 2015). A "range expansion" is a day bigger than the last 3-5 (or 5-10) days; the hold is 3-5 days for 8-20% (up to 40% on cheap stocks).

### Cited Findings
- Exact scan, May 21 2015: "c/c1>=1.04 and v>v1 and v>=100000 ... Gives you stock up 4% plus that also has volume surge compared to volume a day ago. and has volume above 100000. The scan throws a wide net. Just because stock is in 4% b/o it is not automatic buy." Also a "Dollar breakout" for higher-priced stocks that "move in 5 to 50 dollar move but may not have 4% b/o". — [Stockbee, May 21 2015](https://stockbee.blogspot.com/2015/05/how-do-stock-move-on-3-to-5-day-time.html)
- Selection filters from that post: (1) "stocks should not be up 3 days in a row"; (2) "narrow range day or negative day prior to breakout day"; (3) relative smoothness of the prior move; (4) "young trend ... As far as possible first and second breakouts once a trend gets established are better." "If you use them 95% or more of 4% b/o gets eliminated." — same URL
- Range expansion defined: "Range expansion basically means a day which is up bigger than last 5 to 10 days bars" (Dec 31 2013, Jan 28 2014); "a day that is bigger than previous 3 to 5 days move" (May 2015). "Buy range expansion after a period of 5 to 10 day consolidation and an orderly consolidation... after a negative day... after a narrow range day". — [Dec 31 2013](https://stockbee.blogspot.com/2013/12/stocks-move-in-short-term-momentum.html); [Jan 28 2014](https://stockbee.blogspot.com/2014/01/swing-trading-using-momentum-bursts.html); [Jan 17 2014](https://stockbee.blogspot.com/2014/01/buy-range-expansion-at-beginning-of.html)
- Quality guidelines, Jul 12 2016 (verbatim): "stock should have range expansion on breakout day; volume on breakout day should be higher than previous day; day before breakout should be narrow range day or negative day; pre breakout there should not be many big range moves or breakdowns; stock should have linearity in prior uptrend before the consolidation period; correction or consolidation should be orderly during the entire move; volume during consolidation should be preferably orderly and lower; stock should close near high on breakout day". — [Stockbee, Jul 12 2016](https://stockbee.blogspot.com/2016/07/guidelines-to-find-good-momentum-burst.html)
- A-quality example (Jan 14 2014): "preceded by a 3 plus days of period where there was no momentum burst"; example had "for 17 days the stock did not have a momentum bust ... did not also have 4% breakdown". — [Stockbee, Jan 14 2014](https://stockbee.blogspot.com/2014/01/how-to-identify-a-quality-setup.html)
- Burst anatomy, Jan 28 2014: sequence "Range expansion day / Up day (follow through) / Up day (follow through) / pullback / followed by end of momentum"; "this is an impulse move of 3 to 5 day duration"; "stock would go up 8 to 20% ( lower priced stock can even have bursts of up to 40%)"; "follow through should also be of big 4 to 5% plus magnitude on second or third day"; "If you keep holding after the 3 to 5 days period, you would often see the stock ends up giving up all the burst gains". Per-trade average: "just 5 to 8%" (2014 post) / "5 to 10%" (Dec 2013 post); "200 to 1000 or more trades in a year". "Trading this kind of setup requires extremely good ability to ruthlessly cut losses if a trade does not work immediately." — [Jan 28 2014](https://stockbee.blogspot.com/2014/01/swing-trading-using-momentum-bursts.html); [Dec 31 2013](https://stockbee.blogspot.com/2013/12/stocks-move-in-short-term-momentum.html)
- Entry timing: "Always buy a stock on first day of swing move. Or before swing move." "If you are buying a stock on 3rd or 5th day of swing you are starting with low probability entry." "Third day is when many novice notice the move ... the professionals sell in to that euphoria." — [Stockbee, Sep 4 2014](https://stockbee.blogspot.com/2014/09/right-entry-reduces-your-risk.html); Jan 17 2014 URL
- Catalyst not required: "No specific catalyst is needed for these momentum bursts." (Jan 28 2014)

### Inferences
- Daily-bar encoding of Bonde's momentum burst: close/prev close >= 1.04, volume > prior day volume, volume >= 100,000, not up 3 consecutive days, prior day narrow range or red, close near day high; exit by day 3-5 or into a >=10% spike. Entry is intraday on the breakout, so a close-based backtest enters later than he does (he notes entry "might be up 4 to 10%" already).

### Gaps
- A numeric definition of "narrow range", "close near high", or "range expansion" as code: NOT FOUND (only qualitative).
- Bonde's own momentum-burst stop level: only "low of the day" in his generic risk post; no burst-specific stop quoted.

## 5. Stated win rates and common mistakes

### Takeaway
Bonde states "60% of trades are positive" for his 2014 trading overall (not EP-specific). No EP-specific win rate in his words was found.

### Cited Findings
- "Overall 60% of trades are positive and because the worst loss is only .59% of equity the risk is contained." (about his many trades "this year", 2014, all methods) — [Stockbee, Aug 8 2014](https://stockbee.blogspot.com/2014/08/how-i-control-my-risk.html)
- Mistakes he names: buying late in a swing ("If you buy MDSO today ask yourself what were you doing at right low risk entry points") — [Sep 4 2014](https://stockbee.blogspot.com/2014/09/right-entry-reduces-your-risk.html); buying marginal setups ("Do not get into the habit of buying marginal setups", Jan 14 2014); holding past 3-5 days; buying extended trends ("buying a extended move ... will likely hasten your death as a trader", Jan 17 2014); chasing pump-and-dump Seeking Alpha articles (Sep 2013); EP candidates that are "just day trade or few days swing trades" during peak earnings season (Sep 2014); third/fourth earnings surprise "exhaustion gaps or island reversals" (Sep 2013); large-cap EPs with pullbacks, and issuers timing "secondaries and other capital raising events" with surprises (Feb 2010).

### Gaps
- EP-specific win rate, expectancy or drawdown from Bonde: NOT FOUND.
- Third-party win-rate claims (60-70%) from the earlier note remain unverified.

## 6. Source classification

### Takeaway
Everything quoted above is Bonde's own words on his blog, dated per post. Nothing from TraderLion, ChartMill, MarketInOut, Substack or TradingQnA was read this pass.

### Cited Findings
- Own words (dated): Feb 12 2010 EP scan; Jul 30 2014 EP process flow; Sep 2 2014 catalyst hunt; Nov 2 2010 neglect study; Sep 3 2013 news/neglect; May 21 2015 4% scan; Jul 12 2016 guidelines; Jan 14/17/28 2014 burst posts; Aug 8 2014 risk; Jun 27 2011 Kirk Report interview (Bonde answering, posted on his blog); Dec 2 2010 exits.
- Earlier-note claims NOT supported or contradicted by primary text: (a) "opening-range 5-30 minute break entry" (his text: buy immediately, pre-market); (b) "stop = low of day" for EP specifically (only generic); (c) "10-day MA trail" (not found, earlier note already said so); (d) "gap 8-10%+" (his scan is close-to-close >=8%, and his 2010 monthly-mover study says gaps below 10% are better); (e) "10-12 classic EP a year" (his words: "1 to 12" a year, "on an average ... one good trade like this in a year", "some years you find 10 to 12").

### Gaps
- TraderLion pages (403), ChartMill, MarketInOut, Substack, TradingQnA: NOT READ.
- Bonde's EP book/course ("Episodic Pivots" paid material) content: NOT FOUND.
