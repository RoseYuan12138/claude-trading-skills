from agentic_trader.models import (
    AccountState,
    OrderIntent,
    OrderType,
    PositionSnapshot,
    Purpose,
    Side,
)
from agentic_trader.risk_gate import RiskRules, load_rules, validate


def _state(**kw):
    base = dict(equity=100_000.0, cash=100_000.0, day_start_equity=100_000.0)
    base.update(kw)
    return AccountState(**base)


def _held(qty=100, avg=50.0, last=55.0, stop=48.0):
    return {"AAPL": PositionSnapshot(qty=qty, avg_price=avg, last_price=last, stop_price=stop)}


def _entry(qty=100, price=50.0, stop=47.0, symbol="MSFT"):
    return OrderIntent(symbol, Side.BUY, qty, Purpose.ENTRY, price, stop_price=stop)


RULES = RiskRules(
    max_order_notional=20_000,
    max_position_pct=20,
    max_open_positions=3,
    risk_per_trade_pct=1.0,
    daily_loss_limit_pct=3.0,
    max_entries_per_day=2,
)


# ---------- entries ----------


def test_valid_entry_is_allowed():
    assert validate(_entry(), _state(), RULES).allowed


def test_entry_without_stop_is_blocked():
    d = validate(_entry(stop=None), _state(), RULES)
    assert not d.allowed
    assert any("stop" in r for r in d.reasons)


def test_entry_with_stop_above_price_is_blocked():
    assert not validate(_entry(stop=51.0), _state(), RULES).allowed


def test_entry_over_notional_cap_is_blocked():
    # 500 * 50 = 25k > 20k cap
    assert not validate(_entry(qty=500, stop=49.5), _state(), RULES).allowed


def test_entry_risk_over_budget_is_blocked():
    # risk = 300 * (50 - 45) = 1500 > 1% of 100k
    assert not validate(_entry(qty=300, stop=45.0), _state(), RULES).allowed


def test_entry_position_pct_counts_existing_holding():
    state = _state(positions=_held(qty=300, last=55.0))  # 16.5k already
    intent = _entry(qty=100, price=55.0, stop=54.0, symbol="AAPL")  # +5.5k -> 22%
    assert not validate(intent, state, RULES).allowed


def test_entry_blocked_when_max_positions_reached():
    positions = {
        s: PositionSnapshot(qty=1, avg_price=10, last_price=10, stop_price=9) for s in "ABC"
    }
    assert not validate(_entry(), _state(positions=positions), RULES).allowed


def test_entry_blocked_after_daily_loss_limit():
    state = _state(equity=96_500.0, day_start_equity=100_000.0)
    d = validate(_entry(), state, RULES)
    assert not d.allowed
    assert any("daily loss" in r for r in d.reasons)


def test_entry_blocked_when_halted():
    assert not validate(_entry(), _state(halted=True), RULES).allowed


def test_entry_blocked_when_entries_per_day_exhausted():
    assert not validate(_entry(), _state(entries_today=2), RULES).allowed


def test_entry_blocked_by_cash():
    assert not validate(_entry(), _state(cash=1_000.0), RULES).allowed


def test_symbol_whitelist_and_blocklist():
    rules = RiskRules(allowed_symbols=("AAPL",), blocked_symbols=("GME",))
    assert not validate(_entry(symbol="MSFT"), _state(), rules).allowed
    assert not validate(_entry(symbol="GME"), _state(), RiskRules(blocked_symbols=("GME",))).allowed


def test_entry_without_stop_allowed_when_rule_disabled():
    rules = RiskRules(require_stop_on_entry=False)
    assert validate(_entry(stop=None), _state(), rules).allowed


# ---------- exits: risk-reducing, never blocked by entry limits ----------


def test_exit_allowed_even_when_halted_and_over_loss_limit():
    state = _state(equity=90_000.0, halted=True, positions=_held())
    intent = OrderIntent("AAPL", Side.SELL, 100, Purpose.EXIT, 55.0)
    assert validate(intent, state, RULES).allowed


def test_exit_larger_than_position_is_blocked():
    intent = OrderIntent("AAPL", Side.SELL, 150, Purpose.EXIT, 55.0)
    assert not validate(intent, _state(positions=_held()), RULES).allowed


def test_sell_of_unheld_symbol_is_blocked():
    intent = OrderIntent("TSLA", Side.SELL, 1, Purpose.EXIT, 200.0)
    assert not validate(intent, _state(positions=_held()), RULES).allowed


# ---------- stop updates ----------


def _stop(new_stop, qty=100):
    return OrderIntent(
        "AAPL", Side.SELL, qty, Purpose.STOP_UPDATE, 55.0, OrderType.STOP, stop_price=new_stop
    )


def test_tightening_stop_is_allowed():
    assert validate(_stop(50.0), _state(positions=_held()), RULES).allowed


def test_loosening_stop_is_blocked():
    d = validate(_stop(45.0), _state(positions=_held()), RULES)
    assert not d.allowed
    assert any("loosen" in r for r in d.reasons)


def test_loosening_allowed_when_rule_disabled():
    rules = RiskRules(stop_only_tighten=False)
    assert validate(_stop(45.0), _state(positions=_held()), rules).allowed


def test_stop_at_or_above_price_is_blocked():
    assert not validate(_stop(55.0), _state(positions=_held()), RULES).allowed


def test_first_stop_on_unprotected_position_is_allowed():
    assert validate(_stop(40.0), _state(positions=_held(stop=None)), RULES).allowed


def test_stop_qty_cannot_exceed_position():
    assert not validate(_stop(50.0, qty=200), _state(positions=_held()), RULES).allowed


def test_buy_side_stop_update_is_blocked():
    intent = OrderIntent("AAPL", Side.BUY, 100, Purpose.STOP_UPDATE, 55.0, OrderType.STOP, 50.0)
    assert not validate(intent, _state(positions=_held()), RULES).allowed


# ---------- config ----------


def test_load_rules_from_yaml(tmp_path):
    p = tmp_path / "rules.yaml"
    p.write_text("max_order_notional: 1234\nallowed_symbols: [AAPL, MSFT]\n")
    rules = load_rules(p)
    assert rules.max_order_notional == 1234
    assert rules.allowed_symbols == ("AAPL", "MSFT")
    assert rules.stop_only_tighten is True  # default preserved


def test_load_rules_rejects_unknown_keys(tmp_path):
    p = tmp_path / "rules.yaml"
    p.write_text("max_order_notionl: 1234\n")
    try:
        load_rules(p)
    except ValueError as e:
        assert "max_order_notionl" in str(e)
    else:
        raise AssertionError("expected ValueError for typo'd key")
