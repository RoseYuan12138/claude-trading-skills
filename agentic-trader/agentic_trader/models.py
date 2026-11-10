"""Core data types shared by the risk gate, stop logic, monitor and simulator."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"  # stop-market


class Purpose(str, Enum):
    ENTRY = "entry"  # opens or adds to a long position
    EXIT = "exit"  # reduces / closes a position at market or limit
    STOP_UPDATE = "stop_update"  # places or moves the protective stop


@dataclass(frozen=True)
class Bar:
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class OrderIntent:
    """What an agent (LLM or code) wants to do, before it reaches the broker.

    For ENTRY intents ``stop_price`` is the protective stop that will be attached.
    For STOP_UPDATE intents ``stop_price`` is the new stop level.
    ``ref_price`` is the latest price, used for notional and risk checks.
    """

    symbol: str
    side: Side
    qty: float
    purpose: Purpose
    ref_price: float
    order_type: OrderType = OrderType.MARKET
    stop_price: float | None = None
    limit_price: float | None = None
    source: str = "code"  # "code", "agent", "chaos" ... for audit trails
    note: str = ""


@dataclass
class PositionSnapshot:
    qty: float
    avg_price: float
    last_price: float
    stop_price: float | None = None


@dataclass
class AccountState:
    """Everything the risk gate needs to know about the account at decision time."""

    equity: float
    cash: float
    day_start_equity: float
    positions: dict[str, PositionSnapshot] = field(default_factory=dict)
    entries_today: int = 0
    halted: bool = False  # set by the agent layer or a human kill switch


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reasons: tuple[str, ...] = ()

    @staticmethod
    def allow() -> Decision:
        return Decision(True, ())

    @staticmethod
    def deny(*reasons: str) -> Decision:
        return Decision(False, tuple(reasons))
