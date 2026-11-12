#!/usr/bin/env python3
"""Do trailing stops help on index ETFs and 3x ETFs? Intraday stop orders vs close checks.

Compares buy & hold, ATR / percent trailing stops (resting intraday stop orders that fill at
the stop or at a gap open, and close-checked stops that sell at the next open), a 200-day
SMA trend filter, and the filter combined with a stop. Re-entry after a stop: next open
after a 20-day closing breakout. Cash earns the T-bill rate.

TQQQ / SOXL: real fund data from 2010; the 2000-2026 run uses synthetic 3x series built from
QQQ and ^SOX with intraday highs/lows (fund costs calibrated to TQQQ).

Example:
    python3 agentic-trader/scripts/fetch_ohlcv.py --symbols SPY QQQ TQQQ SOXL \\
        --start 1999-01-01 --adjusted --out-dir data/adj
    python3 agentic-trader/scripts/fetch_ohlcv.py --symbols ^SOX ^IRX \\
        --start 1999-01-01 --out-dir data/adj
    python3 agentic-trader/scripts/run_stop_study.py --data-dir data/adj \\
        --output agentic-trader/docs/stop_study_results.md
"""

from __future__ import annotations

import argparse
import statistics
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from agentic_trader.sim.data import load_csv_dir  # noqa: E402
from agentic_trader.sim.rotation import synthetic_leveraged  # noqa: E402
from agentic_trader.sim.stop_study import StopRule, run_stop_strategy  # noqa: E402
from run_aggressive_research import stats  # noqa: E402

TQQQ_COST_PCT = 2.53  # expense + swap drag that makes synthetic 3x QQQ track real TQQQ


def rules(cost_bps: float, slip_bps: float) -> list[StopRule]:
    c = dict(cost_bps=cost_bps, stop_slip_bps=slip_bps)
    return [
        StopRule("Buy & hold", **c),
        StopRule("ATR 2x intraday", stop="atr", atr_mult=2, **c),
        StopRule("ATR 3x intraday", stop="atr", atr_mult=3, **c),
        StopRule("ATR 4x intraday", stop="atr", atr_mult=4, **c),
        StopRule("ATR 5x intraday", stop="atr", atr_mult=5, **c),
        StopRule("ATR 3x close", stop="atr", atr_mult=3, trigger="close", **c),
        StopRule("10% trail intraday", stop="pct", trail_pct=10, **c),
        StopRule("20% trail intraday", stop="pct", trail_pct=20, **c),
        StopRule("SMA200 only", trend_sma=200, **c),
        StopRule("SMA200 + ATR 3x intraday", stop="atr", atr_mult=3, trend_sma=200, **c),
        StopRule("SMA200 + ATR 4x intraday", stop="atr", atr_mult=4, trend_sma=200, **c),
        StopRule(
            "SMA200 + ATR 3x close", stop="atr", atr_mult=3, trend_sma=200, trigger="close", **c
        ),
        StopRule("SMA200 + 35% trail intraday", stop="pct", trail_pct=35, trend_sma=200, **c),
    ]


EPISODES = [
    ("2008 GFC", date(2007, 10, 9), date(2009, 3, 9)),
    ("2020 Covid", date(2020, 2, 19), date(2020, 3, 23)),
    ("2022 bear", date(2021, 11, 19), date(2022, 12, 28)),
    ("2025 tariff", date(2025, 2, 19), date(2025, 4, 8)),
    ("Oct-Nov 2026", date(2026, 10, 1), date(2026, 11, 11)),
]


def window_return(curve, a: date, b: date) -> float | None:
    pts = [(d, e) for d, e in curve if a <= d <= b]
    if len(pts) < 2:
        return None
    before = [e for d, e in curve if d < a]
    base = before[-1] if before else pts[0][1]
    return (pts[-1][1] / base - 1) * 100


def summarize(res, years: float) -> dict:
    s = stats(res.curve)
    stop_exits = [f for f in res.exits if f.reason == "stop"]
    rts = res.round_trips
    return {
        "cagr": s["cagr"],
        "dd": s["dd"],
        "sharpe": s["sharpe"],
        "stops_yr": len(stop_exits) / years,
        "gap_pct": res.gap_fills / len(stop_exits) * 100 if stop_exits else 0.0,
        "gap_loss": statistics.mean(res.gap_losses) * 100 if res.gap_losses else 0.0,
        "whipsaw": sum(1 for r in rts if r > 0) / len(rts) * 100 if rts else 0.0,
        "rt_cost": statistics.median(rts) * 100 if rts else 0.0,
        "in_mkt": res.days_in / len(res.curve) * 100,
    }


def table(title: str, rows: list[tuple[str, dict]]) -> list[str]:
    out = [
        f"### {title}",
        "",
        "| Rule | CAGR % | Max DD % | Sharpe | Stops/yr | Gap fills % | Avg gap vs stop % "
        "| Bought back higher % | Median round trip % | In market % |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, m in rows:
        out.append(
            f"| {name} | {m['cagr']:+.1f} | {m['dd']:.0f} | {m['sharpe']:.2f} | "
            f"{m['stops_yr']:.1f} | {m['gap_pct']:.0f} | {m['gap_loss']:+.1f} | "
            f"{m['whipsaw']:.0f} | {m['rt_cost']:+.1f} | {m['in_mkt']:.0f} |"
        )
    return out + [""]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--data-dir", type=Path, required=True)
    p.add_argument("--output", type=Path, help="write the markdown report here")
    p.add_argument("--end", type=date.fromisoformat, default=None)
    args = p.parse_args(argv)

    d = load_csv_dir(args.data_dir)
    irx = {b.date: b.close for b in d["^IRX"]}
    end = args.end or min(d["SPY"][-1].date, d["QQQ"][-1].date)
    syn_tqqq = synthetic_leveraged(d["QQQ"], 3, irx, TQQQ_COST_PCT, intraday=True)
    syn_soxl = synthetic_leveraged(d["^SOX"], 3, irx, TQQQ_COST_PCT, intraday=True)

    # (label, bars, regime, start, cost_bps, slip_bps)
    runs = [
        ("SPY 2000-2026", d["SPY"], d["SPY"], date(2000, 1, 3), 2, 5),
        ("QQQ 2000-2026", d["QQQ"], d["QQQ"], date(2000, 1, 3), 2, 5),
        ("TQQQ (synthetic) 2000-2026", syn_tqqq, d["QQQ"], date(2000, 1, 3), 5, 15),
        ("SOXL (synthetic) 2000-2026", syn_soxl, d["^SOX"], date(2000, 1, 3), 5, 15),
        ("SPY 2010-2026", d["SPY"], d["SPY"], date(2010, 6, 1), 2, 5),
        ("QQQ 2010-2026", d["QQQ"], d["QQQ"], date(2010, 6, 1), 2, 5),
        ("TQQQ (real) 2010-2026", d["TQQQ"], d["QQQ"], date(2010, 6, 1), 5, 15),
        ("SOXL (real) 2010-2026", d["SOXL"], d["^SOX"], date(2010, 6, 1), 5, 15),
    ]
    lines = [
        "# Stop-loss study: do trailing stops help on index and 3x ETFs?",
        "",
        f"Generated by `scripts/run_stop_study.py`; data through {end}.",
        "",
        "Columns: *Gap fills* = share of stop exits filled at an opening gap below the stop; "
        "*Avg gap vs stop* = how far below the stop those fills were; *Bought back higher* = "
        "share of stop exits where the re-entry price was above the exit price (the stop "
        "cost money); *Median round trip* = re-entry / exit - 1.",
        "",
    ]
    episode_rows: dict[str, list[tuple[str, list]]] = {}
    for label, bars, regime, start, cost, slip in runs:
        years = sum(1 for b in bars if start <= b.date <= end) / 252
        rows = []
        for rule in rules(cost, slip):
            res = run_stop_strategy(bars, rule, regime, start, end, irx)
            rows.append((rule.name, summarize(res, years)))
            if "2000" in label:
                episode_rows.setdefault(label, []).append(
                    (rule.name, [window_return(res.curve, a, b) for _, a, b in EPISODES])
                )
        lines += table(label, rows)
        print(f"done {label}", file=sys.stderr)

    lines += [
        "## Check: synthetic 3x QQQ vs real TQQQ, 2010-2026",
        "",
        "| Rule | Synthetic CAGR / DD / stops | Real CAGR / DD / stops |",
        "|---|---|---|",
    ]
    for rule in rules(5, 15)[:5] + rules(5, 15)[8:9]:
        pair = []
        for bars in (syn_tqqq, d["TQQQ"]):
            res = run_stop_strategy(bars, rule, d["QQQ"], date(2010, 6, 1), end, irx)
            s = stats(res.curve)
            pair.append(f"{s['cagr']:+.1f} / {s['dd']:.0f} / {res.stops}")
        lines.append(f"| {rule.name} | {pair[0]} | {pair[1]} |")
    lines.append("")

    lines += ["## Crash episodes (return over the window, %)", ""]
    for label, rows in episode_rows.items():
        lines += [
            f"### {label}",
            "",
            "| Rule | " + " | ".join(n for n, *_ in EPISODES) + " |",
            "|---|" + "---:|" * len(EPISODES),
        ]
        for name, vals in rows:
            cells = " | ".join("-" if v is None else f"{v:+.0f}" for v in vals)
            lines.append(f"| {name} | {cells} |")
        lines.append("")

    text = "\n".join(lines)
    if args.output:
        args.output.write_text(text)
        print(f"wrote {args.output}", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
