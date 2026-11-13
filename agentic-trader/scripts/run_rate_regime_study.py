#!/usr/bin/env python3
"""Wheel in hiking cycles, buy & hold in cutting cycles? SPY / QQQ, 2000-2026.

Regime from the 3-month T-bill (^IRX) change over a lookback (real time, no Fed foresight).
Strategies: buy & hold, the wheel (0.30-delta put/call, model-priced at VIX/VXN x 0.85),
cash at the T-bill rate. Switching applies the previous day's regime, 5 bps per switch.

Example:
    python3 agentic-trader/scripts/run_rate_regime_study.py --idx-dir data/idx \\
        --macro-dir data/macro --out r.md
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

from agentic_trader.sim.data import load_csv_dir  # noqa: E402
from agentic_trader.sim.rate_regime import mix_by_regime, rate_regimes  # noqa: E402
from agentic_trader.sim.wheel import WheelConfig, wheel_curve  # noqa: E402

END = date(2026, 11, 12)
MAPPINGS = {
    "Always buy & hold": {"hike": "hold", "cut": "hold", "flat": "hold"},
    "Always wheel": {"hike": "wheel", "cut": "wheel", "flat": "wheel"},
    "Your rule: hike -> wheel, cut/flat -> hold": {"hike": "wheel", "cut": "hold", "flat": "hold"},
    "Reverse: hike -> hold, cut -> wheel": {"hike": "hold", "cut": "wheel", "flat": "hold"},
    "Hike -> wheel, cut -> cash, flat -> hold": {"hike": "wheel", "cut": "cash", "flat": "hold"},
    "Hike -> hold, cut -> cash, flat -> hold": {"hike": "hold", "cut": "cash", "flat": "hold"},
}


def stats(curve):
    eq = [e for _, e in curve]
    rets = [b / a - 1 for a, b in zip(eq, eq[1:])]
    sd = statistics.pstdev(rets)
    peak, dd = eq[0], 0.0
    for e in eq:
        peak = max(peak, e)
        dd = max(dd, 1 - e / peak)
    yrs = (curve[-1][0] - curve[0][0]).days / 365.25
    return {
        "cagr": ((eq[-1] / eq[0]) ** (1 / yrs) - 1) * 100,
        "dd": dd * 100,
        "sharpe": statistics.mean(rets) / sd * math.sqrt(252) if sd else 0.0,
    }


def cash_curve(dates, irx):
    out, eq, rate = [], 1.0, 0.0
    for i, d in enumerate(dates):
        if i:
            eq *= 1 + rate / 252
        out.append((d, eq))
        rate = irx.get(d, rate * 100) / 100 if d in irx else rate
    return out


def regime_returns(curve, reg, label):
    """Annualised return of a curve over the days whose previous-day regime == label."""
    m = dict(curve)
    ds = [d for d, _ in curve]
    logs = [
        math.log(m[d] / m[p])
        for p, d in zip(ds, ds[1:])
        if reg.get(p) == label
    ]  # fmt: skip
    if not logs:
        return None, 0
    return (math.exp(statistics.mean(logs) * 252) - 1) * 100, len(logs)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--idx-dir", type=Path, required=True)
    ap.add_argument("--macro-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    idx, macro = load_csv_dir(args.idx_dir), load_csv_dir(args.macro_dir)
    irx = {b.date: b.close for b in idx["^IRX"]}
    setups = {
        "SPY": (idx["SPY"], {b.date: b.close for b in macro["^VIX"]}, date(2000, 1, 3), 0.013),
        "QQQ": (idx["QQQ"], {b.date: b.close for b in macro["^VXN"]}, date(2001, 2, 1), 0.007),
    }
    L = ["# Rate-regime switching: wheel vs buy & hold\n"]
    L.append(
        "Regime = change in the 3-month T-bill over the lookback: 'hike' >= +threshold, "
        "'cut' <= -threshold, else 'flat'. Wheel = 0.30-delta cash-secured puts / covered "
        "calls, model-priced at VIX/VXN x 0.85. Cells: CAGR / max DD / Sharpe.\n"
    )
    reg_main = rate_regimes(irx, 126, 0.25)
    for sym, (bars, iv, first, q) in setups.items():
        hold = wheel_curve(bars, iv, irx, first, END, WheelConfig(mode="hold")).curve
        wheel = wheel_curve(bars, iv, irx, first, END, WheelConfig(div_yield=q, iv_mult=0.85)).curve
        cash = cash_curve([d for d, _ in hold], irx)
        curves = {"hold": hold, "wheel": wheel, "cash": cash}

        L.append(f"## {sym} ({first.year}-2026)\n")
        L.append("### What each strategy earned in each regime (6-month lookback, 0.25 pt)\n")
        L.append("| Regime | Share of days | Buy & hold | Wheel | Cash |")
        L.append("|---|---:|---:|---:|---:|")
        for lab in ("hike", "flat", "cut"):
            row, n = [], 0
            for k in ("hold", "wheel", "cash"):
                r, n = regime_returns(curves[k], reg_main, lab)
                row.append(f"{r:+.1f}%/yr" if r is not None else "-")
            share = n / (len(hold) - 1) * 100
            L.append(f"| {lab} | {share:.0f}% | {' | '.join(row)} |")
        L.append("")

        L.append("### Switching rules (6-month lookback, 0.25 pt), by period\n")
        L.append("| Rule | 2000/01-2026 | 2000/01-2012 | 2013-2026 |")
        L.append("|---|---:|---:|---:|")
        for name, mp in MAPPINGS.items():
            cells = []
            for a, b in ((first, END), (first, date(2012, 12, 31)), (date(2013, 1, 2), END)):
                sub = {k: [(d, e) for d, e in c if a <= d <= b] for k, c in curves.items()}
                s = stats(mix_by_regime(sub, reg_main, mp, "hold"))
                cells.append(f"{s['cagr']:+.1f}% / {s['dd']:.0f}% / {s['sharpe']:.2f}")
            L.append(f"| {name} | {' | '.join(cells)} |")
        L.append("")

        L.append("### Your rule across regime definitions (full period)\n")
        L.append("| Lookback | Threshold | Your rule | Always hold | Always wheel |")
        L.append("|---:|---:|---:|---:|---:|")
        for lb in (63, 126, 252):
            for th in (0.25, 0.5):
                reg = rate_regimes(irx, lb, th)
                cells = [
                    stats(mix_by_regime(curves, reg, MAPPINGS[k], "hold"))
                    for k in (
                        "Your rule: hike -> wheel, cut/flat -> hold",
                        "Always buy & hold",
                        "Always wheel",
                    )
                ]
                L.append(
                    f"| {lb}d | {th} pt | "
                    + " | ".join(f"{s['cagr']:+.1f}% / {s['dd']:.0f}%" for s in cells)
                    + " |"
                )
        L.append("")
    text = "\n".join(L) + "\n"
    if args.out:
        args.out.write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
