"""Execution-ledger projection and strict scalar evidence for platform judges."""

from collections.abc import Mapping
import hashlib
import json
import re
from typing import Any

from agents.agent_harness.results import RunStatus
from agents.agent_harness.redaction import is_sensitive_key, redact_for_persistence


def argument_fingerprints(arguments: Mapping[str, Any]) -> dict[str, str]:
    """Compare bounded JSON values without retaining queries or credentials."""
    fingerprints = {}
    for key, value in list(arguments.items())[:32]:
        if (
            not isinstance(key, str) or is_sensitive_key(key)
            or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,119}", key)
        ):
            continue
        if redact_for_persistence({key: value}) != {key: value}:
            continue
        encoded = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
        )
        fingerprints[key] = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return fingerprints


class ToolArgumentEvidence:
    """Observe resolved Tool-call inputs; this object never authorizes execution."""

    def __init__(self) -> None:
        self._calls: dict[tuple[str, str], dict[str, str]] = {}

    def clear(self) -> None:
        self._calls.clear()

    def __call__(self, event: Mapping[str, Any]) -> None:
        if event.get("type") != "tool_execution_start" or len(self._calls) >= 64:
            return
        name, call_id = event.get("tool_name"), event.get("tool_call_id")
        arguments = event.get("arguments")
        if (
            not isinstance(name, str) or not isinstance(call_id, str)
            or not isinstance(arguments, Mapping)
        ):
            return
        if len(name) > 200 or len(call_id) > 200:
            return
        self._calls[(name, call_id)] = argument_fingerprints(arguments)

    def enrich(self, rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
        return [{
            **row,
            **({"argument_fingerprints": self._calls[key]} if key in self._calls else {}),
        } for row in rows for key in [(row.get("name"), row.get("tool_call_id"))]]


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
        ledger.append({
            "tool": name, "success": state == "completed", "state": state,
            **({"argument_fingerprints": row["argument_fingerprints"]}
               if "argument_fingerprints" in row else {}),
        })
    return ledger


def regression_calls(response: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = response.get("tool_executions", response.get("results", []))
    if not isinstance(rows, list) or len(rows) > 64:
        raise ValueError("regression response calls must be a bounded list")
    if any(not isinstance(row, Mapping) for row in rows):
        raise ValueError("regression response call must be an object")
    for row in rows:
        fingerprints = row.get("argument_fingerprints", {})
        if not isinstance(fingerprints, Mapping) or len(fingerprints) > 32 or any(
            not isinstance(key, str) or len(key) > 120
            or not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None
            for key, value in fingerprints.items()
        ):
            raise ValueError("regression argument fingerprints are invalid")
        if "success" in row:
            boolean_evidence(row, "success")
        if "tool_executions" in response:
            state = row.get("state")
            if state not in {"completed", "failed", "deferred", "coalesced"}:
                raise ValueError("regression execution state is invalid")
            if row.get("success") is not (state == "completed"):
                raise ValueError("regression execution state conflicts with success")
    return rows
