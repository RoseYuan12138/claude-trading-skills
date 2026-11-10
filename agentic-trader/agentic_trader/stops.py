"""Volatility measures and protective-stop policies (pure functions, no I/O)."""

from __future__ import annotations

from collections.abc import Sequence

from .models import Bar


def true_range(bar: Bar, prev_close: float | None) -> float:
    if prev_close is None:
        return bar.high - bar.low
    return max(bar.high - bar.low, abs(bar.high - prev_close), abs(bar.low - prev_close))


class WilderATR:
    """Incremental Wilder ATR so the daemon can update it bar by bar."""

    def __init__(self, period: int = 14):
        self.period = period
        self._prev_close: float | None = None
        self._seed: list[float] = []
        self.value: float | None = None

    def update(self, bar: Bar) -> float | None:
        tr = true_range(bar, self._prev_close)
        self._prev_close = bar.close
        if self.value is None:
            self._seed.append(tr)
            if len(self._seed) == self.period:
                self.value = sum(self._seed) / self.period
        else:
            self.value = (self.value * (self.period - 1) + tr) / self.period
        return self.value


def wilder_atr(bars: Sequence[Bar], period: int = 14) -> list[float | None]:
    atr = WilderATR(period)
    return [atr.update(b) for b in bars]


class StopPolicy:
    """Decides the initial stop at entry and how it trails afterwards."""

    name = "base"

    def initial_stop(self, entry_price: float, atr: float) -> float | None:
        raise NotImplementedError

    def trail(self, current_stop: float | None, highest_close: float, atr: float) -> float | None:
        """Return the desired stop. Callers only ever ratchet it upward."""
        raise NotImplementedError


class NoStop(StopPolicy):
    name = "no_stop"

    def initial_stop(self, entry_price, atr):
        return None

    def trail(self, current_stop, highest_close, atr):
        return current_stop


class FixedPctStop(StopPolicy):
    def __init__(self, pct: float = 8.0):
        self.pct = pct
        self.name = f"fixed_{pct:g}pct"

    def initial_stop(self, entry_price, atr):
        return round(entry_price * (1 - self.pct / 100), 2)

    def trail(self, current_stop, highest_close, atr):
        return current_stop


class AtrTrailingStop(StopPolicy):
    """Chandelier-style stop: highest close since entry minus ``mult`` x ATR."""

    def __init__(self, mult: float = 3.0):
        self.mult = mult
        self.name = f"atr_trailing_{mult:g}x"

    def initial_stop(self, entry_price, atr):
        return round(entry_price - self.mult * atr, 2)

    def trail(self, current_stop, highest_close, atr):
        proposed = round(highest_close - self.mult * atr, 2)
        return proposed if current_stop is None else max(current_stop, proposed)
