from datetime import date, timedelta

import pytest
from agentic_trader.sim.bootstrap import bootstrap_compare


def curve(daily, n=1000, start=date(2001, 1, 1)):
    eq, out = 1.0, []
    for i in range(n):
        out.append((start + timedelta(days=i), eq))
        eq *= 1 + daily(i)
    return out


def test_constant_returns_give_that_cagr_and_no_drawdown():
    res = bootstrap_compare({"flat": curve(lambda i: 0.0004)}, horizon_years=4, n_paths=200, seed=1)
    r = res["flat"]
    assert r["cagr_p50"] == pytest.approx(((1.0004) ** 252 - 1) * 100, rel=1e-6)
    assert r["dd_p50"] == pytest.approx(0.0)
    assert r["p_loss"] == 0.0


def test_paths_are_synchronised_across_strategies():
    a = curve(lambda i: 0.01 if i % 2 else -0.009)
    b = curve(lambda i: 2 * (0.01 if i % 2 else -0.009))
    res = bootstrap_compare({"a": a, "b": b}, horizon_years=2, n_paths=300, seed=3)
    # b is 2x a day by day, so its drawdowns are always deeper on the same paths
    assert res["b"]["dd_p50"] > res["a"]["dd_p50"]
    assert res["b"]["dd_p95"] >= res["a"]["dd_p95"]


def test_seed_makes_results_reproducible():
    c = {"x": curve(lambda i: 0.002 * ((i * 7919) % 11 - 5))}
    assert bootstrap_compare(c, 3, n_paths=100, seed=5) == bootstrap_compare(
        c, 3, n_paths=100, seed=5
    )
