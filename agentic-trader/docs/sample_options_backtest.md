# Options Agent Backtest

- Data: 12 symbols (AAPL, AMD, AMZN, AVGO, GOOGL, INTC, META, MSFT, NVDA, QQQ, SPY, TSLA), 2021-09-01 to 2026-11-10
- Start equity $50,000; each entry risks 2.0% of equity (the full premium); max 10% total premium at risk, 6 positions
- Calls on 20-day breakouts above the 50-day SMA, puts on breakdowns below it, ~35 DTE, at the money

| Scenario | Return % | CAGR % | Max DD % | Sharpe | Trades | Win % | Avg R | Worst R | Lost >=90% | Hold days | Blocked | Unfilled |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A. long option, no stop (exit at 5 DTE) | +47.5 | +7.8 | 23.8 | 0.44 | 246 | 35 | +0.05 | -1.00 | 101 | 33 | 434 | 110 |
| B. long option, -50% stop | +51.2 | +8.3 | 31.6 | 0.44 | 321 | 26 | +0.06 | -0.98 | 1 | 20 | 312 | 149 |
| C. long option, -50% stop, +100% take profit | -11.1 | -2.2 | 28.5 | -0.09 | 261 | 31 | -0.03 | -0.98 | 2 | 14 | 90 | 113 |
| D. long option, -50% stop + trailing [default] | +32.8 | +5.6 | 30.3 | 0.36 | 317 | 30 | +0.04 | -0.98 | 1 | 17 | 258 | 140 |
| E. D + stock-price stop (1.5 ATR) | +37.6 | +6.4 | 30.2 | 0.39 | 336 | 31 | +0.06 | -0.98 | 1 | 16 | 259 | 145 |
| F. debit vertical + D exits | -37.3 | -8.6 | 41.4 | -0.59 | 317 | 32 | -0.10 | -0.98 | 5 | 21 | 641 | 152 |
| G. D, calls only | +65.3 | +10.2 | 22.0 | 0.58 | 236 | 33 | +0.15 | -0.98 | 1 | 18 | 209 | 111 |
| H. D, IV = realized vol (cheap options) | +23.5 | +4.2 | 34.7 | 0.29 | 355 | 30 | +0.04 | -0.99 | 2 | 15 | 272 | 174 |
| I. D, IV = 1.4x realized (expensive options) | -8.9 | -1.8 | 30.7 | -0.04 | 208 | 28 | -0.05 | -0.96 | 1 | 18 | 54 | 61 |
| Stock baseline (shares, ATR 3x trailing) | +69.9 | +10.8 | 14.2 | 0.92 | 233 | 42 | +0.35 | -1.48 | – | – | 137 | – |

## Return by calendar year (%)

| Scenario | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---:|---:|---:|---:|---:|---:|
| A. long option, no stop (exit at 5 DTE) | +20.5 | -0.6 | +2.2 | +7.0 | +1.5 | +10.9 |
| D. long option, -50% stop + trailing [default] | +16.8 | -5.5 | -10.9 | +18.8 | -2.6 | +16.8 |
| Stock baseline (shares, ATR 3x trailing) | +9.7 | -6.4 | +19.6 | +14.0 | +13.0 | +7.4 |

## Exit reasons

- **A. long option, no stop (exit at 5 DTE)**: time_stop 246
- **B. long option, -50% stop**: stop_loss 218, time_stop 103
- **C. long option, -50% stop, +100% take profit**: stop_loss 174, take_profit 73, time_stop 14
- **D. long option, -50% stop + trailing [default]**: stop_loss 175, trailing_stop 99, time_stop 43
- **E. D + stock-price stop (1.5 ATR)**: stop_loss 143, trailing_stop 104, time_stop 46, underlying_stop 43
- **F. debit vertical + D exits**: stop_loss 172, time_stop 97, trailing_stop 48
- **G. D, calls only**: stop_loss 130, trailing_stop 61, time_stop 45
- **H. D, IV = realized vol (cheap options)**: stop_loss 197, trailing_stop 117, time_stop 41
- **I. D, IV = 1.4x realized (expensive options)**: stop_loss 129, trailing_stop 47, time_stop 32

## Model limits (read before trusting any number)

- No historical option chains: prices are Black-Scholes with implied vol = 20-day realized vol x 1.15 (scenarios H/I vary this). Real IV is usually above realized vol, is higher before earnings and collapses after (IV crush), and has skew. None of that is modelled, so long-option results are likely **optimistic**.
- Fills pay 2.5% of the option price each side (min $0.02); entries are limit orders that miss if the next open runs away. Real spreads on single-stock options are often wider, especially out of the money and near expiry.
- Daily bars: stops are checked at the close and filled at the next open, so gaps hit the exit.
- 12 large-cap tech names chosen today (survivorship and selection bias), one period.
