"""Advertising account scope resolution at the application boundary."""

from __future__ import annotations

from typing import Any, Mapping, Optional

from ..domain.ad.security import ACCOUNT_SCOPE_FIELDS


class AdvertisingRuntimeScope:
    """Translate workflow items into provider-neutral account scopes."""

    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime

    def resolve_item(
        self,
        intent: Any,
        platform: str,
        tools: list[Any],
        session: Any,
    ) -> Optional[str]:
        if not tools:
            return None
        tool = tools[0]
        fallback = None
        if not getattr(tool, "is_write_tool", False):
            fallback = (
                getattr(getattr(session, "ctx", None), "account_id", None)
                if len(getattr(intent, "namespaces", []) or []) == 1
                else None
            )
        return self.runtime.account_resolver.resolve(
            intent,
            platform,
            tools,
            fallback,
        )

    def resolve_result(
        self,
        intent: Any,
        platform: str,
        tools: list[Any],
        session: Any,
        item: Mapping[str, Any],
        input_data: Mapping[str, Any],
        output_data: Mapping[str, Any],
    ) -> Optional[str]:
        for source in (item, output_data, input_data):
            for field in ACCOUNT_SCOPE_FIELDS:
                value = source.get(field) if isinstance(source, Mapping) else None
                if value not in (None, ""):
                    return str(value)
        return self.resolve_item(intent, platform, tools, session)


__all__ = ["AdvertisingRuntimeScope"]
