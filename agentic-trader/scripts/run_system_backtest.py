#!/usr/bin/env python3
"""Backtest the whole system as described to the user.

- Long sleeve (shares): 20-day breakout above the 50-day SMA, only while the benchmark is
  above its 50-day SMA; ATR 3x trailing stop; the rule-based agent proxy is woken on
  earnings / gaps / drawdowns (losers exited before earnings, stops tightened).
- Bear sleeve (options): put debit spreads only on clear setups -- an earnings-day gap
  down with volume and a weak close, or a failed rally in a downtrend -- skipping entries
  within 7 days of earnings, when modelled IV > 80%, or when the stock is already > 20%
  below its 50-day SMA.

Example:
    python3 agentic-trader/scripts/run_system_backtest.py --data-dir data/ohlcv --start 2021-09-01
"""

from __future__ import annotations

import argparse
import math
import random
import statistics
import sys
from collections import Counter
from dataclasses import replace
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agentic_trader.agent import RuleBasedAgentProxy  # noqa: E402
from agentic_trader.events import EventCalendar  # noqa: E402
from agentic_trader.monitor import MonitorConfig  # noqa: E402
from agentic_trader.options import OptionExitRules, OptionRules  # noqa: E402
from agentic_trader.risk_gate import load_rules  # noqa: E402
from agentic_trader.sim.data import ETF_SYMBOLS, infer_earnings_calendar, load_csv_dir  # noqa: E402
from agentic_trader.sim.engine import SimConfig, run_simulation  # noqa: E402
from agentic_trader.sim.options_engine import OptionSimConfig, OptionSimulator  # noqa: E402
from agentic_trader.stops import AtrTrailingStop  # noqa: E402

BEAR_EXITS = OptionExitRules(
    stop_loss_pct=50, trail_after_pct=50, trail_pct=35, time_stop_dte=5, underlying_stop_atr=2.0
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


def window_return(curve, start: date, end: date) -> float:
    m = dict(curve)
    a = m[max(d for d in m if d <= start)]
    b = m[max(d for d in m if d <= end)]
    return (b / a - 1) * 100


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


class System:
    def __init__(self, data, bench, start, cash, calendar):
        self.data, self.bench, self.start, self.cash, self.cal = data, bench, start, cash, calendar
        base = load_rules(ROOT / "config" / "sim_rules.yaml")
        self.stock_rules = replace(base, max_order_notional=1e15)  # caps scale with equity

    def _d(self, symbols):
        d = {s: self.data[s] for s in symbols}
        d[self.bench] = self.data[self.bench]
        return d

    def shares(self, symbols, cash, agent=True, regime=True):
        cfg = SimConfig(
            initial_cash=cash,
            start_date=self.start,
            untradable=(self.bench,),
            regime_symbol=self.bench if regime else None,
            regime_sma=50,
        )
        res = run_simulation(
            self._d(symbols),
            self.cal,
            self.stock_rules,
            AtrTrailingStop(3),
            RuleBasedAgentProxy() if agent else None,
            monitor_config=MonitorConfig(macro_min_importance=99),
            config=cfg,
        )
        entries = [f for f in res.fills if f.kind == "entry"]
        return res.equity_curve, entries, res.llm_wakeups

    def bear(self, symbols, cash, risk_pct_of_total, setups=("earnings_gap", "failed_rally")):
        sleeve_pct = risk_pct_of_total * self.cash / cash
        rules = OptionRules(
            max_loss_per_trade_pct=sleeve_pct,
            max_total_risk_pct=min(100.0, sleeve_pct * 5),
            max_contracts=10**9,
        )
        cfg = OptionSimConfig(
            initial_cash=cash,
            risk_per_trade_pct=sleeve_pct,
            start_date=self.start,
            signal_mode="bear_setups",
            bear_setups=setups,
            allow_calls=False,
            structure="debit_vertical",
            regime_symbol=self.bench,
            regime_sma=50,
            untradable=(self.bench,),
            earnings_blackout_days=7,
            max_iv=0.8,
            max_extension_pct=20.0,
        )
        sim = OptionSimulator(self._d(symbols), rules, BEAR_EXITS, cfg, calendar=self.cal)
        res = sim.run()
        return res.equity_curve, res.trades, list(sim.positions.values())

    def variants(self, stocks, bear_universe):
        t = self.cash
        out = {}
        c, e, w = self.shares(stocks, t, agent=False, regime=False)
        out["1. shares, no regime filter, no agent"] = (c, len(e), 0, [])
        c, e, w = self.shares(stocks, t, agent=False)
        out["2. shares + SPY 50d filter"] = (c, len(e), 0, [])
        c, e, w = self.shares(stocks, t)
        out["3. shares + filter + agent"] = (c, len(e), w, [])
        longs, e, w = self.shares(stocks, t * 0.8)
        bc, bt, bo = self.bear(bear_universe, t * 0.2, 1.0)
        out["4. FULL: 80% (3) + 20% bear sleeve"] = (
            combine(longs, bc),
            len(e) + len(bt) + len(bo),
            w,
            bt,
        )
        bc, bt, bo = self.bear(bear_universe, t, 2.0)
        out["5. bear sleeve alone (2%/trade)"] = (bc, len(bt) + len(bo), 0, bt)
        bc, bt, bo = self.bear(bear_universe, t, 2.0, ("earnings_gap",))
        out["5a. bear: earnings gaps only"] = (bc, len(bt) + len(bo), 0, bt)
        bc, bt, bo = self.bear(bear_universe, t, 2.0, ("failed_rally",))
        out["5b. bear: failed rallies only"] = (bc, len(bt) + len(bo), 0, bt)
        spy = [(b.date, b.close) for b in self.data[self.bench] if b.date >= self.start]
        out[f"{self.bench} buy & hold"] = (spy, 0, 0, [])
        return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--data-dir", type=Path, required=True)
    p.add_argument("--start", type=date.fromisoformat, required=True)
    p.add_argument("--benchmark", default="SPY")
    p.add_argument("--calendar", type=Path, help="real earnings calendar JSON (else inferred)")
    p.add_argument("--initial-cash", type=float, default=1_000_000.0)
    p.add_argument("--subsets", type=int, default=6)
    p.add_argument("--output-dir", type=Path, default=Path("reports"))
    args = p.parse_args(argv)

    data = load_csv_dir(args.data_dir)
    bench = args.benchmark.upper()
    cal = EventCalendar.from_json(args.calendar) if args.calendar else infer_earnings_calendar(data)
    stocks = sorted(s for s in data if s not in ETF_SYMBOLS)
    bear_universe = stocks + [s for s in ("QQQ",) if s in data]
    system = System(data, bench, args.start, args.initial_cash, cal)
    full = system.variants(stocks, bear_universe)
    rng = random.Random(7)
    subs = []
    for _ in range(args.subsets):
        pick = sorted(rng.sample(stocks, 8))
        subs.append(system.variants(pick, pick + [s for s in ("QQQ",) if s in data]))

    curve0 = full["2. shares + SPY 50d filter"][0]
    first, last = curve0[0][0], curve0[-1][0]
    months = (last - first).days / 30.44
    lines = [
        "# Full System Backtest",
        "",
        f"- Universe: {', '.join(stocks)} (+QQQ for the bear sleeve); regime {bench} vs 50d SMA",
        f"- Period: {first} to {last}; ${args.initial_cash:,.0f} so contract sizes never bind",
        "- Earnings dates: "
        + (str(args.calendar) if args.calendar else "inferred from volume + gaps (~60% accurate)"),
        "",
        "| Variant | Return % | CAGR % | Max DD % | Sharpe | Entries / month | Oct 6 - Nov 10 2026 % "
        "| Median Sharpe (6 subsets) | Median DD % |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, (curve, n_entries, _, _) in full.items():
        s = stats(curve)
        sub = [stats(v[name][0]) for v in subs]
        rate = f"{n_entries / months:.1f}" if n_entries else "–"
        lines.append(
            f"| {name} | {s['ret']:+.1f} | {s['cagr']:+.1f} | {s['dd']:.1f} | {s['sharpe']:.2f} | "
            f"{rate} | {window_return(curve, date(2026, 10, 6), last):+.1f} | "
            f"{statistics.median(x['sharpe'] for x in sub):.2f} | "
            f"{statistics.median(x['dd'] for x in sub):.1f} |"
        )
    years = sorted({d.year for d, _ in curve0})
    lines += ["", "## Return by year (%)", ""]
    lines.append("| Variant | " + " | ".join(map(str, years)) + " |")
    lines.append("|---|" + "---:|" * len(years))
    for name, (curve, _, _, _) in full.items():
        y = yearly(curve)
        lines.append(f"| {name} | " + " | ".join(f"{y.get(v, 0):+.1f}" for v in years) + " |")
    lines += ["", "## Bear sleeve trades (full universe)", ""]
    for name, (_, _, wakes, trades) in full.items():
        if not trades:
            continue
        reasons = Counter(t.reason for t in trades)
        lines.append(
            f"- **{name}**: {len(trades)} closed, win {sum(t.pnl > 0 for t in trades) / len(trades) * 100:.0f}%, "
            f"avg R {statistics.mean(t.r_multiple for t in trades):+.2f}; exits "
            + ", ".join(f"{k} {v}" for k, v in reasons.most_common())
        )
    wakes = full["3. shares + filter + agent"][2]
    lines += [
        "",
        f"Agent wake-ups (variant 3): {wakes} ({wakes / months:.1f} per month).",
        "",
        "## Limits",
        "",
        "- The agent is the rule proxy, not Claude. Option prices are Black-Scholes from "
        "realized vol x 1.15 (no IV crush, no skew). Earnings dates are inferred.",
        "- One mostly-bullish period; large-cap tech chosen with hindsight; daily bars.",
    ]
    md = "\n".join(lines) + "\n"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out = args.output_dir / f"system_backtest_{last}.md"
    out.write_text(md)
    print(md)
    print(f"Report: {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
