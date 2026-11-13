# Wheel / put-write / buy-write vs buy & hold

Model prices: Black-Scholes, ATM implied vol = VIX / VXN x 0.85, plus skew; monthly options, 1% half bid-ask, no leverage, cash at the T-bill rate, dividend-adjusted prices.

## SPY (2000-2026)

| Strategy | CAGR | Max DD | Vol | Sharpe | 2000/01-2012 CAGR | 2013-2026 CAGR | 2008 | 2022 | 2023-24 | 2025 to 11/28 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Buy & hold | +8.2% | 55% | 19% | 0.51 | +1.7% | +14.5% | -36.2% | -18.6% | +58.2% | +17.9% |
| Wheel, 0.30-delta put / 0.30-delta call (41 assigned, 41 called away) | +7.5% | 40% | 14% | 0.60 | +5.5% | +10.0% | -21.9% | -7.2% | +32.1% | +6.3% |
| Wheel, 0.20-delta put / 0.20-delta call (28 assigned, 28 called away) | +6.5% | 44% | 14% | 0.52 | +4.4% | +9.8% | -21.0% | -4.4% | +33.6% | +6.8% |
| Wheel, ATM put / 0.30-delta call (63 assigned, 62 called away) | +8.9% | 42% | 15% | 0.65 | +4.2% | +12.6% | -23.9% | -13.4% | +39.9% | +11.5% |
| Put-write, ATM (like CBOE PUT) | +7.8% | 38% | 13% | 0.63 | +4.1% | +10.2% | -21.7% | -12.2% | +33.0% | +9.5% |
| Put-write, 0.30 delta | +5.8% | 32% | 10% | 0.59 | +4.3% | +7.6% | -12.4% | -1.0% | +23.2% | +4.6% |
| Buy-write, ATM (like CBOE BXM) | +6.5% | 39% | 13% | 0.53 | +2.8% | +8.8% | -22.9% | -13.6% | +29.3% | +8.0% |
| Buy-write, 0.30 delta | +9.3% | 45% | 16% | 0.63 | +4.2% | +13.4% | -25.6% | -17.0% | +42.9% | +16.8% |

## QQQ (2001-2026)

| Strategy | CAGR | Max DD | Vol | Sharpe | 2000/01-2012 CAGR | 2013-2026 CAGR | 2008 | 2022 | 2023-24 | 2025 to 11/28 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Buy & hold | +10.3% | 69% | 24% | 0.53 | +0.5% | +19.2% | -40.8% | -33.2% | +95.8% | +21.8% |
| Wheel, 0.30-delta put / 0.30-delta call (48 assigned, 47 called away) | +8.3% | 46% | 16% | 0.57 | +5.4% | +10.6% | -29.4% | -23.5% | +36.6% | +2.3% |
| Wheel, 0.20-delta put / 0.20-delta call (28 assigned, 27 called away) | +7.4% | 47% | 16% | 0.53 | +4.2% | +8.9% | -29.6% | -15.3% | +35.2% | +2.2% |
| Wheel, ATM put / 0.30-delta call (63 assigned, 62 called away) | +7.1% | 58% | 18% | 0.48 | +0.7% | +12.3% | -30.8% | -29.9% | +49.2% | +7.6% |
| Put-write, ATM (like CBOE PUT) | +6.2% | 54% | 16% | 0.46 | +1.2% | +9.6% | -29.4% | -28.9% | +38.7% | +6.2% |
| Put-write, 0.30 delta | +6.4% | 37% | 12% | 0.57 | +4.2% | +7.8% | -22.6% | -14.2% | +25.4% | +1.7% |
| Buy-write, ATM (like CBOE BXM) | +5.5% | 55% | 16% | 0.41 | +0.5% | +8.9% | -30.1% | -29.6% | +36.5% | +5.2% |
| Buy-write, 0.30 delta | +8.6% | 64% | 20% | 0.52 | +0.8% | +13.2% | -33.3% | -33.8% | +52.0% | +13.9% |


# Sensitivity: optimistic pricing (ATM IV = VIX / VXN x 1.0)

VIX averaged 19.8 from 2000 while the following 21-day realised vol averaged 15.8; VIX also includes the put skew, so ATM implied vol sits below it. 0.85 is the base case because it puts ATM put-writing roughly level with the S&P and ATM buy-write below it, in line with the long-run behaviour of the CBOE PUT and BXM indexes as I recall it (not verified against index data here).


## SPY (2000-2026)

| Strategy | CAGR | Max DD | Vol | Sharpe | 2000/01-2012 CAGR | 2013-2026 CAGR | 2008 | 2022 | 2023-24 | 2025 to 11/28 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Buy & hold | +8.2% | 55% | 19% | 0.51 | +1.7% | +14.5% | -36.2% | -18.6% | +58.2% | +17.9% |
| Wheel, 0.30-delta put / 0.30-delta call (39 assigned, 39 called away) | +11.4% | 36% | 14% | 0.85 | +9.7% | +14.2% | -17.9% | -1.6% | +40.9% | +10.2% |
| Wheel, 0.20-delta put / 0.20-delta call (21 assigned, 21 called away) | +8.8% | 43% | 14% | 0.68 | +6.7% | +10.0% | -18.8% | +6.3% | +44.5% | +19.6% |
| Wheel, ATM put / 0.30-delta call (60 assigned, 59 called away) | +13.3% | 38% | 15% | 0.90 | +8.5% | +17.2% | -19.6% | -9.2% | +49.6% | +16.4% |
| Put-write, ATM (like CBOE PUT) | +12.3% | 35% | 13% | 0.94 | +8.8% | +14.3% | -16.6% | -7.9% | +42.6% | +14.0% |
| Put-write, 0.30 delta | +9.5% | 29% | 10% | 0.95 | +8.7% | +10.9% | -5.2% | +5.5% | +29.9% | +8.1% |
| Buy-write, ATM (like CBOE BXM) | +11.0% | 35% | 13% | 0.84 | +7.5% | +12.9% | -17.8% | -9.3% | +38.8% | +12.4% |
| Buy-write, 0.30 delta | +13.3% | 42% | 16% | 0.84 | +8.2% | +17.8% | -23.1% | -13.5% | +54.8% | +22.4% |

## QQQ (2001-2026)

| Strategy | CAGR | Max DD | Vol | Sharpe | 2000/01-2012 CAGR | 2013-2026 CAGR | 2008 | 2022 | 2023-24 | 2025 to 11/28 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Buy & hold | +10.3% | 69% | 24% | 0.53 | +0.5% | +19.2% | -40.8% | -33.2% | +95.8% | +21.8% |
| Wheel, 0.30-delta put / 0.30-delta call (41 assigned, 40 called away) | +13.3% | 40% | 16% | 0.86 | +11.8% | +14.4% | -25.2% | -17.7% | +52.2% | +6.1% |
| Wheel, 0.20-delta put / 0.20-delta call (23 assigned, 23 called away) | +11.9% | 39% | 16% | 0.77 | +7.8% | +12.6% | -22.1% | -7.3% | +42.7% | +6.0% |
| Wheel, ATM put / 0.30-delta call (60 assigned, 59 called away) | +12.8% | 51% | 18% | 0.77 | +6.6% | +17.7% | -27.0% | -25.7% | +67.4% | +12.5% |
| Put-write, ATM (like CBOE PUT) | +11.8% | 46% | 16% | 0.78 | +7.4% | +14.5% | -24.2% | -24.5% | +51.2% | +10.9% |
| Put-write, 0.30 delta | +11.3% | 31% | 12% | 0.97 | +10.3% | +11.7% | -15.6% | -6.2% | +33.9% | +5.4% |
| Buy-write, ATM (like CBOE BXM) | +11.1% | 47% | 16% | 0.73 | +6.7% | +13.8% | -25.0% | -25.2% | +49.0% | +9.9% |
| Buy-write, 0.30 delta | +14.0% | 58% | 20% | 0.75 | +6.3% | +18.4% | -29.8% | -30.2% | +67.2% | +19.1% |

