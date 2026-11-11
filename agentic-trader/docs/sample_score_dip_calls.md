# Buy QQQ Calls When the Market Score Is Low

Rule fixed before the out-of-sample run: score < 30 and flat -> buy an ATM 45-DTE QQQ call risking 2% of equity; -50% stop, trailing after +50%, 5-DTE time stop. Priced with the actual VXN unless noted. One position at a time.

## out-of-sample 2011-2021 (2011-01-03 to 2021-08-31)

QQQ buy & hold: +587% (CAGR +19.8%, max DD 29%, Sharpe 1.02)

| Variant | Return % | CAGR % | Max DD % | Sharpe | Trades | Win % | Avg R | Best R | Time in market % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1. score < 30, 2%/trade [pre-registered] | +14 | +1.3 | 6 | 0.52 | 27 | 44 | +0.34 | +2.34 | 19 |
| 2. score < 20, 2%/trade | +16 | +1.4 | 3 | 0.72 | 15 | 60 | +0.68 | +3.15 | 11 |
| 3. score < 40, 2%/trade | +9 | +0.8 | 6 | 0.32 | 33 | 39 | +0.17 | +2.17 | 24 |
| 4. score < 30, 5%/trade | +38 | +3.1 | 14 | 0.52 | 27 | 44 | +0.34 | +2.34 | 19 |
| 5. score < 30, 2%/trade, no stop | +5 | +0.5 | 6 | 0.21 | 17 | 47 | +0.18 | +2.34 | 19 |
| 6. score < 30, 2%, old pricing (realized vol x1.15) | +16 | +1.4 | 5 | 0.48 | 27 | 48 | +0.48 | +5.26 | 19 |
| C1. control: buy calls any day (always on), 2% | +18 | +1.6 | 8 | 0.34 | 126 | 41 | +0.09 | +2.52 | 93 |
| C2. control: buy calls only when score > 70, 2% | +10 | +0.9 | 8 | 0.22 | 94 | 40 | +0.06 | +2.14 | 74 |

## in-sample 2021-2026 (2021-09-01 to 2026-11-10)

QQQ buy & hold: +77% (CAGR +11.7%, max DD 36%, Sharpe 0.60)

| Variant | Return % | CAGR % | Max DD % | Sharpe | Trades | Win % | Avg R | Best R | Time in market % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1. score < 30, 2%/trade [pre-registered] | +6 | +1.2 | 7 | 0.41 | 19 | 37 | +0.27 | +4.53 | 24 |
| 2. score < 20, 2%/trade | -3 | -0.5 | 9 | -0.21 | 14 | 29 | -0.12 | +2.84 | 13 |
| 3. score < 40, 2%/trade | +11 | +2.0 | 12 | 0.55 | 28 | 36 | +0.27 | +4.53 | 36 |
| 4. score < 30, 5%/trade | +16 | +2.9 | 17 | 0.41 | 19 | 37 | +0.27 | +4.53 | 24 |
| 5. score < 30, 2%/trade, no stop | -3 | -0.6 | 9 | -0.22 | 10 | 30 | -0.17 | +2.46 | 23 |
| 6. score < 30, 2%, old pricing (realized vol x1.15) | +3 | +0.6 | 8 | 0.19 | 20 | 35 | +0.15 | +4.93 | 23 |
| C1. control: buy calls any day (always on), 2% | +1 | +0.1 | 15 | 0.05 | 71 | 38 | +0.04 | +4.53 | 92 |
| C2. control: buy calls only when score > 70, 2% | +4 | +0.8 | 7 | 0.20 | 46 | 33 | +0.06 | +3.94 | 62 |

## Limits

- VXN is an index-level 30-day implied vol; QQQ ATM 45-DTE options trade close to it, but skew, term structure and bid-ask are approximated (2.5% of price per fill).
- Low-score days cluster into a handful of selloffs per decade, so trade counts are small: treat differences of a few trades as noise.
- The breadth component uses today's large-cap tech names (survivorship).
