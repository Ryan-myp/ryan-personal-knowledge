"""Provider-neutral execution plan model.

The plan is the boundary between model/Skill intent and Runtime execution.
It contains Tool metadata and dependency edges, but never provider clients,
credentials, or executable user code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence


@dataclass(frozen=True)
class PlanNode:
    """One executable Tool node in a validated plan."""

    node_id: str
    sequence: int
    platform: str
    tool_name: str
    action: str
    resource_type: str
    parent_resource_type: str | None = None
    depends_on: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "sequence": self.sequence,
            "platform": self.platform,
            "tool": self.tool_name,
            "action": self.action,
            "resource_type": self.resource_type,
            "parent_resource_type": self.parent_resource_type,
            "depends_on": list(self.depends_on),
        }


@dataclass(frozen=True)
class ExecutionPlan:
    """A deterministic, serializable Tool dependency plan."""

    schema_version: str
    intent_type: str
    nodes: tuple[PlanNode, ...] = ()

    @classmethod
    def from_tool_plan(
        cls,
        intent: Any,
        tool_plan: Mapping[str, Sequence[Any]],
        canonicalize: Callable[[str], str] | None = None,
    ) -> "ExecutionPlan":
        normalize = canonicalize or (lambda value: str(value or "").strip().lower())
        nodes: list[PlanNode] = []
        latest_by_resource: dict[tuple[str, str], PlanNode] = {}
        sequence = 0
        for raw_platform, tools in tool_plan.items():
            platform = normalize(str(raw_platform))
            for tool in tools or ():
                sequence += 1
                resource_type = str(getattr(tool, "resource_type", "") or "")
                parent_type = getattr(tool, "parent_resource_type", None)
                parent_type = str(parent_type) if parent_type else None
                dependency = latest_by_resource.get((platform, parent_type or ""))
                node_id = f"node-{sequence:04d}"
                node = PlanNode(
                    node_id=node_id,
                    sequence=sequence,
                    platform=platform,
                    tool_name=str(getattr(tool, "name", "") or ""),
                    action=str(getattr(tool, "action", "") or ""),
                    resource_type=resource_type,
                    parent_resource_type=parent_type,
                    depends_on=(dependency.node_id,) if dependency else (),
                )
                nodes.append(node)
                if resource_type:
                    latest_by_resource[(platform, resource_type)] = node
        plan = cls(
            schema_version="1.0",
            intent_type=str(getattr(intent, "intent_type", "") or ""),
            nodes=tuple(nodes),
        )
        plan.validate()
        return plan

    def validate(self) -> None:
        node_ids = [node.node_id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("execution plan contains duplicate node IDs")
        known = set(node_ids)
        for node in self.nodes:
            if not node.tool_name:
                raise ValueError("execution plan node requires a Tool name")
            if any(dependency not in known for dependency in node.depends_on):
                raise ValueError(
                    f"execution plan node {node.node_id} has an unknown dependency"
                )
        # Kahn's algorithm keeps validation provider-neutral and catches
        # malformed/cyclic dependency metadata before execution.
        remaining = {
            node.node_id: set(node.depends_on) for node in self.nodes
        }
        resolved: set[str] = set()
        while remaining:
            ready = [
                node_id for node_id, dependencies in remaining.items()
                if dependencies <= resolved
            ]
            if not ready:
                raise ValueError("execution plan contains a dependency cycle")
            for node_id in ready:
                resolved.add(node_id)
                remaining.pop(node_id)

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "intent_type": self.intent_type,
            "nodes": [node.to_dict() for node in self.nodes],
        }
