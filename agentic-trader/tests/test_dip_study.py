from datetime import date, timedelta

import pytest
from agentic_trader.dip_study import DipParams, capitulation_days, forward_return, tranche_trade
from agentic_trader.models import Bar


def bars_from(closes, volumes=None, start=date(2020, 1, 1)):
    volumes = volumes or [1_000_000] * len(closes)
    out = []
    for i, (c, v) in enumerate(zip(closes, volumes)):
        o = closes[i - 1] if i else c
        out.append(Bar(start + timedelta(days=i), o, max(o, c) * 1.002, min(o, c) * 0.998, c, v))
    return out


def calm_then_crash(vol_mult=3.0, drop=0.08, n=260):
    closes = [100 * 1.0005**i * (1 + 0.001 * ((-1) ** i)) for i in range(n)]
    vols = [1_000_000] * n
    closes.append(closes[-1] * (1 - drop))
    vols.append(int(1_000_000 * vol_mult))
    closes += [closes[-1] * (1 + 0.002 * k) for k in range(1, 70)]
    vols += [1_000_000] * 69
    return bars_from(closes, vols)


def test_high_volume_big_drop_is_flagged():
    b = calm_then_crash()
    days = capitulation_days(b, DipParams(drop_sigma=2.0, vol_mult=2.0))
    assert days == [260]


def test_low_volume_drop_or_small_drop_is_not_flagged():
    assert capitulation_days(calm_then_crash(vol_mult=1.2), DipParams(vol_mult=2.0)) == []
    assert capitulation_days(calm_then_crash(drop=0.002), DipParams(drop_sigma=2.0)) == []


def test_trend_filter_requires_close_above_sma_before_the_drop():
    b = calm_then_crash()
    assert capitulation_days(b, DipParams(trend_sma=200)) == [260]
    falling = bars_from([300 - i for i in range(260)] + [30], [1_000_000] * 260 + [3_000_000])
    assert capitulation_days(falling, DipParams(trend_sma=200, min_drop_pct=1.0)) == []


def test_forward_return_enters_at_next_open():
    b = calm_then_crash()
    r = forward_return(b, 260, 20)
    assert r == pytest.approx(b[280].close / b[261].open - 1)
    assert forward_return(b, len(b) - 3, 20) is None


def test_tranche_time_exit_without_stop():
    b = calm_then_crash()
    t = tranche_trade(b, 260, hold=20, stop_atr=None, cost_bps=0)
    assert t.reason == "time" and t.ret == pytest.approx(b[280].close / b[261].open - 1)


def _flat(n, px, start):
    return [Bar(start + timedelta(days=k), px, px + 1, px - 1, px, 1_000_000) for k in range(n)]


def test_tranche_stop_fills_at_stop_or_gap_open():
    d0 = date(2020, 1, 1)
    base = _flat(30, 100.0, d0)  # ATR ~2
    # signal day 29; entry day 30 opens at 100; day 31 trades down through the stop
    intraday = (
        base
        + [
            Bar(d0 + timedelta(days=30), 100.0, 100.5, 99.5, 100.0, 1),
            Bar(d0 + timedelta(days=31), 99.0, 99.0, 90.0, 91.0, 1),
        ]
        + _flat(25, 91.0, d0 + timedelta(days=32))
    )
    t = tranche_trade(intraday, 29, hold=20, stop_atr=1.0, cost_bps=0, atr_period=14)
    assert t.reason == "stop" and t.exit_price == pytest.approx(t.stop)
    assert 97 < t.stop < 99
    gap = (
        base
        + [
            Bar(d0 + timedelta(days=30), 100.0, 100.5, 99.5, 100.0, 1),
            Bar(d0 + timedelta(days=31), 80.0, 81.0, 79.0, 80.0, 1),
        ]
        + _flat(25, 80.0, d0 + timedelta(days=32))
    )
    t2 = tranche_trade(gap, 29, hold=20, stop_atr=1.0, cost_bps=0, atr_period=14)
    assert t2.reason == "stop" and t2.exit_price == pytest.approx(80.0)  # gapped through
