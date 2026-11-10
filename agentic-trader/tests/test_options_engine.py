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
