# Aggressive Longs + Index Put Hedge

- Universe: AAPL, AMD, AMZN, AVGO, GOOGL, INTC, META, MSFT, NVDA, TSLA; regime SPY vs 50d SMA; hedge on QQQ
- Period: 2021-09-01 to 2026-11-10; $1,000,000
- Aggressive = 1.25% risk per trade, 10 positions, 25% per position, 4 entries/day
- Hedge: ATM 45-DTE QQQ put while SPY < 50d SMA; exit when SPY closes back above, at 5 DTE (re-buy if still bearish), or trailing 40% after +100%

| Variant | Return % | CAGR % | Max DD % | Sharpe | 2022 bear % | Feb-Apr 2025 % | Oct 6-Nov 2026 % | Median Sharpe (subsets) | Median DD % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A. normal longs + SPY 50d filter | +58.7 | +9.3 | 10.7 | 0.86 | -6.0 | -0.9 | -4.9 | 0.90 | 9.7 |
| B. aggressive longs + filter | +92.0 | +13.4 | 15.9 | 0.88 | -9.8 | -1.5 | -6.6 | 0.87 | 14.7 |
| C. B (90%) + QQQ put hedge, 1% premium | +80.8 | +12.1 | 15.5 | 0.83 | -9.3 | -1.0 | -6.5 | 0.82 | 14.1 |
| D. B (90%) + QQQ put hedge, 2% premium | +78.2 | +11.8 | 16.3 | 0.80 | -9.8 | -1.0 | -6.5 | 0.78 | 14.7 |
| E. B (90%) + QQQ put spread hedge, 1% premium | +81.2 | +12.2 | 15.5 | 0.84 | -8.6 | -1.2 | -6.5 | 0.83 | 13.7 |
| SPY buy & hold | +66.0 | +10.3 | 25.4 | 0.66 | -19.5 | -9.5 | -3.7 | 0.66 | 25.4 |
| QQQ buy & hold | +77.3 | +11.7 | 35.6 | 0.60 | -33.1 | -11.9 | -11.2 | 0.60 | 35.6 |

## Hedge trades

- **C. B (90%) + QQQ put hedge, 1% premium**: 57 puts (11.0/yr), won 12, total P&L $-50,367 (-5.0% of start equity)
- **D. B (90%) + QQQ put hedge, 2% premium**: 56 puts (10.8/yr), won 12, total P&L $-76,480 (-7.6% of start equity)
- **E. B (90%) + QQQ put spread hedge, 1% premium**: 54 puts (10.4/yr), won 9, total P&L $-45,784 (-4.6% of start equity)

## Limits

- QQQ option prices are Black-Scholes from realized vol x 1.15; real index puts carry skew (usually pricier), so hedge costs are likely understated.
- One period, mostly bullish; large-cap tech chosen with hindsight.
