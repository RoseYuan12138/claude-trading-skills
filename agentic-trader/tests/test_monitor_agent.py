from datetime import date, timedelta

from agentic_trader.agent import AgentContext, ChaosAgent, RuleBasedAgentProxy
from agentic_trader.events import Event, EventCalendar
from agentic_trader.models import AccountState, Bar, PositionSnapshot, Purpose
from agentic_trader.monitor import Monitor, MonitorConfig, Trigger

D0 = date(2024, 3, 1)  # Friday


def _hist(n=25, last_open=100.0, last_vol=1e6):
    bars = [
        Bar(D0 - timedelta(days=n - i), 100, 101, 99, 100, 1e6) for i in range(1, n)
    ]  # ends the day before D0
    bars.append(Bar(D0, last_open, last_open + 1, last_open - 1, last_open, last_vol))
    return bars


def _pos(last=100.0, avg=95.0, stop=90.0, qty=10):
    return PositionSnapshot(qty=qty, avg_price=avg, last_price=last, stop_price=stop)


def _kinds(triggers):
    return {(t.kind, t.symbol) for t in triggers}


def test_gap_and_volume_spike_detected_for_held_symbol():
    m = Monitor()
    trig = m.scan(
        D0, {"A": _hist(last_open=94, last_vol=5e6)}, {"A": 2}, {"A": _pos()}, EventCalendar()
    )
    assert {("gap", "A"), ("volume_spike", "A")} <= _kinds(trig)
    gap = next(t for t in trig if t.kind == "gap")
    assert gap.value < 0


def test_earnings_over_weekend_is_seen_on_friday():
    cal = EventCalendar([Event(D0 + timedelta(days=3), "earnings", "A", 3)])
    trig = Monitor().scan(D0, {"A": _hist()}, {"A": 2}, {"A": _pos()}, cal)
    assert ("event_ahead", "A") in _kinds(trig)


def test_earnings_for_unheld_symbol_ignored_and_macro_needs_positions():
    cal = EventCalendar(
        [
            Event(D0 + timedelta(days=1), "earnings", "B", 3),
            Event(D0 + timedelta(days=1), "fomc", None, 3),
        ]
    )
    assert Monitor().scan(D0, {}, {}, {}, cal) == []
    trig = Monitor().scan(D0, {"A": _hist()}, {"A": 2}, {"A": _pos()}, cal)
    assert _kinds(trig) == {("event_ahead", None)}


def test_unprotected_and_stop_proximity_and_drawdown():
    positions = {"A": _pos(stop=None), "B": _pos(last=100, stop=99.5)}
    trig = Monitor().scan(D0, {}, {"A": 2, "B": 2}, positions, EventCalendar(), drawdown_pct=9)
    assert {("unprotected", "A"), ("stop_proximity", "B"), ("drawdown", None)} <= _kinds(trig)


def test_should_wake_filters_severity_and_applies_cooldown():
    m = Monitor(MonitorConfig(cooldown_days=3))
    trig = [Trigger("stop_proximity", "A", 1, ""), Trigger("gap", "A", 3, "")]
    assert [t.kind for t in m.should_wake(D0, trig)] == ["gap"]
    assert m.should_wake(D0 + timedelta(days=1), trig) == []
    assert len(m.should_wake(D0 + timedelta(days=3), trig)) == 1


def _ctx(triggers, positions, equity=100_000.0):
    state = AccountState(equity=equity, cash=equity, day_start_equity=equity, positions=positions)
    prices = {s: p.last_price for s, p in positions.items()} or {"A": 100.0}
    return AgentContext(D0, triggers, state, {s: 2.0 for s in prices}, prices, EventCalendar())


def test_proxy_tightens_winner_and_exits_loser_before_earnings():
    positions = {"W": _pos(last=110, avg=100, stop=100), "L": _pos(last=95, avg=100, stop=90)}
    trig = [Trigger("event_ahead", "W", 3, "earnings"), Trigger("event_ahead", "L", 3, "earnings")]
    d = RuleBasedAgentProxy().decide(_ctx(trig, positions))
    by_sym = {i.symbol: i for i in d.intents}
    assert by_sym["W"].purpose is Purpose.STOP_UPDATE and by_sym["W"].stop_price == 108.0
    assert by_sym["L"].purpose is Purpose.EXIT


def test_proxy_never_proposes_looser_stop():
    positions = {"W": _pos(last=110, avg=100, stop=109)}
    d = RuleBasedAgentProxy().decide(_ctx([Trigger("event_ahead", None, 2, "fomc")], positions))
    assert d.intents == []


def test_proxy_halts_on_drawdown():
    d = RuleBasedAgentProxy().decide(_ctx([Trigger("drawdown", None, 3, "dd", 9)], {}))
    assert d.halt_days > 0


def test_chaos_agent_injects_bad_orders():
    positions = {"W": _pos(last=110, avg=100, stop=100)}
    chaos = ChaosAgent(RuleBasedAgentProxy(), rate=1.0, seed=1)
    bad = [i for _ in range(10) for i in chaos.decide(_ctx([], positions)).intents]
    assert chaos.injected == 10
    assert all(i.source == "chaos" for i in bad)
    assert any(i.purpose is Purpose.ENTRY and i.stop_price is None for i in bad) or any(
        i.purpose is Purpose.STOP_UPDATE and i.stop_price < 100 for i in bad
    )


def test_drawdown_alerts_once_per_episode():
    m = Monitor(MonitorConfig(drawdown_pct=8))
    scan = lambda dd: _kinds(m.scan(D0, {}, {}, {}, EventCalendar(), drawdown_pct=dd))  # noqa: E731
    assert ("drawdown", None) in scan(9)
    assert ("drawdown", None) not in scan(12)  # still in the same episode
    assert ("drawdown", None) not in scan(5)  # partial recovery does not re-arm
    scan(3)  # recovered below half the threshold -> re-armed
    assert ("drawdown", None) in scan(8.5)
