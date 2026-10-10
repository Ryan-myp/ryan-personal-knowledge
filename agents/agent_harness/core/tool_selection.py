"""Domain-neutral Tool selection and model-facing Tool prompt rendering.

The selector only evaluates publisher metadata and the parsed intent. It does
not query knowledge, load Skills, inspect credentials, or execute handlers.
Those concerns belong to an application adapter around this module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional, Sequence

from .interfaces import ParsedIntent, ToolDefinition
from .namespace import normalize_namespace
from .policy import RuntimePolicy, apply_policies, policy_metadata


_TOKEN_STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do",
    "for", "from", "how", "i", "in", "is", "it", "me", "my", "of",
    "on", "or", "please", "show", "the", "to", "we", "with", "you",
})
_READ_CUES = (
    "get", "list", "read", "search", "query", "fetch", "retrieve", "show",
    "查一下", "查询", "列出", "查看", "获取", "检索",
)
_WRITE_CUES = (
    "create", "update", "delete", "pause", "enable", "disable", "launch",
    "submit", "save", "publish", "edit", "change", "modify", "set",
    "创建", "新建", "更新", "修改", "删除", "暂停", "启用", "停用",
    "上线", "提交", "保存", "发布", "设置", "调整",
)
_WRITE_NEGATIONS = (
    "do not", "don't", "dont", "never", "without", "avoid", "no need to",
    "不要", "别", "禁止", "不需要", "无需", "不用",
)
_INTENT_REVERSALS = ("but", "instead", "however", "但", "而是", "不过")
_READ_ACTIONS = frozenset({
    "get", "list", "read", "search", "query", "fetch", "retrieve",
})


def _terms(value: Any) -> set[str]:
    text = str(value or "").casefold()
    tokens = {
        item for item in re.findall(r"[a-z0-9]+", text)
        if item not in _TOKEN_STOPWORDS
    }
    tokens.update(
        item[:-1] if item.endswith("s") and len(item) > 3 else item
        for item in tuple(tokens)
    )
    for run in re.findall(r"[\u3400-\u9fff]+", text):
        tokens.update(run[index:index + 2] for index in range(len(run) - 1))
    return tokens


def _tool_field(tool: Any, key: str, default: Any = "") -> Any:
    if isinstance(tool, dict):
        return tool.get(key, default)
    return getattr(tool, key, default)


def _schema_terms(tool: Any) -> set[str]:
    schema = _tool_field(tool, "input_schema", {})
    if callable(getattr(schema, "to_dict", None)):
        schema = schema.to_dict()
    properties = (
        schema.get("properties", {})
        if isinstance(schema, dict)
        else getattr(schema, "properties", {})
    )
    terms: set[str] = set()
    if isinstance(properties, dict):
        for name, spec in properties.items():
            terms.update(_terms(name))
            if isinstance(spec, dict):
                terms.update(_terms(spec.get("description", "")))
    return terms


def _contains_cue(text: str, cue: str) -> bool:
    if re.fullmatch(r"[a-z]+", cue):
        return re.search(rf"\b{re.escape(cue)}(?:s|ed|ing)?\b", text) is not None
    return cue in text


def _is_read_only_request(user_input: str) -> bool:
    text = str(user_input or "").casefold()
    if not any(_contains_cue(text, cue) for cue in _READ_CUES):
        return False
    for cue in _WRITE_CUES:
        for match in re.finditer(re.escape(cue), text):
            prefix = text[max(0, match.start() - 32):match.start()]
            negation_positions = [
                prefix.rfind(negation)
                for negation in _WRITE_NEGATIONS
                if prefix.rfind(negation) >= 0
            ]
            if not negation_positions:
                return False
            last_negation = max(negation_positions)
            if any(
                reversal in prefix[last_negation + 1:]
                for reversal in _INTENT_REVERSALS
            ):
                return False
    return True


def _is_read_tool(tool: Any) -> bool:
    effect = _tool_field(
        tool,
        "effect_class",
        _tool_field(tool, "effect", "read"),
    )
    effect = getattr(effect, "value", effect)
    return str(effect or "read").strip().casefold() in {"read", "none"}


def _relevance_score(query_terms: set[str], tool: Any) -> int:
    fields = (
        (6, _tool_field(tool, "name")),
        (5, _tool_field(tool, "namespace")),
        (5, _tool_field(tool, "intent_types", ())),
        (4, _tool_field(tool, "intent_aliases", ())),
        (3, _tool_field(tool, "action")),
        (3, _tool_field(tool, "resource_type")),
        (2, _tool_field(tool, "description")),
    )
    score = 0
    for weight, value in fields:
        overlap = query_terms & _terms(value)
        score += weight * min(len(overlap), 3)
    return score + len(query_terms & _schema_terms(tool))


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

    def select_relevant(
        self,
        user_input: str,
        available_tools: Sequence[Any],
        *,
        limit: int = 16,
    ) -> list[Any]:
        """Rank a bounded Tool subset using only publisher-owned metadata.

        A zero-score request receives no executable Tool definitions. This
        keeps unrelated Tools out of model context instead of falling back to
        an arbitrary prefix of the registry.
        """
        if limit <= 0:
            raise ValueError("limit must be positive")
        text = str(user_input or "").casefold()
        explicitly_named = [
            tool for tool in (available_tools or ())
            if (name := str(_tool_field(tool, "name", "") or "").strip())
            and name.casefold() in text
        ]
        if explicitly_named:
            candidates = explicitly_named
        else:
            candidates = list(available_tools or ())
        query_terms = _terms(user_input)
        if not query_terms:
            return []
        ranked = [
            (_relevance_score(query_terms, tool), index, tool)
            for index, tool in enumerate(candidates)
        ]
        relevant = [item for item in ranked if item[0] > 0]
        if _is_read_only_request(user_input):
            relevant = [
                item for item in relevant
                if _is_read_tool(item[2])
            ]
        relevant.sort(key=lambda item: (-item[0], item[1]))
        return [tool for _score, _index, tool in relevant[:limit]]

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
