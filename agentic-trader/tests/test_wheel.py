from datetime import date, timedelta

import pytest
from agentic_trader.models import Bar
from agentic_trader.options import Right
from agentic_trader.pricing import bs_delta
from agentic_trader.sim.wheel import WheelConfig, strike_for_delta, wheel_curve


def bars(closes, start=date(2020, 1, 1)):
    return [Bar(start + timedelta(days=i), c, c, c, c, 1) for i, c in enumerate(closes)]


def test_strike_for_delta_hits_the_target():
    k = strike_for_delta(100.0, 30 / 365, 0.04, 0.20, -0.30, Right.PUT, put_skew=0.0)
    assert k < 100
    assert bs_delta(100.0, k, 30 / 365, 0.04, 0.20, Right.PUT) == pytest.approx(-0.30, abs=0.01)
    kc = strike_for_delta(100.0, 30 / 365, 0.04, 0.20, 0.30, Right.CALL, put_skew=0.0)
    assert kc > 100


def run(closes, mode, **kw):
    b = bars(closes)
    iv = {x.date: 20.0 for x in b}
    cfg = WheelConfig(
        mode=mode, cycle_days=5, half_spread_pct=0.0, put_skew=0.0, call_skew=0.0, **kw
    )
    return wheel_curve(b, iv, {}, b[0].date, b[-1].date, cfg)


def test_flat_market_collects_premium():
    res = run([100.0] * 31, "wheel")
    assert res.curve[-1][1] > 1.0  # kept every put premium
    assert res.assignments == 0


def test_crash_assigns_then_sells_calls_and_tracks_the_stock():
    closes = [100.0] * 6 + [70.0] * 25
    res = run(closes, "wheel")
    assert res.assignments == 1
    eq = res.curve[-1][1]
    assert 0.70 < eq < 0.80  # owns the stock bought near the put strike, plus premiums


def test_rally_calls_away_shares():
    closes = [100.0] * 6 + [70.0] * 5 + [120.0] * 20
    res = run(closes, "wheel")
    assert res.assignments == 1 and res.called_away == 1


def test_buy_and_hold_mode_matches_the_stock():
    res = run([100.0, 110.0, 90.0, 120.0], "hold")
    assert res.curve[-1][1] == pytest.approx(1.2)
