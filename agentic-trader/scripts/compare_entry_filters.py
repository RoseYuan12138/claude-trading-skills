#!/usr/bin/env python3
"""Compare entry filters for the share-based agent on real daily OHLCV.

Filters: market regime (benchmark above its SMA), earnings blackout (inferred
earnings dates unless --calendar is given), breakout volume confirmation.
Runs on the full universe and on random symbol subsets to separate signal from luck.

Example:
    python3 agentic-trader/scripts/compare_entry_filters.py --data-dir data/ohlcv \\
        --start 2021-09-01 --benchmark SPY
"""

from __future__ import annotations

import argparse
import random
import statistics
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agentic_trader.events import EventCalendar  # noqa: E402
from agentic_trader.risk_gate import load_rules  # noqa: E402
from agentic_trader.sim.data import ETF_SYMBOLS, infer_earnings_calendar, load_csv_dir  # noqa: E402
from agentic_trader.sim.engine import SimConfig, run_simulation  # noqa: E402
from agentic_trader.stops import AtrTrailingStop  # noqa: E402


def variants(bench: str) -> list[tuple[str, dict]]:
    return [
        ("0. no filter (current rule)", {}),
        (f"1. regime: {bench} > 200d SMA", {"regime_symbol": bench, "regime_sma": 200}),
        (f"2. regime: {bench} > 50d SMA", {"regime_symbol": bench, "regime_sma": 50}),
        ("3. earnings blackout 7 days", {"earnings_blackout_days": 7}),
        ("4. breakout volume >= 1.5x", {"volume_confirm_mult": 1.5}),
        (
            "5. regime 200d + blackout",
            {"regime_symbol": bench, "regime_sma": 200, "earnings_blackout_days": 7},
        ),
        (
            "6. regime 200d + blackout + volume",
            {
                "regime_symbol": bench,
                "regime_sma": 200,
                "earnings_blackout_days": 7,
                "volume_confirm_mult": 1.5,
            },
        ),
        (
            "7. regime 50d + volume (picked after seeing 2 and 4: in-sample)",
            {"regime_symbol": bench, "regime_sma": 50, "volume_confirm_mult": 1.5},
        ),
    ]


def yearly(curve):
    out, first, last, prev = {}, {}, {}, None
    for d, e in curve:
        first.setdefault(d.year, prev if prev is not None else e)
        last[d.year] = e
        prev = e
    for y in first:
        out[y] = (last[y] / first[y] - 1) * 100
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--data-dir", type=Path, required=True)
    p.add_argument("--start", type=date.fromisoformat, required=True)
    p.add_argument("--benchmark", default="SPY")
    p.add_argument("--calendar", type=Path, help="real earnings calendar JSON (else inferred)")
    p.add_argument("--subsets", type=int, default=6)
    p.add_argument("--subset-size", type=int, default=8)
    p.add_argument("--initial-cash", type=float, default=50_000.0)
    p.add_argument("--output-dir", type=Path, default=Path("reports"))
    args = p.parse_args(argv)

    data = load_csv_dir(args.data_dir)
    bench = args.benchmark.upper()
    if bench not in data:
        print(f"benchmark {bench} missing from {args.data_dir}", file=sys.stderr)
        return 1
    calendar = (
        EventCalendar.from_json(args.calendar) if args.calendar else infer_earnings_calendar(data)
    )
    rules = load_rules(ROOT / "config" / "sim_rules.yaml")
    base = SimConfig(initial_cash=args.initial_cash, start_date=args.start, untradable=(bench,))
    stocks = sorted(s for s in data if s not in ETF_SYMBOLS)
    rng = random.Random(7)
    subsets = [
        sorted(rng.sample(stocks, min(args.subset_size, len(stocks)))) for _ in range(args.subsets)
    ]

    def run(symbols, overrides):
        d = {s: data[s] for s in symbols}
        d[bench] = data[bench]
        return run_simulation(
            d, calendar, rules, AtrTrailingStop(3), config=replace(base, **overrides)
        )

    rows, curves = [], {}
    for name, ov in variants(bench):
        full = run(stocks, ov)
        fm = full.metrics()
        curves[name] = full.equity_curve
        sub = [run(s, ov).metrics() for s in subsets]
        rows.append((name, fm, sub))

    first, last = curves[rows[0][0]][0][0], curves[rows[0][0]][-1][0]
    lines = [
        "# Entry Filter Comparison (shares, ATR 3x trailing stop)",
        "",
        f"- Universe: {', '.join(stocks)}; benchmark {bench} (filter only, not traded)",
        f"- Period: {first} to {last}; start equity ${args.initial_cash:,.0f}",
        "- Earnings dates: "
        + (
            "from " + str(args.calendar)
            if args.calendar
            else "inferred from volume + gaps (~60% accurate)"
        ),
        f"- Subsets: {args.subsets} random draws of {args.subset_size} stocks",
        "",
        "| Variant | Return % (all) | Max DD % (all) | Sharpe (all) | Trades (all) | "
        "Median return % (subsets) | Median DD % | Median Sharpe | Subsets beating no-filter |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    base_sub = rows[0][2]
    for name, fm, sub in rows:
        beat = sum(s["sharpe"] > b["sharpe"] for s, b in zip(sub, base_sub))
        lines.append(
            f"| {name} | {fm['total_return_pct']:+.1f} | {fm['max_drawdown_pct']:.1f} | "
            f"{fm['sharpe']:.2f} | {fm['trades']:.0f} | "
            f"{statistics.median(m['total_return_pct'] for m in sub):+.1f} | "
            f"{statistics.median(m['max_drawdown_pct'] for m in sub):.1f} | "
            f"{statistics.median(m['sharpe'] for m in sub):.2f} | "
            + ("–" if name.startswith("0.") else f"{beat} / {len(sub)} (Sharpe)")
            + " |"
        )
    years = sorted({d.year for d, _ in curves[rows[0][0]]})
    lines += ["", "## Return by year, full universe (%)", ""]
    lines.append("| Variant | " + " | ".join(map(str, years)) + " |")
    lines.append("|---|" + "---:|" * len(years))
    for name, _, _ in rows:
        y = yearly(curves[name])
        lines.append(f"| {name} | " + " | ".join(f"{y.get(v, 0):+.1f}" for v in years) + " |")
    lines += [
        "",
        "## Limits",
        "",
        "- One period (2021-2026) and large-cap tech chosen today: selection bias.",
        "- Inferred earnings dates miss some reports and flag some non-earnings days.",
        "- Daily bars, next-open fills, 5 bps slippage, no commissions or dividends.",
    ]
    md = "\n".join(lines) + "\n"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out = args.output_dir / f"entry_filter_comparison_{last}.md"
    out.write_text(md)
    print(md)
    print(f"Report: {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
