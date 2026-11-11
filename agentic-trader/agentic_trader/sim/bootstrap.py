"""Block bootstrap of daily strategy returns: a distribution instead of one history.

Blocks of consecutive trading days (default 63, about a quarter) keep volatility clusters
and trend persistence. All strategies are resampled with the same block draws on their
common dates, so differences between them are not draw luck.
"""

from __future__ import annotations

import math
import random
import statistics
from datetime import date


def _pct(values: list[float], q: float) -> float:
    v = sorted(values)
    k = (len(v) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return v[lo] if lo == hi else v[lo] + (v[hi] - v[lo]) * (k - lo)


def bootstrap_compare(
    curves: dict[str, list[tuple[date, float]]],
    horizon_years: float = 10.0,
    block_days: int = 63,
    n_paths: int = 2000,
    seed: int = 1,
) -> dict[str, dict[str, float]]:
    """Per strategy: CAGR percentiles (p5/p25/p50/p75/p95), max-drawdown percentiles,
    probability of losing money over the horizon and of a drawdown above 50% / 70%."""
    common = sorted(set.intersection(*(set(d for d, _ in c) for c in curves.values())))
    rets = {}
    for name, c in curves.items():
        m = dict(c)
        rets[name] = [m[b] / m[a] - 1 if m[a] > 0 else 0.0 for a, b in zip(common, common[1:])]
    n = len(common) - 1
    horizon = int(horizon_years * 252)
    if n < block_days:
        raise ValueError("history shorter than one block")
    rng = random.Random(seed)
    draws = []
    for _ in range(n_paths):
        starts, length = [], 0
        while length < horizon:
            starts.append(rng.randrange(0, n - block_days + 1))
            length += block_days
        draws.append(starts)

    out: dict[str, dict[str, float]] = {}
    for name, r in rets.items():
        cagrs, dds = [], []
        for starts in draws:
            eq, peak, dd, days = 1.0, 1.0, 0.0, 0
            for s0 in starts:
                for x in r[s0 : s0 + block_days]:
                    if days >= horizon:
                        break
                    eq *= 1 + x
                    peak = max(peak, eq)
                    dd = max(dd, 1 - eq / peak)
                    days += 1
            cagrs.append((max(eq, 1e-12) ** (252 / days) - 1) * 100)
            dds.append(dd * 100)
        out[name] = {
            **{f"cagr_p{int(q * 100)}": _pct(cagrs, q) for q in (0.05, 0.25, 0.5, 0.75, 0.95)},
            **{f"dd_p{int(q * 100)}": _pct(dds, q) for q in (0.5, 0.95)},
            "p_loss": sum(c < 0 for c in cagrs) / len(cagrs),
            "p_dd50": sum(d > 50 for d in dds) / len(dds),
            "p_dd70": sum(d > 70 for d in dds) / len(dds),
            "mean_cagr": statistics.mean(cagrs),
        }
    return out
