"""Does a trailing stop help? Hold one asset fully invested or in cash, with a stop rule.

Mechanics (daily regular-session bars, no lookahead):

- ``trigger="intraday"`` models a resting broker stop order: it fires when the day's low
  touches the stop and fills at the stop, or at the open when the stock gaps below it.
  Robinhood stops only work in regular hours, so the regular-session bar is the right one;
  overnight moves show up as gaps at the open.
- ``trigger="close"`` checks the close and sells at the next open (ignores intraday wicks).
- The stop is ``highest close since entry - atr_mult x ATR`` (``stop="atr"``) or
  ``highest close x (1 - trail_pct)`` (``stop="pct"``). It only moves up. A new entry starts
  from the entry price and the ATR known before that day.
- After a stop, re-enter at the next open once the close breaks above the highest of the
  prior ``reentry_lookback`` closes (``reentry="breakout"``), or never.
- ``trend_sma``: also hold only while the regime series closes at or above its SMA; a trend
  exit sells at the next open and the asset is bought back at the next open after the
  trend returns (no breakout needed).
- Cash earns the previous day's T-bill rate. ``cost_bps`` applies to every trade,
  ``stop_slip_bps`` extra to stop fills.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from ..models import Bar
from ..stops import WilderATR


@dataclass(frozen=True)
class StopRule:
    name: str
    stop: str = "none"  # "none" | "atr" | "pct"
    atr_mult: float = 3.0
    atr_period: int = 14
    trail_pct: float = 10.0
    trigger: str = "intraday"  # "intraday" | "close"
    reentry: str = "breakout"  # "breakout" | "never"
    reentry_lookback: int = 20
    trend_sma: int | None = None
    cost_bps: float = 5.0
    stop_slip_bps: float = 5.0


@dataclass(frozen=True)
class Fill:
    date: date
    price: float  # raw execution price before costs
    reason: str  # "entry" | "stop" | "trend"
    stop_level: float | None = None


@dataclass
class StopStudyResult:
    rule: StopRule
    curve: list[tuple[date, float]] = field(default_factory=list)
    entries: list[Fill] = field(default_factory=list)
    exits: list[Fill] = field(default_factory=list)
    stop_levels: list[tuple[date, float]] = field(default_factory=list)
    round_trips: list[float] = field(default_factory=list)  # re-entry / stop exit - 1
    gap_fills: int = 0
    gap_losses: list[float] = field(default_factory=list)  # fill / stop - 1 on gaps
    days_in: int = 0

    @property
    def stops(self) -> int:
        return sum(1 for f in self.exits if f.reason == "stop")

    @property
    def trend_exits(self) -> int:
        return sum(1 for f in self.exits if f.reason == "trend")


def _trend_map(regime: list[Bar], sma: int) -> dict[date, bool]:
    closes = [b.close for b in regime]
    out, total = {}, 0.0
    for i, c in enumerate(closes):
        total += c
        if i >= sma:
            total -= closes[i - sma]
        if i >= sma - 1:
            out[regime[i].date] = c >= total / sma
    return out


def run_stop_strategy(
    bars: list[Bar],
    rule: StopRule,
    regime: list[Bar] | None = None,
    start: date | None = None,
    end: date | None = None,
    rates_pct: dict[date, float] | None = None,
    initial: float = 10_000.0,
) -> StopStudyResult:
    """Simulate ``rule`` on ``bars``; bars before ``start`` only warm up ATR and SMA."""
    if rule.trend_sma and regime is None:
        raise ValueError("trend_sma needs regime bars")
    start = start or bars[0].date
    trend = _trend_map(regime, rule.trend_sma) if rule.trend_sma else {}
    res = StopStudyResult(rule)
    cost, slip = rule.cost_bps / 10_000, rule.stop_slip_bps / 10_000

    atr = WilderATR(rule.atr_period)
    atr_prev: float | None = None
    cash, shares = initial, 0.0
    stop_level: float | None = None
    high_close = 0.0
    pending: str | None = None  # "buy" | "sell_stop" | "sell_trend" for the next open
    stopped_out, last_stop_price = False, None
    closes: list[float] = []
    rate = 0.0
    started = False

    def trend_ok(d: date) -> bool:
        return trend.get(d, False) if rule.trend_sma else True

    def initial_stop(price: float) -> float | None:
        if rule.stop == "atr":
            return price - rule.atr_mult * atr_prev if atr_prev is not None else None
        if rule.stop == "pct":
            return price * (1 - rule.trail_pct / 100)
        return None

    def sell(d: date, price: float, reason: str, level: float | None, extra: float):
        nonlocal cash, shares, stop_level, stopped_out, last_stop_price
        cash += shares * price * (1 - cost - extra)
        shares = 0.0
        res.exits.append(Fill(d, price, reason, level))
        stop_level = None
        if reason == "stop":
            stopped_out, last_stop_price = True, price

    for i, b in enumerate(bars):
        if end and b.date > end:
            break
        if b.date < start:
            atr_prev = atr.update(b)
            closes.append(b.close)
            if rates_pct and b.date in rates_pct:
                rate = rates_pct[b.date] / 100
            continue

        if not started:  # first session: buy at the open if allowed as of yesterday
            started = True
            prev_date = bars[i - 1].date if i else None
            if not rule.trend_sma or (prev_date is not None and trend_ok(prev_date)):
                pending = "buy"

        # cash accrues yesterday's rate
        if shares == 0 and cash > 0 and res.curve:
            cash *= 1 + rate / 252

        # ---- open: execute pending orders
        if pending == "buy" and shares == 0:
            shares = cash * (1 - cost) / b.open
            cash = 0.0
            res.entries.append(Fill(b.date, b.open, "entry"))
            if stopped_out and last_stop_price:
                res.round_trips.append(b.open / last_stop_price - 1)
            stopped_out = False
            high_close = b.open
            stop_level = initial_stop(b.open)
        elif pending in {"sell_stop", "sell_trend"} and shares > 0:
            reason = "stop" if pending == "sell_stop" else "trend"
            sell(b.date, b.open, reason, stop_level, slip if reason == "stop" else 0.0)
        pending = None

        # ---- intraday: resting stop order
        if shares > 0 and rule.trigger == "intraday" and stop_level is not None:
            if b.open <= stop_level:
                res.gap_fills += 1
                res.gap_losses.append(b.open / stop_level - 1)
                sell(b.date, b.open, "stop", stop_level, slip)
            elif b.low <= stop_level:
                sell(b.date, stop_level, "stop", stop_level, slip)

        # ---- close: update indicators, decide tomorrow
        atr_prev = atr.update(b)
        if shares > 0:
            res.days_in += 1
            if rule.trigger == "close" and stop_level is not None and b.close <= stop_level:
                pending = "sell_stop"
            high_close = max(high_close, b.close)
            if rule.stop == "atr" and atr_prev is not None:
                new = high_close - rule.atr_mult * atr_prev
                stop_level = new if stop_level is None else max(stop_level, new)
            elif rule.stop == "pct":
                new = high_close * (1 - rule.trail_pct / 100)
                stop_level = new if stop_level is None else max(stop_level, new)
            if stop_level is not None:
                res.stop_levels.append((b.date, stop_level))
            if pending is None and rule.trend_sma and not trend_ok(b.date):
                pending = "sell_trend"
        else:
            lookback = closes[-rule.reentry_lookback :]
            can = trend_ok(b.date)
            if stopped_out:
                can = can and rule.reentry == "breakout" and bool(lookback)
                can = can and b.close > max(lookback)
            if can:
                pending = "buy"
        closes.append(b.close)
        if rates_pct and b.date in rates_pct:
            rate = rates_pct[b.date] / 100
        res.curve.append((b.date, cash + shares * b.close))
    return res
