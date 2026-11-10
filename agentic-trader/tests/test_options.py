from datetime import date, timedelta

import pytest
from agentic_trader.models import OrderType, Side
from agentic_trader.options import (
    OptionAction,
    OptionBookState,
    OptionExitRules,
    OptionLeg,
    OptionOrder,
    OptionPosition,
    OptionRules,
    Right,
    classify,
    exit_signal,
    validate_option,
)
from agentic_trader.pricing import bs_price

TODAY = date(2026, 11, 10)
EXP = TODAY + timedelta(days=35)


# ---------------------------------------------------------------- pricing


def test_black_scholes_reference_values():
    assert bs_price(100, 100, 1.0, 0.05, 0.2, Right.CALL) == pytest.approx(10.4506, abs=1e-3)
    assert bs_price(100, 100, 1.0, 0.05, 0.2, Right.PUT) == pytest.approx(5.5735, abs=1e-3)


def test_black_scholes_at_expiry_is_intrinsic():
    assert bs_price(110, 100, 0.0, 0.05, 0.3, Right.CALL) == pytest.approx(10)
    assert bs_price(90, 100, 0.0, 0.05, 0.3, Right.CALL) == 0
    assert bs_price(90, 100, 0.0, 0.05, 0.3, Right.PUT) == pytest.approx(10)


# --------------------------------------------------------------- classify


def leg(right, strike, side, qty=1, exp=EXP, bid=None, ask=None):
    return OptionLeg(right, strike, exp, side, qty, bid, ask)


def order(*legs, limit=2.0, action=OptionAction.OPEN, otype=OrderType.LIMIT):
    return OptionOrder("NVDA", tuple(legs), action, otype, limit, TODAY)


def test_classify_long_call_and_put():
    s = classify(order(leg(Right.CALL, 170, Side.BUY, 2), limit=5.0))
    assert s.name == "long_call" and s.max_loss == pytest.approx(5.0 * 100 * 2)
    assert classify(order(leg(Right.PUT, 160, Side.BUY))).name == "long_put"


def test_classify_debit_and_credit_verticals():
    debit = classify(
        order(leg(Right.CALL, 170, Side.BUY), leg(Right.CALL, 180, Side.SELL), limit=3.0)
    )
    assert debit.name == "debit_vertical" and debit.max_loss == pytest.approx(300)
    credit = classify(
        order(leg(Right.PUT, 150, Side.BUY), leg(Right.PUT, 160, Side.SELL), limit=-2.5)
    )
    assert credit.name == "credit_vertical" and credit.max_loss == pytest.approx((10 - 2.5) * 100)


def test_naked_short_and_odd_structures_are_unsupported():
    assert classify(order(leg(Right.CALL, 200, Side.SELL), limit=-3.0)).name == "naked_short"
    ratio = order(leg(Right.CALL, 170, Side.BUY, 1), leg(Right.CALL, 180, Side.SELL, 2))
    assert classify(ratio).name == "unsupported"
    calendar = order(
        leg(Right.CALL, 170, Side.BUY, exp=EXP + timedelta(days=30)),
        leg(Right.CALL, 170, Side.SELL),
    )
    assert classify(calendar).name == "unsupported"


# ------------------------------------------------------------------- gate

RULES = OptionRules(max_loss_per_trade_pct=2.0, max_total_risk_pct=10.0, min_dte=7)


def state(**kw):
    base = dict(equity=50_000.0, cash=50_000.0, day_start_equity=50_000.0)
    base.update(kw)
    return OptionBookState(**base)


def test_long_call_within_budget_allowed():
    assert validate_option(
        order(leg(Right.CALL, 170, Side.BUY, 2), limit=5.0), state(), RULES
    ).allowed


def test_trade_over_max_loss_budget_blocked():
    d = validate_option(order(leg(Right.CALL, 170, Side.BUY, 3), limit=5.0), state(), RULES)
    assert not d.allowed and any("max loss" in r for r in d.reasons)  # 1500 > 2% of 50k


def test_total_open_risk_cap():
    d = validate_option(
        order(leg(Right.CALL, 170, Side.BUY), limit=5.0), state(open_risk=4_800), RULES
    )
    assert not d.allowed and any("total" in r for r in d.reasons)


def test_naked_short_always_blocked_even_if_listed():
    rules = OptionRules(allowed_structures=("naked_short",))
    d = validate_option(order(leg(Right.PUT, 150, Side.SELL), limit=-3.0), state(), rules)
    assert not d.allowed and any("unlimited" in r or "naked" in r for r in d.reasons)


def test_dte_bounds():
    near = order(leg(Right.CALL, 170, Side.BUY, exp=TODAY + timedelta(days=2)), limit=1.0)
    far = order(leg(Right.CALL, 170, Side.BUY, exp=TODAY + timedelta(days=400)), limit=1.0)
    assert not validate_option(near, state(), RULES).allowed
    assert not validate_option(far, state(), RULES).allowed


def test_market_orders_and_wide_spreads_blocked():
    assert not validate_option(
        order(leg(Right.CALL, 170, Side.BUY), limit=None, otype=OrderType.MARKET), state(), RULES
    ).allowed
    wide = order(leg(Right.CALL, 170, Side.BUY, bid=1.0, ask=1.6), limit=1.3)
    d = validate_option(wide, state(), RULES)
    assert not d.allowed and any("spread" in r for r in d.reasons)


def test_halt_daily_loss_and_entries_per_day():
    o = order(leg(Right.CALL, 170, Side.BUY), limit=2.0)
    assert not validate_option(o, state(halted=True), RULES).allowed
    assert not validate_option(o, state(equity=47_000), RULES).allowed  # -6% on the day
    assert not validate_option(o, state(entries_today=3), RULES).allowed


def test_closing_is_allowed_even_when_halted_but_cannot_open_new_legs():
    held = {("NVDA", "call", 170.0, EXP): 2}
    close = order(leg(Right.CALL, 170, Side.SELL, 2), limit=1.0, action=OptionAction.CLOSE)
    assert validate_option(close, state(halted=True, legs=held), RULES).allowed
    too_many = order(leg(Right.CALL, 170, Side.SELL, 3), limit=1.0, action=OptionAction.CLOSE)
    assert not validate_option(too_many, state(legs=held), RULES).allowed
    not_held = order(leg(Right.PUT, 150, Side.SELL), limit=1.0, action=OptionAction.CLOSE)
    assert not validate_option(not_held, state(legs=held), RULES).allowed


# ------------------------------------------------------------------- exits


def pos(entry=4.0, peak=4.0, entry_s=100.0, right=Right.CALL, exp=EXP):
    return OptionPosition(
        "NVDA", right, exp, entry, peak, entry_s, contracts=1, max_loss=entry * 100
    )


EXIT = OptionExitRules(
    stop_loss_pct=50,
    take_profit_pct=None,
    trail_after_pct=50,
    trail_pct=35,
    time_stop_dte=5,
    underlying_stop_atr=1.5,
)


def test_premium_stop_loss():
    assert exit_signal(pos(), 1.9, 100, 2, TODAY, EXIT) == "stop_loss"
    assert exit_signal(pos(), 2.1, 100, 2, TODAY, EXIT) is None


def test_trailing_after_gain_locks_profit():
    p = pos(entry=4.0, peak=8.0)  # +100% peak -> trail at 8 * 0.65 = 5.2
    assert exit_signal(p, 5.0, 110, 2, TODAY, EXIT) == "trailing_stop"
    assert exit_signal(p, 5.5, 110, 2, TODAY, EXIT) is None


def test_trailing_never_below_breakeven_once_armed():
    p = pos(entry=4.0, peak=6.0)  # +50%: trail level 3.9 < entry -> breakeven 4.0
    assert exit_signal(p, 3.95, 105, 2, TODAY, EXIT) == "trailing_stop"


def test_take_profit_and_time_stop():
    rules = OptionExitRules(take_profit_pct=100, time_stop_dte=5)
    assert exit_signal(pos(), 8.1, 120, 2, TODAY, rules) == "take_profit"
    assert exit_signal(pos(exp=TODAY + timedelta(days=4)), 4.0, 100, 2, TODAY, rules) == "time_stop"


def test_underlying_stop_for_calls_and_puts():
    assert exit_signal(pos(entry_s=100), 3.0, 96.9, 2, TODAY, EXIT) == "underlying_stop"
    put = pos(entry_s=100, right=Right.PUT)
    assert exit_signal(put, 3.0, 103.1, 2, TODAY, EXIT) == "underlying_stop"
    assert exit_signal(put, 3.0, 102.0, 2, TODAY, EXIT) is None
