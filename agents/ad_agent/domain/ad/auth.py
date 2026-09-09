"""Trusted request identity and authorization context.

The Runtime may be embedded by the CLI, an HTTP gateway, or a job worker.  A
caller-provided ``user_id`` is useful for local compatibility, but it is not
an authentication mechanism.  Production embeddings should construct a
``RequestPrincipal`` from an already-authenticated identity and pass it to the
Runtime.  The object intentionally contains only authorization metadata; it
never carries tokens or provider credentials.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional
from ...core.namespace import normalize_namespace as normalize_platform


def normalize_account_id(account_id: Any) -> str:
    """Normalize account IDs only for comparison, never for provider payloads."""
    if account_id is None or isinstance(account_id, bool):
        return ""
    if not isinstance(account_id, (str, int)):
        return ""
    value = str(account_id or "").strip()
    return value[4:] if value.lower().startswith("act_") else value


def _normalize_permissions(value: Any) -> frozenset[str]:
    """Normalize trusted permission claims without accepting scalar strings.

    Treating ``"ads.read"`` as an iterable would produce a set of
    characters.  That is usually a denial, but malformed claims should be
    rejected at the authentication boundary rather than silently changing
    authorization semantics.
    """
    if value is None:
        return frozenset()
    if isinstance(value, (str, bytes)) or not isinstance(
        value, (list, tuple, set, frozenset)
    ):
        raise ValueError("permissions must be an array of strings")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError("permissions must contain non-empty strings")
    return frozenset(item.strip() for item in value)


@dataclass(frozen=True)
class RequestPrincipal:
    """Authorization claims supplied by a trusted embedding boundary.

    ``account_scope`` is deny-by-default: when a principal is present, a
    platform must have an explicit account set and the requested account must
    be in that set.  This prevents a shared service credential from becoming
    an authorization grant merely because a user supplied an account ID.
    """

    user_id: str
    tenant_id: str = "default"
    permissions: frozenset[str] = field(default_factory=frozenset)
    account_scope: Mapping[str, frozenset[str]] = field(default_factory=dict)
    source: str = "trusted"

    def __post_init__(self) -> None:
        user_id = str(self.user_id or "").strip()
        tenant_id = str(self.tenant_id or "default").strip()
        if not user_id:
            raise ValueError("RequestPrincipal.user_id must not be empty")
        object.__setattr__(self, "user_id", user_id)
        object.__setattr__(self, "tenant_id", tenant_id or "default")
        object.__setattr__(self, "permissions", _normalize_permissions(self.permissions))
        normalized_scope: dict[str, frozenset[str]] = {}
        for platform, accounts in (self.account_scope or {}).items():
            normalized_platform = normalize_platform(platform)
            if not normalized_platform:
                continue
            if isinstance(accounts, (str, bytes)):
                raise ValueError("account_scope values must be arrays of account IDs")
            normalized_scope[normalized_platform] = frozenset(
                normalize_account_id(account)
                for account in (accounts or ())
                if normalize_account_id(account)
            )
        object.__setattr__(self, "account_scope", normalized_scope)

    @classmethod
    def from_claims(cls, claims: Mapping[str, Any]) -> "RequestPrincipal":
        """Build a principal from trusted gateway claims, not request JSON."""
        if not isinstance(claims, Mapping):
            raise TypeError("trusted claims must be a mapping")
        raw_scope = claims.get("account_scope", claims.get("accounts", {})) or {}
        if not isinstance(raw_scope, Mapping):
            raise ValueError("account_scope must be an object")
        return cls(
            user_id=str(claims.get("user_id", claims.get("sub", ""))),
            tenant_id=str(claims.get("tenant_id", claims.get("tenant", "default"))),
            permissions=_normalize_permissions(claims.get("permissions", ()) or ()),
            account_scope={
                str(platform): accounts
                for platform, accounts in raw_scope.items()
            },
            source=str(claims.get("source", "trusted")),
        )

    def accounts_for(self, platform: str) -> frozenset[str]:
        return self.account_scope.get(normalize_platform(platform), frozenset())

    def allows_account(self, platform: str, account_id: Any) -> bool:
        normalized = normalize_account_id(account_id)
        return bool(normalized) and normalized in self.accounts_for(platform)

    def to_safe_dict(self) -> dict[str, Any]:
        """Return non-secret claims suitable for audit/context metadata."""
        return {
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "permissions": sorted(self.permissions),
            "account_scope": {
                platform: sorted(accounts)
                for platform, accounts in self.account_scope.items()
            },
            "source": self.source,
        }
