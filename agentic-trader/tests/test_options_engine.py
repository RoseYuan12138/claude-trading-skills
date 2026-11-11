from datetime import date

import pytest
from agentic_trader.models import Bar
from agentic_trader.options import OptionExitRules, OptionRules, Right
from agentic_trader.sim.data import business_days
from agentic_trader.sim.options_engine import (
    OptionSimConfig,
    OptionSimulator,
    expiry_after,
    round_strike,
    strike_step,
)

RULES = OptionRules(max_loss_per_trade_pct=2.5, max_total_risk_pct=10)
EXITS = OptionExitRules(stop_loss_pct=50, trail_after_pct=50, trail_pct=35, time_stop_dte=5)


def test_strike_grid_and_expiry():
    assert strike_step(20) == 0.5 and strike_step(170) == 2.5 and strike_step(515) == 5
    assert round_strike(168.89, 2.5) == 170.0
    assert expiry_after(date(2026, 11, 10), 35) == date(2026, 12, 18)  # Friday
    assert expiry_after(date(2026, 11, 13), 0) == date(2026, 11, 13)


def _path(prices, start=date(2025, 1, 1), wiggle=0.5):
    """Each bar opens at the previous close (no overnight gaps) and closes at ``p``."""
    days = business_days(start, len(prices))
    out, prev = [], prices[0]
    for d, p in zip(days, prices):
        out.append(Bar(d, prev, max(prev, p) + wiggle, min(prev, p) - wiggle, p, 1e6))
        prev = p
    return out


def _flat_then(after, n_flat=60, base=100.0):
    # small zig-zag so realized vol is non-zero, then the scripted move
    flat = [base + (0.3 if i % 2 else -0.3) for i in range(n_flat)]
    return _path(flat + after)


def run(bars, exits=EXITS, rules=RULES, **cfg):
    sim = OptionSimulator({"X": bars}, rules, exits, OptionSimConfig(**cfg))
    return sim.run()


def test_breakout_buys_call_next_open_and_trailing_locks_gain():
    up = [101 + i * 1.5 for i in range(15)] + [123 - i * 2 for i in range(10)]
    res = run(_flat_then(up))
    t = res.trades[0]
    assert t.right is Right.CALL
    assert t.entry_date == _flat_then(up)[61].date  # signal at close of bar 60, fill at 61 open
    assert t.reason in {"trailing_stop", "stop_loss"}
    assert t.pnl > 0


def test_crash_triggers_premium_stop_and_caps_loss_near_premium():
    down = [101, 102, 90, 80, 75, 74, 73, 72, 71, 70]
    res = run(_flat_then(down))
    t = res.trades[0]
    assert t.reason == "stop_loss"
    assert -1.0 <= t.r_multiple <= -0.5
    assert res.equity_curve[-1][1] >= 50_000 * (1 - 0.025) - 1  # never more than the premium


def _rights(bars, **cfg):
    sim = OptionSimulator({"X": bars}, RULES, EXITS, OptionSimConfig(**cfg))
    res = sim.run()
    return [t.right for t in res.trades] + [p.right for p in sim.positions.values()]


def test_breakdown_buys_put_when_allowed_only():
    down = [99 - i for i in range(10)]
    assert _rights(_flat_then(down))[0] is Right.PUT
    assert _rights(_flat_then(down), allow_puts=False) == []


def test_gate_blocks_oversized_premium():
    up = [101 + i for i in range(10)]
    res = run(_flat_then(up), risk_per_trade_pct=6.0, rules=OptionRules(max_loss_per_trade_pct=2.0))
    assert res.trades == [] and sum(res.blocked.values()) > 0


def test_entry_limit_not_filled_after_gap_up():
    bars = _flat_then([101.0])
    gap = Bar(business_days(bars[-1].date, 2)[1], 130, 131, 129, 130, 1e6)
    res = run(bars + [gap])
    assert res.unfilled_entries == 1 and not res.trades


def test_debit_vertical_profit_is_capped_by_width():
    up = [101 + i * 2 for i in range(30)]
    res = run(
        _flat_then(up),
        structure="debit_vertical",
        exits=OptionExitRules(stop_loss_pct=None, trail_after_pct=None, time_stop_dte=5),
    )
    t = res.trades[0]
    width_per_share = t.exit_price  # value can't exceed width
    assert width_per_share <= 2 * 2 * 1.2 + 1  # roughly <= strike width (2x ATR on a grid of 1)


def test_expiry_settles_at_intrinsic_without_time_stop():
    up = [101 + i * 1.0 for i in range(45)]
    res = run(
        _flat_then(up),
        exits=OptionExitRules(stop_loss_pct=None, trail_after_pct=None, time_stop_dte=None),
        target_dte=21,
    )
    assert res.trades[0].reason == "expiry"


def test_metrics_shape():
    res = run(_flat_then([101 + i for i in range(30)]))
    m = res.metrics()
    assert {"total_return_pct", "max_drawdown_pct", "win_rate_pct", "lost_90pct_plus"} <= set(m)
    assert m["trades"] == pytest.approx(len(res.trades))


def test_open_fills_do_not_use_that_days_close():
    """Same history and same open; only the fill day's range differs -> same entry price."""
    bars = _flat_then([101.0])
    nxt = business_days(bars[-1].date, 2)[1]
    calm = Bar(nxt, 101, 101.4, 100.6, 101, 1e6)
    wild = Bar(nxt, 101, 140, 60, 70, 1e6)
    no_exit = OptionExitRules(stop_loss_pct=None, trail_after_pct=None, time_stop_dte=None)
    prices = []
    for last in (calm, wild):
        sim = OptionSimulator({"X": bars + [last]}, RULES, no_exit, OptionSimConfig())
        sim.run()
        prices.append(sim.positions["X"].entry_price)
    assert prices[0] == pytest.approx(prices[1])


# ------------------------------------------------------- regime + direction


def _bench(rising: bool, n: int):
    days = business_days(date(2025, 1, 1), n)
    return [
        Bar(
            d,
            400 + (i if rising else -i) * 0.5,
            401 + (i if rising else -i) * 0.5,
            399 + (i if rising else -i) * 0.5,
            400 + (i if rising else -i) * 0.5,
            5e7,
        )
        for i, d in enumerate(days)
    ]


def _dirs(x_bars, bench_rising, **cfg):
    data = {"X": x_bars, "SPY": _bench(bench_rising, len(x_bars))}
    sim = OptionSimulator(
        data,
        RULES,
        EXITS,
        OptionSimConfig(regime_symbol="SPY", regime_sma=50, untradable=("SPY",), **cfg),
    )
    res = sim.run()
    return [t.right for t in res.trades] + [p.right for p in sim.positions.values()]


def test_regime_gate_calls_only_in_uptrend_puts_only_in_downtrend():
    up = _flat_then([101 + i for i in range(10)])
    down = _flat_then([99 - i for i in range(10)])
    assert _dirs(up, bench_rising=True)[0] is Right.CALL
    assert _dirs(up, bench_rising=False) == []  # bullish signal, weak market: skip
    assert _dirs(down, bench_rising=False)[0] is Right.PUT
    assert _dirs(down, bench_rising=True) == []  # bearish signal, strong market: skip


def test_puts_only_sleeve():
    up = _flat_then([101 + i for i in range(10)])
    down = _flat_then([99 - i for i in range(10)])
    assert _dirs(up, bench_rising=True, allow_calls=False) == []
    assert _dirs(down, bench_rising=False, allow_calls=False)[0] is Right.PUT


def test_benchmark_is_not_traded():
    data = {"SPY": _flat_then([101 + i for i in range(10)])}
    sim = OptionSimulator(data, RULES, EXITS, OptionSimConfig(untradable=("SPY",)))
    assert sim.run().trades == [] and not sim.positions


# ------------------------------------------------------------ bear setups

from agentic_trader.events import Event, EventCalendar  # noqa: E402

BEAR = dict(signal_mode="bear_setups", allow_calls=False, structure="debit_vertical")


def _sim(bars, calendar=None, **cfg):
    sim = OptionSimulator(
        {"X": bars}, RULES, EXITS, OptionSimConfig(**{**BEAR, **cfg}), calendar=calendar
    )
    sim.run()
    return sim


def _entries(sim):
    return [t.entry_date for t in sim.result.trades] + [
        p.entry_date for p in sim.positions.values()
    ]


def _gap_down_after_earnings(gap=0.9, vol=5e6, weak_close=True):
    bars = _flat_then([])
    d = business_days(bars[-1].date, 3)[1:]
    o = bars[-1].close * gap
    c = o * (0.98 if weak_close else 1.03)
    bars.append(Bar(d[0], o, max(o, c) + 0.2, min(o, c) - 0.2, c, vol))
    bars.append(Bar(d[1], c, c + 0.3, c - 0.3, c, 1e6))
    return bars, d[0]


def test_post_earnings_gap_down_buys_put_spread_next_open():
    bars, day = _gap_down_after_earnings()
    sim = _sim(bars, EventCalendar([Event(day, "earnings", "X", 3)]))
    assert _entries(sim) == [bars[-1].date]
    pos = list(sim.positions.values())[0]
    assert pos.right is Right.PUT and len(pos.legs) == 2


def test_gap_down_without_earnings_or_with_strong_close_is_ignored():
    bars, day = _gap_down_after_earnings()
    assert _entries(_sim(bars)) == []  # no earnings event
    bars, day = _gap_down_after_earnings(weak_close=False)
    assert _entries(_sim(bars, EventCalendar([Event(day, "earnings", "X", 3)]))) == []


def _downtrend_then_failed_rally():
    """Returns (bars, signal_day): the failed-rally bar is followed by one quiet bar."""
    prices = [100 - i * 0.6 for i in range(70)]  # falling: below 50d SMA, SMA falling
    bars = _path(prices)
    last = bars[-1]
    sma20 = sum(b.close for b in bars[-20:]) / 20
    d1, d2 = business_days(last.date, 3)[1:]
    # rallies up to the 20d SMA intraday, closes red below it
    bars.append(Bar(d1, last.close + 1.0, sma20 + 0.1, last.close - 0.2, last.close + 0.2, 1e6))
    c = bars[-1].close
    bars.append(Bar(d2, c, c + 0.3, c - 0.3, c, 1e6))
    return bars, d1


def test_failed_rally_in_downtrend_buys_put():
    bars, _ = _downtrend_then_failed_rally()
    assert _entries(_sim(bars)) == [bars[-1].date]


def test_extension_and_iv_filters_block_puts():
    bars, day = _gap_down_after_earnings(gap=0.7)
    cal = EventCalendar([Event(day, "earnings", "X", 3)])
    assert _entries(_sim(bars, cal, max_extension_pct=20)) == []  # already 30% below 50d SMA
    assert _entries(_sim(bars, cal, max_iv=0.05)) == []


def test_option_entries_skip_earnings_blackout():
    bars, signal_day = _downtrend_then_failed_rally()
    soon = business_days(signal_day, 3)[2]
    cal = EventCalendar([Event(soon, "earnings", "X", 3)])
    assert len(_entries(_sim(bars, cal))) == 1
    assert _entries(_sim(bars, cal, earnings_blackout_days=7)) == []


def test_bear_setups_can_be_enabled_individually():
    bars, _ = _downtrend_then_failed_rally()
    assert _entries(_sim(bars, bear_setups=("earnings_gap",))) == []
    assert len(_entries(_sim(bars, bear_setups=("failed_rally",)))) == 1


# ------------------------------------------------------------ index hedge


def _hedge_sim(bench_path, **cfg):
    q = _path(bench_path)
    data = {"QQQ": q, "SPY": q}
    base = dict(
        signal_mode="index_hedge",
        hedge_symbols=("QQQ",),
        regime_symbol="SPY",
        regime_sma=20,
        untradable=("SPY",),
        exit_on_regime_bull=True,
        target_dte=45,
    )
    exits = OptionExitRules(stop_loss_pct=None, trail_after_pct=None, time_stop_dte=5)
    sim = OptionSimulator(data, RULES, exits, OptionSimConfig(**{**base, **cfg}))
    return sim, sim.run()


def test_index_hedge_buys_put_when_regime_turns_bear_and_exits_when_bull_returns():
    up = [100 + i * 0.5 for i in range(40)]
    down = [up[-1] - i * 1.0 for i in range(1, 8)]
    back_up = [down[-1] + i * 2.0 for i in range(1, 12)]
    sim, res = _hedge_sim(up + down + back_up)
    assert res.trades, "expected one hedge round trip"
    t = res.trades[0]
    assert t.underlying == "QQQ" and t.right is Right.PUT
    assert t.reason == "regime_exit"


def test_index_hedge_ignores_breakouts_and_other_symbols():
    up = [100 + i * 0.5 for i in range(60)]
    sim, res = _hedge_sim(up)
    assert res.trades == [] and not sim.positions  # never bearish


# ------------------------------------------------------------ score tiers

from agentic_trader.market_score import ScoreTier  # noqa: E402

TIERS = (
    ScoreTier(70, calls=True, puts=False, risk_pct=2.0, total_pct=10),
    ScoreTier(50, calls=True, puts=False, risk_pct=1.0, total_pct=5),
    ScoreTier(30, calls=False, puts=False, risk_pct=0, total_pct=0),
    ScoreTier(0, calls=False, puts=True, risk_pct=1.0, total_pct=3),
)


def _score_sim(bars, score):
    scores = {b.date: score for b in bars}
    sim = OptionSimulator(
        {"X": bars}, RULES, EXITS, OptionSimConfig(score_tiers=TIERS), scores=scores
    )
    res = sim.run()
    return sim, res


def _rights_and_cost(sim, res):
    rights = [t.right for t in res.trades] + [p.right for p in sim.positions.values()]
    costs = [p.max_loss for p in sim.positions.values()] + [
        t.entry_price * 100 * t.contracts for t in res.trades
    ]
    return rights, costs


def test_score_tiers_choose_direction_and_size():
    up = _flat_then([101 + i for i in range(10)])
    down = _flat_then([99 - i for i in range(10)])
    r_hi, c_hi = _rights_and_cost(*_score_sim(up, 80))
    r_mid, c_mid = _rights_and_cost(*_score_sim(up, 60))
    assert r_hi[0] is Right.CALL and r_mid[0] is Right.CALL
    assert c_hi[0] > c_mid[0] * 1.5  # 2% vs 1% of equity
    assert _rights_and_cost(*_score_sim(up, 40))[0] == []  # cash tier
    assert _rights_and_cost(*_score_sim(down, 60))[0] == []  # puts not allowed at 60
    assert _rights_and_cost(*_score_sim(down, 20))[0][0] is Right.PUT


def test_score_tier_total_cap_limits_positions():
    bars = {s: _flat_then([101 + i for i in range(10)]) for s in ("A", "B", "C", "D")}
    scores = {b.date: 60 for b in bars["A"]}
    sim = OptionSimulator(bars, RULES, EXITS, OptionSimConfig(score_tiers=TIERS), scores=scores)
    res = sim.run()
    opened = len(res.trades) + len(sim.positions)
    assert opened <= 5  # 1% each, 5% cap


def test_no_score_for_the_day_means_no_entry():
    up = _flat_then([101 + i for i in range(10)])
    sim = OptionSimulator({"X": up}, RULES, EXITS, OptionSimConfig(score_tiers=TIERS), scores={})
    res = sim.run()
    assert not res.trades and not sim.positions


# ------------------------------------------------------- score dip + IV override


def _dip_sim(path, score_by_index, **cfg):
    bars = _path(path)
    scores = {b.date: score_by_index(i) for i, b in enumerate(bars)}
    base = dict(signal_mode="score_dip", hedge_symbols=("QQQ",), dip_threshold=30.0)
    sim = OptionSimulator(
        {"QQQ": bars}, RULES, EXITS, OptionSimConfig(**{**base, **cfg}), scores=scores
    )
    return sim, sim.run(), bars


def test_score_dip_buys_call_only_when_score_is_low():
    path = [100 + (0.3 if i % 2 else -0.3) for i in range(80)]
    sim, res, bars = _dip_sim(path, lambda i: 20 if i == 60 else 60)
    entries = [t.entry_date for t in res.trades] + [p.entry_date for p in sim.positions.values()]
    assert entries == [bars[61].date]
    rights = [t.right for t in res.trades] + [p.right for p in sim.positions.values()]
    assert rights == [Right.CALL]
    sim, res, _ = _dip_sim(path, lambda i: 60)
    assert not res.trades and not sim.positions


def test_iv_override_prices_options_with_the_given_vol():
    path = [100 + (0.3 if i % 2 else -0.3) for i in range(80)]
    cheap_sim, _, bars = _dip_sim(path, lambda i: 20 if i == 60 else 60)
    iv = {"QQQ": {b.date: 60.0 for b in bars}}  # 60% implied vol, in index points
    pricey_sim = OptionSimulator(
        {"QQQ": bars},
        RULES,
        EXITS,
        OptionSimConfig(signal_mode="score_dip", hedge_symbols=("QQQ",), dip_threshold=30.0),
        scores={b.date: (20 if i == 60 else 60) for i, b in enumerate(bars)},
        iv_overrides=iv,
    )
    pricey_res = pricey_sim.run()

    def entry_price(sim, res):
        prices = [p.entry_price for p in sim.positions.values()]
        return (prices + [t.entry_price for t in res.trades])[0]

    cheap = entry_price(cheap_sim, cheap_sim.result)
    pricey = entry_price(pricey_sim, pricey_res)
    assert pricey > cheap * 3


# ------------------------------------------------------------ dip overlay


def test_dip_overlay_adds_qqq_calls_in_a_bear_regime_alongside_breakouts():
    n = 80
    days = business_days(date(2025, 1, 1), n)
    falling = [Bar(d, 400 - i, 401 - i, 399 - i, 400 - i, 5e7) for i, d in enumerate(days)]
    qqq = _path([100 + (0.3 if i % 2 else -0.3) for i in range(n)])
    stock = _path(
        [100 + (0.3 if i % 2 else -0.3) for i in range(60)] + [101 + i for i in range(20)]
    )
    data = {"QQQ": qqq, "X": stock, "SPY": falling}
    scores = {d: (20 if i == 65 else 60) for i, d in enumerate(days)}
    cfg = OptionSimConfig(
        regime_symbol="SPY",
        regime_sma=50,
        untradable=("SPY",),
        allow_puts=False,
        dip_overlay=True,
        hedge_symbols=("QQQ",),
        dip_threshold=30.0,
        dip_risk_pct=1.0,
    )
    sim = OptionSimulator(data, RULES, EXITS, cfg, scores=scores)
    res = sim.run()
    held = {t.underlying: t for t in res.trades}
    held.update({s: p for s, p in sim.positions.items()})
    assert "QQQ" in held  # dip call despite the bear regime
    assert "X" not in held  # breakout blocked by the bear regime
    qqq_pos = held["QQQ"]
    cost = (
        qqq_pos.max_loss
        if hasattr(qqq_pos, "max_loss")
        else qqq_pos.entry_price * 100 * qqq_pos.contracts
    )
    assert cost <= 50_000 * 0.01 + 1  # sized with dip_risk_pct


def test_dip_overlay_off_means_no_qqq_dip_trade():
    n = 80
    days = business_days(date(2025, 1, 1), n)
    falling = [Bar(d, 400 - i, 401 - i, 399 - i, 400 - i, 5e7) for i, d in enumerate(days)]
    qqq = _path([100 + (0.3 if i % 2 else -0.3) for i in range(n)])
    cfg = OptionSimConfig(regime_symbol="SPY", regime_sma=50, untradable=("SPY",), allow_puts=False)
    sim = OptionSimulator(
        {"QQQ": qqq, "SPY": falling}, RULES, EXITS, cfg, scores={d: 20 for d in days}
    )
    res = sim.run()
    assert not res.trades and not sim.positions


def test_trades_record_the_setup_that_opened_them():
    path = [100 + (0.3 if i % 2 else -0.3) for i in range(80)]
    sim, res, _ = _dip_sim(path, lambda i: 20 if i == 60 else 60)
    setups = [t.setup for t in res.trades] + [p.setup for p in sim.positions.values()]
    assert setups == ["score_dip"]


# ------------------------------------------------------------ ITM trend calls


def _trend_sim(spy_path, qqq_path, **cfg):
    q = _path(qqq_path)
    spy = _path(spy_path)
    base = dict(
        signal_mode="index_trend",
        hedge_symbols=("QQQ",),
        regime_symbol="SPY",
        regime_sma=20,
        untradable=("SPY",),
        strike_moneyness=0.85,
        target_dte=120,
        risk_per_trade_pct=20.0,
        exit_on_regime_bear=True,
    )
    exits = OptionExitRules(stop_loss_pct=None, trail_after_pct=None, time_stop_dte=30)
    rules = OptionRules(max_loss_per_trade_pct=25, max_total_risk_pct=50, max_dte=200)
    sim = OptionSimulator({"QQQ": q, "SPY": spy}, rules, exits, OptionSimConfig(**{**base, **cfg}))
    return sim, sim.run(), q


def test_index_trend_buys_itm_call_in_bull_regime():
    up = [100 + i * 0.5 for i in range(40)]
    sim, res, q = _trend_sim(up, up)
    pos = list(sim.positions.values()) + res.trades
    assert pos and pos[0].right is Right.CALL
    legs = list(sim.positions.values())[0].legs
    assert legs[0].strike < q[-1].close * 0.9  # ~15% in the money
    assert (legs[0].expiry - q[-1].date).days > 60


def test_index_trend_exits_when_regime_turns_bear():
    path = [100 + i * 0.5 for i in range(40)] + [120 - i * 1.5 for i in range(1, 20)]
    sim, res, _ = _trend_sim(path, path)
    assert res.trades and res.trades[0].reason == "regime_exit"
    assert not sim.positions  # no re-entry while bearish


def test_strike_moneyness_defaults_to_at_the_money():
    up = [100 + i * 0.5 for i in range(40)]
    sim, _, q = _trend_sim(up, up, strike_moneyness=1.0)
    pos = list(sim.positions.values())[0]
    assert abs(pos.legs[0].strike - pos.entry_underlying) <= 2.5


# ------------------------------------------------------------ put credit spreads

CREDIT_EXITS = OptionExitRules(
    stop_loss_pct=None,
    trail_after_pct=None,
    credit_take_profit_pct=50,
    credit_stop_multiple=2.0,
    time_stop_dte=7,
)
CREDIT_RULES = OptionRules(max_loss_per_trade_pct=10, max_total_risk_pct=20, max_dte=120)


def _credit_sim(qqq_path, spy_path=None, exits=CREDIT_EXITS, **cfg):
    q = _path(qqq_path)
    spy = _path(spy_path or qqq_path)
    base = dict(
        signal_mode="put_credit",
        hedge_symbols=("QQQ",),
        regime_symbol="SPY",
        regime_sma=20,
        untradable=("SPY",),
        risk_per_trade_pct=5.0,
        target_dte=35,
        credit_otm_pct=5.0,
        credit_width_pct=5.0,
        exit_on_regime_bear=True,
        iv_floor=0.25,
    )
    sim = OptionSimulator(
        {"QQQ": q, "SPY": spy}, CREDIT_RULES, exits, OptionSimConfig(**{**base, **cfg})
    )
    return sim, sim.run(), q


def test_put_credit_spread_opens_for_a_credit_with_bounded_risk():
    up = [100 + i * 0.3 for i in range(30)]
    sim, res, q = _credit_sim(up)
    pos = list(sim.positions.values())[0]
    assert pos.entry_price < 0  # credit received
    short, long_ = sorted(pos.legs, key=lambda lg: -lg.strike)
    assert short.side.value == "sell" and long_.side.value == "buy"
    assert short.strike < q[-1].close and long_.strike < short.strike
    width = short.strike - long_.strike
    assert pos.max_loss == pytest.approx((width + pos.entry_price) * 100 * pos.contracts)
    assert pos.max_loss <= 50_000 * 0.05 + 1


def test_put_credit_spread_takes_profit_as_the_market_rises():
    up = [100 + i * 0.3 for i in range(30)] + [109 + i * 1.0 for i in range(25)]
    sim, res, _ = _credit_sim(up)
    t = res.trades[0]
    assert t.reason == "take_profit" and t.pnl > 0 and t.setup == "put_credit"


def test_put_credit_spread_loss_never_exceeds_max_loss_in_a_crash():
    path = [100 + i * 0.3 for i in range(30)] + [60.0] * 10
    spy = [100 + i * 0.3 for i in range(40)]  # keep the regime bullish to isolate the stop
    sim, res, q = _credit_sim(path, spy)
    crash_day = q[30].date
    hit = [t for t in res.trades if t.exit_date >= crash_day]
    assert hit, "the spread open into the crash should have been closed"
    t = hit[0]
    assert t.pnl < 0
    assert -t.pnl <= t.max_loss + 1e-6
    assert t.r_multiple >= -1.0 - 1e-9


def test_put_credit_spread_closes_when_regime_turns_bear():
    path = [100 + i * 0.3 for i in range(30)] + [109 - i * 0.2 for i in range(1, 15)]
    spy = [100 + i * 0.3 for i in range(30)] + [109 - i * 1.5 for i in range(1, 15)]
    sim, res, _ = _credit_sim(path, spy)
    assert res.trades and res.trades[-1].reason == "regime_exit"
    assert not sim.positions  # no new spread while bearish


def test_equity_marks_credit_positions_as_liabilities():
    up = [100 + i * 0.3 for i in range(30)]
    sim, res, _ = _credit_sim(up)
    start = res.equity_curve[0][1]
    # right after entry equity is about unchanged (minus the bid-ask cost), not up by the credit
    assert abs(res.equity_curve[-1][1] - start) < start * 0.02


def test_closing_a_credit_spread_pays_at_least_the_mid():
    """Regression: buying back a losing credit spread must cost its value, not ~0."""
    path = [100 + i * 0.3 for i in range(30)] + [88.0] * 10
    spy = [100 + i * 0.3 for i in range(40)]
    sim, res, q = _credit_sim(path, spy)
    crash_day = q[30].date
    t = next(t for t in res.trades if t.exit_date > crash_day)
    assert t.exit_price < t.entry_price  # paid more to close than was received
    assert t.exit_price < -2.5  # deep in the money: costs most of the ~5-point width
    assert t.pnl < 0


def test_vertical_value_is_capped_at_its_width():
    path = [100 + i * 0.3 for i in range(30)] + [40.0] * 10  # far through both strikes
    spy = [100 + i * 0.3 for i in range(40)]
    sim, res, q = _credit_sim(path, spy)
    t = next(t for t in res.trades if t.exit_date > q[30].date)
    assert -t.pnl <= t.max_loss + 1e-6


# ------------------------------------------------------------ pricing inputs


from datetime import timedelta  # noqa: E402

from agentic_trader.models import Side  # noqa: E402
from agentic_trader.options import OptionLeg  # noqa: E402


def _pricing_sim(**cfg):
    bars = _path([100 + (0.3 if i % 2 else -0.3) for i in range(30)])
    sim = OptionSimulator({"QQQ": bars}, RULES, EXITS, OptionSimConfig(**cfg))
    sim.history["QQQ"] = bars
    return sim, bars[-1]


def test_put_skew_raises_otm_put_prices_only():
    flat, last = _pricing_sim()
    skewed, _ = _pricing_sim(put_skew_per_pct=1.0)
    otm = OptionLeg(Right.PUT, 90.0, last.date + timedelta(days=35), Side.BUY, 1)
    atm = OptionLeg(Right.PUT, 100.0, last.date + timedelta(days=35), Side.BUY, 1)
    iv = 0.2
    assert skewed._leg_price("QQQ", otm, 100.0, last.date, iv) > flat._leg_price(
        "QQQ", otm, 100.0, last.date, iv
    )
    assert skewed._leg_price("QQQ", atm, 100.0, last.date, iv) == pytest.approx(
        flat._leg_price("QQQ", atm, 100.0, last.date, iv)
    )


def test_rate_series_is_used_with_a_one_day_lag():
    bars = _path([100 + (0.3 if i % 2 else -0.3) for i in range(30)])
    rates = {b.date: (0.0 if i < 20 else 8.0) for i, b in enumerate(bars)}
    sim = OptionSimulator({"QQQ": bars}, RULES, EXITS, OptionSimConfig(rate=0.04), rates_pct=rates)
    sim.run()
    assert sim._rate_now == pytest.approx(0.08)  # latest known value after the run
    sim2 = OptionSimulator(
        {"QQQ": bars[:21]}, RULES, EXITS, OptionSimConfig(rate=0.04), rates_pct=rates
    )
    sim2.run()
    assert sim2._rate_now == pytest.approx(0.0)  # day 20's 8% is not used on day 20 itself


def test_dip_requires_bull_regime():
    n = 80
    days = business_days(date(2025, 1, 1), n)
    qqq = _path([100 + (0.3 if i % 2 else -0.3) for i in range(n)])
    falling = [Bar(d, 400 - i, 401 - i, 399 - i, 400 - i, 5e7) for i, d in enumerate(days)]
    rising = [Bar(d, 300 + i, 301 + i, 299 + i, 300 + i, 5e7) for i, d in enumerate(days)]
    scores = {d: (20 if i == 60 else 60) for i, d in enumerate(days)}
    base = dict(
        signal_mode="score_dip",
        hedge_symbols=("QQQ",),
        dip_threshold=30.0,
        dip_requires_bull=True,
        regime_symbol="SPY",
        regime_sma=50,
        untradable=("SPY",),
    )
    for spy, expect in ((falling, False), (rising, True)):
        sim = OptionSimulator(
            {"QQQ": qqq, "SPY": spy}, RULES, EXITS, OptionSimConfig(**base), scores=scores
        )
        res = sim.run()
        assert bool(res.trades or sim.positions) is expect


def test_skew_is_by_strike_so_itm_calls_share_otm_put_iv():
    """Put-call parity: a call and a put at the same strike carry the same implied vol."""
    flat, last = _pricing_sim()
    skewed, _ = _pricing_sim(put_skew_per_pct=1.0)
    exp = last.date + timedelta(days=120)
    itm_call = OptionLeg(Right.CALL, 85.0, exp, Side.BUY, 1)
    iv = 0.2
    assert (
        skewed._leg_price("QQQ", itm_call, 100.0, last.date, iv)
        > flat._leg_price("QQQ", itm_call, 100.0, last.date, iv) + 0.5
    )
    # parity holds under skew: C - P = S e^{-qT} - K e^{-rT}
    put = OptionLeg(Right.PUT, 85.0, exp, Side.BUY, 1)
    import math

    t = 120 / 365
    c = skewed._leg_price("QQQ", itm_call, 100.0, last.date, iv)
    p = skewed._leg_price("QQQ", put, 100.0, last.date, iv)
    assert c - p == pytest.approx(100.0 - 85.0 * math.exp(-0.04 * t), abs=1e-6)


# ------------------------------------------------------------ regime buffer + vol target


def test_regime_buffer_ignores_small_dips_below_the_sma():
    up = [100 + i * 0.5 for i in range(40)]
    wobble = [
        up[-1] - 3 + (2 if i % 2 else -2) * 0.3 for i in range(12)
    ]  # hovers ~1-2% below SMA20
    path = up + wobble
    plain, res_plain, _ = _trend_sim(path, path)
    buffered, res_buf, _ = _trend_sim(path, path, regime_buffer_pct=5.0)
    assert any(t.reason == "regime_exit" for t in res_plain.trades)
    assert not any(t.reason == "regime_exit" for t in res_buf.trades)


def test_regime_buffer_still_exits_on_a_real_break():
    path = [100 + i * 0.5 for i in range(40)] + [120 - i * 2.0 for i in range(1, 15)]
    sim, res, _ = _trend_sim(path, path, regime_buffer_pct=2.0)
    assert any(t.reason == "regime_exit" for t in res.trades)


def test_vol_target_sizes_down_when_implied_vol_is_high():
    up = [100 + i * 0.5 for i in range(40)]
    q = _path(up)
    spy = _path(up)
    sizes = []
    for iv in (15.0, 45.0):
        cfg = dict(
            signal_mode="index_trend",
            hedge_symbols=("QQQ",),
            regime_symbol="SPY",
            regime_sma=20,
            untradable=("SPY",),
            strike_moneyness=0.85,
            target_dte=120,
            risk_per_trade_pct=20.0,
            vol_target=0.20,
            vol_target_cap=1.5,
        )
        rules = OptionRules(max_loss_per_trade_pct=40, max_total_risk_pct=40, max_dte=200)
        exits = OptionExitRules(stop_loss_pct=None, trail_after_pct=None, time_stop_dte=30)
        sim = OptionSimulator(
            {"QQQ": q, "SPY": spy},
            rules,
            exits,
            OptionSimConfig(**cfg),
            iv_overrides={"QQQ": {b.date: iv for b in q}},
        )
        res = sim.run()
        first = (list(sim.positions.values()) + res.trades)[0]
        sizes.append(first.max_loss)
    assert sizes[0] > sizes[1] * 2  # 15% IV -> bigger than 45% IV


def test_iv_term_structure_pulls_long_dated_vol_toward_the_long_run_level():
    calm, last = _pricing_sim(iv_term_mean=0.24, iv_term_kappa=3.0)
    flat, _ = _pricing_sim()
    leaps = OptionLeg(Right.CALL, 100.0, last.date + timedelta(days=270), Side.BUY, 1)
    month = OptionLeg(Right.CALL, 100.0, last.date + timedelta(days=30), Side.BUY, 1)
    # calm market (30-day IV 15% < 24%): long-dated options cost more than at a flat 15%
    assert calm._leg_price("QQQ", leaps, 100.0, last.date, 0.15) > flat._leg_price(
        "QQQ", leaps, 100.0, last.date, 0.15
    )
    # stressed market (45%): long-dated options cost less than at a flat 45%
    assert calm._leg_price("QQQ", leaps, 100.0, last.date, 0.45) < flat._leg_price(
        "QQQ", leaps, 100.0, last.date, 0.45
    )
    # 30-day options keep the quoted 30-day vol
    assert calm._leg_price("QQQ", month, 100.0, last.date, 0.15) == pytest.approx(
        flat._leg_price("QQQ", month, 100.0, last.date, 0.15)
    )


def test_regime_also_requires_extra_symbols_above_their_sma():
    up = [100 + i * 0.5 for i in range(40)]
    down = [120 - i * 0.5 for i in range(40)]
    q_down = _path(down)
    spy_up = _path(up)
    base = dict(
        signal_mode="index_trend",
        hedge_symbols=("QQQ",),
        regime_symbol="SPY",
        regime_sma=20,
        untradable=("SPY",),
        strike_moneyness=0.85,
        target_dte=120,
        risk_per_trade_pct=20.0,
    )
    rules = OptionRules(max_loss_per_trade_pct=25, max_total_risk_pct=50, max_dte=200)
    exits = OptionExitRules(stop_loss_pct=None, trail_after_pct=None, time_stop_dte=30)
    only_spy = OptionSimulator(
        {"QQQ": q_down, "SPY": spy_up}, rules, exits, OptionSimConfig(**base)
    )
    res = only_spy.run()
    assert res.trades or only_spy.positions  # SPY alone says bull
    both = OptionSimulator(
        {"QQQ": q_down, "SPY": spy_up}, rules, exits, OptionSimConfig(**base, regime_also=("QQQ",))
    )
    res = both.run()
    assert not res.trades and not both.positions  # QQQ below its SMA blocks entries


def test_monthly_regime_check_only_updates_on_the_first_trading_day_of_a_month():
    days = business_days(date(2025, 1, 1), 120)
    # rises, then dips hard mid-February (below SMA20) and recovers before March
    prices = []
    for i, d in enumerate(days):
        p = 100 + i * 0.5
        if date(2025, 2, 10) <= d <= date(2025, 2, 21):
            p -= 15
        prices.append(p)
    bars = [Bar(d, p, p, p, p, 1e6) for d, p in zip(days, prices)]
    base = dict(
        signal_mode="index_trend",
        hedge_symbols=("QQQ",),
        regime_symbol="SPY",
        regime_sma=20,
        untradable=("SPY",),
        strike_moneyness=0.85,
        target_dte=120,
        risk_per_trade_pct=20.0,
        exit_on_regime_bear=True,
    )
    rules = OptionRules(max_loss_per_trade_pct=25, max_total_risk_pct=50, max_dte=200)
    exits = OptionExitRules(stop_loss_pct=None, trail_after_pct=None, time_stop_dte=30)
    daily = OptionSimulator({"QQQ": bars, "SPY": bars}, rules, exits, OptionSimConfig(**base))
    rd = daily.run()
    monthly = OptionSimulator(
        {"QQQ": bars, "SPY": bars}, rules, exits, OptionSimConfig(**base, regime_check="monthly")
    )
    rm = monthly.run()
    assert any(t.reason == "regime_exit" for t in rd.trades)
    assert not any(t.reason == "regime_exit" for t in rm.trades)  # the dip was inside a month
