"""Business-neutral redaction for durable and transport-facing Agent data."""

from __future__ import annotations

import re
from typing import Any


_SENSITIVE_KEY_PARTS = (
    "token", "secret", "api_key", "private_key", "private_key_id",
    "service_account", "sa_email", "developer_key", "credential",
    "authorization", "bc_id", "bcid", "partner_id", "partnerid",
    "perter_id", "perterid", "developer_token", "mcc",
    "login_customer_id", "logincustomerid", "manager_customer_id",
    "managercustomerid", "client_id", "clientid",
)

_TEXT_PATTERNS = (
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
    if isinstance(value, dict):
        return {
            key: (
                redact_for_persistence(child)
                if str(key).lower() in {"selection_token", "selection_tokens"}
                else "<redacted>"
                if any(part in str(key).lower() for part in _SENSITIVE_KEY_PARTS)
                else redact_for_persistence(child)
            )
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [redact_for_persistence(child) for child in value]
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
