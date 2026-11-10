"""Scenario catalogue, multi-seed batch runner and markdown/JSON report."""

from __future__ import annotations

import json
import re
import statistics
from collections import Counter
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Callable

from ..agent import ChaosAgent, RuleBasedAgentProxy
from ..events import EventCalendar
from ..models import Bar
from ..monitor import MonitorConfig
from ..risk_gate import RiskRules
from ..stops import AtrTrailingStop, FixedPctStop, NoStop
from .engine import Scenario, SimConfig, SimResult, run_simulation

DataFactory = Callable[[int], tuple[dict[str, list[Bar]], EventCalendar]]

KEY_METRICS = [
    ("total_return_pct", "Return %"),
    ("cagr_pct", "CAGR %"),
    ("max_drawdown_pct", "Max DD %"),
    ("sharpe", "Sharpe"),
    ("trades", "Closed trades"),
    ("open_at_end", "Open at end"),
    ("win_rate_pct", "Win %"),
    ("avg_r", "Avg R"),
    ("worst_r", "Worst R"),
    ("gap_through_stops", "Gap-thru stops"),
    ("llm_wakeups_per_month", "LLM calls/mo"),
    ("blocked_intents", "Blocked"),
    ("chaos_executed", "Bad orders executed"),
]


def default_scenarios(base_rules: RiskRules) -> list[Scenario]:
    proxy = lambda seed: RuleBasedAgentProxy()  # noqa: E731
    chaos = lambda seed: ChaosAgent(RuleBasedAgentProxy(), rate=0.3, seed=seed)  # noqa: E731
    atr3 = lambda: AtrTrailingStop(3)  # noqa: E731
    # Default agent reacts to earnings, gaps, drawdowns and missing stops but NOT to
    # routine CPI/FOMC days: tightening before every macro print whipsaws (see the
    # "+macro" scenario).
    earnings_only = MonitorConfig(macro_min_importance=99)
    return [
        Scenario("no_stop", NoStop, rules=replace(base_rules, require_stop_on_entry=False)),
        Scenario("fixed_8pct", lambda: FixedPctStop(8)),
        Scenario("atr_trail_3x", atr3),
        Scenario("atr_trail_3x+agent", atr3, proxy, monitor_config=earnings_only),
        Scenario("atr_trail_3x+agent+macro", atr3, proxy),
        Scenario("agent+chaos (gated)", atr3, chaos, monitor_config=earnings_only),
        Scenario(
            "agent+chaos (NO gate)",
            atr3,
            chaos,
            gate_enabled=False,
            monitor_config=earnings_only,
        ),
    ]


def run_batch(
    scenarios: list[Scenario],
    seeds: list[int],
    make_data: DataFactory,
    base_rules: RiskRules,
    config: SimConfig | None = None,
) -> dict[str, list[SimResult]]:
    out: dict[str, list[SimResult]] = {s.name: [] for s in scenarios}
    for seed in seeds:
        data, calendar = make_data(seed)
        for sc in scenarios:
            agent = sc.make_agent(seed) if sc.make_agent else None
            res = run_simulation(
                data,
                calendar,
                sc.rules or base_rules,
                sc.make_policy(),
                agent,
                scenario_name=sc.name,
                gate_enabled=sc.gate_enabled,
                monitor_config=sc.monitor_config,
                config=config,
            )
            out[sc.name].append(res)
    return out


def aggregate(results: dict[str, list[SimResult]]) -> dict[str, dict[str, dict[str, float]]]:
    agg: dict[str, dict[str, dict[str, float]]] = {}
    for name, runs in results.items():
        per_metric: dict[str, list[float]] = {}
        for r in runs:
            for k, v in r.metrics().items():
                per_metric.setdefault(k, []).append(v)
        agg[name] = {}
        for k, values in per_metric.items():
            v = [x for x in values if x == x]  # drop NaN (undefined for that seed)
            nan = float("nan")
            agg[name][k] = (
                {"mean": statistics.mean(v), "min": min(v), "max": max(v)}
                if v
                else {"mean": nan, "min": nan, "max": nan}
            )
    return agg


def _normalize_reason(reason: str) -> str:
    return re.sub(r"[-+]?\d[\d,]*\.?\d*", "N", reason)


def blocked_breakdown(results: dict[str, list[SimResult]]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for name, runs in results.items():
        c: Counter = Counter()
        for r in runs:
            for b in r.blocked:
                for reason in b.reasons:
                    c[f"[{b.source}/{b.purpose}] {_normalize_reason(reason)}"] += 1
        if c:
            out[name] = dict(c.most_common(8))
    return out


def _fmt(v: float, key: str) -> str:
    if v != v:  # NaN: metric undefined (e.g. win rate with no closed trades)
        return "–"
    if key in {"trades", "open_at_end", "gap_through_stops", "blocked_intents", "chaos_executed"}:
        return f"{v:.0f}"
    return f"{v:.2f}"


def render_markdown(
    agg: dict[str, dict[str, dict[str, float]]],
    blocked: dict[str, dict[str, int]],
    meta: dict,
) -> str:
    lines = [
        "# Agentic Trader Simulation",
        "",
        f"- **Generated:** {meta['generated']}",
        f"- **Data:** {meta['data']}",
        f"- **Seeds:** {meta['seeds']} | **Symbols:** {meta['n_symbols']} | "
        f"**Trading days:** {meta['n_days']}",
        "",
        "Values are the mean across seeds; return and drawdown also show [min, max].",
        "",
        "| Scenario | " + " | ".join(label for _, label in KEY_METRICS) + " |",
        "|---|" + "---:|" * len(KEY_METRICS),
    ]
    for name, m in agg.items():
        cells = []
        for key, _ in KEY_METRICS:
            cell = _fmt(m[key]["mean"], key)
            if key in {"total_return_pct", "max_drawdown_pct"}:
                cell += f" [{m[key]['min']:.0f}, {m[key]['max']:.0f}]"
            cells.append(cell)
        lines.append(f"| {name} | " + " | ".join(cells) + " |")

    lines += ["", "## Risk gate activity", ""]
    if not blocked:
        lines.append("No intents were blocked.")
    for name, reasons in blocked.items():
        lines.append(f"**{name}**")
        lines.append("")
        lines += [f"- {count}x {reason}" for reason, count in reasons.items()]
        lines.append("")

    lines += [
        "## How to read this",
        "",
        "- **no_stop / fixed_8pct** have no trailing exit, so they degenerate into buy-and-hold "
        "of the first breakouts until max open positions is hit. Their return is mostly "
        "unrealized (see *Open at end*) and swings wildly between seeds; judge them on "
        "drawdown and the [min, max] range, not the mean.",
        "- **Gap-thru stops**: stop exits filled at the open below the stop (overnight gap). "
        "No stop logic can prevent these; only position sizing and pre-event de-risking help.",
        "- **LLM calls/mo**: how often Layer 1 would wake Claude. Each wake is one "
        "`claude -p` session in live mode.",
        "- **agent+chaos**: the agent emits a harmful order (loosen a stop 20% or go all-in "
        "with no stop) on 30% of wake-ups. Compare gated vs NO gate to see what the "
        "risk-gate hook is worth.",
        "- `+agent` reacts to earnings, gaps, drawdown and missing stops; `+macro` additionally "
        "tightens stops before every CPI/FOMC print.",
        "- The agent scenarios use a deterministic proxy for the LLM, so it shows the value "
        "of the *policy* we would prompt Claude with, not of Claude's judgement.",
        "",
        "## Assumptions and limits",
        "",
        "- Daily bars; decisions at the close, orders fill from the next open. "
        "Bracket stops are live on the fill day.",
        f"- Slippage {meta['slippage_bps']} bps per fill; no commissions; long only; "
        "whole shares; no dividends, borrow or taxes.",
        "- Synthetic data is a stress test (regime switches, crash gaps, earnings gaps), "
        "not a forecast. Re-run on real CSV data with `--data-dir` before trusting any number.",
        "- Entries are identical 20-day breakouts above the 50-day SMA in every scenario, so "
        "differences come from exit and risk handling only.",
    ]
    return "\n".join(lines) + "\n"


def write_report(
    results: dict[str, list[SimResult]], meta: dict, output_dir: Path
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    agg = aggregate(results)
    blocked = blocked_breakdown(results)
    stem = f"agentic_trader_simulation_{date.today().isoformat()}"
    md_path = output_dir / f"{stem}.md"
    json_path = output_dir / f"{stem}.json"
    md_path.write_text(render_markdown(agg, blocked, meta))
    clean = {
        name: {k: {s: (None if x != x else x) for s, x in v.items()} for k, v in m.items()}
        for name, m in agg.items()
    }
    json_path.write_text(
        json.dumps({"meta": meta, "aggregate": clean, "blocked": blocked}, indent=2, default=str)
    )
    return md_path, json_path
