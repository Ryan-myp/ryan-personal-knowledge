"""Shared credential/account configuration red-line checks."""

from __future__ import annotations

from typing import Any, Iterable


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
