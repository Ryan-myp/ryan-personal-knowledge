"""Signed tokens for provider-backed parameter selections.

Dynamic values such as an App ID or a location ID must come from a provider
lookup, not from an arbitrary string that happens to pass a type check.  This
module keeps the selection proof self-contained and backend-independent:

* lookup results can expose short-lived, user/session/account-bound tokens;
* a create request can submit those tokens instead of trusting copied IDs;
* no token or provider credential is persisted by this module.

The Runtime owns when tokens are issued and verified.  Skills only describe
which lookup tool and output fields provide the value.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, Optional


class ParameterSelectionError(ValueError):
    """Raised when a selection token is malformed, expired or mis-bound."""


class ParameterSelectionSigner:
    """Issue and verify short-lived, context-bound parameter selections."""

    PREFIX = "ps1"

    def __init__(self, secret: Optional[str | bytes] = None, ttl_seconds: int = 600):
        if ttl_seconds <= 0:
            raise ValueError("parameter selection ttl_seconds must be positive")
        if secret is None:
            # A local fallback keeps tests and single-process development safe;
            # deployments with multiple Runtime instances must provide the
            # same AD_AGENT_SELECTION_TOKEN_KEY to all instances.
            secret = secrets.token_bytes(32)
        if isinstance(secret, str):
            secret = secret.encode("utf-8")
        if not isinstance(secret, bytes) or len(secret) < 16:
            raise ValueError("parameter selection secret must contain at least 16 bytes")
        self._secret = bytes(secret)
        self.ttl_seconds = int(ttl_seconds)

    @staticmethod
    def _encode(payload: dict[str, Any]) -> str:
        raw = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    @staticmethod
    def _decode(encoded: str) -> dict[str, Any]:
        try:
            padding = "=" * (-len(encoded) % 4)
            value = json.loads(
                base64.urlsafe_b64decode((encoded + padding).encode("ascii"))
            )
        except (UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise ParameterSelectionError("invalid parameter selection token") from exc
        if not isinstance(value, dict):
            raise ParameterSelectionError("invalid parameter selection payload")
        return value

    def _signature(self, encoded_payload: str) -> str:
        return hmac.new(
            self._secret, encoded_payload.encode("ascii"), hashlib.sha256,
        ).hexdigest()

    def issue(
        self,
        *,
        session_id: str,
        user_id: str,
        account_id: str,
        platform: str,
        tool_name: str,
        field: str,
        source_tool: str,
        value: Any,
        now: Optional[int] = None,
    ) -> tuple[str, int]:
        issued_at = int(time.time() if now is None else now)
        expires_at = issued_at + self.ttl_seconds
        payload = {
            "v": 1,
            "iat": issued_at,
            "exp": expires_at,
            "session_id": str(session_id),
            "user_id": str(user_id),
            "account_id": str(account_id or ""),
            "platform": str(platform),
            "tool_name": str(tool_name),
            "field": str(field),
            "source_tool": str(source_tool),
            "value": value,
        }
        encoded = self._encode(payload)
        return f"{self.PREFIX}.{encoded}.{self._signature(encoded)}", expires_at

    def verify(
        self,
        token: str,
        *,
        session_id: str,
        user_id: str,
        account_id: str,
        platform: str,
        tool_name: str,
        field: str,
        source_tool: str,
        now: Optional[int] = None,
    ) -> Any:
        if not isinstance(token, str):
            raise ParameterSelectionError("parameter selection token must be a string")
        parts = token.split(".")
        if len(parts) != 3 or parts[0] != self.PREFIX:
            raise ParameterSelectionError("invalid parameter selection token")
        encoded, signature = parts[1], parts[2]
        expected = self._signature(encoded)
        if not hmac.compare_digest(signature, expected):
            raise ParameterSelectionError("parameter selection token signature mismatch")
        payload = self._decode(encoded)

        current = int(time.time() if now is None else now)
        try:
            expires_at = int(payload["exp"])
            issued_at = int(payload["iat"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ParameterSelectionError("invalid parameter selection expiry") from exc
        if issued_at > current or expires_at <= current:
            raise ParameterSelectionError("parameter selection token expired")

        expected_context = {
            "session_id": str(session_id),
            "user_id": str(user_id),
            "account_id": str(account_id or ""),
            "platform": str(platform),
            "tool_name": str(tool_name),
            "field": str(field),
            "source_tool": str(source_tool),
        }
        for key, expected_value in expected_context.items():
            if str(payload.get(key, "")) != expected_value:
                raise ParameterSelectionError(
                    f"parameter selection token is not bound to {key}"
                )
        if payload.get("v") != 1 or "value" not in payload:
            raise ParameterSelectionError("invalid parameter selection payload")
        return payload["value"]
