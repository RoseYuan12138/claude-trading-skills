# Agentic Trader

An event-driven trading agent for a **Robinhood agentic account** (Robinhood Trading MCP +
Claude Code), designed to run unattended on a Mac mini. Stop-loss handling is deterministic;
the LLM is only woken up for events that need judgement.

> **Status: simulation + risk gate only.** Nothing here places real orders yet. The live
> pieces (Layer 1 daemon, `claude -p` runner, snapshot writer) are on the roadmap below.

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

## Options agent (independent entries)

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
