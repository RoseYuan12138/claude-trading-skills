# Aggressive QQQ Option Strategies, 2001-2026

All option strategies trade QQQ only and are priced off the actual VXN, the actual 3-month T-bill rate (^IRX) and a 0.7% dividend yield, with a strike-based skew ('base skew': +0.75 vol point per 1% below spot, -0.25 per 1% above, for 30-day options, scaled by sqrt(30/days)) and a 0.5% half bid-ask per leg. Later tables vary skew and costs. Strategy parameters were fixed before the first run; skew, rates, dividends and costs were corrected afterwards (see the strategy document). Exits: S1/S2 -50% premium stop, trailing after +50%, 5 DTE; S3 regime exit (SPY < 200d) and roll at 30 DTE; S4 take profit at 50% of credit, stop at 2x credit, close at 7 DTE or when SPY < 200d.

## 2001-2010 stress (2001-02-01 to 2010-12-31)

| Strategy | CAGR % | Max DD % | Sharpe | Worst year % | Trades |
|---|---:|---:|---:|---:|---:|
| QQQ buy & hold | -1.4 | 69 | 0.10 | -42 | – |
| 2x QQQ buy & hold (QLD-like) | -13.9 | 94 | 0.04 | -73 | – |
| 2x QQQ while SPY > 200d | +5.3 | 50 | 0.33 | -21 | – |
| 3x QQQ while SPY > 200d | +4.8 | 68 | 0.32 | -31 | – |
| S1 breakout calls (5%/trade) | -0.8 | 24 | -0.04 | -7 | 53 (42% won) |
| S2 dip calls, score < 30 (5%/trade) | -0.9 | 40 | -0.06 | -19 | 59 (32% won) |
| S3a ITM trend calls, 30% in premium | +6.0 | 44 | 0.41 | -13 | 49 (39% won) |
| S3b ITM trend calls, 50% in premium | +7.7 | 65 | 0.40 | -22 | 49 (39% won) |
| S4a put credit spreads (10% max loss) | +0.8 | 11 | 0.18 | -5 | 116 (67% won) |
| S4b put credit spreads (25% max loss) | +1.5 | 25 | 0.18 | -13 | 116 (67% won) |
| C1 S3a 80% + S2 20% | +4.9 | 38 | 0.38 | -13 | – |
| C2 S4a 80% + S2 20% | +0.4 | 12 | 0.12 | -8 | – |

## 2011-2021 out of sample (2011-01-03 to 2021-08-31)

| Strategy | CAGR % | Max DD % | Sharpe | Worst year % | Trades |
|---|---:|---:|---:|---:|---:|
| QQQ buy & hold | +21.0 | 29 | 1.07 | -0 | – |
| 2x QQQ buy & hold (QLD-like) | +38.0 | 52 | 1.02 | -8 | – |
| 2x QQQ while SPY > 200d | +30.0 | 35 | 1.03 | -15 | – |
| 3x QQQ while SPY > 200d | +42.7 | 48 | 1.02 | -24 | – |
| S1 breakout calls (5%/trade) | +1.3 | 20 | 0.17 | -8 | 73 (41% won) |
| S2 dip calls, score < 30 (5%/trade) | +4.6 | 13 | 0.67 | -5 | 28 (57% won) |
| S3a ITM trend calls, 30% in premium | +19.0 | 30 | 0.89 | -18 | 57 (54% won) |
| S3b ITM trend calls, 50% in premium | +30.4 | 45 | 0.91 | -29 | 57 (54% won) |
| S4a put credit spreads (10% max loss) | +3.3 | 10 | 0.56 | -6 | 190 (79% won) |
| S4b put credit spreads (25% max loss) | +7.8 | 25 | 0.56 | -17 | 190 (79% won) |
| C1 S3a 80% + S2 20% | +17.2 | 28 | 0.89 | -15 | – |
| C2 S4a 80% + S2 20% | +3.5 | 9 | 0.69 | -6 | – |

## 2021-2026 in sample (2021-09-01 to 2026-11-10)

| Strategy | CAGR % | Max DD % | Sharpe | Worst year % | Trades |
|---|---:|---:|---:|---:|---:|
| QQQ buy & hold | +12.4 | 35 | 0.62 | -33 | – |
| 2x QQQ buy & hold (QLD-like) | +13.8 | 64 | 0.51 | -60 | – |
| 2x QQQ while SPY > 200d | +11.4 | 44 | 0.49 | -42 | – |
| 3x QQQ while SPY > 200d | +10.8 | 60 | 0.46 | -57 | – |
| S1 breakout calls (5%/trade) | +3.1 | 13 | 0.33 | -4 | 31 (39% won) |
| S2 dip calls, score < 30 (5%/trade) | +3.3 | 18 | 0.43 | -17 | 19 (32% won) |
| S3a ITM trend calls, 30% in premium | +4.4 | 40 | 0.30 | -32 | 29 (38% won) |
| S3b ITM trend calls, 50% in premium | +4.4 | 58 | 0.31 | -49 | 29 (38% won) |
| S4a put credit spreads (10% max loss) | +0.6 | 9 | 0.13 | -7 | 86 (69% won) |
| S4b put credit spreads (25% max loss) | +0.9 | 21 | 0.13 | -17 | 86 (69% won) |
| C1 S3a 80% + S2 20% | +4.2 | 35 | 0.31 | -29 | – |
| C2 S4a 80% + S2 20% | +1.1 | 9 | 0.22 | -9 | – |

## 2001-2026 all (2001-02-01 to 2026-11-10)

| Strategy | CAGR % | Max DD % | Sharpe | Worst year % | Trades |
|---|---:|---:|---:|---:|---:|
| QQQ buy & hold | +10.2 | 69 | 0.52 | -42 | – |
| 2x QQQ buy & hold (QLD-like) | +10.9 | 94 | 0.46 | -73 | – |
| 2x QQQ while SPY > 200d | +16.4 | 50 | 0.66 | -42 | – |
| 3x QQQ while SPY > 200d | +20.7 | 68 | 0.65 | -57 | – |
| S1 breakout calls (5%/trade) | +0.8 | 24 | 0.13 | -7 | 158 (41% won) |
| S2 dip calls, score < 30 (5%/trade) | +2.2 | 40 | 0.31 | -19 | 106 (39% won) |
| S3a ITM trend calls, 30% in premium | +10.9 | 44 | 0.59 | -33 | 136 (46% won) |
| S3b ITM trend calls, 50% in premium | +15.8 | 65 | 0.60 | -50 | 136 (46% won) |
| S4a put credit spreads (10% max loss) | +1.7 | 11 | 0.32 | -7 | 394 (73% won) |
| S4b put credit spreads (25% max loss) | +3.8 | 25 | 0.33 | -17 | 394 (73% won) |
| C1 S3a 80% + S2 20% | +10.1 | 38 | 0.58 | -33 | – |
| C2 S4a 80% + S2 20% | +1.8 | 12 | 0.37 | -9 | – |

## Sensitivity to option pricing, 2001-2026 (CAGR % / Max DD % / Sharpe)

| Strategy | no skew | base skew | steep skew |
|---|---|---|---|
| S1 breakout calls (5%/trade) | -0.1 / 28 / 0.04 | +0.8 / 24 / 0.13 | +0.8 / 26 / 0.13 |
| S2 dip calls, score < 30 (5%/trade) | +1.6 / 46 / 0.24 | +2.2 / 40 / 0.31 | +1.8 / 46 / 0.26 |
| S3a ITM trend calls, 30% in premium | +13.3 / 43 / 0.66 | +10.9 / 44 / 0.59 | +9.2 / 45 / 0.53 |
| S3b ITM trend calls, 50% in premium | +19.7 / 63 / 0.67 | +15.8 / 65 / 0.60 | +13.2 / 66 / 0.54 |
| S4a put credit spreads (10% max loss) | +3.6 / 13 / 0.53 | +1.7 / 11 / 0.32 | +0.2 / 15 / 0.07 |
| S4b put credit spreads (25% max loss) | +8.4 / 30 / 0.54 | +3.8 / 25 / 0.33 | +0.1 / 37 / 0.07 |

## Sensitivity to bid-ask costs, 2001-2026, base skew (CAGR % / Max DD % / Sharpe)

| Strategy | 0.5% half spread | 1.0% half spread | 2.5% half spread |
|---|---|---|---|
| S1 breakout calls (5%/trade) | +0.8 / 24 / 0.13 | +0.6 / 24 / 0.11 | -0.4 / 32 / 0.01 |
| S2 dip calls, score < 30 (5%/trade) | +2.2 / 40 / 0.31 | +2.4 / 38 / 0.34 | +1.9 / 40 / 0.27 |
| S3a ITM trend calls, 30% in premium | +10.9 / 44 / 0.59 | +9.2 / 47 / 0.52 | +4.2 / 54 / 0.30 |
| S3b ITM trend calls, 50% in premium | +15.8 / 65 / 0.60 | +12.9 / 67 / 0.52 | +4.5 / 75 / 0.30 |
| S4a put credit spreads (10% max loss) | +1.7 / 11 / 0.32 | +1.8 / 11 / 0.35 | +1.8 / 11 / 0.35 |
| S4b put credit spreads (25% max loss) | +3.8 / 25 / 0.33 | +4.1 / 25 / 0.35 | +4.1 / 26 / 0.35 |

## S3 parameter neighbourhood (base pricing)

Moneyness 0.80/0.85/0.90 x DTE 90/120/180 x regime SMA 150/200/250 x roll at 20/30/45 DTE, for 30% and 50% of equity in premium.

| Premium | Window | Combos | CAGR min / median / max % | Median Max DD % | Median Sharpe | Combos < 0 |
|---:|---|---:|---|---:|---:|---:|
| 30% | 2001-2010 stress | 81 | +2.3 / +5.4 / +9.7 | 38 | 0.39 | 0 |
| 30% | 2011-2021 out of sample | 81 | +13.2 / +19.4 / +29.6 | 29 | 0.92 | 0 |
| 30% | 2021-2026 in sample | 81 | +1.2 / +5.8 / +15.0 | 35 | 0.36 | 0 |
| 30% | 2001-2026 all | 81 | +7.7 / +11.7 / +15.9 | 38 | 0.61 | 0 |
| 50% | 2001-2010 stress | 81 | +0.9 / +7.3 / +13.1 | 57 | 0.40 | 0 |
| 50% | 2011-2021 out of sample | 81 | +20.3 / +30.9 / +47.3 | 44 | 0.94 | 0 |
| 50% | 2021-2026 in sample | 81 | -3.4 / +6.4 / +21.7 | 52 | 0.36 | 5 |
| 50% | 2001-2026 all | 81 | +11.4 / +16.5 / +24.0 | 57 | 0.61 | 0 |

## Return by year, 2001-2026 (%)

| Strategy | 01 | 02 | 03 | 04 | 05 | 06 | 07 | 08 | 09 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 | 24 | 25 | 26 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| QQQ buy & hold | -40 | -37 | +50 | +11 | +2 | +7 | +19 | -42 | +55 | +20 | +3 | +18 | +37 | +19 | +9 | +7 | +33 | -0 | +39 | +48 | +27 | -33 | +55 | +26 | +21 | +10 |
| 2x QQQ buy & hold (QLD-like) | -73 | -68 | +106 | +15 | -3 | +5 | +29 | -72 | +121 | +37 | -0 | +34 | +81 | +37 | +14 | +10 | +70 | -8 | +82 | +90 | +55 | -60 | +118 | +43 | +31 | +11 |
| 2x QQQ while SPY > 200d | +0 | -21 | +62 | -1 | -19 | -4 | +11 | -11 | +64 | +5 | -12 | +28 | +81 | +33 | +3 | +17 | +70 | +0 | +45 | +46 | +55 | -42 | +67 | +43 | +14 | +3 |
| 3x QQQ while SPY > 200d | +0 | -31 | +94 | -5 | -30 | -11 | +11 | -16 | +103 | +4 | -20 | +39 | +137 | +49 | +3 | +24 | +116 | -5 | +68 | +63 | +82 | -57 | +102 | +59 | +16 | -3 |
| S1 breakout calls (5%/trade) | -3 | -7 | -6 | -0 | +7 | -0 | +1 | -3 | -1 | +7 | -6 | +7 | -2 | -1 | -4 | -4 | -1 | +3 | +4 | +24 | +1 | -4 | +9 | -3 | -0 | +8 |
| S2 dip calls, score < 30 (5%/trade) | -13 | -19 | -2 | +5 | +10 | -4 | -2 | -19 | +23 | +23 | +1 | +0 | +0 | +11 | +12 | +2 | +0 | -5 | +20 | +11 | +0 | -17 | +9 | +0 | +13 | +16 |
| S3a ITM trend calls, 30% in premium | +0 | -12 | +50 | -9 | -13 | -7 | +22 | -1 | +35 | +12 | -7 | +16 | +63 | +22 | -18 | +12 | +60 | -4 | +24 | +35 | +29 | -33 | +30 | +16 | +13 | +9 |
| S3b ITM trend calls, 50% in premium | +0 | -19 | +91 | -17 | -22 | -16 | +38 | -1 | +58 | +16 | -12 | +18 | +118 | +37 | -29 | +19 | +112 | -9 | +42 | +61 | +52 | -50 | +48 | +25 | +18 | +10 |
| S4a put credit spreads (10% max loss) | +0 | -5 | +10 | -0 | +1 | -2 | -1 | -0 | +7 | -1 | -1 | +2 | +11 | +1 | +3 | +5 | +9 | -6 | +6 | +3 | +7 | -7 | +4 | +8 | -2 | -3 |
| S4b put credit spreads (25% max loss) | +0 | -13 | +25 | -1 | +2 | -5 | -4 | -1 | +20 | -4 | -4 | +5 | +28 | +2 | +7 | +13 | +25 | -17 | +14 | +6 | +18 | -17 | +10 | +20 | -6 | -8 |
| C1 S3a 80% + S2 20% | -3 | -13 | +42 | -7 | -10 | -7 | +18 | -3 | +33 | +13 | -6 | +14 | +56 | +22 | -16 | +11 | +55 | -4 | +24 | +34 | +28 | -33 | +29 | +15 | +13 | +9 |
| C2 S4a 80% + S2 20% | -3 | -8 | +8 | +1 | +2 | -2 | -1 | -3 | +9 | +2 | -1 | +2 | +9 | +3 | +5 | +4 | +8 | -6 | +8 | +4 | +6 | -9 | +5 | +6 | +0 | +0 |

## Limits

- VXN is 30-day at-the-money implied vol for the Nasdaq-100; strike skew and term structure are modelled, not observed. Real chains are needed to confirm the numbers.
- Bid-ask: 0.5% of the option price per leg (min $0.01) by default; the cost table shows 1% and 2.5%. Fills at the next open after a signal at the close.
- European pricing with a 0.7% dividend yield; no early assignment, no commissions.
- Leveraged-ETF rows are synthetic (daily 2x/3x of dividend-adjusted QQQ minus borrowing at ^IRX and costs calibrated to QLD/TQQQ since 2010).
