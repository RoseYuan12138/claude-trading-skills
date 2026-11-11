"""Forward paper trading for the LEAPS trend-call strategy.

One step per trading day after the close: decide with ``playbook.itm_trend_ticket``, fill at
the real quote if one is given (else the model price plus half the bid-ask), mark the
position to the model, and keep a journal. Logging real quotes next to model prices is the
main point: it measures how far the backtest's pricing is from reality.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from .models import Bar
from .options import MULTIPLIER
from .playbook import ItmTrendParams, OpenCall, _estimate, itm_trend_ticket

HALF_SPREAD_PCT = 0.5  # used when no real quote is given


@dataclass
class PaperPosition:
    strike: float
    expiry: date
    contracts: int
    entry_price: float
    entry_date: date


@dataclass
class JournalRow:
    date: date
    action: str
    contracts: int
    strike: float
    expiry: date | None
    model_price: float  # per share, model mid
    quote: float | None  # per share, what you entered from the broker
    fill: float  # per share, price used for the trade (0 if none)
    equity: float
    note: str = ""

    @property
    def quote_vs_model_pct(self) -> float | None:
        if self.quote is None or not self.model_price:
            return None
        return (self.quote / self.model_price - 1) * 100


@dataclass
class PaperState:
    cash: float
    position: PaperPosition | None = None
    history: list[JournalRow] = field(default_factory=list)
    last_mark: float = 0.0  # model value per share of the open position at the last step
    stop_reason: str | None = None  # "goal" / "floor" once the account has stopped trading

    @property
    def equity(self) -> float:
        if self.position is None:
            return self.cash
        return self.cash + self.last_mark * MULTIPLIER * self.position.contracts

    # ---- persistence ----
    def save(self, path: str | Path) -> None:
        def enc(o):
            if isinstance(o, date):
                return o.isoformat()
            raise TypeError(o)

        data = {
            "cash": self.cash,
            "last_mark": self.last_mark,
            "position": asdict(self.position) if self.position else None,
            "history": [asdict(r) for r in self.history],
            "stop_reason": self.stop_reason,
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(data, indent=2, default=enc))

    @classmethod
    def load(cls, path: str | Path) -> PaperState:
        raw = json.loads(Path(path).read_text())
        pos = raw.get("position")
        if pos:
            pos = PaperPosition(
                pos["strike"],
                date.fromisoformat(pos["expiry"]),
                pos["contracts"],
                pos["entry_price"],
                date.fromisoformat(pos["entry_date"]),
            )
        hist = []
        for r in raw.get("history", []):
            r = dict(r)
            r["date"] = date.fromisoformat(r["date"])
            r["expiry"] = date.fromisoformat(r["expiry"]) if r.get("expiry") else None
            hist.append(JournalRow(**r))
        return cls(raw["cash"], pos, hist, raw.get("last_mark", 0.0), raw.get("stop_reason"))


def paper_step(
    state: PaperState,
    spy_bars: list[Bar],
    qqq_bars: list[Bar],
    iv: float,
    rate: float,
    params: ItmTrendParams | None = None,
    quote: float | None = None,
) -> tuple[PaperState, JournalRow]:
    """Advance one day. ``quote`` is the real per-share price for the contract being
    traded (the new one on BUY/ROLL, the held one on SELL); omit it to use the model."""
    p = params or ItmTrendParams()
    as_of = min(spy_bars[-1].date, qqq_bars[-1].date)
    qqq_close = qqq_bars[-1].close
    pos = state.position
    open_call = OpenCall(pos.strike, pos.expiry, pos.contracts) if pos else None
    # mark the current position before deciding (equity for sizing)
    mark = 0.0
    if pos:
        mark, _ = _estimate(qqq_close, pos.strike, pos.expiry, as_of, iv, rate, p)
    equity = state.cash + mark * MULTIPLIER * (pos.contracts if pos else 0)
    t = itm_trend_ticket(spy_bars, qqq_close, as_of, equity, iv, rate, open_call, p, qqq_bars)
    hs = HALF_SPREAD_PCT / 100
    cash, new_pos, fill, model = state.cash, pos, 0.0, 0.0

    if t.action in {"SELL", "ROLL"} and pos:
        model = mark
        fill = quote if (quote is not None and t.action == "SELL") else mark * (1 - hs)
        cash += fill * MULTIPLIER * pos.contracts
        new_pos = None
    if t.action in {"BUY", "ROLL"}:
        # re-size with the cash actually available after a roll
        budget_equity = cash if new_pos is None else equity
        model = t.est_price
        fill = quote if quote is not None else t.est_price * (1 + hs)
        contracts = int(budget_equity * p.premium_pct / 100 // (fill * MULTIPLIER))
        if contracts > 0:
            cash -= fill * MULTIPLIER * contracts
            new_pos = PaperPosition(t.strike, t.expiry, contracts, fill, as_of)
        else:
            new_pos = None
    if t.action == "HOLD":
        model = mark

    last_mark = 0.0
    if new_pos is not None:
        last_mark, _ = _estimate(qqq_close, new_pos.strike, new_pos.expiry, as_of, iv, rate, p)
    new_state = PaperState(cash, new_pos, list(state.history), last_mark)
    row = JournalRow(
        as_of,
        t.action,
        new_pos.contracts if new_pos else 0,
        new_pos.strike if new_pos else 0.0,
        new_pos.expiry if new_pos else None,
        model,
        quote,
        fill,
        new_state.equity,
        t.note,
    )
    new_state.history.append(row)
    return new_state, row


def check_stop(
    state: PaperState, goal: float, floor: float
) -> tuple[PaperState, JournalRow | None]:
    """Stop trading for good once equity reaches ``goal`` or falls below ``floor``: close
    any open call at the model bid (last mark less half the bid-ask) and hold cash."""
    eq = state.equity
    if state.stop_reason or floor <= eq < goal:
        return state, None
    reason = "goal" if eq >= goal else "floor"
    cash, pos, fill = state.cash, state.position, 0.0
    if pos is not None:
        fill = state.last_mark * (1 - HALF_SPREAD_PCT / 100)
        cash += fill * MULTIPLIER * pos.contracts
    last = state.history[-1].date if state.history else date.today()
    new = PaperState(cash, None, list(state.history), 0.0, reason)
    row = JournalRow(
        last,
        f"STOP_{reason.upper()}",
        0,
        pos.strike if pos else 0.0,
        pos.expiry if pos else None,
        state.last_mark,
        None,
        fill,
        cash,
        f"equity ${eq:,.0f} {'>=' if reason == 'goal' else '<'} "
        f"${goal if reason == 'goal' else floor:,.0f}: stop trading",
    )
    new.history.append(row)
    return new, row
