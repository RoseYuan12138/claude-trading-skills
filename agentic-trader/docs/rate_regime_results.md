# Rate-regime switching: wheel vs buy & hold

Regime = change in the 3-month T-bill over the lookback: 'hike' >= +threshold, 'cut' <= -threshold, else 'flat'. Wheel = 0.30-delta cash-secured puts / covered calls, model-priced at VIX/VXN x 0.85. Cells: CAGR / max DD / Sharpe.

## SPY (2000-2026)

### What each strategy earned in each regime (6-month lookback, 0.25 pt)

| Regime | Share of days | Buy & hold | Wheel | Cash |
|---|---:|---:|---:|---:|
| hike | 28% | +4.8%/yr | +6.5%/yr | +3.2%/yr |
| flat | 49% | +14.9%/yr | +10.6%/yr | +1.1%/yr |
| cut | 23% | -1.2%/yr | +2.4%/yr | +2.3%/yr |

### Switching rules (6-month lookback, 0.25 pt), by period

| Rule | 2000/01-2026 | 2000/01-2012 | 2013-2026 |
|---|---:|---:|---:|
| Always buy & hold | +8.2% / 55% / 0.51 | +1.7% / 55% / 0.18 | +14.5% / 34% / 0.89 |
| Always wheel | +7.5% / 40% / 0.60 | +5.5% / 40% / 0.42 | +9.5% / 29% / 0.82 |
| Your rule: hike -> wheel, cut/flat -> hold | +8.5% / 55% / 0.54 | +3.0% / 55% / 0.25 | +13.8% / 34% / 0.91 |
| Reverse: hike -> hold, cut -> wheel | +9.0% / 44% / 0.58 | +3.6% / 44% / 0.28 | +14.0% / 29% / 0.92 |
| Hike -> wheel, cut -> cash, flat -> hold | +9.3% / 30% / 0.76 | +6.1% / 30% / 0.49 | +12.1% / 21% / 1.06 |
| Hike -> hold, cut -> cash, flat -> hold | +8.9% / 34% / 0.68 | +4.7% / 34% / 0.38 | +12.9% / 24% / 1.00 |

### Your rule across regime definitions (full period)

| Lookback | Threshold | Your rule | Always hold | Always wheel |
|---:|---:|---:|---:|---:|
| 63d | 0.25 pt | +9.0% / 53% | +8.2% / 55% | +7.5% / 40% |
| 63d | 0.5 pt | +8.3% / 55% | +8.2% / 55% | +7.5% / 40% |
| 126d | 0.25 pt | +8.5% / 55% | +8.2% / 55% | +7.5% / 40% |
| 126d | 0.5 pt | +8.5% / 55% | +8.2% / 55% | +7.5% / 40% |
| 252d | 0.25 pt | +7.8% / 55% | +8.2% / 55% | +7.4% / 40% |
| 252d | 0.5 pt | +8.0% / 55% | +8.2% / 55% | +7.4% / 40% |

## QQQ (2001-2026)

### What each strategy earned in each regime (6-month lookback, 0.25 pt)

| Regime | Share of days | Buy & hold | Wheel | Cash |
|---|---:|---:|---:|---:|
| hike | 25% | +8.0%/yr | +5.6%/yr | +2.8%/yr |
| flat | 51% | +17.8%/yr | +13.2%/yr | +1.1%/yr |
| cut | 24% | -2.1%/yr | +1.0%/yr | +2.3%/yr |

### Switching rules (6-month lookback, 0.25 pt), by period

| Rule | 2000/01-2026 | 2000/01-2012 | 2013-2026 |
|---|---:|---:|---:|
| Always buy & hold | +10.3% / 69% / 0.53 | +0.5% / 69% / 0.16 | +19.2% / 35% / 0.95 |
| Always wheel | +8.3% / 46% / 0.57 | +5.4% / 46% / 0.38 | +10.7% / 25% / 0.80 |
| Your rule: hike -> wheel, cut/flat -> hold | +9.6% / 69% / 0.51 | +1.1% / 69% / 0.18 | +17.1% / 31% / 0.93 |
| Reverse: hike -> hold, cut -> wheel | +11.0% / 54% / 0.60 | +4.6% / 54% / 0.31 | +16.5% / 35% / 0.88 |
| Hike -> wheel, cut -> cash, flat -> hold | +10.6% / 39% / 0.71 | +7.4% / 39% / 0.51 | +13.1% / 31% / 0.90 |
| Hike -> hold, cut -> cash, flat -> hold | +11.3% / 39% / 0.70 | +6.7% / 39% / 0.46 | +15.2% / 35% / 0.90 |

### Your rule across regime definitions (full period)

| Lookback | Threshold | Your rule | Always hold | Always wheel |
|---:|---:|---:|---:|---:|
| 63d | 0.25 pt | +10.5% / 69% | +10.3% / 69% | +8.3% / 46% |
| 63d | 0.5 pt | +10.6% / 69% | +10.3% / 69% | +8.3% / 46% |
| 126d | 0.25 pt | +9.6% / 69% | +10.3% / 69% | +8.3% / 46% |
| 126d | 0.5 pt | +9.9% / 69% | +10.3% / 69% | +8.3% / 46% |
| 252d | 0.25 pt | +8.9% / 69% | +10.3% / 69% | +8.3% / 46% |
| 252d | 0.5 pt | +9.0% / 69% | +10.3% / 69% | +8.3% / 46% |

## Regime episodes (6-month lookback, 0.25 pt; short blips omitted)

- hike: 2000 H1-H2, 2004-06 to 2006-09, 2017-03 to 2019-03 (with gaps from 2015-12), 2022-03 to 2023-10, 2026-09 to now
- cut: 2001-01 to 2003 (dot-com bust), 2007-08 to 2009-05 (financial crisis), 2019-07 to 2020-09 (COVID), 2024-09 to 2026-04
- flat: 2009-05 to 2015-12, 2020-09 to 2022-02, most of 2023-11 to 2024-08

Caveats: only 3-4 cutting cycles, and three of them were recessions, so "cut -> cash" mostly
means "out of the market in 2001-02, 2008 and 2020". Switching assumes the wheel can be
exited at its model mark on any close.
