# Do trailing stops help? SPY, QQQ, TQQQ, SOXL (2000-2026)

Study date: 2026-11-12. Full tables: [stop_study_results.md](stop_study_results.md).
Code: `agentic_trader/sim/stop_study.py`, `scripts/run_stop_study.py`.

## Question

Can code-managed stops protect an aggressive account (index ETFs, TQQQ, SOXL) and do they
improve results, once intraday execution is modelled honestly?

## Method

- Daily regular-session bars, dividend-adjusted. One asset, fully invested or in cash
  (cash earns the T-bill rate).
- **Intraday stop** = a resting broker stop order: it fires when the day's low touches the
  stop and fills at the stop, or at the open if the price gaps below it. Robinhood stops
  only trigger in regular hours, so overnight and after-hours moves arrive as opening gaps;
  the regular-session bar models that correctly.
- **Close stop** = check the close, sell at the next open (ignores intraday wicks).
- Stop level: highest close since entry - k x ATR(14), or a percent trail. It only moves up.
- After a stop: buy back at the next open after a 20-day closing breakout.
- **SMA200** = hold only while the underlying index (SPY, QQQ, ^SOX) closes at or above
  its 200-day SMA. It exits at the next open.
- Costs: 2 bps per side on SPY/QQQ and 5 bps on 3x ETFs, plus 5 / 15 bps extra slippage
  on stop fills.
- TQQQ and SOXL use real fund data from 2010. The 2000-2026 runs use synthetic 3x series
  with intraday highs and lows. On 2010-2026 the synthetic TQQQ matches the real fund
  closely: buy & hold +40.1% vs +40.8% a year, the same drawdown and the same stop counts.

## Results (CAGR / max drawdown / Sharpe)

| Rule | SPY 00-26 | QQQ 00-26 | TQQQ 00-26 (syn) | TQQQ 10-26 (real) | SOXL 10-26 (real) |
|---|---|---|---|---|---|
| Buy & hold | 8.2 / 55 / 0.51 | 8.4 / 83 / 0.43 | **-3.8 / 100** / 0.35 | **40.8** / 82 / 0.87 | 34.4 / 90 / 0.79 |
| ATR 2x intraday | 3.3 / 17 / 0.43 | 2.8 / 44 / 0.29 | -2.7 / 95 / 0.09 | 11.0 / 37 / 0.52 | 6.1 / 76 / 0.35 |
| ATR 3x intraday | 5.8 / 19 / **0.62** | 5.2 / 45 / 0.43 | 6.6 / 88 / 0.36 | 16.3 / 48 / 0.63 | 3.5 / 65 / 0.32 |
| ATR 5x intraday | 4.7 / 41 / 0.44 | 6.8 / 67 / 0.47 | 7.5 / 98 / 0.40 | 25.8 / 62 / 0.78 | 8.8 / 86 / 0.46 |
| ATR 3x close | 4.9 / 27 / 0.51 | 6.7 / 44 / 0.50 | 5.0 / 91 / 0.33 | 19.6 / 51 / 0.69 | 4.7 / 76 / 0.37 |
| SMA200 only | 6.7 / 24 / **0.62** | 8.1 / 50 / **0.54** | **9.0** / 93 / **0.43** | 26.3 / 60 / 0.73 | 26.0 / 83 / 0.69 |
| SMA200 + ATR 3x intraday | 3.5 / 15 / 0.49 | 3.6 / 40 / 0.36 | 2.5 / 86 / 0.24 | 12.3 / 42 / 0.54 | -6.2 / 82 / 0.10 |
| SMA200 + 35% trail intraday | 6.7 / 24 / 0.62 | 8.1 / 50 / 0.54 | 9.7 / 85 / **0.44** | 24.2 / 60 / 0.70 | 15.1 / 78 / 0.54 |

How often stops fire, and what each one costs:

| | SPY / QQQ | TQQQ | SOXL |
|---|---|---|---|
| Stops a year (ATR 2x / 3x / 5x) | 7.5 / 4.8 / 2.8 | 8 / 5.5 / 2.9 | 7.9 / 5.8 / 3.2 |
| Stop exits bought back higher | 75-87% | 74-82% | 66-78% |
| Median cost per stop round trip | +2-4% | +7-11% | +10-13% |
| Stop exits filled on an opening gap | 10-20% | 8-17% | 11-24% |
| Gap fill below the stop, average | 0.3-0.8% | 1-3% | 1.5-3.5% |

Crash windows, TQQQ (synthetic, % return over the window):

| Rule | 2008 | Covid 2020 | 2022 | Tariff 2025 | Oct-Nov 2026 |
|---|---:|---:|---:|---:|---:|
| Buy & hold | -94 | -69 | -81 | -57 | -23 |
| ATR 3x intraday | -48 | **-7** | -22 | -11 | -3 |
| ATR 3x close | -60 | -15 | -26 | -13 | -9 |
| SMA200 only | -42 | -56 | -46 | -32 | -32 |

## Findings

1. **Stops are insurance, not alpha.** Across 2010-2026, every stop rule earned less than
   buy & hold on every asset. About 80% of stop exits were bought back at a higher price.
   The payoff comes only from the few large crashes.
2. **Stops do protect in a crash, and intraday stops help most in fast ones.**
   - Covid 2020: TQQQ buy & hold lost 69%; an intraday ATR 3x stop lost 7%; the same stop
     checked at the close lost 15%; the SMA200 filter lost 56% because it was too slow.
   - 2008: buy & hold lost 94%; ATR 3x intraday lost 48%.
3. **For a 3x ETF, some exit rule is mandatory.** Synthetic TQQQ buy & hold from 2000 went
   to zero (-100%). SMA200, ATR 3-5x and SMA200 plus a 35% trail all kept it alive (+6 to
   +10% a year). Max drawdown still stayed at 85-98%: in 2000-2002 and 2008, repeated
   stop-and-rebuy cycles ground the account down.
4. **Tight stops (2x ATR, 10% trail) are the worst choice.** They fire 7-8 times a year,
   each round trip costs 2-11%, and they lose to wider stops on almost every asset and
   period.
5. **Stops do not work on SOXL.** Its volatility is so high that stops fire constantly and
   each round trip costs 10-13%. Only the SMA200 filter came close to buy & hold. SOXL buy
   & hold drew down 90%, and its synthetic history went to zero.
6. **Stacking a stop on top of the SMA200 filter made results worse,** because it doubles
   the whipsaw. The exception is a very wide catastrophe stop (35% trail), which fires
   about once every 3 years and kept the SMA200 result intact.
7. **Gaps are real but small on average.** 10-20% of stop exits fill at an opening gap.
   The average fill is 0.3-0.8% below the stop on SPY/QQQ and 1-3% on 3x ETFs, but single
   gaps are much larger (NVDA after-hours on 2026-11-11: -10%).

## What this means for the agentic account

- Code can manage stops reliably: ratchet the level daily and keep a broker-side stop
  order resting. The study shows the price of that protection.
- For TQQQ: the SMA200 trend filter is the base rule. Add a wide resting intraday stop
  (ATR 5x, or a 30-35% trail) at the broker as crash insurance against Covid-style drops,
  which SMA200 is too slow to catch. Avoid tight stops.
- For SPY/QQQ in a normal account: ATR 3x intraday or SMA200 roughly halves the drawdown
  for 2-3 points of CAGR.
- Options cannot be protected after hours. Single names have overnight gap risk, larger
  around earnings. No stop rule removes either: position size does.
