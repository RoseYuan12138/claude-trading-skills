from datetime import date

from agentic_trader.events import Event, EventCalendar
from agentic_trader.models import Bar
from agentic_trader.risk_gate import RiskRules
from agentic_trader.sim.data import business_days, infer_earnings_calendar
from agentic_trader.sim.engine import SimConfig, run_simulation
from agentic_trader.stops import AtrTrailingStop

RULES = RiskRules(max_order_notional=25_000, max_position_pct=20)
DAYS = business_days(date(2024, 1, 1), 80)
SIGNAL = 60  # X breaks out at the close of this bar


def _x(breakout_volume=1e6):
    bars = []
    for i, d in enumerate(DAYS):
        p = 100 + (5 if i >= SIGNAL else 0) + i * 0.01
        vol = breakout_volume if i == SIGNAL else 1e6
        bars.append(Bar(d, p, p + 0.5, p - 0.5, p, vol))
    return bars


def _spy(rising: bool):
    out = []
    for i, d in enumerate(DAYS):
        p = 400 + (i * 0.3 if rising else -i * 0.3)
        out.append(Bar(d, p, p + 0.2, p - 0.2, p, 5e7))
    return out


def _bought_x(data, cal=None, **cfg):
    cal = cal or EventCalendar()
    res = run_simulation(data, cal, RULES, AtrTrailingStop(3), config=SimConfig(**cfg))
    return any(f.symbol == "X" and f.kind == "entry" for f in res.fills)


def test_regime_filter_blocks_entries_when_benchmark_below_sma():
    falling = {"X": _x(), "SPY": _spy(rising=False)}
    rising = {"X": _x(), "SPY": _spy(rising=True)}
    assert _bought_x(falling)  # no filter
    assert not _bought_x(falling, regime_symbol="SPY", regime_sma=50)
    assert _bought_x(rising, regime_symbol="SPY", regime_sma=50)


def test_regime_filter_allows_entries_until_enough_history():
    data = {"X": _x(), "SPY": _spy(rising=False)}
    assert _bought_x(data, regime_symbol="SPY", regime_sma=500)


def test_earnings_blackout_skips_entry_before_report():
    cal = EventCalendar([Event(DAYS[SIGNAL + 3], "earnings", "X", 3)])
    data = {"X": _x()}
    assert _bought_x(data, cal)
    assert not _bought_x(data, cal, earnings_blackout_days=7)
    assert _bought_x(data, cal, earnings_blackout_days=2)  # report is 3 trading days out


def test_volume_confirmation():
    assert not _bought_x({"X": _x(breakout_volume=1e6)}, volume_confirm_mult=1.5)
    assert _bought_x({"X": _x(breakout_volume=3e6)}, volume_confirm_mult=1.5)


def test_infer_earnings_calendar_finds_quarterly_spikes_and_skips_etfs():
    days = business_days(date(2023, 1, 2), 300)
    spikes = {40, 41, 103, 166, 229}  # 41: second day of the same report
    bars = [
        Bar(d, 10.5, 11, 10, 10.5, (8e6 if i == 41 else 9e6) if i in spikes else 1e6)
        if i in spikes
        else Bar(d, 10, 10.2, 9.8, 10, 1e6)
        for i, d in enumerate(days)
    ]
    quiet = [Bar(d, 10, 10.2, 9.8, 10, 1e6) for d in days]
    cal = infer_earnings_calendar({"ABC": bars, "SPY": bars, "Q1": quiet, "Q2": quiet})
    got = [e.date for e in cal.events]
    assert got == [days[i] for i in (40, 103, 166, 229)]
    assert all(e.symbol == "ABC" and e.kind == "earnings" for e in cal.events)


def test_infer_earnings_drops_market_wide_spikes():
    days = business_days(date(2023, 1, 2), 120)
    crash = 70

    def series():
        return [
            Bar(d, 9.0, 9.2, 8.8, 9.0, 5e6) if i == crash else Bar(d, 10, 10.2, 9.8, 10, 1e6)
            for i, d in enumerate(days)
        ]

    cal = infer_earnings_calendar({s: series() for s in ("A", "B", "C", "D")})
    assert cal.events == []


def test_untradable_benchmark_is_never_bought():
    data = {"SPY": _x()}  # SPY itself breaks out
    res = run_simulation(
        data, EventCalendar(), RULES, AtrTrailingStop(3), config=SimConfig(untradable=("SPY",))
    )
    assert not res.fills
