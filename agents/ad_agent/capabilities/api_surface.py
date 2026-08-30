"""Provider API surface contract shared by capability release audits.

The surface is deliberately declarative and provider-owned.  It describes
what the integration intends to cover; executable behavior still comes only
from a Client method bound to a registered Tool.
"""

from typing import Any, Iterable


IMPLEMENTED = "implemented"
PLANNED = "planned"
NOT_APPLICABLE = "not_applicable"
VALID_STATUSES = {IMPLEMENTED, PLANNED, NOT_APPLICABLE}


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
        if status == IMPLEMENTED and not str(entry.get("method") or "").strip():
            errors.append(f"{prefix}.method is required for implemented operation")
        if status == PLANNED and not str(entry.get("gap") or "").strip():
            errors.append(f"{prefix}.gap is required for planned operation")
    return errors
