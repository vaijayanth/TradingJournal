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

## Position-size cap test (idle cash at 6%, user request 2026-11-09)
`--tier-cap` stops the per-position size growing at a maximum. Uncapped = the 6% row above.

| Cap per new position | ND CAGR / max DD / win rate / profit factor / final | AZ CAGR / max DD / win rate / profit factor / final |
|---|---|---|
| None (uncapped) | 28.1% / -15.5% / 41.4% / 2.01 / Rs2.37 Cr | 19.6% / -22.8% / 40.3% / 1.72 / Rs1.80 Cr |
| Rs1,00,000 | not run | 19.1% / -22.4% / 40.1% / 1.76 / Rs1.72 Cr |
| Rs50,000 | 27.8% / -15.5% / 41.2% / 2.11 / Rs2.32 Cr | 18.6% / -17.2% / 42.0% / 2.03 / Rs1.65 Cr |
| Rs25,000 | 26.4% / -13.1% / 42.0% / 2.42 / Rs2.08 Cr | not run |
| Rs10,000 | 20.9% / -11.8% / 42.7% / 2.63 / Rs1.34 Cr | not run |

## AZ entry window test (2026-11-18, user request)
`--flip-window N` = sessions since the green flip (freshest flip day only, ₹30L, ₹20k + ₹5k/100 trades uncapped, slippage 0.1%, 2016-11-07 to 2026-11-17, 214 stocks). Files: `results/az_win<N>_*`.

| Window | CAGR | Max DD | Closed | Win % | Avg win / loss | PF | Final equity | Missed entries (no cash) |
|---|---|---|---|---|---|---|---|---|
| 0 (flipped today, live rule) | 19.19% | -22.99% | 3,556 | 41.1 | +21.3 / -6.9 | 1.76 | Rs1.74 Cr | 2,465 |
| 1 | 18.92% | -24.23% | 3,528 | 40.7 | +21.4 / -6.9 | 1.75 | Rs1.70 Cr | 2,768 |
| 3 (earlier published setup) | 18.71% | -23.92% | 3,563 | 40.3 | +21.3 / -6.8 | 1.72 | Rs1.67 Cr | 2,938 |
| 5 | 18.87% | -24.53% | 3,618 | 40.2 | +21.3 / -6.8 | 1.71 | Rs1.70 Cr | 3,009 |

Reading: the spread is under 0.5 CAGR points, i.e. noise; flip-today is marginally best on CAGR, drawdown and profit factor, so the stricter rule costs nothing. Because only the freshest flip day is ordered, a wider window rarely adds trades. Same caveats as above (survivorship, dividend-adjusted prices, uncapped sizing).

## AZ capital-linked sizing test (2026-11-18, user request)
Flip window 0, 2016-11-07 to 2026-11-17, 214 stocks, idle cash earns 0%, slippage 0.1%. `--size-pct P --size-base realised|equity`: every new position = P% of (start capital + realised P&L) or of total equity (cash + holdings at the last close), replacing the trade-count ladder. Files: `results/az_size_*`.

| Start capital | Sizing | CAGR | Max DD | Closed | Win % | PF | Final | Missed (no cash) | Max pos |
|---|---|---|---|---|---|---|---|---|---|
| Rs30L | ladder (Rs20k + Rs5k/100) | 19.19% | -22.99% | 3,556 | 41.1 | 1.76 | Rs1.74 Cr | 2,465 | 134 |
| Rs30L | 0.5% realised | 12.61% | -16.28% | 5,919 | 41.5 | 1.83 | Rs0.99 Cr | 0 | 192 |
| Rs30L | 0.67% realised | 14.97% | -19.46% | 5,588 | 41.2 | 1.74 | Rs1.21 Cr | 369 | 157 |
| Rs30L | 1.0% realised | 18.81% | -20.96% | 4,210 | 42.0 | 1.80 | Rs1.69 Cr | 1,796 | 108 |
| Rs30L | 0.67% equity | 15.54% | -19.93% | 5,425 | 41.1 | 1.74 | Rs1.28 Cr | 532 | 147 |
| Rs1 Cr | ladder (Rs20k + Rs5k/100) | 14.92% | -19.07% | 5,322 | 40.5 | 1.77 | Rs4.03 Cr | 649 | 164 |
| Rs1 Cr | 0.5% realised | 12.84% | -16.30% | 5,919 | 41.7 | 1.84 | Rs3.36 Cr | 0 | 192 |
| Rs1 Cr | 0.67% realised | 15.04% | -19.42% | 5,569 | 41.2 | 1.74 | Rs4.08 Cr | 390 | 155 |
| Rs1 Cr | 1.0% realised | 18.53% | -21.11% | 4,187 | 41.8 | 1.77 | Rs5.50 Cr | 1,820 | 108 |
| Rs1 Cr | 0.67% equity | 15.76% | -19.88% | 5,400 | 41.3 | 1.75 | Rs4.34 Cr | 559 | 145 |

Reading: the ladder is capital-specific (Rs20k is 0.67% of Rs30L but 0.2% of Rs1 Cr, so the Rs1 Cr ladder run under-deploys: 14.9% vs 19.2%). A percentage rule gives near-identical results at both capitals (1.0%: 18.8% vs 18.5%). Low percentages leave cash idle (0% yield here), so CAGR falls as deployment falls; 1.0% matches the ladder's return (-0.4 pt at Rs30L) with a shallower drawdown (-21.0% vs -23.0%) and a higher profit factor. Equity base vs realised base: same within noise. Not yet tested: idle cash at 6%, and 1.25-1.5%.

### Same test with 6% on idle cash (liquid-fund yield), flip window 0
Files: `results/az_size6_*`. Percentages are of (start capital + realised P&L).

| Start capital | Sizing | CAGR | Max DD | Closed | Win % | PF | Final | Missed (no cash) | Max pos |
|---|---|---|---|---|---|---|---|---|---|
| Rs30L | ladder | 20.21% | -21.32% | 3,656 | 41.2 | 1.75 | Rs1.90 Cr | 2,360 | 136 |
| Rs30L | 0.67% | 16.77% | -17.51% | 5,751 | 41.4 | 1.75 | Rs1.42 Cr | 189 | 170 |
| Rs30L | 1.0% | 19.87% | -19.42% | 4,363 | 42.0 | 1.78 | Rs1.85 Cr | 1,637 | 113 |
| Rs30L | 1.25% | 20.40% | -21.94% | 3,597 | 42.0 | 1.75 | Rs1.93 Cr | 2,425 | 91 |
| Rs30L | 1.5% | 20.79% | -22.66% | 3,083 | 41.7 | 1.75 | Rs1.99 Cr | 2,953 | 76 |
| Rs1 Cr | ladder | 17.37% | -16.71% | 5,526 | 40.9 | 1.83 | Rs4.98 Cr | 419 | 170 |
| Rs1 Cr | 0.67% | 16.75% | -17.64% | 5,736 | 41.5 | 1.74 | Rs4.72 Cr | 206 | 168 |
| Rs1 Cr | 1.0% | 20.25% | -19.62% | 4,333 | 42.1 | 1.79 | Rs6.35 Cr | 1,667 | 112 |
| Rs1 Cr | 1.25% | 20.44% | -21.12% | 3,591 | 42.0 | 1.76 | Rs6.45 Cr | 2,431 | 90 |
| Rs1 Cr | 1.5% | 20.64% | -22.90% | 3,072 | 41.7 | 1.75 | Rs6.56 Cr | 2,965 | 75 |

Reading: with idle cash earning 6%, CAGR rises with the percentage (16.8% at 0.67% to 20.8% at 1.5%) and so does the drawdown (-17.5% to -22.7%): a smooth return/risk trade-off, not a free lunch. 1.0% gives about the ladder's CAGR (19.9% vs 20.2% at Rs30L) with a shallower drawdown (-19.4% vs -21.3%). The percentage rule is scale-free (1.0%: 19.9% at Rs30L, 20.3% at Rs1 Cr) while the ladder is not (20.2% vs 17.4%).

### Rs1 Cr start with a Rs50,000 ladder base (user request 2026-11-18)
Flip window 0, Rs1 Cr start, 6% idle cash, ladder `--base 50000 --step S` (S per 100 trades opened). Files: `results/az_1cr_*`.

| Sizing at Rs1 Cr | CAGR | Max DD | Closed | Win % | PF | Final | Missed (no cash) | Max pos |
|---|---|---|---|---|---|---|---|---|
| Ladder Rs20k + Rs5k (old base, reference) | 17.37% | -16.71% | 5,526 | 40.9 | 1.83 | Rs4.98 Cr | 419 | 170 |
| Ladder Rs50k + Rs5k | 18.35% | -17.19% | 5,322 | 41.1 | 1.84 | Rs5.41 Cr | 620 | 171 |
| Ladder Rs50k + Rs10k | 19.20% | -18.85% | 4,413 | 41.1 | 1.77 | Rs5.82 Cr | 1,580 | 137 |
| Ladder Rs50k + Rs12.5k (old ladder scaled 2.5x) | 19.82% | -19.42% | 4,138 | 41.3 | 1.77 | Rs6.13 Cr | 1,865 | 137 |
| 0.5% of base (realised) | 14.80% | -12.80% | 5,919 | 41.7 | 1.84 | Rs3.99 Cr | 0 | 192 |
| 1.0% of base (realised, reference) | 20.25% | -19.62% | 4,333 | 42.1 | 1.79 | Rs6.35 Cr | 1,667 | 112 |

Reading: a Rs50k start fixes the under-deployment of the Rs20k ladder at Rs1 Cr (+1.0 pt CAGR for +0.5 pt drawdown with the same Rs5k step). All the variants lie on one return/risk line (CAGR / |max DD| about 1.0-1.1): the step size, not the start size, sets where on the line you sit.
