# Long / Short Backtest (shares long + puts when the market is weak)

- Universe: AAPL, AMD, AMZN, AVGO, GOOGL, INTC, META, MSFT, NVDA, TSLA; regime benchmark SPY vs its 50-day SMA
- Period: 2021-09-01 to 2026-11-10; start equity $50,000
- Put sleeve: long puts only (no stock needed), ~35 DTE at the money, -50% stop, trailing stop after +50%, closed 5 days before expiry
- C: puts risk 0.5% of the account per trade; D: 1%; E/F: 2%

| Variant | Return % | Max DD % | Sharpe | Median return % (subsets) | Median DD % | Median Sharpe | Beats B (Sharpe) |
|---|---:|---:|---:|---:|---:|---:|---:|
| A. shares long, no filter | +60.2 | 14.1 | 0.87 | +48.4 | 11.8 | 0.85 | 0 / 6 |
| B. shares long, SPY>50d filter | +57.8 | 10.6 | 0.86 | +52.3 | 9.6 | 0.90 | – |
| C. B 90% + put sleeve 10% | +54.0 | 10.1 | 0.86 | +45.5 | 9.2 | 0.87 | 2 / 6 |
| D. B 80% + put sleeve 20% | +40.3 | 10.4 | 0.72 | +35.9 | 10.0 | 0.75 | 0 / 6 |
| E. options only: calls if SPY>50d, puts if below | +45.1 | 25.6 | 0.45 | +25.8 | 26.2 | 0.34 | 0 / 6 |
| F. puts only (SPY<50d), 100% of capital | -23.7 | 27.0 | -0.47 | -23.0 | 27.4 | -0.61 | 0 / 6 |

## Return by year, full universe (%)

| Variant | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---:|---:|---:|---:|---:|---:|
| A. shares long, no filter | +8.9 | -6.9 | +19.2 | +16.3 | +9.4 | +4.2 |
| B. shares long, SPY>50d filter | +5.7 | -5.9 | +20.5 | +17.3 | +9.7 | +2.2 |
| C. B 90% + put sleeve 10% | +6.8 | -6.2 | +18.0 | +17.4 | +8.9 | +1.9 |
| D. B 80% + put sleeve 20% | +2.5 | -7.7 | +14.9 | +16.8 | +8.4 | +1.9 |
| E. options only: calls if SPY>50d, puts if below | +28.3 | -12.9 | +2.4 | +19.3 | -7.9 | +15.4 |
| F. puts only (SPY<50d), 100% of capital | -5.5 | -3.9 | -14.1 | +4.9 | -4.5 | -2.5 |

## Put trades (full universe)

- **C. B 90% + put sleeve 10%**: 27 puts, win rate 22%, avg R -0.10, total P&L $-454
- **D. B 80% + put sleeve 20%**: 41 puts, win rate 20%, avg R -0.20, total P&L $-2,915
- **E. options only: calls if SPY>50d, puts if below**: 110 puts, win rate 18%, avg R -0.22, total P&L $-20,268
- **F. puts only (SPY<50d), 100% of capital**: 87 puts, win rate 16%, avg R -0.20, total P&L $-11,863

## Limits

- Option prices are Black-Scholes from realized vol x 1.15: no IV crush, no skew. Puts are usually priced *above* this (skew), so put results are likely optimistic.
- One mostly-bullish period; large-cap tech picked with hindsight.
