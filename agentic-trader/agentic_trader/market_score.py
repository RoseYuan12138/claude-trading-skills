"""Market score (0-100) from trend, breadth, momentum, drawdown, volatility and credit.

Weights and scales are fixed in advance (equal-weight mean of the available components)
rather than fitted, so a backtest of a score-driven strategy is not tuned to its own data.
Each day's score uses only data up to and including that day's close.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import date

from .models import Bar


@dataclass(frozen=True)
class MarketScore:
    score: float
    components: dict[str, float]


@dataclass(frozen=True)
class ScoreTier:
    min_score: float
    calls: bool
    puts: bool
    risk_pct: float  # premium per trade, % of equity
    total_pct: float  # cap on premium at risk across open positions, % of equity


def _clip(x: float) -> float:
    return max(0.0, min(100.0, x))


def _scale(x: float, zero_at: float, hundred_at: float) -> float:
    return _clip((x - zero_at) / (hundred_at - zero_at) * 100)


def market_scores(
    data: dict[str, list[Bar]],
    benchmark: str = "SPY",
    vix: list[Bar] | None = None,
    credit: list[Bar] | None = None,
    breadth_symbols: list[str] | None = None,
) -> dict[date, MarketScore]:
    bench = data[benchmark]
    closes = [b.close for b in bench]
    vix_by = {b.date: b.close for b in vix} if vix else {}
    credit_bars = credit or []
    credit_idx = {b.date: i for i, b in enumerate(credit_bars)}
    names = breadth_symbols or [s for s in data if s != benchmark]
    idx = {s: {b.date: i for i, b in enumerate(data[s])} for s in names}

    out: dict[date, MarketScore] = {}
    for i in range(199, len(bench)):
        d = bench[i].date
        c = closes[i]
        sma50 = sum(closes[i - 49 : i + 1]) / 50
        sma200 = sum(closes[i - 199 : i + 1]) / 200
        comp: dict[str, float] = {
            "trend": (50.0 if c > sma50 else 0.0) + (50.0 if c > sma200 else 0.0)
        }

        above = total = 0
        for s in names:
            j = idx[s].get(d)
            bars = data[s]
            if j is None or j < 49:
                continue
            total += 1
            above += bars[j].close > sum(b.close for b in bars[j - 49 : j + 1]) / 50
        if total:
            comp["breadth"] = above / total * 100

        comp["momentum"] = _scale((c / closes[i - 20] - 1) * 100, -5.0, 5.0)
        high = max(closes[max(0, i - 251) : i + 1])
        comp["drawdown"] = _scale((c / high - 1) * 100, -15.0, 0.0)

        v = vix_by.get(d)
        if v is not None:
            comp["volatility"] = _scale(v, 35.0, 15.0)
        else:
            rets = [math.log(b / a) for a, b in zip(closes[i - 20 : i], closes[i - 19 : i + 1])]
            rv = statistics.pstdev(rets) * math.sqrt(252) * 100
            comp["volatility"] = _scale(rv, 35.0, 10.0)

        k = credit_idx.get(d)
        if k is not None and k >= 49:
            sma = sum(b.close for b in credit_bars[k - 49 : k + 1]) / 50
            comp["credit"] = 100.0 if credit_bars[k].close > sma else 0.0

        out[d] = MarketScore(statistics.mean(comp.values()), comp)
    return out


def pick_tier(score: float, tiers: tuple[ScoreTier, ...]) -> ScoreTier:
    """Highest tier whose ``min_score`` the score reaches (tiers in any order)."""
    for tier in sorted(tiers, key=lambda t: -t.min_score):
        if score >= tier.min_score:
            return tier
    return min(tiers, key=lambda t: t.min_score)
