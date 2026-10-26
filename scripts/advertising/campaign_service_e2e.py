"""Authorized test-account checks through the HTTP Agent with paused delivery parents."""

from __future__ import annotations

import argparse
from contextvars import ContextVar
import json
import logging
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs, urlsplit

import requests
import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.agent_harness.redaction import redact_for_persistence
from agents.agent_harness.core.timeouts import DEFAULT_EXECUTION_TIMEOUT_SECONDS
from agents.deployments.advertising.local_config import load_default_local_env
from agents.tools.advertising.providers.source_factory import create_tool_source
from scripts.advertising.provider_live_e2e_memory import (
    append_live_e2e_observation,
    load_live_e2e_memory,
    require_new_hierarchy_authorization,
    resolve_template_memory,
)

PROVIDERS = ("google-ads", "meta", "tiktok")
CONFIRMED_ACCOUNTS = {
    "google-ads": ["9055507554"],
    "meta": ["2806375919473667"],
    "tiktok": ["7397068114548195329"],
}
HOSTS = {
    "google-ads": "googleads.googleapis.com",
    "meta": "graph.facebook.com",
    "tiktok": "business-api.tiktok.com",
}
RESOURCES = {
    "campaign",
    "ad_group",
    "ad_set",
    "ad",
    "creative",
    "asset_group",
    "listing_group_filter",
    "product_group",
    "creative_portfolio",
}
WRITABLE_HIERARCHY_RESOURCES = {
    "campaign", "ad_group", "ad_set", "ad", "asset_group",
    "listing_group_filter", "product_group",
}
GOOGLE_MUTATION_RESOURCES = {
    "campaigns", "adGroups", "adGroupAds", "adGroupCriteria",
    "assetGroups", "assetGroupListingGroupFilters", "ads",
}
GOOGLE_BATCH_OPERATIONS = {
    "campaignOperation": "campaigns",
    "adGroupOperation": "adGroups",
    "adGroupAdOperation": "adGroupAds",
    "adGroupCriterionOperation": "adGroupCriteria",
    "assetGroupOperation": "assetGroups",
    "assetGroupListingGroupFilterOperation": "assetGroupListingGroupFilters",
}
META_CREATE_RESOURCES = {
    "campaigns": "campaign", "adsets": "ad_set", "ads": "ad",
}
TIKTOK_CREATE_IDS = {
    "campaign": ("campaign_id",),
    "ad_group": ("adgroup_id",),
    "ad": ("ad_id", "ad_ids", "smart_plus_ad_id"),
}
SENSITIVE = re.compile(
    r"token|secret|api[_-]?key|private_key|password|bc_id|partner_id|perter_id|mcc",
    re.I,
)
SIGNED_URL_QUERY_KEYS = {
    "signature",
    "x-signature",
    "x-amz-signature",
    "x-goog-signature",
    "sign",
    "sig",
}


def paused_payload(provider, values):
    status = "DISABLE" if provider == "tiktok" else "PAUSED"
    result = {**values, "status": status}
    if isinstance(values.get("updates"), dict):
        result["updates"] = {**values["updates"], "status": status}
    return result


def summarize_chat(payload, expected_tool):
    data = payload.get("data")
    rows = payload.get("results")
    if not isinstance(rows, list):
        rows = data.get("tool_results", []) if isinstance(data, dict) else []
    rows = [row for row in rows if isinstance(row, dict)]
    execution_rows = payload.get("tool_results")
    if not isinstance(execution_rows, list) and isinstance(data, dict):
        execution_rows = data.get("tool_results")
    execution_rows = (
        [row for row in execution_rows if isinstance(row, dict)]
        if isinstance(execution_rows, list)
        else rows
    )
    coalesced_count = sum(
        any(
            bool((row.get("runtime_signals") or {}).get(signal))
            for signal in (
                "duplicate_read_coalesced",
                "duplicate_write_coalesced",
            )
        )
        for row in execution_rows
    )
    raw_tool_call_count = payload.get("tool_call_count")
    model_tool_call_count = (
        raw_tool_call_count
        if isinstance(raw_tool_call_count, int) and raw_tool_call_count >= 0
        else len(execution_rows)
    )
    effective_execution_count = max(
        0, len(execution_rows) - coalesced_count
    )
    matched = [
        row
        for row in rows
        if (row.get("tool_name") or row.get("tool") or row.get("name")) == expected_tool
    ]
    succeeded = any(
        (row.get("result") or row).get("success") is True
        and not (row.get("result") or row).get("simulated")
        and not any(
            node.get("mode") == "dry_run"
            or node.get("execution_status") == "planned"
            or node.get("simulated") is True
            or str(node.get("data_status") or "").startswith("offline")
            for node in _walk((row.get("result") or row).get("data") or {})
        )
        for row in matched
    )
    unexpected_tools = [
        str(row.get("tool_name") or row.get("tool") or row.get("name") or "")
        for row in rows
        if (row.get("tool_name") or row.get("tool") or row.get("name"))
        != expected_tool
    ]
    passed = (
        len(rows) == 1
        and len(matched) == 1
        and succeeded
        and model_tool_call_count == len(execution_rows)
        and effective_execution_count == 1
    )
    return {
        "passed": passed,
        "status": payload.get("status"),
        "matched_results": matched,
        "unexpected_tools": unexpected_tools,
        "model_tool_call_count": model_tool_call_count,
        "coalesced_call_count": coalesced_count,
        "effective_execution_count": effective_execution_count,
    }


def safe_evidence(value):
    return _scrub_evidence(redact_for_persistence(value))


def _scrub_evidence(value):
    if isinstance(value, dict):
        return {
            key: "<redacted>"
            if key in {"confirmation_payload", "selection_tokens"}
            or SENSITIVE.search(key)
            else _scrub_evidence(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_scrub_evidence(item) for item in value]
    if isinstance(value, str):
        scrubbed = re.sub(
            r"https?://[^\s\"'<>]+",
            _redact_signed_url,
            redact_for_persistence(value),
        )
        return re.sub(
            r"ps1\.[A-Za-z0-9_.-]+", "<redacted>", scrubbed
        )
    return value


def _redact_signed_url(match):
    url = match.group(0).rstrip(".,;)")
    query_keys = {
        key.casefold()
        for key in parse_qs(urlsplit(url).query, keep_blank_values=True)
    }
    return "<redacted>" if query_keys & SIGNED_URL_QUERY_KEYS else match.group(0)


def _created_resource_type(tool_name):
    name = tool_name.lower()
    if "create" not in name:
        return None
    if "listing_group_filter" in name:
        return "listing_group_filter"
    if "product_group" in name:
        return "product_group"
    if "creative_portfolio" in name:
        return "creative_portfolio"
    if "asset_group" in name:
        return "asset_group"
    if "adset" in name and "ad" not in name.replace("adset", ""):
        return "ad_set"
    if "ad_group" in name or "adgroup" in name:
        return "ad_group"
    if "campaign" in name:
        return "campaign"
    if "creative" in name:
        return "creative"
    if "create_ad" in name or name.endswith("_ad"):
        return "ad"
    return None


def _created_live_resources(payload):
    resource_fields = {
        "campaign": ("campaign_id",),
        "ad_group": ("ad_group_id", "adgroup_id"),
        "ad_set": ("adset_id", "ad_set_id"),
        "ad": ("smart_plus_ad_id", "ad_id"),
        "creative": ("creative_id",),
        "asset_group": ("asset_group_id",),
        "product_group": ("product_group_id",),
        "listing_group_filter": ("listing_group_filter_id",),
        "creative_portfolio": ("creative_portfolio_id",),
    }
    results = payload.get("results")
    if not isinstance(results, list):
        return []
    resources = []
    for row in results:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        result = row.get("result") if isinstance(row.get("result"), dict) else row
        data = result.get("data")
        if (
            not isinstance(data, dict)
            or data.get("execution_mode") != "live"
            or result.get("simulated") is True
        ):
            continue
        tool_name = str(result.get("tool") or row.get("tool") or "")
        resource_type = _created_resource_type(tool_name)
        if resource_type is None:
            continue
        for node in _walk(data):
            resource_id = next(
                (
                    node.get(field)
                    for field in resource_fields[resource_type]
                    if node.get(field) is not None
                ),
                None,
            )
            if resource_id is None:
                continue
            resource = {
                "resource_type": resource_type,
                "id": str(resource_id),
            }
            status = node.get("operation_status", node.get("status"))
            if status is not None:
                resource["status"] = str(status)
            resources.append(resource)
            break
    return resources


def _live_error_messages(payload):
    messages = []
    for row in payload.get("results") or ():
        if not isinstance(row, dict):
            continue
        result = row.get("result") if isinstance(row.get("result"), dict) else row
        error = result.get("error")
        if error:
            messages.append(str(error))
    return messages[:5]


def compact_summary(payload, tool):
    summary = summarize_chat(payload, tool)
    records = []
    for row in summary["matched_results"]:
        result = row.get("result") or row
        data = result.get("data") or {}
        records.append(
            {
                "success": result.get("success"),
                "error": result.get("error"),
                "data_status": data.get("data_status"),
                "ids": {
                    k: v
                    for k, v in data.items()
                    if k.endswith("_id") or k in {"id", "resource_name"}
                },
                "counts": {k: len(v) for k, v in data.items() if isinstance(v, list)},
            }
        )
    return safe_evidence(
        {
            "passed": summary["passed"],
            "status": summary["status"],
            "records": records,
            "needs_input": payload.get("needs_input"),
            "needs_confirmation": payload.get("needs_confirmation"),
            "reply": str(payload.get("reply") or "")[:1600],
        }
    )


def classify_evidence(case, events, *, write):
    summary = summarize_chat(case.get("response") or {}, case["tool"])
    if not summary["passed"]:
        return "failed" if summary["matched_results"] else "blocked"
    successful = [
        row
        for row in events
        if row.get("http_status") is not None
        and 200 <= row["http_status"] < 300
        and row.get("provider_code") in (None, 0)
    ]
    if write:
        successful = [
            row
            for row in successful
            if row.get("method") in {"POST", "PATCH", "PUT"}
            and not str(row.get("path") or "").endswith(
                ("googleAds:search", "googleAds:searchStream")
            )
        ]
    return "verified" if successful else "no_provider_evidence"


def readback_checks(read_case, resource_id, expected):
    fields = (
        "id",
        "campaign_id",
        "adgroup_id",
        "adset_id",
        "ad_id",
        "creative_id",
        "asset_group_id",
    )
    record = None
    summary = summarize_chat(read_case.get("response") or {}, read_case["tool"])
    if not summary["passed"]:
        return {}
    for row in summary["matched_results"]:
        result = row.get("result") or row
        if not result.get("success"):
            continue
        record = next(
            (
                node
                for node in _walk(result.get("data") or {})
                if any(
                    str(node.get(field) or "") == str(resource_id) for field in fields
                )
            ),
            None,
        )
        if record is not None:
            break
    if record is None:
        return {}
    aliases = {
        "name": ("name", "ad_name", "adgroup_name", "campaign_name"),
        "status": ("operation_status", "status"),
        "daily_budget": ("daily_budget", "budget"),
        "budget": ("budget", "daily_budget"),
        "final_url": ("final_urls",),
    }
    checks = {}
    for field, value in expected.items():
        observed = next(
            (
                record[key]
                for key in aliases.get(field, (field,))
                if record.get(key) is not None
            ),
            None,
        )
        if observed is None and field in {"headlines", "descriptions"}:
            observed = record.get("responsive_search_ad", {}).get(field)
        if observed is None and field == "creative_id":
            observed = (record.get("creative") or {}).get("id")
        target = value
        if observed is None:
            checks[field] = {"expected": target, "observed": None, "passed": None}
            continue
        if field == "status":
            states = dict.fromkeys(("0", "PAUSED", "DISABLE"), "PAUSED")
            states.update(dict.fromkeys(("1", "ACTIVE", "ENABLE", "ENABLED"), "ACTIVE"))
            normalize = lambda item: states.get(str(item).upper(), str(item))
            observed, target = normalize(observed), normalize(value)
        elif field in {"daily_budget", "budget"} and observed is not None:
            observed, target = float(observed), float(value)
            if read_case["provider"] == "meta":
                target *= 100
        elif field in {"headlines", "descriptions"} and isinstance(observed, list):
            observed = [
                item.get("text") if isinstance(item, dict) else item
                for item in observed
            ]
        elif field == "final_url" and isinstance(observed, list):
            observed = observed[0] if observed else None
        checks[field] = {
            "expected": target,
            "observed": observed,
            "passed": observed == target if observed is not None else None,
        }
    return checks


def report(directory):
    root = Path(directory).resolve()
    definitions = {
        binding.definition.name: binding.definition
        for provider in PROVIDERS
        for binding in create_tool_source(provider).list_bindings()
    }
    events = [
        json.loads(line)
        for line in (root / "provider-http.jsonl").read_text().splitlines()
        if line.strip()
    ]
    cases = []
    documents = []
    for path in (root / "cases").glob("*.json"):
        try:
            case = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (
            not isinstance(case, dict)
            or case.get("provider") not in PROVIDERS
            or case.get("tool") not in definitions
            or not isinstance(case.get("params"), dict)
            or not isinstance(case.get("response"), dict)
        ):
            continue
        documents.append((path, case))
    completion_times = {path: path.stat().st_mtime for path, _ in documents}
    events_by_case = {}
    for event in events:
        events_by_case.setdefault(event.get("case_id"), []).append(event)
    for path, case in sorted(documents, key=lambda item: item[0].name):
        tool = definitions.get(case["tool"])
        scoped_events = events_by_case.get(path.stem, [])
        outcome = classify_evidence(
            case, scoped_events, write=bool(tool and tool.is_write_tool)
        )
        summary = summarize_chat(case.get("response") or {}, case["tool"])
        errors = [
            (item.get("result") or item).get("error")
            for item in summary["matched_results"]
            if (item.get("result") or item).get("error")
        ]
        row = {
            "case_id": path.stem,
            "provider": case["provider"],
            "tool": case["tool"],
            "account": case.get("account"),
            "blueprint_id": case.get("blueprint_id"),
            "blueprint_version": case.get("blueprint_version"),
            "resource": tool.resource_type if tool else None,
            "action": tool.action if tool else None,
            "outcome": outcome,
            "agent_status": summary["status"],
            "error": errors[0] if errors else (case.get("response") or {}).get("error"),
            "transport": scoped_events,
            "matching_result_count": len(summary["matched_results"]),
        }
        if tool and tool.action == "update" and outcome == "verified":
            resource_id = case["params"].get(tool.resource_id_field)
            candidates = [
                (read_path, read_case)
                for read_path, read_case in documents
                if definitions.get(read_case["tool"])
                and definitions[read_case["tool"]].action == "get"
                and definitions[read_case["tool"]].resource_type == tool.resource_type
                and resource_id is not None
                and read_case["params"].get(tool.resource_id_field) == resource_id
                and completion_times[read_path] > completion_times[path]
                and classify_evidence(
                    read_case, events_by_case.get(read_path.stem, []), write=False
                )
                == "verified"
            ]
            checks = {}
            if candidates:
                read_path, read_case = min(
                    candidates, key=lambda item: completion_times[item[0]]
                )
                checks = readback_checks(
                    read_case, resource_id, case["params"].get("updates") or {}
                )
                row["readback_case"] = read_path.stem
            row["readback_checks"] = checks
            states = [check["passed"] for check in checks.values()]
            row["functional_status"] = (
                "failed"
                if False in states
                else "passed"
                if states and all(states)
                else "unverified"
            )
        cases.append(row)
    tested = {case["tool"] for case in cases if case["outcome"] == "verified"}
    unverified = [
        tool.name
        for tool in definitions.values()
        if tool.resource_type in RESOURCES
        and tool.action in {"create", "update", "get", "list"}
        and tool.name not in tested
    ]
    document = {
        "accounts": CONFIRMED_ACCOUNTS,
        "cases": cases,
        "unverified_tools": sorted(unverified),
    }
    _json_write(root / "report.json", document)
    lines = [
        "# Test-account service execution evidence",
        "",
        "All cases use the real /chat endpoint, model, Harness and registered Tools.",
        "Verified means matching non-simulated Tool success plus successful provider transport.",
        "It does not mean every advertising type, update field, or conversation workflow has passed.",
        "Google App Campaign and Ad Group must remain PAUSED; Google App Ad is ENABLED per v24 and cannot serve under paused parents.",
        "",
        "Transport success alone is not functional success. Updates are also checked against subsequent reads.",
        "| Case | Provider | Tool | Transport Evidence | Update Readback | Agent Status |",
        "|---|---|---|---|---|---|",
    ]
    lines.extend(
        f"| [{case['case_id']}](cases/{case['case_id']}.json) | {case['provider']} | "
        f"`{case['tool']}` | {case['outcome']} | {case.get('functional_status', '-')} | {case['agent_status']} |"
        for case in cases
    )
    lines.extend(["", "## Not Verified In This Run", ""])
    lines.extend(f"- `{name}`" for name in sorted(unverified))
    (root / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "cases": len(cases),
                "verified": sum(case["outcome"] == "verified" for case in cases),
                "unverified_tools": len(unverified),
            }
        )
    )


def _json_write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe_evidence(value), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _load_state(directory):
    root = Path(directory).resolve()
    state = json.loads((root / "state.json").read_text())
    key = Path(state["private_auth_file"]).read_text()
    return root, state, {"X-API-Key": key}


def _e2e_request_case(request):
    """Select recorder scope only for confirmed-account chat and read lookups."""
    path = str(getattr(getattr(request, "url", None), "path", ""))
    headers = getattr(request, "headers", {}) or {}
    if path == "/chat":
        provider = str(headers.get("x-e2e-provider") or "")
        account = str(headers.get("x-e2e-account") or "")
        case_id = str(headers.get("x-e2e-case") or "")
    elif path == "/parameter-options/resolve":
        query = getattr(request, "query_params", {}) or {}
        provider = str(query.get("platform") or "")
        account = str(query.get("account_id") or "")
        header_provider = str(headers.get("x-e2e-provider") or provider)
        header_account = str(headers.get("x-e2e-account") or account)
        if (header_provider, header_account) != (provider, account):
            return {}
        case_id = str(headers.get("x-e2e-case") or "")
    else:
        return {}

    if provider not in CONFIRMED_ACCOUNTS:
        return {}
    if account not in CONFIRMED_ACCOUNTS[provider]:
        return {}
    safe_case_id = re.sub(r"[^A-Za-z0-9_.-]", "-", case_id)[:120]
    return {
        "case_id": safe_case_id or f"{provider}-parameter-options",
        "provider": provider,
        "account": account,
    }


def resolve_selection_tokens(
    directory,
    provider,
    tool_name,
    field_values,
    case_id,
    session_id,
    *,
    lookup_queries=None,
    lookup_context=None,
):
    """Resolve exact lookup values into tokens bound to the E2E session."""
    root, state, headers = _load_state(directory)
    account_ids = state.get("accounts", {}).get(provider)
    if (
        provider not in CONFIRMED_ACCOUNTS
        or account_ids != CONFIRMED_ACCOUNTS[provider]
    ):
        raise ValueError("selection lookup requires the confirmed test account")
    if not str(tool_name or "").strip() or not str(session_id or "").strip():
        raise ValueError("selection lookup requires a Tool and session ID")
    if not isinstance(field_values, dict) or not field_values:
        raise ValueError("selection lookup requires field values")
    if lookup_queries is not None and not isinstance(lookup_queries, dict):
        raise ValueError("lookup_queries must be an object")
    if lookup_context is not None and not isinstance(lookup_context, dict):
        raise ValueError("lookup_context must be an object")

    definitions = {
        binding.definition.name: binding.definition
        for binding in create_tool_source(provider).list_bindings()
    }
    definition = definitions.get(tool_name)
    if definition is None:
        raise ValueError(f"selection lookup requires a registered Tool: {tool_name}")

    resolved = {}
    for field, values in field_values.items():
        if (
            not isinstance(field, str)
            or not field.strip()
            or not isinstance(values, (list, tuple))
            or not values
        ):
            raise ValueError("selection fields must contain non-empty value lists")
        field_schema = definition.input_schema.properties.get(field)
        field_type = field_schema.get("type") if isinstance(field_schema, dict) else None
        field_types = (
            {field_type}
            if isinstance(field_type, str)
            else set(field_type)
            if isinstance(field_type, (list, tuple))
            and all(isinstance(item, str) for item in field_type)
            else set()
        )
        supported_types = {"array", "string", "integer", "number", "boolean", "object"}
        if (
            not field_types
            or not field_types <= supported_types
            or ("array" in field_types and len(field_types) > 1)
        ):
            raise ValueError(f"selection field has no supported Tool schema: {field}")
        is_array = "array" in field_types
        if not is_array and len(values) != 1:
            raise ValueError(f"scalar selection field requires exactly one value: {field}")
        queries = (
            lookup_queries.get(field, values)
            if isinstance(lookup_queries, dict) else values
        )
        if not isinstance(queries, (list, tuple)) or len(queries) != len(values):
            raise ValueError(f"lookup query count does not match values for {field}")
        tokens = []
        for expected_value, query in zip(values, queries):
            if expected_value in (None, "") or query in (None, ""):
                raise ValueError(f"selection lookup values must not be empty for {field}")
            query_params = {
                "platform": provider, "field": field, "tool_name": tool_name,
                "account_id": account_ids[0], "session_id": session_id, "query": str(query),
            }
            if lookup_context is not None:
                query_params["lookup_context"] = json.dumps(lookup_context, ensure_ascii=False)
            response = requests.get(
                state["base_url"] + "/parameter-options/resolve",
                params=query_params,
                headers={
                    **headers,
                    "X-E2E-Case": case_id,
                    "X-E2E-Provider": provider,
                    "X-E2E-Account": account_ids[0],
                },
                timeout=DEFAULT_EXECUTION_TIMEOUT_SECONDS,
            )
            if not response.ok:
                raise RuntimeError(
                    f"parameter lookup failed for {provider}.{field} "
                    f"(HTTP {response.status_code})"
                )
            try:
                options = response.json().get("options", [])
            except (AttributeError, ValueError) as error:
                raise RuntimeError(
                    f"parameter lookup returned invalid data for {provider}.{field}"
                ) from error
            matches = [
                item for item in options
                if isinstance(item, dict) and item.get("value") == expected_value
            ]
            if len(matches) != 1:
                raise ValueError(
                    f"selected value was not uniquely returned by "
                    f"{provider}.{field} lookup"
                )
            token = matches[0].get("selection_token")
            if not isinstance(token, str) or not token:
                raise ValueError(
                    f"{provider}.{field} lookup did not return a selection token"
                )
            tokens.append(token)
        resolved[field] = tokens if is_array else tokens[0]
    return resolved


def _approved_tools():
    names = []
    for provider in PROVIDERS:
        for binding in create_tool_source(provider).list_bindings():
            tool = binding.definition
            if (
                tool.action not in {"create", "update", "delete"}
                or tool.resource_type not in WRITABLE_HIERARCHY_RESOURCES
                or not tool.live_support
            ):
                continue
            fields = tool.input_schema.properties
            if (
                tool.action == "create"
                and tool.resource_type != "listing_group_filter"
                and not ({"status", "operation_status"} & set(fields))
            ):
                continue
            names.append(tool.name)
    return sorted(names)


def build_service_config(accounts, *, read_only=False, live=False):
    if accounts != CONFIRMED_ACCOUNTS:
        raise ValueError("configured accounts differ from the user-confirmed test accounts")
    if read_only and live:
        raise ValueError("read-only and live service modes are mutually exclusive")
    return {
        "execution_mode": "read_only" if read_only else "live" if live else "dry_run",
        "execution_timeout_seconds": DEFAULT_EXECUTION_TIMEOUT_SECONDS,
        "allow_live_writes": live,
        "allowed_accounts": {name: list(values) for name, values in accounts.items()},
        "live_approved_tools": _approved_tools() if live else [],
        "granted_permissions": (
            ["ads.read", "knowledge.read", "skills.read", "memory.read"]
            if read_only
            else [
                "ads.read",
                "ads.plan",
                "ads.write",
                "ads.reconcile",
                "knowledge.read",
                "skills.read",
                "memory.read",
            ]
        ),
    }


def start(directory, port, *, read_only=False, live=False):
    load_live_e2e_memory(ROOT)
    load_default_local_env()
    root = Path(directory).resolve()
    root.mkdir(parents=True, exist_ok=True)
    original = yaml.safe_load((ROOT / "agents/ad_agent/config.yaml").read_text()) or {}
    accounts = {p: original["allowed_accounts"][p] for p in PROVIDERS}
    config = build_service_config(accounts, read_only=read_only, live=live)
    config_path = root / "test-config.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    private_root = _private_directory(root)
    auth_file = private_root / "key"
    key = secrets.token_urlsafe(32)
    auth_file.write_text(key)
    auth_file.chmod(0o600)
    env = {
        **os.environ,
        "AD_AGENT_API_KEY": key,
        "AD_AGENT_ENABLE_LIVE": "1" if live else "0",
        "AD_AGENT_CONFIG_PATH": str(config_path),
        "AD_AGENT_DB_PATH": str(private_root / "test.db"),
        "AD_AGENT_SERVICE_PRINCIPAL": "campaign-e2e",
        "AD_AGENT_SERVICE_TENANT": "campaign-e2e",
    }
    process = subprocess.Popen(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "serve",
            "--directory",
            str(root),
            "--port",
            str(port),
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    state = {
        "pid": process.pid,
        "base_url": f"http://127.0.0.1:{port}",
        "private_auth_file": str(auth_file),
        "accounts": accounts,
    }
    _json_write(root / "state.json", state)
    for _ in range(120):
        if process.poll() is not None:
            raise RuntimeError("test service exited; inspect the sanitized service log")
        try:
            response = requests.get(state["base_url"] + "/readyz", timeout=2)
            if response.status_code == 200:
                print(
                    json.dumps(
                        {
                            "ready": True,
                            "pid": process.pid,
                            "base_url": state["base_url"],
                        }
                    )
                )
                return
        except requests.RequestException:
            time.sleep(1)
            continue
        time.sleep(1)
    raise TimeoutError("test service did not become ready")


def _private_directory(root):
    import tempfile

    state_file = root / "state.json"
    if state_file.is_file():
        previous = json.loads(state_file.read_text())
        private = Path(previous["private_auth_file"]).parent
        if private.is_dir():
            return private
    return Path(tempfile.mkdtemp(prefix="ad-crud-auth-"))


def _credential_values(value):
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            if (
                SENSITIVE.search(key)
                and isinstance(item, (str, int))
                and len(str(item)) >= 4
            ):
                found.append(str(item))
            found.extend(_credential_values(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_credential_values(item))
    return found


class SafeFormatter(logging.Formatter):
    def __init__(self):
        super().__init__("%(asctime)s %(levelname)s %(name)s %(message)s")
        credential_file = ROOT / "config/ad_platform_credentials.json"
        credentials = (
            json.loads(credential_file.read_text()) if credential_file.is_file() else {}
        )
        self.secrets = _credential_values(credentials) + [
            v for k, v in os.environ.items() if SENSITIVE.search(k) and len(v) >= 4
        ]

    def format(self, record):
        text = super().format(record)
        for value in self.secrets:
            text = text.replace(value, "<redacted>")
        return redact_for_persistence(text)


def _request_data(request):
    body = request.body or b""
    text = body.decode() if isinstance(body, bytes) else str(body)
    if not text:
        return {
            key: values[0] for key, values in parse_qs(urlsplit(request.url).query).items()
        }
    try:
        return json.loads(text)
    except ValueError:
        return {key: values[0] for key, values in parse_qs(text).items()}


def _walk(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def _walk_with_keys(value, parents=()):
    if isinstance(value, dict):
        yield value, parents
        for key, item in value.items():
            yield from _walk_with_keys(item, (*parents, str(key)))
    elif isinstance(value, list):
        for item in value:
            yield from _walk_with_keys(item, parents)


class ProviderRecorder:
    """Observe real transport, with extra safety restrictions for this test deployment."""

    def __init__(self, directory):
        self.root = Path(directory)
        self._case_context = ContextVar("provider_recorder_case", default=None)
        owned_path = self.root / "created-resource-ids.json"
        persisted_ids = json.loads(owned_path.read_text()) if owned_path.is_file() else []
        self.created = {
            identifier
            for value in persisted_ids
            for identifier in self._resource_identifiers(value)
        }
        typed_path = self.root / "created-resource-types.json"
        typed = json.loads(typed_path.read_text()) if typed_path.is_file() else []
        self.created_typed = {
            (row["provider"], row["account"], row["resource"], row["id"])
            for row in typed
            if isinstance(row, dict)
            and all(isinstance(row.get(key), str) for key in (
                "provider", "account", "resource", "id",
            ))
        }
        self.paused_ad_groups = set()
        self.paused_asset_groups = set()
        self.paused_campaigns = set()
        self.ad_group_campaigns = {}
        self.lock = threading.RLock()
        self.original = requests.Session.send

    @property
    def case(self):
        return self._case_context.get() or {}

    @case.setter
    def case(self, value):
        self._case_context.set(dict(value))

    def install(self):
        recorder = self

        def send(session, request, **kwargs):
            return recorder.send(session, request, **kwargs)

        requests.Session.send = send

    def _guard(self, request, provider, data):
        if not self.case or self.case.get("provider") != provider:
            raise PermissionError("Provider request outside the selected test channel")
        account = self.case["account"]
        path = urlsplit(request.url).path
        if provider == "google-ads" and f"/customers/{account}/" not in path:
            raise PermissionError("Google request outside the test account")
        if provider == "meta":
            account_path = re.search(r"/act_(\d+)(?:/|$)", path)
            if account_path and account_path.group(1) != account:
                raise PermissionError("Meta request outside the test account")
        target = data.get("advertiser_id") or data.get("account_id")
        if target and str(target).removeprefix("act_") != account:
            raise PermissionError("Provider request outside the test account")
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return
        if provider == "meta":
            if request.method == "DELETE":
                match = re.fullmatch(r"/v[\d.]+/(\d+)/?", path)
                if match is None:
                    raise PermissionError("write outside campaign hierarchy")
                self._require_typed(provider, account, match.group(1))
                return
            if request.method != "POST":
                raise PermissionError("write outside campaign hierarchy")
            if not (
                re.fullmatch(
                    rf"/v[\d.]+/act_{account}/(?:campaigns|adsets|ads)/?", path
                )
                or re.fullmatch(r"/v[\d.]+/\d+/?", path)
            ):
                raise PermissionError("write outside campaign hierarchy")
        elif provider == "tiktok":
            if request.method != "POST":
                raise PermissionError("write outside campaign hierarchy")
            action = re.fullmatch(
                r"/open_api/v[\d.]+/(?:smart_plus/)?"
                r"(campaign|adgroup|ad)/(create|update|delete|status/update)/?",
                path,
            )
            if action is None:
                raise PermissionError("write outside campaign hierarchy")
            if action.group(2) == "delete":
                field = {
                    "campaign": "campaign_ids", "ad": "ad_ids",
                    "adgroup": "adgroup_ids",
                }[action.group(1)]
                ids = data.get(field)
                if not isinstance(ids, list) or not ids:
                    raise PermissionError("delete requires owned resource IDs")
                resource = "ad_group" if action.group(1) == "adgroup" else action.group(1)
                self._require_typed(provider, account, ids, resource)
        elif provider == "google-ads":
            if (
                request.method == "POST"
                and path.rsplit("/", 1)[-1] in {
                    "googleAds:search", "googleAds:searchStream",
                }
                and isinstance(data.get("query"), str)
                and data["query"].strip()
                and set(data) <= {"query", "pageSize", "pageToken", "validateOnly"}
            ):
                return
            if request.method != "POST" or not path.endswith(":mutate"):
                raise PermissionError("write outside campaign hierarchy")
            resource = path.rsplit("/", 1)[-1].split(":", 1)[0]
            mutations = [
                (node, parents) for node, parents in _walk_with_keys(data)
                if any(key in node for key in ("create", "update", "remove"))
            ]
            if not mutations:
                raise PermissionError("write outside campaign hierarchy")
            for node, parents in mutations:
                target = resource
                if resource == "googleAds":
                    target = next(
                        (
                            GOOGLE_BATCH_OPERATIONS[key]
                            for key in reversed(parents)
                            if key in GOOGLE_BATCH_OPERATIONS
                        ),
                        "",
                    )
                if target not in GOOGLE_MUTATION_RESOURCES or (
                    target == "ads" and ("create" in node or "remove" in node)
                ):
                    raise PermissionError("write outside campaign hierarchy")
                if "remove" in node:
                    name = node["remove"]
                    match = re.fullmatch(
                        rf"customers/{account}/{target}/([^/]+)", str(name)
                    )
                    if match is None:
                        raise PermissionError("delete outside test account or hierarchy")
                    self._require_created((name, match.group(1)))
        if provider == "meta" and path.rstrip("/").endswith(
            ("/campaigns", "/adsets", "/ads")
        ):
            if data.get("status") != "PAUSED":
                raise PermissionError("Meta creation must explicitly be PAUSED")
        if provider == "google-ads":
            self._guard_google(data, path)
        if provider == "tiktok" and "/create/" in path:
            self._guard_tiktok_creation(data, path)
        if provider == "meta" and re.fullmatch(r"/v[\d.]+/\d+/?", path):
            self._require_typed(
                provider, account, path.rstrip("/").rsplit("/", 1)[-1]
            )
            self._guard_update_status(provider, data)
        if provider == "tiktok" and "/update/" in path:
            resource = "ad_group" if action.group(1) == "adgroup" else action.group(1)
            self._guard_tiktok_update(data, account, resource)

    def _require_created(self, identifiers):
        if any(str(identifier) not in self.created for identifier in identifiers):
            raise PermissionError("delete is not a resource created by this test")

    def _require_typed(self, provider, account, identifiers, resource=None):
        ids = identifiers if isinstance(identifiers, list) else [identifiers]
        allowed_resources = (
            (resource,) if resource else ("campaign", "ad_set", "ad_group", "ad")
        )
        if not ids or any(
            not any(
                (provider, account, kind, str(identifier)) in self.created_typed
                for kind in allowed_resources
            )
            for identifier in ids
        ):
            raise PermissionError("write requires typed ownership from this test")
    @staticmethod
    def _guard_tiktok_creation(data, path):
        if path.rstrip("/").endswith("/smart_plus/ad/create"):
            if str(data.get("operation_status") or "").upper() != "DISABLE":
                raise PermissionError(
                    "TikTok Smart+ Ad creation must explicitly be DISABLE"
                )
            return

        if path.rstrip("/").endswith("/ad/create"):
            creatives = data.get("creatives")
            if (
                not isinstance(creatives, list)
                or not creatives
                or any(
                    not isinstance(creative, dict)
                    or str(creative.get("operation_status") or "").upper()
                    != "DISABLE"
                    for creative in creatives
                )
            ):
                raise PermissionError(
                    "TikTok Ad creation requires every creative to explicitly be DISABLE"
                )
            return

        if str(data.get("operation_status") or "").upper() != "DISABLE":
            raise PermissionError("TikTok creation must explicitly be DISABLE")

    def _guard_google(self, data, path):
        serving_resources = {
            "campaigns": "Campaign",
            "adGroups": "Ad Group",
            "adGroupCriteria": "Product Group",
            "adGroupAds": "Ad",
            "assetGroups": "Asset Group",
        }
        path_resource = path.rsplit("/", 1)[-1].split(":", 1)[0]
        customer = re.search(r"/customers/(\d+)/", path)
        for node, parents in _walk_with_keys(data):
            create = node.get("create")
            if isinstance(create, dict):
                resource = path_resource
                if resource == "googleAds":
                    resource = next(
                        (
                            GOOGLE_BATCH_OPERATIONS[item]
                            for item in reversed(parents)
                            if item in GOOGLE_BATCH_OPERATIONS
                        ),
                        "",
                    )
                label = serving_resources.get(resource)
                if resource == "assetGroups":
                    campaign = re.fullmatch(
                        r"customers/(\d+)/campaigns/(\d+)",
                        str(create.get("campaign") or ""),
                    )
                    customer = re.search(r"/customers/(\d+)/", path)
                    if (
                        campaign is None
                        or customer is None
                        or campaign.group(1) != customer.group(1)
                        or campaign.group(2) not in self.created
                        or campaign.group(2) not in self.paused_campaigns
                    ):
                        raise PermissionError(
                            "Google Asset Group requires a created PAUSED Campaign"
                        )
                if resource == "assetGroupListingGroupFilters":
                    parent = str(create.get("assetGroup") or "")
                    match = re.fullmatch(
                        r"customers/\d+/assetGroups/(\d+)", parent
                    )
                    if (
                        match is None
                        or match.group(1) not in self.paused_asset_groups
                    ):
                        raise PermissionError(
                            "Google listing filter requires a verified PAUSED Asset Group"
                        )
                ad = create.get("ad")
                is_app_ad = isinstance(ad, dict) and isinstance(
                    ad.get("appAd") or ad.get("app_ad"),
                    dict,
                )
                if is_app_ad:
                    self._guard_google_app_ad(create, path)
                    continue
                if label and str(create.get("status") or "").upper() != "PAUSED":
                    raise PermissionError(
                        f"Google {label} creation must explicitly be PAUSED"
                    )
            update = node.get("update")
            if isinstance(update, dict):
                self._guard_update_status("google-ads", update)
                target = path_resource
                if target == "googleAds":
                    target = next(
                        (
                            GOOGLE_BATCH_OPERATIONS[item]
                            for item in reversed(parents)
                            if item in GOOGLE_BATCH_OPERATIONS
                        ),
                        "",
                    )
                resource = update.get("resourceName")
                match = re.fullmatch(
                    rf"customers/{customer.group(1)}/{target}/([^/]+)",
                    resource if isinstance(resource, str) else "",
                ) if customer and target else None
                if match is None:
                    raise PermissionError("update outside test account or hierarchy")
                numeric_ad = match.group(1) if target == "ads" else ""
                owned_ad = bool(numeric_ad) and any(
                    owned.startswith(f"customers/{customer.group(1)}/adGroupAds/")
                    and owned.endswith("~" + numeric_ad)
                    for owned in self.created
                )
                if resource not in self.created and not owned_ad:
                    raise PermissionError(
                        "update is not a resource created by this test"
                    )

    def _guard_google_app_ad(self, create, path):
        if str(create.get("status") or "").upper() != "ENABLED":
            raise PermissionError(
                "Google App Ad creation must explicitly be ENABLED"
            )
        group = re.fullmatch(
            r"customers/(\d+)/adGroups/(\d+)", str(create.get("adGroup") or ""),
        )
        customer = re.search(r"/customers/(\d+)/", path)
        campaign = re.fullmatch(
            r"customers/(\d+)/campaigns/(\d+)",
            self.ad_group_campaigns.get(group.group(2), "") if group else "",
        )
        if (
            group is None or customer is None or campaign is None
            or group.group(1) != customer.group(1)
            or campaign.group(1) != customer.group(1)
            or group.group(2) not in self.paused_ad_groups
            or campaign.group(2) not in self.paused_campaigns
        ):
            raise PermissionError(
                "Google App Ad requires verified PAUSED Ad Group and Campaign"
            )

    def _guard_tiktok_update(self, data, account, resource):
        self._guard_update_status("tiktok", data)
        fields = (
            "campaign_id",
            "adgroup_id",
            "ad_id",
            "smart_plus_ad_id",
            "campaign_ids",
            "adgroup_ids",
            "ad_ids",
        )
        ids = []
        for field in fields:
            value = data.get(field)
            ids.extend(value if isinstance(value, list) else [value] if value else [])
        self._require_typed("tiktok", account, ids, resource)

    @staticmethod
    def _guard_update_status(provider, data):
        allowed = {"DISABLE"} if provider == "tiktok" else {"PAUSED"}
        for node in _walk(data):
            for field in ("status", "operation_status"):
                value = node.get(field)
                if value is not None and str(value).upper() not in allowed:
                    raise PermissionError(
                        "test-account updates must keep delivery paused"
                    )

    def send(self, session, request, **kwargs):
        host = urlsplit(request.url).hostname
        provider = next((p for p, domain in HOSTS.items() if host == domain), None)
        if provider is None:
            return self.original(session, request, **kwargs)
        data = _request_data(request)
        self._guard(request, provider, data)
        case = dict(self.case)
        started = time.monotonic()
        try:
            response = self.original(session, request, **kwargs)
        except requests.RequestException as error:
            self._record_transport(
                case, provider, request, started, transport_error=type(error).__name__
            )
            raise
        try:
            document = response.json()
        except ValueError:
            document = {}
        if provider == "google-ads":
            if response.ok:
                self._capture_google_paused_resources(document)
        path = urlsplit(request.url).path
        creates = (
            "/create/" in path
            or (
                provider == "meta"
                and path.rstrip("/").endswith(
                    ("/campaigns", "/adsets", "/adcreatives", "/ads")
                )
            )
            or (
                provider == "google-ads"
                and ":mutate" in path
                and any("create" in node for node in _walk(data))
            )
        )
        if (
            request.method == "POST"
            and response.ok
            and creates
            and isinstance(document, dict)
            and not document.get("error")
            and document.get("code") in (None, 0)
        ):
            resource = None
            if provider == "meta":
                match = re.fullmatch(
                    r"/v[\d.]+/act_\d+/(campaigns|adsets|ads)/?", path
                )
                resource = META_CREATE_RESOURCES.get(match.group(1)) if match else None
            elif provider == "tiktok":
                match = re.fullmatch(
                    r"/open_api/v[\d.]+/(?:smart_plus/)?"
                    r"(campaign|adgroup|ad)/create/?", path
                )
                resource = (
                    "ad_group" if match.group(1) == "adgroup" else match.group(1)
                ) if match else None
            self._capture_ids(
                document, provider=provider, account=case["account"], resource=resource
            )
        payload = document.get("data") if isinstance(document, dict) else None
        payload = payload if isinstance(payload, dict) else {}
        self._record_transport(
            case,
            provider,
            request,
            started,
            http_status=response.status_code,
            provider_code=document.get("code") if isinstance(document, dict) else None,
            request_id=response.headers.get("request-id")
            or response.headers.get("x-fb-trace-id")
            or (document.get("request_id") if isinstance(document, dict) else None),
            data_keys=sorted(payload),
            collection_counts={key: len(value) for key, value in payload.items() if isinstance(value, list)},
        )
        return response

    def _record_transport(self, case, provider, request, started, **details):
        row = {
            "case_id": case.get("case_id"),
            "provider": provider,
            "method": request.method,
            "path": re.sub(r"\d{6,}", "[resource]", urlsplit(request.url).path),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            **details,
        }
        with (
            self.lock,
            (self.root / "provider-http.jsonl").open("a", encoding="utf-8") as handle,
        ):
            handle.write(json.dumps(row) + "\n")

    def _capture_ids(self, document, *, provider=None, account=None, resource=None):
        fields = {
            "id",
            "campaign_id",
            "adgroup_id",
            "adset_id",
            "ad_id",
            "ad_ids",
            "smart_plus_ad_id",
            "creative_id",
            "asset_group_id",
            "listing_group_filter_id",
            "resourceName",
        }
        for node in _walk(document):
            for field in fields:
                value = node.get(field)
                if isinstance(value, (str, int)):
                    self.created.update(self._resource_identifiers(value))
                elif isinstance(value, list):
                    for item in value:
                        self.created.update(self._resource_identifiers(item))
        _json_write(self.root / "created-resource-ids.json", sorted(self.created))
        if resource and provider in {"meta", "tiktok"} and account:
            fields = ("id",) if provider == "meta" else TIKTOK_CREATE_IDS[resource]
            for node in _walk(document):
                for field in fields:
                    value = node.get(field)
                    values = value if isinstance(value, list) else [value]
                    for identifier in values:
                        if isinstance(identifier, (str, int)) and str(identifier).isdigit():
                            self.created_typed.add(
                                (provider, str(account), resource, str(identifier))
                            )
            _json_write(
                self.root / "created-resource-types.json",
                [
                    dict(zip(("provider", "account", "resource", "id"), row))
                    for row in sorted(self.created_typed)
                ],
            )

    @staticmethod
    def _resource_identifiers(value):
        identifier = str(value)
        identifiers = {identifier}
        parts = identifier.split("/")
        if (
            len(parts) == 4
            and parts[0] == "customers"
            and parts[1].isdigit()
            and parts[2]
            and parts[3]
        ):
            identifiers.add(parts[3])
        return identifiers

    def _capture_google_paused_resources(self, document):
        for node in _walk(document):
            for keys, known_paused in (
                (("adGroup", "ad_group"), self.paused_ad_groups),
                (("assetGroup", "asset_group"), self.paused_asset_groups),
                (("campaign",), self.paused_campaigns),
            ):
                resource = next(
                    (
                        node.get(key)
                        for key in keys
                        if isinstance(node.get(key), dict)
                    ),
                    None,
                )
                if not isinstance(resource, dict) or resource.get("id") is None:
                    continue
                resource_id = str(resource["id"])
                if keys[0] == "adGroup":
                    campaign = resource.get("campaign")
                    if isinstance(campaign, str):
                        self.ad_group_campaigns[resource_id] = campaign
                    else:
                        self.ad_group_campaigns.pop(resource_id, None)
                if str(resource.get("status") or "").upper() == "PAUSED":
                    known_paused.add(resource_id)
                else:
                    known_paused.discard(resource_id)


def serve(directory, port):
    import uvicorn

    root = Path(directory)
    handler = logging.FileHandler(root / "service.log", encoding="utf-8")
    handler.setFormatter(SafeFormatter())
    logging.basicConfig(handlers=[handler], level=logging.INFO, force=True)
    recorder = ProviderRecorder(root)
    recorder.install()
    from agents.deployments.advertising.api_server import app

    @app.middleware("http")
    async def scope(request, call_next):
        token = recorder._case_context.set(_e2e_request_case(request))
        try:
            return await call_next(request)
        finally:
            recorder._case_context.reset(token)

    uvicorn.run(app, host="127.0.0.1", port=port, log_config=None)


def chat(
    directory, provider, tool, params, case_id, write=False, template_id=None,
    session_id=None, user_input=None, *, live=False,
):
    root, state, headers = _load_state(directory)
    if provider not in PROVIDERS:
        raise ValueError("unknown E2E provider")
    account = str(state["accounts"][provider][0])
    definitions = {
        binding.definition.name: binding.definition
        for binding in create_tool_source(provider).list_bindings()
    }
    definition = definitions.get(tool)
    if definition is None:
        raise ValueError("Tool is not registered for the selected test provider")
    if write and tool not in _approved_tools():
        raise ValueError("write requires an approved hierarchy Tool")
    if live and definition.is_write_tool and not write:
        raise ValueError("write Tools require the explicit --write option")
    effective_session_id = str(
        session_id or f"qa-{provider}-{case_id}"
    )
    tool_params = dict(params)
    blueprint_id = tool_params.pop("_e2e_blueprint_id", None)
    blueprint_version = tool_params.pop("_e2e_blueprint_version", None)
    if write:
        for node, parents in _walk_with_keys(tool_params):
            if "selection_tokens" in parents:
                continue
            for field, value in node.items():
                if field == "selection_tokens":
                    continue
                values = value if isinstance(value, list) else [value]
                if any(
                    isinstance(item, str)
                    and re.fullmatch(r"ps1\.[A-Za-z0-9_.-]+", item)
                    for item in values
                ):
                    raise ValueError(
                        "selection token used as a resource value; "
                        "keep the raw value and put proof in selection_tokens"
                    )
    headers = {
        **headers,
        "X-E2E-Case": case_id,
        "X-E2E-Provider": provider,
        "X-E2E-Account": account,
    }
    request_text = str(user_input or "").strip() or (
        f"请调用工具 {tool} 一次，使用本请求中的结构化参数。"
    )
    body = {
        "user_input": request_text,
        "session_id": effective_session_id,
        "account_id": account,
        "platform_params": {provider: tool_params},
        "tool_allowlist": [tool],
        "execution_mode": "live" if write or live else "dry_run",
    }
    if template_id:
        body["creation_template_id"] = str(template_id)
    if blueprint_id:
        body["creation_blueprint_id"] = blueprint_id
    if blueprint_version:
        body["creation_blueprint_version"] = blueprint_version
    evidence = {
        "provider": provider,
        "account": account,
        "tool": tool,
        "session_id": effective_session_id,
        "template_id": template_id,
        "blueprint_id": blueprint_id,
        "blueprint_version": blueprint_version,
        "params": tool_params,
        "phases": [],
    }
    case_path = root / "cases" / f"{case_id}.json"

    def request_phase(phase):
        try:
            response = requests.post(
                state["base_url"] + "/chat", json=body, headers=headers,
                timeout=DEFAULT_EXECUTION_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as error:
            evidence["phases"].append(
                {"phase": phase, "transport_error": type(error).__name__}
            )
            _json_write(case_path, evidence)
            raise
        evidence["phases"].append(
            {"phase": phase, "http_status": response.status_code, "response": payload}
        )
        evidence.update(response=payload, summary=summarize_chat(payload, tool))
        _json_write(case_path, evidence)
        return payload

    payload = request_phase("initial")
    if (
        write
        and payload.get("needs_confirmation")
        and payload.get("confirmation_payload")
    ):
        body.update(
            confirmed=True, confirmation_payload=payload["confirmation_payload"]
        )
        payload = request_phase("confirmed")
    print(json.dumps(compact_summary(payload, tool), ensure_ascii=False))
    return payload


def conversation_chat(
    directory,
    provider,
    user_input,
    case_id,
    session_id=None,
    *,
    live=False,
    allow_read_tools=True,
):
    """Test original user text through the model with only registered reads."""
    root, state, headers = _load_state(directory)
    if state.get("accounts") != CONFIRMED_ACCOUNTS or provider not in PROVIDERS:
        raise ValueError("conversation queries require the confirmed test accounts")
    if not str(user_input or "").strip():
        raise ValueError("conversation queries require user text")
    account = state["accounts"][provider][0]
    body = {
        "user_input": user_input,
        "session_id": session_id or f"qa-conversation-{provider}",
        "account_id": account,
        "execution_mode": "live" if live else "dry_run",
        "tool_allowlist": (
            [
                binding.definition.name
                for binding in create_tool_source(provider).list_bindings()
                if not binding.definition.is_write_tool
            ]
            if allow_read_tools
            else []
        ),
    }
    started = time.monotonic()
    response = requests.post(
        state["base_url"] + "/chat", json=body,
        headers={
            **headers, "X-E2E-Case": case_id,
            "X-E2E-Provider": provider, "X-E2E-Account": account,
        },
        timeout=DEFAULT_EXECUTION_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    _json_write(root / "cases" / f"{case_id}.json", {
        "provider": provider, "account": account, "user_input": user_input,
        "session_id": body["session_id"], "http_status": response.status_code,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "response": payload,
    })
    print(json.dumps({
        "case_id": case_id, "run_id": payload.get("run_id"),
        "status": payload.get("status"), "tool_call_count": payload.get("tool_call_count"),
        "tools": [{
            "name": row.get("tool"), "success": row.get("success"),
            "data_status": (row.get("data") or {}).get("data_status"),
            "error": row.get("error"),
            "counts": {
                key: len(value) for key, value in (row.get("data") or {}).items()
                if isinstance(value, list)
            },
        } for row in payload.get("results") or ()],
        "reply": payload.get("reply"),
    }, ensure_ascii=False))
    return payload


def _creation_card_params(card):
    values = {}

    def assign(target, name, value):
        parts = str(name).split(".")
        if not parts or any(not part for part in parts):
            raise ValueError("creation card has an invalid provider field")
        for part in parts[:-1]:
            target = target.setdefault(part, {})
            if not isinstance(target, dict):
                raise ValueError("creation card has conflicting provider fields")
        target[parts[-1]] = value

    for field in card.get("fields") or ():
        if not isinstance(field, dict) or field.get("visible") is False:
            continue
        value = field.get("value")
        if value is None or value == "":
            continue
        name = field.get("provider_field") or field.get("path")
        if not isinstance(name, str) or not name:
            raise ValueError("creation card field has no provider name")
        assign(values, name, value)
        tool = field.get("tool")
        if isinstance(tool, str) and tool:
            assign(values.setdefault(tool, {}), name, value)
    token_tools = card.get("selection_token_tools") or {}
    if not isinstance(token_tools, dict):
        raise ValueError("creation card selection token map is invalid")
    for field, token in (card.get("selection_tokens") or {}).items():
        tool = token_tools.get(field)
        if isinstance(tool, str) and tool and token:
            values.setdefault(tool, {}).setdefault("selection_tokens", {})[field] = token
    return values


def _ready_creation_card(payload, *, provider, account, template_id, blueprint_id):
    cards = (payload.get("ui") or {}).get("cards") or ()
    for card in cards:
        if not isinstance(card, dict) or card.get("type") != "ad_creation_form":
            continue
        if (
            card.get("provider") != provider
            or str(card.get("account_id") or "") != str(account)
            or card.get("template_id") != template_id
            or card.get("blueprint_id") != blueprint_id
        ):
            continue
        actions = card.get("actions") or ()
        if card.get("ready") is True and any(
            isinstance(action, dict) and action.get("id") == "submit_create"
            for action in actions
        ):
            return card
    return None


def template_chat(
    directory, provider, template_id, params, case_id, *,
    write=False, session_id=None, user_input=None, allow_new_hierarchy=False,
    existing_resources_reconciled=False,
):
    """Exercise the selected template without restricting the model to one Tool."""
    root, state, headers = _load_state(directory)
    if provider not in PROVIDERS or state.get("accounts") != CONFIRMED_ACCOUNTS:
        raise ValueError("template creation requires the confirmed test accounts")
    if not template_id or not isinstance(params, dict):
        raise ValueError("template creation requires a template and JSON parameters")
    account = state["accounts"][provider][0]
    response = requests.get(
        state["base_url"] + f"/creation-templates/{template_id}",
        headers=headers, timeout=DEFAULT_EXECUTION_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    template = response.json()
    if (
        template.get("provider") != provider or template.get("account_id") != account
        or template.get("status") != "active"
    ):
        raise ValueError("template provider/account is outside the confirmed test scope")
    if template.get("template_id") not in (None, template_id):
        raise ValueError("template response does not match selected template ID")
    memory_key = template.get("catalog_key") or template_id
    if not isinstance(memory_key, str):
        raise ValueError("template catalog key must be a string")
    memory = resolve_template_memory(
        ROOT,
        provider=provider,
        account_id=account,
        template_id=memory_key,
        api_template=template,
    )
    reuse_state = memory["hierarchy_reuse"]
    print(
        json.dumps(
            {
                "case_id": case_id,
                "e2e_memory_preflight": {
                    "template_id": template_id,
                    "template_key": memory_key,
                    "verification_state": memory["verification_state"],
                    "template_values_sha256": memory["template_values_sha256"],
                    "known_resource_ids": reuse_state["resource_ids"],
                    "unresolved_attempt_ids": reuse_state["unresolved_attempt_ids"],
                    "recovery_plan": memory["recovery_plan"],
                    "known_findings": [
                        {
                            "id": finding["id"],
                            "status": finding["status"],
                            "next_action": finding["next_action"],
                        }
                        for finding in memory["known_findings"]
                    ],
                },
            },
            ensure_ascii=False,
        )
    )
    if write:
        try:
            require_new_hierarchy_authorization(
                reuse_state,
                allow_new_hierarchy=allow_new_hierarchy,
                existing_resources_reconciled=existing_resources_reconciled,
                verification_state=memory["verification_state"],
                known_findings=memory["known_findings"],
            )
        except ValueError as error:
            known_ids = json.dumps(
                reuse_state.get("resource_ids", {}),
                ensure_ascii=False,
                sort_keys=True,
            )
            raise ValueError(
                f"{error}. Known resource IDs: {known_ids}. See the memory evidence "
                "refs and resume the missing child; an unresolved write always "
                "requires read reconciliation"
            ) from error
    headers = {
        **headers, "X-E2E-Case": case_id,
        "X-E2E-Provider": provider, "X-E2E-Account": account,
    }
    if provider == "google-ads" and memory_key == "google.test.app":
        default_user_input = (
            "使用 google.test.app 内置模板和表单参数创建完整 App Campaign。"
            "Campaign 与 Ad Group 必须为 PAUSED；App Ad 按 Google Ads v24 要求设为 ENABLED。"
            "不得启用父级，不得修改模板字段；完成后逐层回读并确认父级仍暂停。"
            "缺少参数时明确指出；需要确认时返回平台确认计划。"
        )
    else:
        default_user_input = (
            "使用已选内置模板和表单参数创建完整的广告系列，包含模板声明的全部下层级。"
            "严格按模板声明的各层级状态执行；广告投放层级保持暂停。"
            "不得启用 Campaign 或广告组；如模板状态与此冲突，先停止并说明，不要执行写入。"
            "不要修改表单参数；缺少参数时明确指出；需要确认时返回平台的确认计划。"
        )
    body = {
        "user_input": user_input or default_user_input,
        "session_id": session_id or f"template-{provider}-{case_id}",
        "account_id": account,
        "creation_template_id": template_id,
        "creation_blueprint_id": template["blueprint_id"],
        "creation_blueprint_version": template["blueprint_version"],
        "platform_params": {provider: params},
        "execution_mode": "live" if write else "dry_run",
    }
    evidence = {
        "provider": provider, "account": account, "template_id": template_id,
        "blueprint_id": template["blueprint_id"],
        "session_id": body["session_id"], "params": params, "phases": [],
        "native_planning": True,
        "e2e_memory": {
            "template_key": memory["template_key"],
            "blueprint_version": memory["blueprint_version"],
            "template_values_sha256": memory["template_values_sha256"],
            "verification_state": memory["verification_state"],
            "template_values_source": (
                "agents/applications/advertising/contracts/"
                "builtin_creation_templates.json"
            ),
            "remaining_gap": memory.get("remaining_gap"),
            "known_findings": memory["known_findings"],
            "latest_live_test_resources": memory.get("latest_live_test_resources"),
            "known_live_hierarchies": memory["known_live_hierarchies"],
            "observations": memory["observations"],
            "hierarchy_reuse": reuse_state,
            "recovery_plan": memory["recovery_plan"],
            "new_hierarchy_override": bool(allow_new_hierarchy),
        },
    }
    payload = {}
    submitted_creation_card = False
    attempt_id = secrets.token_hex(16)
    for index in range(5):
        phase_id = f"{attempt_id}:{index}"
        if write:
            append_live_e2e_observation(
                ROOT,
                event_type="attempt_started",
                outcome="pending",
                attempt_id=attempt_id,
                phase_id=phase_id,
                phase=index,
                provider=provider,
                account_id=account,
                template_id=memory_key,
                blueprint_version=template["blueprint_version"],
                template_values_sha256=memory["template_values_sha256"],
                case_id=case_id,
            )
        try:
            response = requests.post(
                state["base_url"] + "/chat", json=body, headers=headers,
                timeout=DEFAULT_EXECUTION_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as error:
            if write:
                append_live_e2e_observation(
                    ROOT,
                    event_type="attempt_completed",
                    outcome="ambiguous",
                    attempt_id=attempt_id,
                    phase_id=phase_id,
                    phase=index,
                    provider=provider,
                    account_id=account,
                    template_id=memory_key,
                    blueprint_version=template["blueprint_version"],
                    template_values_sha256=memory["template_values_sha256"],
                    case_id=case_id,
                    error_messages=[type(error).__name__],
                )
            evidence["phases"].append({"transport_error": type(error).__name__})
            _json_write(root / "cases" / f"{case_id}.json", evidence)
            raise
        if write:
            created_resources = _created_live_resources(payload)
            if created_resources:
                outcome = (
                    "completed"
                    if payload.get("status") in {"succeeded", "completed"}
                    else "partial"
                )
            elif payload.get("needs_confirmation") or payload.get("needs_input"):
                outcome = "awaiting_input"
            elif _live_error_messages(payload):
                outcome = "failed"
            else:
                outcome = "completed"
            append_live_e2e_observation(
                ROOT,
                event_type="attempt_completed",
                outcome=outcome,
                attempt_id=attempt_id,
                phase_id=phase_id,
                phase=index,
                provider=provider,
                account_id=account,
                template_id=memory_key,
                blueprint_version=template["blueprint_version"],
                template_values_sha256=memory["template_values_sha256"],
                case_id=case_id,
                created_resources=created_resources,
                error_messages=_live_error_messages(payload),
            )
        evidence["phases"].append({"phase": index, "response": payload})
        evidence["response"] = payload
        _json_write(root / "cases" / f"{case_id}.json", evidence)
        if write and created_resources:
            # A confirmed parent write changes the hierarchy. Continuing with
            # the original full card would replay that write, not resume it.
            evidence["partial_hierarchy_stop"] = created_resources
            _json_write(root / "cases" / f"{case_id}.json", evidence)
            break
        card = _ready_creation_card(
            payload, provider=provider, account=account,
            template_id=template_id, blueprint_id=template["blueprint_id"],
        )
        if (
            not submitted_creation_card
            and payload.get("needs_input")
            and not payload.get("needs_confirmation")
            and card is not None
        ):
            body["user_input"] = f"提交“{card.get('title') or provider + '广告'}”创建计划"
            body["platform_params"] = {provider: _creation_card_params(card)}
            submitted_creation_card = True
            continue
        approval = payload.get("confirmation_payload")
        if not (write and payload.get("needs_confirmation") and isinstance(approval, dict)):
            break
        body["confirmed"] = True
        body["confirmation_payload"] = approval
    print(json.dumps({
        "case_id": case_id, "status": payload.get("status"),
        "phases": len(evidence["phases"]),
        "tools": [
            {"name": item.get("tool"), "success": item.get("success"), "error": item.get("error")}
            for item in payload.get("results") or ()
        ],
        "needs_input": payload.get("needs_input"),
        "needs_confirmation": payload.get("needs_confirmation"),
    }, ensure_ascii=False))
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("start", "serve", "chat", "conversation", "template", "catalog", "stop", "report")
    )
    parser.add_argument("--directory", required=True)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--provider", choices=PROVIDERS)
    parser.add_argument("--tool")
    parser.add_argument("--params", default="{}")
    parser.add_argument("--case-id", default="probe")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--read-only", action="store_true")
    parser.add_argument(
        "--live",
        action="store_true",
        help="explicitly enable live mode for an allowlisted test-account service",
    )
    parser.add_argument(
        "--no-tools",
        action="store_true",
        help="disable Tool execution for knowledge, Skill, or Memory dialogue probes",
    )
    parser.add_argument("--blueprint-id")
    parser.add_argument("--blueprint-version")
    parser.add_argument("--template-id")
    parser.add_argument(
        "--allow-new-hierarchy",
        action="store_true",
        help="explicitly authorize another paused hierarchy after checking the memory ledger",
    )
    parser.add_argument(
        "--confirm-resource-readback",
        action="store_true",
        help="confirm that every known hierarchy resource was read back before creating another",
    )
    parser.add_argument("--session-id")
    parser.add_argument(
        "--user-input",
        help="Exact user text for an existing workflow step, such as submitting a creation card.",
    )
    args = parser.parse_args()
    if args.command == "start":
        start(
            args.directory, args.port, read_only=args.read_only, live=args.live
        )
    elif args.command == "serve":
        serve(args.directory, args.port)
    elif args.command == "chat":
        params = json.loads(args.params)
        if args.blueprint_id:
            params["_e2e_blueprint_id"] = args.blueprint_id
        if args.blueprint_version:
            params["_e2e_blueprint_version"] = args.blueprint_version
        chat(
            args.directory,
            args.provider,
            args.tool,
            params,
            args.case_id,
            args.write,
            args.template_id,
            args.session_id,
            args.user_input,
            live=args.live,
        )
    elif args.command == "conversation":
        conversation_chat(
            args.directory, args.provider, args.user_input, args.case_id,
            args.session_id, live=args.live, allow_read_tools=not args.no_tools,
        )
    elif args.command == "template":
        template_chat(
            args.directory, args.provider, args.template_id,
            json.loads(args.params), args.case_id, write=args.write,
            session_id=args.session_id, user_input=args.user_input,
            allow_new_hierarchy=args.allow_new_hierarchy,
            existing_resources_reconciled=args.confirm_resource_readback,
        )
    elif args.command == "report":
        report(args.directory)
    else:
        root, state, headers = _load_state(args.directory)
        if args.command == "catalog":
            response = requests.get(
                state["base_url"] + "/tools", headers=headers,
                timeout=DEFAULT_EXECUTION_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            tools = [
                item
                for item in response.json()["tools"]
                if not args.provider or item["platform"] == args.provider
            ]
            _json_write(root / "tools.json", tools)
            print(json.dumps(tools, ensure_ascii=False))
        else:
            import signal

            os.kill(state["pid"], signal.SIGTERM)
            Path(state["private_auth_file"]).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
