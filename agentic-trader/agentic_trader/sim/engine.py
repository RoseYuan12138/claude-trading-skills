"""Daily event loop wiring broker, stops, monitor, agent and risk gate together.

Order of operations each trading day D (mirrors the live design):
1. Broker matches pending orders against D's bar (stops live at the broker).
2. Mark to market; update ATR and drawdown.
3. Layer 1 (code): ratchet trailing stops.
4. Layer 1 (code): monitor scans; if warranted, wake Layer 2 (agent) once.
5. Code entry signals (identical across scenarios so stop handling is isolated).
Every intent from steps 3-5 passes the risk gate unless the scenario disables it.
"""

from __future__ import annotations

import math
import statistics
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable

from ..agent import Agent, AgentContext
from ..events import EventCalendar
from ..models import AccountState, Bar, OrderIntent, OrderType, Purpose, Side
from ..monitor import Monitor, MonitorConfig
from ..risk_gate import RiskRules, validate
from ..stops import StopPolicy, WilderATR
from .broker import ClosedTrade, Fill, SimBroker


@dataclass
class SimConfig:
    initial_cash: float = 100_000.0
    risk_pct: float = 0.75  # equity risked per entry, measured to the initial stop
    fallback_risk_atr: float = 2.0  # sizing distance when the policy places no stop
    breakout_lookback: int = 20
    trend_sma: int = 50
    atr_period: int = 14
    slippage_bps: float = 5.0
    # Replay mode: bars before start_date only warm up indicators; initial_positions
    # (symbol -> shares) are bought at the start_date close, funded on top of initial_cash.
    start_date: date | None = None
    initial_positions: dict[str, float] = field(default_factory=dict)
    enable_entries: bool = True
    # Entry filters (all off by default)
    regime_symbol: str | None = None  # e.g. "SPY": no new entries while it closes below its SMA
    regime_sma: int = 200
    earnings_blackout_days: int = 0  # calendar days: skip entries with earnings this close
    volume_confirm_mult: float = 0.0  # breakout volume must be >= mult x 20-day average
    untradable: tuple[str, ...] = ()  # e.g. a benchmark kept only for the regime filter


@dataclass
class Action:
    date: date
    intent: OrderIntent


@dataclass
class AgentLogEntry:
    date: date
    triggers: list[str]
    rationale: list[str]


@dataclass
class Scenario:
    name: str
    make_policy: Callable[[], StopPolicy]
    make_agent: Callable[[int], Agent] | None = None  # receives the seed
    gate_enabled: bool = True
    rules: RiskRules | None = None  # overrides the base rules when set
    monitor_config: MonitorConfig | None = None


@dataclass
class BlockedIntent:
    date: date
    source: str
    purpose: str
    symbol: str
    reasons: tuple[str, ...]


@dataclass
class SimResult:
    scenario: str
    equity_curve: list[tuple[date, float]]
    trades: list[ClosedTrade]
    llm_wakeups: int = 0
    blocked: list[BlockedIntent] = field(default_factory=list)
    executed_by_source: Counter = field(default_factory=Counter)
    chaos_injected: int = 0
    fills: list[Fill] = field(default_factory=list)
    open_at_end: int = 0
    actions: list[Action] = field(default_factory=list)
    agent_log: list[AgentLogEntry] = field(default_factory=list)

    def metrics(self) -> dict[str, float]:
        eq = [e for _, e in self.equity_curve]
        start, end = eq[0], eq[-1]
        years = len(eq) / 252
        rets = [b / a - 1 for a, b in zip(eq, eq[1:]) if a > 0]
        sd = statistics.pstdev(rets) if len(rets) > 1 else 0.0
        peak, max_dd = eq[0], 0.0
        for e in eq:
            peak = max(peak, e)
            max_dd = max(max_dd, 1 - e / peak)
        rs = [t.r_multiple for t in self.trades]
        stop_exits = [t for t in self.trades if t.exit_kind == "stop"]
        gapped = [t for t in stop_exits if t.gapped_through_stop]
        gap_excess = [(t.exit_price - t.stop_level) / t.risk_per_share for t in gapped]
        return {
            "total_return_pct": (end / start - 1) * 100,
            "cagr_pct": ((end / start) ** (1 / years) - 1) * 100 if years > 0 and end > 0 else 0.0,
            "max_drawdown_pct": max_dd * 100,
            "sharpe": statistics.mean(rets) / sd * math.sqrt(252) if sd > 0 else 0.0,
            "trades": float(len(self.trades)),
            "win_rate_pct": (sum(r > 0 for r in rs) / len(rs) * 100) if rs else float("nan"),
            "avg_r": statistics.mean(rs) if rs else 0.0,
            "worst_r": min(rs) if rs else 0.0,
            "stop_exits": float(len(stop_exits)),
            "gap_through_stops": float(len(gapped)),
            "avg_gap_slippage_r": statistics.mean(gap_excess) if gap_excess else 0.0,
            "open_at_end": float(self.open_at_end),
            "llm_wakeups": float(self.llm_wakeups),
            "llm_wakeups_per_month": self.llm_wakeups / (len(eq) / 21) if eq else 0.0,
            "blocked_intents": float(len(self.blocked)),
            "chaos_injected": float(self.chaos_injected),
            "chaos_executed": float(self.executed_by_source.get("chaos", 0)),
        }


def run_simulation(
    data: dict[str, list[Bar]],
    calendar: EventCalendar,
    rules: RiskRules,
    stop_policy: StopPolicy,
    agent: Agent | None = None,
    *,
    scenario_name: str = "",
    gate_enabled: bool = True,
    monitor_config: MonitorConfig | None = None,
    config: SimConfig | None = None,
) -> SimResult:
    sim = _Simulator(
        data, calendar, rules, stop_policy, agent, gate_enabled, monitor_config, config
    )
    return sim.run(scenario_name or stop_policy.name)


class _Simulator:
    def __init__(
        self,
        data: dict[str, list[Bar]],
        calendar: EventCalendar,
        rules: RiskRules,
        stop_policy: StopPolicy,
        agent: Agent | None,
        gate_enabled: bool,
        monitor_config: MonitorConfig | None,
        config: SimConfig | None,
    ):
        self.cfg = config or SimConfig()
        if self.cfg.regime_symbol and self.cfg.regime_symbol not in data:
            raise ValueError(f"regime_symbol {self.cfg.regime_symbol} is not in the data")
        self.data = data
        self.calendar = calendar
        self.rules = rules
        self.policy = stop_policy
        self.agent = agent
        self.gate_enabled = gate_enabled
        self.broker = SimBroker(self.cfg.initial_cash, self.cfg.slippage_bps)
        self.monitor = Monitor(monitor_config)
        self.history: dict[str, list[Bar]] = {s: [] for s in data}
        self.atr_calc = {s: WilderATR(self.cfg.atr_period) for s in data}
        self.atrs: dict[str, float | None] = {}
        self.closes: dict[str, float] = {}
        self.halted_until: date | None = None
        # per-day state
        self.today = date.min
        self.equity = self.prev_equity = self.cfg.initial_cash
        self.entries_today = 0
        self.result = SimResult("", [], self.broker.closed_trades, fills=self.broker.fills)

    # ----------------------------------------------------------------- helpers

    def halted(self) -> bool:
        return self.halted_until is not None and self.today < self.halted_until

    def state(self) -> AccountState:
        return AccountState(
            equity=self.equity,
            cash=self.broker.cash - self.broker.pending_entry_notional(self.closes),
            day_start_equity=self.prev_equity,
            positions=self.broker.snapshots(self.closes),
            entries_today=self.entries_today,
            halted=self.halted(),
        )

    def route(self, intent: OrderIntent, risk_per_share: float | None = None) -> bool:
        d, res = self.today, self.result
        if self.gate_enabled:
            decision = validate(intent, self.state(), self.rules)
            if not decision.allowed:
                res.blocked.append(
                    BlockedIntent(
                        d, intent.source, intent.purpose.value, intent.symbol, decision.reasons
                    )
                )
                return False
        try:
            self.broker.submit(intent, d, risk_per_share)
        except ValueError as e:
            res.blocked.append(
                BlockedIntent(d, intent.source, intent.purpose.value, intent.symbol, (str(e),))
            )
            return False
        res.executed_by_source[intent.source] += 1
        res.actions.append(Action(d, intent))
        return True

    # -------------------------------------------------------------------- loop

    def run(self, name: str) -> SimResult:
        self.result.scenario = name
        by_date = {s: {b.date: b for b in bars} for s, bars in self.data.items()}
        dates = sorted({d for idx in by_date.values() for d in idx})
        start = self.cfg.start_date
        if start is not None and start not in dates:
            raise ValueError(f"start_date {start} has no bar in the data")
        started = start is None
        peak = self.cfg.initial_cash
        for d in dates:
            self.today = d
            self.entries_today = 0
            for s in self.data:
                bar = by_date[s].get(d)
                if bar is None:
                    continue
                self.broker.process_bar(s, bar)
                self.history[s].append(bar)
                self.atrs[s] = self.atr_calc[s].update(bar)
                self.closes[s] = bar.close

            if not started:
                if d < start:
                    continue  # warm-up: indicators only
                started = True
                self._seed_positions()
                self.prev_equity = peak = self.broker.equity(self.closes)

            self.equity = self.broker.equity(self.closes)
            peak = max(peak, self.equity)
            drawdown_pct = (1 - self.equity / peak) * 100

            self._trail_stops()
            if self.agent is not None:
                self._maybe_wake_agent(drawdown_pct)
            if self.cfg.enable_entries and not self.halted():
                self._enter_breakouts()

            self.result.equity_curve.append((d, self.equity))
            self.prev_equity = self.equity
        self.result.chaos_injected = getattr(self.agent, "injected", 0)
        self.result.open_at_end = len(self.broker.positions)
        return self.result

    def _seed_positions(self) -> None:
        for s, qty in self.cfg.initial_positions.items():
            if s not in self.closes:
                raise ValueError(f"no price for initial position {s}")
            close, atr = self.closes[s], self.atrs.get(s)
            stop = self.policy.initial_stop(close, atr) if atr else None
            risk = close - stop if stop is not None else self.cfg.fallback_risk_atr * (atr or 0)
            self.broker.cash += qty * close  # holdings are funded on top of initial_cash
            self.broker.seed_position(s, qty, close, self.today, risk or None)

    def _trail_stops(self) -> None:
        for s, pos in list(self.broker.positions.items()):
            atr = self.atrs.get(s)
            if not atr or s not in self.closes:
                continue
            desired = self.policy.trail(pos.stop_price, pos.highest_close, atr)
            if desired is None or desired >= self.closes[s]:
                continue
            if pos.stop_price is not None and desired <= pos.stop_price + 0.005:
                continue
            self.route(
                OrderIntent(
                    s,
                    Side.SELL,
                    pos.qty,
                    Purpose.STOP_UPDATE,
                    self.closes[s],
                    OrderType.STOP,
                    stop_price=desired,
                    note="trail",
                )
            )

    def _maybe_wake_agent(self, drawdown_pct: float) -> None:
        snap = self.state()
        triggers = self.monitor.scan(
            self.today, self.history, self.atrs, snap.positions, self.calendar, drawdown_pct
        )
        if not self.monitor.should_wake(self.today, triggers):
            return
        self.result.llm_wakeups += 1
        ctx = AgentContext(self.today, triggers, snap, self.atrs, dict(self.closes), self.calendar)
        decision = self.agent.decide(ctx)
        self.result.agent_log.append(
            AgentLogEntry(self.today, [t.detail for t in triggers], list(decision.rationale))
        )
        if decision.halt_days:
            until = self.today + timedelta(days=decision.halt_days)
            self.halted_until = max(self.halted_until or until, until)
        for intent in decision.intents:
            self.route(intent)

    def _regime_ok(self) -> bool:
        cfg = self.cfg
        if not cfg.regime_symbol:
            return True
        h = self.history[cfg.regime_symbol]
        if len(h) < cfg.regime_sma:
            return True  # not enough history yet: do not filter
        sma = sum(b.close for b in h[-cfg.regime_sma :]) / cfg.regime_sma
        return h[-1].close >= sma

    def _passes_filters(self, s: str, h: list[Bar]) -> bool:
        cfg = self.cfg
        if cfg.earnings_blackout_days > 0 and any(
            e.kind == "earnings"
            for e in self.calendar.upcoming(self.today, cfg.earnings_blackout_days, [s])
            if e.symbol == s
        ):
            return False
        if cfg.volume_confirm_mult > 0:
            window = h[-21:-1]
            avg = sum(b.volume for b in window) / len(window) if window else 0.0
            if avg <= 0 or h[-1].volume < cfg.volume_confirm_mult * avg:
                return False
        return True

    def _enter_breakouts(self) -> None:
        cfg = self.cfg
        if not self._regime_ok():
            return
        min_history = max(cfg.breakout_lookback, cfg.trend_sma, cfg.atr_period) + 1
        pending = self.broker.pending_entry_symbols()
        for s in sorted(self.data):
            h = self.history[s]
            if s in self.broker.positions or s in pending or len(h) < min_history:
                continue
            if s in cfg.untradable:
                continue
            atr = self.atrs.get(s)
            if h[-1].date != self.today or not atr:
                continue
            close = h[-1].close
            prior_high = max(b.high for b in h[-cfg.breakout_lookback - 1 : -1])
            sma = sum(b.close for b in h[-cfg.trend_sma :]) / cfg.trend_sma
            if close <= prior_high or close <= sma:
                continue
            if not self._passes_filters(s, h):
                continue
            stop = self.policy.initial_stop(close, atr)
            risk_ps = close - stop if stop is not None else cfg.fallback_risk_atr * atr
            if risk_ps <= 0:
                continue
            snap = self.state()
            qty = min(
                math.floor(snap.equity * cfg.risk_pct / 100 / risk_ps),
                math.floor(self.rules.max_order_notional / close),
                math.floor(snap.equity * self.rules.max_position_pct / 100 / close),
                math.floor(max(snap.cash, 0) / close),
            )
            if qty <= 0:
                continue
            intent = OrderIntent(s, Side.BUY, qty, Purpose.ENTRY, close, stop_price=stop)
            if self.route(intent, risk_per_share=risk_ps):
                self.entries_today += 1
