#!/usr/bin/env python3
"""Compare stop-management scenarios on synthetic or real (CSV) data.

Examples:
    # Synthetic stress market, 5 seeds x 8 years x 12 symbols
    python3 agentic-trader/scripts/run_simulation.py --seeds 5

    # Real data: one CSV per symbol (date,open,high,low,close,volume)
    python3 agentic-trader/scripts/run_simulation.py --data-dir data/ohlcv \\
        --calendar data/events.json
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agentic_trader.events import EventCalendar  # noqa: E402
from agentic_trader.risk_gate import load_rules  # noqa: E402
from agentic_trader.sim.data import generate_market, load_csv_dir  # noqa: E402
from agentic_trader.sim.engine import SimConfig  # noqa: E402
from agentic_trader.sim.report import (  # noqa: E402
    aggregate,
    default_scenarios,
    run_batch,
    write_report,
)


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--seeds", type=int, default=5, help="number of synthetic markets (default 5)")
    p.add_argument("--seed-start", type=int, default=1)
    p.add_argument("--symbols", type=int, default=12, help="synthetic symbol count")
    p.add_argument("--years", type=float, default=8.0, help="synthetic history length")
    p.add_argument("--data-dir", type=Path, help="directory of <SYMBOL>.csv files (real data)")
    p.add_argument("--calendar", type=Path, help="events JSON for --data-dir mode")
    p.add_argument("--rules", type=Path, default=ROOT / "config" / "sim_rules.yaml")
    p.add_argument("--initial-cash", type=float, default=100_000.0)
    p.add_argument("--slippage-bps", type=float, default=5.0)
    p.add_argument("--output-dir", type=Path, default=Path("reports"))
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    rules = load_rules(args.rules)
    cfg = SimConfig(initial_cash=args.initial_cash, slippage_bps=args.slippage_bps)

    if args.data_dir:
        data = load_csv_dir(args.data_dir)
        calendar = EventCalendar.from_json(args.calendar) if args.calendar else EventCalendar()
        seeds = [0]
        make_data = lambda seed: (data, calendar)  # noqa: E731
        data_desc = f"CSV from {args.data_dir}" + ("" if args.calendar else " (no event calendar)")
        n_symbols, n_days = len(data), max(len(b) for b in data.values())
    else:
        n_days = int(args.years * 252)
        symbols = [f"SYN{i:02d}" for i in range(1, args.symbols + 1)]
        seeds = list(range(args.seed_start, args.seed_start + args.seeds))
        make_data = lambda seed: generate_market(symbols, n_days, seed)  # noqa: E731
        data_desc = "synthetic regime-switching market with earnings/macro gaps"
        n_symbols = len(symbols)

    scenarios = default_scenarios(rules)
    print(f"Running {len(scenarios)} scenarios x {len(seeds)} seed(s)...", file=sys.stderr)
    results = run_batch(scenarios, seeds, make_data, rules, cfg)

    meta = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "data": data_desc,
        "seeds": seeds,
        "n_symbols": n_symbols,
        "n_days": n_days,
        "slippage_bps": args.slippage_bps,
        "rules_file": str(args.rules),
    }
    md, js = write_report(results, meta, args.output_dir)

    agg = aggregate(results)
    print(f"{'scenario':<24}{'return%':>9}{'maxDD%':>8}{'sharpe':>8}{'llm/mo':>8}{'bad exec':>9}")
    for name, m in agg.items():
        print(
            f"{name:<24}{m['total_return_pct']['mean']:>9.1f}{m['max_drawdown_pct']['mean']:>8.1f}"
            f"{m['sharpe']['mean']:>8.2f}{m['llm_wakeups_per_month']['mean']:>8.1f}"
            f"{m['chaos_executed']['mean']:>9.0f}"
        )
    print(f"\nReport: {md}\nJSON:   {js}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
