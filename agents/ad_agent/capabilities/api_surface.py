"""Provider API surface contract shared by capability release audits.

The surface is deliberately declarative and provider-owned.  It describes
what the integration intends to cover; executable behavior still comes only
from a Client method bound to a registered Tool.
"""

from collections import defaultdict
from typing import Any, Iterable


IMPLEMENTED = "implemented"
PLANNED = "planned"
NOT_APPLICABLE = "not_applicable"
VALID_STATUSES = {IMPLEMENTED, PLANNED, NOT_APPLICABLE}

# These fields describe the difference between a provider operation being
# represented in our code and being proven against a live provider account.
# The distinction is intentionally part of the provider package contract so a
# Tool count can never be mistaken for official API completeness.
EXECUTION_DRY_RUN = "dry_run_only"
EXECUTION_LIVE_VERIFIED = "live_verified"
EXECUTION_NOT_SUPPORTED = "not_supported"
VALID_EXECUTION_STATUSES = {
    EXECUTION_DRY_RUN,
    EXECUTION_LIVE_VERIFIED,
    EXECUTION_NOT_SUPPORTED,
}

EVIDENCE_CODE_CONTRACT = "code_contract"
EVIDENCE_PROVIDER_DOC_SCOPE = "provider_doc_scope"
EVIDENCE_PROVIDER_E2E = "provider_e2e"
VALID_EVIDENCE_LEVELS = {
    EVIDENCE_CODE_CONTRACT,
    EVIDENCE_PROVIDER_DOC_SCOPE,
    EVIDENCE_PROVIDER_E2E,
}


def materialize_surface(
    entries: Iterable[dict[str, Any]], metadata: dict[str, Any]
) -> list[dict[str, Any]]:
    """Attach provider-owned provenance to implementation surface entries.

    Existing capability files stay concise and provider-owned.  Defaults are
    deliberately conservative: an implemented entry is dry-run-only until a
    provider E2E check promotes it, and its evidence is a code contract until
    an operation-specific source/evidence is recorded.
    """
    result: list[dict[str, Any]] = []
    for raw in entries:
        entry = dict(raw)
        entry.setdefault("provider", metadata.get("provider", ""))
        entry.setdefault("api_version", metadata.get("api_version", ""))
        entry.setdefault("source_url", metadata.get("source_url", ""))
        entry.setdefault("evidence_level", EVIDENCE_CODE_CONTRACT)
        status = str(entry.get("status") or "")
        entry.setdefault(
            "execution_status",
            EXECUTION_DRY_RUN if status == IMPLEMENTED else EXECUTION_NOT_SUPPORTED,
        )
        entry.setdefault(
            "inventory_scope",
            metadata.get("inventory_scope", "implementation_surface_baseline"),
        )
        result.append(entry)
    return result


def materialize_inventory(
    entries: Iterable[dict[str, Any]], metadata: dict[str, Any]
) -> list[dict[str, Any]]:
    """Attach source/version provenance to provider inventory rows."""
    result: list[dict[str, Any]] = []
    for raw in entries:
        entry = dict(raw)
        entry.setdefault("provider", metadata.get("provider", ""))
        entry.setdefault("api_version", metadata.get("api_version", ""))
        entry.setdefault("source_url", metadata.get("source_url", ""))
        entry.setdefault("evidence_level", EVIDENCE_PROVIDER_DOC_SCOPE)
        entry.setdefault("endpoint", entry.get("provider_operation", ""))
        result.append(entry)
    return result


def validate_inventory(
    inventory: Iterable[dict[str, Any]], metadata: dict[str, Any]
) -> list[str]:
    """Validate a provider's official inventory without imposing a central list."""
    errors: list[str] = []
    for index, entry in enumerate(inventory):
        prefix = f"inventory[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in ("resource", "action", "status", "source_url"):
            if not str(entry.get(field) or "").strip():
                errors.append(f"{prefix}.{field} is required")
        status = str(entry.get("status") or "").strip()
        if status not in VALID_STATUSES:
            errors.append(f"{prefix}.status must be one of {sorted(VALID_STATUSES)}")
        if entry.get("provider") and entry.get("provider") != metadata.get("provider"):
            errors.append(f"{prefix}.provider does not match provider metadata")
        if status == IMPLEMENTED and not str(entry.get("surface_method") or "").strip():
            errors.append(f"{prefix}.surface_method is required for implemented inventory")
        if not str(entry.get("endpoint") or entry.get("provider_operation") or "").strip():
            errors.append(f"{prefix}.endpoint is required")
    return errors


def build_inventory_report(
    surface: Iterable[dict[str, Any]],
    inventory: Iterable[dict[str, Any]],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Compare a provider-owned official inventory with the implementation surface."""
    surface_by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    surface_by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in surface:
        surface_by_key[(str(entry.get("resource")), str(entry.get("action")))].append(entry)
        if entry.get("method"):
            surface_by_method[str(entry["method"])].append(entry)

    covered: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    for raw in inventory:
        entry = dict(raw)
        key = (str(entry.get("resource")), str(entry.get("action")))
        method = str(entry.get("surface_method") or "").strip()
        if method:
            # The provider operation is the stable join key.  Surface action
            # labels may intentionally be provider-specific (for example a
            # single DV360 CRUD adapter), so do not require resource/action
            # spelling to be identical when a method is declared.
            matches = list(surface_by_method.get(method, []))
        else:
            matches = list(surface_by_key.get(key, []))
        implemented = [item for item in matches if item.get("status") == IMPLEMENTED]
        item = {
            **entry,
            "surface_matches": [
                {
                    "method": item.get("method"),
                    "status": item.get("status"),
                    "execution_status": item.get("execution_status"),
                }
                for item in matches
            ],
            "covered": bool(implemented),
        }
        if implemented:
            covered.append(item)
        else:
            gaps.append(item)

    total = len(covered) + len(gaps)
    all_entries = covered + gaps
    execution_statuses: dict[str, int] = defaultdict(int)
    evidence_levels: dict[str, int] = defaultdict(int)
    for item in covered:
        statuses = {
            str(match.get("execution_status") or "unknown")
            for match in item.get("surface_matches", [])
        } or {"unknown"}
        for status in statuses:
            execution_statuses[status] += 1
    for item in all_entries:
        evidence_levels[str(item.get("evidence_level") or "unknown")] += 1
    evidence_gaps = [
        item for item in all_entries
        if item.get("evidence_level") != EVIDENCE_PROVIDER_E2E
    ]
    return {
        "provider": metadata.get("provider", ""),
        "api_version": metadata.get("api_version", ""),
        "source_url": metadata.get("source_url", ""),
        "scope": metadata.get("inventory_scope", ""),
        "completeness": metadata.get("completeness", "scoped_not_exhaustive"),
        "total": total,
        "covered": len(covered),
        "gaps": len(gaps),
        "coverage_ratio": round(len(covered) / total, 4) if total else 0.0,
        "execution_statuses": dict(sorted(execution_statuses.items())),
        "evidence_levels": dict(sorted(evidence_levels.items())),
        "evidence_gaps": evidence_gaps,
        "covered_entries": covered,
        "gaps_entries": gaps,
    }


def validate_surface(entries: Iterable[dict[str, Any]]) -> list[str]:
    """Return contract errors without coupling the audit to a provider."""
    errors: list[str] = []
    for index, entry in enumerate(entries):
        prefix = f"surface[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in ("resource", "action", "status"):
            if not str(entry.get(field) or "").strip():
                errors.append(f"{prefix}.{field} is required")
        status = str(entry.get("status") or "").strip()
        if status not in VALID_STATUSES:
            errors.append(f"{prefix}.status must be one of {sorted(VALID_STATUSES)}")
        execution_status = str(entry.get("execution_status") or "").strip()
        if execution_status and execution_status not in VALID_EXECUTION_STATUSES:
            errors.append(
                f"{prefix}.execution_status must be one of {sorted(VALID_EXECUTION_STATUSES)}"
            )
        evidence_level = str(entry.get("evidence_level") or "").strip()
        if evidence_level and evidence_level not in VALID_EVIDENCE_LEVELS:
            errors.append(
                f"{prefix}.evidence_level must be one of {sorted(VALID_EVIDENCE_LEVELS)}"
            )
        if status == IMPLEMENTED and not str(entry.get("method") or "").strip():
            errors.append(f"{prefix}.method is required for implemented operation")
        if status == PLANNED and not str(entry.get("gap") or "").strip():
            errors.append(f"{prefix}.gap is required for planned operation")
    return errors
