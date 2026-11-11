#!/usr/bin/env python3
"""Breakout calls in bull regimes + QQQ dip calls when the market score is low.

One account, one premium budget. Breakout calls: 20-day breakout above the 50-day SMA
while SPY is above its 50-day SMA. Dip calls: QQQ ATM call when the market score is
below 30, regardless of regime. Tested out of sample (2011-2021) and in sample
(2021-2026); QQQ options priced off the actual VXN.

Example:
    python3 agentic-trader/scripts/run_combined_calls.py --data-dir data/ohlcv --macro-dir data/macro
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

from agentic_trader.market_score import market_scores  # noqa: E402
from agentic_trader.options import OptionExitRules, OptionRules  # noqa: E402
from agentic_trader.sim.data import ETF_SYMBOLS, load_csv_dir  # noqa: E402
from agentic_trader.sim.options_engine import OptionSimConfig, OptionSimulator  # noqa: E402

EXITS = OptionExitRules(stop_loss_pct=50, trail_after_pct=50, trail_pct=35, time_stop_dte=5)
PERIODS = {
    "out-of-sample 2011-2021": (date(2011, 1, 3), date(2021, 8, 31)),
    "in-sample 2021-2026": (date(2021, 9, 1), date(2026, 11, 10)),
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


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--data-dir", type=Path, required=True)
    p.add_argument("--macro-dir", type=Path, required=True, help="^VIX.csv, ^VXN.csv, HYG.csv")
    p.add_argument("--initial-cash", type=float, default=1_000_000.0)
    p.add_argument("--subsets", type=int, default=6)
    p.add_argument("--output-dir", type=Path, default=Path("reports"))
    args = p.parse_args(argv)

    data = load_csv_dir(args.data_dir)
    macro = load_csv_dir(args.macro_dir)
    stocks = sorted(s for s in data if s not in ETF_SYMBOLS)
    scores = {
        d: m.score
        for d, m in market_scores(
            {**{s: data[s] for s in stocks}, "SPY": data["SPY"]},
            "SPY",
            vix=macro.get("^VIX"),
            credit=macro.get("HYG"),
            breadth_symbols=stocks,
        ).items()
    }
    vxn = {"QQQ": {b.date: b.close for b in macro["^VXN"]}}

    def run(symbols, start, end, *, mode, risk=5.0, dip=None, cap=10.0, iv=1.15):
        d = {s: [b for b in data[s] if b.date <= end] for s in symbols}
        d["SPY"] = [b for b in data["SPY"] if b.date <= end]
        base = dict(
            initial_cash=args.initial_cash,
            start_date=start,
            untradable=("SPY",),
            hedge_symbols=("QQQ",),
            dip_threshold=30.0,
            target_dte=45 if mode == "dip" else 35,
            iv_premium=iv,
        )
        if mode == "dip":
            cfg = OptionSimConfig(**base, signal_mode="score_dip", risk_per_trade_pct=dip or risk)
        else:
            cfg = OptionSimConfig(
                **base,
                risk_per_trade_pct=risk,
                regime_symbol="SPY",
                regime_sma=50,
                allow_puts=False,
                dip_overlay=dip is not None,
                dip_risk_pct=dip,
            )
        rules = OptionRules(
            max_loss_per_trade_pct=max(risk, dip or 0) + 0.01,
            max_total_risk_pct=cap,
            max_open_positions=50,
            max_entries_per_day=10,
            daily_loss_limit_pct=100.0,
            max_contracts=10**9,
            max_dte=120,
        )
        res = OptionSimulator(d, rules, EXITS, cfg, scores=scores, iv_overrides=vxn).run()
        return res

    universe = stocks + ["QQQ"]
    variants = [
        ("A. stocks: breakout calls 5% (cap 10%)", universe, dict(mode="breakout")),
        ("B. QQQ dip calls only, 5%", ["QQQ"], dict(mode="dip", dip=5.0, cap=5.01)),
        ("C. A + QQQ dip calls 5% (cap 15%)", universe, dict(mode="breakout", dip=5.0, cap=15.0)),
        ("D. A + QQQ dip calls 2% (cap 12%)", universe, dict(mode="breakout", dip=2.0, cap=12.0)),
        (
            "E. C with stock options at 1.4x IV",
            universe,
            dict(mode="breakout", dip=5.0, cap=15.0, iv=1.4),
        ),
        ("F. QQQ only: breakout calls 5%", ["QQQ"], dict(mode="breakout", cap=5.01)),
        ("G. QQQ only: breakout + dip calls 5%", ["QQQ"], dict(mode="breakout", dip=5.0, cap=5.01)),
    ]

    lines = [
        "# Combined: Breakout Calls (Bull Regime) + QQQ Dip Calls (Low Score)",
        "",
        "- One account and one premium budget; exits for both: -50% premium stop, trailing "
        "after +50%, 5-DTE time stop",
        "- QQQ options priced off the actual VXN; single-stock options off 20d realized vol x1.15",
        "- **The 10-stock universe is today's winners, so the 2011-2021 stock rows carry heavy "
        "survivorship bias; the QQQ-only rows (F, G) do not.**",
        "",
    ]
    rng = random.Random(7)
    for pname, (start, end) in PERIODS.items():
        refs = {}
        for sym in ("QQQ", "SPY"):
            bars = [b for b in data[sym] if start <= b.date <= end]
            refs[sym] = stats([(b.date, b.close) for b in bars])
        lines += [
            f"## {pname} ({start} to {end})",
            "",
            f"Buy & hold: QQQ {refs['QQQ']['ret']:+.0f}% (CAGR {refs['QQQ']['cagr']:+.1f}%, DD "
            f"{refs['QQQ']['dd']:.0f}%, Sharpe {refs['QQQ']['sharpe']:.2f}); SPY "
            f"{refs['SPY']['ret']:+.0f}% (CAGR {refs['SPY']['cagr']:+.1f}%, DD {refs['SPY']['dd']:.0f}%)",
            "",
            "| Variant | Return % | CAGR % | Max DD % | Sharpe | Trades | Dip trades | Worst year % "
            "| Median Sharpe (subsets) |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        available = [s for s in stocks if data[s][0].date <= start]
        subsets = [
            sorted(rng.sample(available, min(8, len(available)))) + ["QQQ"]
            for _ in range(args.subsets)
        ]
        yearly_rows = []
        for name, syms, kw in variants:
            res = run(syms, start, end, **kw)
            s = stats(res.equity_curve)
            dips = sum(1 for t in res.trades if t.setup == "score_dip")
            if len(syms) > 1:
                sub = statistics.median(
                    stats(run(x, start, end, **kw).equity_curve)["sharpe"] for x in subsets
                )
                sub_txt = f"{sub:.2f}"
            else:
                sub_txt = "–"
            lines.append(
                f"| {name} | {s['ret']:+.0f} | {s['cagr']:+.1f} | {s['dd']:.0f} | {s['sharpe']:.2f} | "
                f"{len(res.trades)} | {dips} | {min(s['years'].values()):+.0f} | {sub_txt} |"
            )
            if name[0] in "ACFG":
                yearly_rows.append((name, s["years"]))
            print(".", end="", file=sys.stderr, flush=True)
        years = sorted({y for _, ys in yearly_rows for y in ys})
        lines += ["", "Return by year (%):", ""]
        lines.append("| Variant | " + " | ".join(map(str, years)) + " |")
        lines.append("|---|" + "---:|" * len(years))
        for name, ys in yearly_rows:
            lines.append(
                f"| {name[:2]} | " + " | ".join(f"{ys.get(y, 0):+.0f}" for y in years) + " |"
            )
        lines.append("")
    print(file=sys.stderr)
    lines += [
        "## Limits",
        "",
        "- Single-stock option prices are modelled (row E shows 1.4x IV); VXN is index-level "
        "implied vol, without skew or term structure.",
        "- Dip trades are few (a handful of selloffs per decade), so their contribution is noisy.",
    ]
    md = "\n".join(lines) + "\n"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out = args.output_dir / "combined_calls.md"
    out.write_text(md)
    print(md)
    print(f"Report: {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
