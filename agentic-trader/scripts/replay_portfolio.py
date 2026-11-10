#!/usr/bin/env python3
"""Replay real holdings through the agent: what would it have done since a given date?

Holdings are bought at the --start close. Bars before --start (include ~2 months) only
warm up ATR. No new entries are made; the run compares how each variant protects the
holdings.

Calendar JSON: [{"date": "2026-10-30", "kind": "earnings", "symbol": "INTC", "importance": 3}]
Use the first session that trades on the news as the date (the next day for after-close
reports).

Example:
    python3 agentic-trader/scripts/replay_portfolio.py --data-dir data/ohlcv \\
        --calendar data/events.json --start 2026-10-06 \\
        --hold NVDA:100 --hold INTC:100 --hold AMD:100
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agentic_trader.agent import RuleBasedAgentProxy  # noqa: E402
from agentic_trader.events import EventCalendar  # noqa: E402
from agentic_trader.monitor import MonitorConfig  # noqa: E402
from agentic_trader.risk_gate import load_rules  # noqa: E402
from agentic_trader.sim.data import load_csv_dir  # noqa: E402
from agentic_trader.sim.engine import SimConfig, SimResult, run_simulation  # noqa: E402
from agentic_trader.stops import AtrTrailingStop, NoStop  # noqa: E402


def parse_hold(text: str) -> tuple[str, float]:
    sym, _, qty = text.partition(":")
    if not sym or not qty:
        raise argparse.ArgumentTypeError("use SYMBOL:SHARES, e.g. NVDA:100")
    return sym.upper(), float(qty)


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--data-dir", type=Path, required=True)
    p.add_argument("--calendar", type=Path)
    p.add_argument("--start", type=date.fromisoformat, required=True)
    p.add_argument("--hold", type=parse_hold, action="append", required=True)
    p.add_argument("--extra-cash", type=float, default=0.0)
    p.add_argument("--rules", type=Path, default=ROOT / "config" / "sim_rules.yaml")
    p.add_argument("--slippage-bps", type=float, default=5.0)
    p.add_argument("--output-dir", type=Path, default=Path("reports"))
    return p.parse_args(argv)


def variants(rules):
    earnings_only = MonitorConfig(macro_min_importance=99)
    no_stop_rules = replace(rules, require_stop_on_entry=False)
    return [
        ("buy & hold", NoStop(), None, None, no_stop_rules),
        ("ATR 3x trailing (code only)", AtrTrailingStop(3), None, None, rules),
        ("ATR 3x + agent", AtrTrailingStop(3), RuleBasedAgentProxy(), earnings_only, rules),
        ("ATR 2x + agent", AtrTrailingStop(2), RuleBasedAgentProxy(), earnings_only, rules),
    ]


def per_symbol(res: SimResult, holds, closes) -> dict[str, dict]:
    out = {}
    for sym, qty in holds:
        seed = next(f for f in res.fills if f.kind == "seed" and f.symbol == sym)
        sells = [t for t in res.trades if t.symbol == sym]
        sold_qty = sum(t.qty for t in sells)
        value = sum(t.exit_price * t.qty for t in sells) + (qty - sold_qty) * closes[sym]
        out[sym] = {
            "cost": seed.price * qty,
            "value": value,
            "pnl": value - seed.price * qty,
            "exits": [
                {"date": str(t.exit_date), "price": t.exit_price, "qty": t.qty, "kind": t.exit_kind}
                for t in sells
            ],
        }
    return out


def render(start, end, holds, results, closes, main_name) -> str:
    lines = [
        f"# Portfolio Replay: {start} to {end}",
        "",
        "- Holdings bought at the close on the start date: "
        + ", ".join(f"{q:g} {s}" for s, q in holds),
        "- Daily bars; stops are broker-side; agent orders fill at the next open.",
        "",
        "| Variant | Final value | P&L | P&L % | Max DD % | LLM calls |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, (res, _) in results.items():
        start_eq, end_eq = res.equity_curve[0][1], res.equity_curve[-1][1]
        m = res.metrics()
        lines.append(
            f"| {name} | ${end_eq:,.0f} | ${end_eq - start_eq:+,.0f} | "
            f"{(end_eq / start_eq - 1) * 100:+.1f}% | {m['max_drawdown_pct']:.1f} | "
            f"{res.llm_wakeups} |"
        )
    lines += ["", "## Per symbol", ""]
    lines.append("| Variant | " + " | ".join(s for s, _ in holds) + " |")
    lines.append("|---|" + "---|" * len(holds))
    for name, (_, sym_rows) in results.items():
        cells = []
        for s, _ in holds:
            r = sym_rows[s]
            ex = r["exits"]
            how = (
                "held"
                if not ex
                else "; ".join(f"{e['kind']} {e['date'][5:]} @{e['price']:.2f}" for e in ex)
            )
            cells.append(f"${r['pnl']:+,.0f} ({how})")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")

    res = results[main_name][0]
    lines += ["", f"## What `{main_name}` did, day by day", ""]
    fills_by_day: dict[date, list[str]] = {}
    for f in res.fills:
        if f.kind != "seed":
            fills_by_day.setdefault(f.date, []).append(
                f"**FILL** {f.kind} {f.qty:g} {f.symbol} @ {f.price:.2f}"
            )
    acts_by_day: dict[date, list[str]] = {}
    for a in res.actions:
        i = a.intent
        what = (
            f"stop {i.symbol} -> {i.stop_price:.2f}"
            if i.purpose.value == "stop_update"
            else f"{i.purpose.value} {i.qty:g} {i.symbol} at next open"
        )
        why = i.note or ""
        acts_by_day.setdefault(a.date, []).append(f"[{i.source}] {what}" + (f" ({why})" if why else ""))
    wake_by_day = {e.date: e for e in res.agent_log}
    for d, _ in res.equity_curve:
        items = fills_by_day.get(d, []) + acts_by_day.get(d, [])
        if d in wake_by_day:
            items.insert(0, "**Claude woken**: " + "; ".join(wake_by_day[d].triggers))
        if items:
            lines.append(f"- **{d}** (closes: " + ", ".join(f"{s} {closes[d][s]:.2f}" for s, _ in holds) + ")")
            lines += [f"  - {x}" for x in items]
    lines += [
        "",
        "## Caveats",
        "",
        "- The agent is the deterministic rule proxy, not Claude itself; a real LLM would also "
        "read news and guidance.",
        "- Fills use daily OHLC: an intraday stop fills at the stop price (minus slippage), "
        "or at the open if the stock gaps below it.",
        "- Past replay, one month, three correlated stocks: anecdote, not evidence.",
    ]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    args = parse_args(argv)
    holds = args.hold
    data = load_csv_dir(args.data_dir, [s for s, _ in holds])
    missing = [s for s, _ in holds if s not in data]
    if missing:
        print(f"missing CSV for: {', '.join(missing)}", file=sys.stderr)
        return 1
    calendar = EventCalendar.from_json(args.calendar) if args.calendar else EventCalendar()
    rules = load_rules(args.rules)
    cfg = SimConfig(
        initial_cash=args.extra_cash,
        slippage_bps=args.slippage_bps,
        start_date=args.start,
        initial_positions=dict(holds),
        enable_entries=False,
    )
    closes = {b.date: {} for bars in data.values() for b in bars}
    for s, bars in data.items():
        for b in bars:
            closes[b.date][s] = b.close
    last = max(closes)

    results = {}
    for name, policy, agent, mon, r in variants(rules):
        res = run_simulation(
            data, calendar, r, policy, agent, scenario_name=name, monitor_config=mon, config=cfg
        )
        results[name] = (res, per_symbol(res, holds, closes[last]))

    md = render(args.start, last, holds, results, closes, "ATR 3x + agent")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"portfolio_replay_{args.start}_{last}"
    (args.output_dir / f"{stem}.md").write_text(md)
    (args.output_dir / f"{stem}.json").write_text(
        json.dumps(
            {
                name: {
                    "equity_curve": [(str(d), e) for d, e in res.equity_curve],
                    "per_symbol": rows,
                    "llm_wakeups": res.llm_wakeups,
                }
                for name, (res, rows) in results.items()
            },
            indent=2,
        )
    )
    print(md)
    print(f"Report: {args.output_dir / (stem + '.md')}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
