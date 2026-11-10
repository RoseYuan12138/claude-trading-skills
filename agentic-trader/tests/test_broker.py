from datetime import date

import pytest
from agentic_trader.models import Bar, OrderIntent, OrderType, Purpose, Side
from agentic_trader.sim.broker import SimBroker

D1, D2, D3, D4 = (date(2024, 1, d) for d in (1, 2, 3, 4))


def bar(d, o, h, low, c):
    return Bar(d, o, h, low, c, 1e6)


def entry(qty=100, stop=95.0):
    return OrderIntent("AAA", Side.BUY, qty, Purpose.ENTRY, 100.0, stop_price=stop)


def stop_update(new_stop, qty=100):
    return OrderIntent(
        "AAA", Side.SELL, qty, Purpose.STOP_UPDATE, 100.0, OrderType.STOP, stop_price=new_stop
    )


@pytest.fixture
def broker():
    return SimBroker(cash=100_000, slippage_bps=0)


def test_market_entry_fills_next_open_and_attaches_stop(broker):
    broker.submit(entry(), as_of=D1)
    assert broker.process_bar("AAA", bar(D1, 99, 101, 98, 100)) == []  # same-day: no fill
    fills = broker.process_bar("AAA", bar(D2, 101, 102, 100, 101))
    assert [(f.kind, f.price, f.qty) for f in fills] == [("entry", 101, 100)]
    assert broker.cash == pytest.approx(100_000 - 10_100)
    pos = broker.positions["AAA"]
    assert pos.qty == 100 and pos.stop_price == 95.0


def test_stop_fills_at_stop_when_touched_intraday(broker):
    broker.submit(entry(), as_of=D1)
    broker.process_bar("AAA", bar(D2, 100, 101, 99, 100))
    fills = broker.process_bar("AAA", bar(D3, 97, 98, 94, 96))
    assert [(f.kind, f.price) for f in fills] == [("stop", 95.0)]
    assert "AAA" not in broker.positions
    assert broker.cash == pytest.approx(100_000 - 10_000 + 9_500)


def test_gap_through_stop_fills_at_open(broker):
    broker.submit(entry(), as_of=D1)
    broker.process_bar("AAA", bar(D2, 100, 101, 99, 100))
    fills = broker.process_bar("AAA", bar(D3, 88, 90, 85, 89))
    assert fills[0].kind == "stop" and fills[0].price == 88
    trade = broker.closed_trades[-1]
    assert trade.gapped_through_stop
    assert trade.r_multiple == pytest.approx((88 - 100) / 5)


def test_stop_update_replaces_stop_and_applies_next_bar(broker):
    broker.submit(entry(), as_of=D1)
    broker.process_bar("AAA", bar(D2, 100, 110, 99, 109))
    broker.submit(stop_update(105), as_of=D2)
    assert broker.positions["AAA"].stop_price == 105
    fills = broker.process_bar("AAA", bar(D3, 107, 108, 104, 106))
    assert fills[0].price == 105


def test_exit_closes_position_and_cancels_stop(broker):
    broker.submit(entry(), as_of=D1)
    broker.process_bar("AAA", bar(D2, 100, 101, 99, 100))
    broker.submit(OrderIntent("AAA", Side.SELL, 100, Purpose.EXIT, 100.0), as_of=D2)
    fills = broker.process_bar("AAA", bar(D3, 102, 103, 90, 95))
    assert [(f.kind, f.price) for f in fills] == [("exit", 102)]
    assert broker.open_stop_orders() == {}


def test_entry_clipped_to_available_cash():
    b = SimBroker(cash=5_000, slippage_bps=0)
    b.submit(entry(qty=100), as_of=D1)
    fills = b.process_bar("AAA", bar(D2, 100, 101, 99, 100))
    assert fills[0].qty == 50


def test_slippage_applied_against_trader():
    b = SimBroker(cash=100_000, slippage_bps=10)
    b.submit(entry(), as_of=D1)
    f = b.process_bar("AAA", bar(D2, 100, 101, 99, 100))[0]
    assert f.price == pytest.approx(100.1)


def test_equity_marks_to_market(broker):
    broker.submit(entry(), as_of=D1)
    broker.process_bar("AAA", bar(D2, 100, 101, 99, 100))
    assert broker.equity({"AAA": 110}) == pytest.approx(100_000 + 1_000)


def test_bracket_stop_protects_on_entry_day(broker):
    broker.submit(entry(), as_of=D1)
    fills = broker.process_bar("AAA", bar(D2, 100, 101, 93, 94))
    assert [(f.kind, f.price) for f in fills] == [("entry", 100), ("stop", 95.0)]
    assert "AAA" not in broker.positions


def test_replaced_stop_does_not_fill_same_day(broker):
    broker.submit(entry(), as_of=D1)
    broker.process_bar("AAA", bar(D2, 100, 110, 99, 109))
    broker.submit(stop_update(105), as_of=D2)
    # A bar on D2 itself (already processed) must not re-trigger; D3 is the first eligible bar.
    assert broker.process_bar("AAA", bar(D3, 108, 109, 106, 107)) == []


def test_slippage_on_touched_stop_is_not_a_gap():
    b = SimBroker(cash=100_000, slippage_bps=10)
    b.submit(entry(), as_of=D1)
    b.process_bar("AAA", bar(D2, 100, 101, 99, 100))
    b.process_bar("AAA", bar(D3, 97, 98, 94, 96))
    trade = b.closed_trades[-1]
    assert trade.exit_price < 95.0  # slippage
    assert not trade.gapped_through_stop
