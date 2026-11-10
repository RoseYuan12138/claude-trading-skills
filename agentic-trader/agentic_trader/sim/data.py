"""Market data for simulation: CSV loader and a seeded synthetic market.

The synthetic market is built to stress stop logic, not to look pretty:
* Markov bull/bear regimes with fat-tailed crash days (market-wide gaps).
* Quarterly earnings per symbol with large overnight gaps (known in advance).
* FOMC / CPI days with elevated market-wide overnight moves.
"""

from __future__ import annotations

import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path

from ..events import Event, EventCalendar
from ..models import Bar


def business_days(start: date, n: int) -> list[date]:
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def generate_market(
    symbols: list[str],
    n_days: int = 252 * 8,
    seed: int = 1,
    start: date = date(2017, 1, 2),
) -> tuple[dict[str, list[Bar]], EventCalendar]:
    rng = random.Random(seed)
    days = business_days(start, n_days)
    events: list[Event] = []

    # --- macro calendar (deterministic cadence, known in advance) ---
    macro_shock: dict[int, float] = {}
    for i in range(10, n_days, 32):  # ~8 FOMC meetings a year
        events.append(Event(days[i], "fomc", None, 3))
        macro_shock[i] = 0.012
    for i in range(5, n_days, 21):  # monthly CPI
        events.append(Event(days[i], "cpi", None, 3))
        macro_shock[i] = max(macro_shock.get(i, 0.0), 0.010)

    # --- market factor: overnight + intraday returns per day ---
    bull = True
    mkt_on, mkt_id = [], []
    for i in range(n_days):
        if bull and rng.random() < 1 / 300:
            bull = False
        elif not bull and rng.random() < 1 / 70:
            bull = True
        mu, sigma = (0.0005, 0.008) if bull else (-0.0012, 0.018)
        r_on = rng.gauss(mu * 0.3, sigma * 0.45)
        r_id = rng.gauss(mu * 0.7, sigma * 0.85)
        if i in macro_shock:
            r_on += rng.gauss(0, macro_shock[i])
        if not bull and rng.random() < 1 / 90:  # crash day, mostly overnight
            r_on += -rng.uniform(0.04, 0.09)
        mkt_on.append(r_on)
        mkt_id.append(r_id)

    data: dict[str, list[Bar]] = {}
    for sym in symbols:
        beta = rng.uniform(0.8, 1.5)
        idio = rng.uniform(0.010, 0.022)
        drift = rng.uniform(-0.0003, 0.0007)
        base_vol = rng.uniform(2e6, 2e7)
        earn_offset = rng.randrange(10, 63)
        earn_days = set(range(earn_offset, n_days, 63))
        for i in earn_days:
            events.append(Event(days[i], "earnings", sym, 3))

        price = rng.uniform(30, 300)
        bars: list[Bar] = []
        for i, d in enumerate(days):
            r_on = beta * mkt_on[i] + rng.gauss(0, idio * 0.3)
            vol_mult = math.exp(rng.gauss(0, 0.3))
            if i in earn_days:
                scale = 0.07 if rng.random() < 0.8 else 0.14
                r_on += rng.gauss(0, scale)
                vol_mult *= rng.uniform(3, 6)
            r_id = beta * mkt_id[i] + drift + rng.gauss(0, idio * 0.9)
            o = price * math.exp(r_on)
            c = o * math.exp(r_id)
            wiggle = idio * 0.5
            h = max(o, c) * math.exp(abs(rng.gauss(0, wiggle)))
            low = min(o, c) * math.exp(-abs(rng.gauss(0, wiggle)))
            if abs(r_on) > 0.04:
                vol_mult *= 2.5
            bars.append(
                Bar(d, round(o, 2), round(h, 2), round(low, 2), round(c, 2), base_vol * vol_mult)
            )
            price = c
        data[sym] = bars
    return data, EventCalendar(events)


def load_csv_dir(data_dir: str | Path, symbols: list[str] | None = None) -> dict[str, list[Bar]]:
    """Load ``<SYMBOL>.csv`` files with columns date,open,high,low,close,volume."""
    data_dir = Path(data_dir)
    files = sorted(data_dir.glob("*.csv"))
    out: dict[str, list[Bar]] = {}
    for f in files:
        sym = f.stem.upper()
        if symbols and sym not in symbols:
            continue
        with f.open(newline="") as fh:
            rows = list(csv.DictReader(fh))
        bars = []
        for r in rows:
            r = {k.strip().lower(): v for k, v in r.items()}
            bars.append(
                Bar(
                    date.fromisoformat(r["date"][:10]),
                    float(r["open"]),
                    float(r["high"]),
                    float(r["low"]),
                    float(r["close"]),
                    float(r.get("volume") or 0),
                )
            )
        out[sym] = sorted(bars, key=lambda b: b.date)
    if not out:
        raise FileNotFoundError(f"no CSV files found in {data_dir}")
    return out


ETF_SYMBOLS = frozenset({"SPY", "QQQ", "DIA", "IWM", "VOO", "VTI", "XLK", "SMH", "SOXX"})


def _is_quad_witching(d: date) -> bool:
    return d.month in (3, 6, 9, 12) and d.weekday() == 4 and 15 <= d.day <= 21


def infer_earnings_calendar(
    data: dict[str, list[Bar]],
    skip: frozenset[str] = ETF_SYMBOLS,
    volume_mult: float = 1.8,
    gap_pct: float = 2.0,
    lookback: int = 50,
    min_gap: int = 45,
    cluster_days: int = 3,
    market_share: float = 0.4,
) -> EventCalendar:
    """Reconstruct past earnings dates from price/volume (no free history source).

    Candidate day: volume >= ``volume_mult`` x the median of the previous ``lookback``
    days AND an overnight gap or close-to-close move of at least ``gap_pct`` %.
    Dropped: quad-witching days, and days when at least ``market_share`` of the symbols
    are candidates (market-wide events). Within ``cluster_days`` the highest-volume day
    wins; reports are at least ``min_gap`` trading days apart. Real report dates are
    published weeks ahead, so treating these as known in advance is a fair proxy, but
    expect misses and false positives.
    """
    stocks = {s: b for s, b in data.items() if s.upper() not in skip}
    candidates: dict[str, list[int]] = {}
    for sym, bars in stocks.items():
        idx = []
        for i in range(20, len(bars)):
            window = sorted(b.volume for b in bars[max(0, i - lookback) : i])
            median = window[len(window) // 2]
            if median <= 0 or bars[i].volume < volume_mult * median:
                continue
            prev = bars[i - 1].close
            move = max(abs(bars[i].open / prev - 1), abs(bars[i].close / prev - 1)) * 100
            if move < gap_pct or _is_quad_witching(bars[i].date):
                continue
            idx.append(i)
        candidates[sym] = idx

    per_day: dict[date, int] = {}
    for sym, idx in candidates.items():
        for i in idx:
            per_day[stocks[sym][i].date] = per_day.get(stocks[sym][i].date, 0) + 1
    crowded = {
        d for d, n in per_day.items() if len(stocks) >= 3 and n / len(stocks) >= market_share
    }

    events: list[Event] = []
    for sym, idx in candidates.items():
        bars = stocks[sym]
        accepted: list[int] = []
        for i in idx:
            if bars[i].date in crowded:
                continue
            if accepted and i - accepted[-1] <= cluster_days:
                if bars[i].volume > bars[accepted[-1]].volume:
                    accepted[-1] = i
                continue
            if accepted and i - accepted[-1] < min_gap:
                continue
            accepted.append(i)
        events += [Event(bars[i].date, "earnings", sym, 3) for i in accepted]
    return EventCalendar(events)
