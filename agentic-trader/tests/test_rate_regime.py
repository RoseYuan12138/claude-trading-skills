from datetime import date, timedelta

import pytest
from agentic_trader.sim.rate_regime import mix_by_regime, rate_regimes


def days(n, start=date(2020, 1, 1)):
    return [start + timedelta(days=i) for i in range(n)]


def test_rate_regimes_from_t_bill_changes():
    d = days(10)
    rates = dict(zip(d, [1.0, 1.0, 1.0, 1.5, 2.0, 2.0, 2.0, 1.5, 1.0, 1.0]))
    reg = rate_regimes(rates, lookback=3, threshold=0.25)
    assert reg[d[2]] is None  # not enough history
    assert reg[d[4]] == "hike"  # 2.0 vs 1.0 three days earlier
    assert reg[d[6]] == "hike"  # 2.0 vs 1.5
    assert reg[d[8]] == "cut"  # 1.0 vs 2.0
    assert reg[d[3]] == "hike"  # 1.5 vs 1.0


def test_mix_uses_yesterdays_regime_and_charges_switches():
    d = days(5)
    a = list(zip(d, [1.0, 1.1, 1.21, 1.331, 1.4641]))  # +10% a day
    b = list(zip(d, [1.0, 1.0, 1.0, 1.0, 1.0]))  # flat
    reg = {d[0]: "hike", d[1]: "hike", d[2]: "cut", d[3]: "cut", d[4]: "cut"}
    out = mix_by_regime({"A": a, "B": b}, reg, {"hike": "A", "cut": "B"}, "B", cost_bps=0)
    eq = [e for _, e in out]
    # day1, day2 follow A (regime of d0, d1 = hike), day3+ follow B
    assert eq == pytest.approx([1.0, 1.1, 1.21, 1.21, 1.21])
    out2 = mix_by_regime({"A": a, "B": b}, reg, {"hike": "A", "cut": "B"}, "B", cost_bps=100)
    assert out2[-1][1] == pytest.approx(1.21 * 0.99)  # one switch A -> B
