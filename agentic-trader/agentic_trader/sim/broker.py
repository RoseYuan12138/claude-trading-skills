"""Daily-bar simulated broker with server-side protective stops.

Execution model (deliberately conservative):
* Orders submitted on day D are eligible from the next bar onward.
* Market orders fill at the open (+/- slippage).
* Sell-stops fill at the stop price when the bar trades through it, or at the
  open when the bar gaps below the stop (the realistic worst case for stops).
* Entries carrying ``stop_price`` get a broker-side stop attached on fill, like a
  take-profit/stop-loss order at Robinhood.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from datetime import date

from ..models import Bar, OrderIntent, OrderType, PositionSnapshot, Purpose, Side


@dataclass
class _Order:
    id: int
    symbol: str
    side: Side
    qty: float
    order_type: OrderType
    created: date
    stop_price: float | None = None
    attach_stop: float | None = None
    risk_per_share: float | None = None
    kind: str = "entry"  # entry / exit / stop
    attached: bool = False  # bracket stop created by an entry fill: live on the same bar


@dataclass
class Fill:
    date: date
    symbol: str
    side: Side
    qty: float
    price: float
    kind: str


@dataclass
class SimPosition:
    qty: float
    avg_price: float
    entry_date: date
    risk_per_share: float
    highest_close: float
    stop_order_id: int | None = None
    stop_price: float | None = None


@dataclass
class ClosedTrade:
    symbol: str
    entry_date: date
    exit_date: date
    entry_price: float
    exit_price: float
    qty: float
    risk_per_share: float
    exit_kind: str
    stop_level: float | None
    gap_fill: bool = False  # stop filled at an open that was already below the stop

    @property
    def pnl(self) -> float:
        return (self.exit_price - self.entry_price) * self.qty

    @property
    def r_multiple(self) -> float:
        return (self.exit_price - self.entry_price) / self.risk_per_share

    @property
    def gapped_through_stop(self) -> bool:
        return self.gap_fill


class SimBroker:
    def __init__(self, cash: float, slippage_bps: float = 5.0):
        self.cash = float(cash)
        self.slippage = slippage_bps / 10_000
        self.positions: dict[str, SimPosition] = {}
        self.orders: dict[int, _Order] = {}
        self.fills: list[Fill] = []
        self.closed_trades: list[ClosedTrade] = []
        self._ids = itertools.count(1)

    # ------------------------------------------------------------------ orders

    def submit(self, intent: OrderIntent, as_of: date, risk_per_share: float | None = None) -> int:
        if intent.order_type is OrderType.LIMIT:
            raise NotImplementedError("limit orders are not simulated yet")
        oid = next(self._ids)
        if intent.purpose is Purpose.ENTRY:
            order = _Order(
                oid,
                intent.symbol,
                Side.BUY,
                intent.qty,
                OrderType.MARKET,
                as_of,
                attach_stop=intent.stop_price,
                risk_per_share=risk_per_share,
                kind="entry",
            )
        elif intent.purpose is Purpose.EXIT:
            order = _Order(oid, intent.symbol, Side.SELL, intent.qty, OrderType.MARKET, as_of)
            order.kind = "exit"
        else:  # STOP_UPDATE: replace the existing protective stop
            pos = self.positions.get(intent.symbol)
            if pos is None:
                raise ValueError(f"no position in {intent.symbol} to protect")
            if pos.stop_order_id is not None:
                self.orders.pop(pos.stop_order_id, None)
            order = _Order(
                oid,
                intent.symbol,
                Side.SELL,
                min(intent.qty, pos.qty),
                OrderType.STOP,
                as_of,
                stop_price=intent.stop_price,
                kind="stop",
            )
            pos.stop_order_id = oid
            pos.stop_price = intent.stop_price
        self.orders[oid] = order
        return oid

    def open_stop_orders(self) -> dict[int, _Order]:
        return {i: o for i, o in self.orders.items() if o.kind == "stop"}

    def pending_entry_symbols(self) -> set[str]:
        return {o.symbol for o in self.orders.values() if o.kind == "entry"}

    def pending_entry_notional(self, prices: dict[str, float]) -> float:
        return sum(
            o.qty * prices.get(o.symbol, 0.0) for o in self.orders.values() if o.kind == "entry"
        )

    # --------------------------------------------------------------- matching

    def process_bar(self, symbol: str, bar: Bar) -> list[Fill]:
        fills: list[Fill] = []
        # Pass 1: market orders at the open.
        for order in [o for o in self._eligible(symbol, bar) if o.order_type is OrderType.MARKET]:
            if order.id in self.orders:
                fill = self._fill_market(order, bar)
                if fill:
                    fills.append(fill)
        # Pass 2: stops through the bar (including bracket stops attached in pass 1).
        for order in [o for o in self._eligible(symbol, bar) if o.order_type is OrderType.STOP]:
            if order.id in self.orders:
                fill = self._fill_stop(order, bar)
                if fill:
                    fills.append(fill)
        pos = self.positions.get(symbol)
        if pos:
            pos.highest_close = max(pos.highest_close, bar.close)
        self.fills.extend(fills)
        return fills

    def _eligible(self, symbol: str, bar: Bar) -> list[_Order]:
        return sorted(
            (
                o
                for o in self.orders.values()
                if o.symbol == symbol and (o.created < bar.date or o.attached)
            ),
            key=lambda o: o.id,
        )

    def _fill_market(self, order: _Order, bar: Bar) -> Fill | None:
        del self.orders[order.id]
        if order.side is Side.BUY:
            price = bar.open * (1 + self.slippage)
            qty = min(order.qty, math.floor(self.cash / price))
            if qty <= 0:
                return None
            self._open(order, qty, price, bar)
            return Fill(bar.date, order.symbol, Side.BUY, qty, price, "entry")
        pos = self.positions.get(order.symbol)
        if pos is None:
            return None
        qty = min(order.qty, pos.qty)
        price = bar.open * (1 - self.slippage)
        self._close(order.symbol, qty, price, bar.date, "exit")
        return Fill(bar.date, order.symbol, Side.SELL, qty, price, "exit")

    def _fill_stop(self, order: _Order, bar: Bar) -> Fill | None:
        stop = order.stop_price
        if stop is None or bar.low > stop:
            return None
        del self.orders[order.id]
        pos = self.positions.get(order.symbol)
        if pos is None:
            return None
        gapped = bar.open < stop
        price = (bar.open if gapped else stop) * (1 - self.slippage)
        qty = min(order.qty, pos.qty)
        self._close(order.symbol, qty, price, bar.date, "stop", stop_level=stop, gap=gapped)
        return Fill(bar.date, order.symbol, Side.SELL, qty, price, "stop")

    def _open(self, order: _Order, qty: float, price: float, bar: Bar) -> None:
        self.cash -= qty * price
        pos = self.positions.get(order.symbol)
        risk = order.risk_per_share
        if risk is None and order.attach_stop is not None:
            risk = price - order.attach_stop
        risk = risk if risk and risk > 0 else price * 0.08
        if pos is None:
            pos = SimPosition(qty, price, bar.date, risk, bar.open)
            self.positions[order.symbol] = pos
        else:
            total = pos.qty + qty
            pos.avg_price = (pos.avg_price * pos.qty + price * qty) / total
            pos.qty = total
        if order.attach_stop is not None:
            if pos.stop_order_id is not None:
                self.orders.pop(pos.stop_order_id, None)
            sid = next(self._ids)
            self.orders[sid] = _Order(
                sid,
                order.symbol,
                Side.SELL,
                pos.qty,
                OrderType.STOP,
                bar.date,
                stop_price=order.attach_stop,
                kind="stop",
                attached=True,
            )
            pos.stop_order_id = sid
            pos.stop_price = order.attach_stop

    def _close(
        self,
        symbol: str,
        qty: float,
        price: float,
        when: date,
        kind: str,
        stop_level: float | None = None,
        gap: bool = False,
    ) -> None:
        pos = self.positions[symbol]
        self.cash += qty * price
        self.closed_trades.append(
            ClosedTrade(
                symbol,
                pos.entry_date,
                when,
                pos.avg_price,
                price,
                qty,
                pos.risk_per_share,
                kind,
                stop_level if stop_level is not None else pos.stop_price,
                gap,
            )
        )
        pos.qty -= qty
        if pos.qty <= 1e-9:
            if pos.stop_order_id is not None:
                self.orders.pop(pos.stop_order_id, None)
            del self.positions[symbol]
        elif pos.stop_order_id in self.orders:
            self.orders[pos.stop_order_id].qty = pos.qty

    # -------------------------------------------------------------- reporting

    def equity(self, prices: dict[str, float]) -> float:
        return self.cash + sum(
            p.qty * prices.get(s, p.avg_price) for s, p in self.positions.items()
        )

    def snapshots(self, prices: dict[str, float]) -> dict[str, PositionSnapshot]:
        return {
            s: PositionSnapshot(p.qty, p.avg_price, prices.get(s, p.avg_price), p.stop_price)
            for s, p in self.positions.items()
        }
