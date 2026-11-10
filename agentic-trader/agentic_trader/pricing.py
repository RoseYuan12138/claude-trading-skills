"""Dependency-free Black-Scholes pricing (European, no dividends)."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .options import Right


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_price(S: float, K: float, T: float, r: float, sigma: float, right: Right) -> float:
    """Price per share. ``T`` in years; at or after expiry returns intrinsic value."""
    is_call = getattr(right, "value", right) == "call"
    if T <= 0 or sigma <= 0:
        intrinsic = S - K if is_call else K - S
        return max(intrinsic, 0.0)
    vol_t = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / vol_t
    d2 = d1 - vol_t
    disc = math.exp(-r * T)
    if is_call:
        return S * _norm_cdf(d1) - K * disc * _norm_cdf(d2)
    return K * disc * _norm_cdf(-d2) - S * _norm_cdf(-d1)


def bs_delta(S: float, K: float, T: float, r: float, sigma: float, right: Right) -> float:
    is_call = getattr(right, "value", right) == "call"
    if T <= 0 or sigma <= 0:
        if is_call:
            return 1.0 if S > K else 0.0
        return -1.0 if S < K else 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    return _norm_cdf(d1) if is_call else _norm_cdf(d1) - 1.0
