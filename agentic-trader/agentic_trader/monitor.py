"""Layer 1: cheap, deterministic market monitor.

Runs every few minutes (live) or every bar (simulation) with zero LLM cost and
decides *when* the expensive LLM layer is worth waking up.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from .events import EventCalendar
from .models import Bar, PositionSnapshot


@dataclass(frozen=True)
class Trigger:
    kind: str  # gap / volume_spike / stop_proximity / event_ahead / drawdown / unprotected
    symbol: str | None
    severity: int  # 1 info (code handles it), 2 notable, 3 urgent
    detail: str
    value: float = 0.0  # e.g. gap %, drawdown %


@dataclass
class MonitorConfig:
    gap_pct: float = 4.0
    volume_mult: float = 3.0
    volume_lookback: int = 20
    stop_proximity_atr: float = 0.5
    event_horizon_days: int = 3  # calendar days, so Friday sees Monday's events
    macro_min_importance: int = 3
    drawdown_pct: float = 8.0
    flag_unprotected: bool = True
    wake_severity: int = 2
    cooldown_days: int = 3  # same (kind, symbol) won't wake the LLM again within this window


class Monitor:
    def __init__(self, config: MonitorConfig | None = None):
        self.cfg = config or MonitorConfig()
        self._last_wake: dict[tuple[str, str | None], date] = {}
        # Drawdown alerts once per episode: re-armed only after recovering below half
        # the threshold. Otherwise a persistent drawdown re-halts entries forever.
        self._drawdown_armed = True

    def scan(
        self,
        as_of: date,
        history: dict[str, Sequence[Bar]],
        atrs: dict[str, float | None],
        positions: dict[str, PositionSnapshot],
        calendar: EventCalendar,
        drawdown_pct: float = 0.0,
    ) -> list[Trigger]:
        cfg = self.cfg
        out: list[Trigger] = []
        for sym, pos in positions.items():
            bars = history.get(sym) or ()
            if len(bars) >= 2 and bars[-1].date == as_of:
                today, prev = bars[-1], bars[-2]
                gap = (today.open / prev.close - 1) * 100
                if abs(gap) >= cfg.gap_pct:
                    out.append(Trigger("gap", sym, 3, f"{sym} gapped {gap:+.1f}%", gap))
                window = bars[-cfg.volume_lookback - 1 : -1]
                if window:
                    avg_vol = sum(b.volume for b in window) / len(window)
                    if avg_vol > 0 and today.volume >= cfg.volume_mult * avg_vol:
                        out.append(
                            Trigger(
                                "volume_spike",
                                sym,
                                2,
                                f"{sym} volume {today.volume / avg_vol:.1f}x 20d avg",
                            )
                        )
            atr = atrs.get(sym)
            if pos.stop_price is None:
                if cfg.flag_unprotected:
                    out.append(Trigger("unprotected", sym, 3, f"{sym} has no protective stop"))
            elif atr and pos.last_price - pos.stop_price <= cfg.stop_proximity_atr * atr:
                out.append(
                    Trigger(
                        "stop_proximity",
                        sym,
                        1,
                        f"{sym} {pos.last_price:.2f} within {cfg.stop_proximity_atr} ATR of stop",
                    )
                )

        for ev in calendar.upcoming(as_of, cfg.event_horizon_days, positions.keys()):
            if ev.symbol is not None:
                out.append(Trigger("event_ahead", ev.symbol, 3, f"{ev.kind} on {ev.date}"))
            elif positions and ev.importance >= cfg.macro_min_importance:
                out.append(Trigger("event_ahead", None, 2, f"{ev.kind} on {ev.date}"))

        if drawdown_pct < cfg.drawdown_pct / 2:
            self._drawdown_armed = True
        elif drawdown_pct >= cfg.drawdown_pct and self._drawdown_armed:
            self._drawdown_armed = False
            out.append(
                Trigger(
                    "drawdown", None, 3, f"portfolio drawdown {drawdown_pct:.1f}%", drawdown_pct
                )
            )
        return out

    def should_wake(self, as_of: date, triggers: Sequence[Trigger]) -> list[Trigger]:
        """Return the triggers that justify an LLM call (and arm their cooldown)."""
        fresh = []
        for t in triggers:
            if t.severity < self.cfg.wake_severity:
                continue
            key = (t.kind, t.symbol)
            last = self._last_wake.get(key)
            if last is not None and (as_of - last).days < self.cfg.cooldown_days:
                continue
            fresh.append(t)
        for t in fresh:
            self._last_wake[(t.kind, t.symbol)] = as_of
        return fresh
