#!/usr/bin/env python3
"""Refinements of the leveraged trend strategy, options vs ETF, 2001-2026.

Pre-registered variants (fixed before running):
  V1 regime hysteresis: enter above SMA200 x 1.02, exit below SMA200 x 0.98
  V2 volatility targeting: premium (or leverage) scaled by target vol / VXN, capped
  V3 LEAPS: 270-DTE calls rolled at 60 DTE instead of 120 / 30
  V1+V2+V3 combined
ETF counterparts: 2x QQQ rotation with/without the buffer; dynamic 0-3x leverage targeting
25% (or 20%) volatility from VXN.

Example:
    python3 agentic-trader/scripts/run_trend_variants.py --data-dir data/ohlcv \\
        --macro-dir data/macro --adj-dir data/adjusted
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from agentic_trader.options import OptionExitRules, OptionRules  # noqa: E402
from agentic_trader.sim.data import load_csv_dir  # noqa: E402
from agentic_trader.sim.options_engine import OptionSimConfig, OptionSimulator  # noqa: E402
from agentic_trader.sim.rotation import (  # noqa: E402
    dynamic_leverage_curve,
    rotation_curve,
    synthetic_leveraged,
)
from run_aggressive_research import (  # noqa: E402
    BASE_PRICING,
    HALF_SPREAD_PCT,
    PERIODS,
    PRICING,
    stats,
)

S3 = dict(moneyness=0.85, dte=120, roll=30, buffer=0.0, vol_target=None, cap=1.0)
OPTION_VARIANTS = [
    ("S3 base, 30% premium", dict(S3, premium=30.0)),
    ("S3 base, 50% premium", dict(S3, premium=50.0)),
    ("V1 buffer 2%, 30%", dict(S3, premium=30.0, buffer=2.0)),
    ("V1 buffer 2%, 50%", dict(S3, premium=50.0, buffer=2.0)),
    ("V2 vol target 22%, 30% base (max 50%)", dict(S3, premium=30.0, vol_target=0.22, cap=1.67)),
    ("V2 vol target 22%, 40% base (max 60%)", dict(S3, premium=40.0, vol_target=0.22, cap=1.5)),
    ("V3 LEAPS 270d / roll 60, 30%", dict(S3, premium=30.0, dte=270, roll=60)),
    ("V3 LEAPS 270d / roll 60, 50%", dict(S3, premium=50.0, dte=270, roll=60)),
    (
        "V1+V2+V3, 30% base (max 50%)",
        dict(S3, premium=30.0, buffer=2.0, vol_target=0.22, cap=1.67, dte=270, roll=60),
    ),
    (
        "V1+V2+V3, 40% base (max 60%)",
        dict(S3, premium=40.0, buffer=2.0, vol_target=0.22, cap=1.5, dte=270, roll=60),
    ),
]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--data-dir", type=Path, required=True)
    p.add_argument("--macro-dir", type=Path, required=True)
    p.add_argument("--adj-dir", type=Path, required=True)
    p.add_argument("--initial-cash", type=float, default=1_000_000.0)
    p.add_argument("--output-dir", type=Path, default=Path("reports"))
    p.add_argument(
        "--iv-term-mean",
        type=float,
        default=None,
        help="long-run IV for the term structure, e.g. 0.24 (default: flat)",
    )
    p.add_argument("--iv-term-kappa", type=float, default=3.0)
    p.add_argument("--options-only", action="store_true")
    args = p.parse_args(argv)

    data = load_csv_dir(args.data_dir)
    macro = load_csv_dir(args.macro_dir)
    adj = load_csv_dir(args.adj_dir)
    vxn_series = {b.date: b.close for b in macro["^VXN"]}
    vxn = {"QQQ": vxn_series}
    irx = {b.date: b.close for b in adj["^IRX"]}
    two_x = synthetic_leveraged(adj["QQQ"], 2.0, irx, expense_pct=1.43)
    put_skew, call_skew = PRICING[BASE_PRICING]

    def option_curve(v, start, end):
        d = {s: [b for b in data[s] if b.date <= end] for s in ("QQQ", "SPY")}
        cfg = OptionSimConfig(
            initial_cash=args.initial_cash,
            start_date=start,
            untradable=("SPY",),
            hedge_symbols=("QQQ",),
            signal_mode="index_trend",
            regime_symbol="SPY",
            regime_sma=200,
            regime_buffer_pct=v["buffer"],
            exit_on_regime_bear=True,
            strike_moneyness=v["moneyness"],
            target_dte=v["dte"],
            risk_per_trade_pct=v["premium"],
            vol_target=v["vol_target"],
            vol_target_cap=v["cap"],
            div_yield=0.007,
            half_spread_pct=HALF_SPREAD_PCT,
            min_half_spread=0.01,
            put_skew_per_pct=put_skew,
            call_skew_per_pct=call_skew,
            iv_term_mean=args.iv_term_mean,
            iv_term_kappa=args.iv_term_kappa,
        )
        max_prem = v["premium"] * (v["cap"] if v["vol_target"] else 1.0)
        rules = OptionRules(
            max_loss_per_trade_pct=max_prem + 0.01,
            max_total_risk_pct=max_prem + 0.01,
            max_contracts=10**9,
            max_dte=400,
            daily_loss_limit_pct=100.0,
        )
        exits = OptionExitRules(stop_loss_pct=None, trail_after_pct=None, time_stop_dte=v["roll"])
        return (
            OptionSimulator(d, rules, exits, cfg, iv_overrides=vxn, rates_pct=irx)
            .run()
            .equity_curve
        )

    etf_variants = [
        ("ETF: QQQ buy & hold", lambda a, b: rotation_curve(adj["QQQ"], None, a, b)),
        (
            "ETF: 2x QQQ while SPY > 200d",
            lambda a, b: rotation_curve(two_x, adj["SPY"], a, b, sma=200),
        ),
        (
            "ETF V5: 2x QQQ, 2% buffer",
            lambda a, b: dynamic_leverage_curve(
                adj["QQQ"],
                adj["SPY"],
                {d: 1.0 for d in vxn_series},
                a,
                b,
                target_vol=0.02,
                max_leverage=2.0,
                buffer_pct=2.0,
                rates_pct=irx,
            ),
        ),
        (
            "ETF V4: 0-3x, target vol 25%",
            lambda a, b: dynamic_leverage_curve(
                adj["QQQ"],
                adj["SPY"],
                vxn_series,
                a,
                b,
                target_vol=0.25,
                max_leverage=3.0,
                rates_pct=irx,
            ),
        ),
        (
            "ETF V4: 0-3x, target 25%, 2% buffer",
            lambda a, b: dynamic_leverage_curve(
                adj["QQQ"],
                adj["SPY"],
                vxn_series,
                a,
                b,
                target_vol=0.25,
                max_leverage=3.0,
                buffer_pct=2.0,
                rates_pct=irx,
            ),
        ),
        (
            "ETF V4: 0-2x, target vol 20%",
            lambda a, b: dynamic_leverage_curve(
                adj["QQQ"],
                adj["SPY"],
                vxn_series,
                a,
                b,
                target_vol=0.20,
                max_leverage=2.0,
                rates_pct=irx,
            ),
        ),
    ]

    lines = [
        "# Leveraged Trend Refinements: Options vs ETF",
        "",
        "Options: QQQ calls ~15% ITM held while SPY > 200d SMA (base pricing: VXN, ^IRX, 0.7% "
        f"dividend, strike skew, {HALF_SPREAD_PCT}% half bid-ask). ETF rows are synthetic "
        "daily-leveraged QQQ (dividend-adjusted, borrowing at ^IRX). Variants were fixed before "
        "running. Cells: CAGR % / max drawdown % / Sharpe / worst calendar year %.",
        "",
        "| Strategy | " + " | ".join(PERIODS) + " |",
        "|---|" + "---|" * len(PERIODS),
    ]

    def cell(curve):
        s = stats(curve)
        return f"{s['cagr']:+.1f} / {s['dd']:.0f} / {s['sharpe']:.2f} / {s['worst']:+.0f}"

    if args.iv_term_mean is not None:
        lines.insert(
            3,
            f"IV term structure on: 30-day VXN mean-reverts to {args.iv_term_mean:.0%} at "
            f"kappa {args.iv_term_kappa:g}/yr for other expiries.\n",
        )
    for name, fn in [] if args.options_only else etf_variants:
        lines.append(
            f"| {name} | " + " | ".join(cell(fn(a, b)) for a, b in PERIODS.values()) + " |"
        )
        print(".", end="", file=sys.stderr, flush=True)
    for name, v in OPTION_VARIANTS:
        lines.append(
            f"| {name} | "
            + " | ".join(cell(option_curve(v, a, b)) for a, b in PERIODS.values())
            + " |"
        )
        print(".", end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)
    md = "\n".join(lines) + "\n"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    suffix = "" if args.iv_term_mean is None else f"_term{args.iv_term_kappa:g}"
    out = args.output_dir / f"trend_variants{suffix}.md"
    out.write_text(md)
    print(md)
    print(f"Report: {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
