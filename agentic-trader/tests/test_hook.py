import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from agentic_trader.hook import ToolMap, evaluate_tool_call
from agentic_trader.risk_gate import RiskRules

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 10, 15, 0, tzinfo=timezone.utc)
MAP = ToolMap.load(ROOT / "config" / "mcp_tool_map.yaml")
RULES = RiskRules(max_order_notional=5_000, max_position_pct=20, risk_per_trade_pct=1.0)


def snapshot(age_min=1, **kw):
    snap = {
        "as_of": (NOW - timedelta(minutes=age_min)).isoformat(),
        "equity": 20_000,
        "cash": 10_000,
        "day_start_equity": 20_000,
        "positions": {"AAPL": {"qty": 10, "avg_price": 200, "last_price": 210, "stop_price": 195}},
        "quotes": {"MSFT": 400},
    }
    snap.update(kw)
    return snap


def call(tool, **tool_input):
    return {"tool_name": f"mcp__robinhood-trading__{tool}", "tool_input": tool_input}


def ev(payload, snap):
    return evaluate_tool_call(payload, MAP, RULES, snap, NOW)


def test_non_trading_tools_pass_through():
    assert ev({"tool_name": "Bash", "tool_input": {}}, None).allowed


def test_read_only_tools_allowed_even_without_snapshot():
    assert ev(call("get_positions"), None).allowed


def test_unknown_trading_tool_blocked():
    d = ev(call("transfer_funds", amount=1000), snapshot())
    assert not d.allowed and "unknown trading tool" in d.reasons[0]


def test_entry_with_attached_stop_allowed():
    p = call(
        "place_order", symbol="msft", side="buy", quantity=5, type="market", stop_loss_price=390
    )
    assert ev(p, snapshot()).allowed


def test_entry_without_stop_blocked():
    p = call("place_order", symbol="MSFT", side="buy", quantity=5, type="market")
    assert not ev(p, snapshot()).allowed


def test_dollar_based_entry_converted_to_qty_and_capped():
    p = call(
        "place_order", symbol="MSFT", side="buy", amount=8000, type="market", stop_loss_price=399
    )
    d = ev(p, snapshot())
    assert not d.allowed and any("notional" in r for r in d.reasons)


def test_loosening_stop_blocked_tightening_allowed():
    loosen = call(
        "place_order", symbol="AAPL", side="sell", quantity=10, type="stop", stop_price=180
    )
    tighten = call(
        "place_order", symbol="AAPL", side="sell", quantity=10, type="stop", stop_price=205
    )
    assert not ev(loosen, snapshot()).allowed
    assert ev(tighten, snapshot()).allowed


def test_stale_snapshot_blocks_entries_but_not_exits():
    entry = call(
        "place_order", symbol="MSFT", side="buy", quantity=1, type="market", stop_loss_price=390
    )
    exit_ = call("place_order", symbol="AAPL", side="sell", quantity=10, type="market")
    stale = snapshot(age_min=60)
    assert not ev(entry, stale).allowed
    assert ev(exit_, stale).allowed
    assert ev(exit_, None).allowed  # even with no snapshot at all


def test_unparseable_order_blocked():
    assert not ev(call("place_order", symbol="AAPL", side="hold", quantity=1), snapshot()).allowed
    assert not ev(
        call("place_order", symbol="AAPL", side="buy", quantity=1, type="trailing_stop"), snapshot()
    ).allowed


def test_buy_stop_blocked():
    p = call("place_order", symbol="MSFT", side="buy", quantity=1, type="stop", stop_price=410)
    assert not ev(p, snapshot()).allowed


def test_cancel_policy():
    assert ev(call("cancel_order", order_id="x"), snapshot()).allowed
    deny_map = ToolMap(cancel_policy="deny")
    assert not evaluate_tool_call(call("cancel_order"), deny_map, RULES, snapshot(), NOW).allowed


def test_tool_map_rejects_unknown_keys(tmp_path):
    p = tmp_path / "m.yaml"
    p.write_text("server_prefx: mcp__rh\n")
    with pytest.raises(ValueError):
        ToolMap.load(p)


@pytest.fixture
def home(tmp_path):
    shutil.copytree(ROOT / "config", tmp_path / "config")
    (tmp_path / "state").mkdir()
    snap = snapshot()
    snap["as_of"] = datetime.now(timezone.utc).isoformat()
    (tmp_path / "state" / "account_snapshot.json").write_text(json.dumps(snap))
    return tmp_path


def _run_hook(home, payload):
    env = {**os.environ, "AGENTIC_TRADER_HOME": str(home)}
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "risk_gate_hook.py")],
        input=json.dumps(payload) if isinstance(payload, dict) else payload,
        capture_output=True,
        text=True,
        env=env,
    )


def test_hook_script_blocks_with_exit_2_and_logs(home):
    bad = call("place_order", symbol="AAPL", side="sell", quantity=10, type="stop", stop_price=100)
    proc = _run_hook(home, bad)
    assert proc.returncode == 2
    assert "cannot loosen stop" in proc.stderr
    log = (home / "state" / "hook_audit.jsonl").read_text().splitlines()
    assert json.loads(log[-1])["allowed"] is False


def test_hook_script_allows_with_exit_0(home):
    proc = _run_hook(home, call("get_portfolio"))
    assert proc.returncode == 0, proc.stderr


def test_hook_script_blocks_garbage_input(home):
    assert _run_hook(home, "not json").returncode == 2


# ------------------------------------------------------------ option orders

from agentic_trader.options import OptionRules, load_option_rules  # noqa: E402

OPT_RULES = load_option_rules(ROOT / "config" / "live_option_rules.yaml")


def opt_snapshot(age_min=1, **kw):
    snap = snapshot(age_min, equity=100_000, cash=100_000, **kw)
    snap.setdefault(
        "option_positions",
        [
            {
                "underlying": "QQQ",
                "right": "call",
                "strike": 575,
                "expiry": "2027-08-20",
                "qty": 2,
                "avg_price": 135.0,
            }
        ],
    )
    return snap


def opt_call(**tool_input):
    base = dict(
        symbol="QQQ",
        option_type="call",
        strike=575,
        expiration="2027-08-20",
        side="buy",
        quantity=1,
        type="limit",
        price=136.0,
    )
    base.update(tool_input)
    return {"tool_name": "mcp__robinhood-trading__place_option_order", "tool_input": base}


def ev_opt(payload, snap, option_rules=OPT_RULES):
    return evaluate_tool_call(payload, MAP, RULES, snap, NOW, option_rules=option_rules)


def test_leaps_call_within_profile_is_allowed():
    snap = opt_snapshot(option_positions=[])
    assert ev_opt(opt_call(quantity=3), snap).allowed  # $40.8k = 41% of $100k


def test_option_premium_over_profile_cap_is_blocked():
    snap = opt_snapshot(option_positions=[])
    d = ev_opt(opt_call(quantity=4), snap)  # $54.4k > 50%
    assert not d.allowed and any("max loss" in r for r in d.reasons)


def test_option_wrong_underlying_short_dte_and_market_orders_blocked():
    snap = opt_snapshot(option_positions=[])
    assert not ev_opt(opt_call(symbol="TSLA"), snap).allowed
    assert not ev_opt(opt_call(expiration="2026-12-18"), snap).allowed  # < 150 DTE
    assert not ev_opt(opt_call(type="market", price=None), snap).allowed


def test_option_naked_sell_blocked_closing_held_leg_allowed_even_when_stale():
    snap = opt_snapshot()
    assert not ev_opt(opt_call(side="sell", strike=700), snap).allowed  # not held: naked
    stale = opt_snapshot(age_min=120)
    assert ev_opt(opt_call(side="sell", quantity=2), stale).allowed
    assert not ev_opt(opt_call(side="sell", quantity=3), opt_snapshot()).allowed  # more than held


def test_option_entry_blocked_when_snapshot_stale_or_no_rules():
    assert not ev_opt(opt_call(), opt_snapshot(age_min=120, option_positions=[])).allowed
    d = ev_opt(opt_call(), opt_snapshot(option_positions=[]), option_rules=None)
    assert not d.allowed and "option rules" in d.reasons[0]


def test_load_option_rules_rejects_unknown_keys(tmp_path):
    p = tmp_path / "o.yaml"
    p.write_text("max_loss_per_trade_pct: 10\nmax_loss_per_trad_pct: 5\n")
    with pytest.raises(ValueError):
        load_option_rules(p)
    assert isinstance(OPT_RULES, OptionRules)


def test_hook_script_gates_option_orders_end_to_end(home):
    snap = opt_snapshot(option_positions=[])
    snap["as_of"] = datetime.now(timezone.utc).isoformat()
    (home / "state" / "account_snapshot.json").write_text(json.dumps(snap))
    exp = (datetime.now(timezone.utc).date() + timedelta(days=270)).isoformat()
    ok = _run_hook(home, opt_call(quantity=3, expiration=exp))
    too_big = _run_hook(home, opt_call(quantity=4, expiration=exp))
    assert ok.returncode == 0, ok.stderr
    assert too_big.returncode == 2 and "max loss" in too_big.stderr
