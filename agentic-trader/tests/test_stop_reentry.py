from datetime import date, timedelta

import pytest
from agentic_trader.models import Bar
from agentic_trader.sim.stop_reentry import Rule, stop_reentry_curve


def bars(closes, start=date(2020, 1, 1)):
    return [Bar(start + timedelta(days=i), c, c, c, c, 1) for i, c in enumerate(closes)]


def run(closes, exit_rule, entry_rule, **kw):
    b = bars(closes)
    return stop_reentry_curve(b, exit_rule, entry_rule, b[0].date, b[-1].date, cost_bps=0, **kw)


def test_drawdown_stop_exits_then_rebound_reenters():
    # up to 100, crash to 80 (-20%), bottom at 70, rebound to 77 (+10% off the low), then 90
    closes = [100.0] * 5 + [90.0, 80.0, 75.0, 70.0, 72.0, 77.0, 80.0, 90.0]
    res = run(closes, Rule("drawdown", 10), Rule("rebound", 10))
    # exit signal at the close of 90 (-10%): flat from the next day on
    assert res.events[0][1] == "EXIT" and res.events[0][0] == date(2020, 1, 6)
    assert res.events[1][1] == "ENTER" and res.events[1][0] == date(2020, 1, 11)
    eq = dict(res.curve)
    # invested through day 6 (100 -> 90), flat while it falls to 70 and back to 77,
    # invested again from 77 -> 80 -> 90
    assert eq[date(2020, 1, 13)] == pytest.approx(0.9 * 90 / 77)


def test_sma_rules_and_signal_lag():
    closes = [10.0] * 5 + [12.0] * 5 + [8.0] * 5 + [12.0] * 5
    res = run(closes, Rule("sma", 3), Rule("sma", 3))
    kinds = [k for _, k in res.events]
    assert kinds == ["EXIT", "ENTER"]
    eq = dict(res.curve)
    # exit at the close of the first 8 (day 11); the 12 -> 8 move is taken, nothing after
    assert eq[date(2020, 1, 15)] == pytest.approx(8 / 10)


def test_breakout_reentry_and_cash_rate():
    closes = [100.0, 100.0, 80.0, 79.0, 78.0, 81.0, 82.0]
    rates = {date(2020, 1, 1): 25.2}  # 25.2%/yr -> 0.1% a trading day
    res = run(closes, Rule("drawdown", 15), Rule("breakout", 3), rates_pct=rates)
    assert [k for _, k in res.events] == ["EXIT", "ENTER"]
    eq = dict(res.curve)
    # flat on days 4-6 (3 days of cash at 0.1%), re-enter at the close of 81 (> max of 80, 79, 78)
    assert eq[date(2020, 1, 6)] == pytest.approx(0.8 * 1.001**3)
    assert eq[date(2020, 1, 7)] == pytest.approx(0.8 * 1.001**3 * 82 / 81)


def test_buy_and_hold_rule_never_exits():
    res = run([1.0, 2.0, 0.5, 3.0], Rule("never", 0), Rule("never", 0))
    assert not res.events and res.curve[-1][1] == pytest.approx(3.0)
    assert res.time_invested == pytest.approx(1.0)
