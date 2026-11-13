"""Monthly option-selling strategies on an index ETF: the wheel, put-writing and buy-write.

* wheel     - sell a cash-secured put; if assigned, hold the shares and sell covered calls
              until they are called away, then sell puts again
* putwrite  - always sell a cash-secured put, settled in cash at expiry (like CBOE PUT)
* buywrite  - always hold the shares and sell a call each cycle (like CBOE BXM)
* hold      - buy and hold

Options are priced with Black-Scholes off an implied-vol index (VIX for SPY, VXN for QQQ)
plus a strike skew; strikes are chosen by delta. Positions are fractional (no contract
rounding), fully cash-secured (no leverage), and cash earns the T-bill rate. Prices should
be dividend-adjusted so held shares earn dividends. No early assignment.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

from ..models import Bar
from ..options import Right
from ..pricing import bs_delta, bs_price


@dataclass(frozen=True)
class WheelConfig:
    mode: str = "wheel"  # wheel / putwrite / buywrite / hold
    put_delta: float = -0.30
    call_delta: float = 0.30
    cycle_days: int = 21  # trading days per option (about one month)
    half_spread_pct: float = 1.0  # of the option price, paid when selling (and buying back)
    min_half_spread: float = 0.01
    put_skew: float = 0.75  # vol points per 1% below spot (30-day basis)
    call_skew: float = -0.25  # vol points per 1% above spot
    div_yield: float = 0.013
    iv_mult: float = 1.0  # ATM implied vol = index (VIX/VXN) x this; VIX sits above ATM IV


def _leg_iv(spot, k, t, iv, put_skew, call_skew):
    days = max(t * 365, 7)
    scale = math.sqrt(30 / days)
    below = max((spot - k) / spot * 100, 0.0)
    above = max((k - spot) / spot * 100, 0.0)
    return max(iv + scale * (put_skew * below + call_skew * above) / 100, 0.01)


def strike_for_delta(spot, t, rate, iv, target, right, put_skew=0.75, call_skew=-0.25):
    lo, hi = spot * 0.3, spot * 2.0
    for _ in range(80):
        k = (lo + hi) / 2
        d = bs_delta(spot, k, t, rate, _leg_iv(spot, k, t, iv, put_skew, call_skew), right)
        # delta falls (calls) / rises toward 0 (puts) as the strike rises / falls
        if right is Right.CALL:
            lo, hi = (k, hi) if d > target else (lo, k)
        else:
            lo, hi = (lo, k) if d < target else (k, hi)
    return (lo + hi) / 2


@dataclass
class WheelResult:
    curve: list[tuple[date, float]] = field(default_factory=list)
    assignments: int = 0
    called_away: int = 0
    cycles: int = 0


def wheel_curve(
    bars: list[Bar],
    iv_pct: dict[date, float],
    rates_pct: dict[date, float],
    start: date,
    end: date,
    cfg: WheelConfig,
) -> WheelResult:
    res = WheelResult()
    data = [b for b in bars if start <= b.date <= end]
    if not data:
        return res
    cash, shares = 1.0, 0.0
    short: tuple[str, float, int, float] | None = None  # (right, strike, expiry idx, qty)
    rate = 0.0
    last_iv = 20.0
    q = cfg.div_yield

    def price_short(i, s):
        right, k, exp_i, qty = short
        days_left = max(exp_i - i, 0) * 365 / 252
        t = days_left / 365
        iv = _leg_iv(s, k, t, last_iv / 100, cfg.put_skew, cfg.call_skew)
        r = Right.PUT if right == "put" else Right.CALL
        return bs_price(s, k, t, rate, iv, r, q)

    def open_short(i, s, right_name):
        nonlocal cash, short
        t = cfg.cycle_days / 252
        iv = last_iv / 100
        r = Right.PUT if right_name == "put" else Right.CALL
        target = cfg.put_delta if right_name == "put" else cfg.call_delta
        k = strike_for_delta(s, t, rate, iv, target, r, cfg.put_skew, cfg.call_skew)
        px = bs_price(s, k, t, rate, _leg_iv(s, k, t, iv, cfg.put_skew, cfg.call_skew), r, q)
        px = max(px - max(cfg.min_half_spread * s / 100, px * cfg.half_spread_pct / 100), 0.0)
        equity = cash + shares * s
        qty = shares if right_name == "call" else equity / k  # fully secured
        cash += px * qty
        short = (right_name, k, i + cfg.cycle_days, qty)
        res.cycles += 1

    for i, b in enumerate(data):
        s = b.close
        if i:
            cash *= 1 + rate / 252
        if b.date in iv_pct:
            last_iv = iv_pct[b.date] * cfg.iv_mult
        # expiry
        if short and i >= short[2]:
            right, k, _, qty = short
            if right == "put":
                if s < k:
                    if cfg.mode == "wheel":
                        cash -= k * qty
                        shares += qty
                        res.assignments += 1
                    else:
                        cash -= (k - s) * qty
            elif s > k:
                if cfg.mode == "wheel":
                    cash += k * qty
                    shares -= qty
                    res.called_away += 1
                else:
                    cash -= (s - k) * qty
            short = None
        if cfg.mode == "hold" and i == 0:
            shares, cash = 1.0 / s, 0.0
        if cfg.mode == "buywrite" and short is None:
            equity = cash + shares * s
            shares, cash = equity / s, 0.0
        if short is None and cfg.mode != "hold":
            if cfg.mode == "wheel":
                open_short(i, s, "call" if shares > 1e-12 else "put")
            elif cfg.mode == "putwrite":
                open_short(i, s, "put")
            else:
                open_short(i, s, "call")
        equity = cash + shares * s
        if short:
            equity -= price_short(i, s) * short[3]
        res.curve.append((b.date, equity))
        if b.date in rates_pct:
            rate = rates_pct[b.date] / 100
    return res
