"""Deterministic risk gate.

Every order intent -- whether produced by code or by an LLM agent -- passes through
``validate`` before reaching a broker. The same function backs the Claude Code
PreToolUse hook (see ``hook.py``) so an agent talking to the Robinhood MCP server
directly cannot bypass it.

Design principles:
* Risk-reducing actions (exits, tightening stops) are never blocked by entry limits,
  the daily loss breaker or the halt flag.
* Risk-increasing actions (entries, loosening stops) must pass every check.
* Fail closed: anything malformed is denied.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path

import yaml

from .models import AccountState, Decision, OrderIntent, OrderType, Purpose, Side


@dataclass(frozen=True)
class RiskRules:
    max_order_notional: float = 10_000.0
    max_position_pct: float = 25.0  # of equity, per symbol, after the order
    max_open_positions: int = 8
    risk_per_trade_pct: float = 1.0  # qty * (price - stop) as % of equity
    daily_loss_limit_pct: float = 3.0  # no new entries once down this much on the day
    max_entries_per_day: int = 5
    require_stop_on_entry: bool = True
    stop_only_tighten: bool = True
    allowed_symbols: tuple[str, ...] = ()  # empty = any symbol
    blocked_symbols: tuple[str, ...] = ()


def load_rules(path: str | Path) -> RiskRules:
    data = yaml.safe_load(Path(path).read_text()) or {}
    known = {f.name for f in fields(RiskRules)}
    unknown = sorted(set(data) - known)
    if unknown:
        raise ValueError(f"unknown risk rule keys: {', '.join(unknown)}")
    for key in ("allowed_symbols", "blocked_symbols"):
        if key in data:
            data[key] = tuple(str(s).upper() for s in data[key] or ())
    return RiskRules(**data)


def validate(intent: OrderIntent, state: AccountState, rules: RiskRules) -> Decision:
    if intent.qty <= 0 or intent.ref_price <= 0:
        return Decision.deny("qty and ref_price must be positive")
    symbol = intent.symbol.upper()
    if intent.purpose is Purpose.ENTRY:
        return _validate_entry(intent, symbol, state, rules)
    if intent.purpose is Purpose.EXIT:
        return _validate_exit(intent, symbol, state)
    if intent.purpose is Purpose.STOP_UPDATE:
        return _validate_stop_update(intent, symbol, state, rules)
    return Decision.deny(f"unknown purpose {intent.purpose!r}")


def _validate_entry(
    intent: OrderIntent, symbol: str, state: AccountState, rules: RiskRules
) -> Decision:
    if intent.side is not Side.BUY:
        return Decision.deny("short selling is not supported")

    reasons: list[str] = []
    if state.halted:
        reasons.append("trading halted: no new entries")
    if symbol in rules.blocked_symbols:
        reasons.append(f"{symbol} is on the blocked list")
    if rules.allowed_symbols and symbol not in rules.allowed_symbols:
        reasons.append(f"{symbol} is not on the allowed list")

    if state.day_start_equity > 0:
        day_pnl_pct = (state.equity / state.day_start_equity - 1) * 100
        if day_pnl_pct <= -rules.daily_loss_limit_pct:
            reasons.append(
                f"daily loss breaker: {day_pnl_pct:.2f}% <= -{rules.daily_loss_limit_pct}%"
            )
    if state.entries_today >= rules.max_entries_per_day:
        reasons.append(f"max entries per day reached ({rules.max_entries_per_day})")

    held = state.positions.get(symbol)
    if held is None and len(state.positions) >= rules.max_open_positions:
        reasons.append(f"max open positions reached ({rules.max_open_positions})")

    price = intent.limit_price if intent.order_type is OrderType.LIMIT else intent.ref_price
    price = price or intent.ref_price
    notional = intent.qty * price
    if notional > rules.max_order_notional:
        reasons.append(f"order notional {notional:,.0f} > cap {rules.max_order_notional:,.0f}")
    if notional > state.cash:
        reasons.append(f"order notional {notional:,.0f} > cash {state.cash:,.0f}")

    if state.equity > 0:
        existing = held.qty * held.last_price if held else 0.0
        pos_pct = (existing + notional) / state.equity * 100
        if pos_pct > rules.max_position_pct:
            reasons.append(f"position would be {pos_pct:.1f}% > {rules.max_position_pct}%")

    stop = intent.stop_price
    if stop is None:
        if rules.require_stop_on_entry:
            reasons.append("entry must carry a protective stop")
    elif stop >= price:
        reasons.append(f"stop {stop} must be below entry price {price}")
    elif state.equity > 0:
        risk_pct = intent.qty * (price - stop) / state.equity * 100
        if risk_pct > rules.risk_per_trade_pct:
            reasons.append(f"risk to stop {risk_pct:.2f}% > {rules.risk_per_trade_pct}%")

    return Decision.deny(*reasons) if reasons else Decision.allow()


def _validate_exit(intent: OrderIntent, symbol: str, state: AccountState) -> Decision:
    if intent.side is not Side.SELL:
        return Decision.deny("exit must be a sell")
    held = state.positions.get(symbol)
    if held is None:
        return Decision.deny(f"no position in {symbol} to exit")
    if intent.qty > held.qty + 1e-9:
        return Decision.deny(f"exit qty {intent.qty} > position {held.qty} (would go short)")
    return Decision.allow()


def _validate_stop_update(
    intent: OrderIntent, symbol: str, state: AccountState, rules: RiskRules
) -> Decision:
    if intent.side is not Side.SELL:
        return Decision.deny("protective stop must be a sell")
    if intent.stop_price is None:
        return Decision.deny("stop update requires stop_price")
    held = state.positions.get(symbol)
    if held is None:
        return Decision.deny(f"no position in {symbol} to protect")
    if intent.qty > held.qty + 1e-9:
        return Decision.deny(f"stop qty {intent.qty} > position {held.qty}")
    if intent.stop_price >= intent.ref_price:
        return Decision.deny(
            f"stop {intent.stop_price} must be below last price {intent.ref_price}; use an exit"
        )
    if (
        rules.stop_only_tighten
        and held.stop_price is not None
        and intent.stop_price < held.stop_price - 1e-9
    ):
        return Decision.deny(f"cannot loosen stop from {held.stop_price} to {intent.stop_price}")
    return Decision.allow()
