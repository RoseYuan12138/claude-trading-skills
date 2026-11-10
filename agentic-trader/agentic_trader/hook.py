"""Claude Code PreToolUse hook: run every Robinhood MCP call through the risk gate.

Wire-up (in the Claude Code settings used on the trading machine):

    "hooks": {"PreToolUse": [{"matcher": "mcp__robinhood__.*",
        "hooks": [{"type": "command",
                   "command": "python3 /path/to/agentic-trader/scripts/risk_gate_hook.py"}]}]}

Exit code 0 allows the call; exit code 2 blocks it and the stderr text is shown to
Claude as the reason. Anything unexpected is blocked (fail closed).

The Robinhood Trading MCP tool names and argument names are not publicly
documented, so they are mapped in ``config/mcp_tool_map.yaml``. Inspect the real
tool schemas on your machine and edit that file before going live.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .models import AccountState, Decision, OrderIntent, OrderType, PositionSnapshot, Purpose, Side
from .risk_gate import RiskRules, validate

_ORDER_TYPES = {
    "market": OrderType.MARKET,
    "limit": OrderType.LIMIT,
    "stop": OrderType.STOP,
    "stop_market": OrderType.STOP,
    "stop_loss": OrderType.STOP,
    "stop_limit": OrderType.STOP,
}


@dataclass
class ToolMap:
    server_prefix: str = "mcp__robinhood"
    read_only_prefixes: tuple[str, ...] = ("get", "list", "search", "fetch", "view", "describe")
    cancel_prefixes: tuple[str, ...] = ("cancel",)
    cancel_policy: str = "allow"  # "allow" or "deny"
    order_tools: dict[str, dict[str, str]] = field(default_factory=dict)
    snapshot_max_age_minutes: float = 15.0

    @classmethod
    def load(cls, path: str | Path) -> ToolMap:
        raw = yaml.safe_load(Path(path).read_text()) or {}
        unknown = sorted(set(raw) - set(cls.__dataclass_fields__))
        if unknown:
            raise ValueError(f"unknown tool map keys: {', '.join(unknown)}")
        tm = cls(**raw)
        tm.read_only_prefixes = tuple(tm.read_only_prefixes)
        tm.cancel_prefixes = tuple(tm.cancel_prefixes)
        if tm.cancel_policy not in {"allow", "deny"}:
            raise ValueError("cancel_policy must be 'allow' or 'deny'")
        return tm


def load_snapshot(path: str | Path) -> dict[str, Any] | None:
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text())


def _snapshot_age_minutes(snapshot: dict[str, Any], now: datetime) -> float:
    as_of = datetime.fromisoformat(snapshot["as_of"])
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    return (now - as_of).total_seconds() / 60


def _account_state(snapshot: dict[str, Any]) -> AccountState:
    positions = {
        sym.upper(): PositionSnapshot(
            qty=float(p["qty"]),
            avg_price=float(p["avg_price"]),
            last_price=float(p["last_price"]),
            stop_price=None if p.get("stop_price") is None else float(p["stop_price"]),
        )
        for sym, p in (snapshot.get("positions") or {}).items()
    }
    equity = float(snapshot["equity"])
    return AccountState(
        equity=equity,
        cash=float(snapshot["cash"]),
        day_start_equity=float(snapshot.get("day_start_equity", equity)),
        positions=positions,
        entries_today=int(snapshot.get("entries_today", 0)),
        halted=bool(snapshot.get("halted", False)),
    )


def _ref_price(sym: str, snapshot: dict | None, limit_price: float | None) -> float | None:
    if snapshot:
        pos = (snapshot.get("positions") or {}).get(sym)
        if pos and pos.get("last_price"):
            return float(pos["last_price"])
        quote = (snapshot.get("quotes") or {}).get(sym)
        if quote:
            return float(quote)
    return limit_price


def _num(value: Any) -> float | None:
    return None if value in (None, "") else float(value)


def parse_order(
    tool_input: dict[str, Any], mapping: dict[str, str], snapshot: dict | None
) -> OrderIntent:
    """Translate an MCP order-tool call into an OrderIntent. Raises ValueError if unclear."""

    def get(key: str) -> Any:
        name = mapping.get(key)
        return tool_input.get(name) if name else None

    symbol = str(get("symbol") or "").upper()
    if not symbol:
        raise ValueError("order has no symbol")
    side = Side(str(get("side") or "").lower())
    type_name = str(get("order_type") or "market").lower()
    if type_name not in _ORDER_TYPES:
        raise ValueError(f"unsupported order type {type_name!r}")
    order_type = _ORDER_TYPES[type_name]
    limit_price = _num(get("limit_price"))
    stop_price = _num(get("stop_price"))
    attached_stop = _num(get("attached_stop_price"))

    ref = _ref_price(symbol, snapshot, limit_price)
    qty = _num(get("quantity"))
    notional = _num(get("notional"))
    if qty is None and notional is not None and ref:
        qty = notional / ref
    if not qty or qty <= 0:
        raise ValueError("order has no positive quantity")
    is_exit = side is Side.SELL and order_type is not OrderType.STOP
    if not ref:
        if not is_exit:
            raise ValueError(f"no reference price for {symbol}: add it to snapshot quotes")
        ref = 1.0  # exits are validated on quantity only; never block getting out

    if side is Side.BUY:
        if order_type is OrderType.STOP:
            raise ValueError("buy-stop orders are not allowed")
        return OrderIntent(
            symbol, side, qty, Purpose.ENTRY, ref, order_type, attached_stop, limit_price, "agent"
        )
    if order_type is OrderType.STOP:
        return OrderIntent(
            symbol,
            side,
            qty,
            Purpose.STOP_UPDATE,
            ref,
            order_type,
            stop_price,
            limit_price,
            "agent",
        )
    return OrderIntent(symbol, side, qty, Purpose.EXIT, ref, order_type, None, limit_price, "agent")


def evaluate_tool_call(
    payload: dict[str, Any],
    tool_map: ToolMap,
    rules: RiskRules,
    snapshot: dict[str, Any] | None,
    now: datetime | None = None,
) -> Decision:
    now = now or datetime.now(timezone.utc)
    tool_name = str(payload.get("tool_name", ""))
    prefix = tool_map.server_prefix + "__"
    if not tool_name.startswith(prefix):
        return Decision.allow()  # not a trading tool
    suffix = tool_name[len(prefix) :]
    lowered = suffix.lower()

    if suffix in tool_map.order_tools:
        tool_input = payload.get("tool_input") or {}
        try:
            intent = parse_order(tool_input, tool_map.order_tools[suffix], snapshot)
        except (ValueError, TypeError) as e:
            return Decision.deny(f"could not parse order ({e}); blocked to be safe")

        fresh = snapshot is not None and (
            _snapshot_age_minutes(snapshot, now) <= tool_map.snapshot_max_age_minutes
        )
        if not fresh:
            if intent.purpose is Purpose.EXIT:
                return Decision.allow()  # never block getting out
            return Decision.deny(
                "account snapshot missing or stale: refresh it before entries or stop changes"
            )
        return validate(intent, _account_state(snapshot), rules)

    if lowered.startswith(tool_map.cancel_prefixes):
        if tool_map.cancel_policy == "deny":
            return Decision.deny("order cancellation is disabled by policy")
        return Decision.allow()
    if lowered.startswith(tool_map.read_only_prefixes):
        return Decision.allow()
    return Decision.deny(
        f"unknown trading tool {suffix!r}: add it to read_only_prefixes or order_tools "
        "in config/mcp_tool_map.yaml"
    )


def audit(path: str | Path, payload: dict, decision: Decision, now: datetime) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": now.isoformat(),
        "tool": payload.get("tool_name"),
        "input": payload.get("tool_input"),
        "allowed": decision.allowed,
        "reasons": list(decision.reasons),
    }
    with p.open("a") as fh:
        fh.write(json.dumps(row, default=str) + "\n")
