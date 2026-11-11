#!/usr/bin/env python3
"""Sweep how aggressively to buy options, with and without stops.

Calls on 20-day breakouts above the 50-day SMA while the benchmark is above its 50-day
SMA; optionally puts on breakdowns while it is below. Varies premium risked per trade,
total premium at risk, stops and expiry. Reports return, drawdown, the lowest equity
point and robustness across random symbol subsets.

Example:
    python3 agentic-trader/scripts/run_aggressive_options.py --data-dir data/ohlcv --start 2021-09-01
"""

from __future__ import annotations

import argparse
import itertools
import math
import random
import statistics
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agentic_trader.options import OptionExitRules, OptionRules  # noqa: E402
from agentic_trader.sim.data import ETF_SYMBOLS, load_csv_dir  # noqa: E402
from agentic_trader.sim.options_engine import OptionSimConfig, OptionSimulator  # noqa: E402

STOPS = {
    "stop -50% + trail": OptionExitRules(
        stop_loss_pct=50, trail_after_pct=50, trail_pct=35, time_stop_dte=5
    ),
    "no stop": OptionExitRules(stop_loss_pct=None, trail_after_pct=None, time_stop_dte=5),
}


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
    by_year: dict[int, list[float]] = {}
    for d, e in curve:
        by_year.setdefault(d.year, []).append(e)
    yrs, prev = [], None
    for y in sorted(by_year):
        start = prev if prev is not None else by_year[y][0]
        yrs.append((by_year[y][-1] / start - 1) * 100)
        prev = by_year[y][-1]
    return {
        "ret": (end / eq[0] - 1) * 100,
        "cagr": ((end / eq[0]) ** (1 / years) - 1) * 100,
        "dd": dd * 100,
        "sharpe": statistics.mean(rets) / sd * math.sqrt(252) if sd > 0 else 0.0,
        "low": min(eq) / eq[0] * 100,
        "worst_year": min(yrs),
    }


def window(curve, a: date, b: date) -> float:
    m = dict(curve)
    x = m[max(d for d in m if d <= a)]
    y = m[max(d for d in m if d <= b)]
    return (y / x - 1) * 100


def run(data, bench, start, cash, risk, total, puts, stop, dte=35, iv=1.15):
    d = dict(data)
    cfg = OptionSimConfig(
        initial_cash=cash,
        risk_per_trade_pct=risk,
        start_date=start,
        regime_symbol=bench,
        regime_sma=50,
        untradable=(bench,),
        allow_puts=puts,
        target_dte=dte,
        iv_premium=iv,
    )
    rules = OptionRules(
        max_loss_per_trade_pct=risk + 0.01,
        max_total_risk_pct=total,
        max_open_positions=50,
        max_entries_per_day=10,
        daily_loss_limit_pct=100.0,
        max_contracts=10**9,
        max_dte=120,
    )
    return OptionSimulator(d, rules, STOPS[stop], cfg).run().equity_curve


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--data-dir", type=Path, required=True)
    p.add_argument("--start", type=date.fromisoformat, required=True)
    p.add_argument("--benchmark", default="SPY")
    p.add_argument("--initial-cash", type=float, default=1_000_000.0)
    p.add_argument("--subsets", type=int, default=6)
    p.add_argument("--output-dir", type=Path, default=Path("reports"))
    args = p.parse_args(argv)

    data = load_csv_dir(args.data_dir)
    bench = args.benchmark.upper()
    stocks = sorted(s for s in data if s not in ETF_SYMBOLS)
    universe = stocks + [s for s in ("QQQ",) if s in data]
    rng = random.Random(7)
    subsets = [sorted(rng.sample(stocks, 8)) + ["QQQ"] for _ in range(args.subsets)]

    def dataset(symbols):
        out = {s: data[s] for s in symbols}
        out[bench] = data[bench]
        return out

    grid = []
    for risk, total, puts, stop in itertools.product(
        (2.0, 5.0, 10.0), (10.0, 25.0, 50.0), (False, True), tuple(STOPS)
    ):
        if total < risk:
            continue
        grid.append(dict(risk=risk, total=total, puts=puts, stop=stop))
    extra = [
        dict(risk=5.0, total=25.0, puts=False, stop="stop -50% + trail", dte=60),
        dict(risk=5.0, total=25.0, puts=False, stop="stop -50% + trail", iv=1.4),
    ]

    rows = []
    for g in grid + extra:
        curve = run(dataset(universe), bench, args.start, args.initial_cash, **g)
        s = stats(curve)
        sub = [stats(run(dataset(x), bench, args.start, args.initial_cash, **g)) for x in subsets]
        s["oct_nov"] = window(curve, date(2026, 10, 6), curve[-1][0])
        s["med_ret"] = statistics.median(x["ret"] for x in sub)
        s["med_dd"] = statistics.median(x["dd"] for x in sub)
        s["neg"] = sum(x["ret"] < 0 for x in sub)
        s["worst_low"] = min(x["low"] for x in sub)
        rows.append((g, s))
        print(".", end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)

    last = run(dataset(["QQQ"]), bench, args.start, 1.0, 2.0, 10.0, False, "no stop")[-1][0]
    lines = [
        "# Aggressive Option Buying: How Much, and Do Stops Help?",
        "",
        f"- Universe: {', '.join(universe)}; calls only while {bench} > 50d SMA, puts (if on) "
        "only while below; ~35 DTE at the money",
        f"- Period: {args.start} to {last}; ${args.initial_cash:,.0f}; risk = premium paid per "
        "trade (its worst case); total = cap on premium at risk across open positions",
        "- 'Lowest point' = the lowest equity reached, as % of starting equity",
        "",
        "| Risk/trade | Total cap | Puts | Exits | Return % | CAGR % | Max DD % | Sharpe | "
        "Worst year % | Lowest point % | Oct-Nov 2026 % | Median return (subsets) | "
        "Median DD | Subsets < 0 | Worst subset low % |",
        "|---:|---:|---|---|" + "---:|" * 11,
    ]
    for g, s in rows:
        tag = ""
        if g.get("dte"):
            tag = f" ({g['dte']} DTE)"
        if g.get("iv"):
            tag = f" (IV {g['iv']}x)"
        lines.append(
            f"| {g['risk']:g}% | {g['total']:g}% | {'yes' if g['puts'] else 'no'} | "
            f"{g['stop']}{tag} | {s['ret']:+.0f} | {s['cagr']:+.1f} | {s['dd']:.0f} | "
            f"{s['sharpe']:.2f} | {s['worst_year']:+.0f} | {s['low']:.0f} | {s['oct_nov']:+.1f} | "
            f"{s['med_ret']:+.0f} | {s['med_dd']:.0f} | {s['neg']}/{len(subsets)} | "
            f"{s['worst_low']:.0f} |"
        )
    lines += [
        "",
        "## Limits",
        "",
        "- Black-Scholes prices from realized vol x 1.15 (one row at 1.4x): no IV crush around "
        "earnings, no skew, so results are likely optimistic.",
        "- Stops are checked at the close and filled at the next open.",
        "- One mostly-bullish period; large-cap tech picked with hindsight.",
    ]
    md = "\n".join(lines) + "\n"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out = args.output_dir / f"aggressive_options_{last}.md"
    out.write_text(md)
    print(md)
    print(f"Report: {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
