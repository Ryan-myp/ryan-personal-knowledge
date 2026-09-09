"""Generic deterministic hashing helpers for Core contracts."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


# Shared Core protects only credential-shaped vocabulary that is meaningful
# for any application. Domain adapters may add their own fields at their
# boundary without expanding the shared Runtime contract.
GENERIC_SENSITIVE_FIELD_NAMES = frozenset({
    "access_token", "refresh_token", "id_token", "client_secret", "app_secret",
    "private_key", "private_key_id", "api_key", "developer_key", "developer_token", "password",
    "authorization", "credential", "credentials", "secret", "token",
})
_GENERIC_SENSITIVE_TEXT = re.compile(
    r"(?is)(?P<prefix>['\"]?(?:(?:access|refresh|id|developer)[_-]?token|"
    r"(?:client|app|private)[_-]?(?:secret|key)|api[_-]?key|"
    r"authorization|password|credential(?:s)?)[ '\"]*[:=][ '\"]*)"
    r"['\"]?[^'\"\s,;}]+['\"]?"
)


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


def normalize_field_name(value: Any) -> str:
    """Normalize a structured field name for generic contract comparisons."""
    return "".join(char for char in str(value or "").lower() if char.isalnum())


_GENERIC_SENSITIVE_FIELD_NAMES_NORMALIZED = frozenset(
    normalize_field_name(item) for item in GENERIC_SENSITIVE_FIELD_NAMES
)


def is_sensitive_field(value: Any, extra_fields: Any = ()) -> bool:
    """Return whether a field is credential-shaped for a generic consumer."""
    protected = set(_GENERIC_SENSITIVE_FIELD_NAMES_NORMALIZED)
    if isinstance(extra_fields, (str, bytes)):
        extra_fields = (extra_fields,)
    protected.update(normalize_field_name(item) for item in (extra_fields or ()))
    normalized = normalize_field_name(value)
    return (
        normalized in protected
        or normalized.endswith("token")
        or normalized.endswith("secret")
    )


def redact_sensitive_text(value: Any) -> str:
    """Redact credential-shaped assignments embedded in free-form text."""
    return _GENERIC_SENSITIVE_TEXT.sub(
        lambda match: f"{match.group('prefix')}<redacted>",
        str(value or ""),
    )


__all__ = [
    "GENERIC_SENSITIVE_FIELD_NAMES",
    "canonical_json",
    "is_sensitive_field",
    "normalize_field_name",
    "redact_sensitive_text",
    "sha256_json",
    "sha256_text",
]
