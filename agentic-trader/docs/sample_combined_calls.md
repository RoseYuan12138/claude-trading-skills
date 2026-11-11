# Combined: Breakout Calls (Bull Regime) + QQQ Dip Calls (Low Score)

- One account and one premium budget; exits for both: -50% premium stop, trailing after +50%, 5-DTE time stop
- QQQ options priced off the actual VXN; single-stock options off 20d realized vol x1.15
- **The 10-stock universe is today's winners, so the 2011-2021 stock rows carry heavy survivorship bias; the QQQ-only rows (F, G) do not.**

## out-of-sample 2011-2021 (2011-01-03 to 2021-08-31)

Buy & hold: QQQ +587% (CAGR +19.8%, DD 29%, Sharpe 1.02); SPY +255% (CAGR +12.6%, DD 34%)

| Variant | Return % | CAGR % | Max DD % | Sharpe | Trades | Dip trades | Worst year % | Median Sharpe (subsets) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A. stocks: breakout calls 5% (cap 10%) | +147 | +8.9 | 40 | 0.44 | 238 | 0 | -21 | 0.37 |
| B. QQQ dip calls only, 5% | +38 | +3.1 | 14 | 0.52 | 27 | 27 | -8 | – |
| C. A + QQQ dip calls 5% (cap 15%) | +110 | +7.2 | 48 | 0.37 | 359 | 66 | -28 | 0.32 |
| D. A + QQQ dip calls 2% (cap 12%) | +203 | +11.0 | 37 | 0.50 | 271 | 49 | -22 | 0.39 |
| E. C with stock options at 1.4x IV | +42 | +3.3 | 50 | 0.26 | 350 | 57 | -22 | 0.11 |
| F. QQQ only: breakout calls 5% | -25 | -2.7 | 38 | -0.26 | 76 | 0 | -9 | – |
| G. QQQ only: breakout + dip calls 5% | +8 | +0.8 | 32 | 0.12 | 102 | 102 | -11 | – |

Return by year (%):

| Variant | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A. | -17 | -2 | -9 | +11 | +24 | -21 | +60 | +43 | -11 | +78 | -15 |
| C. | -25 | +23 | -15 | -10 | +35 | -28 | +44 | +18 | +3 | +104 | -14 |
| F. | -9 | +0 | -4 | -7 | -7 | -5 | -6 | -2 | -0 | +18 | -3 |
| G. | -6 | +4 | -4 | -5 | -1 | +1 | -6 | -11 | +15 | +31 | -3 |

## in-sample 2021-2026 (2021-09-01 to 2026-11-10)

Buy & hold: QQQ +77% (CAGR +11.7%, DD 36%, Sharpe 0.60); SPY +66% (CAGR +10.3%, DD 25%)

| Variant | Return % | CAGR % | Max DD % | Sharpe | Trades | Dip trades | Worst year % | Median Sharpe (subsets) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A. stocks: breakout calls 5% (cap 10%) | +84 | +12.5 | 43 | 0.51 | 115 | 0 | -14 | 0.50 |
| B. QQQ dip calls only, 5% | +16 | +2.9 | 17 | 0.41 | 19 | 19 | -16 | – |
| C. A + QQQ dip calls 5% (cap 15%) | +82 | +12.2 | 43 | 0.47 | 180 | 29 | -34 | 0.47 |
| D. A + QQQ dip calls 2% (cap 12%) | +86 | +12.7 | 45 | 0.52 | 140 | 26 | -19 | 0.47 |
| E. C with stock options at 1.4x IV | -10 | -2.0 | 51 | 0.12 | 175 | 29 | -38 | 0.15 |
| F. QQQ only: breakout calls 5% | +4 | +0.8 | 16 | 0.12 | 32 | 0 | -7 | – |
| G. QQQ only: breakout + dip calls 5% | -8 | -1.5 | 28 | -0.06 | 51 | 51 | -24 | – |

Return by year (%):

| Variant | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---:|---:|---:|---:|---:|---:|
| A. | +68 | -14 | -0 | +46 | -12 | -0 |
| C. | +53 | -34 | +27 | +32 | -14 | +24 |
| F. | +4 | -7 | +5 | -2 | -2 | +7 |
| G. | +4 | -24 | +27 | -3 | -6 | +1 |

## Limits

- Single-stock option prices are modelled (row E shows 1.4x IV); VXN is index-level implied vol, without skew or term structure.
- Dip trades are few (a handful of selloffs per decade), so their contribution is noisy.
