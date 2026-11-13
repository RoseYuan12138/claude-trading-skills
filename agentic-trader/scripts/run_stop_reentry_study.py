#!/usr/bin/env python3
"""Index stop-and-re-entry study: sell on a stop in a selloff, buy back when a recovery
starts. QQQ / SPY / IWM (dividend-adjusted), cash at the T-bill rate, 5 bps per switch.

Grid: 11 exit rules x 9 re-entry rules, compared with buy & hold and the 200-day SMA rule,
over 2000-2026 (from the dot-com peak), 2000-2012 and 2013-2026. Medians across the grid
are reported so that one lucky parameter set does not carry the conclusion.

Example:
    python3 agentic-trader/scripts/fetch_ohlcv.py --symbols QQQ SPY IWM --adjusted \\
        --start 1999-01-01 --out-dir data/idx   # plus ^IRX.csv in the same folder
    python3 agentic-trader/scripts/run_stop_reentry_study.py --data-dir data/idx --out r.md
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
from agentic_trader.sim.stop_reentry import Rule, stop_reentry_curve  # noqa: E402

EXITS = [Rule("drawdown", v) for v in (5, 8, 10, 15, 20)]
EXITS += [Rule("sma", v) for v in (50, 100, 200)]
EXITS += [Rule("atr", v) for v in (3, 4, 5)]
ENTRIES = [Rule("rebound", v) for v in (5, 10, 15)]
ENTRIES += [Rule("sma", v) for v in (20, 50, 200)]
ENTRIES += [Rule("breakout", v) for v in (10, 20, 50)]
END = date(2026, 11, 12)


def periods(sym):
    first = date(2001, 6, 1) if sym == "IWM" else date(2000, 1, 3)
    return {
        "full": (first, END),
        "2000-2012": (first, date(2012, 12, 31)),
        "2013-2026": (date(2013, 1, 2), END),
    }


def metrics(res):
    eq = [e for _, e in res.curve]
    rets = [b / a - 1 for a, b in zip(eq, eq[1:])]
    sd = statistics.pstdev(rets)
    peak, dd = eq[0], 0.0
    for e in eq:
        peak = max(peak, e)
        dd = max(dd, 1 - e / peak)
    yrs = (res.curve[-1][0] - res.curve[0][0]).days / 365.25
    cagr = (eq[-1] / eq[0]) ** (1 / yrs) - 1
    return {
        "cagr": cagr * 100,
        "dd": dd * 100,
        "sharpe": statistics.mean(rets) / sd * math.sqrt(252) if sd else 0.0,
        "mar": cagr * 100 / (dd * 100) if dd else 0.0,
        "inv": res.time_invested * 100,
        "trades_yr": len(res.events) / 2 / yrs,
    }


def cell(m):
    return f"{m['cagr']:+.1f}% / {m['dd']:.0f}%"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    data = load_csv_dir(args.data_dir)
    irx = {b.date: b.close for b in data["^IRX"]}
    L = ["# Index stop-and-re-entry study\n"]
    L.append(
        "Sell when the exit rule fires at a close, buy back when the re-entry rule fires; the "
        "position applies from the next day. Dividend-adjusted prices, cash earns ^IRX, 5 bps "
        "per switch. Cells: CAGR / max drawdown.\n"
    )
    for sym in ("QQQ", "SPY", "IWM"):
        bars = data[sym]
        P = periods(sym)
        runs = {}

        def run(ex, en, per):
            key = (str(ex), str(en), per)
            if key not in runs:
                a, b = P[per]
                runs[key] = metrics(stop_reentry_curve(bars, ex, en, a, b, rates_pct=irx))
            return runs[key]

        bh = {p: run(Rule("never", 0), Rule("never", 0), p) for p in P}
        sma200 = {p: run(Rule("sma", 200), Rule("sma", 200), p) for p in P}
        grid = [(ex, en) for ex in EXITS for en in ENTRIES]
        for ex, en in grid:
            for p in P:
                run(ex, en, p)

        L.append(f"## {sym}\n")
        L.append(
            "| Rule (exit -> re-entry) | Full: CAGR / DD | Sharpe | Invested | Trades/yr | "
            "2000-2012 | 2013-2026 |"
        )
        L.append("|---|---:|---:|---:|---:|---:|---:|")

        def row(name, m3):
            f = m3["full"]
            L.append(
                f"| {name} | {cell(f)} | {f['sharpe']:.2f} | {f['inv']:.0f}% | "
                f"{f['trades_yr']:.1f} | {cell(m3['2000-2012'])} | {cell(m3['2013-2026'])} |"
            )

        row("**Buy & hold**", bh)
        row("**200d SMA -> 200d SMA (current rule)**", sma200)
        ranked = sorted(grid, key=lambda g: -run(g[0], g[1], "full")["sharpe"])
        L.append("| *Top 8 by full-period Sharpe:* | | | | | | |")
        for ex, en in ranked[:8]:
            row(f"{ex} -> {en}", {p: run(ex, en, p) for p in P})
        L.append("| *Bottom 3:* | | | | | | |")
        for ex, en in ranked[-3:]:
            row(f"{ex} -> {en}", {p: run(ex, en, p) for p in P})
        L.append("")

        # family medians
        L.append(f"### {sym}: median across the grid, by rule family (full period)\n")
        L.append("| Exit family | Re-entry family | Median CAGR | Median DD | Median Sharpe | "
                 "Beat B&H Sharpe | Beat B&H in both halves |")  # fmt: skip
        L.append("|---|---|---:|---:|---:|---:|---:|")
        fams_ex = sorted({e.kind for e in EXITS}, key=["drawdown", "atr", "sma"].index)
        fams_en = sorted({e.kind for e in ENTRIES}, key=["rebound", "breakout", "sma"].index)
        for fx in fams_ex:
            for fn in fams_en:
                cells = [(ex, en) for ex, en in grid if ex.kind == fx and en.kind == fn]
                ms = [run(ex, en, "full") for ex, en in cells]
                beat = sum(m["sharpe"] > bh["full"]["sharpe"] for m in ms)
                both = sum(
                    run(ex, en, "2000-2012")["sharpe"] > bh["2000-2012"]["sharpe"]
                    and run(ex, en, "2013-2026")["sharpe"] > bh["2013-2026"]["sharpe"]
                    for ex, en in cells
                )
                L.append(
                    f"| {fx} | {fn} | {statistics.median(m['cagr'] for m in ms):+.1f}% | "
                    f"{statistics.median(m['dd'] for m in ms):.0f}% | "
                    f"{statistics.median(m['sharpe'] for m in ms):.2f} | {beat}/{len(ms)} | "
                    f"{both}/{len(ms)} |"
                )
        allm = [run(ex, en, "full") for ex, en in grid]
        L.append(
            f"\nAll {len(grid)} combinations: median CAGR "
            f"{statistics.median(m['cagr'] for m in allm):+.1f}%, median max DD "
            f"{statistics.median(m['dd'] for m in allm):.0f}%, median Sharpe "
            f"{statistics.median(m['sharpe'] for m in allm):.2f} "
            f"(buy & hold {bh['full']['cagr']:+.1f}% / {bh['full']['dd']:.0f}% / "
            f"{bh['full']['sharpe']:.2f}).\n"
        )
        print(f"{sym} done", file=sys.stderr)
    text = "\n".join(L) + "\n"
    if args.out:
        args.out.write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
