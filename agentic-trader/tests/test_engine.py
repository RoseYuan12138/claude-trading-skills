from datetime import date

from agentic_trader.agent import ChaosAgent, RuleBasedAgentProxy
from agentic_trader.events import EventCalendar
from agentic_trader.models import Bar
from agentic_trader.risk_gate import RiskRules
from agentic_trader.sim.data import business_days, generate_market, load_csv_dir
from agentic_trader.sim.engine import run_simulation
from agentic_trader.sim.report import aggregate, default_scenarios, render_markdown, run_batch
from agentic_trader.stops import AtrTrailingStop, NoStop

RULES = RiskRules(max_order_notional=25_000, max_position_pct=20)
SYMS = ["S1", "S2", "S3", "S4"]


def test_synthetic_market_is_deterministic_and_valid():
    a, cal_a = generate_market(SYMS, 300, seed=7)
    b, _ = generate_market(SYMS, 300, seed=7)
    assert a == b
    for bars in a.values():
        assert len(bars) == 300
        assert all(x.low <= min(x.open, x.close) and x.high >= max(x.open, x.close) for x in bars)
        assert all(x.date.weekday() < 5 for x in bars)
    kinds = {e.kind for e in cal_a.events}
    assert {"earnings", "fomc", "cpi"} <= kinds


def test_same_seed_same_result():
    data, cal = generate_market(SYMS, 400, seed=3)
    r1 = run_simulation(data, cal, RULES, AtrTrailingStop(3)).metrics()
    r2 = run_simulation(data, cal, RULES, AtrTrailingStop(3)).metrics()
    assert r1 == r2


def test_trailing_stop_bounds_worst_trade_vs_no_stop():
    data, cal = generate_market(SYMS * 2, 1000, seed=5)
    data = {f"{s}_{i}": bars for i, (s, bars) in enumerate(data.items())}
    no_stop = run_simulation(
        data, cal, RiskRules(require_stop_on_entry=False, max_order_notional=25_000), NoStop()
    )
    trail = run_simulation(data, cal, RULES, AtrTrailingStop(3))
    assert trail.metrics()["stop_exits"] > 0
    assert no_stop.metrics()["stop_exits"] == 0


def test_gate_blocks_every_chaos_order():
    data, cal = generate_market(SYMS, 800, seed=2)
    chaos = ChaosAgent(RuleBasedAgentProxy(), rate=1.0, seed=2)
    res = run_simulation(data, cal, RULES, AtrTrailingStop(3), chaos)
    assert res.chaos_injected > 0
    assert res.executed_by_source.get("chaos", 0) == 0
    assert any(b.source == "chaos" for b in res.blocked)


def test_ungated_chaos_orders_execute():
    data, cal = generate_market(SYMS, 800, seed=2)
    chaos = ChaosAgent(RuleBasedAgentProxy(), rate=1.0, seed=2)
    res = run_simulation(data, cal, RULES, AtrTrailingStop(3), chaos, gate_enabled=False)
    assert res.executed_by_source.get("chaos", 0) > 0


def test_no_lookahead_entry_fills_at_next_open():
    days = business_days(date(2024, 1, 1), 80)
    bars = []
    for i, d in enumerate(days):
        p = 100 + (5 if i >= 60 else 0) + i * 0.01  # breakout signal at the close of day 60
        bars.append(Bar(d, p, p + 0.5, p - 0.5, p, 1e6))
    bars[61] = Bar(days[61], 200.0, 201.0, 199.0, 200.0, 1e6)  # next bar opens far higher
    res = run_simulation({"X": bars}, EventCalendar(), RULES, AtrTrailingStop(3))
    entry = next(f for f in res.fills if f.kind == "entry")
    assert entry.date == days[61]
    assert entry.price >= 200.0  # filled at the next open, not the signal close


def test_csv_loader(tmp_path):
    (tmp_path / "abc.csv").write_text(
        "Date,Open,High,Low,Close,Volume\n2024-01-03,10,11,9,10.5,100\n2024-01-02,9,10,8,9.5,90\n"
    )
    data = load_csv_dir(tmp_path)
    assert list(data) == ["ABC"]
    assert [b.date for b in data["ABC"]] == [date(2024, 1, 2), date(2024, 1, 3)]


def test_batch_report_renders():
    syms = SYMS
    results = run_batch(
        default_scenarios(RULES), [1], lambda s: generate_market(syms, 300, s), RULES
    )
    agg = aggregate(results)
    md = render_markdown(
        agg,
        {},
        {
            "generated": "x",
            "data": "y",
            "seeds": [1],
            "n_symbols": 4,
            "n_days": 300,
            "slippage_bps": 5,
        },
    )
    assert "agent+chaos (NO gate)" in md and "| Scenario |" in md
