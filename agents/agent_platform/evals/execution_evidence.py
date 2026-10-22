"""Execution-ledger projection and strict scalar evidence for platform judges."""

from collections.abc import Mapping
from typing import Any

from agents.agent_harness.results import RunStatus


def run_status_evidence(value: Any) -> str:
    if not isinstance(value, str) or value not in {item.value for item in RunStatus}:
        raise ValueError("Runtime status evidence is invalid")
    return RunStatus(value).value


def boolean_evidence(value: Mapping[str, Any], key: str) -> bool:
    field = value[key]
    if type(field) is not bool:
        raise ValueError(f"{key} evidence must be boolean")
    return field


def execution_ledger(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, (list, tuple)) or len(rows) > 64:
        raise ValueError("Tool execution evidence must be a bounded list")
    ledger = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("Tool execution evidence must be an object")
        name = row.get("name")
        if not isinstance(name, str) or not name.strip() or len(name) > 200:
            raise ValueError("Tool execution requires a bounded name")
        error = boolean_evidence(row, "is_error")
        signals = row.get("runtime_signals") or {}
        if not isinstance(signals, Mapping):
            raise ValueError("Tool runtime signals must be an object")
        content = row.get("content")
        failed = isinstance(content, Mapping) and (
            "success" in content and not boolean_evidence(content, "success")
        )
        state = "failed" if error or failed else "completed"
        if signals.get("tool_execution_deferred") is True:
            state = "deferred"
        elif any(signals.get(key) is True for key in (
            "duplicate_read_coalesced", "duplicate_write_coalesced",
        )):
            state = "coalesced"
        ledger.append({"tool": name, "success": state == "completed", "state": state})
    return ledger


def regression_calls(response: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = response.get("tool_executions", response.get("results", []))
    if not isinstance(rows, list) or len(rows) > 64:
        raise ValueError("regression response calls must be a bounded list")
    if any(not isinstance(row, Mapping) for row in rows):
        raise ValueError("regression response call must be an object")
    for row in rows:
        if "success" in row:
            boolean_evidence(row, "success")
        if "tool_executions" in response:
            state = row.get("state")
            if state not in {"completed", "failed", "deferred", "coalesced"}:
                raise ValueError("regression execution state is invalid")
            if row.get("success") is not (state == "completed"):
                raise ValueError("regression execution state conflicts with success")
    return rows
