from datetime import date

import pytest
from agentic_trader.market_score import ScoreTier, market_scores, pick_tier
from agentic_trader.models import Bar
from agentic_trader.sim.data import business_days

DAYS = business_days(date(2024, 1, 1), 300)


def series(f, vol=1e6):
    return [Bar(d, f(i), f(i) * 1.005, f(i) * 0.995, f(i), vol) for i, d in enumerate(DAYS)]


def test_strong_uptrend_scores_high_and_downtrend_low():
    up = {"SPY": series(lambda i: 100 + i * 0.3), "A": series(lambda i: 50 + i * 0.1)}
    down = {"SPY": series(lambda i: 200 - i * 0.3), "A": series(lambda i: 80 - i * 0.1)}
    s_up = market_scores(up, "SPY")[DAYS[-1]]
    s_down = market_scores(down, "SPY")[DAYS[-1]]
    assert s_up.score > 80 and s_down.score <= 20  # smooth decline: realized vol stays "calm"
    assert s_up.components["trend"] == 100 and s_down.components["trend"] == 0
    assert s_up.components["breadth"] == 100 and s_down.components["breadth"] == 0


def test_vix_and_credit_components_are_used_when_given():
    data = {"SPY": series(lambda i: 100 + i * 0.3)}
    calm = series(lambda i: 12.0, vol=0)
    panic = series(lambda i: 40.0, vol=0)
    hyg_down = series(lambda i: 90 - i * 0.05)
    a = market_scores(data, "SPY", vix=calm)[DAYS[-1]]
    b = market_scores(data, "SPY", vix=panic, credit=hyg_down)[DAYS[-1]]
    assert a.components["volatility"] == 100
    assert b.components["volatility"] == 0 and b.components["credit"] == 0
    assert b.score < a.score


def test_falls_back_to_realized_vol_without_vix():
    s = market_scores({"SPY": series(lambda i: 100 + i * 0.3)}, "SPY")[DAYS[-1]]
    assert s.components["volatility"] == 100  # near-zero realized vol
    assert "credit" not in s.components


def test_no_lookahead_score_uses_data_up_to_that_day():
    base = {"SPY": series(lambda i: 100 + i * 0.3)}
    crashed = {"SPY": base["SPY"][:-1] + [Bar(DAYS[-1], 50, 51, 49, 50, 1e6)]}
    before = market_scores(base, "SPY")
    after = market_scores(crashed, "SPY")
    assert before[DAYS[-2]].score == pytest.approx(after[DAYS[-2]].score)
    assert after[DAYS[-1]].score < before[DAYS[-1]].score


def test_scores_need_200_days_of_history():
    s = market_scores({"SPY": series(lambda i: 100 + i)}, "SPY")
    assert DAYS[150] not in s and DAYS[250] in s


def test_pick_tier():
    tiers = (
        ScoreTier(70, calls=True, puts=False, risk_pct=5, total_pct=15),
        ScoreTier(50, calls=True, puts=False, risk_pct=2, total_pct=10),
        ScoreTier(30, calls=False, puts=False, risk_pct=0, total_pct=0),
        ScoreTier(0, calls=False, puts=True, risk_pct=2, total_pct=6),
    )
    assert pick_tier(85, tiers).risk_pct == 5
    assert pick_tier(55, tiers).risk_pct == 2 and pick_tier(55, tiers).calls
    assert not pick_tier(40, tiers).calls and not pick_tier(40, tiers).puts
    assert pick_tier(10, tiers).puts


def test_fetch_to_rows_dividend_adjustment():
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "fetch_ohlcv", Path(__file__).resolve().parents[1] / "scripts" / "fetch_ohlcv.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    payload = {
        "chart": {
            "result": [
                {
                    "meta": {"gmtoffset": 0},
                    "timestamp": [1700000000, 1700086400],
                    "indicators": {
                        "quote": [
                            {
                                "open": [10, 10],
                                "high": [11, 11],
                                "low": [9, 9],
                                "close": [10, 10],
                                "volume": [1, 1],
                            }
                        ],
                        "adjclose": [{"adjclose": [9.5, 10]}],
                    },
                }
            ]
        }
    }
    raw = mod.to_rows(payload)
    adj = mod.to_rows(payload, adjusted=True)
    assert raw[0][4] == 10 and adj[0][4] == 9.5
    assert adj[0][1] == pytest.approx(9.5) and adj[0][2] == pytest.approx(10.45)
