#!/usr/bin/env python3
"""Long shares + a put sleeve that only bets on declines when the market is weak.

Long sleeve: share breakouts with an ATR 3x trailing stop, entries only while the
benchmark is above its 50-day SMA. Put sleeve: long puts (no stock needed) on breakdowns,
only while the benchmark is below its 50-day SMA. Each sleeve has its own cash; the
portfolio is their sum.

Example:
    python3 agentic-trader/scripts/run_long_short_sim.py --data-dir data/ohlcv \\
        --start 2021-09-01 --benchmark SPY
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

from agentic_trader.events import EventCalendar  # noqa: E402
from agentic_trader.options import OptionExitRules, OptionRules  # noqa: E402
from agentic_trader.risk_gate import load_rules  # noqa: E402
from agentic_trader.sim.data import ETF_SYMBOLS, load_csv_dir  # noqa: E402
from agentic_trader.sim.engine import SimConfig, run_simulation  # noqa: E402
from agentic_trader.sim.options_engine import OptionSimConfig, OptionSimulator  # noqa: E402
from agentic_trader.stops import AtrTrailingStop  # noqa: E402

EXITS = OptionExitRules(stop_loss_pct=50, trail_after_pct=50, trail_pct=35, time_stop_dte=5)


def stats(curve: list[tuple[date, float]]) -> dict[str, float]:
    eq = [e for _, e in curve]
    rets = [b / a - 1 for a, b in zip(eq, eq[1:]) if a > 0]
    sd = statistics.pstdev(rets) if len(rets) > 1 else 0.0
    peak, dd = eq[0], 0.0
    for e in eq:
        peak = max(peak, e)
        dd = max(dd, 1 - e / peak)
    return {
        "ret": (eq[-1] / eq[0] - 1) * 100,
        "dd": dd * 100,
        "sharpe": statistics.mean(rets) / sd * math.sqrt(252) if sd > 0 else 0.0,
    }


def yearly(curve):
    first, last, prev = {}, {}, None
    for d, e in curve:
        first.setdefault(d.year, prev if prev is not None else e)
        last[d.year] = e
        prev = e
    return {y: (last[y] / first[y] - 1) * 100 for y in first}


def combine(*curves):
    maps = [dict(c) for c in curves]
    dates = sorted(set.intersection(*(set(m) for m in maps)))
    return [(d, sum(m[d] for m in maps)) for d in dates]


class Runner:
    def __init__(self, data, bench, start, cash):
        self.data, self.bench, self.start, self.cash = data, bench, start, cash
        self.rules = load_rules(ROOT / "config" / "sim_rules.yaml")

    def _data(self, symbols):
        d = {s: self.data[s] for s in symbols}
        d[self.bench] = self.data[self.bench]
        return d

    def shares(self, symbols, cash, regime: bool):
        cfg = SimConfig(
            initial_cash=cash,
            start_date=self.start,
            untradable=(self.bench,),
            regime_symbol=self.bench if regime else None,
            regime_sma=50,
        )
        res = run_simulation(
            self._data(symbols), EventCalendar(), self.rules, AtrTrailingStop(3), config=cfg
        )
        return res.equity_curve

    def options(self, symbols, cash, risk_pct_of_total, total, calls, puts):
        sleeve_pct = risk_pct_of_total * total / cash  # risk per trade as % of the sleeve
        rules = OptionRules(
            max_loss_per_trade_pct=sleeve_pct, max_total_risk_pct=min(100.0, sleeve_pct * 5)
        )
        cfg = OptionSimConfig(
            initial_cash=cash,
            risk_per_trade_pct=sleeve_pct,
            start_date=self.start,
            regime_symbol=self.bench,
            regime_sma=50,
            untradable=(self.bench,),
            allow_calls=calls,
            allow_puts=puts,
        )
        res = OptionSimulator(self._data(symbols), rules, EXITS, cfg).run()
        return res.equity_curve, res.trades

    def variants(self, symbols):
        t = self.cash
        out = {}
        out["A. shares long, no filter"] = (self.shares(symbols, t, False), [])
        out["B. shares long, SPY>50d filter"] = (self.shares(symbols, t, True), [])
        for w, risk in ((0.1, 0.5), (0.2, 1.0)):
            puts, trades = self.options(symbols, t * w, risk, t, calls=False, puts=True)
            longs = self.shares(symbols, t * (1 - w), True)
            name = (
                f"{'C' if w == 0.1 else 'D'}. B {100 - int(w * 100)}% + put sleeve {int(w * 100)}%"
            )
            out[name] = (combine(longs, puts), trades)
        curve, trades = self.options(symbols, t, 2.0, t, calls=True, puts=True)
        out["E. options only: calls if SPY>50d, puts if below"] = (curve, trades)
        curve, trades = self.options(symbols, t, 2.0, t, calls=False, puts=True)
        out["F. puts only (SPY<50d), 100% of capital"] = (curve, trades)
        return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--data-dir", type=Path, required=True)
    p.add_argument("--start", type=date.fromisoformat, required=True)
    p.add_argument("--benchmark", default="SPY")
    p.add_argument("--initial-cash", type=float, default=50_000.0)
    p.add_argument("--subsets", type=int, default=6)
    p.add_argument("--subset-size", type=int, default=8)
    p.add_argument("--output-dir", type=Path, default=Path("reports"))
    args = p.parse_args(argv)

    data = load_csv_dir(args.data_dir)
    bench = args.benchmark.upper()
    if bench not in data:
        print(f"benchmark {bench} missing", file=sys.stderr)
        return 1
    runner = Runner(data, bench, args.start, args.initial_cash)
    stocks = sorted(s for s in data if s not in ETF_SYMBOLS)
    rng = random.Random(7)
    subsets = [
        sorted(rng.sample(stocks, min(args.subset_size, len(stocks)))) for _ in range(args.subsets)
    ]

    full = runner.variants(stocks)
    subs = [runner.variants(s) for s in subsets]

    first, last = next(iter(full.values()))[0][0][0], next(iter(full.values()))[0][-1][0]
    lines = [
        "# Long / Short Backtest (shares long + puts when the market is weak)",
        "",
        f"- Universe: {', '.join(stocks)}; regime benchmark {bench} vs its 50-day SMA",
        f"- Period: {first} to {last}; start equity ${args.initial_cash:,.0f}",
        "- Put sleeve: long puts only (no stock needed), ~35 DTE at the money, -50% stop, "
        "trailing stop after +50%, closed 5 days before expiry",
        "- C: puts risk 0.5% of the account per trade; D: 1%; E/F: 2%",
        "",
        "| Variant | Return % | Max DD % | Sharpe | Median return % (subsets) | Median DD % "
        "| Median Sharpe | Beats B (Sharpe) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    b_name = "B. shares long, SPY>50d filter"
    for name, (curve, _) in full.items():
        s = stats(curve)
        sub = [stats(v[name][0]) for v in subs]
        beats = sum(x["sharpe"] > stats(v[b_name][0])["sharpe"] for x, v in zip(sub, subs))
        lines.append(
            f"| {name} | {s['ret']:+.1f} | {s['dd']:.1f} | {s['sharpe']:.2f} | "
            f"{statistics.median(x['ret'] for x in sub):+.1f} | "
            f"{statistics.median(x['dd'] for x in sub):.1f} | "
            f"{statistics.median(x['sharpe'] for x in sub):.2f} | "
            + ("–" if name == b_name else f"{beats} / {len(sub)}")
            + " |"
        )

    years = sorted({d.year for d, _ in full[b_name][0]})
    lines += ["", "## Return by year, full universe (%)", ""]
    lines.append("| Variant | " + " | ".join(map(str, years)) + " |")
    lines.append("|---|" + "---:|" * len(years))
    for name, (curve, _) in full.items():
        y = yearly(curve)
        lines.append(f"| {name} | " + " | ".join(f"{y.get(v, 0):+.1f}" for v in years) + " |")

    lines += ["", "## Put trades (full universe)", ""]
    for name, (_, trades) in full.items():
        puts = [t for t in trades if t.right.value == "put"]
        if not puts:
            continue
        wins = sum(t.pnl > 0 for t in puts)
        lines.append(
            f"- **{name}**: {len(puts)} puts, win rate {wins / len(puts) * 100:.0f}%, "
            f"avg R {statistics.mean(t.r_multiple for t in puts):+.2f}, "
            f"total P&L ${sum(t.pnl for t in puts):+,.0f}"
        )
    lines += [
        "",
        "## Limits",
        "",
        "- Option prices are Black-Scholes from realized vol x 1.15: no IV crush, no skew. "
        "Puts are usually priced *above* this (skew), so put results are likely optimistic.",
        "- One mostly-bullish period; large-cap tech picked with hindsight.",
    ]
    md = "\n".join(lines) + "\n"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out = args.output_dir / f"long_short_backtest_{last}.md"
    out.write_text(md)
    print(md)
    print(f"Report: {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
