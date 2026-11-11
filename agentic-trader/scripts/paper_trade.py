#!/usr/bin/env python3
"""Daily forward paper trade of the LEAPS trend-call strategy.

Run once a day after the close. The first run creates the paper account (--init-cash).
Pass --quote with the real broker price (per share, the mid you would actually get) of the
contract the ticket names; the journal records quote vs model so the backtest's pricing
can be checked against reality.

Examples:
    python3 agentic-trader/scripts/paper_trade.py --fetch --init-cash 50000
    python3 agentic-trader/scripts/paper_trade.py --fetch                 # following days
    python3 agentic-trader/scripts/paper_trade.py --fetch --quote 136.20  # with a real quote

    # $10k agentic account: strike ladder, 95% premium, stop at $100k or below $3k
    python3 agentic-trader/scripts/paper_trade.py --fetch \
        --state agentic-trader/reports/paper/agentic_10k/state.json \
        --journal agentic-trader/reports/paper/agentic_10k/journal.csv \
        --premium-pct 95 --ladder 0.85 0.90 0.95 1.00 --goal 100000 --floor 3000
"""

from __future__ import annotations

import argparse
import csv
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from agentic_trader.paper import PaperState, check_stop, paper_step  # noqa: E402
from agentic_trader.playbook import ItmTrendParams  # noqa: E402
from agentic_trader.sim.data import load_csv_dir  # noqa: E402

JOURNAL_HEADER = (
    "| Date | Action | Contracts | Strike | Expiry | Model $/sh | Quote $/sh | Quote vs model | "
    "Fill $/sh | Equity | Note |\n|---|---|---:|---:|---|---:|---:|---:|---:|---:|---|\n"
)


def fetch_market(days: int = 420) -> Path:
    import fetch_ohlcv  # scripts/fetch_ohlcv.py

    tmp = Path(tempfile.mkdtemp(prefix="paper_trade_"))
    start = date.today() - timedelta(days=days)
    for sym in ("SPY", "QQQ", "^VXN", "^IRX"):
        rows = fetch_ohlcv.fetch(sym, start, date.today())
        with (tmp / f"{sym}.csv").open("w") as fh:
            fh.write("date,open,high,low,close,volume\n")
            fh.writelines(",".join(map(str, r)) + "\n" for r in rows)
    return tmp


CSV_FIELDS = [
    "date",
    "action",
    "contracts",
    "strike",
    "expiry",
    "model_price",
    "quote",
    "quote_vs_model_pct",
    "fill",
    "cash",
    "equity",
    "note",
]


def write_csv_row(path: Path, row, state) -> None:
    new = not path.exists()
    with path.open("a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(CSV_FIELDS)
        gap = row.quote_vs_model_pct
        w.writerow(
            [
                row.date,
                row.action,
                row.contracts,
                f"{row.strike:g}",
                row.expiry or "",
                f"{row.model_price:.2f}",
                "" if row.quote is None else f"{row.quote:.2f}",
                "" if gap is None else f"{gap:+.1f}",
                f"{row.fill:.2f}",
                f"{state.cash:.2f}",
                f"{row.equity:.2f}",
                row.note,
            ]
        )


def write_md_row(path: Path, row) -> None:
    gap = row.quote_vs_model_pct
    if not path.exists():
        path.write_text("# LEAPS trend-call paper journal\n\n" + JOURNAL_HEADER)
    with path.open("a") as fh:
        fh.write(
            f"| {row.date} | {row.action} | {row.contracts} | {row.strike:g} | "
            f"{row.expiry or ''} | {row.model_price:.2f} | "
            f"{'' if row.quote is None else f'{row.quote:.2f}'} | "
            f"{'' if gap is None else f'{gap:+.1f}%'} | {row.fill:.2f} | {row.equity:,.0f} | "
            f"{row.note} |\n"
        )


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--data-dir", type=Path, help="dir with SPY.csv, QQQ.csv, ^VXN.csv, ^IRX.csv")
    p.add_argument("--fetch", action="store_true", help="download fresh data from Yahoo first")
    p.add_argument("--state", type=Path, default=Path("reports/paper/leaps_state.json"))
    p.add_argument("--journal", type=Path, default=Path("reports/paper/leaps_journal.md"))
    p.add_argument("--init-cash", type=float, help="create a new paper account with this cash")
    p.add_argument("--premium-pct", type=float, default=30.0)
    p.add_argument("--quote", type=float, help="real per-share price of the traded contract")
    p.add_argument("--ladder", type=float, nargs="+", help="moneyness ladder, deepest first")
    p.add_argument("--goal", type=float, help="close out and stop trading at this equity")
    p.add_argument("--floor", type=float, default=0.0, help="close out and stop below this")
    p.add_argument("--dry-run", action="store_true", help="print, but do not save")
    args = p.parse_args(argv)

    if args.state.exists():
        state = PaperState.load(args.state)
    elif args.init_cash:
        state = PaperState(cash=args.init_cash)
    else:
        p.error(f"no state at {args.state}: pass --init-cash to start a paper account")

    if state.stop_reason:
        print(f"Account stopped ({state.stop_reason}); equity ${state.equity:,.0f}. Nothing to do.")
        return 0
    data_dir = fetch_market() if args.fetch else args.data_dir
    if data_dir is None:
        p.error("pass --data-dir or --fetch")
    data = load_csv_dir(data_dir)
    as_of = min(data["SPY"][-1].date, data["QQQ"][-1].date)
    if state.history and state.history[-1].date >= as_of:
        print(f"Already stepped for {as_of}; nothing to do.")
        return 0
    vxn = next(b.close for b in reversed(data["^VXN"]) if b.date <= as_of)
    irx = next(b.close for b in reversed(data["^IRX"]) if b.date <= as_of)
    params = ItmTrendParams(premium_pct=args.premium_pct, moneyness_ladder=tuple(args.ladder or ()))
    new_state, row = paper_step(
        state, data["SPY"], data["QQQ"], vxn / 100, irx / 100, params, args.quote
    )
    rows = [row]
    if args.goal:
        new_state, stop_row = check_stop(new_state, args.goal, args.floor)
        if stop_row:
            rows.append(stop_row)

    for row in rows:
        gap = row.quote_vs_model_pct
        print(
            f"{row.date}: {row.action}"
            + (f" {row.contracts} x QQQ {row.strike:g}C {row.expiry}" if row.contracts else "")
            + f" | model ${row.model_price:,.2f}/sh"
            + (f" | quote ${row.quote:,.2f} ({gap:+.1f}% vs model)" if gap is not None else "")
            + f" | equity ${row.equity:,.0f}"
            + (f" | {row.note}" if row.note else "")
        )
    if args.dry_run:
        return 0
    new_state.save(args.state)
    args.journal.parent.mkdir(parents=True, exist_ok=True)
    for row in rows:
        if args.journal.suffix == ".csv":
            write_csv_row(args.journal, row, new_state)
        else:
            write_md_row(args.journal, row)
    print(f"State: {args.state}\nJournal: {args.journal}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
