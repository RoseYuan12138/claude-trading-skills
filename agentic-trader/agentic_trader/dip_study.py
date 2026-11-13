"""High-volume selloff ("capitulation") study: does buying after a big drop on heavy volume
pay, and does a stop on that add help?

Signal on day i (known at the close): the day's return is below -drop_sigma x the stock's
20-day daily-return standard deviation (and at least min_drop_pct), volume is at least
vol_mult x its 50-day average, and optionally the prior close was above its trend SMA.
Trades enter at the next open (no lookahead).
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from .models import Bar
from .stops import wilder_atr


@dataclass(frozen=True)
class DipParams:
    drop_sigma: float = 2.0
    min_drop_pct: float = 3.0
    vol_mult: float = 2.0
    trend_sma: int | None = None  # require the prior close above this SMA ("dip in uptrend")
    sigma_window: int = 20
    vol_window: int = 50


def capitulation_days(bars: list[Bar], p: DipParams) -> list[int]:
    warm = max(p.sigma_window + 1, p.vol_window, (p.trend_sma or 0) + 1)
    closes = [b.close for b in bars]
    rets = [0.0] + [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]
    out = []
    for i in range(warm, len(bars)):
        window = rets[i - p.sigma_window : i]
        sd = statistics.pstdev(window)
        r = rets[i]
        if r > -p.min_drop_pct / 100 or r > -p.drop_sigma * sd:
            continue
        avg_vol = sum(b.volume for b in bars[i - p.vol_window : i]) / p.vol_window
        if avg_vol <= 0 or bars[i].volume < p.vol_mult * avg_vol:
            continue
        if p.trend_sma:
            sma = sum(closes[i - p.trend_sma : i]) / p.trend_sma
            if closes[i - 1] < sma:
                continue
        out.append(i)
    return out


def forward_return(bars: list[Bar], i: int, horizon: int) -> float | None:
    """Return from the next open (i + 1) to the close of day i + horizon."""
    if i + horizon >= len(bars):
        return None
    return bars[i + horizon].close / bars[i + 1].open - 1


@dataclass(frozen=True)
class TrancheTrade:
    signal_index: int
    entry_price: float
    exit_price: float
    exit_index: int
    reason: str  # "time" or "stop"
    stop: float | None
    ret: float  # after costs


def tranche_trade(
    bars: list[Bar],
    i: int,
    hold: int = 20,
    stop_atr: float | None = 2.5,
    cost_bps: float = 5.0,
    atr_period: int = 14,
    atrs: list[float | None] | None = None,
) -> TrancheTrade | None:
    """Buy at the next open, exit at the close ``hold`` days after the signal, or earlier at a
    stop ``stop_atr`` x ATR (as of the signal day) below the entry. A stop fills at the stop
    level, or at the open when the day gaps below it."""
    if i + hold >= len(bars):
        return None
    entry = bars[i + 1].open
    stop = None
    if stop_atr is not None:
        atrs = atrs if atrs is not None else wilder_atr(bars[: i + 1], atr_period)
        a = atrs[i]
        if a is None or not math.isfinite(a):
            return None
        stop = entry - stop_atr * a
    exit_px, exit_i, reason = bars[i + hold].close, i + hold, "time"
    if stop is not None:
        for j in range(i + 1, i + hold + 1):
            b = bars[j]
            if j > i + 1 and b.open <= stop:
                exit_px, exit_i, reason = b.open, j, "stop"
                break
            if b.low <= stop:
                exit_px, exit_i, reason = stop, j, "stop"
                break
    cost = cost_bps / 10_000
    ret = exit_px * (1 - cost) / (entry * (1 + cost)) - 1
    return TrancheTrade(i, entry, exit_px, exit_i, reason, stop, ret)
