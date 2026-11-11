# Agentic Trader

An event-driven trading agent for a **Robinhood agentic account** (Robinhood Trading MCP +
Claude Code), designed to run unattended on a Mac mini. Stop-loss handling is deterministic;
the LLM is only woken up for events that need judgement.

> **Status: simulation + risk gate only.** Nothing here places real orders yet. The live
> pieces (Layer 1 daemon, `claude -p` runner, snapshot writer) are on the roadmap below.

> **Latest research (2026-11-11): [docs/AGGRESSIVE_OPTIONS_STRATEGY.md](docs/AGGRESSIVE_OPTIONS_STRATEGY.md).**
> It reruns the option strategies on QQQ for 2001-2026 with VXN implied vol, the actual T-bill
> rate, dividends, strike skew and realistic bid-ask, after fixing a credit-spread pricing bug.
> Its conclusions supersede the earlier option sections below, which used realized-vol pricing.
> The robust aggressive setup is leveraged trend-following: LEAPS-style ITM QQQ calls
> (~15% ITM, ~270 days, rolled at 60) or QLD, held while SPY and QQQ are both above their
> 200-day SMAs. Today's ticket:
> `scripts/strategy_today.py --fetch --equity <$>`; refinements: `scripts/run_trend_variants.py`.

## Architecture

```
Layer 0  Robinhood (server side)   every position carries a stop / take-profit order
                                   -> survives a crashed Mac mini or a dead network
Layer 1  Python daemon (code)      every 1-5 min: ATR trailing stops, gap / volume / stop-
                                   proximity checks, event calendar, drawdown, heartbeat
                                   -> zero token cost; decides WHEN to wake Layer 2
Layer 2  Claude Code (`claude -p`) a few calls per month (sim: ~2): earnings, gaps on
                                   losing positions, drawdowns, missing stops
                                   -> acts through the Robinhood Trading MCP
Gate     PreToolUse hook (code)    every MCP order passes risk_gate.validate(); fail closed
```

Risk-reducing actions (exits, tightening a stop) are never blocked. Risk-increasing ones
(entries, loosening a stop) must pass every rule in `config/live_rules.yaml`.

## Layout

| Path | What |
|---|---|
| `agentic_trader/risk_gate.py` | Deterministic order validation (notional, position %, risk-to-stop, daily loss breaker, stop-only-tighten, symbol lists, halt) |
| `agentic_trader/stops.py` | Incremental Wilder ATR, fixed / ATR-trailing stop policies |
| `agentic_trader/monitor.py` | Layer 1 triggers + wake/cooldown logic |
| `agentic_trader/agent.py` | Layer 2 interface, `RuleBasedAgentProxy` (LLM stand-in for sims), `ChaosAgent` (injects bad orders) |
| `agentic_trader/hook.py` + `scripts/risk_gate_hook.py` | Claude Code PreToolUse hook for the Robinhood MCP |
| `agentic_trader/sim/` | Daily-bar broker (gap-aware stop fills), engine, synthetic market, report |
| `scripts/run_simulation.py` | Scenario comparison CLI |
| `agentic_trader/options.py` | Option orders: structure classification, options risk gate (defined risk only, premium budgets, DTE, spread, limit-only), exit rules |
| `agentic_trader/pricing.py` | Dependency-free Black-Scholes |
| `agentic_trader/sim/options_engine.py` | Simulator for an agent that opens its own option positions |
| `scripts/run_options_sim.py` | Options backtest on real OHLCV vs a stock baseline |
| `scripts/compare_entry_filters.py` | Entry-filter comparison (regime / earnings blackout / volume) on real data |
| `agentic_trader/market_score.py` | 0-100 market score and score tiers |
| `scripts/run_score_dip_calls.py` | Low-score QQQ calls, in and out of sample, VXN-priced |
| `scripts/run_score_strategy.py` | Score predictive check + score-tiered call/put backtest |
| `scripts/run_aggressive_options.py` | Sweep of option aggressiveness, stops and puts |
| `scripts/run_hedge_backtest.py` | Aggressive longs + regime-triggered QQQ put hedge |
| `scripts/run_system_backtest.py` | Whole-system backtest (long sleeve + bear setups) |
| `scripts/run_long_short_sim.py` | Long shares + regime-gated put sleeve backtest |
| `agentic_trader/playbook.py` + `scripts/strategy_today.py` | Today's action for the ITM trend-call strategy (and the QLD alternative) |
| `agentic_trader/sim/rotation.py` | Regime rotation and synthetic leveraged-ETF benchmarks |
| `scripts/run_aggressive_research.py` | Final QQQ option research, 2001-2026, with skew/cost sensitivity and parameter sweep |
| `scripts/run_combined_calls.py` | Breakout calls + dip calls, in and out of sample |
| `scripts/fetch_ohlcv.py` | Daily OHLCV from Yahoo Finance's chart API into CSVs |
| `scripts/replay_portfolio.py` | Replay real holdings from a start date: buy & hold vs stops vs agent, daily action log |
| `config/` | Risk rules (sim / live) and the MCP tool mapping |

## Quick start

```bash
# tests (from the repository root)
uv run --extra dev python -m pytest agentic-trader/tests -q

# synthetic stress test: 7 scenarios x 5 seeds x 8 years x 12 symbols (~10 s)
python3 agentic-trader/scripts/run_simulation.py --seeds 5 --output-dir reports/

# real data: one <SYMBOL>.csv per symbol (date,open,high,low,close,volume),
# optional events JSON: [{"date": "2026-01-28", "kind": "earnings", "symbol": "AAPL", "importance": 3}]
python3 agentic-trader/scripts/run_simulation.py --data-dir data/ohlcv --calendar data/events.json
```

Replay real holdings (bought at the `--start` close; earlier bars only warm up ATR):

```bash
python3 agentic-trader/scripts/replay_portfolio.py --data-dir data/ohlcv --calendar data/events.json \
    --start 2026-10-06 --hold NVDA:100 --hold INTC:100 --hold AMD:100
```

## What the first simulation says

Synthetic data only (see `docs/sample_simulation_report.md`). Treat the numbers as a sanity
check of the mechanics, not as a forecast:

- **ATR trailing stop vs no stop / fixed stop:** max drawdown 20% vs 55-60%, and a much tighter
  range across seeds. The mean return is lower because the no-stop variants become buy-and-hold
  of the first breakouts. A trailing stop limits drawdown; it doesn't raise returns.
- **Agent on earnings / gaps / drawdowns:** same return and drawdown, worst trade -2.8R -> -2.4R,
  about 2 LLM calls per month.
- **Tightening before every CPI / FOMC print hurts:** -17 points of return from whipsaw. Off by
  default.
- **Risk gate vs a misbehaving agent** (bad order on 30% of wake-ups): gated, 0 of the bad orders
  executed and the results match the clean agent. Ungated, 55 executed: max drawdown 20% -> 29%
  (worst seed 35% -> 50%) and Sharpe 0.58 -> 0.48. The mean return was higher only because random
  concentration paid off in a rising synthetic market.
- About 19% of stop exits filled at an open below the stop. Stops can't prevent overnight gaps;
  position sizing and de-risking before events are what limit them.

## Entry filters (shares)

`SimConfig` options, all off by default: `regime_symbol` / `regime_sma` (no new entries while
the benchmark closes below its SMA), `earnings_blackout_days`, `volume_confirm_mult`, and
`untradable` (keep a benchmark for the filter without trading it). `infer_earnings_calendar`
rebuilds past report dates from volume spikes plus gaps. It got about 60% of the 2024 dates
right, so pass a real calendar with `--calendar` when you have one.

Results (`docs/sample_entry_filters.md`; 10 large-cap tech stocks, 2021-09 to 2026-11; Sharpe
compared on 6 random 8-stock subsets):

| Filter | Return (all) | Max DD (all) | Sharpe (all) | Beats no-filter |
|---|---:|---:|---:|---:|
| none | +60% | 14.1% | 0.87 | – |
| SPY > 50d SMA | +58% | **10.6%** | 0.86 | **6 / 6** |
| breakout volume >= 1.5x | +47% | **8.1%** | **0.96** | 4 / 6 |
| SPY > 200d SMA | +52% | 13.7% | 0.80 | 0 / 6 |
| earnings blackout 7d (inferred dates) | +50% | 13.6% | 0.78 | 0 / 6 |
| 50d regime + volume (in-sample pick) | +41% | 7.7% | 0.87 | 1 / 6 |

The 50-day regime filter is the one change that helped on every subset: same return, lower
drawdown. Volume confirmation halves drawdown but also trades and return. The 200-day filter
reacts too slowly, and stacking filters over-restricts.

## Options agent (independent entries)

> Superseded by [docs/AGGRESSIVE_OPTIONS_STRATEGY.md](docs/AGGRESSIVE_OPTIONS_STRATEGY.md): the results below used realized-vol option pricing.

The agent may open its own calls and puts (and verticals). Hard rules in
`agentic_trader/options.py`, enforced before any order:

- Defined risk only: long calls / puts and same-expiry verticals. Naked short options are
  rejected **even if listed in the config**.
- Worst-case loss per order <= 2% of equity, total worst-case open risk <= 10%, <= 6 positions,
  <= 3 entries a day, 5% daily loss breaker, cash must cover the worst case.
- Limit orders only, 7-90 DTE, per-leg bid-ask spread <= 10% of mid, <= 20 contracts.
- Closing orders always pass, as long as they only reduce held legs.

Exits (code layer, `OptionExitRules`): -50% premium stop, trailing stop armed at +50% (35% below
the peak, never below breakeven), time stop at 5 DTE, optional stock-price stop.

First backtest (`docs/sample_options_backtest.md`; 12 large-cap tech names, 2021-09 to 2026-11,
Black-Scholes prices). Medians across 6 random 8-symbol subsets:

| Variant | Median return | Median max DD | Median Sharpe | Subsets < 0 |
|---|---:|---:|---:|---:|
| Options, no stop (exit at 5 DTE) | +6% | 25% | 0.15 | 3 of 6 |
| Options, -50% stop + trailing | +30% | 25% | 0.36 | 0 of 6 |
| Same, but IV priced at 1.4x realized vol | +9% | 25% | 0.19 | 1 of 6 |
| Shares, ATR 3x trailing (baseline) | +53% | 11% | 0.91 | 0 of 6 |

Stops matter more for options than for shares: without them, 101 of 246 trades lost at least 90%
of the premium. The edge is thin and depends mostly on what the options cost: the model has no
IV crush or skew, so real results are likely worse. Capping winners (+100% take profit) and
debit verticals with these exits both lost money.

### Bearish bets with puts (no stock needed)

`OptionSimConfig(regime_symbol="SPY", regime_sma=50)` allows calls only while SPY is above its
50-day SMA and puts only while it is below; `allow_calls=False` gives a puts-only sleeve.
`scripts/run_long_short_sim.py` adds such a sleeve to the long-shares agent.

Result on the same data (`docs/sample_long_short_backtest.md`): **the put sleeve did not
help.** Puts won 16-20% of the time and lost money in every year except 2024, including the
2022 bear market. A 10% sleeve left drawdown roughly unchanged (10.6% -> 10.1%) and cut return
by about 4 points. Wider stops, a stock-price stop, 60 DTE, or no stops at all all still lost.
The reasons: puts bought after a breakdown pay for already high volatility, and bear-market
rallies of 5%+ are common, which is all it takes to halve an at-the-money put. Puts are also
usually priced above this model (skew). In this period the best bear-market defense was simply
not buying: the 50-day regime filter on longs.

## Full system backtest

`scripts/run_system_backtest.py` puts it all together: 80% long shares (SPY 50d filter, ATR
trailing stop, agent proxy woken on events) plus a 20% bear sleeve that buys put debit spreads
only on clear setups (earnings-day gap down, failed rally in a downtrend), skipping entries near
earnings, at IV > 80%, or more than 20% below the 50d SMA. `OptionSimConfig.signal_mode =
"bear_setups"` implements the bear setups; multi-leg orders are checked against a package
bid-ask cap (`max_package_spread_pct`).

Result (`docs/sample_system_backtest.md`, 2021-09 to 2026-11):

| Variant | Return | Max DD | Sharpe | Entries / month |
|---|---:|---:|---:|---:|
| shares + SPY 50d filter | +59% | 10.7% | 0.86 | 3.3 |
| + agent proxy | +50% | 10.2% | 0.81 | 3.7 |
| full system (+ bear sleeve) | +27% | 11.4% | 0.54 | 5.2 |
| bear sleeve alone | -32% | 33.1% | -0.86 | 1.5 |
| SPY buy & hold | +66% | 25.4% | 0.66 | – |

The simplest version (shares + regime filter) is the best. With inferred, noisy earnings dates
the agent proxy cost about 9 points. Failed-rally puts lost money (25% win rate), and the
earnings-gap setup fired only 7 times. The bear sleeve made no trades in the Oct-Nov 2026 drop:
the IV and "already extended" filters excluded exactly the shorts that would have paid.

## Aggressive in bull regimes + index put hedge

`OptionSimConfig(signal_mode="index_hedge", exit_on_regime_bull=True)` holds a QQQ put while
SPY is below its 50d SMA and closes it when SPY closes back above. Run it with
`scripts/run_hedge_backtest.py` (`docs/sample_hedge_backtest.md`).

How fast does the 50d signal react? Since 2021-09 it caught all five SPY declines of 8% or more,
4-15 days after the peak with SPY down 2-4% (2026-10-16 this time, -2.0%). But it flips about 9
times a year, and two thirds of those flips are false alarms (no further 5% drop).

| Variant | Return | Max DD | Sharpe | 2022 | Oct-Nov 2026 |
|---|---:|---:|---:|---:|---:|
| normal longs + 50d filter | +59% | 10.7% | 0.86 | -6.0% | -4.9% |
| **aggressive longs** + filter (1.25% risk, 10 positions) | **+92%** | 15.9% | 0.88 | -9.8% | -6.6% |
| aggressive + QQQ put hedge (1% premium per signal) | +81% | 15.5% | 0.83 | -9.3% | -6.5% |
| QQQ buy & hold | +77% | 35.6% | 0.60 | -33.1% | -11.2% |
| QQQ 90% + put hedge 1% | +65% | 33.0% | 0.58 | -30.8% | -10.9% |
| QQQ 90% + 10% cash | +70% | 32.2% | 0.59 | -29.9% | -10.6% |

Taking more risk in bull regimes paid off here, though on stocks chosen with hindsight. The put
hedge did not: on the trading account the regime filter and stops are already the hedge (the
book is mostly in cash when puts are bought), and on a buy-and-hold core, plain cash beat the
puts. The hedge costs 4.6-7.6% of equity over five years because two thirds of its signals are
false alarms and it buys after the drop has begun, when puts are expensive.

## Aggressive option buying sweep

> Superseded by [docs/AGGRESSIVE_OPTIONS_STRATEGY.md](docs/AGGRESSIVE_OPTIONS_STRATEGY.md): the results below used realized-vol option pricing.

`scripts/run_aggressive_options.py` (`docs/sample_aggressive_options.md`) sweeps premium per trade
(2/5/10%), total premium cap (10/25/50%), puts on/off and stops on/off: calls on breakouts while
SPY is above its 50d SMA, puts on breakdowns while it is below.

- **Calls only, with a stop:** every size made money, but drawdowns grow fast: 2% per trade
  +31-60% with a 31-33% max drawdown; 10% per trade with one position at a time +159% with 51%.
- **Adding puts lost money in almost every configuration** (the bear-regime puts bled in false
  alarms), even though they made +13-57% in Oct-Nov 2026.
- **Bigger total caps blow up:** at 10% per trade with a 50% cap, the account fell to 1-21% of
  its start. Without stops, results were worse in most rows.
- **Everything depends on option prices.** The best row (10% per trade, calls) is +397% if
  options cost realized vol, +159% at 1.15x (the default), and +71-75% at 1.3-1.4x, about SPY's
  +66% but with a ~50% drawdown. At 1.4x the 2% and 5% rows lose money. Single-stock IV usually
  trades above realized vol, and well above it before earnings, so real chains are needed.

## Market score -> call/put tiers

> Superseded by [docs/AGGRESSIVE_OPTIONS_STRATEGY.md](docs/AGGRESSIVE_OPTIONS_STRATEGY.md): the results below used realized-vol option pricing.

`agentic_trader/market_score.py` computes a 0-100 score as the equal-weight mean of trend (SPY vs
50d/200d), breadth, 20d momentum, distance from the 1y high, VIX, and HYG vs its 50d (use
`fetch_ohlcv.py --adjusted` for HYG). `OptionSimConfig.score_tiers` lets each day's score choose
whether calls or puts are allowed and how large to trade. Run it with
`scripts/run_score_strategy.py` (`docs/sample_score_strategy.md`). The weights and tiers were
fixed before testing.

- **The score measures risk, not direction.** Below 30, QQQ's median next-20-day return was
  +2.9%, against +1.5% at 70 or above. But the chance of a 5%+ drop along the way was 58%,
  against 27%.
- **Tiers by score did worse than fixed settings:** +12% (calls 5%/2% by score, puts below 30)
  vs +86% for fixed 5% calls gated by SPY > 50d. Dropping the puts gave +24%. Results swing
  from +35% to -15% when the thresholds move 10 points, and lose money at 1.4x IV.
- Use it as a risk thermometer (for example, to scale size or tighten stops). Do not use it as a
  call/put switch. "Buy calls when the score is low" fits this data, but it was found in-sample,
  so it is a hypothesis for the forward paper test, not a rule.

### Low score -> buy QQQ calls (out-of-sample test)

`OptionSimConfig(signal_mode="score_dip", dip_threshold=30)` buys an ATM 45-DTE QQQ call when the
score is below the threshold and the account is flat; `iv_overrides` prices QQQ options off the
actual VXN. `scripts/run_score_dip_calls.py` (`docs/sample_score_dip_calls.md`) fixes the rule,
then tests it on 2011-2021 (out of sample) and 2021-2026 (where the idea came from).

- Average result per trade: +0.34R out of sample (27 trades) and +0.27R in sample (19). Buying
  calls on any day averaged +0.09R / +0.04R, and buying only when the score is above 70,
  +0.06R. Pooled t of about 1.8; trades cluster in a few selloffs, so treat this as suggestive,
  not proven.
- Low scores are rare, so the money sits idle about 80% of the time: +14% over 2011-2021 at 2% per
  trade (+38% at 5%), against +587% for QQQ buy & hold. This is an add-on, not a standalone
  strategy. Stops helped (+5% without). The threshold is kept at 30: 20 looked better out of
  sample but lost in sample.

## Going live on the Mac mini (planned steps)

1. Enable agentic trading in the Robinhood app and **fund the agent account only with money you
   can afford to lose**. The account boundary is the hardest limit.
2. `claude mcp add` the Robinhood Trading MCP, then ask Claude Code to list its tools and input
   schemas. Fix every name in `config/mcp_tool_map.yaml`, which currently holds placeholders.
   Unknown tools on that server are blocked.
3. Register the hook in the Claude Code settings used for trading:
   ```json
   {"hooks": {"PreToolUse": [{"matcher": "mcp__robinhood__.*",
     "hooks": [{"type": "command",
                "command": "python3 /ABSOLUTE/PATH/agentic-trader/scripts/risk_gate_hook.py"}]}]}}
   ```
   Every decision is appended to `state/hook_audit.jsonl`.
4. Keep `state/account_snapshot.json` fresh (see schema below). If it is older than 15 minutes,
   entries and stop changes are blocked and exits still pass.
5. Mac mini: `sudo pmset -a sleep 0 disksleep 0`, turn on auto-restart after power failure,
   turn off automatic macOS update restarts, run the daemon under launchd `KeepAlive`, and send
   heartbeats to your phone.

Snapshot schema:

```json
{"as_of": "2026-11-10T15:00:00+00:00", "equity": 20000, "cash": 10000,
 "day_start_equity": 20000, "entries_today": 0, "halted": false,
 "positions": {"AAPL": {"qty": 10, "avg_price": 200, "last_price": 210, "stop_price": 195}},
 "quotes": {"MSFT": 400}}
```

## Roadmap

- [ ] **Snapshot writer that the agent can't tamper with**: a PostToolUse hook that builds the
      snapshot from real MCP responses (positions / orders / quotes), plus permission deny
      rules on `state/**`. Today, anything that can write the file could fool the gate.
- [ ] Layer 1 daemon (launchd): price feed, ATR trailing, monitor, heartbeat, "unprotected
      position" alarm (needed because `cancel_policy: allow` opens a gap between cancel and
      replace).
- [ ] `claude -p` runner: trigger context in the prompt, existing skills (earnings-calendar,
      market-news-analyst, exposure-coach, position-sizer) for analysis.
- [ ] Map the Robinhood MCP option-order tool into the hook (option orders are blocked as
      unknown tools until then) and validate them with `validate_option`.
- [ ] Options backtest with real historical chains (IV, skew, earnings crush).
- [ ] Re-run the simulation on real OHLCV + real earnings/macro calendars.
- [ ] Intraday bars in the simulator; limit orders; partial fills.

## Known simulation limits

Daily bars; fills from the next open; slippage 5 bps; no commissions, dividends or taxes; long
only; whole shares; entries are identical 20-day breakouts in every scenario. The LLM is
modelled by a deterministic rule proxy, so results show the value of the *policy* we would
prompt Claude with, not of Claude's own judgement.
