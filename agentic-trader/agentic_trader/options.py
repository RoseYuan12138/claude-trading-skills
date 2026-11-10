"""Options: order model, structure classification, risk gate and exit rules.

The agent may take aggressive *directional* risk with options, but only in structures
whose worst case is known when the order is placed (long calls/puts, verticals).
Naked short options are always rejected, whatever the config says.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from .models import Decision, OrderType, Side

MULTIPLIER = 100


class Right(str, Enum):
    CALL = "call"
    PUT = "put"


class OptionAction(str, Enum):
    OPEN = "open"
    CLOSE = "close"


@dataclass(frozen=True)
class OptionLeg:
    right: Right
    strike: float
    expiry: date
    side: Side
    qty: int  # contracts
    bid: float | None = None
    ask: float | None = None

    def key(self, underlying: str) -> tuple[str, str, float, date]:
        return (underlying.upper(), self.right.value, float(self.strike), self.expiry)


@dataclass(frozen=True)
class OptionOrder:
    underlying: str
    legs: tuple[OptionLeg, ...]
    action: OptionAction
    order_type: OrderType
    limit_price: float | None  # net per share: > 0 pays a debit, < 0 receives a credit
    as_of: date
    source: str = "agent"
    note: str = ""


@dataclass(frozen=True)
class Structure:
    name: str  # long_call / long_put / debit_vertical / credit_vertical / naked_short / unsupported
    max_loss: float  # dollars, for the whole order
    is_debit: bool = True
    width: float = 0.0


def classify(order: OptionOrder) -> Structure:
    legs = order.legs
    price = order.limit_price
    buys = [lg for lg in legs if lg.side is Side.BUY]
    sells = [lg for lg in legs if lg.side is Side.SELL]
    if sells and not buys:
        return Structure("naked_short", float("inf"), is_debit=False)

    if len(legs) == 1:
        lg = legs[0]
        px = price if price is not None else (lg.ask or 0.0)
        name = "long_call" if lg.right is Right.CALL else "long_put"
        return Structure(name, max(px, 0.0) * MULTIPLIER * lg.qty)

    if len(legs) == 2 and len(buys) == 1 and len(sells) == 1:
        long_leg, short_leg = buys[0], sells[0]
        if (
            long_leg.right is short_leg.right
            and long_leg.expiry == short_leg.expiry
            and long_leg.qty == short_leg.qty
            and long_leg.strike != short_leg.strike
        ):
            width = abs(long_leg.strike - short_leg.strike)
            qty = long_leg.qty
            if long_leg.right is Right.CALL:
                is_debit = long_leg.strike < short_leg.strike
            else:
                is_debit = long_leg.strike > short_leg.strike
            net = price or 0.0
            if is_debit:
                return Structure("debit_vertical", max(net, 0.0) * MULTIPLIER * qty, True, width)
            credit = max(-net, 0.0)
            return Structure(
                "credit_vertical", max(width - credit, 0.0) * MULTIPLIER * qty, False, width
            )
    return Structure("unsupported", float("inf"))


@dataclass(frozen=True)
class OptionRules:
    allowed_structures: tuple[str, ...] = (
        "long_call",
        "long_put",
        "debit_vertical",
        "credit_vertical",
    )
    max_loss_per_trade_pct: float = 2.0  # worst-case loss of one order, % of equity
    max_total_risk_pct: float = 10.0  # sum of worst-case losses of open option positions
    max_open_positions: int = 6
    max_entries_per_day: int = 3
    daily_loss_limit_pct: float = 5.0
    min_dte: int = 7
    max_dte: int = 90
    max_spread_pct: float = 10.0  # single-leg (ask - bid) / mid, when quotes are known
    max_package_spread_pct: float = 25.0  # multi-leg: summed leg widths / |net mid|
    max_contracts: int = 20
    require_limit: bool = True


@dataclass
class OptionBookState:
    equity: float
    cash: float
    day_start_equity: float
    open_risk: float = 0.0
    open_positions: int = 0
    entries_today: int = 0
    halted: bool = False
    legs: dict[tuple[str, str, float, date], int] = field(default_factory=dict)  # +long/-short


def validate_option(order: OptionOrder, state: OptionBookState, rules: OptionRules) -> Decision:
    if not order.legs or any(lg.qty <= 0 for lg in order.legs):
        return Decision.deny("order needs legs with positive contract counts")
    if order.action is OptionAction.CLOSE:
        return _validate_close(order, state)

    reasons: list[str] = []
    if state.halted:
        reasons.append("trading halted: no new positions")
    if state.day_start_equity > 0:
        day = (state.equity / state.day_start_equity - 1) * 100
        if day <= -rules.daily_loss_limit_pct:
            reasons.append(f"daily loss breaker: {day:.2f}% <= -{rules.daily_loss_limit_pct}%")
    if state.entries_today >= rules.max_entries_per_day:
        reasons.append(f"max entries per day reached ({rules.max_entries_per_day})")
    if state.open_positions >= rules.max_open_positions:
        reasons.append(f"max open option positions reached ({rules.max_open_positions})")

    s = classify(order)
    if s.name == "naked_short":
        return Decision.deny("naked short options have unlimited or undefined risk: never allowed")
    if s.name == "unsupported":
        return Decision.deny("unsupported structure: use a long option or a same-expiry vertical")
    if s.name not in rules.allowed_structures:
        reasons.append(f"structure {s.name} is not allowed")

    if rules.require_limit and (
        order.order_type is not OrderType.LIMIT or order.limit_price is None
    ):
        reasons.append("option entries must be limit orders")
    elif order.limit_price is not None:
        if s.is_debit and order.limit_price <= 0:
            reasons.append("debit structure needs a positive limit price")
        if not s.is_debit and not (-s.width < order.limit_price < 0):
            reasons.append("credit structure needs a negative limit smaller than the width")

    for lg in order.legs:
        dte = (lg.expiry - order.as_of).days
        if not rules.min_dte <= dte <= rules.max_dte:
            reasons.append(f"{dte} DTE outside [{rules.min_dte}, {rules.max_dte}]")
        if lg.qty > rules.max_contracts:
            reasons.append(f"{lg.qty} contracts > cap {rules.max_contracts}")

    spread = _net_spread_pct(order.legs)
    cap = rules.max_spread_pct if len(order.legs) == 1 else rules.max_package_spread_pct
    if spread is not None and spread > cap:
        reasons.append(f"bid-ask spread {spread:.1f}% > {cap}%")

    if state.equity > 0:
        loss_pct = s.max_loss / state.equity * 100
        if loss_pct > rules.max_loss_per_trade_pct:
            reasons.append(
                f"max loss ${s.max_loss:,.0f} = {loss_pct:.2f}% > {rules.max_loss_per_trade_pct}%"
            )
        total_pct = (state.open_risk + s.max_loss) / state.equity * 100
        if total_pct > rules.max_total_risk_pct:
            reasons.append(f"total open risk {total_pct:.2f}% > {rules.max_total_risk_pct}%")
    if s.max_loss > state.cash:
        reasons.append(f"max loss ${s.max_loss:,.0f} not covered by cash ${state.cash:,.0f}")

    return Decision.deny(*reasons) if reasons else Decision.allow()


def _net_spread_pct(legs: tuple[OptionLeg, ...]) -> float | None:
    """Bid-ask width of the whole order as % of its net mid (None if quotes are missing).

    Multi-leg orders trade as one package, so the package spread is what costs money; a
    cheap far leg with a wide relative spread is fine if the combination is tight.
    """
    if any(lg.bid is None or lg.ask is None for lg in legs):
        return None
    net_mid = sum(((lg.bid + lg.ask) / 2) * (1 if lg.side is Side.BUY else -1) for lg in legs)
    width = sum(lg.ask - lg.bid for lg in legs)
    if abs(net_mid) <= 0:
        return float("inf")
    return width / abs(net_mid) * 100


def _validate_close(order: OptionOrder, state: OptionBookState) -> Decision:
    for lg in order.legs:
        held = state.legs.get(lg.key(order.underlying), 0)
        closes_long = lg.side is Side.SELL and 0 < lg.qty <= held
        closes_short = lg.side is Side.BUY and 0 < lg.qty <= -held
        if not (closes_long or closes_short):
            return Decision.deny(
                f"close leg {lg.right.value} {lg.strike} {lg.expiry} x{lg.qty} does not match "
                f"the held position ({held}); it would open new risk"
            )
    return Decision.allow()


# ------------------------------------------------------------------ exits


@dataclass
class OptionPosition:
    """A debit option position, tracked per share of the net premium."""

    underlying: str
    right: Right  # direction: CALL = bullish, PUT = bearish
    expiry: date
    entry_price: float
    peak_price: float
    entry_underlying: float
    contracts: int
    max_loss: float
    legs: tuple[OptionLeg, ...] = ()
    entry_date: date | None = None


@dataclass(frozen=True)
class OptionExitRules:
    stop_loss_pct: float | None = 50.0  # close when value falls this far below entry
    take_profit_pct: float | None = None  # close when value rises this far above entry
    trail_after_pct: float | None = 50.0  # arm a trailing stop after this gain...
    trail_pct: float = 35.0  # ...trailing this far below the peak, never below breakeven
    time_stop_dte: int | None = 5  # close before the last days of time decay / assignment
    underlying_stop_atr: float | None = None  # thesis stop on the stock itself


def exit_signal(
    pos: OptionPosition,
    value: float,
    underlying: float,
    atr: float | None,
    as_of: date,
    rules: OptionExitRules,
) -> str | None:
    """Return the exit reason for a debit position, or None to keep holding."""
    if pos.entry_price <= 0:
        raise ValueError("exit_signal handles debit positions only")
    entry = pos.entry_price
    if rules.time_stop_dte is not None and (pos.expiry - as_of).days <= rules.time_stop_dte:
        return "time_stop"
    if rules.take_profit_pct is not None and value >= entry * (1 + rules.take_profit_pct / 100):
        return "take_profit"
    if rules.stop_loss_pct is not None and value <= entry * (1 - rules.stop_loss_pct / 100):
        return "stop_loss"
    if rules.trail_after_pct is not None and pos.peak_price >= entry * (
        1 + rules.trail_after_pct / 100
    ):
        level = max(entry, pos.peak_price * (1 - rules.trail_pct / 100))
        if value <= level:
            return "trailing_stop"
    if rules.underlying_stop_atr is not None and atr:
        band = rules.underlying_stop_atr * atr
        if pos.right is Right.CALL and underlying <= pos.entry_underlying - band:
            return "underlying_stop"
        if pos.right is Right.PUT and underlying >= pos.entry_underlying + band:
            return "underlying_stop"
    return None
