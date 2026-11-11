import importlib.util
from datetime import date, timedelta
from pathlib import Path

from agentic_trader.models import Bar

_spec = importlib.util.spec_from_file_location(
    "run_agentic_10k", Path(__file__).resolve().parents[1] / "scripts" / "run_agentic_10k.py"
)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def _curve(values):
    d0 = date(2020, 1, 1)
    return [(d0 + timedelta(days=i), v) for i, v in enumerate(values)]


def test_goal_freezes_equity():
    curve, outcome, when = mod.goal_or_ruin(_curve([10, 50, 120, 40, 200]), goal=100, floor=3)
    assert outcome == "goal" and when == date(2020, 1, 3)
    assert [e for _, e in curve] == [10, 50, 120, 120, 120]


def test_ruin_before_goal():
    curve, outcome, _ = mod.goal_or_ruin(_curve([10, 2, 150]), goal=100, floor=3)
    assert outcome == "ruin" and [e for _, e in curve] == [10, 2, 2]


def test_open_when_neither():
    curve, outcome, when = mod.goal_or_ruin(_curve([10, 20]), goal=100, floor=3)
    assert outcome == "open" and when is None and len(curve) == 2


def _bars(closes, start=date(2020, 1, 1)):
    return [Bar(start + timedelta(days=i), c, c, c, c, 0) for i, c in enumerate(closes)]


def test_splice_synthetic_meets_real_series():
    base = _bars([100, 101, 102, 103])
    real = _bars([50, 51], start=date(2020, 1, 3))
    out = mod.splice_synthetic(real, base, 3.0, {})
    assert [b.date for b in out] == [date(2020, 1, 1) + timedelta(days=i) for i in range(4)]
    assert out[2].close == 50 and out[1].close < 50  # rising base -> earlier synthetic is lower
    assert abs(out[1].close / out[2].close - 1 / (1 + 3 * (102 / 101 - 1))) < 1e-4  # minus fees


def test_ladder_steps_toward_the_money_when_itm_is_unaffordable():
    from agentic_trader.options import OptionExitRules, OptionRules
    from agentic_trader.sim.options_engine import OptionSimConfig

    n = 260
    spy = _bars([100 + i * 0.1 for i in range(n)])
    qqq = _bars([600 + i * 0.5 for i in range(n)])
    cfg = OptionSimConfig(
        initial_cash=10_000,
        untradable=("SPY",),
        hedge_symbols=("QQQ",),
        risk_per_trade_pct=80,
        signal_mode="index_trend",
        regime_symbol="SPY",
        regime_sma=200,
        target_dte=270,
        iv_floor=0.25,
        half_spread_pct=0.5,
    )
    rules = OptionRules(
        max_loss_per_trade_pct=80.01, max_total_risk_pct=80.01, max_dte=400, max_contracts=100
    )
    exits = OptionExitRules(stop_loss_pct=None, trail_after_pct=None, time_stop_dte=60)
    # one ~15% ITM call on a ~$700 underlying costs > $8k, so the ladder must go nearer ATM
    sim = mod.LadderSimulator({"SPY": spy, "QQQ": qqq}, rules, exits, cfg)
    res = sim.run()
    pos = sim.positions["QQQ"]
    spot = pos.entry_underlying
    assert pos.contracts == 1
    assert pos.legs[0].strike > spot * 0.86
    assert pos.max_loss <= 10_000 * 0.8 + 1
    assert not res.trades  # still holding the first call
