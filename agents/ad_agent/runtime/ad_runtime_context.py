"""Context assembly services for the advertising application.

The Harness treats request context as opaque. This adapter is the only place
that interprets advertising Skill metadata, declarative creation context, and
bounded prior Tool results for the model-facing turn pipeline.
"""

from __future__ import annotations

import inspect
import json
from collections import OrderedDict
from typing import Any

from ..core.interfaces import ParsedIntent, ToolResult


class AdvertisingRuntimeContext:
    """Build bounded advisory context without registering or executing Tools."""

    def __init__(self, runtime: Any, *, max_blueprint_entries: int = 128) -> None:
        self.runtime = runtime
        self._max_blueprint_entries = max(1, int(max_blueprint_entries))
        self._blueprint_context_cache: OrderedDict[tuple[str, ...], str] = (
            OrderedDict()
        )

    def build_skill_context(
        self,
        user_input: str,
        available_tools: list[Any],
        intent_type: str | None,
        tenant_id: str,
    ) -> dict[str, Any]:
        context = self.runtime.tool_selector.build_context_for_input(
            user_input,
            available_tools,
            intent_type,
            tenant_id=tenant_id,
        )
        if not isinstance(context, dict):
            context = {}
        raw_platforms = context.get("platforms")
        provider_scope = [
            item.strip()
            for item in str(raw_platforms or "").split(",")
            if item.strip()
        ]
        provider_key = tuple(sorted(set(provider_scope)))
        publisher_context = self._blueprint_context_cache.get(provider_key)
        if publisher_context is not None:
            self._blueprint_context_cache.move_to_end(provider_key)
        else:
            publisher_context = self.runtime.creation_card_builder.llm_context(
                providers=list(provider_key) or None
            )
            self._blueprint_context_cache[provider_key] = publisher_context
            while len(self._blueprint_context_cache) > self._max_blueprint_entries:
                self._blueprint_context_cache.popitem(last=False)
        context["publisher_context"] = publisher_context
        return context

    def optimize_tool_selection(
        self,
        user_input: str,
        intent: ParsedIntent,
        available_tools: list[Any],
        tenant_id: str,
    ) -> dict[str, Any]:
        optimizer = self.runtime.tool_selector.optimize_for_llm
        try:
            parameters = inspect.signature(optimizer).parameters
        except (TypeError, ValueError):
            parameters = {}
        if "tenant_id" in parameters:
            return optimizer(
                user_input,
                intent,
                available_tools,
                tenant_id=tenant_id,
            )
        return optimizer(user_input, intent, available_tools)

    def prior_tool_results(
        self,
        session: Any,
        max_results: int = 8,
        max_chars: int = 4000,
    ) -> str:
        rows: list[str] = []
        for tool_name, result in list(session.tool_results.items())[-max_results:]:
            if not isinstance(result, ToolResult):
                continue
            safe = self.runtime._redact_for_persistence(result.to_dict())
            try:
                encoded = json.dumps(
                    safe,
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                )
            except (TypeError, ValueError):
                encoded = json.dumps(
                    {
                        "success": result.success,
                        "error": str(result.error or ""),
                    },
                    ensure_ascii=False,
                )
            rows.append(f"[{tool_name}] {encoded[:1200]}")
        return "\n".join(rows)[:max_chars]

    @staticmethod
    def from_session_metadata(session: Any = None) -> dict[str, Any]:
        if session is None:
            return {}
        value = session.ctx.metadata.get("skill_context")
        return value if isinstance(value, dict) else {}

    def clear(self) -> None:
        self._blueprint_context_cache.clear()

    def snapshot(self) -> OrderedDict[tuple[str, ...], str]:
        """Capture the bounded cache for an atomic Skill lifecycle rollback."""
        return OrderedDict(self._blueprint_context_cache)

    def restore(self, snapshot: Any) -> None:
        """Restore only valid bounded cache entries after a failed unload."""
        if not isinstance(snapshot, dict):
            raise TypeError("context cache snapshot must be a mapping")
        self._blueprint_context_cache = OrderedDict(
            (tuple(key), str(value))
            for key, value in snapshot.items()
        )
        while len(self._blueprint_context_cache) > self._max_blueprint_entries:
            self._blueprint_context_cache.popitem(last=False)


__all__ = ["AdvertisingRuntimeContext"]
