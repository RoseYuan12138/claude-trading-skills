# High-volume selloff study (2000-2026)

Capitulation day: return <= -2 x the 20-day return stdev and <= -3%, volume >= 2 x the 50-day average (base). Entry at the next open. Baseline = the same forward return from every day in the same stocks.

## A. Forward returns after the signal vs any day

### Index ETFs (SPY, QQQ, IWM)

| Signal | Events (months) | 5d mean / win | 20d mean / win | 60d mean / win | 20d worst 10% | 20d edge vs any day |
|---|---:|---:|---:|---:|---:|---:|
| Big drop only (no volume filter) | 236 (97) | +0.2% / 55% | +0.0% / 54% | +3.4% / 64% | -12.5% | -0.7% |
| Big drop + volume >= 2x (base) | 86 (31) | +0.0% / 60% | +0.0% / 56% | +5.5% / 74% | -15.3% | -0.7% |
| Big drop + volume >= 3x | 27 (13) | +1.9% / 70% | -0.3% / 58% | +5.7% / 81% | -15.3% | -1.0% |
| Base, only in an uptrend (above 200d) | 52 (23) | +0.8% / 65% | +0.1% / 58% | +2.7% / 71% | -9.5% | -0.6% |
| Base, only in a downtrend (below 200d) | 33 (12) | -1.3% / 52% | -0.3% / 52% | +9.3% / 79% | -16.4% | -1.1% |
| *Any day (baseline)* | 19405 | +0.2% / 56% | +0.7% / 62% | +2.4% / 67% | -5.8% | - |

### Mega-cap survivors (AAPL, MSFT, NVDA, AMZN, GOOGL, META, AVGO, TSLA, AMD)

| Signal | Events (months) | 5d mean / win | 20d mean / win | 60d mean / win | 20d worst 10% | 20d edge vs any day |
|---|---:|---:|---:|---:|---:|---:|
| Big drop only (no volume filter) | 1390 (291) | +0.5% / 54% | +2.2% / 57% | +8.3% / 63% | -13.3% | -0.2% |
| Big drop + volume >= 2x (base) | 458 (205) | +0.7% / 52% | +2.4% / 57% | +8.6% / 64% | -12.4% | -0.0% |
| Big drop + volume >= 3x | 178 (123) | +0.2% / 45% | +1.8% / 53% | +6.6% / 56% | -12.7% | -0.6% |
| Base, only in an uptrend (above 200d) | 300 (156) | +0.8% / 52% | +1.8% / 55% | +8.4% / 65% | -9.5% | -0.6% |
| Base, only in a downtrend (below 200d) | 149 (91) | +0.9% / 52% | +4.5% / 62% | +10.3% / 64% | -17.4% | +2.0% |
| *Any day (baseline)* | 49193 | +0.5% / 54% | +2.5% / 59% | +7.8% / 64% | -11.1% | - |

### Laggards / fallen (INTC, CSCO, IBM, GE, C, BA, PFE, T, F)

| Signal | Events (months) | 5d mean / win | 20d mean / win | 60d mean / win | 20d worst 10% | 20d edge vs any day |
|---|---:|---:|---:|---:|---:|---:|
| Big drop only (no volume filter) | 1348 (287) | +0.0% / 50% | +0.3% / 51% | +2.2% / 54% | -12.5% | -0.1% |
| Big drop + volume >= 2x (base) | 522 (221) | -0.0% / 48% | +0.7% / 49% | +2.3% / 56% | -10.5% | +0.2% |
| Big drop + volume >= 3x | 218 (143) | -0.2% / 44% | +1.0% / 48% | +2.2% / 53% | -10.2% | +0.6% |
| Base, only in an uptrend (above 200d) | 219 (131) | -0.2% / 46% | +0.4% / 48% | +2.7% / 57% | -8.1% | -0.1% |
| Base, only in a downtrend (below 200d) | 297 (144) | +0.1% / 49% | +1.0% / 49% | +2.1% / 55% | -13.2% | +0.5% |
| *Any day (baseline)* | 58518 | +0.1% / 51% | +0.4% / 52% | +1.4% / 54% | -9.4% | - |

### Robustness: base signal by period, 20-day forward return

| Group | 2000-2012 signal / any day | 2013-2026 signal / any day |
|---|---:|---:|
| Index ETFs | -1.8% (n=24) / +0.3% | +0.8% (n=58) / +1.1% |
| Mega-cap survivors | -0.6% (n=181) / +1.7% | +4.5% (n=269) / +2.9% |
| Laggards / fallen | +0.6% (n=225) / +0.1% | +0.8% (n=291) / +0.8% |

## B. Trades: buy at the next open, hold 20 days, with / without a stop

One trade per stock at a time; 5 bps per side. 'Every 20th day' applies the same rules to entries that ignore the signal.

### Index ETFs

| Entries | Exit | Trades | Mean | Win rate | Avg win | Avg loss | Worst | Stopped | Profit factor |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Base signal | no stop | 51 | -1.5% | 53% | +5.2% | -9.1% | -31.2% | 0% | 0.64 |
| Base signal | stop 2.5 ATR | 57 | -1.7% | 33% | +5.9% | -5.5% | -13.4% | 61% | 0.54 |
| Base signal | stop 1.5 ATR | 61 | -1.3% | 23% | +6.1% | -3.6% | -8.4% | 77% | 0.51 |
| Signal in uptrend | no stop | 35 | -0.3% | 60% | +5.0% | -8.3% | -31.2% | 0% | 0.90 |
| Signal in uptrend | stop 2.5 ATR | 37 | -1.0% | 38% | +5.2% | -4.7% | -9.5% | 59% | 0.66 |
| Signal in uptrend | stop 1.5 ATR | 38 | -1.1% | 24% | +5.7% | -3.2% | -8.4% | 76% | 0.56 |
| Every 20th day | no stop | 486 | +0.5% | 58% | +4.0% | -4.3% | -30.7% | 0% | 1.29 |
| Every 20th day | stop 2.5 ATR | 600 | +0.3% | 48% | +4.6% | -3.8% | -16.8% | 39% | 1.15 |
| Every 20th day | stop 1.5 ATR | 678 | +0.0% | 37% | +4.8% | -2.7% | -12.4% | 57% | 1.02 |

### Mega-cap survivors

| Entries | Exit | Trades | Mean | Win rate | Avg win | Avg loss | Worst | Stopped | Profit factor |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Base signal | no stop | 373 | +1.8% | 56% | +9.8% | -8.5% | -63.1% | 0% | 1.48 |
| Base signal | stop 2.5 ATR | 383 | +0.8% | 50% | +10.4% | -8.6% | -46.6% | 34% | 1.20 |
| Base signal | stop 1.5 ATR | 395 | +0.5% | 41% | +10.8% | -6.5% | -46.6% | 54% | 1.14 |
| Signal in uptrend | no stop | 254 | +1.4% | 53% | +8.4% | -6.6% | -24.2% | 0% | 1.46 |
| Signal in uptrend | stop 2.5 ATR | 261 | +0.4% | 46% | +9.0% | -7.1% | -26.4% | 37% | 1.09 |
| Signal in uptrend | stop 1.5 ATR | 268 | +0.4% | 38% | +9.7% | -5.4% | -16.8% | 57% | 1.11 |
| Every 20th day | no stop | 1233 | +1.8% | 56% | +9.6% | -8.1% | -43.0% | 0% | 1.52 |
| Every 20th day | stop 2.5 ATR | 1480 | +2.1% | 52% | +11.0% | -7.3% | -36.1% | 35% | 1.61 |
| Every 20th day | stop 1.5 ATR | 1680 | +1.6% | 41% | +11.5% | -5.4% | -31.0% | 55% | 1.50 |

### Laggards / fallen

| Entries | Exit | Trades | Mean | Win rate | Avg win | Avg loss | Worst | Stopped | Profit factor |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Base signal | no stop | 402 | -0.2% | 45% | +7.5% | -6.4% | -51.5% | 0% | 0.94 |
| Base signal | stop 2.5 ATR | 426 | -0.5% | 40% | +8.4% | -6.5% | -26.2% | 38% | 0.86 |
| Base signal | stop 1.5 ATR | 437 | -1.0% | 29% | +9.1% | -5.1% | -36.9% | 63% | 0.73 |
| Signal in uptrend | no stop | 196 | +0.1% | 46% | +6.3% | -5.2% | -42.0% | 0% | 1.03 |
| Signal in uptrend | stop 2.5 ATR | 198 | -0.4% | 41% | +6.6% | -5.3% | -14.8% | 37% | 0.86 |
| Signal in uptrend | stop 1.5 ATR | 200 | -0.7% | 30% | +7.2% | -4.0% | -12.2% | 62% | 0.76 |
| Every 20th day | no stop | 1467 | +0.1% | 50% | +6.4% | -6.4% | -52.5% | 0% | 1.03 |
| Every 20th day | stop 2.5 ATR | 1807 | +0.0% | 45% | +6.9% | -5.6% | -44.6% | 39% | 1.01 |
| Every 20th day | stop 1.5 ATR | 2056 | +0.1% | 36% | +7.6% | -4.1% | -26.8% | 59% | 1.04 |

