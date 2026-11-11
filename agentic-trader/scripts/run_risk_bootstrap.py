#!/usr/bin/env python3
"""What could 10 years of each aggressive strategy look like? Block bootstrap, 2000-2026.

Resamples quarter-long blocks of the 2000-2026 daily returns (the same blocks for every
strategy) into many 10-year paths and reports the spread of outcomes, not one history.

Example:
    python3 agentic-trader/scripts/run_risk_bootstrap.py --data-dir data/ohlcv \\
        --macro-dir data/macro --adj-dir data/adjusted --paths 5000
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from agentic_trader.sim.bootstrap import bootstrap_compare  # noqa: E402
from agentic_trader.sim.rotation import rotation_curve, synthetic_leveraged  # noqa: E402
from run_aggressive_research import load_inputs, run_option_strategy  # noqa: E402


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--data-dir", type=Path, required=True)
    p.add_argument("--macro-dir", type=Path, required=True)
    p.add_argument("--adj-dir", type=Path, required=True)
    p.add_argument("--paths", type=int, default=5000)
    p.add_argument("--years", type=float, default=10.0)
    p.add_argument("--output-dir", type=Path, default=Path("reports"))
    args = p.parse_args(argv)

    data, _macro, adj, scores, vxn, irx = load_inputs(args.data_dir, args.macro_dir, args.adj_dir)
    start, end = date(2000, 1, 3), date(2026, 11, 10)
    two = synthetic_leveraged(adj["QQQ"], 2.0, irx, expense_pct=1.43)
    three = synthetic_leveraged(adj["QQQ"], 3.0, irx, expense_pct=2.53)
    curves = {
        "QQQ buy & hold": rotation_curve(adj["QQQ"], None, start, end),
        "2x QQQ, SPY and QQQ > 200d": rotation_curve(
            two, adj["SPY"], start, end, sma=200, regime_also=[adj["QQQ"]]
        ),
        "3x QQQ, SPY and QQQ > 200d": rotation_curve(
            three, adj["SPY"], start, end, sma=200, regime_also=[adj["QQQ"]]
        ),
    }
    for name in (
        "S3e LEAPS 270d, 30%, SPY and QQQ > 200d",
        "S3f LEAPS 270d, 50%, SPY and QQQ > 200d",
    ):
        curves[name] = run_option_strategy(name, data, scores, vxn, irx, start, end, 1_000_000.0)[0]

    res = bootstrap_compare(curves, horizon_years=args.years, n_paths=args.paths, seed=7)
    lines = [
        f"# {args.years:g}-Year Outcome Distribution (block bootstrap of 2000-2026)",
        "",
        f"{args.paths} paths of {args.years:g} years built from 63-day blocks of 2000-2026 daily "
        "returns, with the same blocks for every strategy. Option strategies use the base "
        "pricing of `run_aggressive_research.py`.",
        "",
        "| Strategy | CAGR p5 | p25 | median | p75 | p95 | Median max DD | p95 max DD | "
        "P(lose money) | P(DD > 50%) | P(DD > 70%) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, r in res.items():
        lines.append(
            f"| {name} | {r['cagr_p5']:+.1f}% | {r['cagr_p25']:+.1f}% | {r['cagr_p50']:+.1f}% | "
            f"{r['cagr_p75']:+.1f}% | {r['cagr_p95']:+.1f}% | {r['dd_p50']:.0f}% | "
            f"{r['dd_p95']:.0f}% | {r['p_loss'] * 100:.0f}% | {r['p_dd50'] * 100:.0f}% | "
            f"{r['p_dd70'] * 100:.0f}% |"
        )
    lines += [
        "",
        "Limits: the bootstrap reshuffles history; it cannot invent regimes that never "
        "happened, and quarter-long blocks understate multi-year bear markets like 2000-2002.",
    ]
    md = "\n".join(lines) + "\n"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out = args.output_dir / "risk_bootstrap.md"
    out.write_text(md)
    print(md)
    print(f"Report: {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
