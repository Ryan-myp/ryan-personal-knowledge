"""Deterministic, structured assertions for the ad-agent skill-up adapter.

The upstream case format remains the source of truth for normal skill-up
execution.  These assertions are an additional platform-owned release gate:
they inspect the structured Runtime evidence instead of relying only on
human-facing text matching.  Case authors can assert routing and safety
facts, but cannot provide executable judges or commands.
"""

from __future__ import annotations

from typing import Any, Mapping


def _runtime_evidence(result: Mapping[str, Any]) -> Mapping[str, Any]:
    metadata = result.get("metadata") or {}
    evidence = metadata.get("runtime_result") if isinstance(metadata, Mapping) else None
    return evidence if isinstance(evidence, Mapping) else {}


def _tool_names(evidence: Mapping[str, Any]) -> list[str]:
    plan = evidence.get("tool_plan") or {}
    names: list[str] = []
    if isinstance(plan, Mapping):
        for values in plan.values():
            if isinstance(values, (list, tuple)):
                names.extend(str(value) for value in values)
    return list(dict.fromkeys(names))


def _results(evidence: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    values = evidence.get("results")
    return [item for item in values if isinstance(item, Mapping)] if isinstance(values, list) else []


def evaluate_structured_expectations(
    result: Mapping[str, Any], expected: Mapping[str, Any] | None,
) -> list[str]:
    """Return human-readable failures for the optional ``expect.structured`` block."""
    structured = (expected or {}).get("structured") if isinstance(expected, Mapping) else None
    if not isinstance(structured, Mapping):
        return []
    evidence = _runtime_evidence(result)
    failures: list[str] = []

    intent = evidence.get("intent") if isinstance(evidence.get("intent"), Mapping) else {}
    if "intent_type" in structured and intent.get("intent_type") != structured["intent_type"]:
        failures.append(f"intent.intent_type expected {structured['intent_type']!r}, got {intent.get('intent_type')!r}")
    if "platforms" in structured and intent.get("platforms") != structured["platforms"]:
        failures.append(f"intent.platforms expected {structured['platforms']!r}, got {intent.get('platforms')!r}")
    for key in ("needs_input", "needs_confirmation"):
        if key in structured:
            actual = bool(evidence.get(key, False))
            if actual != bool(structured[key]):
                failures.append(f"{key} expected {bool(structured[key])!r}, got {actual!r}")

    rows = _results(evidence)
    if "results_count" in structured and len(rows) != int(structured["results_count"]):
        failures.append(f"results_count expected {structured['results_count']}, got {len(rows)}")
    if structured.get("results_empty") is True and rows:
        failures.append(f"results_empty expected true, got {len(rows)} result envelope(s)")
    names = _tool_names(evidence)
    if "tool_names" in structured:
        expected_names = [str(value) for value in structured["tool_names"]]
        if names != expected_names:
            failures.append(f"tool_names expected {expected_names!r}, got {names!r}")
    if "result_data_status" in structured:
        statuses = [str((row.get("data") or {}).get("data_status") or "") for row in rows]
        expected_statuses = [str(value) for value in structured["result_data_status"]]
        if statuses != expected_statuses:
            failures.append(f"result_data_status expected {expected_statuses!r}, got {statuses!r}")
    return failures
