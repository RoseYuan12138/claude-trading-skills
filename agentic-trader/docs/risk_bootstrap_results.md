# 10-Year Outcome Distribution (block bootstrap of 2000-2026)

5000 paths of 10 years built from 63-day blocks of 2000-2026 daily returns, with the same blocks for every strategy. Option strategies use the base pricing of `run_aggressive_research.py`.

| Strategy | CAGR p5 | p25 | median | p75 | p95 | Median max DD | p95 max DD | P(lose money) | P(DD > 50%) | P(DD > 70%) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| QQQ buy & hold | -4.6% | +3.3% | +8.8% | +14.1% | +21.8% | 50% | 73% | 13% | 48% | 8% |
| 2x QQQ, SPY and QQQ > 200d | -6.1% | +4.3% | +11.5% | +18.7% | +30.0% | 54% | 83% | 14% | 58% | 24% |
| 3x QQQ, SPY and QQQ > 200d | -13.4% | +2.1% | +13.2% | +24.3% | +42.6% | 71% | 95% | 21% | 90% | 52% |
| S3e LEAPS 270d, 30%, SPY and QQQ > 200d | -0.4% | +5.4% | +9.4% | +13.8% | +20.3% | 34% | 56% | 6% | 10% | 0% |
| S3f LEAPS 270d, 50%, SPY and QQQ > 200d | -2.2% | +7.3% | +14.0% | +21.4% | +32.6% | 50% | 75% | 8% | 50% | 10% |

Limits: the bootstrap reshuffles history; it cannot invent regimes that never happened, and quarter-long blocks understate multi-year bear markets like 2000-2002.
