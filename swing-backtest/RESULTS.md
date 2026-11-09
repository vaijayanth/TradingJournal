# Swing strategy backtests - last 10 years (2016-11-07 to 2026-11-09)

Engine: `swing_backtest.py` (daily closes, next-open fills, Supertrend(10,3), cash-limited, equity = cash + holdings). Data: the backtester's `checkpoints/raw` history (starts 2016-11-07). Costs: Indian delivery charges + 0.1% slippage per fill. Run: `python -I swing-backtest/swing_backtest.py --data <checkpoints dir> --strategy az|dhan --start 2016-11-07 --out swing-backtest/results/<name>`.

| | ND (Dhan, dh252) | AZ (Zerodha, Nifty F&O) |
|---|---|---|
| Universe | 1,480 stocks | 214 stocks |
| Start capital | Rs20,00,000 | Rs30,00,000 |
| Entry | close above the 252-session closing high + Supertrend green | Supertrend turned green within 3 sessions, freshest flip day only |
| Size | Rs1,000 + Rs1,000 per 100 closed trades (uncapped) | Rs20,000 + Rs5,000 per 100 trades (uncapped) |
| Final equity | Rs2.04 Cr | Rs1.68 Cr |
| CAGR | 26.1% (29.4% after the 1-year warm-up) | 18.8% |
| Max drawdown | -17.8% | -23.8% (both bottomed 2022-06-20) |
| Closed trades / win rate | 7,602 / 41.4% | 3,572 / 40.3% |
| Avg win / avg loss | +33.1% / -9.0% | +21.3% / -6.8% |
| Profit factor | 2.01 | 1.72 |
| Avg hold winners / losers | 103 d / 39 d | 107 d / 36 d |
| Fees paid | Rs8.1 L | Rs9.6 L |

Caveats: survivorship bias (today's listings and today's F&O list), dividend-adjusted prices, no liquidity limits, no tax, uncapped sizing compounds the result, the AZ sizing cap is an assumption (none stated), and ND's first year has no signals (needs 252 sessions of history).

## With idle cash in a liquid ETF (LIQUIDBEES), user request 2026-11-09
Idle cash accrues daily at a flat annual yield (`--cash-rate`). LIQUIDBEES pays its return as dividends (price stays Rs1,000), so Yahoo has no usable return series; LIQUIDCASE's price-only return was about 5.5% a year in 2025-26, so 5%, 6% and 7% are shown. No charges on the ETF are modelled.

| Yield on idle cash | ND CAGR / max DD / final | AZ CAGR / max DD / final |
|---|---|---|
| 0% (base above) | 26.1% / -17.8% / Rs2.04 Cr | 18.8% / -23.8% / Rs1.68 Cr |
| 5% | 27.7% / -15.9% / Rs2.30 Cr | 19.6% / -22.9% / Rs1.79 Cr |
| **6%** | **28.1% / -15.5% / Rs2.37 Cr** | **19.6% / -22.8% / Rs1.80 Cr** |
| 7% | 28.4% / -15.2% / Rs2.43 Cr | 19.9% / -22.5% / Rs1.85 Cr |
