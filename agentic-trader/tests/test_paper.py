from datetime import date, timedelta

import pytest
from agentic_trader.models import Bar
from agentic_trader.paper import PaperState, paper_step
from agentic_trader.playbook import ItmTrendParams
from agentic_trader.sim.data import business_days

DAYS = business_days(date(2025, 1, 1), 300)


def trend(rising: bool, base: float, step: float):
    return [
        Bar(d, p, p, p, p, 1e6)
        for d, p in ((d, base + (i if rising else -i) * step) for i, d in enumerate(DAYS))
    ]


SPY_UP, QQQ_UP = trend(True, 400, 0.5), trend(True, 500, 0.4)
SPY_DOWN = trend(False, 600, 0.5)


def step(state, as_of_idx=-1, spy=SPY_UP, qqq=QQQ_UP, quote=None, **kw):
    as_of = DAYS[as_of_idx]
    spy = [b for b in spy if b.date <= as_of]
    qqq = [b for b in qqq if b.date <= as_of]
    return paper_step(state, spy, qqq, iv=0.22, rate=0.04, params=ItmTrendParams(**kw), quote=quote)


def test_first_bullish_day_buys_and_keeps_equity_roughly_unchanged():
    s0 = PaperState(cash=100_000.0)
    s1, row = step(s0)
    assert row.action == "BUY" and s1.position is not None
    assert s1.cash < 100_000 * 0.8
    assert s1.equity == pytest.approx(100_000, rel=0.02)  # only the bid-ask is lost
    assert s1.position.entry_date == DAYS[-1]


def test_hold_then_roll_then_sell():
    s, _ = step(PaperState(cash=100_000.0), as_of_idx=220)
    s2, row = step(s, as_of_idx=230)
    assert row.action == "HOLD" and s2.position.strike == s.position.strike
    # pretend expiry is close: the next step must roll
    near = s2.position.__class__(
        **{**s2.position.__dict__, "expiry": DAYS[230] + timedelta(days=40)}
    )
    s3, row = step(PaperState(cash=s2.cash, position=near, history=s2.history), as_of_idx=231)
    assert row.action == "ROLL" and (s3.position.expiry - DAYS[231]).days >= 270
    s4, row = step(s3, as_of_idx=232, spy=SPY_DOWN)
    assert row.action == "SELL" and s4.position is None and s4.cash > 0


def test_cash_when_bearish_and_flat():
    s, row = step(PaperState(cash=50_000.0), spy=SPY_DOWN)
    assert row.action == "CASH" and s.position is None and s.cash == 50_000.0


def test_real_quote_is_used_and_model_gap_recorded():
    s, row = step(PaperState(cash=100_000.0), quote=150.0)
    assert s.position.entry_price == 150.0
    assert row.model_price > 0 and row.quote == 150.0
    assert row.quote_vs_model_pct == pytest.approx((150.0 / row.model_price - 1) * 100)


def test_state_round_trips_through_json(tmp_path):
    s, _ = step(PaperState(cash=100_000.0))
    path = tmp_path / "state.json"
    s.save(path)
    loaded = PaperState.load(path)
    assert loaded.position == s.position and loaded.cash == pytest.approx(s.cash)
    assert len(loaded.history) == len(s.history) == 1
