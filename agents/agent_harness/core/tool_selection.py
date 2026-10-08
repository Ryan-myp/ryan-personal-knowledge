"""Domain-neutral Tool selection and model-facing Tool prompt rendering.

The selector only evaluates publisher metadata and the parsed intent. It does
not query knowledge, load Skills, inspect credentials, or execute handlers.
Those concerns belong to an application adapter around this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional, Sequence

from .interfaces import ParsedIntent, ToolDefinition
from .namespace import normalize_namespace
from .policy import RuntimePolicy, apply_policies, policy_metadata


@dataclass
class ToolSelection:
    """Bounded, deterministic result of metadata-driven Tool selection."""

    selected_tools: list[ToolDefinition] = field(default_factory=list)
    namespaces: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    expert_knowledge: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "namespaces": list(self.namespaces),
            "tool_count": len(self.selected_tools),
            "tools": [tool.name for tool in self.selected_tools],
            "context_keys": list(self.context),
            "expert_knowledge_available": bool(self.expert_knowledge),
        }


class ToolSelector:
    """Select Tools from registry metadata without domain vocabularies."""

    def __init__(
        self,
        *,
        policies: Optional[Iterable[RuntimePolicy]] = None,
        max_tools_per_namespace: int = 8,
    ) -> None:
        if max_tools_per_namespace <= 0:
            raise ValueError("max_tools_per_namespace must be positive")
        self.policies = list(policies or ())
        self.max_tools_per_namespace = int(max_tools_per_namespace)

    def set_policies(self, policies: Iterable[RuntimePolicy] | None) -> None:
        self.policies = list(policies or ())

    def select(
        self,
        *,
        user_input: str,
        intent: ParsedIntent,
        available_tools: Sequence[ToolDefinition],
    ) -> ToolSelection:
        tools = list(available_tools or ())
        namespaces = list(getattr(intent, "namespaces", None) or ())
        if not namespaces:
            namespaces = self.detect_namespaces(user_input, tools)
        if self.policies:
            namespaces = apply_policies(self.policies, namespaces)
            if not namespaces:
                namespaces = apply_policies(
                    self.policies, self.registered_namespaces(tools)
                )

        selected: list[ToolDefinition] = []
        for namespace in namespaces:
            scoped = [
                tool for tool in tools
                if normalize_namespace(getattr(tool, "namespace", ""))
                == normalize_namespace(namespace)
            ]
            selected.extend(
                self.filter_by_intent(scoped, getattr(intent, "intent_type", ""))
            )
        return ToolSelection(
            selected_tools=selected,
            namespaces=list(dict.fromkeys(namespaces)),
            context={
                "intent_type": str(getattr(intent, "intent_type", "") or ""),
                "intent_attributes": dict(
                    getattr(intent, "attributes", {}) or {}
                ),
                **policy_metadata(self.policies),
            },
        )

    def registered_namespaces(
        self, available_tools: Sequence[ToolDefinition]
    ) -> list[str]:
        return sorted({
            normalize_namespace(getattr(tool, "namespace", ""))
            for tool in (available_tools or ())
            if normalize_namespace(getattr(tool, "namespace", ""))
        })

    def detect_namespaces(
        self,
        user_input: str,
        available_tools: Sequence[ToolDefinition],
    ) -> list[str]:
        text = str(user_input or "").casefold()
        mentions: list[tuple[int, str]] = []
        for namespace in self.registered_namespaces(available_tools):
            aliases = {
                namespace,
                namespace.replace("-", " "),
                namespace.replace("_", " "),
            }
            positions = [
                text.find(alias.casefold())
                for alias in aliases
                if alias and text.find(alias.casefold()) >= 0
            ]
            if positions:
                mentions.append((min(positions), namespace))
        return [namespace for _, namespace in sorted(mentions)]

    def filter_by_intent(
        self,
        tools: Sequence[ToolDefinition],
        intent_type: str,
    ) -> list[ToolDefinition]:
        if not intent_type:
            return list(tools)[: self.max_tools_per_namespace]
        exact = [
            tool for tool in tools
            if intent_type in (getattr(tool, "intent_types", None) or [])
        ]
        return exact[: self.max_tools_per_namespace]


class PromptRenderer:
    """Render a bounded Tool contract for a model or UI preview."""

    def __init__(self, *, max_description_chars: int = 180) -> None:
        if max_description_chars <= 0:
            raise ValueError("max_description_chars must be positive")
        self.max_description_chars = int(max_description_chars)

    def render(self, selection: ToolSelection) -> str:
        if not selection.selected_tools:
            return "暂无可用工具"
        scope = ", ".join(selection.namespaces) or "未指定"
        lines = [f"## 可用工具（namespace: {scope}）"]
        for index, tool in enumerate(selection.selected_tools, 1):
            lines.append(
                f"{index}. **{tool.name}** ({tool.risk_level.value})"
            )
            description = str(tool.description or "")
            if len(description) > self.max_description_chars:
                description = description[: self.max_description_chars] + "..."
            lines.append(f"   描述: {description}")
            schema = tool.input_schema
            if schema.properties:
                lines.append(f"   参数: {list(schema.properties)}")
                enum_fields = {
                    name: spec.get("enum")
                    for name, spec in schema.properties.items()
                    if isinstance(spec, dict) and spec.get("enum") is not None
                }
                if enum_fields:
                    lines.append(f"   固定选项: {enum_fields}")
                lookup_fields = {
                    name: (
                        spec.get("lookup_tool")
                        or (
                            spec.get("lookup", {}).get("tool")
                            if isinstance(spec.get("lookup"), dict)
                            else None
                        )
                    )
                    for name, spec in schema.properties.items()
                    if isinstance(spec, dict)
                    and (
                        spec.get("lookup_tool")
                        or isinstance(spec.get("lookup"), dict)
                    )
                }
                lookup_fields = {
                    name: tool_name
                    for name, tool_name in lookup_fields.items()
                    if tool_name
                }
                if lookup_fields:
                    lines.append(f"   动态选项查询工具: {lookup_fields}")
            if schema.required:
                lines.append(f"   必填: {schema.required}")
            if schema.requires:
                lines.append(f"   执行契约必填: {schema.requires}")
            if schema.requires_any_of:
                lines.append(f"   执行契约至少选择一项: {schema.requires_any_of}")
            if schema.requires_exactly_one_of:
                lines.append(
                    "   执行契约必须且只能选择一项: "
                    f"{schema.requires_exactly_one_of}"
                )
            if schema.conditional_rules:
                lines.append(f"   条件依赖: {schema.conditional_rules}")
            lines.append("")
        if selection.expert_knowledge:
            lines.extend(["## 专家知识", selection.expert_knowledge[:1000]])
        return "\n".join(lines)


__all__ = ["PromptRenderer", "ToolSelection", "ToolSelector"]
