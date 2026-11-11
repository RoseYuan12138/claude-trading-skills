from datetime import date

import pytest
from agentic_trader.models import Bar
from agentic_trader.sim.data import business_days
from agentic_trader.sim.rotation import rotation_curve

DAYS = business_days(date(2024, 1, 1), 120)


def bars(prices):
    return [Bar(d, p, p, p, p, 1) for d, p in zip(DAYS, prices)]


def test_buy_and_hold_matches_asset_return():
    a = bars([100 * 1.01**i for i in range(120)])
    c = rotation_curve(a, None, DAYS[10], DAYS[-1])
    assert c[-1][1] / c[0][1] == pytest.approx(a[-1].close / a[10].close)


def test_cash_when_regime_is_below_sma_and_one_day_delay():
    a = bars([100 + i for i in range(120)])
    falling = bars([200 - i for i in range(120)])
    c = rotation_curve(a, falling, DAYS[60], DAYS[-1], sma=20, switch_cost_bps=0)
    assert c[-1][1] == pytest.approx(c[0][1])  # never invested
    # regime turns bullish only from day 80: the gain starts the day after the signal
    turn = [200 - i for i in range(80)] + [120 + 5 * i for i in range(40)]
    c = rotation_curve(a, bars(turn), DAYS[60], DAYS[-1], sma=5, switch_cost_bps=0)
    m = dict(c)
    signal_day = next(DAYS[i] for i in range(80, 120) if turn[i] >= sum(turn[i - 4 : i + 1]) / 5)
    k = DAYS.index(signal_day)
    assert m[DAYS[k]] == pytest.approx(m[DAYS[60]])  # not yet invested on the signal day
    assert m[DAYS[k + 1]] > m[DAYS[k]]


def test_switch_cost_applied():
    a = bars([100.0] * 120)
    flip = bars([100 + (5 if (i // 10) % 2 else -5) for i in range(120)])
    c = rotation_curve(a, flip, DAYS[30], DAYS[-1], sma=10, switch_cost_bps=10)
    assert c[-1][1] < c[0][1]


def test_synthetic_leveraged_one_x_without_costs_matches_asset():
    from agentic_trader.sim.rotation import synthetic_leveraged

    a = bars([100 * (1.01 if i % 2 else 0.995) ** i for i in range(120)])
    s = synthetic_leveraged(a, 1.0, expense_pct=0.0)
    assert s[-1].close / s[0].close == pytest.approx(a[-1].close / a[0].close)


def test_synthetic_leveraged_daily_returns_and_costs():
    from agentic_trader.sim.rotation import synthetic_leveraged

    a = bars([100, 101, 99.99] + [99.99] * 117)
    s = synthetic_leveraged(a, 2.0, {DAYS[0]: 5.04}, expense_pct=0.0)
    assert s[1].close / s[0].close - 1 == pytest.approx(0.02 - 0.0504 / 252)
    wiped = synthetic_leveraged(bars([100, 60] + [60] * 118), 3.0, expense_pct=0.0)
    assert wiped[1].close == 0.0  # a -40% day wipes out a 3x fund
