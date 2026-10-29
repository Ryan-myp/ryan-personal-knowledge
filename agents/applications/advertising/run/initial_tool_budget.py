"""Limit initial schema breadth; registered Tools remain discoverable on demand."""

import json

from agents.agent_harness.tool_schema_projection import model_tool_payload


def bound_initial_tools(tools, *, max_tools: int = 8, max_chars: int = 18000, pinned_names=()):
    selected = [tool for tool in tools if tool.name in pinned_names]
    used = sum(len(json.dumps(model_tool_payload(tool), ensure_ascii=False)) for tool in selected)
    for tool in tools:
        if tool in selected:
            continue
        size = len(json.dumps(model_tool_payload(tool), ensure_ascii=False))
        if selected and (len(selected) >= max_tools or used + size > max_chars):
            break
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
