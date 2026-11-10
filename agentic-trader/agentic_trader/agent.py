"""Layer 2: the event-driven decision maker.

Live, this is Claude Code (``claude -p``) acting through the Robinhood Trading MCP,
guarded by the risk-gate hook. In simulation it is replaced by
``RuleBasedAgentProxy`` -- a deterministic stand-in encoding what we would ask the
LLM to do -- so backtests are reproducible and cost nothing. ``ChaosAgent`` wraps
any agent and injects bad orders to prove the risk gate catches them.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date
from typing import Protocol

from .events import EventCalendar
from .models import AccountState, OrderIntent, OrderType, PositionSnapshot, Purpose, Side
from .monitor import Trigger


@dataclass
class AgentContext:
    as_of: date
    triggers: list[Trigger]
    state: AccountState
    atrs: dict[str, float | None]
    prices: dict[str, float]
    calendar: EventCalendar


@dataclass
class AgentDecision:
    intents: list[OrderIntent] = field(default_factory=list)
    halt_days: int = 0
    rationale: list[str] = field(default_factory=list)


class Agent(Protocol):
    name: str

    def decide(self, ctx: AgentContext) -> AgentDecision: ...


def _stop_intent(sym: str, pos: PositionSnapshot, stop: float, source: str, note: str):
    return OrderIntent(
        sym,
        Side.SELL,
        pos.qty,
        Purpose.STOP_UPDATE,
        pos.last_price,
        OrderType.STOP,
        stop_price=stop,
        source=source,
        note=note,
    )


def _exit_intent(sym: str, pos: PositionSnapshot, source: str, note: str):
    return OrderIntent(
        sym, Side.SELL, pos.qty, Purpose.EXIT, pos.last_price, source=source, note=note
    )


class RuleBasedAgentProxy:
    """What we would instruct the LLM to do, written as rules.

    * Earnings ahead on a held name: exit if the position is under water,
      otherwise tighten the stop to ``earnings_atr_mult`` x ATR.
    * High-importance macro event ahead: tighten every stop to ``macro_atr_mult`` x ATR.
    * Large gap down on a losing position: exit.
    * Position without a stop: place one at ``default_atr_mult`` x ATR.
    * Portfolio drawdown breach: halt new entries for ``drawdown_halt_days``.
    """

    name = "rule_proxy"

    def __init__(
        self,
        earnings_atr_mult: float = 1.0,
        macro_atr_mult: float = 1.5,
        default_atr_mult: float = 2.0,
        exit_losers_before_earnings: bool = True,
        drawdown_halt_days: int = 5,
    ):
        self.earnings_atr_mult = earnings_atr_mult
        self.macro_atr_mult = macro_atr_mult
        self.default_atr_mult = default_atr_mult
        self.exit_losers_before_earnings = exit_losers_before_earnings
        self.drawdown_halt_days = drawdown_halt_days

    def decide(self, ctx: AgentContext) -> AgentDecision:
        positions = ctx.state.positions
        exits: dict[str, str] = {}
        stops: dict[str, tuple[float, str]] = {}
        decision = AgentDecision()

        def want_stop(sym: str, mult: float, why: str) -> None:
            atr = ctx.atrs.get(sym)
            pos = positions.get(sym)
            if not atr or pos is None:
                return
            proposed = round(pos.last_price - mult * atr, 2)
            if pos.stop_price is not None and proposed <= pos.stop_price:
                return
            if sym not in stops or proposed > stops[sym][0]:
                stops[sym] = (proposed, why)

        for t in ctx.triggers:
            if t.kind == "event_ahead" and t.symbol in positions:
                pos = positions[t.symbol]
                if self.exit_losers_before_earnings and pos.last_price < pos.avg_price:
                    exits[t.symbol] = f"losing into {t.detail}"
                else:
                    want_stop(t.symbol, self.earnings_atr_mult, f"tighten before {t.detail}")
            elif t.kind == "event_ahead" and t.symbol is None:
                for sym in positions:
                    want_stop(sym, self.macro_atr_mult, f"tighten before {t.detail}")
            elif t.kind == "gap" and t.symbol in positions and t.value < 0:
                pos = positions[t.symbol]
                if pos.last_price < pos.avg_price:
                    exits[t.symbol] = t.detail
            elif t.kind == "unprotected" and t.symbol in positions:
                want_stop(t.symbol, self.default_atr_mult, "add missing stop")
            elif t.kind == "drawdown":
                decision.halt_days = max(decision.halt_days, self.drawdown_halt_days)
                decision.rationale.append(f"halt entries: {t.detail}")

        for sym, why in exits.items():
            decision.intents.append(_exit_intent(sym, positions[sym], "agent", why))
            decision.rationale.append(f"exit {sym}: {why}")
        for sym, (stop, why) in stops.items():
            if sym in exits:
                continue
            decision.intents.append(_stop_intent(sym, positions[sym], stop, "agent", why))
            decision.rationale.append(f"stop {sym} -> {stop}: {why}")
        return decision


class ChaosAgent:
    """Wraps an agent and, with probability ``rate`` per wake-up, adds a harmful order.

    Models an LLM that misreads context or is prompt-injected by a news article.
    """

    def __init__(self, inner: Agent, rate: float = 0.3, seed: int = 0):
        self.inner = inner
        self.rate = rate
        self.rng = random.Random(seed)
        self.name = f"{inner.name}+chaos"
        self.injected = 0

    def decide(self, ctx: AgentContext) -> AgentDecision:
        decision = self.inner.decide(ctx)
        if self.rng.random() >= self.rate:
            return decision
        positions = ctx.state.positions
        protected = [s for s, p in positions.items() if p.stop_price is not None]
        if protected and self.rng.random() < 0.5:
            sym = self.rng.choice(sorted(protected))
            pos = positions[sym]
            loose = round(pos.stop_price * 0.8, 2)
            decision.intents.append(_stop_intent(sym, pos, loose, "chaos", "loosen stop 20%"))
        else:
            sym = self.rng.choice(sorted(ctx.prices))
            price = ctx.prices[sym]
            qty = int(ctx.state.equity * 0.5 / price)
            if qty > 0:
                decision.intents.append(
                    OrderIntent(
                        sym,
                        Side.BUY,
                        qty,
                        Purpose.ENTRY,
                        price,
                        source="chaos",
                        note="all-in buy, no stop",
                    )
                )
        self.injected += 1
        return decision
