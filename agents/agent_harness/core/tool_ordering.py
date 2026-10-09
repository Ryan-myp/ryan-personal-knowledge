"""Generic ordering helpers for Tools with declared resource dependencies."""

from __future__ import annotations

from typing import Any, Sequence


def order_by_resource_dependencies(tools: Sequence[Any]) -> list[Any]:
    """Order Tools by declared parent resources with a stable fallback.

    A parent absent from the supplied set is treated as an existing resource.
    Malformed cycles remain visible and deterministic for the contract audit.
    """
    remaining: list[Any] = []
    seen_names: set[str] = set()
    for tool in tools:
        name = str(getattr(tool, "name", "") or "")
        if name in seen_names:
            continue
        seen_names.add(name)
        remaining.append(tool)

    emitted_resources: set[str] = set()
    declared_resources = {
        str(getattr(tool, "resource_type", "") or "")
        for tool in remaining
    }
    ordered: list[Any] = []
    while remaining:
        ready = [
            tool for tool in remaining
            if not getattr(tool, "parent_resource_type", None)
            or str(getattr(tool, "parent_resource_type", "")) in emitted_resources
            or str(getattr(tool, "parent_resource_type", ""))
            not in declared_resources
        ]
        if not ready:
            ready = [min(remaining, key=lambda tool: str(tool.name))]
        ready.sort(key=lambda tool: str(getattr(tool, "name", "")))
        for tool in ready:
            ordered.append(tool)
            remaining.remove(tool)
            resource_type = str(getattr(tool, "resource_type", "") or "")
            if resource_type:
                emitted_resources.add(resource_type)
    return ordered


__all__ = ["order_by_resource_dependencies"]
