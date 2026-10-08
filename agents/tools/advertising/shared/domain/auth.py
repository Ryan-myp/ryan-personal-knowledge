"""Provider-specific advertising account identifier normalization."""

from __future__ import annotations

from typing import Any


def normalize_account_id(account_id: Any) -> str:
    """Normalize Meta account IDs for comparison, never for provider payloads."""
    if account_id is None or isinstance(account_id, bool):
        return ""
    if not isinstance(account_id, (str, int)):
        return ""
    value = str(account_id).strip()
    return value[4:] if value.lower().startswith("act_") else value


__all__ = ["normalize_account_id"]
