"""Index stop-and-re-entry: sell on a stop, buy back when a recovery starts.

Rules are evaluated on each close; the resulting position applies from the next day's
close-to-close return (no lookahead). Out of the market the account earns the short rate.

Exit rules:  "drawdown" x  - close <= x% below the highest close since entering
             "sma" n       - close below its n-day SMA
             "atr" m       - close <= highest close since entry - m x 14-day ATR
             "never"       - buy and hold
Entry rules: "rebound" x   - close >= x% above the lowest close since exiting
             "sma" n       - close at/above its n-day SMA
             "breakout" n  - close above the highest close of the previous n days
             "never"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from ..models import Bar
from ..stops import wilder_atr


@dataclass(frozen=True)
class Rule:
    kind: str
    value: float

    def __str__(self) -> str:
        unit = {"drawdown": "% off the high", "rebound": "% off the low", "atr": " x ATR"}
        if self.kind == "never":
            return "never"
        if self.kind in unit:
            return f"{self.kind} {self.value:g}{unit[self.kind]}"
        return f"{self.kind} {self.value:g}d"


@dataclass
class StopReentryResult:
    curve: list[tuple[date, float]] = field(default_factory=list)
    events: list[tuple[date, str]] = field(default_factory=list)
    time_invested: float = 0.0


def stop_reentry_curve(
    bars: list[Bar],
    exit_rule: Rule,
    entry_rule: Rule,
    start: date,
    end: date,
    cost_bps: float = 5.0,
    rates_pct: dict[date, float] | None = None,
    initial: float = 1.0,
) -> StopReentryResult:
    closes = [b.close for b in bars]
    atrs = wilder_atr(bars, 14) if exit_rule.kind == "atr" else None
    res = StopReentryResult()
    invested = True
    peak = trough = None
    equity, rate, days_in, days = initial, 0.0, 0, 0
    started = False

    prefix = [0.0]
    for c in closes:
        prefix.append(prefix[-1] + c)

    def sma(i, n):
        n = int(n)
        return (prefix[i + 1] - prefix[i + 1 - n]) / n if i >= n - 1 else None

    for i, b in enumerate(bars):
        if rates_pct and b.date in rates_pct:
            new_rate = rates_pct[b.date] / 100
        else:
            new_rate = None
        if b.date > end:
            break
        if b.date >= start:
            if started:
                # apply yesterday's decision to today's return
                if invested:
                    equity *= closes[i] / closes[i - 1]
                    days_in += 1
                else:
                    equity *= 1 + rate / 252
                days += 1
            started = True
            res.curve.append((b.date, equity))
        if new_rate is not None:
            rate = new_rate  # today's rate applies from tomorrow
        c = closes[i]
        # decide at today's close
        if invested:
            peak = c if peak is None else max(peak, c)
            out = False
            k, v = exit_rule.kind, exit_rule.value
            if k == "drawdown":
                out = c <= peak * (1 - v / 100)
            elif k == "sma":
                m = sma(i, v)
                out = m is not None and c < m
            elif k == "atr":
                a = atrs[i]
                out = a is not None and c <= peak - v * a
            if out and b.date >= start:
                invested, trough, peak = False, c, None
                equity *= 1 - cost_bps / 10_000
                res.events.append((b.date, "EXIT"))
        else:
            trough = min(trough, c)
            k, v = entry_rule.kind, entry_rule.value
            back = False
            if k == "rebound":
                back = c >= trough * (1 + v / 100)
            elif k == "sma":
                m = sma(i, v)
                back = m is not None and c >= m
            elif k == "breakout":
                n = int(v)
                back = i >= n and c > max(closes[i - n : i])
            if back:
                invested, peak, trough = True, c, None
                equity *= 1 - cost_bps / 10_000
                res.events.append((b.date, "ENTER"))
        if res.curve and b.date >= start:
            res.curve[-1] = (b.date, equity)
    res.time_invested = days_in / days if days else 1.0
    return res
