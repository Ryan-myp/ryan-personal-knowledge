"""Limit initial schema breadth; registered Tools remain discoverable on demand."""

import json

from agents.agent_harness.tool_schema_projection import model_tool_payload


def bound_initial_tools(tools, *, max_tools: int = 8, max_chars: int = 18000, pinned_names=()):
    # Keep the highest-ranked capability even when workflow entry schemas alone
    # exceed the soft budget; pinning must not evict knowledge/search/read tools.
    selected = [tool for index, tool in enumerate(tools) if index == 0 or tool.name in pinned_names]
    used = sum(len(json.dumps(model_tool_payload(tool), ensure_ascii=False)) for tool in selected)
    # Broad candidates are not evidence of multi-channel intent. Give each
    # namespace a first opportunity without attaching every schema in it.
    representatives = {}
    for tool in tools:
        representatives.setdefault(getattr(tool, "namespace", ""), tool)
    for tool in (*representatives.values(), *tools):
        if tool in selected:
            continue
        if selected and len(selected) >= max_tools:
            break
        size = len(json.dumps(model_tool_payload(tool), ensure_ascii=False))
        if selected and used + size > max_chars:
            continue
        selected.append(tool)
        used += size
    names = {tool.name for tool in selected}
    return [tool for tool in tools if tool.name in names]


def blueprint_entry_names(runtime):
    """Keep declared workflow entry points reachable without attaching entire workflows."""
    catalog = getattr(runtime, "creation_blueprints", None)
    if catalog is None:
        return set()
    return {blueprint.tools[0] for blueprint in catalog.list() if blueprint.tools}
