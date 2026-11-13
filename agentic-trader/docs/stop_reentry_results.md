# Index stop-and-re-entry study

Sell when the exit rule fires at a close, buy back when the re-entry rule fires; the position applies from the next day. Dividend-adjusted prices, cash earns ^IRX, 5 bps per switch. Cells: CAGR / max drawdown.

## QQQ

| Rule (exit -> re-entry) | Full: CAGR / DD | Sharpe | Invested | Trades/yr | 2000-2012 | 2013-2026 |
|---|---:|---:|---:|---:|---:|---:|
| **Buy & hold** | +8.4% / 83% | 0.43 | 100% | 0.0 | -2.4% / 83% | +19.2% / 35% |
| **200d SMA -> 200d SMA (current rule)** | +7.7% / 56% | 0.52 | 74% | 3.5 | -0.0% / 56% | +15.1% / 22% |
| *Top 8 by full-period Sharpe:* | | | | | | |
| drawdown 8% off the high -> sma 50d | +9.4% / 49% | 0.60 | 78% | 2.5 | +2.2% / 49% | +16.3% / 21% |
| sma 200d -> sma 50d | +9.2% / 61% | 0.59 | 75% | 9.7 | +0.5% / 61% | +17.8% / 21% |
| sma 50d -> sma 20d | +8.6% / 40% | 0.58 | 67% | 14.7 | +4.7% / 40% | +12.1% / 20% |
| sma 200d -> breakout 20d | +8.4% / 52% | 0.57 | 72% | 4.6 | +0.2% / 52% | +16.7% / 18% |
| drawdown 15% off the high -> breakout 20d | +9.6% / 58% | 0.56 | 89% | 0.9 | +1.6% / 58% | +17.3% / 35% |
| sma 200d -> breakout 50d | +7.9% / 53% | 0.56 | 68% | 2.3 | +0.9% / 53% | +15.0% / 19% |
| drawdown 20% off the high -> breakout 50d | +9.3% / 60% | 0.55 | 87% | 0.4 | +4.5% / 60% | +13.7% / 41% |
| drawdown 5% off the high -> sma 20d | +8.5% / 59% | 0.55 | 77% | 5.2 | +2.7% / 59% | +14.1% / 26% |
| *Bottom 3:* | | | | | | |
| atr 4 x ATR -> rebound 15% off the low | +0.5% / 69% | 0.11 | 45% | 1.8 | -5.6% / 69% | +7.1% / 25% |
| drawdown 10% off the high -> rebound 5% off the low | -1.2% / 90% | 0.06 | 90% | 3.2 | -11.7% / 90% | +9.2% / 48% |
| atr 3 x ATR -> rebound 5% off the low | -1.6% / 92% | 0.04 | 73% | 4.7 | -10.9% / 92% | +7.4% / 39% |

### QQQ: median across the grid, by rule family (full period)

| Exit family | Re-entry family | Median CAGR | Median DD | Median Sharpe | Beat B&H Sharpe | Beat B&H in both halves |
|---|---|---:|---:|---:|---:|---:|
| drawdown | rebound | +5.1% | 65% | 0.38 | 1/15 | 0/15 |
| drawdown | breakout | +6.2% | 58% | 0.46 | 10/15 | 1/15 |
| drawdown | sma | +8.0% | 58% | 0.53 | 13/15 | 3/15 |
| atr | rebound | +2.3% | 69% | 0.23 | 0/9 | 0/9 |
| atr | breakout | +4.5% | 65% | 0.34 | 1/9 | 0/9 |
| atr | sma | +6.0% | 69% | 0.38 | 4/9 | 0/9 |
| sma | rebound | +4.0% | 41% | 0.36 | 2/9 | 0/9 |
| sma | breakout | +6.4% | 45% | 0.48 | 6/9 | 3/9 |
| sma | sma | +7.0% | 49% | 0.50 | 7/9 | 3/9 |

All 99 combinations: median CAGR +5.9%, median max DD 58%, median Sharpe 0.42 (buy & hold +8.4% / 83% / 0.43).

## SPY

| Rule (exit -> re-entry) | Full: CAGR / DD | Sharpe | Invested | Trades/yr | 2000-2012 | 2013-2026 |
|---|---:|---:|---:|---:|---:|---:|
| **Buy & hold** | +8.2% / 55% | 0.51 | 100% | 0.0 | +1.7% / 55% | +14.5% / 34% |
| **200d SMA -> 200d SMA (current rule)** | +6.8% / 23% | 0.62 | 74% | 3.4 | +1.7% / 23% | +11.5% / 19% |
| *Top 8 by full-period Sharpe:* | | | | | | |
| drawdown 10% off the high -> rebound 15% off the low | +9.1% / 27% | 0.73 | 77% | 0.6 | +4.5% / 27% | +13.4% / 21% |
| drawdown 10% off the high -> rebound 10% off the low | +9.3% / 34% | 0.69 | 85% | 0.8 | +4.9% / 34% | +13.3% / 26% |
| drawdown 10% off the high -> breakout 50d | +8.2% / 35% | 0.68 | 81% | 0.6 | +4.7% / 35% | +11.3% / 21% |
| sma 200d -> breakout 50d | +6.5% / 24% | 0.65 | 68% | 2.2 | +2.3% / 24% | +10.7% / 15% |
| sma 200d -> sma 200d | +6.8% / 23% | 0.62 | 74% | 3.4 | +1.7% / 23% | +11.5% / 19% |
| drawdown 10% off the high -> sma 200d | +7.4% / 30% | 0.62 | 82% | 0.7 | +5.5% / 22% | +9.1% / 30% |
| sma 200d -> breakout 20d | +6.4% / 28% | 0.62 | 72% | 5.1 | +1.4% / 28% | +11.2% / 17% |
| drawdown 10% off the high -> breakout 20d | +8.0% / 49% | 0.61 | 89% | 0.9 | +2.1% / 49% | +13.7% / 19% |
| *Bottom 3:* | | | | | | |
| sma 50d -> rebound 5% off the low | +1.0% / 38% | 0.15 | 53% | 5.9 | -0.4% / 38% | +2.4% / 33% |
| drawdown 5% off the high -> rebound 15% off the low | +0.8% / 38% | 0.13 | 36% | 1.5 | -1.3% / 27% | +3.2% / 21% |
| drawdown 5% off the high -> rebound 5% off the low | +0.5% / 57% | 0.11 | 79% | 3.8 | -5.0% / 57% | +5.7% / 41% |

### SPY: median across the grid, by rule family (full period)

| Exit family | Re-entry family | Median CAGR | Median DD | Median Sharpe | Beat B&H Sharpe | Beat B&H in both halves |
|---|---|---:|---:|---:|---:|---:|
| drawdown | rebound | +6.8% | 50% | 0.48 | 6/15 | 3/15 |
| drawdown | breakout | +6.8% | 48% | 0.51 | 9/15 | 2/15 |
| drawdown | sma | +6.7% | 46% | 0.50 | 7/15 | 3/15 |
| atr | rebound | +2.9% | 40% | 0.28 | 0/9 | 0/9 |
| atr | breakout | +4.2% | 42% | 0.39 | 1/9 | 0/9 |
| atr | sma | +5.7% | 45% | 0.45 | 3/9 | 0/9 |
| sma | rebound | +2.8% | 20% | 0.39 | 2/9 | 0/9 |
| sma | breakout | +4.4% | 33% | 0.46 | 4/9 | 1/9 |
| sma | sma | +4.4% | 34% | 0.43 | 3/9 | 1/9 |

All 99 combinations: median CAGR +5.4%, median max DD 41%, median Sharpe 0.46 (buy & hold +8.2% / 55% / 0.51).

## IWM

| Rule (exit -> re-entry) | Full: CAGR / DD | Sharpe | Invested | Trades/yr | 2000-2012 | 2013-2026 |
|---|---:|---:|---:|---:|---:|---:|
| **Buy & hold** | +8.4% / 59% | 0.46 | 100% | 0.0 | +6.0% / 59% | +10.2% / 41% |
| **200d SMA -> 200d SMA (current rule)** | +4.6% / 27% | 0.37 | 69% | 4.6 | +2.4% / 27% | +6.2% / 27% |
| *Top 8 by full-period Sharpe:* | | | | | | |
| atr 5 x ATR -> sma 20d | +9.4% / 56% | 0.54 | 89% | 1.9 | +7.2% / 56% | +11.1% / 42% |
| drawdown 15% off the high -> rebound 15% off the low | +8.5% / 46% | 0.52 | 85% | 0.6 | +6.7% / 46% | +9.9% / 33% |
| atr 5 x ATR -> breakout 50d | +6.9% / 29% | 0.52 | 64% | 1.4 | +4.7% / 29% | +8.6% / 24% |
| atr 5 x ATR -> breakout 10d | +8.6% / 58% | 0.51 | 88% | 1.9 | +6.3% / 58% | +10.4% / 40% |
| atr 5 x ATR -> rebound 5% off the low | +8.8% / 60% | 0.50 | 88% | 1.9 | +6.6% / 60% | +10.5% / 38% |
| atr 5 x ATR -> sma 50d | +7.6% / 53% | 0.50 | 79% | 1.8 | +5.1% / 53% | +9.4% / 33% |
| atr 5 x ATR -> rebound 15% off the low | +6.9% / 38% | 0.49 | 56% | 1.2 | +4.6% / 38% | +9.1% / 22% |
| drawdown 15% off the high -> breakout 20d | +8.0% / 41% | 0.49 | 91% | 0.7 | +7.4% / 36% | +8.2% / 41% |
| *Bottom 3:* | | | | | | |
| sma 50d -> rebound 5% off the low | +1.6% / 45% | 0.18 | 53% | 7.2 | +3.8% / 42% | -0.4% / 41% |
| drawdown 8% off the high -> rebound 10% off the low | +1.3% / 49% | 0.16 | 67% | 2.4 | -0.5% / 49% | +2.6% / 42% |
| drawdown 8% off the high -> rebound 15% off the low | +0.6% / 40% | 0.11 | 50% | 1.7 | +1.8% / 32% | -0.3% / 40% |

### IWM: median across the grid, by rule family (full period)

| Exit family | Re-entry family | Median CAGR | Median DD | Median Sharpe | Beat B&H Sharpe | Beat B&H in both halves |
|---|---|---:|---:|---:|---:|---:|
| drawdown | rebound | +6.0% | 48% | 0.39 | 3/15 | 1/15 |
| drawdown | breakout | +6.2% | 40% | 0.41 | 4/15 | 0/15 |
| drawdown | sma | +6.3% | 45% | 0.43 | 4/15 | 0/15 |
| atr | rebound | +5.1% | 50% | 0.36 | 3/9 | 1/9 |
| atr | breakout | +5.6% | 42% | 0.44 | 3/9 | 2/9 |
| atr | sma | +5.9% | 44% | 0.43 | 3/9 | 3/9 |
| sma | rebound | +2.2% | 36% | 0.24 | 0/9 | 0/9 |
| sma | breakout | +4.2% | 35% | 0.37 | 0/9 | 0/9 |
| sma | sma | +3.9% | 40% | 0.32 | 0/9 | 0/9 |

All 99 combinations: median CAGR +5.2%, median max DD 41%, median Sharpe 0.39 (buy & hold +8.4% / 59% / 0.46).

## Sensitivity: drawdown stop level x re-entry rule (full period, CAGR % / max DD %)

| SPY re-entry \ stop | 6% | 8% | 10% | 12% | 15% | 20% |
|---|---:|---:|---:|---:|---:|---:|
| rebound 10% off the low | +4.6/33 | +6.8/40 | **+9.3/34** | +8.2/42 | +7.2/51 | +7.9/50 |
| rebound 15% off the low | +3.3/20 | +6.2/28 | **+9.1/27** | +7.4/38 | +6.4/47 | +6.9/55 |
| rebound 20% off the low | +4.6/19 | +6.0/23 | +8.2/30 | +6.9/38 | +6.6/46 | +8.0/49 |
| sma 50d | +4.8/55 | +5.3/53 | +7.7/46 | +6.6/50 | +6.7/54 | +6.5/55 |
| breakout 50d | +4.4/34 | +6.0/39 | +8.2/35 | +7.7/37 | +6.6/44 | +7.6/55 |

| QQQ re-entry \ stop | 6% | 8% | 10% | 12% | 15% | 20% |
|---|---:|---:|---:|---:|---:|---:|
| rebound 10% off the low | +2.7/66 | +6.0/57 | +6.4/55 | +9.2/59 | +8.3/64 | +7.1/79 |
| rebound 15% off the low | +2.8/49 | +4.7/52 | +5.1/48 | +7.6/47 | +6.9/59 | +6.6/74 |
| rebound 20% off the low | +5.0/22 | +4.5/32 | +4.4/35 | +7.5/36 | +7.1/47 | +9.0/59 |
| sma 50d | +8.7/44 | +9.4/49 | +6.7/58 | +8.9/65 | +9.2/63 | +7.2/79 |
| breakout 50d | +5.5/35 | +6.0/47 | +4.4/54 | +8.4/48 | +8.4/50 | +9.3/60 |

Buy & hold: SPY +8.2% / 55%, QQQ +8.4% / 83%. The SPY 10% stop is a local peak (8% and 12%
are clearly worse), so the best cell is likely partly luck.
