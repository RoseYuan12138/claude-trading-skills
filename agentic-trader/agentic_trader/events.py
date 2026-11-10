"""Scheduled market events (earnings, FOMC, CPI ...) known in advance."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path

MACRO_KINDS = frozenset({"fomc", "cpi", "nfp", "pce", "gdp"})


@dataclass(frozen=True)
class Event:
    date: date
    kind: str  # "earnings" or a macro kind
    symbol: str | None = None  # None for macro events
    importance: int = 2  # 1 low, 2 medium, 3 high


class EventCalendar:
    def __init__(self, events: Iterable[Event] = ()):
        self.events = sorted(events, key=lambda e: e.date)

    def upcoming(
        self, as_of: date, horizon_days: int, symbols: Iterable[str] | None = None
    ) -> list[Event]:
        """Events strictly after ``as_of`` and within ``horizon_days`` calendar days.

        Macro events are always returned; earnings only for ``symbols`` (if given).
        """
        wanted = set(symbols) if symbols is not None else None
        end = as_of + timedelta(days=horizon_days)
        out = []
        for e in self.events:
            if e.date <= as_of:
                continue
            if e.date > end:
                break
            if e.symbol is None or wanted is None or e.symbol in wanted:
                out.append(e)
        return out

    def on(self, day: date) -> list[Event]:
        return [e for e in self.events if e.date == day]

    # ---- persistence: compatible shape for economic/earnings calendar exports ----

    def to_json(self, path: str | Path) -> None:
        rows = [{**asdict(e), "date": e.date.isoformat()} for e in self.events]
        Path(path).write_text(json.dumps(rows, indent=2))

    @classmethod
    def from_json(cls, path: str | Path) -> EventCalendar:
        rows = json.loads(Path(path).read_text())
        return cls(
            Event(
                date.fromisoformat(r["date"]),
                r["kind"],
                r.get("symbol"),
                int(r.get("importance", 2)),
            )
            for r in rows
        )
