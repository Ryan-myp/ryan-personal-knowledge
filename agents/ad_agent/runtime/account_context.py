"""Provider-neutral account context resolution.

The resolver reads account-like fields declared by selected Tool schemas and
returns a scoped account candidate. It does not validate permissions or call a
provider; those decisions remain in the Runtime policy boundary.
"""

from __future__ import annotations

from typing import Any, Optional

from ..core.scope import ResourceScope


class AccountResolver:
    """Advertising adapter for the generic Tool scope contract."""

    ACCOUNT_FIELDS = (
        "account_id", "ad_account_id", "advertiser_id", "customer_id",
    )

    def __init__(self, services: Any):
        self.services = services

    def resolve(
        self,
        intent: Any,
        platform: str,
        tools: list[Any],
        fallback_account: Optional[str],
        *,
        allow_automatic_account: bool = True,
    ) -> Optional[str]:
        """Resolve an account without crossing the write-account boundary.

        ``fallback_account`` is a caller/session supplied value.  The
        configured whitelist is only a discovery convenience for read-only
        requests.  A write request must identify its target account in the
        current request; silently selecting the sole whitelisted account can
        still target the wrong advertiser after configuration changes.
        """
        params = self.services.input_builder.platform_params_for_intent(
            intent, platform
        )
        actual_platform = self.services.canonical_platform(platform)
        declared_keys = []
        for tool in tools:
            published_fields = getattr(tool, "scope_fields", None) or ()
            if published_fields:
                declared_keys.extend(str(item) for item in published_fields)
                continue
            declared_keys.extend(
                key
                for key in self.ACCOUNT_FIELDS
                if key in getattr(
                    getattr(tool, "input_schema", None), "properties", {}
                )
            )
        candidate_keys = list(dict.fromkeys(
            declared_keys + list(self.ACCOUNT_FIELDS)
        ))
        sources = [params]
        for tool in tools:
            specific = params.get(tool.name)
            if isinstance(specific, dict):
                sources.append(specific)
        for source in sources:
            for key in candidate_keys:
                value = source.get(key)
                if value not in (None, ""):
                    return str(value)
        if fallback_account:
            return str(fallback_account)
        if not allow_automatic_account or any(
            bool(getattr(tool, "is_write_tool", False)) for tool in tools
        ):
            return None
        allowed = self.services.available_accounts(actual_platform, None)
        return str(allowed[0]) if len(allowed) == 1 else None

    def resolve_scope(
        self,
        request: Any,
        tools: list[Any],
        fallback: Optional[str] = None,
    ) -> Optional[ResourceScope]:
        """Expose the advertising resolver through the generic Scope port."""
        if not tools:
            return None
        namespace = str(getattr(tools[0], "namespace", "") or "")
        value = self.resolve(
            request,
            namespace,
            tools,
            fallback,
            allow_automatic_account=not any(
                bool(getattr(tool, "is_write_tool", False)) for tool in tools
            ),
        )
        if value in (None, ""):
            return None
        scope_type = next(
            (
                str(getattr(tool, "scope_type", "") or "").strip()
                for tool in tools
                if getattr(tool, "scope_type", None)
            ),
            "account",
        )
        return ResourceScope(
            scope_type=scope_type,
            scope_id=str(value),
            namespace=self.services.canonical_platform(namespace),
            source="ad-account-resolver",
        )
