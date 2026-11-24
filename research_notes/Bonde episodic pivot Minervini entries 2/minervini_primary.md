# Minervini entry strategies: primary-source verification attempt

Status: NOT COMPLETED. Every WebFetch failed with `getaddrinfo ENOTFOUND` (host outside the session's allowed network): www.chartmill.com, traderlion.com, www.mql5.com, stockbee.blogspot.com, tradingqna.com, www.minervini.com. The allow-list change reported by the caller has not taken effect in this session. Only one WebSearch (snippet-level) succeeded. Nothing below is verified from a full page or from Minervini's own text. The earlier notes in `research_notes/Bonde episodic pivot Minervini entries/minervini_entries.md` therefore stand unchanged, apart from the single addition below.

## Trend Template: 8 criteria and the 25% vs 30% dispute

### Takeaway
One new, still secondary, data point: an MQL5 article attributes 25% to "Think and Trade Like a Champion" and 30% to an earlier book. No Minervini text was reached, so the dispute is not resolved.

### Cited Findings
- An MQL5 article on automating the template says Minervini specifies 25% above the 52-week low in "Think and Trade Like a Champion" and 30% in an earlier book. The search tool's summary did not name the earlier book and I could not open the article — [MQL5 article](https://www.mql5.com/en/articles/22790) (found via search summary only)
- The 52-week-high condition is "within 25%" consistently across the scripts surfaced — [TradingView Minervini Trend Template](https://www.tradingview.com/script/zygjiw4C-Minervini-Trend-Template)
- Scripts differ on the low threshold: several TradingView scripts use 25%; a LevelUp screener lists "Price is 30%+ above the 52-week low"; a SEPA-based script uses "at least 30%" — [LevelUp screener](https://tradingview.com/script/xt1TZYqW-LevelUp-Minervini-Trend-Template-Screener); [Minervini SEPA System](https://in.tradingview.com/script/kcihs4Hp-Minervini-SEPA-System)
- Remaining criteria (MA stack, rising 200MA, RS floor 70) as in the earlier notes, still from ChartMill/TradingView snippets only.

### Inferences
- Both thresholds exist in circulation; the "25% later / 30% earlier" attribution is plausible but rests on one unread article.

### Gaps
- Primary text for all 8 criteria: NOT FOUND. 200MA slope duration in Minervini's words: NOT FOUND. Fix: allow the hosts, or provide the book text.

## VCP (contractions, depth, volume, pivot, buy range, breakout volume)

### Takeaway
No new information; ChartMill's VCP article could not be fetched.

### Cited Findings
- None new. See earlier notes (community conventions only).

### Gaps
- Minervini's own statements on contraction count, depth, dry-up, buy range and breakout volume: NOT FOUND. Community vs Minervini separation could not be improved.

## Cheat, low cheat, Power Play, handle, undercut entries

### Takeaway
Nothing new found.

### Cited Findings
- None new.

### Gaps
- Numeric rules for all of these: NOT FOUND.

## Risk, sizing, selling, win rate, SEPA fundamentals, market filters

### Takeaway
Nothing new found; TraderLion's risk page could not be fetched.

### Cited Findings
- None new.

### Gaps
- Max stop %, risk per trade, average-loss target, 3:1 rule, pyramiding, win rate and average gain/loss as he states them, Code 33 thresholds, market filters: NOT FOUND from primary sources.

## Open-source or vendor backtests of the Trend Template / VCP

### Takeaway
None found.

### Cited Findings
- None. No search was run for this; the fetch blocks ended the session's useful work.

### Gaps
- Backtest numbers: NOT FOUND.
