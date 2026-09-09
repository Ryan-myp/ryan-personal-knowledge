"""Advertising input red-lines and idempotency material.

The generic Core only provides deterministic hashing.  Credential names,
provider account identifiers and update restrictions are application policy
and therefore live with the advertising domain.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from ...core.security import canonical_json, normalize_field_name, sha256_json, sha256_text


def request_hash(
    platform: str, account_id: Optional[str], tool_name: str, input_hash: str,
) -> str:
    """Return an advertising request binding for idempotency/audit."""
    return sha256_text("|".join((
        str(platform or "").strip().lower(),
        str(account_id or ""),
        str(tool_name or ""),
        str(input_hash or ""),
    )))


PROTECTED_INPUT_FIELDS = frozenset({
    "token", "accesstoken", "refreshtoken", "developertoken", "clientid",
    "clientsecret", "apikey", "appsecret", "secretkey", "privatekey",
    "privatekeyid", "serviceaccount", "serviceaccountemail", "saemail",
    "developerkey", "authorization", "credential", "credentials",
    "bcid", "partnerid", "perterid", "mcc",
    "logincustomerid", "managercustomerid",
})


PROTECTED_UPDATE_FIELDS = PROTECTED_INPUT_FIELDS | frozenset({
    "accountid", "adaccountid", "advertiserid", "customerid",
    "logincustomerid", "managercustomerid", "bcid", "partnerid", "mcc",
})

# The advertising application binds one logical account scope to several
# provider wire spellings. This alias set is application policy, not a Core
# Runtime contract.
ACCOUNT_SCOPE_FIELDS = (
    "account_id", "ad_account_id", "advertiser_id", "customer_id",
)


def protected_field_paths(
    value: Any,
    fields: Iterable[str] = PROTECTED_INPUT_FIELDS,
    path: str = "",
    limit: int = 10,
) -> list[str]:
    """Find advertising credential/account keys recursively."""
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


__all__ = [
    "PROTECTED_INPUT_FIELDS",
    "PROTECTED_UPDATE_FIELDS",
    "ACCOUNT_SCOPE_FIELDS",
    "canonical_json",
    "normalize_field_name",
    "protected_field_paths",
    "protected_update_paths",
    "request_hash",
    "sha256_json",
]
