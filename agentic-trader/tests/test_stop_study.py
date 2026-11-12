from datetime import date, timedelta

import pytest
from agentic_trader.models import Bar
from agentic_trader.sim.rotation import synthetic_leveraged
from agentic_trader.sim.stop_study import StopRule, run_stop_strategy

D0 = date(2020, 1, 1)


def bars(rows):
    """rows: (open, high, low, close)."""
    return [
        Bar(D0 + timedelta(days=i), o, h, low, c, 1_000) for i, (o, h, low, c) in enumerate(rows)
    ]


def flat(n, px=100.0, rng=1.0):
    return [(px, px + rng, px - rng, px)] * n


NO_COST = dict(cost_bps=0.0, stop_slip_bps=0.0)


def test_buy_and_hold_tracks_the_asset_from_the_first_open():
    b = bars([(100, 101, 99, 100), (100, 111, 99, 110), (110, 121, 109, 120)])
    r = run_stop_strategy(b, StopRule("hold", **NO_COST))
    assert r.curve[-1][1] == pytest.approx(10_000 * 120 / 100)
    assert r.stops == 0 and r.days_in == 3


def test_intraday_stop_fills_at_the_stop_price_when_the_low_touches_it():
    # ATR on the warm-up bars is 2.0 -> 3x ATR stop = 100 - 6 = 94
    b = bars(flat(20) + [(99, 100, 90, 98)] + flat(3, 98))
    r = run_stop_strategy(b, StopRule("atr3", stop="atr", atr_mult=3, **NO_COST), start=b[20].date)
    assert r.stops == 1 and r.gap_fills == 0
    assert r.exits[0].price == pytest.approx(r.exits[0].stop_level)
    assert r.exits[0].stop_level < 100


def test_gap_below_the_stop_fills_at_the_open():
    b = bars(flat(20) + flat(1) + [(80, 82, 78, 81)] + flat(2, 81))
    r = run_stop_strategy(b, StopRule("atr3", stop="atr", atr_mult=3, **NO_COST), start=b[20].date)
    assert r.stops == 1 and r.gap_fills == 1
    assert r.exits[0].price == pytest.approx(80)


def test_close_trigger_ignores_intraday_wicks():
    wick = bars(flat(20) + flat(1) + [(100, 101, 85, 100)] + flat(3))
    intraday = run_stop_strategy(
        wick, StopRule("i", stop="atr", atr_mult=3, **NO_COST), start=wick[20].date
    )
    close = run_stop_strategy(
        wick, StopRule("c", stop="atr", atr_mult=3, trigger="close", **NO_COST), start=wick[20].date
    )
    assert intraday.stops == 1 and close.stops == 0


def test_close_trigger_sells_at_the_next_open():
    b = bars(flat(20) + flat(1) + [(99, 99, 90, 91), (92, 93, 89, 90)] + flat(2, 90))
    r = run_stop_strategy(
        b, StopRule("c", stop="atr", atr_mult=3, trigger="close", **NO_COST), start=b[20].date
    )
    assert r.stops == 1 and r.exits[0].date == b[22].date and r.exits[0].price == 92


def test_stop_only_ratchets_up():
    up = [(100 + i, 101 + i, 99 + i, 100 + i) for i in range(10)]
    down = [(109 - i * 0.5, 110 - i * 0.5, 108 - i * 0.5, 109 - i * 0.5) for i in range(1, 4)]
    b = bars(flat(20) + up + down)
    r = run_stop_strategy(b, StopRule("a", stop="atr", atr_mult=3, **NO_COST), start=b[20].date)
    levels = [lvl for _, lvl in r.stop_levels]
    assert all(b2 >= a2 for a2, b2 in zip(levels, levels[1:]))


def test_breakout_reentry_after_a_stop():
    after = [(90, 91, 89, 90)] * 21 + [(90, 96, 90, 95), (95, 96, 94, 95)]
    b = bars(flat(20) + [(99, 100, 85, 90)] + after)
    r = run_stop_strategy(
        b, StopRule("a", stop="atr", atr_mult=3, reentry_lookback=20, **NO_COST), start=b[20].date
    )
    assert r.stops == 1 and len(r.entries) == 2
    assert r.entries[1].date == b[-1].date and r.entries[1].price == 95  # next open after breakout
    assert r.round_trips[0] == pytest.approx(95 / r.exits[0].price - 1)


def test_trend_filter_exits_next_open_and_reenters_when_trend_returns():
    rows = flat(5, 100) + [(100, 100, 80, 80), (80, 80, 79, 79)] + flat(3, 120)
    b = bars(rows)
    r = run_stop_strategy(b, StopRule("sma", trend_sma=5, **NO_COST), regime=b, start=b[5].date)
    assert r.stops == 0 and r.trend_exits == 1
    assert r.exits[0].date == b[6].date and r.exits[0].price == 80
    assert r.entries[-1].date == b[8].date  # trend back on at day 7's close


def test_cash_earns_the_tbill_rate_while_out():
    b = bars(flat(20) + [(99, 100, 50, 60)] + [(60, 61, 59, 60)] * 252)
    rates = {x.date: 5.0 for x in b}
    r = run_stop_strategy(
        b,
        StopRule("a", stop="atr", atr_mult=3, reentry="never", **NO_COST),
        start=b[20].date,
        rates_pct=rates,
    )
    after_exit = r.curve[0][1]
    assert r.curve[-1][1] == pytest.approx(after_exit * (1 + 0.05 / 252) ** 252, rel=1e-3)


def test_costs_reduce_the_result():
    b = bars(flat(20) + [(99, 100, 85, 90)] + [(90, 91, 89, 90)] * 21 + [(90, 96, 90, 95)] * 3)
    free = run_stop_strategy(b, StopRule("a", stop="atr", **NO_COST), start=b[20].date)
    paid = run_stop_strategy(
        b, StopRule("a", stop="atr", cost_bps=10, stop_slip_bps=20), start=b[20].date
    )
    assert paid.curve[-1][1] < free.curve[-1][1]


def test_pct_trailing_stop():
    b = bars(flat(20) + [(100, 110, 100, 110), (110, 110, 98, 100)] + flat(2, 100))
    r = run_stop_strategy(b, StopRule("p", stop="pct", trail_pct=10, **NO_COST), start=b[20].date)
    assert r.stops == 1 and r.exits[0].price == pytest.approx(99)  # 110 x 0.9


def test_synthetic_leveraged_intraday_maps_high_and_low():
    idx = bars([(100, 101, 99, 100), (100, 102, 95, 101)])
    lev = synthetic_leveraged(idx, 3, expense_pct=0.0, intraday=True)
    assert lev[1].low == pytest.approx(100 * (1 + 3 * -0.05))
    assert lev[1].high == pytest.approx(100 * (1 + 3 * 0.02))
    assert lev[1].close == pytest.approx(103)
    assert synthetic_leveraged(idx, 3, expense_pct=0.0)[1].low == pytest.approx(103)
