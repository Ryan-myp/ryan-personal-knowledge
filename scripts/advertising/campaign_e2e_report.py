"""Summarize controlled campaign E2E runs without promoting historical claims."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.tools.advertising.providers.source_factory import create_tool_source
from scripts.advertising.campaign_service_e2e import WRITABLE_HIERARCHY_RESOURCES
from scripts.advertising.provider_live_e2e_memory import load_live_e2e_memory


_CASE_NAME = re.compile(r"[a-zA-Z0-9_.-]{1,120}\Z")
_RUN_ID = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\Z")
_MAX_CASES = 500
_MAX_BYTES = 4_194_304


def _read_json(path: Path) -> dict[str, Any]:
    if path.stat().st_size > _MAX_BYTES:
        raise ValueError("E2E case exceeds size limit")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("E2E case must be an object")
    return value


def _http_events(directory: Path) -> dict[tuple[str, str], list[dict[str, Any]]]:
    path = directory / "provider-http.jsonl"
    if not path.exists():
        return {}
    if path.is_symlink():
        raise ValueError("Provider transport journal must be a regular file")
    if path.stat().st_size > _MAX_BYTES:
        raise ValueError("Provider transport journal exceeds size limit")
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if isinstance(row, dict):
            key = (str(row.get("case_id") or ""), str(row.get("provider") or ""))
            grouped.setdefault(key, []).append(row)
    return grouped


def _latest_response(case: Mapping[str, Any]) -> dict[str, Any]:
    phases = case.get("phases")
    if isinstance(phases, list):
        for phase in reversed(phases):
            if isinstance(phase, dict) and isinstance(phase.get("response"), dict):
                return phase["response"]
    response = case.get("response")
    return response if isinstance(response, dict) else {}


def _case_summary(
    path: Path,
    trusted_accounts: Mapping[str, str],
    tools: Mapping[str, Mapping[str, Any]],
    http_events: Mapping[tuple[str, str], list[dict[str, Any]]],
) -> dict[str, Any]:
    case = _read_json(path)
    provider = case.get("provider")
    account = case.get("account")
    response = _latest_response(case)
    results = response.get("results")
    results = results if isinstance(results, list) else []
    expected_tool = case.get("tool") or (
        results[0].get("tool") if len(results) == 1 and isinstance(results[0], dict)
        else None
    )
    definition = (
        tools.get(provider, {}).get(expected_tool)
        if isinstance(provider, str) and isinstance(expected_tool, str)
        else None
    )
    run_id = response.get("run_id")
    run_id = run_id if isinstance(run_id, str) and _RUN_ID.fullmatch(run_id) else None
    row = {
        "case_id": path.stem,
        "provider": provider if isinstance(provider, str) and provider in trusted_accounts else "unknown",
        "tool": expected_tool if definition else None,
        "action": definition.action if definition else None,
        "resource": definition.resource_type if definition else None,
        "run_id": run_id,
        "verdict": "not_verified",
    }
    if (
        not isinstance(provider, str)
        or provider not in trusted_accounts
        or account != trusted_accounts[provider]
    ):
        row["verdict"] = "out_of_scope"
        return row
    if definition is None or len(results) != 1 or not isinstance(results[0], dict):
        return row
    if (
        definition.is_write_tool
        and definition.resource_type not in WRITABLE_HIERARCHY_RESOURCES
    ):
        row["verdict"] = "out_of_scope"
        return row
    result = results[0]
    transport = http_events.get((path.stem, provider), [])
    network_ok = bool(transport) and all(
        isinstance(event.get("http_status"), int)
        and 200 <= event["http_status"] < 300
        and event.get("provider_code") in (None, 0)
        for event in transport
    )
    data = result.get("data")
    is_live = (
        result.get("success") is True
        and result.get("simulated") is not True
        and isinstance(data, dict)
        and data.get("data_status") == "live"
        and result.get("tool") == expected_tool
        and response.get("status") in {"succeeded", "completed"}
        and bool(row["run_id"])
    )
    if definition.is_write_tool:
        row["verdict"] = "write_requires_readback_review"
    elif network_ok and is_live:
        row["verdict"] = "read_verified"
    return row


def build_report(directory: Path, memory: Mapping[str, Any]) -> dict[str, Any]:
    """A Tool result plus a matching transport is proof of a read, not a write."""
    directory = Path(directory)
    trusted_accounts = memory["scope"]["test_accounts"]
    tools = {
        provider: {
            binding.definition.name: binding.definition
            for binding in create_tool_source(provider).list_bindings()
        }
        for provider in trusted_accounts
    }
    paths = sorted((directory / "cases").glob("*.json"))
    if (directory / "cases").is_symlink() or len(paths) > _MAX_CASES or any(
        not _CASE_NAME.fullmatch(path.stem) or path.is_symlink()
        for path in paths
    ):
        raise ValueError("E2E case inventory is invalid or exceeds limit")
    events = _http_events(directory)
    cases = [
        _case_summary(path, trusted_accounts, tools, events)
        for path in paths
    ]
    campaign_types = [{
        "provider": item["provider"],
        "campaign_type": item["campaign_type"],
        "template_key": item["template_key"],
        "historical_state": item["verification_state"],
        "current_write_verified": False,
        "gap_recorded": bool(item.get("remaining_gap")),
    } for item in memory["campaign_types"]]
    return {
        "schema_version": "campaign-e2e-diagnostic/v1",
        "scope": "confirmed_test_accounts_campaign_hierarchy_only",
        "read_verified": sum(row["verdict"] == "read_verified" for row in cases),
        "write_verified": 0,
        "cases": cases,
        "campaign_types": campaign_types,
        "limitations": [
            "Historical template memory is not current-run CRUD evidence.",
            "Writes need exact resource readback and human review; no automatic promotion.",
            "Deletes are not live-enabled by the current Provider Tool contracts.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = build_report(args.directory, load_live_e2e_memory(ROOT))
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
