"""Switch between strategies by interest-rate regime.

The regime on each date comes from the 3-month T-bill (^IRX): "hike" when it is at least
``threshold`` points above its level ``lookback`` trading days earlier, "cut" when at least
that much below, else "flat". The 3-month bill moves ahead of the Fed, so this is a
market-based, real-time proxy (no knowledge of later Fed decisions).

``mix_by_regime`` holds, each day, the strategy mapped to the previous day's regime, using
that strategy's daily return. This treats each strategy as a fund you can switch into at
the close (an option-selling strategy is assumed closed at its model mark), and charges
``cost_bps`` per switch.
"""

from __future__ import annotations

from datetime import date


def rate_regimes(
    rates_pct: dict[date, float], lookback: int = 126, threshold: float = 0.25
) -> dict[date, str | None]:
    ds = sorted(rates_pct)
    out: dict[date, str | None] = {}
    for i, d in enumerate(ds):
        if i < lookback:
            out[d] = None
            continue
        chg = rates_pct[d] - rates_pct[ds[i - lookback]]
        out[d] = "hike" if chg >= threshold else "cut" if chg <= -threshold else "flat"
    return out


def mix_by_regime(
    curves: dict[str, list[tuple[date, float]]],
    regimes: dict[date, str | None],
    mapping: dict[str, str],
    default: str,
    cost_bps: float = 5.0,
) -> list[tuple[date, float]]:
    common = sorted(set.intersection(*(set(d for d, _ in c) for c in curves.values())))
    eqs = {k: dict(c) for k, c in curves.items()}
    reg_dates = sorted(regimes)
    out, equity, held = [], 1.0, None
    j, last_reg = 0, None
    for i, d in enumerate(common):
        if i:
            prev = common[i - 1]
            while j < len(reg_dates) and reg_dates[j] <= prev:
                last_reg = regimes[reg_dates[j]]
                j += 1
            want = mapping.get(last_reg, default) if last_reg else default
            if held is not None and want != held:
                equity *= 1 - cost_bps / 10_000
            held = want
            equity *= eqs[want][d] / eqs[want][prev]
        out.append((d, equity))
    return out
