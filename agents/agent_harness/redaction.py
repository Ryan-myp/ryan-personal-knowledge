"""Business-neutral redaction for durable and transport-facing Agent data."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


_SENSITIVE_KEY_PARTS = (
    "token", "secret", "api_key", "private_key", "private_key_id",
    "service_account", "sa_email", "developer_key", "credential",
    "authorization", "bc_id", "bcid", "partner_id", "partnerid",
    "perter_id", "perterid", "developer_token", "mcc",
    "login_customer_id", "logincustomerid", "manager_customer_id",
    "managercustomerid", "client_id", "clientid",
)

_PUBLIC_TOKEN_COUNTER_KEYS = frozenset({
    "input_tokens", "output_tokens", "total_tokens", "prompt_tokens",
    "completion_tokens", "cache_read_input_tokens", "cache_write_input_tokens",
    "cache_creation_input_tokens", "cached_input_tokens", "cached_tokens",
    "max_input_tokens", "max_output_tokens", "max_total_tokens", "max_tokens",
})

_SENSITIVE_CANONICAL_PARTS = frozenset(
    part.replace("_", "").replace("-", "") for part in _SENSITIVE_KEY_PARTS
)


def _sensitive_key(key: Any) -> bool:
    canonical = str(key).lower().replace("_", "").replace("-", "")
    return any(part in canonical for part in _SENSITIVE_CANONICAL_PARTS)

_TEXT_PATTERNS = (
    r"(?i)(?P<prefix>['\"]?authorization['\"]?\s*[:=]\s*['\"]?(?:bearer|basic)\s+)[^\s,'\";}]+",
    r"(?is)(?P<prefix>['\"]?(?:api[_-]?key|app[_-]?secret)['\"]?\s*[:=]\s*)['\"][^'\"]*['\"]",
    r"(?i)(?P<prefix>\b(?:api[_-]?key|app[_-]?secret)\s*[:=]\s*)[^\s,;}]+",
    r"(?is)(?P<prefix>['\"]?(?:access|refresh|developer)[_-]?token['\"]?\s*[:=]\s*)['\"][^'\"]*['\"]",
    r"(?is)(?P<prefix>['\"]?private[_-]?key['\"]?\s*[:=]\s*)['\"]-----BEGIN.*?-----END[^\r\n]*-----['\"]",
    r"(?is)(?P<prefix>['\"]?private[_-]?key['\"]?\s*[:=]\s*)['\"][^'\"]*['\"]",
    r"(?is)(?P<prefix>['\"]?client[_-]?secret['\"]?\s*[:=]\s*)['\"][^'\"]*['\"]",
    r"(?is)(?P<prefix>['\"]?(?:bc[_-]?id|partner[_-]?id|perter[_-]?id|mcc|login[_-]?customer[_-]?id|manager[_-]?customer[_-]?id|client[_-]?id)['\"]?\s*[:=]\s*)['\"][^'\"]*['\"]",
    r"(?is)(?P<prefix>['\"]?authorization['\"]?\s*[:=]\s*)['\"][^'\"]*['\"]",
    r"(?i)(?P<prefix>\b(?:access|refresh|developer)[_-]?token\s*[:=]\s*)[^\s,;}]+",
    r"(?is)(?P<prefix>\bprivate[_-]?key\s*[:=]\s*)-----BEGIN.*?-----END[^\r\n]*-----",
    r"(?i)(?P<prefix>\bprivate[_-]?key\s*[:=]\s*)[^\s,;}]+",
    r"(?i)(?P<prefix>\bclient[_-]?secret\s*[:=]\s*)[^\s,;}]+",
    r"(?i)(?P<prefix>\b(?:bc[_-]?id|partner[_-]?id|perter[_-]?id|mcc|login[_-]?customer[_-]?id|manager[_-]?customer[_-]?id|client[_-]?id|authorization)\s*[:=]\s*)[^\s,;}]+",
)


def redact_for_persistence(value: Any) -> Any:
    """Remove credential-shaped fields and pasted secrets from arbitrary data."""
    if isinstance(value, Mapping):
        return {
            key: (
                redact_for_persistence(child)
                if str(key).lower() in {"selection_token", "selection_tokens"}
                or (
                    str(key).lower() in _PUBLIC_TOKEN_COUNTER_KEYS
                    and type(child) is int and child >= 0
                )
                else "<redacted>"
                if _sensitive_key(key)
                else redact_for_persistence(child)
            )
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [redact_for_persistence(child) for child in value]
    if isinstance(value, tuple):
        return tuple(redact_for_persistence(child) for child in value)
    if isinstance(value, str):
        redacted = value
        for pattern in _TEXT_PATTERNS:
            redacted = re.sub(
                pattern,
                lambda match: f"{match.group('prefix')}<redacted>",
                redacted,
            )
        return redacted
    return value


__all__ = ["redact_for_persistence"]
