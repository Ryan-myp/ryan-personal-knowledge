"""Shared credential/account configuration red-line checks."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Optional


def canonical_json(value: Any) -> str:
    """Serialize contract/security material deterministically.

    ``sort_keys`` plus compact separators gives equivalent JSON objects the
    same representation while avoiding Python's implementation-specific
    ``repr`` output. ``default=str`` is retained for legacy Tool inputs that
    contain UUID/date-like scalar values.
    """
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, default=str,
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_text(canonical_json(value))


def request_hash(
    platform: str, account_id: Optional[str], tool_name: str, input_hash: str,
) -> str:
    """Return the provider-neutral idempotency/request binding hash."""
    return sha256_text("|".join((
        str(platform or "").strip().lower(),
        str(account_id or ""),
        str(tool_name or ""),
        str(input_hash or ""),
    )))


def normalize_field_name(value: Any) -> str:
    return "".join(char for char in str(value or "").lower() if char.isalnum())


# Fields that must never arrive as Tool business input, at any nesting level.
PROTECTED_INPUT_FIELDS = frozenset({
    "token", "accesstoken", "refreshtoken", "developertoken", "clientid",
    "clientsecret", "apikey", "appsecret", "secretkey", "privatekey",
    "privatekeyid", "serviceaccount", "serviceaccountemail", "saemail",
    "developerkey", "authorization", "credential", "credentials",
    "bcid", "partnerid", "perterid", "mcc",
    "logincustomerid", "managercustomerid",
})


# A provider update must not mutate account/credential configuration. Account
# identifiers remain valid top-level Tool inputs for selecting a target; this
# set is used only for nested update payloads and provider configuration
# objects.
PROTECTED_UPDATE_FIELDS = PROTECTED_INPUT_FIELDS | frozenset({
    "accountid", "adaccountid", "advertiserid", "customerid",
    "logincustomerid", "managercustomerid", "bcid", "partnerid", "mcc",
})


def protected_field_paths(
    value: Any,
    fields: Iterable[str] = PROTECTED_INPUT_FIELDS,
    path: str = "",
    limit: int = 10,
) -> list[str]:
    """Find red-line keys recursively, preserving paths for safe errors."""
    protected = set(fields)
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            current = f"{path}.{key_text}" if path else key_text
            if normalize_field_name(key_text) in protected:
                found.append(current)
            else:
                found.extend(protected_field_paths(item, protected, current, limit))
            if len(found) >= limit:
                return found[:limit]
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found.extend(protected_field_paths(item, protected, f"{path}[{index}]", limit))
            if len(found) >= limit:
                return found[:limit]
    return found[:limit]


def protected_update_paths(value: Any, path: str = "") -> list[str]:
    return protected_field_paths(value, PROTECTED_UPDATE_FIELDS, path)
