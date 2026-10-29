"""Load, validate, and append durable test-account live E2E memory."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

from agents.agent_harness.redaction import redact_for_persistence


MEMORY_RELATIVE_PATH = Path(
    "agents/tools/advertising/contracts/provider_live_e2e_memory.json"
)
OBSERVATIONS_RELATIVE_PATH = Path(
    "agents/tools/advertising/contracts/provider_live_e2e_observations.jsonl"
)
TEMPLATE_RELATIVE_PATH = Path(
    "agents/applications/advertising/contracts/builtin_creation_templates.json"
)
RESOURCE_TYPES = {
    "campaign",
    "ad_group",
    "ad_set",
    "ad",
    "creative",
    "asset_group",
    "product_group",
    "listing_group_filter",
    "creative_portfolio",
}
OBSERVATION_EVENTS = {"attempt_started", "attempt_completed", "attempt_reconciled"}
OBSERVATION_OUTCOMES = {
    "pending",
    "awaiting_input",
    "completed",
    "partial",
    "provider_rejected",
    "failed",
    "ambiguous",
    "no_write",
}
_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_TOKEN_VALUE_RE = re.compile(
    r"(?i)\b(access[_-]?token|refresh[_-]?token|developer[_-]?token|"
    r"client[_-]?secret|app[_-]?secret|authorization)\s*[:=]\s*"
    r"([^\s,;&]+)"
)
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object in {path}")
    return value


def _template_digest(values: Any) -> str:
    encoded = json.dumps(
        values,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_observations(repository_root: Path) -> list[dict[str, Any]]:
    path = Path(repository_root) / OBSERVATIONS_RELATIVE_PATH
    if not path.exists():
        return []
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"invalid live E2E observation at {path}:{line_number}"
            ) from error
        if not isinstance(row, dict):
            raise ValueError(
                f"live E2E observation must be an object at {path}:{line_number}"
            )
        if row.get("event_type") not in OBSERVATION_EVENTS:
            raise ValueError(
                f"unknown live E2E observation event at {path}:{line_number}"
            )
        rows.append(row)
    return rows


def _safe_error_message(value: Any) -> str:
    message = str(value or "")
    message = str(redact_for_persistence(message))
    message = _TOKEN_VALUE_RE.sub(r"\1=<redacted>", message)
    message = _URL_RE.sub("<url>", message)
    return message[:500]


def _normalize_resources(resources: Any) -> list[dict[str, str]]:
    if not isinstance(resources, list):
        raise ValueError("created_resources must be a list")
    normalized = []
    seen = set()
    for resource in resources:
        if not isinstance(resource, dict):
            raise ValueError("created resource evidence must be an object")
        resource_type = resource.get("resource_type")
        resource_id = resource.get("id")
        if resource_type not in RESOURCE_TYPES or not isinstance(resource_id, (str, int)):
            raise ValueError("created resource evidence has an invalid type or ID")
        identifier = str(resource_id).strip()
        if not identifier or len(identifier) > 200:
            raise ValueError("created resource evidence has an invalid ID")
        key = (resource_type, identifier)
        if key in seen:
            continue
        seen.add(key)
        row = {"resource_type": resource_type, "id": identifier}
        status = resource.get("status")
        if isinstance(status, (str, int)):
            row["status"] = str(status)[:80]
        normalized.append(row)
    return normalized


def _configured_test_accounts(value: Any) -> set[str]:
    """Normalize the backward-compatible single-account and multi-account scopes."""
    values = [value] if isinstance(value, str) else value
    if not isinstance(values, list) or not values:
        raise ValueError("live E2E test-account scope must be a non-empty string or list")
    accounts = [str(item).strip() for item in values]
    if any(not account for account in accounts) or len(set(accounts)) != len(accounts):
        raise ValueError("live E2E test-account scope contains blank or duplicate IDs")
    return set(accounts)


def _finding_applies_to(
    finding: dict[str, Any], *, provider: str, campaign_type: str,
    account_id: str,
) -> bool:
    """Match type-wide findings and optional account-scoped findings."""
    return any(
        isinstance(scope, dict)
        and scope.get("provider") == provider
        and scope.get("campaign_type") == campaign_type
        and scope.get("test_account") in (None, account_id)
        for scope in finding.get("applies_to", [])
    )


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )
    if len(payload) > 16_384:
        raise ValueError("live E2E observation exceeds the size limit")
    descriptor = os.open(
        path,
        os.O_CREAT | os.O_APPEND | os.O_WRONLY,
        0o600,
    )
    try:
        written = os.write(descriptor, payload)
    finally:
        os.close(descriptor)
    if written != len(payload):
        raise OSError("incomplete append to live E2E observation journal")


def append_live_e2e_observation(
    repository_root: Path,
    *,
    event_type: str,
    attempt_id: str,
    phase_id: str,
    phase: int,
    provider: str,
    account_id: str,
    template_id: str,
    blueprint_version: str,
    template_values_sha256: str,
    case_id: str,
    outcome: str,
    created_resources: Any = None,
    error_messages: Any = (),
    reconciliation_case_id: str | None = None,
) -> dict[str, Any]:
    """Append a minimal redacted live-test event; never persist raw Tool payloads."""
    root = Path(repository_root)
    if event_type not in OBSERVATION_EVENTS:
        raise ValueError("unsupported live E2E observation event")
    if outcome not in OBSERVATION_OUTCOMES:
        raise ValueError("unsupported live E2E observation outcome")
    if not attempt_id or len(attempt_id) > 120 or not phase_id or len(phase_id) > 160:
        raise ValueError("live E2E attempt identifiers are invalid")
    if not isinstance(phase, int) or phase < 0:
        raise ValueError("live E2E phase must be a non-negative integer")

    memory = load_live_e2e_memory(root)
    record = next(
        (item for item in memory["campaign_types"] if item.get("template_key") == template_id),
        None,
    )
    if record is None:
        raise ValueError(f"template has no durable live E2E memory: {template_id}")
    account_scope = _configured_test_accounts(
        memory["scope"]["test_accounts"].get(provider)
    )
    if (
        record.get("provider") != provider
        or account_id not in account_scope
        or record.get("test_account") != account_id
    ):
        raise ValueError("live E2E observation is outside the confirmed test account")
    if (
        record.get("blueprint_version") != blueprint_version
        or record.get("template_values_sha256") != template_values_sha256
    ):
        raise ValueError("live E2E observation does not match the locked template")
    if event_type == "attempt_started" and outcome != "pending":
        raise ValueError("started live E2E attempts must be pending")
    if event_type == "attempt_reconciled":
        if outcome != "no_write":
            raise ValueError("no-write reconciliation requires a no_write outcome")
        if (
            not isinstance(reconciliation_case_id, str)
            or not reconciliation_case_id.strip()
            or len(reconciliation_case_id) > 160
            or reconciliation_case_id == case_id
        ):
            raise ValueError("no-write reconciliation requires a distinct readback case")
        prior = [
            item for item in _read_observations(root)
            if item.get("attempt_id") == attempt_id
            and item.get("phase_id") == phase_id
        ]
        if (
            not any(
                item.get("event_type") == "attempt_completed"
                and item.get("outcome") == "ambiguous"
                and item.get("provider") == provider
                and item.get("account_id") == account_id
                and item.get("template_id") == template_id
                for item in prior
            )
            or any(item.get("event_type") == "attempt_reconciled" for item in prior)
        ):
            raise ValueError("reconciliation requires an unreconciled ambiguous attempt")
    elif reconciliation_case_id is not None:
        raise ValueError("readback evidence is only valid for reconciliation")

    errors = error_messages if isinstance(error_messages, list) else []
    row = {
        "schema_version": "1.0.0",
        "event_type": event_type,
        "attempt_id": attempt_id,
        "phase_id": phase_id,
        "phase": phase,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "provider": provider,
        "account_id": account_id,
        "template_id": template_id,
        "blueprint_version": blueprint_version,
        "template_values_sha256": template_values_sha256,
        "case_id": str(case_id)[:160],
        "outcome": outcome,
        "created_resources": (
            _normalize_resources(
                [] if created_resources is None else created_resources
            )
            if event_type == "attempt_completed"
            else []
        ),
        "error_messages": (
            [_safe_error_message(message) for message in errors[:5] if message]
            if event_type == "attempt_completed"
            else []
        ),
    }
    if event_type == "attempt_reconciled":
        row["reconciliation_case_id"] = reconciliation_case_id
    _append_jsonl(root / OBSERVATIONS_RELATIVE_PATH, row)
    return row


def _hierarchy_resources(record: dict[str, Any]) -> list[dict[str, Any]]:
    hierarchies = record.get("known_live_hierarchies")
    if not isinstance(hierarchies, list):
        return []
    return [row for row in hierarchies if isinstance(row, dict)]


def _template_locks(record: dict[str, Any]) -> set[tuple[str, str]]:
    locks = {
        (
            str(record.get("blueprint_version") or ""),
            str(record.get("template_values_sha256") or ""),
        )
    }
    history = record.get("historical_template_locks", [])
    if not isinstance(history, list):
        raise ValueError("historical template locks must be a list")

    for lock in history:
        if not isinstance(lock, dict):
            raise ValueError("historical template lock must be an object")
        version = lock.get("blueprint_version")
        digest = lock.get("template_values_sha256")
        evidence_refs = lock.get("evidence_refs")
        if (
            not isinstance(version, str)
            or not version
            or not isinstance(digest, str)
            or not _SHA256_RE.fullmatch(digest)
            or not isinstance(evidence_refs, list)
            or not evidence_refs
            or any(not isinstance(reference, str) or not reference for reference in evidence_refs)
        ):
            raise ValueError("historical template lock is incomplete or invalid")
        pair = (version, digest)
        if pair in locks:
            raise ValueError("historical template lock duplicates an existing lock")
        locks.add(pair)
    return locks


def hierarchy_reuse_state(
    record: dict[str, Any],
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Determine whether a new full hierarchy risks duplicating prior live work."""
    resources_by_type: dict[str, list[str]] = {}
    known_hierarchies = _hierarchy_resources(record)

    for hierarchy in known_hierarchies:
        resource_ids = hierarchy.get("resource_ids") or {}
        if not isinstance(resource_ids, dict):
            continue
        for resource_type, resource_id in resource_ids.items():
            if resource_type in RESOURCE_TYPES and resource_id:
                resources_by_type.setdefault(resource_type, []).append(str(resource_id))

    events_by_phase: dict[str, list[dict[str, Any]]] = {}
    for event in observations:
        if not isinstance(event, dict):
            continue
        events_by_phase.setdefault(str(event.get("phase_id") or ""), []).append(event)
        for resource in event.get("created_resources") or []:
            if not isinstance(resource, dict):
                continue
            resource_type = resource.get("resource_type")
            resource_id = resource.get("id")
            if resource_type in RESOURCE_TYPES and resource_id:
                resources_by_type.setdefault(resource_type, []).append(str(resource_id))

    unresolved_attempt_ids = set()
    completed_outcomes = set()
    for events in events_by_phase.values():
        started = any(item.get("event_type") == "attempt_started" for item in events)
        reconciled = any(
            item.get("event_type") == "attempt_reconciled"
            and item.get("outcome") == "no_write"
            and item.get("reconciliation_case_id")
            for item in events
        )
        completion_rows = [
            item for item in events if item.get("event_type") == "attempt_completed"
        ]
        if started and not completion_rows and not reconciled:
            unresolved_attempt_ids.update(
                str(item.get("attempt_id"))
                for item in events
                if item.get("attempt_id")
            )
        for item in completion_rows:
            if (
                item.get("outcome") == "ambiguous"
                and item.get("attempt_id")
                and not reconciled
            ):
                unresolved_attempt_ids.add(str(item["attempt_id"]))
            if item.get("outcome"):
                completed_outcomes.add(str(item["outcome"]))

    flattened_ids = {
        resource_type: list(dict.fromkeys(resource_ids))
        for resource_type, resource_ids in resources_by_type.items()
    }
    prior_write = bool(
        record.get("prior_live_write_observed")
        or record.get("latest_live_test_resources")
        or known_hierarchies
        or flattened_ids
    )
    return {
        "prior_live_write_observed": prior_write,
        "requires_reconciliation": prior_write or bool(unresolved_attempt_ids),
        "resource_ids": {
            resource_type: resource_ids[-1]
            for resource_type, resource_ids in flattened_ids.items()
        },
        "known_hierarchies": known_hierarchies,
        "unresolved_attempt_ids": sorted(unresolved_attempt_ids),
        "recent_outcomes": sorted(completed_outcomes),
    }


def require_new_hierarchy_authorization(
    reuse_state: dict[str, Any],
    *,
    allow_new_hierarchy: bool,
    existing_resources_reconciled: bool = False,
    verification_state: str | None = None,
    known_findings: list[dict[str, Any]] = (),
) -> None:
    """Fail closed on unresolved writes and implicit hierarchy duplication."""
    if reuse_state.get("unresolved_attempt_ids"):
        raise ValueError(
            "a previous live write has an ambiguous outcome; reconcile its resource "
            "IDs before any retry"
        )
    if verification_state == "blocked_by_provider":
        raise ValueError(
            "this template has a known Provider block; do not repeat the full "
            "hierarchy create to rediscover it"
        )
    unresolved_findings = [
        finding for finding in known_findings if finding.get("status") == "unresolved"
    ]
    if unresolved_findings:
        finding = unresolved_findings[0]
        raise ValueError(
            "this template has an unresolved known failure; resume the existing "
            f"hierarchy and follow its recovery instruction: {finding.get('next_action')}"
        )
    if reuse_state.get("requires_reconciliation") and not allow_new_hierarchy:
        raise ValueError(
            "durable memory shows prior live writes; reuse or reconcile the existing "
            "test-account hierarchy before creating another"
        )
    if (
        reuse_state.get("requires_reconciliation")
        and allow_new_hierarchy
        and not existing_resources_reconciled
    ):
        raise ValueError(
            "confirm a readback reconciliation of all known resources before "
            "authorizing a new hierarchy"
        )


def load_live_e2e_memory(repository_root: Path) -> dict[str, Any]:
    """Validate every in-scope template lock and the durable observation journal."""
    root = Path(repository_root)
    memory = _read_json(root / MEMORY_RELATIVE_PATH)
    template_document = _read_json(root / TEMPLATE_RELATIVE_PATH)
    scope = memory.get("scope") or {}
    test_accounts = scope.get("test_accounts")
    if not isinstance(test_accounts, dict) or not test_accounts:
        raise ValueError("live E2E memory has no confirmed test-account map")
    if memory.get("safety", {}).get("test_accounts_only") is not True:
        raise ValueError("live E2E memory must be restricted to test accounts")
    if memory.get("safety", {}).get("new_campaign_hierarchy_must_remain_paused") is not True:
        raise ValueError("live E2E memory must require paused resource hierarchies")

    templates = {
        item.get("key"): item
        for item in template_document.get("templates", [])
        if isinstance(item, dict) and item.get("key")
    }
    rows = memory.get("campaign_types")
    if not isinstance(rows, list) or not rows:
        raise ValueError("live E2E memory has no campaign type records")

    declared_types = scope.get("providers")
    if not isinstance(declared_types, dict):
        raise ValueError("live E2E memory has no declared campaign type scope")
    expected_scopes = set()
    for provider, campaign_types in declared_types.items():
        if (
            provider not in test_accounts
            or not isinstance(campaign_types, list)
            or not campaign_types
        ):
            raise ValueError("live E2E memory has an invalid declared campaign type scope")
        expected_scopes.update(
            (provider, campaign_type, account_id)
            for campaign_type in campaign_types
            for account_id in _configured_test_accounts(test_accounts[provider])
        )
    for exclusion in scope.get("excluded", []):
        if isinstance(exclusion, dict):
            excluded_pair = (
                exclusion.get("provider"), exclusion.get("campaign_type")
            )
            excluded_account = exclusion.get("test_account")
            expected_scopes = {
                item for item in expected_scopes
                if (item[0], item[1]) != excluded_pair
                or (excluded_account and item[2] != excluded_account)
            }

    actual_scopes = {
        (record.get("provider"), record.get("campaign_type"), record.get("test_account"))
        for record in rows
        if isinstance(record, dict)
    }
    if len(actual_scopes) != len(rows) or actual_scopes != expected_scopes:
        raise ValueError(
            "live E2E memory does not cover the declared campaign type scope for each account"
        )

    seen_keys = set()
    for record in rows:
        key = record.get("template_key")
        if not isinstance(key, str) or key in seen_keys:
            raise ValueError("live E2E memory has a missing or duplicate template key")
        seen_keys.add(key)
        template = templates.get(key)
        if template is None:
            raise ValueError(f"live E2E template is missing: {key}")
        provider = record.get("provider")
        trusted_accounts = _configured_test_accounts(test_accounts.get(provider))
        if record.get("test_account") not in trusted_accounts:
            raise ValueError(f"live E2E test account metadata drift: {key}")
        if (
            provider != template.get("provider")
            or record.get("blueprint_id") != template.get("blueprint_id")
            or record.get("blueprint_version") != template.get("blueprint_version")
        ):
            raise ValueError(f"live E2E template metadata drift: {key}")
        if template.get("account_id") != record.get("test_account"):
            raise ValueError(f"live E2E template test account scope drift: {key}")
        if record.get("template_values_sha256") != _template_digest(
            template.get("values")
        ):
            raise ValueError(f"live E2E template parameter digest drift: {key}")
        _template_locks(record)
        for field, expected in record.get("expected_status_values", {}).items():
            if template.get("values", {}).get(field) != expected:
                raise ValueError(f"live E2E paused status drift for {key}.{field}")
        for field in record.get("critical_fields", []):
            if field not in template.get("values", {}):
                raise ValueError(
                    f"live E2E critical template field is missing: {key}.{field}"
                )
        live_resources = record.get("latest_live_test_resources")
        if live_resources is not None:
            required_resource_ids = ("account_id", "campaign_id", "ad_group_id", "ad_id")
            if any(not live_resources.get(field) for field in required_resource_ids):
                raise ValueError(f"live E2E resource IDs are incomplete: {key}")
            if live_resources.get("delivery_status") != record.get("creation_status"):
                raise ValueError(f"live E2E resource status drift: {key}")
        prior_live_write = record.get("prior_live_write_observed")
        if not isinstance(prior_live_write, bool):
            raise ValueError(f"live E2E write history must be explicit: {key}")
        hierarchies = record.get("known_live_hierarchies")
        if not isinstance(hierarchies, list):
            raise ValueError(f"live E2E resource history must be a list: {key}")
        if prior_live_write and not hierarchies:
            raise ValueError(f"live E2E resource history is missing: {key}")
        if not prior_live_write and (
            hierarchies
            or record.get("verification_state") not in {
                "not_run", "blocked_by_provider",
            }
        ):
            raise ValueError(f"unstarted live E2E template has unexpected write history: {key}")
        for hierarchy in hierarchies:
            if not isinstance(hierarchy, dict) or not hierarchy.get("evidence_ref"):
                raise ValueError(f"live E2E resource history lacks evidence: {key}")
            resource_ids = hierarchy.get("resource_ids")
            if not isinstance(resource_ids, dict) or not resource_ids:
                raise ValueError(f"live E2E resource history lacks IDs: {key}")
            if any(
                resource_type not in RESOURCE_TYPES or not resource_id
                for resource_type, resource_id in resource_ids.items()
            ):
                raise ValueError(f"live E2E resource history has invalid IDs: {key}")
        if (
            record.get("verification_state") != "live_verified"
            and not record.get("remaining_gap")
        ):
            raise ValueError(f"unverified live E2E template needs a remaining gap: {key}")

    scoped_campaign_types = {
        (record.get("provider"), record.get("campaign_type")) for record in rows
    }
    findings = memory.get("known_findings")
    if not isinstance(findings, list):
        raise ValueError("live E2E memory has no structured known findings")
    for finding in findings:
        if (
            not isinstance(finding, dict)
            or not isinstance(finding.get("applies_to"), list)
            or not finding["applies_to"]
        ):
            raise ValueError("live E2E finding must declare its provider and type scope")
        if any(
            not isinstance(scope, dict)
            or (scope.get("provider"), scope.get("campaign_type"))
            not in scoped_campaign_types
            or (
                scope.get("test_account") is not None
                and scope.get("test_account")
                not in _configured_test_accounts(
                    test_accounts.get(scope.get("provider"))
                )
            )
            for scope in finding["applies_to"]
        ):
            raise ValueError("live E2E finding scope references an unsupported type")

    for record in rows:
        if record.get("verification_state") != "blocked_by_provider":
            continue
        if not any(
            finding.get("status") == "provider_limited"
            and _finding_applies_to(
                finding,
                provider=record["provider"],
                campaign_type=record["campaign_type"],
                account_id=record["test_account"],
            )
            for finding in findings
        ):
            raise ValueError(
                "provider-blocked live E2E template needs a matching scoped finding"
            )

    for observation in _read_observations(root):
        record = next(
            (
                item
                for item in rows
                if item.get("template_key") == observation.get("template_id")
            ),
            None,
        )
        trusted_locks = _template_locks(record) if record is not None else set()
        if (
            record is None
            or observation.get("provider") != record.get("provider")
            or observation.get("account_id") != record.get("test_account")
            or (
                observation.get("blueprint_version"),
                observation.get("template_values_sha256"),
            )
            not in trusted_locks
        ):
            raise ValueError(
                "live E2E observation does not match a current or registered "
                "historical template lock"
            )
    return memory


def resolve_template_memory(
    repository_root: Path,
    *,
    provider: str,
    account_id: str,
    template_id: str,
    api_template: dict[str, Any],
) -> dict[str, Any]:
    """Match a live template response to its locks, history, and recovery guidance."""
    root = Path(repository_root)
    memory = load_live_e2e_memory(root)
    record = next(
        (
            item
            for item in memory["campaign_types"]
            if item.get("template_key") == template_id
        ),
        None,
    )
    if record is None:
        raise ValueError(f"template has no durable live E2E memory: {template_id}")
    if record.get("provider") != provider or api_template.get("provider") != provider:
        raise ValueError("template provider does not match live E2E memory")
    if (
        account_id != record.get("test_account")
        or api_template.get("account_id") != account_id
    ):
        raise ValueError("template account does not match the confirmed test account")
    if (
        api_template.get("blueprint_id") != record.get("blueprint_id")
        or api_template.get("blueprint_version") != record.get("blueprint_version")
    ):
        raise ValueError("template blueprint does not match live E2E memory")

    observations = [
        row
        for row in _read_observations(root)
        if row.get("provider") == provider
        and row.get("account_id") == account_id
        and row.get("template_id") == template_id
    ]
    reuse_state = hierarchy_reuse_state(record, observations)
    known_findings = [
        finding
        for finding in memory.get("known_findings", [])
        if _finding_applies_to(
            finding,
            provider=provider,
            campaign_type=record.get("campaign_type"),
            account_id=account_id,
        )
    ]
    return {
        **record,
        "known_findings": known_findings,
        "observations": observations[-20:],
        "hierarchy_reuse": reuse_state,
        "recovery_plan": _recovery_plan(record, reuse_state, known_findings),
    }


def _recovery_plan(
    record: dict[str, Any],
    reuse_state: dict[str, Any],
    known_findings: list[dict[str, Any]],
) -> dict[str, str]:
    """Turn stored evidence into the next safe test action."""
    if reuse_state.get("unresolved_attempt_ids"):
        return {
            "action": "reconcile_ambiguous_write",
            "instruction": (
                "A prior write has an unknown outcome. Read the exact resource "
                "hierarchy first; do not retry any create until reconciled."
            ),
        }

    if record.get("verification_state") == "blocked_by_provider":
        finding = next(
            (
                item
                for item in known_findings
                if item.get("status") == "provider_limited"
            ),
            None,
        )
        return {
            "action": "respect_provider_block",
            "instruction": (
                " ".join(
                    part
                    for part in (
                        finding.get("fix"),
                        finding.get("next_action"),
                    )
                    if part
                )
                if finding
                else str(record.get("remaining_gap") or "Do not repeat the blocked write.")
            ),
        }

    unresolved = [
        finding
        for finding in known_findings
        if finding.get("status") == "unresolved"
    ]
    if unresolved:
        finding = unresolved[0]
        return {
            "action": "resume_existing_and_capture_diagnostics",
            "instruction": str(finding.get("next_action") or record.get("remaining_gap")),
        }

    if reuse_state.get("requires_reconciliation"):
        gap = str(record.get("remaining_gap") or "").strip()
        instruction = (
            "Read back the known test-account hierarchy and resume only missing "
            "resources. Do not replay the full template or recreate existing parents."
        )
        if gap:
            instruction = f"{instruction} Remaining gap: {gap}"
        return {
            "action": "readback_and_resume_existing_hierarchy",
            "instruction": instruction,
        }

    return {
        "action": "use_locked_template_values",
        "instruction": (
            "Use the parameter values from the locked built-in template and verify "
            "the resulting resources through readback."
        ),
    }


def build_live_e2e_memory_report(
    repository_root: Path,
    *,
    provider: str | None = None,
    template_id: str | None = None,
    include_template_values: bool = False,
) -> dict[str, Any]:
    """Build a filtered, actionable report for a test-account E2E run."""
    root = Path(repository_root)
    memory = load_live_e2e_memory(root)
    template_document = _read_json(root / TEMPLATE_RELATIVE_PATH)
    templates = {
        item.get("key"): item
        for item in template_document.get("templates", [])
        if isinstance(item, dict) and item.get("key")
    }
    records = [
        record
        for record in memory["campaign_types"]
        if (provider is None or record.get("provider") == provider)
        and (template_id is None or record.get("template_key") == template_id)
    ]
    if not records:
        raise ValueError("no live E2E memory matches the requested provider/template")

    entries = []
    for record in records:
        template = templates[record["template_key"]]
        provider_name = str(record["provider"])
        observations = [
            row
            for row in _read_observations(root)
            if row.get("provider") == provider_name
            and row.get("account_id") == record.get("test_account")
            and row.get("template_id") == record.get("template_key")
        ]
        reuse_state = hierarchy_reuse_state(record, observations)
        known_findings = [
            finding
            for finding in memory.get("known_findings", [])
            if _finding_applies_to(
                finding,
                provider=provider_name,
                campaign_type=record.get("campaign_type"),
                account_id=record["test_account"],
            )
        ]
        entry = {
            "provider": provider_name,
            "campaign_type": record["campaign_type"],
            "test_account": record["test_account"],
            "template_id": record["template_key"],
            "blueprint_id": record["blueprint_id"],
            "blueprint_version": record["blueprint_version"],
            "template_values_sha256": record["template_values_sha256"],
            "template_values_source": str(TEMPLATE_RELATIVE_PATH),
            "verification_state": record["verification_state"],
            "known_live_hierarchies": record["known_live_hierarchies"],
            "known_findings": known_findings,
            "recent_observations": observations[-20:],
            "recovery_plan": _recovery_plan(record, reuse_state, known_findings),
        }
        if include_template_values:
            entry["template_values"] = template.get("values")
        entries.append(entry)

    return {
        "source": str(MEMORY_RELATIVE_PATH),
        "test_accounts_only": True,
        "entries": entries,
    }


__all__ = [
    "append_live_e2e_observation",
    "build_live_e2e_memory_report",
    "hierarchy_reuse_state",
    "load_live_e2e_memory",
    "require_new_hierarchy_authorization",
    "resolve_template_memory",
]
