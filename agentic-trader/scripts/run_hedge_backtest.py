#!/usr/bin/env python3
"""Aggressive longs in bull regimes + a small index put hedge in bear regimes.

Long sleeve: share breakouts (ATR 3x trailing stop) only while the benchmark is above its
50-day SMA; "aggressive" raises risk per trade, position caps and entries per day.
Hedge sleeve: while the benchmark is below its 50-day SMA, hold an at-the-money put (or
put spread) on QQQ worth a fixed share of equity; close it when the benchmark closes back
above the SMA, at 5 DTE (then re-buy if still bearish), or via a trailing stop after a
big gain.

Example:
    python3 agentic-trader/scripts/run_hedge_backtest.py --data-dir data/ohlcv --start 2021-09-01
"""

from __future__ import annotations

import argparse
import math
import random
import statistics
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agentic_trader.events import EventCalendar  # noqa: E402
from agentic_trader.options import OptionExitRules, OptionRules  # noqa: E402
from agentic_trader.risk_gate import load_rules  # noqa: E402
from agentic_trader.sim.data import ETF_SYMBOLS, load_csv_dir  # noqa: E402
from agentic_trader.sim.engine import SimConfig, run_simulation  # noqa: E402
from agentic_trader.sim.options_engine import OptionSimConfig, OptionSimulator  # noqa: E402
from agentic_trader.stops import AtrTrailingStop  # noqa: E402

HEDGE_EXITS = OptionExitRules(
    stop_loss_pct=None, trail_after_pct=100, trail_pct=40, time_stop_dte=5
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
    return {
        "ret": (eq[-1] / eq[0] - 1) * 100,
        "cagr": ((eq[-1] / eq[0]) ** (1 / years) - 1) * 100,
        "dd": dd * 100,
        "sharpe": statistics.mean(rets) / sd * math.sqrt(252) if sd > 0 else 0.0,
    }


def window(curve, a: date, b: date) -> float:
    m = dict(curve)
    x = m[max(d for d in m if d <= a)]
    y = m[max(d for d in m if d <= b)]
    return (y / x - 1) * 100


def combine(*curves):
    maps = [dict(c) for c in curves]
    dates = sorted(set.intersection(*(set(m) for m in maps)))
    return [(d, sum(m[d] for m in maps)) for d in dates]


class Runner:
    def __init__(self, data, bench, start, cash):
        self.data, self.bench, self.start, self.cash = data, bench, start, cash
        base = load_rules(ROOT / "config" / "sim_rules.yaml")
        self.normal = replace(base, max_order_notional=1e15)
        self.aggressive = replace(
            self.normal,
            max_open_positions=10,
            max_position_pct=25,
            max_entries_per_day=4,
            risk_per_trade_pct=1.5,
        )

    def longs(self, symbols, cash, aggressive):
        d = {s: self.data[s] for s in symbols}
        d[self.bench] = self.data[self.bench]
        cfg = SimConfig(
            initial_cash=cash,
            start_date=self.start,
            untradable=(self.bench,),
            regime_symbol=self.bench,
            regime_sma=50,
            risk_pct=1.25 if aggressive else 0.75,
        )
        rules = self.aggressive if aggressive else self.normal
        return run_simulation(
            d, EventCalendar(), rules, AtrTrailingStop(3), config=cfg
        ).equity_curve

    def hedge(self, cash, premium_pct_of_total, structure="long"):
        sleeve_pct = premium_pct_of_total * self.cash / cash
        d = {"QQQ": self.data["QQQ"], self.bench: self.data[self.bench]}
        cfg = OptionSimConfig(
            initial_cash=cash,
            risk_per_trade_pct=sleeve_pct,
            start_date=self.start,
            signal_mode="index_hedge",
            hedge_symbols=("QQQ",),
            regime_symbol=self.bench,
            regime_sma=50,
            untradable=(self.bench,),
            exit_on_regime_bull=True,
            target_dte=45,
            structure=structure,
            spread_width_atr=4.0,
        )
        rules = OptionRules(
            max_loss_per_trade_pct=sleeve_pct + 0.01,
            max_total_risk_pct=min(100.0, sleeve_pct * 2),
            max_contracts=10**9,
            max_dte=120,
        )
        res = OptionSimulator(d, rules, HEDGE_EXITS, cfg).run()
        return res.equity_curve, res.trades

    def variants(self, stocks):
        t = self.cash
        out = {}
        out["A. normal longs + SPY 50d filter"] = (self.longs(stocks, t, False), [])
        out["B. aggressive longs + filter"] = (self.longs(stocks, t, True), [])
        for pct, struct, tag in (
            (1.0, "long", "C"),
            (2.0, "long", "D"),
            (1.0, "debit_vertical", "E"),
        ):
            hc, ht = self.hedge(t * 0.1, pct, struct)
            name = (
                f"{tag}. B (90%) + QQQ {'put' if struct == 'long' else 'put spread'} hedge, "
                f"{pct:g}% premium"
            )
            out[name] = (combine(self.longs(stocks, t * 0.9, True), hc), ht)
        for sym in (self.bench, "QQQ"):
            bars = [b for b in self.data[sym] if b.date >= self.start]
            out[f"{sym} buy & hold"] = ([(b.date, b.close) for b in bars], [])
        return out


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
    if bench not in data or "QQQ" not in data:
        print("need benchmark and QQQ CSVs", file=sys.stderr)
        return 1
    stocks = sorted(s for s in data if s not in ETF_SYMBOLS)
    r = Runner(data, bench, args.start, args.initial_cash)
    full = r.variants(stocks)
    rng = random.Random(7)
    subs = [r.variants(sorted(rng.sample(stocks, 8))) for _ in range(args.subsets)]

    base_curve = full["A. normal longs + SPY 50d filter"][0]
    first, last = base_curve[0][0], base_curve[-1][0]
    windows = [
        ("2022 bear", date(2021, 12, 31), date(2022, 12, 30)),
        ("Feb-Apr 2025", date(2025, 2, 19), date(2025, 4, 30)),
        ("Oct 6-Nov 2026", date(2026, 10, 6), last),
    ]
    lines = [
        "# Aggressive Longs + Index Put Hedge",
        "",
        f"- Universe: {', '.join(stocks)}; regime {bench} vs 50d SMA; hedge on QQQ",
        f"- Period: {first} to {last}; ${args.initial_cash:,.0f}",
        "- Aggressive = 1.25% risk per trade, 10 positions, 25% per position, 4 entries/day",
        "- Hedge: ATM 45-DTE QQQ put while SPY < 50d SMA; exit when SPY closes back above, "
        "at 5 DTE (re-buy if still bearish), or trailing 40% after +100%",
        "",
        "| Variant | Return % | CAGR % | Max DD % | Sharpe | "
        + " | ".join(w[0] + " %" for w in windows)
        + " | Median Sharpe (subsets) | Median DD % |",
        "|---|" + "---:|" * (6 + len(windows)),
    ]
    for name, (curve, _) in full.items():
        s = stats(curve)
        sub = [stats(v[name][0]) for v in subs]
        lines.append(
            f"| {name} | {s['ret']:+.1f} | {s['cagr']:+.1f} | {s['dd']:.1f} | {s['sharpe']:.2f} | "
            + " | ".join(f"{window(curve, a, b):+.1f}" for _, a, b in windows)
            + f" | {statistics.median(x['sharpe'] for x in sub):.2f} | "
            f"{statistics.median(x['dd'] for x in sub):.1f} |"
        )
    lines += ["", "## Hedge trades", ""]
    for name, (_, trades) in full.items():
        if not trades:
            continue
        pnl = sum(t.pnl for t in trades)
        win = sum(t.pnl > 0 for t in trades)
        lines.append(
            f"- **{name}**: {len(trades)} puts ({len(trades) / ((last - first).days / 365):.1f}/yr), "
            f"won {win}, total P&L ${pnl:+,.0f} ({pnl / args.initial_cash * 100:+.1f}% of start equity)"
        )
    lines += [
        "",
        "## Limits",
        "",
        "- QQQ option prices are Black-Scholes from realized vol x 1.15; real index puts carry "
        "skew (usually pricier), so hedge costs are likely understated.",
        "- One period, mostly bullish; large-cap tech chosen with hindsight.",
    ]
    md = "\n".join(lines) + "\n"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out = args.output_dir / f"hedge_backtest_{last}.md"
    out.write_text(md)
    print(md)
    print(f"Report: {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
