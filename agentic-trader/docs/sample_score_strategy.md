# Market Score -> Call/Put Tiers

Score = equal-weight mean of trend (SPY vs 50d/200d), breadth (% of stocks above 50d), 20d momentum, distance from 1y high, VIX and HYG vs its 50d. Weights and tiers were fixed before testing.

**Score on 2026-11-10: 42.8** (trend 50, breadth 40, momentum 14, drawdown 75, volatility 78, credit 0)

## 1. Does the score predict QQQ over the next 20 trading days?

| Score band | Days | Median 20d % | Mean 20d % | Up % | Dropped >= 5% at some point % |
|---|---:|---:|---:|---:|---:|
| < 30 | 180 | +2.9 | +2.7 | 61 | 58 |
| 30-50 | 164 | +3.4 | +2.1 | 68 | 35 |
| 50-70 | 184 | +0.4 | -0.2 | 52 | 44 |
| >= 70 | 756 | +1.5 | +0.9 | 63 | 27 |

## 2. Strategies

Tiers: >= 70 calls 5%/trade (cap 15%); 50-70 calls 2% (cap 10%); 30-50 no new trades; < 30 puts 2% (cap 6%). Exits: -50% premium stop, trailing after +50%, 5 DTE time stop.

| Variant | Return % | CAGR % | Max DD % | Sharpe | 2022 % | Oct 6-Nov 2026 % | Median return (subsets) | Median DD | Subsets < 0 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A. fixed: calls 2%/trade (cap 10%), SPY>50d | +31 | +5.4 | 33 | 0.34 | -15 | -7.1 | +32 | 26 | 0/6 |
| B. fixed: calls 5%/trade (cap 10%), SPY>50d | +86 | +12.8 | 42 | 0.52 | -14 | -7.4 | +95 | 33 | 0/6 |
| C. fixed: calls/puts 2% by SPY 50d | -15 | -3.2 | 55 | 0.02 | -22 | +13.2 | -11 | 46 | 4/6 |
| D. SCORE tiers (calls 5%/2%, cash, puts 2%) | +12 | +2.3 | 50 | 0.24 | -28 | -10.3 | +12 | 52 | 3/6 |
| E. SCORE tiers, no puts | +24 | +4.3 | 45 | 0.29 | -24 | -9.6 | +29 | 45 | 1/6 |
| F. D with thresholds -10 | +35 | +6.0 | 46 | 0.34 | -22 | -13.8 | +40 | 47 | 1/6 |
| G. D with thresholds +10 | -15 | -3.2 | 52 | 0.08 | -21 | -6.1 | -5 | 49 | 3/6 |
| H. D, IV = realized vol | +82 | +12.2 | 48 | 0.48 | -23 | -11.8 | +23 | 52 | 2/6 |
| I. D, IV = 1.4x realized | -46 | -11.1 | 68 | -0.22 | -32 | -8.9 | -35 | 62 | 6/6 |

## Limits

- Option prices: Black-Scholes from realized vol x 1.15 (rows H/I vary it); no IV crush or skew. One mostly-bullish period; stocks chosen with hindsight.
- The score is equal-weighted by design; a fitted score would look better in-sample and worse out of sample.
