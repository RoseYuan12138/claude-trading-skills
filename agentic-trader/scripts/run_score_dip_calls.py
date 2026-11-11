#!/usr/bin/env python3
"""Buy QQQ calls when the market score is low; test in and out of sample.

The idea came from 2021-09..2026-11 data (forward QQQ returns were higher after low
scores), so that period is in-sample. The pre-registered rule is tested on 2011-01..2021-08
as out-of-sample: score < 30 and no open position -> buy an at-the-money 45-DTE QQQ call
risking 2% of equity; -50% premium stop, trailing stop after +50%, close at 5 DTE.
QQQ options are priced with the actual VXN (Nasdaq-100 implied vol index) when given.

Example:
    python3 agentic-trader/scripts/run_score_dip_calls.py --data-dir data/ohlcv --macro-dir data/macro
"""

from __future__ import annotations

import argparse
import math
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

STOP = OptionExitRules(stop_loss_pct=50, trail_after_pct=50, trail_pct=35, time_stop_dte=5)
NO_STOP = OptionExitRules(stop_loss_pct=None, trail_after_pct=None, time_stop_dte=5)
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
    return {
        "ret": (end / eq[0] - 1) * 100,
        "cagr": ((end / eq[0]) ** (1 / years) - 1) * 100,
        "dd": dd * 100,
        "sharpe": statistics.mean(rets) / sd * math.sqrt(252) if sd > 0 else 0.0,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--data-dir", type=Path, required=True)
    p.add_argument("--macro-dir", type=Path, required=True, help="^VIX.csv, ^VXN.csv, HYG.csv")
    p.add_argument("--initial-cash", type=float, default=1_000_000.0)
    p.add_argument("--output-dir", type=Path, default=Path("reports"))
    args = p.parse_args(argv)

    data = load_csv_dir(args.data_dir)
    macro = load_csv_dir(args.macro_dir)
    stocks = sorted(s for s in data if s not in ETF_SYMBOLS)
    scored = market_scores(
        {**{s: data[s] for s in stocks}, "SPY": data["SPY"]},
        "SPY",
        vix=macro.get("^VIX"),
        credit=macro.get("HYG"),
        breadth_symbols=stocks,
    )
    scores = {d: m.score for d, m in scored.items()}
    inverted = {d: 100 - s for d, s in scores.items()}  # "score < 30" on this == score > 70
    vxn = {"QQQ": {b.date: b.close for b in macro["^VXN"]}} if "^VXN" in macro else {}

    variants = [
        ("1. score < 30, 2%/trade [pre-registered]", 30, 2.0, STOP, scores, vxn),
        ("2. score < 20, 2%/trade", 20, 2.0, STOP, scores, vxn),
        ("3. score < 40, 2%/trade", 40, 2.0, STOP, scores, vxn),
        ("4. score < 30, 5%/trade", 30, 5.0, STOP, scores, vxn),
        ("5. score < 30, 2%/trade, no stop", 30, 2.0, NO_STOP, scores, vxn),
        ("6. score < 30, 2%, old pricing (realized vol x1.15)", 30, 2.0, STOP, scores, {}),
        ("C1. control: buy calls any day (always on), 2%", 101, 2.0, STOP, scores, vxn),
        ("C2. control: buy calls only when score > 70, 2%", 30, 2.0, STOP, inverted, vxn),
    ]

    lines = [
        "# Buy QQQ Calls When the Market Score Is Low",
        "",
        "Rule fixed before the out-of-sample run: score < 30 and flat -> buy an ATM 45-DTE QQQ "
        "call risking 2% of equity; -50% stop, trailing after +50%, 5-DTE time stop. Priced "
        "with the actual VXN unless noted. One position at a time.",
        "",
    ]
    for pname, (start, end) in PERIODS.items():
        q = {
            "QQQ": [b for b in data["QQQ"] if b.date <= end],
            "SPY": [b for b in data["SPY"] if b.date <= end],
        }
        bars = [b for b in q["QQQ"] if b.date >= start]
        bh = stats([(b.date, b.close) for b in bars])
        lines += [
            f"## {pname} ({start} to {end})",
            "",
            f"QQQ buy & hold: {bh['ret']:+.0f}% (CAGR {bh['cagr']:+.1f}%, max DD {bh['dd']:.0f}%, "
            f"Sharpe {bh['sharpe']:.2f})",
            "",
            "| Variant | Return % | CAGR % | Max DD % | Sharpe | Trades | Win % | Avg R | "
            "Best R | Time in market % |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for name, thr, risk, exits, sc, iv in variants:
            cfg = OptionSimConfig(
                initial_cash=args.initial_cash,
                risk_per_trade_pct=risk,
                start_date=start,
                signal_mode="score_dip",
                hedge_symbols=("QQQ",),
                dip_threshold=thr,
                untradable=("SPY",),
                target_dte=45,
            )
            rules = OptionRules(
                max_loss_per_trade_pct=risk + 0.01,
                max_total_risk_pct=risk + 0.01,
                max_contracts=10**9,
                max_dte=120,
                daily_loss_limit_pct=100.0,
            )
            sim = OptionSimulator(q, rules, exits, cfg, scores=sc, iv_overrides=iv)
            res = sim.run()
            s = stats(res.equity_curve)
            trades = res.trades
            rs = [t.r_multiple for t in trades]
            held = sum((t.exit_date - t.entry_date).days for t in trades)
            span = (res.equity_curve[-1][0] - res.equity_curve[0][0]).days or 1
            lines.append(
                f"| {name} | {s['ret']:+.0f} | {s['cagr']:+.1f} | {s['dd']:.0f} | {s['sharpe']:.2f} | "
                f"{len(trades)} | {(sum(r > 0 for r in rs) / len(rs) * 100) if rs else 0:.0f} | "
                f"{statistics.mean(rs) if rs else 0:+.2f} | {max(rs) if rs else 0:+.2f} | "
                f"{held / span * 100:.0f} |"
            )
            print(".", end="", file=sys.stderr, flush=True)
        lines.append("")
    print(file=sys.stderr)
    lines += [
        "## Limits",
        "",
        "- VXN is an index-level 30-day implied vol; QQQ ATM 45-DTE options trade close to it, "
        "but skew, term structure and bid-ask are approximated (2.5% of price per fill).",
        "- Low-score days cluster into a handful of selloffs per decade, so trade counts are "
        "small: treat differences of a few trades as noise.",
        "- The breadth component uses today's large-cap tech names (survivorship).",
    ]
    md = "\n".join(lines) + "\n"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out = args.output_dir / "score_dip_calls.md"
    out.write_text(md)
    print(md)
    print(f"Report: {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
