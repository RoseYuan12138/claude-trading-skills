#!/usr/bin/env python3
"""Download daily OHLCV from Yahoo Finance's public chart API into <SYMBOL>.csv files.

Prices are split-adjusted (not dividend-adjusted). No API key needed. For research
and simulation only: check Yahoo's terms before any other use.

Example:
    python3 agentic-trader/scripts/fetch_ohlcv.py --symbols NVDA AMD SPY \\
        --start 2021-06-01 --out-dir data/ohlcv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

URL = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={p1}&period2={p2}&interval=1d"
)


def to_rows(payload: dict) -> list[tuple]:
    result = payload["chart"]["result"][0]
    offset = timedelta(seconds=result["meta"].get("gmtoffset", 0))
    quote = result["indicators"]["quote"][0]
    rows = []
    for i, ts in enumerate(result.get("timestamp") or []):
        o, h, low, c, v = (quote[k][i] for k in ("open", "high", "low", "close", "volume"))
        if None in (o, h, low, c):
            continue
        d = (datetime.fromtimestamp(ts, timezone.utc) + offset).date()
        rows.append((d.isoformat(), round(o, 4), round(h, 4), round(low, 4), round(c, 4), v or 0))
    return rows


def fetch(sym: str, start: date, end: date, retries: int = 4) -> list[tuple]:
    p1 = int(datetime(start.year, start.month, start.day, tzinfo=timezone.utc).timestamp())
    p2 = int(datetime(end.year, end.month, end.day, tzinfo=timezone.utc).timestamp()) + 86_400
    req = urllib.request.Request(
        URL.format(sym=sym, p1=p1, p2=p2), headers={"User-Agent": "Mozilla/5.0"}
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return to_rows(json.load(resp))
        except Exception as e:  # network / rate limit: back off and retry
            if attempt == retries - 1:
                raise RuntimeError(f"{sym}: {e}") from e
            time.sleep(2 ** (attempt + 1))
    return []


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--symbols", nargs="+", required=True)
    p.add_argument("--start", type=date.fromisoformat, required=True)
    p.add_argument("--end", type=date.fromisoformat, default=date.today())
    p.add_argument("--out-dir", type=Path, default=Path("data/ohlcv"))
    args = p.parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    failed = 0
    for sym in args.symbols:
        try:
            rows = fetch(sym.upper(), args.start, args.end)
        except RuntimeError as e:
            print(e, file=sys.stderr)
            failed += 1
            continue
        with (args.out_dir / f"{sym.upper()}.csv").open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["date", "open", "high", "low", "close", "volume"])
            w.writerows(rows)
        print(f"{sym.upper()}: {len(rows)} bars {rows[0][0]} -> {rows[-1][0]}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
