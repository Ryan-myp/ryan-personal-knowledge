"""Authentication and principal resolution for the advertising HTTP API."""

from __future__ import annotations

import hmac
import json
import logging
from typing import Any, Callable, Optional

from fastapi import HTTPException, Request

from agents.agent_harness.redaction import redact_for_persistence
from agents.agent_platform.governance.identity.principal import RequestPrincipal

logger = logging.getLogger(__name__)


class RequestAuthorizer:
    """Resolve trusted request identity without coupling routes to config."""

    def __init__(
        self,
        *,
        runtime_getter: Callable[[], Any],
        api_key_getter: Callable[[], str],
        principals_getter: Callable[[], dict[str, dict[str, Any]]],
        allow_unauthenticated_getter: Callable[[], bool],
        service_principal_getter: Callable[[], RequestPrincipal] | None = None,
    ) -> None:
        self._runtime_getter = runtime_getter
        self._api_key_getter = api_key_getter
        self._principals_getter = principals_getter
        self._allow_unauthenticated_getter = allow_unauthenticated_getter
        self._service_principal_getter = service_principal_getter

    def authorize(
        self,
        api_key: Optional[str],
        request: Optional[Request] = None,
    ) -> RequestPrincipal:
        """Resolve a deployment-trusted identity for shared or keyed access."""
        if self._allow_unauthenticated_getter():
            # Shared mode deliberately ignores browser keys and client address:
            # localhost and remote clients must share one persisted identity.
            return self._configured_service_principal()

        principals = self._principals_getter()
        configured_key = self._api_key_getter()

        if api_key:
            if principals:
                claims = principals.get(api_key)
                if not isinstance(claims, dict):
                    raise HTTPException(status_code=401, detail="Invalid API key")
                try:
                    return RequestPrincipal.from_claims(claims)
                except (TypeError, ValueError) as exc:
                    logger.error("API key principal 配置无效: %s", exc)
                    raise HTTPException(
                        status_code=503,
                        detail="API principal configuration is invalid",
                    ) from exc
            if configured_key and hmac.compare_digest(api_key, configured_key):
                return self._configured_service_principal()
            raise HTTPException(status_code=401, detail="Invalid API key")

        if principals or configured_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
        raise HTTPException(
            status_code=503,
            detail=(
                "API authentication is not configured; set AD_AGENT_API_KEY "
                "or enable AD_AGENT_ALLOW_UNAUTHENTICATED=1 for shared access"
            ),
        )

    def require_permission(
        self,
        principal: RequestPrincipal,
        permission: str,
    ) -> None:
        requested = str(permission or "").strip()
        granted = set(principal.permissions or ())
        domain = requested.split(".", 1)[0] if "." in requested else ""
        # ``ads.write`` is a higher privilege only inside the advertising
        # domain. It must not become a cross-domain administrator for Wiki,
        # MCP, Plugin, Skill, or Memory control-plane APIs.
        allowed = (
            requested in granted
            or "admin" in granted
            or (domain == "ads" and "ads.write" in granted)
        )
        if not allowed:
            raise HTTPException(
                status_code=403,
                detail=f"缺少操作所需权限：{requested}",
            )

    def configured_service_principal(self) -> RequestPrincipal:
        return self._configured_service_principal()

    def safe_exception_text(self, error: Exception) -> str:
        return redact_for_persistence(str(error))

    def _configured_service_principal(self) -> RequestPrincipal:
        if self._service_principal_getter is not None:
            return self._service_principal_getter()
        runtime = self._runtime_getter()
        if runtime is not None:
            permissions = set(getattr(runtime, "_granted_permissions", set()))
            validator = getattr(runtime, "whitelist_validator", None)
            account_scope = {
                str(platform): set(values or [])
                for platform, values in getattr(
                    validator,
                    "allowed_accounts",
                    {},
                ).items()
            } if validator is not None else {}
        else:
            permissions = set()
            account_scope = {}
        return RequestPrincipal(
            user_id="ad-agent-service",
            tenant_id="default",
            permissions=frozenset(permissions),
            account_scope=account_scope,
            source="shared-service",
            provider_read_namespaces=getattr(
                getattr(runtime, "whitelist_validator", None),
                "provider_read_namespaces", frozenset(),
            ),
        )
