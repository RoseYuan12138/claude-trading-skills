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
    regime_also: list[list[Bar]] | None = None,
) -> list[tuple[date, float]]:
    """Equity curve. ``regime=None`` means always invested (buy & hold). Every series in
    ``regime_also`` must also be above its own SMA for the asset to be held."""
    closes = {b.date: b.close for b in asset}
    dates = [b.date for b in asset if start <= b.date <= end]
    rc = {}
    if regime is not None:
        rc = _above_sma(regime, sma)
        for extra in regime_also or []:
            other = _above_sma(extra, sma)
            rc = {d: ok and other.get(d, False) for d, ok in rc.items()}
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


def _above_sma(bars: list[Bar], sma: int) -> dict[date, bool]:
    closes = [b.close for b in bars]
    return {
        b.date: closes[i] >= sum(closes[i - sma + 1 : i + 1]) / sma
        for i, b in enumerate(bars)
        if i >= sma - 1
    }


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


def dynamic_leverage_curve(
    index: list[Bar],
    regime: list[Bar] | None,
    vol_pct: dict[date, float],
    start: date,
    end: date,
    target_vol: float = 0.25,
    max_leverage: float = 3.0,
    sma: int = 200,
    buffer_pct: float = 0.0,
    rates_pct: dict[date, float] | None = None,
    expense_pct_per_x: float = 0.5,
    trade_cost_bps: float = 5.0,
    initial: float = 1.0,
) -> list[tuple[date, float]]:
    """Daily leverage = clip(target_vol / implied vol, 0, max) while the regime is bullish.

    Approximates a mix of QQQ / QLD / TQQQ and cash. Everything observed on day d-1 sets the
    exposure for day d: borrowing (L - 1) x short rate, an expense of ``expense_pct_per_x`` per
    unit of leverage a year, and ``trade_cost_bps`` on each change in leverage.
    """
    closes = [b.close for b in index]
    dates = [b.date for b in index]
    regime_ok: dict[date, bool] = {}
    if regime is not None:
        rc = [b.close for b in regime]
        state = None
        for i, b in enumerate(regime):
            if i < sma - 1:
                continue
            m = sum(rc[i - sma + 1 : i + 1]) / sma
            c, buf = rc[i], buffer_pct / 100
            if state is None or buf == 0:
                state = c >= m
            elif state and c < m * (1 - buf):
                state = False
            elif not state and c >= m * (1 + buf):
                state = True
            regime_ok[b.date] = state
    equity, lev, rate = initial, 0.0, 0.0
    curve = []
    for i, d in enumerate(dates):
        if d < start or d > end:
            if rates_pct and d in rates_pct:
                rate = rates_pct[d] / 100
            continue
        prev = dates[i - 1] if i else None
        if prev is not None and prev >= start:
            r = closes[i] / closes[i - 1] - 1
            equity *= max(
                1 + lev * r - max(lev - 1, 0) * rate / 252 - lev * expense_pct_per_x / 100 / 252,
                0.0,
            )
        curve.append((d, equity))
        # decide tomorrow's leverage from today's information
        if rates_pct and d in rates_pct:
            rate = rates_pct[d] / 100
        ok = True if regime is None else regime_ok.get(d, False)
        v = vol_pct.get(d)
        new = 0.0
        if ok and v:
            new = min(max(target_vol / (v / 100), 0.0), max_leverage)
        equity *= 1 - abs(new - lev) * trade_cost_bps / 10_000
        lev = new
    return curve
