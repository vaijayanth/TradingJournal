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

### Rs20,000 base with a Rs10,000 step (user request 2026-11-18)
Flip window 0, 6% idle cash, 2016-11-07 to 2026-11-17. Files: `results/az_ladder_*_b20k_s10k_*`.

| Start capital | Ladder | CAGR | Max DD | Closed | Win % | PF | Final | Missed (no cash) | Max pos |
|---|---|---|---|---|---|---|---|---|---|
| Rs30L | Rs20k + Rs5k (current) | 20.21% | -21.32% | 3,656 | 41.2 | 1.75 | Rs1.90 Cr | 2,360 | 136 |
| Rs30L | Rs20k + Rs10k | 20.91% | -22.48% | 2,761 | 41.7 | 1.76 | Rs2.01 Cr | 3,279 | 129 |
| Rs1 Cr | Rs20k + Rs5k | 17.37% | -16.71% | 5,526 | 40.9 | 1.83 | Rs4.98 Cr | 419 | 170 |
| Rs1 Cr | Rs20k + Rs10k | 18.24% | -18.88% | 4,497 | 40.6 | 1.75 | Rs5.36 Cr | 1,500 | 146 |

Reading: doubling the step adds about 0.7-0.9 pt CAGR and 1.2-2.2 pt drawdown, the same return/risk line as the other variants.

## ND (Dhan dh252) sizing test (2026-11-18, user request)
Strategy: close above the 252-session closing high + Supertrend green, whole-position Supertrend-red exit, add-on at -6%; universe = every validated symbol (1,495) or the live ND universe (`--live-universe`: 1,483, ETFs and InvITs removed). 2016-11-07 to 2026-11-17, 6% idle cash, 0.1% slippage. Ladder = Rs1,000 + Rs1,000 per 100 closed trades, uncapped (the live position-size-doubling milestone is NOT modelled). `--size-pct` = each new position is that % of (start capital + realised P&L). Files: `results/nd_*`.

| Start capital | Sizing | CAGR | Max DD | Closed | Win % | Avg win / loss | PF | Final | Missed (no cash) | Max pos |
|---|---|---|---|---|---|---|---|---|---|---|
| Rs20L | ladder, all symbols | 28.08% | -15.46% | 7,927 | 41.4 | +33.0 / -9.0 | 2.02 | Rs2.39 Cr | 21,253 | 469 |
| Rs20L | ladder, live universe | 28.01% | -15.42% | 7,898 | 41.3 | +33.1 / -9.0 | 2.01 | Rs2.38 Cr | 20,957 | 469 |
| Rs20L | 0.1% | 11.63% | -5.40% | 9,986 | 42.2 | +35.4 / -8.4 | 2.11 | Rs0.60 Cr | 0 | 650 |
| Rs20L | 0.25% | 19.82% | -11.69% | 9,518 | 43.0 | +34.8 / -8.9 | 2.05 | Rs1.23 Cr | 3,998 | 504 |
| Rs20L | 0.5% | 26.20% | -19.46% | 7,140 | 42.6 | +35.5 / -9.1 | 1.85 | Rs2.06 Cr | 26,029 | 288 |
| Rs20L | 1.0% | 31.58% | -22.48% | 4,350 | 42.7 | +36.5 / -9.2 | 1.81 | Rs3.13 Cr | 51,218 | 162 |
| Rs1 Cr | ladder (live universe) | 18.28% | -10.04% | 9,903 | 42.8 | +34.8 / -8.8 | 2.19 | Rs5.38 Cr | 655 | 650 |
| Rs1 Cr | 0.1% | 12.10% | -4.97% | 9,986 | 43.0 | +34.6 / -8.9 | 2.32 | Rs3.14 Cr | 0 | 650 |
| Rs1 Cr | 0.25% | 20.28% | -11.50% | 9,518 | 43.2 | +34.7 / -8.9 | 2.07 | Rs6.37 Cr | 4,001 | 505 |
| Rs1 Cr | 0.5% | 26.18% | -19.36% | 7,113 | 42.5 | +35.4 / -9.2 | 1.84 | Rs10.29 Cr | 26,429 | 286 |
| Rs1 Cr | 1.0% | 31.84% | -22.41% | 4,314 | 43.0 | +36.3 / -9.3 | 1.84 | Rs15.98 Cr | 51,421 | 162 |

Reading: at Rs20L the Rs1,000 ladder (28.0% / -15.4%, return per drawdown 1.8) sits on a better frontier than any fixed percentage (1.0%: 31.6% / -22.5%, 1.4; 0.25%: 19.8% / -11.7%, 1.7) because it starts at 0.05% of capital and ramps with experience. The ladder is capital-specific: at Rs1 Cr it under-deploys (18.3%). Percentage rules are scale-free (1.0%: 31.6% at Rs20L, 31.8% at Rs1 Cr). Up to 469-650 simultaneous positions: far above the live book (about 50), so liquidity and execution limits would bind in practice.

### ND doubling ladder: size doubles every 100 trades (user request 2026-11-18)
`--double` = base x 2^(closed trades / 100) (Rs1,000, 2,000, 4,000 ... Rs1,00,000 after 7 doublings = 700 trades); `--tier-cap` limits it. Live ND universe, 6% idle cash, 2016-11-07 to 2026-11-17. Files: `results/nd_*_dbl_*`.

| Start capital | Sizing | CAGR | Max DD | Closed | Win % | PF | Final | Missed (no cash) |
|---|---|---|---|---|---|---|---|---|
| Rs20L | ladder Rs1k + Rs1k (live, ref) | 28.01% | -15.42% | 7,898 | 41.3 | 2.01 | Rs2.38 Cr | 20,957 |
| Rs20L | double, cap Rs5k | 15.84% | -6.71% | 9,953 | 42.4 | 2.54 | Rs0.87 Cr | 132 |
| Rs20L | double, cap Rs10k | 20.77% | -12.04% | 9,564 | 42.5 | 2.60 | Rs1.33 Cr | 3,874 |
| Rs20L | double, cap Rs25k | 27.55% | -20.29% | 8,528 | 42.2 | 2.48 | Rs2.29 Cr | 13,813 |
| Rs20L | double, cap Rs50k | 31.56% | -26.10% | 7,321 | 40.8 | 2.23 | Rs3.13 Cr | 26,377 |
| Rs20L | double, cap Rs1L | 37.19% | -27.92% | 6,293 | 40.2 | 2.14 | Rs4.76 Cr | 36,447 |
| Rs20L | double, no cap | 23.54% | -35.52% | 1,176 | 36.4 | 1.53 | Rs1.67 Cr | 83,052 |
| Rs1 Cr | ladder Rs1k + Rs1k (ref) | 18.28% | -10.04% | 9,903 | 42.8 | 2.19 | Rs5.38 Cr | 655 |
| Rs1 Cr | double, cap Rs10k | 11.03% | -3.61% | 9,986 | 42.7 | 2.65 | Rs2.86 Cr | 0 |
| Rs1 Cr | double, cap Rs25k | 16.19% | -6.51% | 9,984 | 42.8 | 2.72 | Rs4.50 Cr | 14 |
| Rs1 Cr | double, cap Rs50k | 21.10% | -11.56% | 9,581 | 42.7 | 2.70 | Rs6.82 Cr | 3,663 |
| Rs1 Cr | double, cap Rs1L | 25.90% | -16.39% | 8,862 | 42.2 | 2.54 | Rs10.07 Cr | 10,709 |
| Rs1 Cr | double, no cap | 23.97% | -33.64% | 1,415 | 35.7 | 1.56 | Rs8.62 Cr | 81,207 |

Reading: uncapped doubling fails (about 1,200-1,400 closed trades in 10 years, win rate 36%, drawdown -34 to -36%): after about 1,000 trades one position is more than the whole account, so cash runs out and almost every entry is missed. With a cap it is a return/risk trade-off on a line slightly below the linear ladder at Rs20L (return per drawdown 1.4 for the doubling with cap Rs25k-1L vs 1.8 for the ladder), but with higher profit factors (2.1-2.6).

### Dhan entry on the AZ (Nifty F&O) universe (user request 2026-11-18)
`--strategy dhan --fno-universe`: close above the 252-session closing high + Supertrend green, whole-position Supertrend-red exit, add-on at -6%, on the 214 current Nifty F&O stocks (BSE, BEL, RECLTD excluded). 2016-11-07 to 2026-11-17, 6% idle cash. Files: `results/fno_*`. AZ rows are the flip-today strategy (window 0) from the sizing tests, for comparison.

| Strategy / sizing | Start | CAGR | Max DD | Closed | Win % | Avg win / loss | PF | Final | Missed | Max pos |
|---|---|---|---|---|---|---|---|---|---|---|
| Dhan entry, ladder Rs1k + Rs1k | Rs20L | 8.96% | -4.48% | 2,267 | 41.7 | +23.2 / -6.4 | 2.13 | Rs0.47 Cr | 0 | 151 |
| Dhan entry, ladder Rs1k + Rs1k | Rs30L | 8.05% | -3.26% | 2,267 | 41.7 | +23.2 / -6.4 | 2.13 | Rs0.65 Cr | 0 | 151 |
| Dhan entry, ladder Rs20k + Rs5k | Rs30L | 15.56% | -12.75% | 2,155 | 42.6 | +22.6 / -6.7 | 2.22 | Rs1.28 Cr | 1,138 | 107 |
| Dhan entry, 0.25% of capital | Rs30L | 7.74% | -1.96% | 2,267 | 42.2 | +23.0 / -6.5 | 2.18 | Rs0.63 Cr | 0 | 151 |
| Dhan entry, 0.5% | Rs30L | 9.67% | -4.20% | 2,267 | 42.4 | +22.8 / -6.6 | 2.20 | Rs0.76 Cr | 0 | 151 |
| Dhan entry, 1.0% | Rs30L | 13.32% | -10.08% | 2,256 | 42.6 | +22.7 / -6.7 | 2.10 | Rs1.05 Cr | 138 | 123 |
| AZ flip-today, ladder Rs20k + Rs5k (ref) | Rs30L | 20.21% | -21.32% | 3,656 | 41.2 | +21.0 / -6.8 | 1.75 | Rs1.90 Cr | 2,360 | 136 |
| AZ flip-today, 1.0% (ref) | Rs30L | 19.87% | -19.42% | 4,363 | 42.0 | +22.1 / -6.8 | 1.78 | Rs1.85 Cr | 1,637 | 113 |

Reading: on the 214-stock F&O universe the 252-day-high entry produces far fewer trades (2,267 vs 3,556-4,363 in 10 years), so the Rs1,000 ladder barely deploys capital (CAGR 8-9%, drawdown -3 to -4%, no missed entries). At equal sizing (Rs20k + Rs5k) it earns 15.6% with a shallower drawdown (-12.8% vs -21.3%) and higher PF (2.22 vs 1.75) than the AZ flip-today entry, but less return. The Dhan entry's big average win (+33%) comes from the small/mid-cap names of the full 1,483-stock universe; on F&O stocks it is +23%.

### Dhan entry on the F&O universe: sizing up to 3% (user request 2026-11-18)
Same setup as the table above (Rs30L, 6% idle cash, each position = that % of start capital + realised P&L). Files: `results/fno_30L_d_p*`.

| Sizing | CAGR | Max DD | Return / DD | Closed | Win % | PF | Final | Missed | Max pos |
|---|---|---|---|---|---|---|---|---|---|
| 0.5% | 9.67% | -4.20% | 2.30 | 2,267 | 42.4 | 2.20 | Rs0.76 Cr | 0 | 151 |
| 1.0% | 13.32% | -10.08% | 1.32 | 2,256 | 42.6 | 2.10 | Rs1.05 Cr | 138 | 123 |
| 1.5% | 16.25% | -15.98% | 1.02 | 2,001 | 42.8 | 2.09 | Rs1.36 Cr | 2,374 | 84 |
| 2.0% | 18.29% | -19.48% | 0.94 | 1,765 | 42.7 | 2.05 | Rs1.62 Cr | 4,812 | 63 |
| 2.5% | 19.39% | -22.63% | 0.86 | 1,558 | 43.2 | 2.01 | Rs1.77 Cr | 6,900 | 50 |
| 3.0% | 20.78% | -23.15% | 0.90 | 1,341 | 44.1 | 2.09 | Rs1.99 Cr | 8,882 | 41 |
| Ladder Rs20k + Rs5k | 15.56% | -12.75% | 1.22 | 2,155 | 42.6 | 2.22 | Rs1.28 Cr | 1,138 | 107 |
| AZ flip-today, ladder Rs20k + Rs5k (ref) | 20.21% | -21.32% | 0.95 | 3,656 | 41.2 | 1.75 | Rs1.90 Cr | 2,360 | 136 |

Reading: sized up, the Dhan entry on F&O stocks reaches AZ-like returns only at 3% (20.8% vs 20.2%) with a similar drawdown (-23.2% vs -21.3%), so its return per drawdown (0.90) falls to the AZ level (0.95); its edge is lower risk at low sizing, not more return. Cash becomes the limit: at 3% it holds at most 41 positions and misses 8,882 entries.

### ND at Rs1 Cr: scaled ladder base (user request 2026-11-18)
Live ND universe, 6% idle cash, 2016-11-07 to 2026-11-17. Files: `results/nd_1Cr_b*`.

| Start capital | Ladder | CAGR | Max DD | Return / DD | Closed | Win % | PF | Final | Missed | Max pos |
|---|---|---|---|---|---|---|---|---|---|---|
| Rs20L | Rs1k + Rs1k (live) | 28.01% | -15.42% | 1.82 | 7,898 | 41.3 | 2.01 | Rs2.38 Cr | 20,957 | 469 |
| Rs1 Cr | Rs1k + Rs1k (old size) | 18.28% | -10.04% | 1.82 | 9,903 | 42.8 | 2.19 | Rs5.38 Cr | 655 | 650 |
| Rs1 Cr | Rs5k + Rs1k | 19.18% | -9.86% | 1.95 | 9,896 | 43.1 | 2.22 | Rs5.81 Cr | 730 | 598 |
| Rs1 Cr | Rs5k + Rs2.5k | 24.68% | -12.19% | 2.02 | 8,944 | 42.4 | 2.13 | Rs9.13 Cr | 10,140 | 469 |
| Rs1 Cr | **Rs5k + Rs5k** | **28.08%** | **-15.37%** | 1.83 | 7,897 | 41.5 | 2.01 | Rs11.95 Cr | 21,033 | 469 |
| Rs1 Cr | Rs10k + Rs5k | 28.08% | -15.67% | 1.79 | 7,840 | 41.5 | 2.00 | Rs11.95 Cr | 21,691 | 469 |

Reading: scaling the ladder 5x with capital (Rs5k + Rs5k at Rs1 Cr) reproduces the Rs20L result almost exactly (28.1% vs 28.0%, -15.4% vs -15.4%). A smaller step trades return for a shallower drawdown (Rs5k + Rs2.5k: 24.7%, -12.2%).

### AZ at Rs1 Cr: scaled ladder (user request 2026-11-18)
Flip window 0, 6% idle cash, 2016-11-07 to 2026-11-17. Scaled = both base and step multiplied by 1 Cr / Rs30L = 3.33 (Rs20k -> Rs66.7k, Rs5k -> Rs16.7k). Files: `results/az_1Cr_b66700_s16700*`.

| Start capital | Ladder | CAGR | Max DD | Return / DD | Closed | Win % | PF | Final | Missed | Max pos |
|---|---|---|---|---|---|---|---|---|---|---|
| Rs30L | Rs20k + Rs5k (live) | 20.21% | -21.32% | 0.95 | 3,656 | 41.2 | 1.75 | Rs1.90 Cr | 2,360 | 136 |
| Rs1 Cr | Rs20k + Rs5k (old size) | 17.37% | -16.71% | 1.04 | 5,526 | 40.9 | 1.83 | Rs4.98 Cr | 419 | 170 |
| Rs1 Cr | Rs50k + Rs5k | 18.35% | -17.19% | 1.07 | 5,322 | 41.1 | 1.84 | Rs5.41 Cr | 620 | 171 |
| Rs1 Cr | Rs50k + Rs12.5k | 19.82% | -19.42% | 1.02 | 4,138 | 41.3 | 1.77 | Rs6.13 Cr | 1,865 | 137 |
| Rs1 Cr | **Rs66.7k + Rs16.7k (scaled)** | **20.22%** | **-21.65%** | 0.93 | 3,648 | 41.1 | 1.75 | Rs6.34 Cr | 2,368 | 135 |

Reading: the scaled ladder reproduces the Rs30L result (20.2% vs 20.2%, -21.7% vs -21.3%). Both strategies scale cleanly when base and step grow with capital.

### Ladder step every 50 trades instead of 100 (user request 2026-11-18)
`--every 50`. Same period and costs as above (6% idle cash). Files: `results/nd_20L_e50_*`, `results/az_30L_e50_*`.

| Strategy | Ladder | CAGR | Max DD | Return / DD | Closed | Win % | PF | Final | Missed |
|---|---|---|---|---|---|---|---|---|---|
| ND Rs20L | Rs1k per 100 trades (live) | 28.01% | -15.42% | 1.82 | 7,898 | 41.3 | 2.01 | Rs2.38 Cr | 20,957 |
| ND Rs20L | Rs1k per 50 trades (faster) | 31.63% | -19.32% | 1.64 | 6,769 | 40.7 | 1.93 | Rs3.14 Cr | 31,729 |
| ND Rs20L | Rs500 per 50 trades (same ramp) | 27.92% | -15.56% | 1.79 | 7,891 | 41.2 | 2.00 | Rs2.36 Cr | 21,170 |
| AZ Rs30L | Rs5k per 100 trades (live) | 20.21% | -21.32% | 0.95 | 3,656 | 41.2 | 1.75 | Rs1.90 Cr | 2,360 |
| AZ Rs30L | Rs5k per 50 trades (faster) | 21.13% | -22.61% | 0.93 | 2,770 | 41.4 | 1.75 | Rs2.05 Cr | 3,270 |
| AZ Rs30L | Rs2.5k per 50 trades (same ramp) | 20.65% | -21.06% | 0.98 | 3,701 | 41.3 | 1.76 | Rs1.97 Cr | 2,313 |

Reading: stepping every 50 trades with the same step is just a faster ramp (more return, more drawdown, same return per drawdown or worse). With half the step it is the same ramp in smaller increments and changes almost nothing.
