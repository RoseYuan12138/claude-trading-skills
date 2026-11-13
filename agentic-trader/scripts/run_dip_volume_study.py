#!/usr/bin/env python3
"""Buy after a high-volume selloff? With or without a stop? Real-data study, 2000-2026.

A. Event study: forward returns (next open -> close after 5 / 20 / 60 days) after a
   capitulation day vs after any day in the same stocks (the baseline).
B. Trades: buy a tranche at the next open, exit after 20 days, with no stop or an ATR stop;
   one trade per stock at a time. Same rules applied to "every 20th day" entries as a
   baseline.

Groups: index ETFs (no survivorship), today's mega-cap survivors (biased upward), and big
names that lagged or collapsed (biased downward). Daily Yahoo bars, split-adjusted, no
dividends; 5 bps cost per side on trades. Events cluster in crashes and are not independent.

Example:
    python3 agentic-trader/scripts/fetch_ohlcv.py --symbols SPY QQQ IWM AAPL ... --start 2000-01-01 \\
        --out-dir data/dip
    python3 agentic-trader/scripts/run_dip_volume_study.py --data-dir data/dip --out report.md
"""

from __future__ import annotations

import argparse
import statistics
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agentic_trader.dip_study import (  # noqa: E402
    DipParams,
    capitulation_days,
    forward_return,
    tranche_trade,
)
from agentic_trader.sim.data import load_csv_dir  # noqa: E402
from agentic_trader.stops import wilder_atr  # noqa: E402

GROUPS = {
    "Index ETFs": ["SPY", "QQQ", "IWM"],
    "Mega-cap survivors": ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO", "TSLA", "AMD"],
    "Laggards / fallen": ["INTC", "CSCO", "IBM", "GE", "C", "BA", "PFE", "T", "F"],
}
SIGNALS = {
    "Big drop only (no volume filter)": DipParams(vol_mult=0.0),
    "Big drop + volume >= 2x (base)": DipParams(),
    "Big drop + volume >= 3x": DipParams(vol_mult=3.0),
    "Base, only in an uptrend (above 200d)": DipParams(trend_sma=200),
    "Base, only in a downtrend (below 200d)": None,  # filled below
}
HORIZONS = (5, 20, 60)
STOPS = {"no stop": None, "stop 2.5 ATR": 2.5, "stop 1.5 ATR": 1.5}


def downtrend_days(bars, p: DipParams, sma=200):
    closes = [b.close for b in bars]
    return [
        i
        for i in capitulation_days(bars, p)
        if i > sma and closes[i - 1] < sum(closes[i - sma : i]) / sma
    ]


def signal_days(bars, name):
    if name == "Base, only in a downtrend (below 200d)":
        return downtrend_days(bars, DipParams())
    return capitulation_days(bars, SIGNALS[name])


def fmt(x, pct=True):
    return "-" if x is None else (f"{x * 100:+.1f}%" if pct else f"{x:.0f}")


def stats(rs):
    if not rs:
        return None
    return {
        "n": len(rs),
        "mean": statistics.mean(rs),
        "median": statistics.median(rs),
        "win": sum(r > 0 for r in rs) / len(rs),
        "p10": sorted(rs)[int(0.1 * (len(rs) - 1))],
    }


def event_study(data, syms, name, split=None):
    out = {h: [] for h in HORIZONS}
    base = {h: [] for h in HORIZONS}
    months = set()
    for s in syms:
        bars = data.get(s)
        if not bars:
            continue
        days = signal_days(bars, name)
        for i in days:
            if split and not (split[0] <= bars[i].date <= split[1]):
                continue
            months.add((bars[i].date.year, bars[i].date.month))
            for h in HORIZONS:
                r = forward_return(bars, i, h)
                if r is not None:
                    out[h].append(r)
        for i in range(250, len(bars)):
            if split and not (split[0] <= bars[i].date <= split[1]):
                continue
            for h in HORIZONS:
                r = forward_return(bars, i, h)
                if r is not None:
                    base[h].append(r)
    return out, base, len(months)


def trades(data, syms, days_fn, stop_atr, hold=20):
    rs, stops = [], 0
    for s in syms:
        bars = data.get(s)
        if not bars:
            continue
        atrs = wilder_atr(bars, 14)
        busy_until = -1
        for i in days_fn(bars):
            if i <= busy_until:
                continue
            t = tranche_trade(bars, i, hold=hold, stop_atr=stop_atr, atrs=atrs)
            if t is None:
                continue
            rs.append(t.ret)
            stops += t.reason == "stop"
            busy_until = t.exit_index
    if not rs:
        return None
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r <= 0]
    return {
        "n": len(rs),
        "mean": statistics.mean(rs),
        "win": len(wins) / len(rs),
        "avg_win": statistics.mean(wins) if wins else 0.0,
        "avg_loss": statistics.mean(losses) if losses else 0.0,
        "worst": min(rs),
        "stop_pct": stops / len(rs),
        "pf": (sum(wins) / -sum(losses)) if losses and sum(losses) < 0 else float("inf"),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    data = load_csv_dir(args.data_dir)
    L = ["# High-volume selloff study (2000-2026)\n"]
    L.append(
        "Capitulation day: return <= -2 x the 20-day return stdev and <= -3%, volume >= 2 x "
        "the 50-day average (base). Entry at the next open. Baseline = the same forward return "
        "from every day in the same stocks.\n"
    )

    L.append("## A. Forward returns after the signal vs any day\n")
    for g, syms in GROUPS.items():
        L.append(f"### {g} ({', '.join(s for s in syms if s in data)})\n")
        L.append(
            "| Signal | Events (months) | 5d mean / win | 20d mean / win | 60d mean / win | "
            "20d worst 10% | 20d edge vs any day |"
        )
        L.append("|---|---:|---:|---:|---:|---:|---:|")
        base_row = None
        for name in SIGNALS:
            ev, base, months = event_study(data, syms, name)
            cells = []
            for h in HORIZONS:
                st = stats(ev[h])
                cells.append(f"{fmt(st['mean'])} / {st['win']:.0%}" if st else "-")
            st20, b20 = stats(ev[20]), stats(base[20])
            base_row = base
            edge = st20["mean"] - b20["mean"] if st20 else None
            n = len(ev[5])
            L.append(
                f"| {name} | {n} ({months}) | {' | '.join(cells)} | "
                f"{fmt(st20['p10']) if st20 else '-'} | {fmt(edge)} |"
            )
        cells = []
        for h in HORIZONS:
            st = stats(base_row[h])
            cells.append(f"{fmt(st['mean'])} / {st['win']:.0%}")
        L.append(f"| *Any day (baseline)* | {len(base_row[5])} | {' | '.join(cells)} | "
                 f"{fmt(stats(base_row[20])['p10'])} | - |")  # fmt: skip
        L.append("")

    L.append("### Robustness: base signal by period, 20-day forward return\n")
    L.append("| Group | 2000-2012 signal / any day | 2013-2026 signal / any day |")
    L.append("|---|---:|---:|")
    for g, syms in GROUPS.items():
        cells = []
        for a, b in (
            (date(2000, 1, 1), date(2012, 12, 31)),
            (date(2013, 1, 1), date(2026, 12, 31)),
        ):
            ev, base, _ = event_study(data, syms, "Big drop + volume >= 2x (base)", (a, b))
            s1, s0 = stats(ev[20]), stats(base[20])
            cells.append(f"{fmt(s1['mean']) if s1 else '-'} (n={s1['n'] if s1 else 0}) / "
                         f"{fmt(s0['mean'])}")  # fmt: skip
        L.append(f"| {g} | {' | '.join(cells)} |")
    L.append("")

    L.append("## B. Trades: buy at the next open, hold 20 days, with / without a stop\n")
    L.append(
        "One trade per stock at a time; 5 bps per side. 'Every 20th day' applies the same "
        "rules to entries that ignore the signal.\n"
    )
    for g, syms in GROUPS.items():
        L.append(f"### {g}\n")
        L.append(
            "| Entries | Exit | Trades | Mean | Win rate | Avg win | Avg loss | Worst | "
            "Stopped | Profit factor |"
        )
        L.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        entry_sets = {
            "Base signal": lambda b: capitulation_days(b, DipParams()),
            "Signal in uptrend": lambda b: capitulation_days(b, DipParams(trend_sma=200)),
            "Every 20th day": lambda b: list(range(250, len(b), 20)),
        }
        for en, fn in entry_sets.items():
            for sn, sa in STOPS.items():
                t = trades(data, syms, fn, sa)
                if not t:
                    continue
                L.append(
                    f"| {en} | {sn} | {t['n']} | {fmt(t['mean'])} | {t['win']:.0%} | "
                    f"{fmt(t['avg_win'])} | {fmt(t['avg_loss'])} | {fmt(t['worst'])} | "
                    f"{t['stop_pct']:.0%} | {t['pf']:.2f} |"
                )
        L.append("")
    text = "\n".join(L) + "\n"
    if args.out:
        args.out.write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
