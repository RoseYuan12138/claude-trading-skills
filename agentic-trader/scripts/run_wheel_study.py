#!/usr/bin/env python3
"""Wheel (cash-secured puts -> covered calls) vs put-writing, buy-write and buy & hold.

SPY priced off VIX (from 2000), QQQ off VXN (from 2001, when VXN starts). Dividend-adjusted
prices, monthly (21 trading-day) options, strikes by delta, base skew, 1% half bid-ask on
each sale, cash at the T-bill rate, no leverage, fractional positions. Model prices only.

Example:
    python3 agentic-trader/scripts/run_wheel_study.py --idx-dir data/idx --macro-dir data/macro
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
from agentic_trader.sim.wheel import WheelConfig, wheel_curve  # noqa: E402

END = date(2026, 11, 12)
VARIANTS = {
    "Buy & hold": WheelConfig(mode="hold"),
    "Wheel, 0.30-delta put / 0.30-delta call": WheelConfig(),
    "Wheel, 0.20-delta put / 0.20-delta call": WheelConfig(put_delta=-0.20, call_delta=0.20),
    "Wheel, ATM put / 0.30-delta call": WheelConfig(put_delta=-0.50),
    "Put-write, ATM (like CBOE PUT)": WheelConfig(mode="putwrite", put_delta=-0.50),
    "Put-write, 0.30 delta": WheelConfig(mode="putwrite"),
    "Buy-write, ATM (like CBOE BXM)": WheelConfig(mode="buywrite", call_delta=0.50),
    "Buy-write, 0.30 delta": WheelConfig(mode="buywrite"),
}
WINDOWS = {
    "2008": (date(2008, 1, 2), date(2008, 12, 31)),
    "2022": (date(2022, 1, 3), date(2022, 12, 30)),
    "2023-24": (date(2023, 1, 3), date(2024, 12, 31)),
    "2025 to 11/28": (date(2025, 1, 2), date(2025, 11, 28)),
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
        "vol": sd * math.sqrt(252) * 100,
        "total": (eq[-1] / eq[0] - 1) * 100,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--idx-dir", type=Path, required=True, help="adjusted SPY/QQQ + ^IRX")
    ap.add_argument("--macro-dir", type=Path, required=True, help="^VIX and ^VXN")
    ap.add_argument("--iv-mult", type=float, default=0.85, help="ATM IV = VIX/VXN x this")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    idx, macro = load_csv_dir(args.idx_dir), load_csv_dir(args.macro_dir)
    irx = {b.date: b.close for b in idx["^IRX"]}
    setups = {
        "SPY": (idx["SPY"], {b.date: b.close for b in macro["^VIX"]}, date(2000, 1, 3), 0.013),
        "QQQ": (idx["QQQ"], {b.date: b.close for b in macro["^VXN"]}, date(2001, 2, 1), 0.007),
    }
    L = ["# Wheel / put-write / buy-write vs buy & hold\n"]
    L.append(
        f"Model prices: Black-Scholes, ATM implied vol = VIX / VXN x {args.iv_mult:g}, plus "
        "skew; monthly options, 1% half bid-ask, no leverage, cash at the T-bill rate, "
        "dividend-adjusted prices.\n"
    )
    for sym, (bars, iv, first, q) in setups.items():
        L.append(f"## {sym} ({first.year}-2026)\n")
        L.append(
            "| Strategy | CAGR | Max DD | Vol | Sharpe | 2000/01-2012 CAGR | 2013-2026 CAGR | "
            + " | ".join(WINDOWS)
            + " |"
        )
        L.append("|---|---:|---:|---:|---:|---:|---:|" + "---:|" * len(WINDOWS))
        for name, cfg in VARIANTS.items():
            cfg = WheelConfig(**{**cfg.__dict__, "div_yield": q, "iv_mult": args.iv_mult})
            full = wheel_curve(bars, iv, irx, first, END, cfg)
            s = stats(full.curve)
            a = stats(wheel_curve(bars, iv, irx, first, date(2012, 12, 31), cfg).curve)
            b = stats(wheel_curve(bars, iv, irx, date(2013, 1, 2), END, cfg).curve)
            wins = [
                stats(wheel_curve(bars, iv, irx, x, y, cfg).curve)["total"]
                for x, y in WINDOWS.values()
            ]
            extra = ""
            if cfg.mode == "wheel":
                extra = f" ({full.assignments} assigned, {full.called_away} called away)"
            L.append(
                f"| {name}{extra} | {s['cagr']:+.1f}% | {s['dd']:.0f}% | {s['vol']:.0f}% | "
                f"{s['sharpe']:.2f} | {a['cagr']:+.1f}% | {b['cagr']:+.1f}% | "
                + " | ".join(f"{w:+.1f}%" for w in wins)
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
