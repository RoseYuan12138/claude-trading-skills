"""Daily-bar simulator for an agent that opens its own option positions.

Pricing model (an approximation -- no historical option chains):
* Implied vol = 20-day realized vol x ``iv_premium`` (floored), Black-Scholes, no dividends.
* Every fill pays half the bid-ask spread: ``max(min_half_spread, half_spread_pct x mid)``.
* Decisions at the close; orders work from the next open. Entries are limit orders at
  the ask seen at the close and do not fill if the next open is worse. Exits fill at
  the next open's bid, so overnight gaps hit the exit price.
Not modelled: earnings IV crush, volatility skew, early assignment, dividends.
"""

from __future__ import annotations

import math
import re
import statistics
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta

from ..events import EventCalendar
from ..models import Bar, OrderType, Side
from ..options import (
    MULTIPLIER,
    OptionAction,
    OptionBookState,
    OptionExitRules,
    OptionLeg,
    OptionOrder,
    OptionPosition,
    OptionRules,
    Right,
    exit_signal,
    validate_option,
)
from ..pricing import bs_price
from ..stops import WilderATR


@dataclass
class OptionSimConfig:
    initial_cash: float = 50_000.0
    risk_per_trade_pct: float = 2.0  # premium paid (= worst case) per entry, % of equity
    structure: str = "long"  # "long" or "debit_vertical"
    target_dte: int = 35
    spread_width_atr: float = 2.0  # short-strike distance for verticals
    iv_premium: float = 1.15
    iv_floor: float = 0.15
    half_spread_pct: float = 2.5
    entry_limit_buffer_pct: float = 3.0  # limit = ask + this % of mid, so small gaps still fill
    min_half_spread: float = 0.02
    rate: float = 0.04
    breakout_lookback: int = 20
    trend_sma: int = 50
    hv_window: int = 20
    atr_period: int = 14
    allow_puts: bool = True
    allow_calls: bool = True
    start_date: date | None = None
    # Market regime: with regime_symbol set, calls only while it closes at/above its SMA and
    # puts only while it closes below (bearish bets need no stock: long puts only).
    regime_symbol: str | None = None
    regime_sma: int = 50
    untradable: tuple[str, ...] = ()
    # Signals: "breakout" (calls on 20d highs, puts on 20d lows) or "bear_setups":
    # puts only on (a) an earnings-day gap down >= gap_down_pct on >= gap_volume_mult x
    # volume closing in the lower half of its range (any regime), or (b) a failed rally in a
    # downtrend: below a falling 50d SMA, high reaches the 20d SMA, red close below it
    # (requires the regime to be bearish when regime_symbol is set).
    signal_mode: str = "breakout"
    gap_down_pct: float = 5.0
    gap_volume_mult: float = 1.5
    rally_band_pct: float = 1.5
    bear_setups: tuple[str, ...] = ("earnings_gap", "failed_rally")
    # Entry filters applied to every signal
    earnings_blackout_days: int = 0  # skip entries with earnings this many calendar days ahead
    max_iv: float | None = None  # skip when the modelled IV is above this (e.g. 0.8)
    max_extension_pct: float | None = None  # skip if already this far past the 50d SMA


@dataclass
class OptionTrade:
    underlying: str
    right: Right
    entry_date: date
    exit_date: date
    entry_price: float
    exit_price: float
    contracts: int
    reason: str

    @property
    def pnl(self) -> float:
        return (self.exit_price - self.entry_price) * MULTIPLIER * self.contracts

    @property
    def r_multiple(self) -> float:
        """P&L as a multiple of the premium at risk: -1.0 means the whole premium was lost."""
        return (self.exit_price - self.entry_price) / self.entry_price


@dataclass
class OptionSimResult:
    name: str
    equity_curve: list[tuple[date, float]] = field(default_factory=list)
    trades: list[OptionTrade] = field(default_factory=list)
    blocked: Counter = field(default_factory=Counter)
    unfilled_entries: int = 0

    def metrics(self) -> dict[str, float]:
        eq = [e for _, e in self.equity_curve]
        rets = [b / a - 1 for a, b in zip(eq, eq[1:]) if a > 0]
        sd = statistics.pstdev(rets) if len(rets) > 1 else 0.0
        peak, max_dd = eq[0], 0.0
        for e in eq:
            peak = max(peak, e)
            max_dd = max(max_dd, 1 - e / peak)
        years = len(eq) / 252
        rs = [t.r_multiple for t in self.trades]
        holds = [(t.exit_date - t.entry_date).days for t in self.trades]
        return {
            "total_return_pct": (eq[-1] / eq[0] - 1) * 100,
            "cagr_pct": ((eq[-1] / eq[0]) ** (1 / years) - 1) * 100 if eq[-1] > 0 else -100.0,
            "max_drawdown_pct": max_dd * 100,
            "sharpe": statistics.mean(rets) / sd * math.sqrt(252) if sd > 0 else 0.0,
            "trades": float(len(rs)),
            "win_rate_pct": sum(r > 0 for r in rs) / len(rs) * 100 if rs else float("nan"),
            "avg_r": statistics.mean(rs) if rs else float("nan"),
            "worst_r": min(rs) if rs else float("nan"),
            "lost_90pct_plus": float(sum(r <= -0.9 for r in rs)),
            "avg_hold_days": statistics.mean(holds) if holds else float("nan"),
        }


def strike_step(price: float) -> float:
    if price < 25:
        return 0.5
    if price < 100:
        return 1.0
    if price < 250:
        return 2.5
    if price < 1000:
        return 5.0
    return 10.0


def round_strike(price: float, step: float) -> float:
    return round(round(price / step) * step, 4)


def expiry_after(as_of: date, days: int) -> date:
    d = as_of + timedelta(days=days)
    return d + timedelta(days=(4 - d.weekday()) % 7)  # next Friday on/after


@dataclass
class _Pending:
    symbol: str
    legs: tuple[OptionLeg, ...]
    right: Right
    limit: float
    contracts: int
    max_loss: float
    created: date


class OptionSimulator:
    def __init__(
        self,
        data: dict[str, list[Bar]],
        rules: OptionRules,
        exits: OptionExitRules,
        config: OptionSimConfig | None = None,
        name: str = "",
        calendar: EventCalendar | None = None,
    ):
        self.data = data
        self.calendar = calendar or EventCalendar()
        self.rules = rules
        self.exits = exits
        self.cfg = config or OptionSimConfig()
        if self.cfg.regime_symbol and self.cfg.regime_symbol not in data:
            raise ValueError(f"regime_symbol {self.cfg.regime_symbol} is not in the data")
        self.cash = self.cfg.initial_cash
        self.positions: dict[str, OptionPosition] = {}
        self.pending_entries: dict[str, _Pending] = {}
        self.pending_exits: dict[str, str] = {}  # symbol -> reason
        self.history: dict[str, list[Bar]] = {s: [] for s in data}
        self.atr = {s: WilderATR(self.cfg.atr_period) for s in data}
        self.atrs: dict[str, float | None] = {}
        self.result = OptionSimResult(name)

    # ------------------------------------------------------------ pricing

    def _iv(self, sym: str) -> float:
        closes = [b.close for b in self.history[sym][-self.cfg.hv_window - 1 :]]
        if len(closes) < 3:
            return self.cfg.iv_floor
        rets = [math.log(b / a) for a, b in zip(closes, closes[1:])]
        hv = statistics.stdev(rets) * math.sqrt(252)
        return max(hv * self.cfg.iv_premium, self.cfg.iv_floor)

    def _mid(self, sym: str, legs: tuple[OptionLeg, ...], spot: float, as_of: date) -> float:
        iv = self._iv(sym)
        total = 0.0
        for lg in legs:
            t = max((lg.expiry - as_of).days, 0) / 365
            px = bs_price(spot, lg.strike, t, self.cfg.rate, iv, lg.right)
            total += px if lg.side is Side.BUY else -px
        return total

    def _half_spread(self, sym, legs, spot, as_of) -> float:
        iv = self._iv(sym)
        h = 0.0
        for lg in legs:
            t = max((lg.expiry - as_of).days, 0) / 365
            px = bs_price(spot, lg.strike, t, self.cfg.rate, iv, lg.right)
            h += max(self.cfg.min_half_spread, px * self.cfg.half_spread_pct / 100)
        return h

    # -------------------------------------------------------------- state

    def _value(self, sym: str, as_of: date) -> float:
        pos = self.positions[sym]
        return max(self._mid(sym, pos.legs, self.history[sym][-1].close, as_of), 0.0)

    def _equity(self, as_of: date) -> float:
        return self.cash + sum(
            self._value(s, as_of) * MULTIPLIER * p.contracts for s, p in self.positions.items()
        )

    def _book(self, equity: float, day_start: float, entries_today: int) -> OptionBookState:
        legs: dict = {}
        for s, p in self.positions.items():
            for lg in p.legs:
                sign = 1 if lg.side is Side.BUY else -1
                legs[lg.key(s)] = legs.get(lg.key(s), 0) + sign * lg.qty
        open_risk = sum(p.max_loss for p in self.positions.values()) + sum(
            p.max_loss for p in self.pending_entries.values()
        )
        return OptionBookState(
            equity=equity,
            cash=self.cash - sum(p.max_loss for p in self.pending_entries.values()),
            day_start_equity=day_start,
            open_risk=open_risk,
            open_positions=len(self.positions) + len(self.pending_entries),
            entries_today=entries_today,
            legs=legs,
        )

    # --------------------------------------------------------------- loop

    def run(self) -> OptionSimResult:
        by_date = {s: {b.date: b for b in bars} for s, bars in self.data.items()}
        dates = sorted({d for idx in by_date.values() for d in idx})
        start = self.cfg.start_date
        prev_equity = self.cfg.initial_cash
        for d in dates:
            today = {s: idx[d] for s, idx in by_date.items() if d in idx}
            for s, bar in today.items():
                # Fill at the open using only information known before it (no lookahead):
                # IV and ATR still reflect yesterday's close.
                self._execute_at_open(s, bar, d)
                self.history[s].append(bar)
                self.atrs[s] = self.atr[s].update(bar)
            if start is not None and d < start:
                continue
            for s in list(self.positions):
                if s in today:
                    self._settle_if_expired(s, d)
            equity = self._equity(d)
            entries_today = 0
            for s in list(self.positions):
                if s not in today or s in self.pending_exits:
                    continue
                pos = self.positions[s]
                value = self._value(s, d)
                pos.peak_price = max(pos.peak_price, value)
                reason = exit_signal(pos, value, today[s].close, self.atrs.get(s), d, self.exits)
                if reason:
                    self.pending_exits[s] = reason
            for s in sorted(today):
                if s in self.positions or s in self.pending_entries:
                    continue
                order = self._signal(s, d, equity)
                if order is None:
                    continue
                decision = validate_option(
                    order, self._book(equity, prev_equity, entries_today), self.rules
                )
                if not decision.allowed:
                    for r in decision.reasons:
                        self.result.blocked[_short_reason(r)] += 1
                    continue
                self.pending_entries[s] = _Pending(
                    s,
                    order.legs,
                    order.legs[0].right,
                    order.limit_price,
                    order.legs[0].qty,
                    order.limit_price * MULTIPLIER * order.legs[0].qty,
                    d,
                )
                entries_today += 1
            self.result.equity_curve.append((d, equity))
            prev_equity = equity
        return self.result

    def _regime(self) -> str | None:
        """'bull' / 'bear' from the benchmark vs its SMA; None if no filter or no history."""
        cfg = self.cfg
        if not cfg.regime_symbol:
            return None
        h = self.history[cfg.regime_symbol]
        if len(h) < cfg.regime_sma:
            return None
        sma = sum(b.close for b in h[-cfg.regime_sma :]) / cfg.regime_sma
        return "bull" if h[-1].close >= sma else "bear"

    def _signal(self, s: str, d: date, equity: float) -> OptionOrder | None:
        cfg, h = self.cfg, self.history[s]
        if s in cfg.untradable:
            return None
        atr = self.atrs.get(s)
        if len(h) < max(cfg.breakout_lookback, cfg.trend_sma) + 1 or not atr:
            return None
        close = h[-1].close
        prior = h[-cfg.breakout_lookback - 1 : -1]
        sma = sum(b.close for b in h[-cfg.trend_sma :]) / cfg.trend_sma
        regime = self._regime()
        if cfg.signal_mode == "bear_setups":
            setup = self._bear_setup(s, h, d, sma, regime) if cfg.allow_puts else None
            if setup is None:
                return None
            right, note = Right.PUT, setup
        elif (
            cfg.allow_calls
            and regime != "bear"
            and close > max(b.high for b in prior)
            and close > sma
        ):
            right, note = Right.CALL, "bull"
        elif (
            cfg.allow_puts
            and regime != "bull"
            and close < min(b.low for b in prior)
            and close < sma
        ):
            right, note = Right.PUT, "bear"
        else:
            return None
        if not self._entry_filters_ok(s, d, close, sma, right):
            return None
        step = strike_step(close)
        expiry = expiry_after(d, cfg.target_dte)
        k = round_strike(close, step)
        legs = [OptionLeg(right, k, expiry, Side.BUY, 1)]
        if cfg.structure == "debit_vertical":
            w = max(step, round_strike(cfg.spread_width_atr * atr, step))
            k2 = k + w if right is Right.CALL else k - w
            legs.append(OptionLeg(right, k2, expiry, Side.SELL, 1))
        legs_t = tuple(legs)
        mid = self._mid(s, legs_t, close, d)
        half = self._half_spread(s, legs_t, close, d)
        limit = round(mid + half + mid * cfg.entry_limit_buffer_pct / 100, 2)
        if limit <= 0.05:
            return None
        contracts = min(
            math.floor(equity * cfg.risk_per_trade_pct / 100 / (limit * MULTIPLIER)),
            self.rules.max_contracts,
        )
        if contracts <= 0:
            return None
        quoted = tuple(
            OptionLeg(
                lg.right,
                lg.strike,
                lg.expiry,
                lg.side,
                contracts,
                *self._leg_quote(s, lg, close, d),
            )
            for lg in legs_t
        )
        return OptionOrder(s, quoted, OptionAction.OPEN, OrderType.LIMIT, limit, d, note=note)

    def _bear_setup(self, s: str, h: list[Bar], d: date, sma50: float, regime) -> str | None:
        cfg = self.cfg
        today, prev = h[-1], h[-2]
        window = h[-21:-1]
        avg_vol = sum(b.volume for b in window) / len(window)
        gap = (today.open / prev.close - 1) * 100
        rng = today.high - today.low
        weak_close = today.close <= today.open and (
            rng <= 0 or today.close <= today.low + 0.5 * rng
        )
        is_earnings = any(e.kind == "earnings" and e.symbol == s for e in self.calendar.on(d))
        if (
            is_earnings
            and gap <= -cfg.gap_down_pct
            and avg_vol > 0
            and today.volume >= cfg.gap_volume_mult * avg_vol
            and weak_close
            and "earnings_gap" in cfg.bear_setups
        ):
            return "earnings_gap"
        if "failed_rally" not in cfg.bear_setups:
            return None
        if regime == "bull" or len(h) < cfg.trend_sma + 11:
            return None
        sma20 = sum(b.close for b in h[-21:-1]) / 20
        sma50_before = sum(b.close for b in h[-cfg.trend_sma - 10 : -10]) / cfg.trend_sma
        if (
            today.close < sma50
            and sma50 < sma50_before
            and today.high >= sma20 * (1 - cfg.rally_band_pct / 100)
            and today.close < sma20
            and today.close < today.open
        ):
            return "failed_rally"
        return None

    def _entry_filters_ok(self, s: str, d: date, close: float, sma50: float, right) -> bool:
        cfg = self.cfg
        if cfg.earnings_blackout_days > 0 and any(
            e.kind == "earnings" and e.symbol == s
            for e in self.calendar.upcoming(d, cfg.earnings_blackout_days, [s])
        ):
            return False
        if cfg.max_iv is not None and self._iv(s) > cfg.max_iv:
            return False
        if cfg.max_extension_pct is not None and sma50 > 0:
            ext = (close / sma50 - 1) * 100 if right is Right.CALL else (1 - close / sma50) * 100
            if ext > cfg.max_extension_pct:
                return False
        return True

    def _leg_quote(self, s, lg, spot, d) -> tuple[float, float]:
        t = max((lg.expiry - d).days, 0) / 365
        px = bs_price(spot, lg.strike, t, self.cfg.rate, self._iv(s), lg.right)
        h = max(self.cfg.min_half_spread, px * self.cfg.half_spread_pct / 100)
        return max(px - h, 0.0), px + h

    def _execute_at_open(self, s: str, bar: Bar, d: date) -> None:
        if s in self.pending_exits and s in self.positions:
            reason = self.pending_exits.pop(s)
            pos = self.positions.pop(s)
            mid = max(self._mid(s, pos.legs, bar.open, d), 0.0)
            px = max(mid - self._half_spread(s, pos.legs, bar.open, d), 0.0)
            self.cash += px * MULTIPLIER * pos.contracts
            self.result.trades.append(
                OptionTrade(
                    s, pos.right, pos.entry_date, d, pos.entry_price, px, pos.contracts, reason
                )
            )
        p = self.pending_entries.pop(s, None)
        if p is None:
            return
        mid = self._mid(s, p.legs, bar.open, d)
        px = mid + self._half_spread(s, p.legs, bar.open, d)
        if px > p.limit or px <= 0:
            self.result.unfilled_entries += 1
            return
        cost = px * MULTIPLIER * p.contracts
        if cost > self.cash:
            self.result.unfilled_entries += 1
            return
        self.cash -= cost
        self.positions[s] = OptionPosition(
            s, p.right, p.legs[0].expiry, px, px, bar.open, p.contracts, cost, p.legs, d
        )

    def _settle_if_expired(self, s: str, d: date) -> None:
        pos = self.positions[s]
        if d < pos.expiry:
            return
        px = max(self._mid(s, pos.legs, self.history[s][-1].close, pos.expiry), 0.0)
        self.positions.pop(s)
        self.pending_exits.pop(s, None)
        self.cash += px * MULTIPLIER * pos.contracts
        self.result.trades.append(
            OptionTrade(
                s, pos.right, pos.entry_date, d, pos.entry_price, px, pos.contracts, "expiry"
            )
        )


def _short_reason(reason: str) -> str:
    return re.sub(r"[-+$]?\d[\d,]*\.?\d*%?", "N", reason)
