from datetime import date, timedelta

import pytest
from agentic_trader.models import Bar
from agentic_trader.playbook import ItmTrendParams, OpenCall, itm_trend_ticket
from agentic_trader.sim.data import business_days

DAYS = business_days(date(2025, 1, 1), 260)


def spy(rising: bool):
    return [
        Bar(d, p, p, p, p, 1e6)
        for d, p in ((d, 400 + (i if rising else -i) * 0.5) for i, d in enumerate(DAYS))
    ]


def ticket(spy_bars, position=None, equity=100_000.0, **kw):
    return itm_trend_ticket(
        spy_bars,
        qqq_close=600.0,
        as_of=DAYS[-1],
        equity=equity,
        iv=0.22,
        rate=0.04,
        position=position,
        params=ItmTrendParams(**kw),
    )


def test_bull_regime_without_position_buys_an_itm_call():
    t = ticket(spy(True))
    assert t.action == "BUY"
    assert t.strike == pytest.approx(510.0)  # 15% in the money, on the $5 grid
    assert (t.expiry - DAYS[-1]).days >= 270 and t.expiry.weekday() == 4
    assert t.contracts >= 1
    assert t.premium <= 100_000 * 0.30 + 1e-6
    assert 0.8 < t.delta < 1.0
    assert 0.8 < t.exposure < 2.0  # ~1-1.5x QQQ exposure at 30% premium (whole contracts)


def test_bear_regime_means_cash():
    t = ticket(spy(False))
    assert t.action == "CASH" and t.contracts == 0
    t = ticket(spy(False), position=OpenCall(510.0, DAYS[-1] + timedelta(days=90), 2))
    assert t.action == "SELL"


def test_hold_and_roll():
    far = OpenCall(510.0, DAYS[-1] + timedelta(days=150), 2)
    near = OpenCall(510.0, DAYS[-1] + timedelta(days=50), 2)
    assert ticket(spy(True), position=far).action == "HOLD"
    t = ticket(spy(True), position=near)
    assert t.action == "ROLL" and t.contracts >= 1


def test_too_small_account_cannot_buy_one_contract():
    t = ticket(spy(True), equity=5_000.0)
    assert t.action == "BUY" and t.contracts == 0
    assert "too small" in t.note
