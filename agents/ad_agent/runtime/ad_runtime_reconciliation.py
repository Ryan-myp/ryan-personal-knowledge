"""Write/read reconciliation lookup for the advertising application."""

from __future__ import annotations

from typing import Any, Optional


class AdvertisingRuntimeReconciliation:
    """Resolve an unambiguous read Tool for a write Tool."""

    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime

    def resolve_readback_definition(self, write_tool: str) -> Optional[Any]:
        runtime = self.runtime
        try:
            write_definition, _handler = runtime._get_registered_tool(write_tool)
        except KeyError:
            return None
        platform = runtime._canonical_platform(write_definition.namespace)
        declared_readback = str(
            getattr(write_definition, "readback_tool", "") or ""
        ).strip()
        if declared_readback:
            try:
                candidate, _handler = runtime._get_registered_tool(
                    declared_readback
                )
            except KeyError:
                return None
            if not self._matches_readback(
                candidate,
                write_definition,
                platform,
                runtime,
            ):
                return None
            return candidate

        candidates = [
            definition
            for definition in runtime.registry.list_all()
            if definition.is_read_tool
            and runtime._canonical_platform(definition.namespace) == platform
            and definition.action == "get"
            and definition.resource_type == write_definition.resource_type
            and definition.parent_resource_type
            == write_definition.parent_resource_type
        ]
        return candidates[0] if len(candidates) == 1 else None

    @staticmethod
    def _matches_readback(
        candidate: Any,
        write_definition: Any,
        platform: str,
        runtime: Any,
    ) -> bool:
        return bool(
            candidate.is_read_tool
            and candidate.action == "get"
            and candidate.resource_type == write_definition.resource_type
            and candidate.parent_resource_type
            == write_definition.parent_resource_type
        ) and platform == runtime._canonical_platform(candidate.namespace)


__all__ = ["AdvertisingRuntimeReconciliation"]
