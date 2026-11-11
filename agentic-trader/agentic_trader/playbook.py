"""Today's action for the ITM trend-call strategy (the most robust aggressive setup found).

Rule (see docs/AGGRESSIVE_OPTIONS_STRATEGY.md): while SPY and QQQ both close above their
200-day SMAs,
hold a QQQ call about 15% in the money with about 270 days to expiry (a LEAPS-style
call), sized so the premium is a fixed share of the account; roll it when 60 days are
left; sell and stay in cash when either closes below its SMA. The premium is the most the
position can lose.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from .models import Bar
from .options import MULTIPLIER, Right
from .pricing import bs_delta, bs_price
from .sim.options_engine import _term_iv, expiry_after, round_strike, strike_step


def monthly_expiry_on_or_after(d: date) -> date:
    """Third Friday (standard monthly option expiry) on or after ``d``."""
    from datetime import timedelta

    year, month = d.year, d.month
    while True:
        first = date(year, month, 1)
        third_friday = first + timedelta(days=(4 - first.weekday()) % 7 + 14)
        if third_friday >= d:
            return third_friday
        month += 1
        if month == 13:
            year, month = year + 1, 1


@dataclass(frozen=True)
class ItmTrendParams:
    moneyness: float = 0.85  # strike = close x moneyness (0.85 = 15% in the money)
    target_dte: int = 270
    roll_dte: int = 60
    regime_sma: int = 200
    require_qqq_trend: bool = True  # QQQ must also be above its own SMA (needs qqq_bars)
    premium_pct: float = 30.0  # share of the account paid in premium (= max loss)
    put_skew_per_pct: float = 0.75  # strike skew used for the price estimate (30-day basis)
    div_yield: float = 0.007
    iv_term_mean: float | None = 0.24  # long-dated IV mean-reverts toward this
    iv_term_kappa: float = 3.0
    # Small accounts: try these moneyness levels in order (deepest ITM first) and buy the
    # first strike of which one contract, plus fill_buffer_pct, fits the premium budget.
    # Empty = use ``moneyness`` only.
    moneyness_ladder: tuple[float, ...] = ()
    fill_buffer_pct: float = 0.5  # half the bid-ask assumed when checking what fits


@dataclass(frozen=True)
class OpenCall:
    strike: float
    expiry: date
    contracts: int


@dataclass(frozen=True)
class Ticket:
    action: str  # BUY / HOLD / ROLL / SELL / CASH
    regime_close: float
    regime_sma: float
    qqq_close: float = 0.0
    qqq_sma: float = 0.0
    strike: float = 0.0
    expiry: date | None = None
    est_price: float = 0.0  # per share
    contracts: int = 0
    premium: float = 0.0  # dollars
    delta: float = 0.0
    exposure: float = 0.0  # QQQ dollar exposure / account equity
    note: str = ""


def _estimate(qqq: float, strike: float, expiry: date, as_of: date, iv: float, rate: float, p):
    days = max((expiry - as_of).days, 1)
    t = days / 365
    if p.iv_term_mean is not None:
        iv = _term_iv(iv, t, p.iv_term_mean, p.iv_term_kappa)
    below = max((qqq - strike) / qqq * 100, 0.0)
    leg_iv = iv + math.sqrt(30 / max(days, 7)) * p.put_skew_per_pct * below / 100
    price = bs_price(qqq, strike, t, rate, leg_iv, Right.CALL, p.div_yield)
    delta = bs_delta(qqq, strike, t, rate, leg_iv, Right.CALL)
    return price, delta


def itm_trend_ticket(
    spy_bars: list[Bar],
    qqq_close: float,
    as_of: date,
    equity: float,
    iv: float,
    rate: float,
    position: OpenCall | None = None,
    params: ItmTrendParams | None = None,
    qqq_bars: list[Bar] | None = None,
) -> Ticket:
    """Decide today's action. ``iv`` and ``rate`` are annual decimals (VXN 22 -> 0.22).

    With ``params.require_qqq_trend`` (the default) ``qqq_bars`` must be given and QQQ must
    also close above its own SMA."""
    p = params or ItmTrendParams()
    closes = [b.close for b in spy_bars if b.date <= as_of]
    if len(closes) < p.regime_sma:
        raise ValueError(f"need {p.regime_sma} SPY closes, got {len(closes)}")
    sma = sum(closes[-p.regime_sma :]) / p.regime_sma
    bull = closes[-1] >= sma
    why = "SPY below its SMA"
    q_close = q_sma = 0.0
    if p.require_qqq_trend:
        if not qqq_bars:
            raise ValueError("require_qqq_trend needs qqq_bars")
        qc = [b.close for b in qqq_bars if b.date <= as_of]
        if len(qc) < p.regime_sma:
            raise ValueError(f"need {p.regime_sma} QQQ closes, got {len(qc)}")
        q_close, q_sma = qc[-1], sum(qc[-p.regime_sma :]) / p.regime_sma
        if q_close < q_sma:
            bull = False
            why = "QQQ below its SMA" if closes[-1] >= sma else "SPY and QQQ below their SMAs"
    base = dict(regime_close=closes[-1], regime_sma=sma, qqq_close=q_close, qqq_sma=q_sma)

    if not bull:
        if position:
            return Ticket("SELL", **base, contracts=position.contracts, note=why)
        return Ticket("CASH", **base, note=f"{why}: stay in cash")

    if position and (position.expiry - as_of).days > p.roll_dte:
        price, delta = _estimate(qqq_close, position.strike, position.expiry, as_of, iv, rate, p)
        exposure = delta * MULTIPLIER * position.contracts * qqq_close / equity
        return Ticket(
            "HOLD",
            **base,
            strike=position.strike,
            expiry=position.expiry,
            est_price=price,
            contracts=position.contracts,
            premium=price * MULTIPLIER * position.contracts,
            delta=delta,
            exposure=exposure,
            note=f"{(position.expiry - as_of).days} days left; roll at {p.roll_dte}",
        )

    step = strike_step(qqq_close)
    expiry = monthly_expiry_on_or_after(expiry_after(as_of, p.target_dte))
    budget = equity * p.premium_pct / 100
    for m in p.moneyness_ladder or (p.moneyness,):
        strike = round_strike(qqq_close * m, step)
        price, delta = _estimate(qqq_close, strike, expiry, as_of, iv, rate, p)
        if p.moneyness_ladder:
            ask = price * (1 + p.fill_buffer_pct / 100) * MULTIPLIER
            contracts = math.floor(budget / ask)
        else:
            contracts = math.floor(budget / (price * MULTIPLIER))
        if contracts:
            break
    action = "ROLL" if position else "BUY"
    note = (
        ""
        if contracts
        else (
            f"account too small: one contract costs ${price * MULTIPLIER:,.0f}, budget "
            f"${equity * p.premium_pct / 100:,.0f}"
        )
    )
    return Ticket(
        action,
        **base,
        strike=strike,
        expiry=expiry,
        est_price=price,
        contracts=contracts,
        premium=price * MULTIPLIER * contracts,
        delta=delta,
        exposure=delta * MULTIPLIER * contracts * qqq_close / equity,
        note=note,
    )
