# Entry Filter Comparison (shares, ATR 3x trailing stop)

- Universe: AAPL, AMD, AMZN, AVGO, GOOGL, INTC, META, MSFT, NVDA, TSLA; benchmark SPY (filter only, not traded)
- Period: 2021-09-01 to 2026-11-10; start equity $50,000
- Earnings dates: inferred from volume + gaps (~60% accurate)
- Subsets: 6 random draws of 8 stocks

| Variant | Return % (all) | Max DD % (all) | Sharpe (all) | Trades (all) | Median return % (subsets) | Median DD % | Median Sharpe | Subsets beating no-filter |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0. no filter (current rule) | +60.2 | 14.1 | 0.87 | 217 | +48.4 | 11.8 | 0.85 | – |
| 1. regime: SPY > 200d SMA | +51.8 | 13.7 | 0.80 | 202 | +42.2 | 11.6 | 0.78 | 0 / 6 (Sharpe) |
| 2. regime: SPY > 50d SMA | +57.8 | 10.6 | 0.86 | 207 | +52.3 | 9.6 | 0.90 | 6 / 6 (Sharpe) |
| 3. earnings blackout 7 days | +49.6 | 13.6 | 0.78 | 211 | +43.8 | 11.5 | 0.81 | 0 / 6 (Sharpe) |
| 4. breakout volume >= 1.5x | +47.2 | 8.1 | 0.96 | 124 | +36.6 | 7.1 | 0.92 | 4 / 6 (Sharpe) |
| 5. regime 200d + blackout | +42.5 | 13.2 | 0.71 | 196 | +39.1 | 11.3 | 0.76 | 0 / 6 (Sharpe) |
| 6. regime 200d + blackout + volume | +31.1 | 7.6 | 0.75 | 112 | +25.9 | 6.8 | 0.75 | 1 / 6 (Sharpe) |
| 7. regime 50d + volume (picked after seeing 2 and 4: in-sample) | +40.7 | 7.7 | 0.87 | 118 | +31.1 | 6.9 | 0.82 | 1 / 6 (Sharpe) |

## Return by year, full universe (%)

| Variant | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---:|---:|---:|---:|---:|---:|
| 0. no filter (current rule) | +8.9 | -6.9 | +19.2 | +16.3 | +9.4 | +4.2 |
| 1. regime: SPY > 200d SMA | +8.9 | -8.3 | +19.6 | +16.3 | +6.9 | +2.3 |
| 2. regime: SPY > 50d SMA | +5.7 | -5.9 | +20.5 | +17.3 | +9.7 | +2.2 |
| 3. earnings blackout 7 days | +9.5 | -6.8 | +19.6 | +13.6 | +5.0 | +2.7 |
| 4. breakout volume >= 1.5x | +8.0 | -3.7 | +16.2 | +9.7 | +5.7 | +5.0 |
| 5. regime 200d + blackout | +9.5 | -8.2 | +19.1 | +13.5 | +3.1 | +1.7 |
| 6. regime 200d + blackout + volume | +6.9 | -2.9 | +9.1 | +9.7 | +0.9 | +4.5 |
| 7. regime 50d + volume (picked after seeing 2 and 4: in-sample) | +6.5 | -3.1 | +12.7 | +8.0 | +6.7 | +5.1 |

## Limits

- One period (2021-2026) and large-cap tech chosen today: selection bias.
- Inferred earnings dates miss some reports and flag some non-earnings days.
- Daily bars, next-open fills, 5 bps slippage, no commissions or dividends.
