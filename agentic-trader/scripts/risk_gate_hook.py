#!/usr/bin/env python3
"""Claude Code PreToolUse hook entry point (reads the hook payload JSON from stdin).

Files (relative to AGENTIC_TRADER_HOME, default: this project's root):
    config/live_rules.yaml        risk limits (stocks)
    config/live_option_rules.yaml option risk profile (optional; option orders are blocked
                                  without it)
    config/mcp_tool_map.yaml      Robinhood MCP tool / argument mapping
    state/account_snapshot.json   latest account snapshot
    state/hook_audit.jsonl        append-only decision log
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agentic_trader.hook import ToolMap, audit, evaluate_tool_call, load_snapshot  # noqa: E402
from agentic_trader.options import load_option_rules  # noqa: E402
from agentic_trader.risk_gate import load_rules  # noqa: E402


def main() -> int:
    home = Path(os.environ.get("AGENTIC_TRADER_HOME", ROOT))
    now = datetime.now(timezone.utc)
    try:
        payload = json.load(sys.stdin)
    except Exception as e:  # malformed input: block
        print(f"risk gate: unreadable hook payload ({e})", file=sys.stderr)
        return 2
    try:
        tool_map = ToolMap.load(home / "config" / "mcp_tool_map.yaml")
        rules = load_rules(home / "config" / "live_rules.yaml")
        snapshot = load_snapshot(home / "state" / "account_snapshot.json")
        opt_path = home / "config" / "live_option_rules.yaml"
        option_rules = load_option_rules(opt_path) if opt_path.exists() else None
        decision = evaluate_tool_call(payload, tool_map, rules, snapshot, now, option_rules)
    except Exception as e:  # any internal failure on a trading call: block
        if not str(payload.get("tool_name", "")).startswith("mcp__"):
            return 0
        print(f"risk gate error, blocking to be safe: {e}", file=sys.stderr)
        return 2
    try:
        audit(home / "state" / "hook_audit.jsonl", payload, decision, now)
    except OSError:
        pass  # never let logging failures change the decision
    if decision.allowed:
        return 0
    print("risk gate blocked this order: " + "; ".join(decision.reasons), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
