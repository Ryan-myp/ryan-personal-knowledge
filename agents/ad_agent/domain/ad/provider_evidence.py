"""Validated, redacted summaries for controlled Provider E2E evidence.

The evidence file is intentionally declarative.  It is not a replay script and
never contains raw Provider responses or credentials.  This module gives the
release gate one conservative interpretation of that file:

* ``live_verified`` means the declared run has no rejected operation;
* ``partial_live_verified`` and provider-limited runs remain visible but never
  promote a campaign type to fully verified;
* summaries expose only account suffixes and operation outcomes.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterator, Mapping

from ...core.namespace import normalize_namespace as normalize_platform


SUPPORTED_RUN_STATUSES = {
    "live_verified",
    "partial_live_verified",
    "provider_limited",
    "live_verified_with_provider_limits",
}
SUPPORTED_OPERATION_STATES = {
    "passed",
    "provider_rejected",
    "not_run",
    "unknown",
    "failed",
    "skipped",
}
_REQUIRED_SAFETY = {
    "test_accounts_only": True,
    "new_resources_paused": True,
    "deleted": False,
    "credentials_included": False,
    "raw_provider_responses_included": False,
}
_CREDENTIAL_KEYS = {
    "access_token",
    "refresh_token",
    "client_secret",
    "app_secret",
    "private_key",
    "developer_token",
    "bc_id",
    "partner_id",
    "perter_id",
    "mcc",
    "password",
}


def _redacted_id(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "missing"
    return f"…{text[-4:]}" if len(text) > 4 else "configured"


def _walk_keys(value: Any, path: str = "") -> Iterator[tuple[str, str]]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            current = f"{path}.{key}" if path else str(key)
            yield current, str(key).strip().lower()
            yield from _walk_keys(child, current)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_keys(child, f"{path}[{index}]")


def _campaign_types(run: Mapping[str, Any]) -> list[str]:
    single = str(run.get("campaign_type") or "").strip()
    if single:
        return [single]
    values = run.get("campaign_types")
    if isinstance(values, list):
        return sorted({
            str(value).strip()
            for value in values
            if str(value).strip()
        })
    return []


def _iter_resource_records(
    resources: Mapping[str, Any],
    path: tuple[str, ...] = (),
) -> Iterator[tuple[str, Mapping[str, Any]]]:
    """Yield leaf resource records from Meta/TikTok and Google shapes."""
    if not isinstance(resources, Mapping):
        return
    if "create" in resources or "update" in resources:
        yield ".".join(path) or "resource", resources
        return
    for name, child in resources.items():
        if isinstance(child, Mapping):
            yield from _iter_resource_records(child, (*path, str(name)))


def validate_provider_evidence(raw: Mapping[str, Any]) -> list[str]:
    """Return deterministic contract errors without exposing secret values."""
    errors: list[str] = []
    if not isinstance(raw, Mapping):
        return ["provider evidence must be an object"]

    for path, key in _walk_keys(raw):
        if key in _CREDENTIAL_KEYS or "token" in key or "secret" in key:
            errors.append(f"{path}: credential-shaped field is not allowed")

    if str(raw.get("schema_version") or "") != "1.0":
        errors.append("schema_version must be '1.0'")
    if not str(raw.get("generated_at") or "").strip():
        errors.append("generated_at is required")
    if not str(raw.get("scope") or "").strip():
        errors.append("scope is required")

    safety = raw.get("safety")
    if not isinstance(safety, Mapping):
        errors.append("safety must be an object")
    else:
        for key, expected in _REQUIRED_SAFETY.items():
            if safety.get(key) is not expected:
                errors.append(
                    f"safety.{key} must be {str(expected).lower()}"
                )

    runs = raw.get("runs")
    if not isinstance(runs, list) or not runs:
        errors.append("runs must be a non-empty array")
        return errors

    for index, run in enumerate(runs):
        prefix = f"runs[{index}]"
        if not isinstance(run, Mapping):
            errors.append(f"{prefix} must be an object")
            continue
        provider = normalize_platform(str(run.get("provider") or "").strip())
        if not provider:
            errors.append(f"{prefix}.provider is required")
        if not str(run.get("test_account") or "").strip():
            errors.append(f"{prefix}.test_account is required")
        status = str(run.get("status") or "").strip()
        if status not in SUPPORTED_RUN_STATUSES:
            errors.append(
                f"{prefix}.status must be one of {sorted(SUPPORTED_RUN_STATUSES)}"
            )
        campaign_types = _campaign_types(run)
        if not campaign_types:
            errors.append(f"{prefix}.campaign_type(s) is required")
        resources = run.get("resources")
        if not isinstance(resources, Mapping):
            errors.append(f"{prefix}.resources must be an object")
            continue

        operation_count = 0
        passed_count = 0
        rejected_count = 0
        for resource_path, record in _iter_resource_records(resources):
            for action in ("create", "update"):
                if action not in record:
                    continue
                operation_count += 1
                state = str(record.get(action) or "").strip()
                if state not in SUPPORTED_OPERATION_STATES:
                    errors.append(
                        f"{prefix}.resources.{resource_path}.{action} has unsupported state "
                        f"{state!r}"
                    )
                if state == "passed":
                    passed_count += 1
                    if not str(record.get("id") or "").strip():
                        errors.append(
                            f"{prefix}.resources.{resource_path}.{action} "
                            "passed but id is missing"
                        )
                elif state in {"provider_rejected", "failed", "unknown"}:
                    rejected_count += 1
        if operation_count == 0:
            errors.append(f"{prefix}.resources must contain create/update outcomes")
        if status == "live_verified" and rejected_count:
            errors.append(
                f"{prefix}.status live_verified conflicts with rejected/unknown operations"
            )
        if status == "live_verified" and passed_count == 0:
            errors.append(f"{prefix}.status live_verified has no passed operation")

    return list(dict.fromkeys(errors))


def _operation_summary(
    runs: list[Mapping[str, Any]],
) -> dict[str, dict[str, int]]:
    counters: dict[str, Counter[str]] = defaultdict(Counter)
    for run in runs:
        resources = run.get("resources")
        if not isinstance(resources, Mapping):
            continue
        for resource_path, record in _iter_resource_records(resources):
            for action in ("create", "update"):
                if action in record:
                    counters[f"{resource_path}:{action}"][
                        str(record.get(action) or "unknown")
                    ] += 1
    return {
        key: dict(sorted(counter.items()))
        for key, counter in sorted(counters.items())
    }


def build_provider_evidence_report(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Build a safe provider/campaign/resource evidence matrix."""
    errors = validate_provider_evidence(raw)
    if errors:
        return {
            "format_version": 1,
            "valid": False,
            "errors": errors,
            "run_count": 0,
            "providers": {},
        }

    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for run in raw["runs"]:
        provider = normalize_platform(str(run["provider"]))
        grouped[provider].append(run)

    provider_reports: dict[str, Any] = {}
    for provider, runs in sorted(grouped.items()):
        statuses = Counter(str(run["status"]) for run in runs)
        campaign_types = sorted({
            campaign_type
            for run in runs
            for campaign_type in _campaign_types(run)
        })
        fully_verified_types = sorted({
            campaign_type
            for run in runs
            if run["status"] == "live_verified"
            for campaign_type in _campaign_types(run)
        })
        limited_types = sorted({
            campaign_type
            for run in runs
            if run["status"] != "live_verified"
            for campaign_type in _campaign_types(run)
        })
        accounts = sorted({
            _redacted_id(run.get("test_account"))
            for run in runs
        })
        provider_reports[provider] = {
            "run_count": len(runs),
            "status_counts": dict(sorted(statuses.items())),
            "fully_verified_runs": statuses.get("live_verified", 0),
            "partial_runs": statuses.get("partial_live_verified", 0),
            "limited_runs": (
                statuses.get("provider_limited", 0)
                + statuses.get("live_verified_with_provider_limits", 0)
            ),
            "campaign_types": campaign_types,
            "fully_verified_campaign_types": fully_verified_types,
            "limited_campaign_types": limited_types,
            "account_previews": accounts,
            "operations": _operation_summary(runs),
        }

    return {
        "format_version": 1,
        "valid": True,
        "errors": [],
        "generated_at": str(raw.get("generated_at") or ""),
        "scope": str(raw.get("scope") or ""),
        "safety": {
            key: bool(raw["safety"][key])
            for key in _REQUIRED_SAFETY
        },
        "run_count": len(raw["runs"]),
        "providers": provider_reports,
    }


def load_provider_evidence(path: str | Path) -> dict[str, Any]:
    """Load and summarize a JSON evidence file without returning raw payloads."""
    evidence_path = Path(path)
    try:
        raw = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "format_version": 1,
            "valid": False,
            "errors": [f"unable to load provider evidence: {type(exc).__name__}"],
            "run_count": 0,
            "providers": {},
        }
    return build_provider_evidence_report(raw)
