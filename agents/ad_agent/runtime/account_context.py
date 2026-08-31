"""Provider-neutral account context resolution.

The resolver reads account-like fields declared by selected Tool schemas and
returns a scoped account candidate. It does not validate permissions or call a
provider; those decisions remain in the Runtime policy boundary.
"""

from __future__ import annotations

from typing import Any, Optional


class AccountResolver:
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
    ) -> Optional[str]:
        params = self.services.input_builder.platform_params_for_intent(
            intent, platform
        )
        actual_platform = self.services.canonical_platform(platform)
        declared_keys = [
            key
            for tool in tools
            for key in self.ACCOUNT_FIELDS
            if key in getattr(
                getattr(tool, "input_schema", None), "properties", {}
            )
        ]
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
        allowed = self.services.available_accounts(actual_platform, None)
        return str(allowed[0]) if len(allowed) == 1 else None
