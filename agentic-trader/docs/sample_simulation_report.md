# Agentic Trader Simulation

- **Generated:** 2026-11-10T21:31:41
- **Data:** synthetic regime-switching market with earnings/macro gaps
- **Seeds:** [1, 2, 3, 4, 5] | **Symbols:** 12 | **Trading days:** 2016

Values are the mean across seeds; return and drawdown also show [min, max].

| Scenario | Return % | CAGR % | Max DD % | Sharpe | Closed trades | Open at end | Win % | Avg R | Worst R | Gap-thru stops | LLM calls/mo | Blocked | Bad orders executed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| no_stop | 118.85 [-80, 397] | 5.33 | 60.34 [33, 80] | 0.37 | 0 | 8 | – | 0.00 | 0.00 | 0 | 0.00 | 146 | 0 |
| fixed_8pct | 164.62 [-63, 499] | 7.89 | 54.93 [32, 75] | 0.47 | 59 | 7 | 0.00 | -1.11 | -2.56 | 15 | 0.00 | 275 | 0 |
| atr_trail_3x | 66.61 [-31, 133] | 5.61 | 20.06 [13, 34] | 0.56 | 349 | 4 | 38.82 | 0.17 | -2.83 | 67 | 0.00 | 101 | 0 |
| atr_trail_3x+agent | 68.03 [-32, 123] | 5.66 | 20.08 [12, 35] | 0.58 | 381 | 4 | 39.20 | 0.16 | -2.43 | 64 | 1.87 | 91 | 0 |
| atr_trail_3x+agent+macro | 50.72 [-30, 104] | 4.44 | 18.18 [11, 34] | 0.50 | 428 | 4 | 39.51 | 0.11 | -2.32 | 66 | 2.84 | 80 | 0 |
| agent+chaos (gated) | 68.03 [-32, 123] | 5.66 | 20.08 [12, 35] | 0.58 | 381 | 4 | 39.20 | 0.16 | -2.43 | 64 | 1.87 | 142 | 0 |
| agent+chaos (NO gate) | 87.39 [-47, 235] | 6.07 | 28.79 [16, 50] | 0.48 | 400 | 4 | 38.37 | 0.13 | -2.62 | 68 | 1.98 | 0 | 55 |

## Risk gate activity

**no_stop**

- 730x [code/entry] max open positions reached (N)
- 2x [code/entry] daily loss breaker: N% <= N%

**fixed_8pct**

- 1373x [code/entry] max open positions reached (N)
- 3x [code/entry] max entries per day reached (N)
- 1x [code/entry] daily loss breaker: N% <= N%

**atr_trail_3x**

- 487x [code/entry] max open positions reached (N)
- 19x [code/entry] max entries per day reached (N)

**atr_trail_3x+agent**

- 431x [code/entry] max open positions reached (N)
- 23x [code/entry] max entries per day reached (N)
- 1x [code/entry] daily loss breaker: N% <= N%

**atr_trail_3x+agent+macro**

- 372x [code/entry] max open positions reached (N)
- 26x [code/entry] max entries per day reached (N)
- 1x [code/entry] daily loss breaker: N% <= N%

**agent+chaos (gated)**

- 431x [code/entry] max open positions reached (N)
- 129x [chaos/entry] order notional N > cap N
- 129x [chaos/entry] position would be N% > N%
- 129x [chaos/entry] entry must carry a protective stop
- 128x [chaos/stop_update] cannot loosen stop from N to N
- 73x [chaos/entry] order notional N > cash N
- 23x [code/entry] max entries per day reached (N)
- 4x [chaos/entry] max open positions reached (N)

## How to read this

- **no_stop / fixed_8pct** have no trailing exit, so they degenerate into buy-and-hold of the first breakouts until max open positions is hit. Their return is mostly unrealized (see *Open at end*) and swings wildly between seeds; judge them on drawdown and the [min, max] range, not the mean.
- **Gap-thru stops**: stop exits filled at the open below the stop (overnight gap). No stop logic can prevent these; only position sizing and pre-event de-risking help.
- **LLM calls/mo**: how often Layer 1 would wake Claude. Each wake is one `claude -p` session in live mode.
- **agent+chaos**: the agent emits a harmful order (loosen a stop 20% or go all-in with no stop) on 30% of wake-ups. Compare gated vs NO gate to see what the risk-gate hook is worth.
- `+agent` reacts to earnings, gaps, drawdown and missing stops; `+macro` additionally tightens stops before every CPI/FOMC print.
- The agent scenarios use a deterministic proxy for the LLM, so it shows the value of the *policy* we would prompt Claude with, not of Claude's judgement.

## Assumptions and limits

- Daily bars; decisions at the close, orders fill from the next open. Bracket stops are live on the fill day.
- Slippage 5.0 bps per fill; no commissions; long only; whole shares; no dividends, borrow or taxes.
- Synthetic data is a stress test (regime switches, crash gaps, earnings gaps), not a forecast. Re-run on real CSV data with `--data-dir` before trusting any number.
- Entries are identical 20-day breakouts above the 50-day SMA in every scenario, so differences come from exit and risk handling only.
