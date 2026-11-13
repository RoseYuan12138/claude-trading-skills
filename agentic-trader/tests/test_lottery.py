from datetime import date

import pytest
from agentic_trader.lottery import Basket, BasketRules, implied_vol
from agentic_trader.options import Right
from agentic_trader.pricing import bs_price

D0 = date(2026, 11, 13)
EXP = date(2027, 1, 15)


def basket(cash=500.0, **kw):
    return Basket(cash=cash, rules=BasketRules(**kw))


def test_implied_vol_round_trips():
    iv = implied_vol(0.60, 61.2, 92.5, 63 / 365, 0.04, Right.CALL)
    assert bs_price(61.2, 92.5, 63 / 365, 0.04, iv, Right.CALL) == pytest.approx(0.60, abs=1e-4)


def test_buy_records_ticket_and_debits_cash():
    b = basket()
    t = b.buy("INTC", Right.CALL, 92.5, EXP, 1, 0.60, 61.2, D0, rate=0.04, thesis="vol > IV")
    assert b.cash == pytest.approx(440.0)
    assert t.status == "open" and t.cost == pytest.approx(60.0)
    assert 0.5 < t.entry_iv < 0.8


def test_rules_block_oversized_and_over_budget_tickets():
    b = basket(max_ticket=100.0)
    with pytest.raises(ValueError, match="ticket"):
        b.buy("INTC", Right.CALL, 92.5, EXP, 2, 0.60, 61.2, D0)  # $120 > $100
    with pytest.raises(ValueError, match="cash"):
        basket(cash=50.0).buy("INTC", Right.CALL, 92.5, EXP, 1, 0.60, 61.2, D0)


def test_no_adding_to_a_losing_ticket():
    b = basket()
    b.buy("INTC", Right.CALL, 92.5, EXP, 1, 0.60, 61.2, D0)
    with pytest.raises(ValueError, match="already"):
        b.buy("INTC", Right.CALL, 92.5, EXP, 1, 0.30, 55.0, date(2026, 11, 20))


def test_expiry_settles_at_intrinsic_from_the_real_close():
    b = basket()
    b.buy("INTC", Right.CALL, 92.5, EXP, 1, 0.60, 61.2, D0)
    b.step({"INTC": 100.0}, EXP)
    t = b.tickets[0]
    assert t.status == "expired" and t.exit_price == pytest.approx(7.5)
    assert b.cash == pytest.approx(440 + 750)
    assert t.pnl == pytest.approx(690.0)


def test_expiry_worthless_and_model_mark_before_expiry():
    b = basket()
    b.buy("INTC", Right.CALL, 92.5, EXP, 1, 0.60, 61.2, D0)
    alerts = b.step({"INTC": 61.2}, date(2026, 12, 13))
    assert 0 < b.tickets[0].mark < 0.60 and not alerts
    b.step({"INTC": 80.0}, EXP)
    assert b.tickets[0].status == "expired" and b.tickets[0].pnl == pytest.approx(-60.0)
    assert b.equity == pytest.approx(440.0)


def test_take_profit_alert_when_model_mark_triples():
    b = basket()
    b.buy("INTC", Right.CALL, 92.5, EXP, 1, 0.60, 61.2, D0)
    alerts = b.step({"INTC": 85.0}, date(2026, 12, 1))
    assert alerts and "INTC" in alerts[0]


def test_close_with_quote_and_save_load(tmp_path):
    b = basket()
    b.buy("INTC", Right.CALL, 92.5, EXP, 1, 0.60, 61.2, D0)
    b.close(0, 2.0, date(2026, 12, 1))
    assert b.cash == pytest.approx(640.0) and b.tickets[0].status == "closed"
    b.save(tmp_path / "b.json")
    b2 = Basket.load(tmp_path / "b.json")
    assert b2.cash == pytest.approx(640.0) and b2.tickets[0].pnl == pytest.approx(140.0)
    assert b2.summary()["closed"] == 1 and b2.summary()["realised_pnl"] == pytest.approx(140.0)
