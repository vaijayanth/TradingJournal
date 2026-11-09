# Options strategy v2 (agreed in discussion 2026-11-09; NOT yet built into the engines)

Premium selling with defined risk, Tastytrade-style, adjusted for Indian stock options (monthly expiries only, physical settlement, gap risk around results, large lots).
Accounts: ND (Dhan) Rs50 lakh, universe = the 10 shares MCX, SHRIRAMFIN, CGPOWER, BSE, DIXON, HCLTECH, INFY, BANKINDIA, BPCL, CUMMINSIND (capital grows with profits); AZ (Zerodha) Rs1.5 crore, universe = Nifty F&O stocks.
All numbers are proposals the user agreed to start from; tune them with a trade log.

## Clarifications (user, 2026-11-09)
- ND: the Rs50 lakh options capital is SEPARATE from the swing/investment shares (the same 10 stocks, about Rs7.8 lakh market value). Shares do NOT count toward the options loss limits.
- DECIDED: ND uses BOTH sides as in v2 (put spread on green, call spread on red), one spread per stock. Suggested extra (user to accept or reject): a sub-limit on the put-spread side, about 5% of capital in total max loss, because the long shares and the short puts both lose in a market fall.

- DECIDED (2026-11-09, final): ND's options universe is the full Nifty F&O universe (same funnel as AZ), not just the 10 swing stocks. ND and AZ each rank independently and take their own top-ranked candidates (leaving out the stocks they already hold); OVERLAP BETWEEN THE TWO BROKERS IS ALLOWED. Each broker's own limits apply separately (ND 8-10 spreads, AZ 15-20). Optional, informational only: list stocks open at both brokers. (An earlier idea to split ranks 1-10 / 11-30 was dropped.)
- DECIDED (2026-11-09, final for swing shares): ND scans the 10 swing shares FIRST (tier 1) but ONLY FOR BEAR CALL SPREADS: a swing share that meets all the call-spread criteria (Supertrend red, skip rules, IVP, ROI, limits) gets its spread before the rest; swing shares get NO put spreads (they are already long those stocks). Remaining slots and loss budget are filled from the rest of the Nifty F&O universe (tier 2, both sides) by score. The priority never overrides the hard filters. AZ has no such priority. The put-side cap of about 5% of capital is no longer needed for the swing shares; it stays an optional general limit for tier-2 put spreads (not yet accepted).

## Entry
1. Direction from the Supertrend colour: green = bull put spread, red = bear call spread. Most recent flips rank first.
2. Skip: results inside the trade window; F&O ban list; an open spread in that stock already; RSI veto (no calls on a green stock with RSI > 70, no puts on a red stock with RSI < 30); thin open interest or a stale price on either leg; one lot's max loss above the per-position limit.
3. Window: expiry 30-45 days away (mid-month for next month's expiry). Place after about 09:30 IST with a fair limit price, never a blind last price.
4. Edge: IV percentile (IVP) of the stock's ATM IV over the last 252 days: 70+ full size, 50-70 normal, 30-50 half size, below 30 skip; until IV history exists use chain IV above recent realised volatility.
5. Strikes: short leg nearest 0.12-0.15 delta (CHANGED 2026-11-09 after the backtest below: 0.20-0.30 lost money once realistic slippage was included), hedge 1-2 listed strikes further out.
6. Pay check: net credit / margin (spread width - credit) at least 2%, and credit at least Rs2 a share.
7. Size: max loss of the spread (width x quantity - credit) at most about 1% of capital for ND, 0.7% for AZ.
8. Book limits: ND 8-10 spreads (one per stock); AZ 15-20 target, 25 maximum, at most 2 per sector; total max loss about 8% of capital; margin in use at most 35% (AZ 30-35%); keep about 20% of the loss budget free. If a month is down 4% of capital, open nothing new until the next cycle.
9. Selection for AZ: filters above, then rank by score = IVP 30% + ROI on margin 25% + fresh flip 20% + liquidity 15% + strike buffer beyond the recent range 10%; fill from the top within the limits; the user confirms each ticket.

## Profit taking
- Close the whole spread when buying it back costs 50% of the credit received (short leg price - hedge leg price <= 0.5 x credit). Raise a "Profit Exit" alert for it; the 60% single-leg decay rule is for naked legs only.

## Exit and management
- Time exit: at 21 days left, close; roll only if the Supertrend signal is still valid, IVP is still good and the roll gives a net credit.
- Loss exit: close when buying the spread back costs 2x the credit received (loss = 1x the credit), or when the short strike's delta reaches 0.35, or after a close beyond the short strike (close next morning).
- Never hold an in-the-money leg into the last 7 days (physical delivery at expiry): the "Expiry risk" alert.
- No averaging down, no adding naked legs to "defend", no re-entry in the same stock in the same cycle unless a new Supertrend flip appears.
- Because spreads are defined risk, the protection is the capped max loss plus these alerts; broker stop orders on one leg of a spread are not used.

## To build
IV history (NSE F&O bhavcopy, backfill about a year, daily update) and the IVP filter; results calendar and F&O ban list checks; realised volatility; spread-level credit/margin/ROI and net-value Profit Exit and loss alerts; position and risk limits as hard checks in the ticket builders; a closed-trade log; a paper month before real money.

## Backtest findings (2026-11-09, options-backtest/, real NSE bhavcopy EOD settlement prices, Jan 2024 - Oct 2026, 54 liquid F&O stocks incl. the ND 10)
Rules simulated: entry 30-45 DTE, Supertrend colour direction (previous close), hedge up to 2 listed strikes out, 50% profit take, stop when the spread costs 2x the credit, time exit at 21 DTE, Indian charges, slippage 0/3/6% of each leg's premium, 1 lot per trade. In-sample, about 31 months, survivorship (universe = today's most liquid names), end-of-day marks (not intraday), no results/ban filters.
- Slippage decides everything: at 0% slippage almost every variant is positive; at 3% only the low-delta ones are comfortably positive; at 6% most are negative except 0.15 delta (and condors).
- Short delta 0.10-0.15 is the most robust (stop hits about 16%); 0.20-0.30 had 25-30% stop hits and turned negative at 3-6% slippage. Do not use 0.25-0.30.
- 0.15 delta, colour-directed spreads, 3% slippage: 237 trades, win 79%, avg win Rs3.5k, avg loss -Rs7.2k, expectancy +Rs1.2k per 1-lot trade, about 4% on margin per trade; scaled to Rs50k max loss per position on Rs50L: about 0.3-0.5% per month, worst month -0.8%, max drawdown -1.7%. 2024 was negative (-Rs20k at 1 lot), 2025 and 2026 positive.
- 0.15 delta iron condors (both sides, colour-agnostic) were the best risk-adjusted: win 81-84%, max drawdown about -0.26% of capital, 26/32 months positive, about 0.14-0.24% per month.
- IVP >= 50 mostly reduces drawdown and trade count (about -40% trades) rather than adding return at 0.15 delta; it rescued the higher-delta variants.
- Colour direction adds little over always selling puts (put-only 0.15 delta: expectancy Rs1.0k vs Rs1.2k directed); call spreads alone are rare (95 trades).
- Realistic expectation: about 0.3-0.7% per month on total capital before extreme months, not 1-2%.

## V1 backtest on AZ (2026-11-09, options-backtest/v1_backtest.py; real NSE EOD prices Jan 2024 - Oct 2026, all Nifty F&O stocks, 215 with data, Rs1.5 crore, margin modelled at 13% of stock value per lot)
V1 as the user described: sell ~0.10 delta stock calls (V1 signal: RSI>70 or Supertrend red with RSI>=30), stop at 3x premium, profit at 60% decay, strict exit when the stock closes at or above the strike, held otherwise to expiry; 1 lot per signal; slippage max(3%, 1 tick) per fill.
- Entering 30-45 days out: 4,132 trades, win 79%, avg win +Rs4.9k, avg loss -Rs15.3k, expectancy +Rs698 per trade, about +6.8% a year on Rs1.5 crore (about 0.55% a month, about Rs83k), worst month -5.2%, max drawdown -10.6%, peak margin 76%, worst trade -Rs1.94 lakh (ANGELONE, Jan 2026). By year: 2024 +Rs5.2L, 2025 +Rs21.7L, 2026 (to Oct) +Rs2.0L.
- Entering 14-28 days out (closer to how it is traded now): NEGATIVE, about -2.5% a year.
- Exit mix (30-45 DTE): profit exits 79% (+Rs4.8k each), stops 10.6% (-Rs11.5k each), strike exits 10.3% (-Rs18.8k each; the biggest loss source), expiry 0.3%.
- Without the strict strike exit the return is similar but the worst trade is -Rs3.6L and drawdown -13.1%; adding a Supertrend-colour-flip exit cut the return to about 4.6% a year.
- Entry rule hardly matters (V1 signal 6.8%, red only 5.9%, every stock 7.0% but drawdown -16%).
- Slippage: 0% = 10.6% a year, 3% = 6.8%, 6% = 2.4%. Costs about 8% of gross profit. Halving the margin used (cap 50%) lowered the return to 3.7% but not the drawdown (-10.5%).
- Caveats: EOD marks (intraday touches and gaps not seen), no results/ban filter, modelled margin, no physical-delivery effects, in-sample 31 months.

## V1 backtest: entry only on a fresh red flip, and results filter (2026-11-09)
Same set-up as the V1 backtest (AZ, Rs1.5Cr, 0.10 delta calls, 30-45 DTE, stop 3x, profit 60% decay, strict strike exit, 3% slippage). Results dates from Yahoo (`options-backtest/fetch_results_dates.py`, coverage uneven for older periods).
- Enter only when Supertrend turned red within the last 2 sessions: 850 trades, win 82.7%, expectancy Rs290, +0.58%/yr, max DD -2.4%, worst trade -Rs67k (average margin used only 6.5% of capital).
- Same plus skip when results fall within 15 days: 687 trades, win 83.7%, expectancy Rs499, +0.82%/yr, max DD -1.9%.
- Original V1 signal plus the 15-day results filter: 3,800 trades, win 80.6%, expectancy Rs857, +7.7%/yr (was 6.8%), max DD -9.1% (was -10.6%), worst trade -Rs1.21L (was -Rs1.94L).

## Fresh-flip calls + bull put spreads (2026-11-09, `options-backtest/v1_putspread.py`)
Rs1.5Cr, 30-45 DTE, results filter 15 days, 3% slippage. Calls = red flip, 0.10 delta. Put spread = sell put at the delta shown, buy 2 strikes lower, stop 3x credit, profit 60% decay, exit if stock closes at/below the short strike.
- Flip within 2 days, put 0.10 delta: puts 160 trades +0.5%/yr; calls+puts 850 trades +1.3%/yr, DD -1.6%.
- Flip within 2 days, put 0.15 delta: puts 390 trades, win 80.5%, +0.8%/yr, DD -1.0%; calls+puts 1,080 trades +1.6%/yr, DD -1.6%.
- Flip within 5 days, put 0.15 delta: puts 622 trades +1.2%/yr; calls+puts 1,628 trades win 82.5%, +3.2%/yr, DD -3.2%, worst trade -Rs67k, average margin ~10% of capital.
