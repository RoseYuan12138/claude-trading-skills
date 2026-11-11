"""Regime rotation: hold an asset while a benchmark is above its SMA, else cash.

Used to benchmark aggressive option strategies against simply holding leveraged ETFs
(QLD = 2x QQQ, TQQQ = 3x QQQ) with a trend filter. The signal observed at the close of
day d-1 sets the position for day d's close-to-close return, so there is no lookahead;
each switch costs ``switch_cost_bps``.
"""

from __future__ import annotations

from datetime import date

from ..models import Bar


def rotation_curve(
    asset: list[Bar],
    regime: list[Bar] | None,
    start: date,
    end: date,
    sma: int = 50,
    switch_cost_bps: float = 10.0,
    cash_rate: float = 0.0,
    initial: float = 1.0,
) -> list[tuple[date, float]]:
    """Equity curve. ``regime=None`` means always invested (buy & hold)."""
    closes = {b.date: b.close for b in asset}
    dates = [b.date for b in asset if start <= b.date <= end]
    rc = {}
    if regime is not None:
        rcl = [b.close for b in regime]
        for i, b in enumerate(regime):
            if i >= sma - 1:
                rc[b.date] = rcl[i] >= sum(rcl[i - sma + 1 : i + 1]) / sma
    asset_dates = [b.date for b in asset]
    prev_of = {d: asset_dates[i - 1] for i, d in enumerate(asset_dates) if i > 0}

    equity, invested = initial, None
    curve = []
    for d in dates:
        p = prev_of.get(d)
        if p is None:
            curve.append((d, equity))
            continue
        want = True if regime is None else rc.get(p, False)
        if invested is not None and want != invested:
            equity *= 1 - switch_cost_bps / 10_000
        if want:
            equity *= closes[d] / closes[p]
        else:
            equity *= 1 + cash_rate / 252
        invested = want
        curve.append((d, equity))
    return curve


def synthetic_leveraged(
    bars: list[Bar],
    leverage: float,
    rates_pct: dict[date, float] | None = None,
    expense_pct: float = 0.95,
) -> list[Bar]:
    """Daily-rebalanced leveraged series (like QLD/TQQQ) built from an index ETF.

    Daily return = L x index return - (L - 1) x short rate - expense ratio (both annual,
    accrued per trading day). ``rates_pct`` maps dates to the annual short rate in percent
    (e.g. ^IRX); the last known rate carries forward.
    """
    out: list[Bar] = []
    level, rate = 100.0, 0.0
    for i, b in enumerate(bars):
        if rates_pct and b.date in rates_pct:
            rate = rates_pct[b.date] / 100
        if i:
            r = b.close / bars[i - 1].close - 1
            level *= max(
                1 + leverage * r - (leverage - 1) * rate / 252 - expense_pct / 100 / 252, 0.0
            )
        out.append(Bar(b.date, level, level, level, level, b.volume))
    return out
