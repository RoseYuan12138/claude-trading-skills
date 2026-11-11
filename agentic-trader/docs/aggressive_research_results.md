# Aggressive QQQ Option Strategies, 2001-2026

All option strategies trade QQQ only and are priced off the actual VXN, the actual 3-month T-bill rate (^IRX) and a 0.7% dividend yield, with a strike-based skew ('base skew': +0.75 vol point per 1% below spot, -0.25 per 1% above, for 30-day options, scaled by sqrt(30/days)), a term structure (30-day VXN mean-reverting to 24% at kappa 3/yr for longer expiries) and a 0.5% half bid-ask per leg. Later tables vary skew and costs. Strategy parameters were fixed before the first run; skew, rates, dividends and costs were corrected afterwards (see the strategy document). Exits: S1/S2 -50% premium stop, trailing after +50%, 5 DTE; S3 regime exit (SPY < 200d) and roll at 30 DTE; S4 take profit at 50% of credit, stop at 2x credit, close at 7 DTE or when SPY < 200d.

## 2000-2026 from the dot-com peak (2000-01-03 to 2026-11-10)

| Strategy | CAGR % | Max DD % | Sharpe | Worst year % | Trades |
|---|---:|---:|---:|---:|---:|
| QQQ buy & hold | +8.3 | 83 | 0.43 | -42 | – |
| 2x QQQ buy & hold (QLD-like) | +5.6 | 99 | 0.37 | -75 | – |
| 2x QQQ while SPY > 200d | +10.2 | 86 | 0.46 | -73 | – |
| 3x QQQ while SPY > 200d | +10.0 | 96 | 0.45 | -90 | – |
| 2x QQQ while SPY and QQQ > 200d | +10.3 | 78 | 0.47 | -65 | – |
| S1 breakout calls (5%/trade) | +0.3 | 29 | 0.08 | -7 | 164 (40% won) |
| S2 dip calls, score < 30 (5%/trade) | +3.3 | 45 | 0.40 | -26 | 122 (39% won) |
| S3a ITM trend calls, 30% in premium | +7.3 | 59 | 0.42 | -41 | 148 (45% won) |
| S3b ITM trend calls, 50% in premium | +9.4 | 81 | 0.43 | -62 | 148 (45% won) |
| S3c LEAPS trend calls, 270d/roll 60, 30% | +8.2 | 50 | 0.50 | -35 | 110 (38% won) |
| S3d LEAPS trend calls, 270d/roll 60, 50% | +11.6 | 72 | 0.51 | -54 | 110 (38% won) |
| S3e LEAPS 270d, 30%, SPY and QQQ > 200d | +9.0 | 43 | 0.55 | -34 | 110 (37% won) |
| S3f LEAPS 270d, 50%, SPY and QQQ > 200d | +13.3 | 62 | 0.57 | -53 | 110 (37% won) |
| S4a put credit spreads (10% max loss) | +0.9 | 30 | 0.18 | -25 | 419 (73% won) |
| S4b put credit spreads (25% max loss) | +1.6 | 62 | 0.18 | -54 | 419 (73% won) |
| C1 S3a 80% + S2 20% | +6.7 | 51 | 0.43 | -33 | – |
| C2 S4a 80% + S2 20% | +1.5 | 29 | 0.29 | -15 | – |

## 2001-2010 stress (2001-02-01 to 2010-12-31)

| Strategy | CAGR % | Max DD % | Sharpe | Worst year % | Trades |
|---|---:|---:|---:|---:|---:|
| QQQ buy & hold | -1.4 | 69 | 0.10 | -42 | – |
| 2x QQQ buy & hold (QLD-like) | -13.9 | 94 | 0.04 | -73 | – |
| 2x QQQ while SPY > 200d | +5.3 | 50 | 0.33 | -21 | – |
| 3x QQQ while SPY > 200d | +4.8 | 68 | 0.32 | -31 | – |
| 2x QQQ while SPY and QQQ > 200d | +6.7 | 44 | 0.39 | -26 | – |
| S1 breakout calls (5%/trade) | -0.8 | 24 | -0.04 | -7 | 53 (42% won) |
| S2 dip calls, score < 30 (5%/trade) | -0.4 | 40 | 0.00 | -26 | 61 (30% won) |
| S3a ITM trend calls, 30% in premium | +5.4 | 46 | 0.37 | -14 | 49 (41% won) |
| S3b ITM trend calls, 50% in premium | +6.6 | 66 | 0.36 | -24 | 49 (41% won) |
| S3c LEAPS trend calls, 270d/roll 60, 30% | +4.9 | 38 | 0.37 | -11 | 38 (39% won) |
| S3d LEAPS trend calls, 270d/roll 60, 50% | +6.9 | 55 | 0.39 | -18 | 38 (39% won) |
| S3e LEAPS 270d, 30%, SPY and QQQ > 200d | +7.2 | 28 | 0.53 | -11 | 33 (36% won) |
| S3f LEAPS 270d, 50%, SPY and QQQ > 200d | +11.1 | 41 | 0.56 | -18 | 33 (36% won) |
| S4a put credit spreads (10% max loss) | +0.3 | 11 | 0.08 | -5 | 118 (66% won) |
| S4b put credit spreads (25% max loss) | +0.3 | 26 | 0.09 | -12 | 118 (66% won) |
| C1 S3a 80% + S2 20% | +4.5 | 40 | 0.35 | -15 | – |
| C2 S4a 80% + S2 20% | +0.2 | 12 | 0.06 | -9 | – |

## 2011-2021 out of sample (2011-01-03 to 2021-08-31)

| Strategy | CAGR % | Max DD % | Sharpe | Worst year % | Trades |
|---|---:|---:|---:|---:|---:|
| QQQ buy & hold | +21.0 | 29 | 1.07 | -0 | – |
| 2x QQQ buy & hold (QLD-like) | +38.0 | 52 | 1.02 | -8 | – |
| 2x QQQ while SPY > 200d | +30.0 | 35 | 1.03 | -15 | – |
| 3x QQQ while SPY > 200d | +42.7 | 48 | 1.02 | -24 | – |
| 2x QQQ while SPY and QQQ > 200d | +25.3 | 35 | 0.92 | -24 | – |
| S1 breakout calls (5%/trade) | +0.4 | 22 | 0.09 | -9 | 74 (39% won) |
| S2 dip calls, score < 30 (5%/trade) | +4.8 | 13 | 0.68 | -5 | 28 (57% won) |
| S3a ITM trend calls, 30% in premium | +17.4 | 31 | 0.82 | -20 | 57 (54% won) |
| S3b ITM trend calls, 50% in premium | +27.3 | 46 | 0.84 | -31 | 57 (54% won) |
| S3c LEAPS trend calls, 270d/roll 60, 30% | +18.4 | 25 | 0.98 | -12 | 39 (44% won) |
| S3d LEAPS trend calls, 270d/roll 60, 50% | +29.2 | 38 | 0.99 | -20 | 39 (44% won) |
| S3e LEAPS 270d, 30%, SPY and QQQ > 200d | +15.7 | 26 | 0.87 | -12 | 48 (38% won) |
| S3f LEAPS 270d, 50%, SPY and QQQ > 200d | +24.7 | 40 | 0.89 | -20 | 48 (38% won) |
| S4a put credit spreads (10% max loss) | +4.1 | 10 | 0.69 | -6 | 193 (80% won) |
| S4b put credit spreads (25% max loss) | +9.9 | 25 | 0.69 | -15 | 193 (80% won) |
| C1 S3a 80% + S2 20% | +15.7 | 28 | 0.83 | -16 | – |
| C2 S4a 80% + S2 20% | +4.2 | 9 | 0.80 | -6 | – |

## 2021-2026 in sample (2021-09-01 to 2026-11-10)

| Strategy | CAGR % | Max DD % | Sharpe | Worst year % | Trades |
|---|---:|---:|---:|---:|---:|
| QQQ buy & hold | +12.4 | 35 | 0.62 | -33 | – |
| 2x QQQ buy & hold (QLD-like) | +13.8 | 64 | 0.51 | -60 | – |
| 2x QQQ while SPY > 200d | +11.4 | 44 | 0.49 | -42 | – |
| 3x QQQ while SPY > 200d | +10.8 | 60 | 0.46 | -57 | – |
| 2x QQQ while SPY and QQQ > 200d | +12.2 | 40 | 0.52 | -32 | – |
| S1 breakout calls (5%/trade) | +2.9 | 14 | 0.31 | -5 | 31 (39% won) |
| S2 dip calls, score < 30 (5%/trade) | +4.3 | 16 | 0.52 | -13 | 21 (38% won) |
| S3a ITM trend calls, 30% in premium | +3.8 | 41 | 0.28 | -33 | 29 (38% won) |
| S3b ITM trend calls, 50% in premium | +2.9 | 59 | 0.27 | -50 | 29 (38% won) |
| S3c LEAPS trend calls, 270d/roll 60, 30% | +5.1 | 34 | 0.34 | -30 | 20 (30% won) |
| S3d LEAPS trend calls, 270d/roll 60, 50% | +6.2 | 51 | 0.35 | -45 | 20 (30% won) |
| S3e LEAPS 270d, 30%, SPY and QQQ > 200d | +8.5 | 24 | 0.51 | -18 | 17 (35% won) |
| S3f LEAPS 270d, 50%, SPY and QQQ > 200d | +12.6 | 38 | 0.54 | -29 | 17 (35% won) |
| S4a put credit spreads (10% max loss) | +1.8 | 8 | 0.32 | -7 | 88 (70% won) |
| S4b put credit spreads (25% max loss) | +4.0 | 21 | 0.33 | -17 | 88 (70% won) |
| C1 S3a 80% + S2 20% | +4.0 | 34 | 0.30 | -28 | – |
| C2 S4a 80% + S2 20% | +2.4 | 8 | 0.46 | -8 | – |

## 2001-2026 all (2001-02-01 to 2026-11-10)

| Strategy | CAGR % | Max DD % | Sharpe | Worst year % | Trades |
|---|---:|---:|---:|---:|---:|
| QQQ buy & hold | +10.2 | 69 | 0.52 | -42 | – |
| 2x QQQ buy & hold (QLD-like) | +10.9 | 94 | 0.46 | -73 | – |
| 2x QQQ while SPY > 200d | +16.4 | 50 | 0.66 | -42 | – |
| 3x QQQ while SPY > 200d | +20.7 | 68 | 0.65 | -57 | – |
| 2x QQQ while SPY and QQQ > 200d | +15.4 | 44 | 0.65 | -32 | – |
| S1 breakout calls (5%/trade) | +0.4 | 24 | 0.09 | -7 | 159 (40% won) |
| S2 dip calls, score < 30 (5%/trade) | +2.7 | 40 | 0.35 | -26 | 110 (38% won) |
| S3a ITM trend calls, 30% in premium | +9.9 | 46 | 0.54 | -34 | 136 (46% won) |
| S3b ITM trend calls, 50% in premium | +14.0 | 66 | 0.55 | -51 | 136 (46% won) |
| S3c LEAPS trend calls, 270d/roll 60, 30% | +10.4 | 38 | 0.63 | -30 | 98 (39% won) |
| S3d LEAPS trend calls, 270d/roll 60, 50% | +15.6 | 55 | 0.64 | -46 | 98 (39% won) |
| S3e LEAPS 270d, 30%, SPY and QQQ > 200d | +11.2 | 28 | 0.68 | -18 | 99 (37% won) |
| S3f LEAPS 270d, 50%, SPY and QQQ > 200d | +17.2 | 41 | 0.71 | -29 | 99 (37% won) |
| S4a put credit spreads (10% max loss) | +2.1 | 11 | 0.39 | -7 | 401 (74% won) |
| S4b put credit spreads (25% max loss) | +4.8 | 26 | 0.39 | -17 | 401 (74% won) |
| C1 S3a 80% + S2 20% | +9.1 | 40 | 0.54 | -33 | – |
| C2 S4a 80% + S2 20% | +2.2 | 12 | 0.45 | -9 | – |

## Sensitivity to option pricing, 2001-2026 (CAGR % / Max DD % / Sharpe)

| Strategy | no skew | base skew | steep skew | base skew, flat term structure |
|---|---|---|---|---|
| S1 breakout calls (5%/trade) | -0.4 / 33 / 0.00 | +0.4 / 24 / 0.09 | +0.5 / 25 / 0.10 | +0.8 / 24 / 0.13 |
| S2 dip calls, score < 30 (5%/trade) | +2.2 / 42 / 0.31 | +2.7 / 40 / 0.35 | +2.9 / 38 / 0.38 | +2.2 / 40 / 0.31 |
| S3a ITM trend calls, 30% in premium | +12.7 / 44 / 0.64 | +9.9 / 46 / 0.54 | +8.1 / 47 / 0.48 | +10.9 / 44 / 0.59 |
| S3b ITM trend calls, 50% in premium | +18.5 / 64 / 0.64 | +14.0 / 66 / 0.55 | +11.2 / 67 / 0.48 | +15.8 / 65 / 0.60 |
| S3c LEAPS trend calls, 270d/roll 60, 30% | +12.2 / 37 / 0.69 | +10.4 / 38 / 0.63 | +9.4 / 38 / 0.59 | +12.7 / 36 / 0.76 |
| S3d LEAPS trend calls, 270d/roll 60, 50% | +18.5 / 54 / 0.70 | +15.6 / 55 / 0.64 | +14.0 / 56 / 0.60 | +19.6 / 53 / 0.78 |
| S3e LEAPS 270d, 30%, SPY and QQQ > 200d | +12.8 / 29 / 0.73 | +11.2 / 28 / 0.68 | +10.2 / 28 / 0.65 | +13.4 / 25 / 0.82 |
| S3f LEAPS 270d, 50%, SPY and QQQ > 200d | +19.7 / 43 / 0.75 | +17.2 / 41 / 0.71 | +15.8 / 41 / 0.67 | +21.1 / 38 / 0.84 |
| S4a put credit spreads (10% max loss) | +3.8 / 13 / 0.55 | +2.1 / 11 / 0.39 | +1.0 / 15 / 0.22 | +1.7 / 11 / 0.32 |
| S4b put credit spreads (25% max loss) | +8.9 / 30 / 0.56 | +4.8 / 26 / 0.39 | +1.9 / 35 / 0.22 | +3.8 / 25 / 0.33 |

## Sensitivity to bid-ask costs, 2001-2026, base skew (CAGR % / Max DD % / Sharpe)

| Strategy | 0.5% half spread | 1.0% half spread | 2.5% half spread |
|---|---|---|---|
| S1 breakout calls (5%/trade) | +0.4 / 24 / 0.09 | +0.4 / 23 / 0.09 | -0.6 / 34 / -0.02 |
| S2 dip calls, score < 30 (5%/trade) | +2.7 / 40 / 0.35 | +2.5 / 41 / 0.34 | +2.5 / 36 / 0.33 |
| S3a ITM trend calls, 30% in premium | +9.9 / 46 / 0.54 | +8.2 / 48 / 0.47 | +3.2 / 56 / 0.26 |
| S3b ITM trend calls, 50% in premium | +14.0 / 66 / 0.55 | +11.1 / 69 / 0.48 | +2.9 / 76 / 0.26 |
| S3c LEAPS trend calls, 270d/roll 60, 30% | +10.4 / 38 / 0.63 | +9.1 / 40 / 0.57 | +5.5 / 47 / 0.38 |
| S3d LEAPS trend calls, 270d/roll 60, 50% | +15.6 / 55 / 0.64 | +13.4 / 58 / 0.58 | +7.3 / 66 / 0.39 |
| S3e LEAPS 270d, 30%, SPY and QQQ > 200d | +11.2 / 28 / 0.68 | +9.9 / 30 / 0.62 | +6.2 / 37 / 0.43 |
| S3f LEAPS 270d, 50%, SPY and QQQ > 200d | +17.2 / 41 / 0.71 | +15.0 / 45 / 0.64 | +8.7 / 54 / 0.44 |
| S4a put credit spreads (10% max loss) | +2.1 / 11 / 0.39 | +2.2 / 11 / 0.40 | +2.0 / 11 / 0.38 |
| S4b put credit spreads (25% max loss) | +4.8 / 26 / 0.39 | +5.0 / 26 / 0.40 | +4.6 / 26 / 0.38 |

## LEAPS parameter neighbourhood, SPY and QQQ > SMA (base pricing)

Moneyness 0.80/0.85/0.90 x DTE 180/270/365 x regime SMA 150/200/250 x roll at 30/60/90 DTE, for 30% and 50% of equity in premium.

| Premium | Window | Combos | CAGR min / median / max % | Median Max DD % | Median Sharpe | Combos < 0 |
|---:|---|---:|---|---:|---:|---:|
| 30% | 2000-2026 from the dot-com peak | 81 | +5.5 / +7.7 / +11.4 | 45 | 0.49 | 0 |
| 30% | 2001-2010 stress | 81 | +4.6 / +6.4 / +8.8 | 26 | 0.48 | 0 |
| 30% | 2011-2021 out of sample | 81 | +9.0 / +14.7 / +21.8 | 28 | 0.83 | 0 |
| 30% | 2021-2026 in sample | 81 | +2.7 / +8.2 / +14.8 | 24 | 0.51 | 0 |
| 30% | 2001-2026 all | 81 | +7.5 / +10.1 / +14.0 | 32 | 0.62 | 0 |
| 50% | 2000-2026 from the dot-com peak | 81 | +7.7 / +10.9 / +16.0 | 65 | 0.50 | 0 |
| 50% | 2001-2010 stress | 81 | +6.8 / +9.6 / +12.8 | 40 | 0.49 | 0 |
| 50% | 2011-2021 out of sample | 81 | +13.8 / +22.7 / +34.5 | 41 | 0.85 | 0 |
| 50% | 2021-2026 in sample | 81 | +0.8 / +12.4 / +21.4 | 38 | 0.53 | 0 |
| 50% | 2001-2026 all | 81 | +11.4 / +15.1 / +20.7 | 47 | 0.64 | 0 |

## Return by year, 2001-2026 (%)

| Strategy | 01 | 02 | 03 | 04 | 05 | 06 | 07 | 08 | 09 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 | 24 | 25 | 26 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| QQQ buy & hold | -40 | -37 | +50 | +11 | +2 | +7 | +19 | -42 | +55 | +20 | +3 | +18 | +37 | +19 | +9 | +7 | +33 | -0 | +39 | +48 | +27 | -33 | +55 | +26 | +21 | +10 |
| 2x QQQ buy & hold (QLD-like) | -73 | -68 | +106 | +15 | -3 | +5 | +29 | -72 | +121 | +37 | -0 | +34 | +81 | +37 | +14 | +10 | +70 | -8 | +82 | +90 | +55 | -60 | +118 | +43 | +31 | +11 |
| 2x QQQ while SPY > 200d | +0 | -21 | +62 | -1 | -19 | -4 | +11 | -11 | +64 | +5 | -12 | +28 | +81 | +33 | +3 | +17 | +70 | +0 | +45 | +46 | +55 | -42 | +67 | +43 | +14 | +3 |
| 3x QQQ while SPY > 200d | +0 | -31 | +94 | -5 | -30 | -11 | +11 | -16 | +103 | +4 | -20 | +39 | +137 | +49 | +3 | +24 | +116 | -5 | +68 | +63 | +82 | -57 | +102 | +59 | +16 | -3 |
| 2x QQQ while SPY and QQQ > 200d | +0 | -2 | +62 | -6 | -26 | +2 | +11 | -11 | +64 | +5 | -21 | +18 | +81 | +33 | +3 | +2 | +70 | -2 | +40 | +46 | +55 | -32 | +50 | +43 | +21 | -5 |
| S1 breakout calls (5%/trade) | -2 | -7 | -6 | -0 | +7 | -1 | +0 | -3 | -1 | +6 | -7 | +6 | -0 | -4 | -4 | -3 | -3 | +2 | +3 | +20 | +1 | -5 | +8 | -3 | -1 | +9 |
| S2 dip calls, score < 30 (5%/trade) | -7 | -26 | -1 | +5 | +9 | -4 | +5 | -19 | +20 | +24 | +1 | +0 | +0 | +11 | +13 | +2 | +0 | -5 | +20 | +11 | +0 | -13 | +10 | +0 | +13 | +16 |
| S3a ITM trend calls, 30% in premium | +0 | -12 | +54 | -9 | -14 | -9 | +20 | -1 | +35 | +9 | -9 | +14 | +60 | +20 | -20 | +10 | +56 | -5 | +22 | +37 | +30 | -34 | +29 | +15 | +12 | +9 |
| S3b ITM trend calls, 50% in premium | +0 | -20 | +99 | -18 | -24 | -18 | +34 | -1 | +58 | +11 | -15 | +16 | +111 | +32 | -31 | +16 | +105 | -11 | +39 | +62 | +52 | -51 | +46 | +24 | +17 | +10 |
| S3c LEAPS trend calls, 270d/roll 60, 30% | +0 | -10 | +47 | -6 | -11 | -9 | +15 | -1 | +31 | +7 | -2 | +12 | +52 | +19 | -12 | +9 | +44 | +3 | +23 | +39 | +34 | -30 | +25 | +22 | +11 | +4 |
| S3d LEAPS trend calls, 270d/roll 60, 50% | +0 | -17 | +82 | -10 | -18 | -16 | +26 | -1 | +49 | +11 | -4 | +21 | +91 | +30 | -20 | +14 | +77 | +2 | +37 | +64 | +57 | -46 | +42 | +37 | +15 | +6 |
| S3e LEAPS 270d, 30%, SPY and QQQ > 200d | +0 | +0 | +47 | -5 | -11 | -0 | +16 | -1 | +31 | +7 | -6 | -4 | +46 | +19 | -12 | +3 | +47 | +12 | +20 | +39 | +34 | -18 | +22 | +22 | +18 | +2 |
| S3f LEAPS 270d, 50%, SPY and QQQ > 200d | +0 | +0 | +82 | -9 | -18 | -0 | +27 | -1 | +49 | +11 | -11 | -7 | +82 | +32 | -20 | +5 | +82 | +18 | +32 | +64 | +57 | -29 | +37 | +37 | +27 | +2 |
| S4a put credit spreads (10% max loss) | +0 | -5 | +9 | -0 | -1 | -3 | -2 | -0 | +7 | -1 | +0 | +3 | +11 | +2 | +5 | +6 | +10 | -6 | +6 | +3 | +8 | -7 | +5 | +9 | -2 | +2 |
| S4b put credit spreads (25% max loss) | +0 | -12 | +25 | -1 | -3 | -8 | -6 | -1 | +19 | -4 | +1 | +6 | +31 | +6 | +12 | +15 | +26 | -15 | +16 | +6 | +19 | -17 | +11 | +23 | -5 | +3 |
| C1 S3a 80% + S2 20% | -1 | -15 | +45 | -8 | -11 | -8 | +17 | -3 | +33 | +11 | -8 | +12 | +53 | +19 | -17 | +10 | +51 | -5 | +22 | +35 | +28 | -33 | +28 | +14 | +12 | +9 |
| C2 S4a 80% + S2 20% | -1 | -9 | +8 | +1 | +0 | -3 | -1 | -3 | +9 | +3 | +1 | +2 | +9 | +4 | +6 | +5 | +8 | -6 | +9 | +4 | +6 | -8 | +5 | +7 | +1 | +4 |

## Limits

- VXN is 30-day at-the-money implied vol for the Nasdaq-100; strike skew and term structure are modelled, not observed. Real chains are needed to confirm the numbers.
- Bid-ask: 0.5% of the option price per leg (min $0.01) by default; the cost table shows 1% and 2.5%. Fills at the next open after a signal at the close.
- European pricing with a 0.7% dividend yield; no early assignment, no commissions.
- Leveraged-ETF rows are synthetic (daily 2x/3x of dividend-adjusted QQQ minus borrowing at ^IRX and costs calibrated to QLD/TQQQ since 2010).
