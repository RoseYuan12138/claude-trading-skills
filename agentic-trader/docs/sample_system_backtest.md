# Full System Backtest

- Universe: AAPL, AMD, AMZN, AVGO, GOOGL, INTC, META, MSFT, NVDA, TSLA (+QQQ for the bear sleeve); regime SPY vs 50d SMA
- Period: 2021-09-01 to 2026-11-10; $1,000,000 so contract sizes never bind
- Earnings dates: inferred from volume + gaps (~60% accurate)

| Variant | Return % | CAGR % | Max DD % | Sharpe | Entries / month | Oct 6 - Nov 10 2026 % | Median Sharpe (6 subsets) | Median DD % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1. shares, no regime filter, no agent | +61.4 | +9.7 | 14.2 | 0.87 | 3.5 | -5.2 | 0.84 | 11.9 |
| 2. shares + SPY 50d filter | +58.7 | +9.3 | 10.7 | 0.86 | 3.3 | -4.9 | 0.90 | 9.7 |
| 3. shares + filter + agent | +49.7 | +8.1 | 10.2 | 0.81 | 3.7 | -4.3 | 0.82 | 10.0 |
| 4. FULL: 80% (3) + 20% bear sleeve | +27.2 | +4.8 | 11.4 | 0.54 | 5.2 | -4.0 | 0.51 | 12.1 |
| 5. bear sleeve alone (2%/trade) | -32.0 | -7.2 | 33.1 | -0.86 | 1.5 | +0.0 | -0.86 | 31.5 |
| 5a. bear: earnings gaps only | -3.7 | -0.7 | 6.2 | -0.65 | 0.1 | +0.0 | -0.51 | 5.2 |
| 5b. bear: failed rallies only | -29.2 | -6.5 | 30.1 | -0.76 | 1.5 | +0.0 | -0.77 | 29.4 |
| SPY buy & hold | +66.0 | +10.3 | 25.4 | 0.66 | – | -3.7 | 0.66 | 25.4 |

## Return by year (%)

| Variant | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---:|---:|---:|---:|---:|---:|
| 1. shares, no regime filter, no agent | +9.1 | -7.1 | +19.4 | +16.7 | +9.7 | +4.2 |
| 2. shares + SPY 50d filter | +5.6 | -6.0 | +20.7 | +17.7 | +10.2 | +2.0 |
| 3. shares + filter + agent | +4.5 | -6.3 | +19.0 | +11.3 | +13.2 | +2.0 |
| 4. FULL: 80% (3) + 20% bear sleeve | -0.9 | -6.0 | +11.6 | +7.8 | +12.2 | +1.1 |
| 5. bear sleeve alone (2%/trade) | -9.4 | -1.3 | -11.9 | -9.8 | +0.6 | -4.9 |
| 5a. bear: earnings gaps only | -1.7 | -0.3 | +0.0 | -3.8 | +2.0 | +0.0 |
| 5b. bear: failed rallies only | -7.9 | -1.1 | -13.0 | -6.3 | +0.5 | -5.2 |
| SPY buy & hold | +5.1 | -19.5 | +24.3 | +23.3 | +16.4 | +10.0 |

## Bear sleeve trades (full universe)

- **4. FULL: 80% (3) + 20% bear sleeve**: 96 closed, win 25%, avg R -0.22; exits stop_loss 51, trailing_stop 20, time_stop 19, underlying_stop 6
- **5. bear sleeve alone (2%/trade)**: 95 closed, win 24%, avg R -0.22; exits stop_loss 51, trailing_stop 20, time_stop 18, underlying_stop 6
- **5a. bear: earnings gaps only**: 7 closed, win 14%, avg R -0.29; exits stop_loss 3, time_stop 2, trailing_stop 1, underlying_stop 1
- **5b. bear: failed rallies only**: 91 closed, win 25%, avg R -0.20; exits stop_loss 49, trailing_stop 20, time_stop 17, underlying_stop 5

Agent wake-ups (variant 3): 133 (2.1 per month).

## Limits

- The agent is the rule proxy, not Claude. Option prices are Black-Scholes from realized vol x 1.15 (no IV crush, no skew). Earnings dates are inferred.
- One mostly-bullish period; large-cap tech chosen with hindsight; daily bars.
