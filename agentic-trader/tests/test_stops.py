from datetime import date, timedelta

import pytest
from agentic_trader.models import Bar
from agentic_trader.stops import AtrTrailingStop, FixedPctStop, NoStop, WilderATR, wilder_atr


def _bars(n, rng=2.0, start=100.0):
    d0 = date(2024, 1, 1)
    return [
        Bar(d0 + timedelta(days=i), start, start + rng / 2, start - rng / 2, start, 1e6)
        for i in range(n)
    ]


def test_atr_is_none_until_period_then_equals_constant_range():
    atrs = wilder_atr(_bars(20), period=14)
    assert all(a is None for a in atrs[:13])
    assert atrs[13] == pytest.approx(2.0)
    assert atrs[-1] == pytest.approx(2.0)


def test_atr_uses_gap_from_previous_close():
    bars = _bars(3, rng=1.0)
    gap = Bar(bars[-1].date + timedelta(days=1), 90, 90.5, 89.5, 90, 1e6)
    atr = WilderATR(period=1)
    for b in bars:
        atr.update(b)
    assert atr.update(gap) == pytest.approx(10.5)  # |low - prev_close| = 100 - 89.5


def test_atr_trailing_initial_and_ratchet():
    p = AtrTrailingStop(3)
    assert p.initial_stop(100, 2) == 94
    assert p.trail(94, 110, 2) == 104  # moves up with highest close
    assert p.trail(104, 105, 2) == 104  # never moves down
    assert p.trail(104, 110, 5) == 104  # wider ATR does not loosen


def test_fixed_pct_never_moves():
    p = FixedPctStop(8)
    assert p.initial_stop(100, 2) == 92
    assert p.trail(92, 150, 2) == 92


def test_no_stop():
    assert NoStop().initial_stop(100, 2) is None
    assert NoStop().trail(None, 120, 2) is None
