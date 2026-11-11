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
from ..market_score import ScoreTier, pick_tier
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
    classify,
    credit_exit_signal,
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
    rate: float = 0.04  # used when no rate series is given
    div_yield: float = 0.0  # continuous dividend yield of the underlying (QQQ ~0.007)
    # Volatility skew by strike, in vol points per 1% away from spot: strikes below spot
    # trade at higher IV (index skew is roughly 0.5-1.5 points per 1% for 1-month options,
    # flatter for longer expiries), strikes above at lower IV. Applies to calls and puts.
    put_skew_per_pct: float = 0.0
    call_skew_per_pct: float = 0.0
    skew_term_scaling: bool = True  # skew values are for 30-day options; scale by sqrt(30/days)
    # IV term structure: the given IV is a 30-day vol; other expiries mean-revert toward
    # iv_term_mean at speed iv_term_kappa (per year). None = flat term structure.
    iv_term_mean: float | None = None
    iv_term_kappa: float = 3.0
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
    # Hysteresis: a bull regime flips to bear only below SMA x (1 - buffer%), a bear regime
    # flips to bull only above SMA x (1 + buffer%). 0 = plain close vs SMA.
    regime_buffer_pct: float = 0.0
    untradable: tuple[str, ...] = ()
    # Volatility targeting: scale the premium per trade by clip(vol_target / IV,
    # vol_target_floor, vol_target_cap). None = off.
    vol_target: float | None = None
    vol_target_cap: float = 1.5
    vol_target_floor: float = 0.25
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
    # "index_hedge": hold a put on hedge_symbols whenever the regime is bearish
    hedge_symbols: tuple[str, ...] = ("QQQ",)
    exit_on_regime_bull: bool = False  # close puts as soon as the regime turns bullish
    # Market-score tiers (see market_score.py): when set, each day's score picks whether
    # calls / puts are allowed, the premium per trade and the cap on premium at risk.
    score_tiers: tuple[ScoreTier, ...] = ()
    # "score_dip": buy a call on hedge_symbols whenever the day's score is below this
    dip_threshold: float = 30.0
    dip_requires_bull: bool = (
        False  # only buy dips while the regime is bullish (needs regime_symbol)
    )
    # In "breakout" mode, also buy dip calls on hedge_symbols when the score is below
    # dip_threshold (ignoring the regime filter), sized with dip_risk_pct.
    dip_overlay: bool = False
    # Strike placement: calls at close x m, puts at close x (2 - m). 1.0 = at the money,
    # 0.85 = calls 15% in the money (a stock-replacement call with little time value).
    strike_moneyness: float = 1.0
    # "index_trend": hold a call on hedge_symbols whenever the regime is bullish
    exit_on_regime_bear: bool = False  # close bullish positions when the regime turns bearish
    # "put_credit": sell a put spread on hedge_symbols while the regime is bullish; short
    # strike credit_otm_pct below the close, long strike credit_width_pct below that.
    credit_otm_pct: float = 5.0
    credit_width_pct: float = 5.0
    dip_risk_pct: float | None = None
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
    setup: str = ""
    max_loss: float = 0.0  # dollars at risk when opened

    @property
    def pnl(self) -> float:
        return (self.exit_price - self.entry_price) * MULTIPLIER * self.contracts

    @property
    def r_multiple(self) -> float:
        """P&L as a multiple of the money at risk: -1.0 means the whole risk was lost."""
        if self.entry_price < 0 and self.max_loss > 0:  # credit spread
            return self.pnl / self.max_loss
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


def _term_iv(iv30: float, t: float, long_run: float, kappa: float) -> float:
    """Average implied vol to expiry ``t`` (years) when variance mean-reverts to long_run**2."""

    def g(x: float) -> float:
        return (1 - math.exp(-kappa * x)) / (kappa * x)

    t30 = 30 / 365
    var = long_run**2 + (iv30**2 - long_run**2) * g(t) / g(t30)
    return math.sqrt(max(var, 1e-6))


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
    setup: str = ""


class OptionSimulator:
    def __init__(
        self,
        data: dict[str, list[Bar]],
        rules: OptionRules,
        exits: OptionExitRules,
        config: OptionSimConfig | None = None,
        name: str = "",
        calendar: EventCalendar | None = None,
        scores: dict[date, float] | None = None,
        iv_overrides: dict[str, dict[date, float]] | None = None,
        rates_pct: dict[date, float] | None = None,
    ):
        self.data = data
        self.calendar = calendar or EventCalendar()
        self.scores = scores or {}
        # symbol -> {date: implied vol in index points, e.g. VXN 25.0 = 25%}; used as-is
        # (no iv_premium) on the latest bar already known, so open fills use yesterday's.
        self.iv_overrides = iv_overrides or {}
        # annual short rate in percent by date (e.g. ^IRX); the latest known value is used
        self.rates_pct = rates_pct or {}
        self.rules = rules
        self.exits = exits
        self.cfg = config or OptionSimConfig()
        self._rate_now = self.cfg.rate
        self._pending_rate: float | None = None
        self._regime_state: str | None = None
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
        override = self.iv_overrides.get(sym)
        if override and self.history[sym]:
            v = override.get(self.history[sym][-1].date)
            if v is not None:
                return max(v / 100, self.cfg.iv_floor)
        closes = [b.close for b in self.history[sym][-self.cfg.hv_window - 1 :]]
        if len(closes) < 3:
            return self.cfg.iv_floor
        rets = [math.log(b / a) for a, b in zip(closes, closes[1:])]
        hv = statistics.stdev(rets) * math.sqrt(252)
        return max(hv * self.cfg.iv_premium, self.cfg.iv_floor)

    def _leg_price(self, sym: str, lg: OptionLeg, spot: float, as_of: date, iv: float) -> float:
        """Black-Scholes with a strike-based skew: strikes below spot get IV +
        put_skew_per_pct per 1% below, strikes above spot + call_skew_per_pct per 1% above,
        for calls and puts alike (put-call parity: same strike, same IV)."""
        cfg = self.cfg
        t = max((lg.expiry - as_of).days, 0) / 365
        if cfg.iv_term_mean is not None and t > 0:
            iv = _term_iv(iv, t, cfg.iv_term_mean, cfg.iv_term_kappa)
        below = max((spot - lg.strike) / spot * 100, 0.0)
        above = max((lg.strike - spot) / spot * 100, 0.0)
        # skew per 1% flattens with expiry: scale by sqrt(30 / days), as is common
        days = max((lg.expiry - as_of).days, 1)
        scale = math.sqrt(30 / max(days, 7)) if cfg.skew_term_scaling else 1.0
        leg_iv = iv + scale * (cfg.put_skew_per_pct * below + cfg.call_skew_per_pct * above) / 100
        return bs_price(
            spot, lg.strike, t, self._rate_now, max(leg_iv, 0.01), lg.right, cfg.div_yield
        )

    def _mid(self, sym: str, legs: tuple[OptionLeg, ...], spot: float, as_of: date) -> float:
        iv = self._iv(sym)
        total = 0.0
        for lg in legs:
            px = self._leg_price(sym, lg, spot, as_of, iv)
            total += px if lg.side is Side.BUY else -px
        if len(legs) == 2 and legs[0].right is legs[1].right:
            width = abs(legs[0].strike - legs[1].strike)  # a vertical is worth at most its width
            total = max(-width, min(width, total))
        return total

    def _half_spread(self, sym, legs, spot, as_of) -> float:
        """Half the bid-ask, per share. Single legs: % of the option price. Multi-leg orders
        trade as one package: % of the net mid, at least min_half_spread per leg (charging
        each deep-ITM leg separately would make a spread cost more than its width)."""
        cfg = self.cfg
        if len(legs) > 1:
            net = abs(self._mid(sym, legs, spot, as_of))
            return max(cfg.min_half_spread * len(legs), net * cfg.half_spread_pct / 100)
        px = self._leg_price(sym, legs[0], spot, as_of, self._iv(sym))
        return max(cfg.min_half_spread, px * cfg.half_spread_pct / 100)

    # -------------------------------------------------------------- state

    def _value(self, sym: str, as_of: date) -> float:
        """Signed mid per share: >= 0 for debit positions, <= 0 for credit positions."""
        pos = self.positions[sym]
        mid = self._mid(sym, pos.legs, self.history[sym][-1].close, as_of)
        return min(mid, 0.0) if pos.entry_price < 0 else max(mid, 0.0)

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
            if self._pending_rate is not None:
                self._rate_now = self._pending_rate  # yesterday's rate, known before the open
            r = self.rates_pct.get(d)
            self._pending_rate = r / 100 if r is not None else self._pending_rate
            for s, bar in today.items():
                # Fill at the open using only information known before it (no lookahead):
                # IV and ATR still reflect yesterday's close.
                self._execute_at_open(s, bar, d)
                self.history[s].append(bar)
                self.atrs[s] = self.atr[s].update(bar)
            self._update_regime()
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
                regime = self._regime()
                bullish = (pos.right is Right.CALL) == (pos.entry_price > 0)
                if (self.cfg.exit_on_regime_bull and not bullish and regime == "bull") or (
                    self.cfg.exit_on_regime_bear and bullish and regime == "bear"
                ):
                    self.pending_exits[s] = "regime_exit"
                    continue
                if pos.entry_price < 0:
                    reason = credit_exit_signal(pos, value, d, self.exits)
                else:
                    reason = exit_signal(
                        pos, value, today[s].close, self.atrs.get(s), d, self.exits
                    )
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
                    classify(order).max_loss,
                    d,
                    order.note,
                )
                entries_today += 1
            self.result.equity_curve.append((d, equity))
            prev_equity = equity
        return self.result

    def _regime(self) -> str | None:
        """'bull' / 'bear' for today (see _update_regime); None if no filter or history."""
        return self._regime_state

    def _update_regime(self) -> None:
        """Once per day after the close is known: benchmark vs its SMA, with hysteresis."""
        cfg = self.cfg
        if not cfg.regime_symbol:
            return
        h = self.history[cfg.regime_symbol]
        if len(h) < cfg.regime_sma:
            return
        sma = sum(b.close for b in h[-cfg.regime_sma :]) / cfg.regime_sma
        close, buf = h[-1].close, cfg.regime_buffer_pct / 100
        state = self._regime_state
        if state is None:
            state = "bull" if close >= sma else "bear"
        elif state == "bull" and close < sma * (1 - buf):
            state = "bear"
        elif state == "bear" and close >= sma * (1 + buf):
            state = "bull"
        if buf == 0:
            state = "bull" if close >= sma else "bear"
        self._regime_state = state

    def _signal(self, s: str, d: date, equity: float) -> OptionOrder | None:
        cfg, h = self.cfg, self.history[s]
        if s in cfg.untradable:
            return None
        atr = self.atrs.get(s)
        if cfg.signal_mode == "score_dip":
            score = self.scores.get(d)
            if s not in cfg.hedge_symbols or not atr or score is None:
                return None
            if score >= cfg.dip_threshold:
                return None
            if cfg.dip_requires_bull and self._regime() != "bull":
                return None
            return self._build_order(s, d, equity, Right.CALL, "score_dip", h[-1].close, atr)
        if cfg.dip_overlay and cfg.signal_mode == "breakout" and s in cfg.hedge_symbols and atr:
            score = self.scores.get(d)
            if score is not None and score < cfg.dip_threshold:
                risk = cfg.dip_risk_pct if cfg.dip_risk_pct is not None else cfg.risk_per_trade_pct
                return self._build_order(
                    s, d, equity, Right.CALL, "score_dip", h[-1].close, atr, risk
                )
        if cfg.signal_mode == "put_credit":
            if s not in cfg.hedge_symbols or not atr or self._regime() == "bear":
                return None
            return self._build_put_credit(s, d, equity, h[-1].close)
        if cfg.signal_mode == "index_trend":
            if s not in cfg.hedge_symbols or not atr or self._regime() == "bear":
                return None
            return self._build_order(s, d, equity, Right.CALL, "trend", h[-1].close, atr)
        if cfg.signal_mode == "index_hedge":
            if s not in cfg.hedge_symbols or not atr or self._regime() != "bear":
                return None
            return self._build_order(s, d, equity, Right.PUT, "hedge", h[-1].close, atr)
        if len(h) < max(cfg.breakout_lookback, cfg.trend_sma) + 1 or not atr:
            return None
        close = h[-1].close
        prior = h[-cfg.breakout_lookback - 1 : -1]
        sma = sum(b.close for b in h[-cfg.trend_sma :]) / cfg.trend_sma
        regime = self._regime()
        calls_ok, puts_ok, risk = cfg.allow_calls, cfg.allow_puts, None
        if cfg.score_tiers:
            score = self.scores.get(d)
            if score is None:
                return None
            tier = pick_tier(score, cfg.score_tiers)
            open_risk = sum(p.max_loss for p in self.positions.values()) + sum(
                p.max_loss for p in self.pending_entries.values()
            )
            if open_risk / equity * 100 + tier.risk_pct > tier.total_pct + 1e-9:
                return None
            calls_ok, puts_ok, risk = calls_ok and tier.calls, puts_ok and tier.puts, tier.risk_pct
        if cfg.signal_mode == "bear_setups":
            setup = self._bear_setup(s, h, d, sma, regime) if puts_ok else None
            if setup is None:
                return None
            right, note = Right.PUT, setup
        elif calls_ok and regime != "bear" and close > max(b.high for b in prior) and close > sma:
            right, note = Right.CALL, "bull"
        elif puts_ok and regime != "bull" and close < min(b.low for b in prior) and close < sma:
            right, note = Right.PUT, "bear"
        else:
            return None
        if not self._entry_filters_ok(s, d, close, sma, right):
            return None
        return self._build_order(s, d, equity, right, note, close, atr, risk)

    def _build_order(
        self, s, d, equity, right, note, close, atr, risk_pct: float | None = None
    ) -> OptionOrder | None:
        cfg = self.cfg
        risk_pct = cfg.risk_per_trade_pct if risk_pct is None else risk_pct
        if cfg.vol_target:
            mult = cfg.vol_target / max(self._iv(s), 1e-6)
            risk_pct *= min(max(mult, cfg.vol_target_floor), cfg.vol_target_cap)
        step = strike_step(close)
        expiry = expiry_after(d, cfg.target_dte)
        m = cfg.strike_moneyness
        k = round_strike(close * (m if right is Right.CALL else 2 - m), step)
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
            math.floor(equity * risk_pct / 100 / (limit * MULTIPLIER)),
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

    def _build_put_credit(self, s: str, d: date, equity: float, close: float) -> OptionOrder | None:
        cfg = self.cfg
        step = strike_step(close)
        expiry = expiry_after(d, cfg.target_dte)
        k_short = round_strike(close * (1 - cfg.credit_otm_pct / 100), step)
        k_long = round_strike(k_short - max(step, close * cfg.credit_width_pct / 100), step)
        if k_long >= k_short:
            return None
        legs = (
            OptionLeg(Right.PUT, k_short, expiry, Side.SELL, 1),
            OptionLeg(Right.PUT, k_long, expiry, Side.BUY, 1),
        )
        mid = self._mid(s, legs, close, d)  # negative: net credit
        half = self._half_spread(s, legs, close, d)
        credit = -(mid + half)  # expected credit after crossing the spread
        if credit <= 0.05:
            return None
        limit = round(-credit * (1 - cfg.entry_limit_buffer_pct / 100), 2)  # accept a bit less
        width = k_short - k_long
        loss_per_contract = (width + limit) * MULTIPLIER
        contracts = min(
            math.floor(equity * cfg.risk_per_trade_pct / 100 / loss_per_contract),
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
            for lg in legs
        )
        return OptionOrder(
            s, quoted, OptionAction.OPEN, OrderType.LIMIT, limit, d, note="put_credit"
        )

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
        px = self._leg_price(s, lg, spot, d, self._iv(s))
        h = max(self.cfg.min_half_spread, px * self.cfg.half_spread_pct / 100)
        return max(px - h, 0.0), px + h

    def _execute_at_open(self, s: str, bar: Bar, d: date) -> None:
        if s in self.pending_exits and s in self.positions:
            reason = self.pending_exits.pop(s)
            pos = self.positions.pop(s)
            mid = self._mid(s, pos.legs, bar.open, d)  # signed: negative for credit positions
            if pos.entry_price > 0:
                mid = max(mid, 0.0)
            else:
                mid = min(mid, 0.0)
            px = mid - self._half_spread(s, pos.legs, bar.open, d)  # we cross the spread
            if pos.entry_price > 0:
                px = max(px, 0.0)
            elif len(pos.legs) == 2:
                px = max(px, -abs(pos.legs[0].strike - pos.legs[1].strike))
            self.cash += px * MULTIPLIER * pos.contracts
            self.result.trades.append(
                OptionTrade(
                    s,
                    pos.right,
                    pos.entry_date,
                    d,
                    pos.entry_price,
                    px,
                    pos.contracts,
                    reason,
                    pos.setup,
                    pos.max_loss,
                )
            )
        p = self.pending_entries.pop(s, None)
        if p is None:
            return
        mid = self._mid(s, p.legs, bar.open, d)
        px = mid + self._half_spread(s, p.legs, bar.open, d)
        if px > p.limit or (p.limit > 0 and px <= 0):
            self.result.unfilled_entries += 1
            return
        cost = px * MULTIPLIER * p.contracts  # negative for a credit
        if px < 0:
            width = abs(p.legs[0].strike - p.legs[1].strike)
            max_loss = (width + px) * MULTIPLIER * p.contracts
        else:
            max_loss = cost
        if max_loss > self.cash or max_loss <= 0:
            self.result.unfilled_entries += 1
            return
        self.cash -= cost
        self.positions[s] = OptionPosition(
            s,
            p.right,
            p.legs[0].expiry,
            px,
            px,
            bar.open,
            p.contracts,
            max_loss,
            p.legs,
            d,
            p.setup,
        )

    def _settle_if_expired(self, s: str, d: date) -> None:
        pos = self.positions[s]
        if d < pos.expiry:
            return
        px = self._mid(s, pos.legs, self.history[s][-1].close, pos.expiry)
        px = min(px, 0.0) if pos.entry_price < 0 else max(px, 0.0)
        self.positions.pop(s)
        self.pending_exits.pop(s, None)
        self.cash += px * MULTIPLIER * pos.contracts
        self.result.trades.append(
            OptionTrade(
                s,
                pos.right,
                pos.entry_date,
                d,
                pos.entry_price,
                px,
                pos.contracts,
                "expiry",
                pos.setup,
                pos.max_loss,
            )
        )


def _short_reason(reason: str) -> str:
    return re.sub(r"[-+$]?\d[\d,]*\.?\d*%?", "N", reason)
