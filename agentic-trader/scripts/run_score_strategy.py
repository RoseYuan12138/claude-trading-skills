#!/usr/bin/env python3
"""Market score (0-100) -> call/put tiers, tested on real data.

1. Does the score predict anything? Forward 20-day QQQ returns by score band.
2. Do score tiers beat fixed settings? Calls on breakouts / puts on breakdowns, sized and
   allowed by the day's tier. Tiers are fixed in advance; shifted thresholds, option
   pricing and random symbol subsets test robustness.

Example:
    python3 agentic-trader/scripts/fetch_ohlcv.py --symbols ^VIX --start 2020-06-01 --out-dir data/macro
    python3 agentic-trader/scripts/fetch_ohlcv.py --symbols HYG --adjusted --start 2020-06-01 --out-dir data/macro
    python3 agentic-trader/scripts/run_score_strategy.py --data-dir data/ohlcv --macro-dir data/macro \\
        --start 2021-09-01
"""

from __future__ import annotations

import argparse
import math
import random
import statistics
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agentic_trader.market_score import ScoreTier, market_scores  # noqa: E402
from agentic_trader.options import OptionExitRules, OptionRules  # noqa: E402
from agentic_trader.sim.data import ETF_SYMBOLS, load_csv_dir  # noqa: E402
from agentic_trader.sim.options_engine import OptionSimConfig, OptionSimulator  # noqa: E402

EXITS = OptionExitRules(stop_loss_pct=50, trail_after_pct=50, trail_pct=35, time_stop_dte=5)


def tiers(shift: float = 0.0, puts: bool = True) -> tuple[ScoreTier, ...]:
    return (
        ScoreTier(70 + shift, calls=True, puts=False, risk_pct=5.0, total_pct=15.0),
        ScoreTier(50 + shift, calls=True, puts=False, risk_pct=2.0, total_pct=10.0),
        ScoreTier(30 + shift, calls=False, puts=False, risk_pct=0.0, total_pct=0.0),
        ScoreTier(0, calls=False, puts=puts, risk_pct=2.0, total_pct=6.0),
    )


def stats(curve):
    eq = [e for _, e in curve]
    rets = [b / a - 1 for a, b in zip(eq, eq[1:]) if a > 0]
    sd = statistics.pstdev(rets) if len(rets) > 1 else 0.0
    peak, dd = eq[0], 0.0
    for e in eq:
        peak = max(peak, e)
        dd = max(dd, 1 - e / peak)
    years = len(eq) / 252
    end = max(eq[-1], 1e-9)
    yearly, prev = {}, None
    for d, e in curve:
        yearly.setdefault(d.year, [prev if prev is not None else e, e])
        yearly[d.year][1] = e
        prev = e
    return {
        "ret": (end / eq[0] - 1) * 100,
        "cagr": ((end / eq[0]) ** (1 / years) - 1) * 100,
        "dd": dd * 100,
        "sharpe": statistics.mean(rets) / sd * math.sqrt(252) if sd > 0 else 0.0,
        "years": {y: (b / a - 1) * 100 for y, (a, b) in yearly.items()},
    }


def window(curve, a: date, b: date) -> float:
    m = dict(curve)
    x = m[max(d for d in m if d <= a)]
    y = m[max(d for d in m if d <= b)]
    return (y / x - 1) * 100


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--data-dir", type=Path, required=True)
    p.add_argument("--macro-dir", type=Path, help="dir with ^VIX.csv and HYG.csv (optional)")
    p.add_argument("--start", type=date.fromisoformat, required=True)
    p.add_argument("--benchmark", default="SPY")
    p.add_argument("--initial-cash", type=float, default=1_000_000.0)
    p.add_argument("--subsets", type=int, default=6)
    p.add_argument("--output-dir", type=Path, default=Path("reports"))
    args = p.parse_args(argv)

    data = load_csv_dir(args.data_dir)
    macro = load_csv_dir(args.macro_dir) if args.macro_dir else {}
    bench = args.benchmark.upper()
    stocks = sorted(s for s in data if s not in ETF_SYMBOLS)
    scored = market_scores(
        {**{s: data[s] for s in stocks}, bench: data[bench]},
        bench,
        vix=macro.get("^VIX"),
        credit=macro.get("HYG"),
        breadth_symbols=stocks,
    )
    scores = {d: m.score for d, m in scored.items()}

    # ---- 1. predictive check on QQQ forward returns
    q = data["QQQ"]
    qi = {b.date: i for i, b in enumerate(q)}
    bands = [("< 30", 0, 30), ("30-50", 30, 50), ("50-70", 50, 70), (">= 70", 70, 101)]
    pred_rows = []
    for label, lo, hi in bands:
        fwd, big_drop = [], 0
        for d, s in scores.items():
            if d < args.start or not lo <= s < hi or d not in qi:
                continue
            i = qi[d]
            if i + 20 >= len(q):
                continue
            fwd.append((q[i + 20].close / q[i].close - 1) * 100)
            big_drop += min(b.low for b in q[i + 1 : i + 21]) / q[i].close - 1 <= -0.05
        if fwd:
            pred_rows.append(
                (
                    label,
                    len(fwd),
                    statistics.median(fwd),
                    statistics.mean(fwd),
                    sum(x > 0 for x in fwd) / len(fwd) * 100,
                    big_drop / len(fwd) * 100,
                )
            )

    # ---- 2. strategies
    universe = stocks + ["QQQ"]

    def ds(symbols):
        out = {s: data[s] for s in symbols}
        out[bench] = data[bench]
        return out

    def run(symbols, kind, iv=1.15, shift=0.0):
        rules = OptionRules(
            max_loss_per_trade_pct=5.01,
            max_total_risk_pct=15.0,
            max_open_positions=50,
            max_entries_per_day=10,
            daily_loss_limit_pct=100.0,
            max_contracts=10**9,
        )
        base = dict(
            initial_cash=args.initial_cash,
            start_date=args.start,
            untradable=(bench,),
            iv_premium=iv,
        )
        if kind == "fixed2":
            cfg = OptionSimConfig(
                **base, risk_per_trade_pct=2.0, regime_symbol=bench, regime_sma=50, allow_puts=False
            )
            rules = OptionRules(
                **{**rules.__dict__, "max_loss_per_trade_pct": 2.01, "max_total_risk_pct": 10.0}
            )
        elif kind == "fixed5":
            cfg = OptionSimConfig(
                **base, risk_per_trade_pct=5.0, regime_symbol=bench, regime_sma=50, allow_puts=False
            )
            rules = OptionRules(**{**rules.__dict__, "max_total_risk_pct": 10.0})
        elif kind == "gate_both":
            cfg = OptionSimConfig(
                **base, risk_per_trade_pct=2.0, regime_symbol=bench, regime_sma=50
            )
            rules = OptionRules(
                **{**rules.__dict__, "max_loss_per_trade_pct": 2.01, "max_total_risk_pct": 10.0}
            )
        elif kind == "score":
            cfg = OptionSimConfig(**base, score_tiers=tiers(shift))
        elif kind == "score_no_puts":
            cfg = OptionSimConfig(**base, score_tiers=tiers(shift, puts=False))
        else:
            raise ValueError(kind)
        return OptionSimulator(ds(symbols), rules, EXITS, cfg, scores=scores).run().equity_curve

    variants = [
        ("A. fixed: calls 2%/trade (cap 10%), SPY>50d", "fixed2", {}),
        ("B. fixed: calls 5%/trade (cap 10%), SPY>50d", "fixed5", {}),
        ("C. fixed: calls/puts 2% by SPY 50d", "gate_both", {}),
        ("D. SCORE tiers (calls 5%/2%, cash, puts 2%)", "score", {}),
        ("E. SCORE tiers, no puts", "score_no_puts", {}),
        ("F. D with thresholds -10", "score", {"shift": -10.0}),
        ("G. D with thresholds +10", "score", {"shift": 10.0}),
        ("H. D, IV = realized vol", "score", {"iv": 1.0}),
        ("I. D, IV = 1.4x realized", "score", {"iv": 1.4}),
    ]
    rng = random.Random(7)
    subsets = [sorted(rng.sample(stocks, 8)) + ["QQQ"] for _ in range(args.subsets)]
    rows = []
    for name, kind, kw in variants:
        curve = run(universe, kind, **kw)
        sub = [stats(run(x, kind, **kw)) for x in subsets]
        rows.append((name, stats(curve), window(curve, date(2026, 10, 6), curve[-1][0]), sub))
        print(".", end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)

    last = max(scores)
    today = scored[last]
    lines = [
        "# Market Score -> Call/Put Tiers",
        "",
        "Score = equal-weight mean of trend (SPY vs 50d/200d), breadth (% of stocks above 50d), "
        "20d momentum, distance from 1y high, VIX"
        + (" and HYG vs its 50d" if "HYG" in macro else "")
        + ". Weights and tiers were fixed before testing.",
        "",
        f"**Score on {last}: {today.score:.1f}** "
        + "("
        + ", ".join(f"{k} {v:.0f}" for k, v in today.components.items())
        + ")",
        "",
        "## 1. Does the score predict QQQ over the next 20 trading days?",
        "",
        "| Score band | Days | Median 20d % | Mean 20d % | Up % | Dropped >= 5% at some point % |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, n, med, mean, up, drop in pred_rows:
        lines.append(f"| {label} | {n} | {med:+.1f} | {mean:+.1f} | {up:.0f} | {drop:.0f} |")
    lines += [
        "",
        "## 2. Strategies",
        "",
        "Tiers: >= 70 calls 5%/trade (cap 15%); 50-70 calls 2% (cap 10%); 30-50 no new trades; "
        "< 30 puts 2% (cap 6%). Exits: -50% premium stop, trailing after +50%, 5 DTE time stop.",
        "",
        "| Variant | Return % | CAGR % | Max DD % | Sharpe | 2022 % | Oct 6-Nov 2026 % | "
        "Median return (subsets) | Median DD | Subsets < 0 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, s, octnov, sub in rows:
        lines.append(
            f"| {name} | {s['ret']:+.0f} | {s['cagr']:+.1f} | {s['dd']:.0f} | {s['sharpe']:.2f} | "
            f"{s['years'].get(2022, 0):+.0f} | {octnov:+.1f} | "
            f"{statistics.median(x['ret'] for x in sub):+.0f} | "
            f"{statistics.median(x['dd'] for x in sub):.0f} | {sum(x['ret'] < 0 for x in sub)}/{len(sub)} |"
        )
    lines += [
        "",
        "## Limits",
        "",
        "- Option prices: Black-Scholes from realized vol x 1.15 (rows H/I vary it); no IV crush "
        "or skew. One mostly-bullish period; stocks chosen with hindsight.",
        "- The score is equal-weighted by design; a fitted score would look better in-sample and "
        "worse out of sample.",
    ]
    md = "\n".join(lines) + "\n"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out = args.output_dir / f"score_strategy_{last}.md"
    out.write_text(md)
    print(md)
    print(f"Report: {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
