#!/usr/bin/env python3
"""Paper lottery basket: small bets on cheap far-OTM options, tracked to expiry.

Rules: at most --max-ticket dollars per ticket (default $100), no averaging down, every
ticket logs a thesis. Before expiry tickets are marked with Black-Scholes at the entry
implied vol (model only: a take-profit alert means "check the real quote"); at expiry they
settle at intrinsic value from the underlying's real Yahoo close.

Examples:
    D=agentic-trader/reports/paper/lottery
    python3 agentic-trader/scripts/lottery_basket.py --dir $D init --cash 500
    python3 agentic-trader/scripts/lottery_basket.py --dir $D buy INTC call 92.5 2027-01-15 \\
        --contracts 1 --price 0.60 --thesis "realised vol 86-144% vs 65% implied"
    python3 agentic-trader/scripts/lottery_basket.py --dir $D step --fetch   # daily, after close
    python3 agentic-trader/scripts/lottery_basket.py --dir $D close 0 --price 1.85
    python3 agentic-trader/scripts/lottery_basket.py --dir $D report
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from agentic_trader.lottery import Basket, BasketRules  # noqa: E402
from agentic_trader.options import Right  # noqa: E402

FIELDS = ["date", "event", "ticket", "contracts", "price", "spot", "cash", "equity", "note"]


def last_close(sym: str, upto: date) -> tuple[date, float]:
    import fetch_ohlcv  # scripts/fetch_ohlcv.py

    rows = [r for r in fetch_ohlcv.fetch(sym, upto - timedelta(days=10), upto) if r[0] <= str(upto)]
    if not rows:
        raise RuntimeError(f"no {sym} bars up to {upto}")
    return date.fromisoformat(rows[-1][0]), float(rows[-1][4])


def close_on(sym: str, day: date) -> float | None:
    import fetch_ohlcv

    rows = [r for r in fetch_ohlcv.fetch(sym, day - timedelta(days=7), day) if r[0] <= str(day)]
    return float(rows[-1][4]) if rows else None


def log(path: Path, b: Basket, d, event, ticket="", contracts=0, price=0.0, spot=0.0, note=""):
    new = not path.exists()
    with path.open("a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(FIELDS)
        w.writerow(
            [d, event, ticket, contracts, f"{price:.2f}", f"{spot:.2f}", f"{b.cash:.2f}",
             f"{b.equity:.2f}", note]
        )  # fmt: skip


def report_md(b: Basket) -> str:
    s = b.summary()
    lines = [
        "# Lottery basket (paper)",
        "",
        "PAPER ONLY. Entry prices are the quotes given at entry; open-ticket marks are "
        "Black-Scholes at the entry implied vol (model, not quotes); expired tickets settle at "
        "intrinsic value from the real underlying close.",
        "",
        f"Cash ${b.cash:,.2f} | equity ${s['equity']:,.2f} | tickets {s['tickets']} "
        f"(open {s['open']}, finished {s['closed']}, winners {s['winners']}) | spent "
        f"${s['spent']:,.0f} | realised P/L ${s['realised_pnl']:+,.0f} | open model P/L "
        f"${s['open_model_pnl']:+,.0f}",
        "",
        "| # | Ticket | Qty | Entry | Entry date | Spot at entry | Entry IV | Status | "
        "Mark / exit | Last spot | P/L | Thesis |",
        "|---:|---|---:|---:|---|---:|---:|---|---:|---:|---:|---|",
    ]
    for i, t in enumerate(b.tickets):
        px = t.exit_price if t.status != "open" else t.mark
        lines.append(
            f"| {i} | {t.label} | {t.contracts} | {t.entry_price:.2f} | {t.entry_date} | "
            f"{t.entry_spot:.2f} | {t.entry_iv:.0%} | {t.status} | {px or 0:.2f} | "
            f"{t.last_spot:.2f} | {t.pnl:+,.0f} | {t.thesis} |"
        )
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--dir", type=Path, default=Path("reports/paper/lottery"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init")
    p.add_argument("--cash", type=float, default=500.0)
    p.add_argument("--max-ticket", type=float, default=100.0)
    p = sub.add_parser("buy")
    p.add_argument("symbol")
    p.add_argument("right", choices=["call", "put"])
    p.add_argument("strike", type=float)
    p.add_argument("expiry", type=date.fromisoformat)
    p.add_argument("--contracts", type=int, default=1)
    p.add_argument("--price", type=float, required=True, help="per-share price you would pay")
    p.add_argument("--spot", type=float, help="underlying price (default: last Yahoo close)")
    p.add_argument("--date", type=date.fromisoformat, default=date.today())
    p.add_argument("--rate", type=float, default=0.041)
    p.add_argument("--thesis", required=True, help="why this ticket (logged)")
    p = sub.add_parser("step")
    p.add_argument("--fetch", action="store_true", help="use last Yahoo closes")
    p.add_argument("--spot", action="append", default=[], help="SYMBOL=PRICE (repeatable)")
    p.add_argument("--date", type=date.fromisoformat, default=date.today())
    p = sub.add_parser("close")
    p.add_argument("index", type=int)
    p.add_argument("--price", type=float, required=True, help="real per-share sale price")
    p.add_argument("--date", type=date.fromisoformat, default=date.today())
    sub.add_parser("report")
    args = ap.parse_args(argv)

    state, journal, md = args.dir / "state.json", args.dir / "journal.csv", args.dir / "README.md"
    if args.cmd == "init":
        if state.exists():
            ap.error(f"{state} exists")
        b = Basket(args.cash, BasketRules(max_ticket=args.max_ticket))
        args.dir.mkdir(parents=True, exist_ok=True)
        b.save(state)
        log(journal, b, date.today(), "INIT", note=f"cash ${args.cash:,.0f}")
    else:
        if not state.exists():
            ap.error(f"no basket at {state}: run init first")
        b = Basket.load(state)

    if args.cmd == "buy":
        spot = args.spot
        if spot is None:
            _, spot = last_close(args.symbol, args.date)
        t = b.buy(
            args.symbol, Right(args.right), args.strike, args.expiry, args.contracts,
            args.price, spot, args.date, rate=args.rate, thesis=args.thesis,
        )  # fmt: skip
        b.save(state)
        log(journal, b, args.date, "BUY", t.label, t.contracts, t.entry_price, spot, args.thesis)
        print(
            f"BUY {t.contracts} x {t.label} @ {t.entry_price:.2f} (cost ${t.cost:,.0f}); spot "
            f"{spot:.2f}; implied vol {t.entry_iv:.0%}; cash ${b.cash:,.2f}"
        )
    elif args.cmd == "step":
        spots = dict(kv.split("=") for kv in args.spot)
        spots = {k.upper(): float(v) for k, v in spots.items()}
        open_syms = {t.symbol for t in b.tickets if t.status == "open"}
        if args.fetch:
            for sym in open_syms - set(spots):
                expiring = [t.expiry for t in b.tickets if t.symbol == sym and t.status == "open"]
                day = min(args.date, min(expiring)) if min(expiring) <= args.date else args.date
                px = close_on(sym, day)
                if px is not None:
                    spots[sym] = px
        before = {i: t.status for i, t in enumerate(b.tickets)}
        alerts = b.step(spots, args.date)
        b.save(state)
        for i, t in enumerate(b.tickets):
            if before[i] == "open" and t.status == "expired":
                log(journal, b, args.date, "EXPIRE", t.label, t.contracts, t.exit_price,
                    t.last_spot, f"P/L ${t.pnl:+,.0f}")  # fmt: skip
        for a in alerts:
            log(journal, b, args.date, "TP_ALERT", note=a)
            print("ALERT:", a)
        log(journal, b, args.date, "MARK", note=", ".join(f"{k} {v:.2f}" for k, v in spots.items()))
    elif args.cmd == "close":
        t = b.close(args.index, args.price, args.date)
        b.save(state)
        log(journal, b, args.date, "CLOSE", t.label, t.contracts, args.price, t.last_spot,
            f"P/L ${t.pnl:+,.0f}")  # fmt: skip

    md.write_text(report_md(b))
    print(report_md(b))
    return 0


if __name__ == "__main__":
    sys.exit(main())
