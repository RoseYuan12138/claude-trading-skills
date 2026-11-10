#!/usr/bin/env python3
"""Backtest an agent that opens its own option positions, on real daily OHLCV.

Calls on 20-day breakouts above the 50-day SMA, puts on breakdowns below it, about
35 DTE at the money. Each entry risks ``--risk-pct`` of equity (the full premium).
Compares exit rules, structures and implied-vol assumptions against a stock baseline.

Example:
    python3 agentic-trader/scripts/fetch_ohlcv.py --symbols SPY QQQ NVDA AMD \\
        --start 2021-06-01 --out-dir data/ohlcv
    python3 agentic-trader/scripts/run_options_sim.py --data-dir data/ohlcv --start 2021-09-01
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agentic_trader.events import EventCalendar  # noqa: E402
from agentic_trader.options import OptionExitRules, OptionRules  # noqa: E402
from agentic_trader.risk_gate import load_rules  # noqa: E402
from agentic_trader.sim.data import load_csv_dir  # noqa: E402
from agentic_trader.sim.engine import SimConfig, run_simulation  # noqa: E402
from agentic_trader.sim.options_engine import OptionSimConfig, OptionSimulator  # noqa: E402
from agentic_trader.stops import AtrTrailingStop  # noqa: E402

NO_STOP = OptionExitRules(stop_loss_pct=None, trail_after_pct=None, time_stop_dte=5)
STOP50 = OptionExitRules(stop_loss_pct=50, trail_after_pct=None, time_stop_dte=5)
STOP_TP = OptionExitRules(stop_loss_pct=50, take_profit_pct=100, trail_after_pct=None)
TRAIL = OptionExitRules(stop_loss_pct=50, trail_after_pct=50, trail_pct=35, time_stop_dte=5)
TRAIL_U = OptionExitRules(
    stop_loss_pct=50, trail_after_pct=50, trail_pct=35, time_stop_dte=5, underlying_stop_atr=1.5
)

COLUMNS = [
    ("total_return_pct", "Return %", "{:+.1f}"),
    ("cagr_pct", "CAGR %", "{:+.1f}"),
    ("max_drawdown_pct", "Max DD %", "{:.1f}"),
    ("sharpe", "Sharpe", "{:.2f}"),
    ("trades", "Trades", "{:.0f}"),
    ("win_rate_pct", "Win %", "{:.0f}"),
    ("avg_r", "Avg R", "{:+.2f}"),
    ("worst_r", "Worst R", "{:+.2f}"),
    ("lost_90pct_plus", "Lost >=90%", "{:.0f}"),
    ("avg_hold_days", "Hold days", "{:.0f}"),
]


def scenarios(base: OptionSimConfig):
    def cfg(**kw):
        return OptionSimConfig(**{**base.__dict__, **kw})

    return [
        ("A. long option, no stop (exit at 5 DTE)", NO_STOP, cfg()),
        ("B. long option, -50% stop", STOP50, cfg()),
        ("C. long option, -50% stop, +100% take profit", STOP_TP, cfg()),
        ("D. long option, -50% stop + trailing [default]", TRAIL, cfg()),
        ("E. D + stock-price stop (1.5 ATR)", TRAIL_U, cfg()),
        ("F. debit vertical + D exits", TRAIL, cfg(structure="debit_vertical")),
        ("G. D, calls only", TRAIL, cfg(allow_puts=False)),
        ("H. D, IV = realized vol (cheap options)", TRAIL, cfg(iv_premium=1.0)),
        ("I. D, IV = 1.4x realized (expensive options)", TRAIL, cfg(iv_premium=1.4)),
    ]


def yearly(curve: list[tuple[date, float]]) -> dict[int, float]:
    out: dict[int, float] = {}
    first: dict[int, float] = {}
    last: dict[int, float] = {}
    prev_end = None
    for d, e in curve:
        if d.year not in first:
            first[d.year] = prev_end if prev_end is not None else e
        last[d.year] = e
        prev_end = e
    for y in first:
        out[y] = (last[y] / first[y] - 1) * 100
    return out


def fmt(v: float, spec: str) -> str:
    return "–" if v != v else spec.format(v)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--data-dir", type=Path, required=True)
    p.add_argument("--start", type=date.fromisoformat, required=True)
    p.add_argument("--initial-cash", type=float, default=50_000.0)
    p.add_argument("--risk-pct", type=float, default=2.0)
    p.add_argument("--output-dir", type=Path, default=Path("reports"))
    args = p.parse_args(argv)

    data = load_csv_dir(args.data_dir)
    rules = OptionRules(max_loss_per_trade_pct=args.risk_pct)
    base = OptionSimConfig(
        initial_cash=args.initial_cash, risk_per_trade_pct=args.risk_pct, start_date=args.start
    )

    rows, curves, exits_by = [], {}, {}
    for name, exits, cfg in scenarios(base):
        res = OptionSimulator(data, rules, exits, cfg, name).run()
        rows.append((name, res.metrics(), sum(res.blocked.values()), res.unfilled_entries))
        curves[name] = res.equity_curve
        exits_by[name] = Counter(t.reason for t in res.trades)

    # Stock baseline: same signals' spirit, shares with an ATR trailing stop.
    stock_rules = load_rules(ROOT / "config" / "sim_rules.yaml")
    stock_cfg = SimConfig(initial_cash=args.initial_cash, start_date=args.start)
    stock = run_simulation(data, EventCalendar(), stock_rules, AtrTrailingStop(3), config=stock_cfg)
    sm = stock.metrics()
    curves["Stock baseline (shares, ATR 3x trailing)"] = stock.equity_curve

    first, last = curves[rows[0][0]][0][0], curves[rows[0][0]][-1][0]
    lines = [
        "# Options Agent Backtest",
        "",
        f"- Data: {len(data)} symbols ({', '.join(sorted(data))}), {first} to {last}",
        f"- Start equity ${args.initial_cash:,.0f}; each entry risks {args.risk_pct}% of equity "
        "(the full premium); max 10% total premium at risk, 6 positions",
        "- Calls on 20-day breakouts above the 50-day SMA, puts on breakdowns below it, "
        "~35 DTE, at the money",
        "",
        "| Scenario | " + " | ".join(c[1] for c in COLUMNS) + " | Blocked | Unfilled |",
        "|---|" + "---:|" * (len(COLUMNS) + 2),
    ]
    for name, m, blocked, unfilled in rows:
        lines.append(
            f"| {name} | "
            + " | ".join(fmt(m[k], spec) for k, _, spec in COLUMNS)
            + f" | {blocked} | {unfilled} |"
        )
    lines.append(
        "| Stock baseline (shares, ATR 3x trailing) | "
        f"{sm['total_return_pct']:+.1f} | {sm['cagr_pct']:+.1f} | {sm['max_drawdown_pct']:.1f} | "
        f"{sm['sharpe']:.2f} | {sm['trades']:.0f} | {fmt(sm['win_rate_pct'], '{:.0f}')} | "
        f"{sm['avg_r']:+.2f} | {sm['worst_r']:+.2f} | – | – | {sm['blocked_intents']:.0f} | – |"
    )

    focus = [
        "A. long option, no stop (exit at 5 DTE)",
        "D. long option, -50% stop + trailing [default]",
        "Stock baseline (shares, ATR 3x trailing)",
    ]
    years = sorted({d.year for d, _ in curves[focus[0]]})
    lines += ["", "## Return by calendar year (%)", ""]
    lines.append("| Scenario | " + " | ".join(str(y) for y in years) + " |")
    lines.append("|---|" + "---:|" * len(years))
    for name in focus:
        y = yearly(curves[name])
        lines.append(f"| {name} | " + " | ".join(f"{y.get(yr, 0):+.1f}" for yr in years) + " |")

    lines += ["", "## Exit reasons", ""]
    for name, c in exits_by.items():
        lines.append(f"- **{name}**: " + ", ".join(f"{k} {v}" for k, v in c.most_common()))

    lines += [
        "",
        "## Model limits (read before trusting any number)",
        "",
        "- No historical option chains: prices are Black-Scholes with implied vol = 20-day "
        "realized vol x 1.15 (scenarios H/I vary this). Real IV is usually above realized vol, "
        "is higher before earnings and collapses after (IV crush), and has skew. None of that "
        "is modelled, so long-option results are likely **optimistic**.",
        "- Fills pay 2.5% of the option price each side (min $0.02); entries are limit orders "
        "that miss if the next open runs away. Real spreads on single-stock options are often "
        "wider, especially out of the money and near expiry.",
        "- Daily bars: stops are checked at the close and filled at the next open, so gaps hit "
        "the exit.",
        "- 12 large-cap tech names chosen today (survivorship and selection bias), one period.",
    ]
    md = "\n".join(lines) + "\n"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"options_agent_backtest_{last}"
    (args.output_dir / f"{stem}.md").write_text(md)
    (args.output_dir / f"{stem}.json").write_text(
        json.dumps(
            {name: {k: (None if v != v else v) for k, v in m.items()} for name, m, _, _ in rows},
            indent=2,
        )
    )
    print(md)
    print(f"Report: {args.output_dir / (stem + '.md')}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
