#!/usr/bin/env python3
"""Print today's action for the ITM trend-call strategy (and the QLD alternative).

Rule: while SPY and QQQ both close above their 200-day SMAs, hold a ~15% ITM QQQ call with
~270 days to expiry, premium = --premium-pct of the account; roll at 60 days left; sell
and hold cash when either closes below its SMA. Prices are model estimates from VXN; check
the real quote (and use a limit order near the mid) before trading.

Examples:
    # download fresh SPY / QQQ / VXN / T-bill data and print the ticket
    python3 agentic-trader/scripts/strategy_today.py --fetch --equity 50000

    # with an open position: strike 575, expiry 2027-03-19, 1 contract
    python3 agentic-trader/scripts/strategy_today.py --fetch --equity 50000 \\
        --position 575:2027-03-19:1
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from agentic_trader.playbook import ItmTrendParams, OpenCall, itm_trend_ticket  # noqa: E402
from agentic_trader.sim.data import load_csv_dir  # noqa: E402


def parse_position(text: str) -> OpenCall:
    strike, expiry, contracts = text.split(":")
    return OpenCall(float(strike), date.fromisoformat(expiry), int(contracts))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--data-dir", type=Path, help="dir with SPY.csv, QQQ.csv, ^VXN.csv, ^IRX.csv")
    p.add_argument("--fetch", action="store_true", help="download fresh data from Yahoo first")
    p.add_argument("--equity", type=float, required=True, help="account value in dollars")
    p.add_argument("--premium-pct", type=float, default=30.0, help="premium as %% of account")
    p.add_argument("--position", type=parse_position, help="open call as STRIKE:EXPIRY:CONTRACTS")
    args = p.parse_args(argv)

    if args.fetch:
        import fetch_ohlcv  # scripts/fetch_ohlcv.py

        tmp = Path(tempfile.mkdtemp(prefix="strategy_today_"))
        start = date.today() - timedelta(days=420)
        for sym in ("SPY", "QQQ", "^VXN", "^IRX"):
            rows = fetch_ohlcv.fetch(sym, start, date.today())
            with (tmp / f"{sym}.csv").open("w") as fh:
                fh.write("date,open,high,low,close,volume\n")
                fh.writelines(",".join(map(str, r)) + "\n" for r in rows)
        data_dir = tmp
    elif args.data_dir:
        data_dir = args.data_dir
    else:
        p.error("pass --data-dir or --fetch")

    data = load_csv_dir(data_dir)
    spy, qqq = data["SPY"], data["QQQ"]
    as_of = min(spy[-1].date, qqq[-1].date)
    qqq_close = next(b.close for b in reversed(qqq) if b.date <= as_of)
    vxn = next(b.close for b in reversed(data["^VXN"]) if b.date <= as_of)
    irx = next(b.close for b in reversed(data["^IRX"]) if b.date <= as_of)
    params = ItmTrendParams(premium_pct=args.premium_pct)
    t = itm_trend_ticket(
        spy, qqq_close, as_of, args.equity, vxn / 100, irx / 100, args.position, params, qqq
    )
    spy_ok = t.regime_close >= t.regime_sma
    qqq_ok = t.qqq_close >= t.qqq_sma

    print(
        f"As of {as_of}: SPY {t.regime_close:.2f} vs 200d SMA {t.regime_sma:.2f} "
        f"({'above' if spy_ok else 'below'}); QQQ {t.qqq_close:.2f} vs 200d SMA "
        f"{t.qqq_sma:.2f} ({'above' if qqq_ok else 'below'}); VXN {vxn:.1f}; T-bill {irx:.2f}%"
    )
    print(f"ACTION: {t.action}")
    if t.action in {"BUY", "ROLL", "HOLD"}:
        verb = "Hold" if t.action == "HOLD" else "Buy"
        if t.action == "ROLL" and args.position:
            print(
                f"  Sell {args.position.contracts} x QQQ {args.position.strike:g}C "
                f"{args.position.expiry} (limit near the mid)"
            )
        print(
            f"  {verb} {t.contracts} x QQQ {t.strike:g}C expiring {t.expiry} "
            f"(choose the nearest listed monthly expiry on or after this date)"
        )
        print(
            f"  Estimated price ${t.est_price:,.2f}/share = ${t.est_price * 100:,.0f}/contract; "
            f"premium ${t.premium:,.0f} = {t.premium / args.equity * 100:.0f}% of the account "
            f"(this is the most the position can lose)"
        )
        print(f"  Delta {t.delta:.2f} -> QQQ exposure {t.exposure:.2f}x the account")
        if t.note:
            print(f"  Note: {t.note}")
    elif t.action == "SELL":
        print(f"  Sell {t.contracts} contract(s) and hold cash until SPY closes above its SMA")
    else:
        print(f"  {t.note}")
    if spy_ok and qqq_ok and t.exposure > 0:
        qld = min(t.exposure / 2, 1.0) * args.equity
        print(f"ETF alternative with the same exposure: ${qld:,.0f} in QLD (2x QQQ), rest in cash")
    print("Estimates come from a model (VXN + skew). Check the real quote before trading.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
