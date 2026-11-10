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
    return {"tool_name": f"mcp__robinhood__{tool}", "tool_input": tool_input}


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
