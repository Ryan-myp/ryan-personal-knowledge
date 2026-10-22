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
    "check", "find", "get", "list", "look at", "read", "search", "query",
    "fetch", "retrieve", "show",
    "which", "what", "available",
    "查一下", "查找", "找一下", "查询", "列出", "列表", "清单", "查看",
    "看下", "看看", "看一下", "帮我看", "瞧一下", "获取", "检索", "搜索",
    "有哪些", "有啥", "哪几个", "哪些",
)
_LIST_READ_CUES = ("list", "列出", "列表", "清单")
_DETAIL_READ_CUES = ("detail", "details", "详情", "详细信息", "具体信息")
_READ_ACTION_CUES = tuple(
    cue for cue in _READ_CUES if cue not in {"which", "what", "available"}
)
_WRITE_CUES = (
    "create", "execute", "generate", "run", "update", "delete", "pause", "enable", "disable", "launch",
    "submit", "save", "publish", "edit", "change", "modify", "set",
    "创建", "新建", "生成", "执行", "运行", "更新", "修改", "删除", "暂停", "启用", "停用",
    "上线", "提交", "保存", "发布", "设置", "调整",
)
_WRITE_NEGATIONS = (
    "do not", "don't", "dont", "never", "without", "avoid", "no need to",
    "不要", "别", "禁止", "不需要", "无需", "不用",
)
_AMBIGUOUS_OPERATION_CUES = frozenset({"set", "设置"})
_KNOWLEDGE_EXPLANATION_CUES = (
    "相关知识", "基础知识", "基础概念", "知识介绍", "讲下", "讲讲", "讲一讲",
    "介绍一下", "介绍下", "给我介绍", "告诉我", "科普一下",
    "详解", "详细讲解", "详细解释", "讲解一下", "讲解下", "解释一下", "解释下",
    "怎么理解", "是什么", "是什么意思", "是什么概念", "原理是什么", "有什么区别",
    "有啥区别", "有何区别", "区别是什么", "对比一下", "what is", "what are", "tell me about",
    "overview", "basics", "fundamentals", "explain", "difference between",
)
_INTENT_REVERSALS = ("but", "instead", "however", "但", "而是", "不过")
_SCOPE_RELATION = re.compile(r"(?:下(?:面|的)?|之下|里面|\bunder\b|\bwithin\b|\bin\b)")
_MULTI_TARGET = re.compile(r"(?:以及|同时|并且|和|与|、|\band\b|\balso\b)")
_CONTEXT_REFERENCE_CUES = (
    "this", "that", "these", "those", "same", "above", "previous",
    "earlier", "continue", "again", "这个", "这些", "那个", "那些",
    "它", "上面", "之前", "刚才", "刚刚", "继续", "再来", "接着",
    "为什么", "为啥", "什么原因", "原因呢", "怎么回事", "why",
    "有模板吗", "有模板", "模板呢", "any template", "any templates",
)
_CONTEXT_FILLER_CUES = (
    "我要", "我想", "帮我", "请帮我", "请问", "麻烦", "一下",
    "please", "could you", "would you",
)
_KNOWLEDGE_FOLLOWUP_CUES = (
    "为什么", "为啥", "什么原因", "原因呢", "怎么回事", "why",
)
_PROCESS_CUES = (
    "流程", "工作流", "workflow", "process",
)
_PROCESS_CLAUSE_SEPARATORS = re.compile(
    r"(?:[，,。；;]|并且|然后|同时|并|以及|\b(?:and|then|also|but)\b)"
)
_READ_ACTIONS = frozenset({
    "find", "get", "list", "read", "search", "query", "fetch", "retrieve",
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


def _cue_matches(text: str, cue: str):
    if re.fullmatch(r"[a-z]+", cue):
        stem = re.escape(cue)
        variants = [f"{stem}(?:s|d|ed|ing)?", f"{stem}{cue[-1]}ing"]
        if cue.endswith("e"):
            variants.append(f"{re.escape(cue[:-1])}ing")
        return re.finditer(r"\b(?:" + "|".join(variants) + r")\b", text)
    return re.finditer(re.escape(cue), text)


def _contains_cue(text: str, cue: str) -> bool:
    return next(_cue_matches(text, cue), None) is not None


def _request_verbs(user_input: str, tools: Sequence[Any]) -> str:
    """Remove compound resource nouns before classifying request verbs."""
    text = str(user_input or "").casefold()
    for resource in {
        str(_tool_field(tool, "resource_type")).casefold() for tool in tools
    }:
        parts = re.findall(r"[a-z0-9]+", resource)
        if len(parts) > 1:
            pattern = r"\b" + r"[\s_-]*".join(map(re.escape, parts)) + r"s?\b"
            text = re.sub(pattern, " ", text)
    return text


def _is_read_only_request(user_input: str) -> bool:
    text = str(user_input or "").casefold()
    if not any(_contains_cue(text, cue) for cue in _READ_CUES):
        return False
    for cue in _WRITE_CUES:
        for match in _cue_matches(text, cue):
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


def _has_explicit_read_action(user_input: str) -> bool:
    text = str(user_input or "").casefold()
    return any(_contains_cue(text, cue) for cue in _READ_ACTION_CUES)


def _is_explicit_list_request(user_input: str) -> bool:
    text = str(user_input or "").casefold()
    return any(_contains_cue(text, cue) for cue in _LIST_READ_CUES)


def _has_unnegated_action_cue(user_input: str, cues: Sequence[str]) -> bool:
    text = str(user_input or "").casefold()
    for cue in cues:
        for match in _cue_matches(text, cue):
            prefix = text[max(0, match.start() - 32):match.start()]
            negation_positions = [
                prefix.rfind(negation)
                for negation in _WRITE_NEGATIONS
                if prefix.rfind(negation) >= 0
            ]
            if not negation_positions:
                return True
            last_negation = max(negation_positions)
            if any(
                reversal in prefix[last_negation + 1:]
                for reversal in _INTENT_REVERSALS
            ):
                return True
    return False


def _has_unnegated_write_cue(user_input: str) -> bool:
    return _has_unnegated_action_cue(user_input, _WRITE_CUES)


def _needs_conversation_context(user_input: str, tools: Sequence[Any]) -> bool:
    """Reuse prior scope only for references to a known registered resource."""
    text = str(user_input or "").strip()
    if not text:
        return False
    if (
        _is_read_only_request(_request_verbs(text, tools))
        and any(
            _is_read_tool(tool) and _matches_publisher_target(text, tool)
            for tool in tools or ()
        )
    ):
        return True
    if len(text) > 64 or not any(
        _contains_cue(text.casefold(), cue)
        for cue in _CONTEXT_REFERENCE_CUES
    ):
        return False
    residual = text.casefold()
    for cue in sorted(
        (
            *_CONTEXT_REFERENCE_CUES,
            *_CONTEXT_FILLER_CUES,
            *_READ_CUES,
            *_WRITE_CUES,
        ),
        key=len,
        reverse=True,
    ):
        residual = residual.replace(cue.casefold(), " ")
    residual = re.sub(r"\b\d+\b", " ", residual)
    return not _terms(residual)


def _is_process_explanation_request(
    user_input: str,
    tools: Sequence[Any],
) -> bool:
    """Keep workflow explanations separate from operational Tool requests."""
    text = str(user_input or "").casefold()
    if _is_read_only_request(_request_verbs(user_input, tools)):
        return False
    if not any(_contains_cue(text, cue) for cue in _PROCESS_CUES):
        return False

    # A separate actionable clause remains routable. Verbs inside the workflow
    # topic itself describe a process, not an execution request.
    for clause in _PROCESS_CLAUSE_SEPARATORS.split(text):
        if not clause.strip() or any(
            _contains_cue(clause, cue) for cue in _PROCESS_CUES
        ):
            continue
        verb_text = _request_verbs(clause, tools)
        if (
            _has_unnegated_write_cue(verb_text)
            or _is_read_only_request(verb_text)
        ):
            return False
    return True


def _is_knowledge_explanation_request(
    user_input: str,
    tools: Sequence[Any],
) -> bool:
    """Keep explicit conceptual explanations out of the executable Tool set."""
    text = str(user_input or "").casefold()
    if not any(_contains_cue(text, cue) for cue in _KNOWLEDGE_EXPLANATION_CUES):
        return False

    action_text = _request_verbs(text, tools)
    is_comparison = any(
        _contains_cue(text, cue)
        for cue in ("有什么区别", "有啥区别", "有何区别", "区别是什么", "对比一下")
    )
    if _has_explicit_read_action(action_text) and not is_comparison:
        return False
    strong_write_cues = tuple(
        cue for cue in _WRITE_CUES if cue not in _AMBIGUOUS_OPERATION_CUES
    )
    return not _has_unnegated_action_cue(action_text, strong_write_cues)


def _is_read_tool(tool: Any) -> bool:
    effect = _tool_field(
        tool,
        "effect_class",
        _tool_field(tool, "effect", "read"),
    )
    effect = getattr(effect, "value", effect)
    return str(effect or "read").strip().casefold() in {"read", "none"}


def _is_knowledge_tool(tool: Any) -> bool:
    traits = _tool_field(tool, "traits", ()) or ()
    if isinstance(traits, str):
        traits = (traits,)
    normalized_traits = {
        str(item).strip().casefold() for item in traits
    }
    resource = str(_tool_field(tool, "resource_type", "")).strip().casefold()
    return "knowledge" in normalized_traits or resource == "knowledge"


def _is_web_search_tool(tool: Any) -> bool:
    traits = _tool_field(tool, "traits", ()) or ()
    if isinstance(traits, str):
        traits = (traits,)
    return "web_search" in {
        str(item).strip().casefold() for item in traits
    }


def _is_semantic_discovery_tool(tool: Any) -> bool:
    traits = _tool_field(tool, "traits", ()) or ()
    if isinstance(traits, str):
        traits = (traits,)
    return (
        _is_read_tool(tool)
        and "semantic_discovery" in {
            str(item).strip().casefold() for item in traits
        }
    )


def _semantic_discovery_tools(tools: Sequence[Any]) -> list[Any]:
    return [
        tool for tool in tools or ()
        if _is_semantic_discovery_tool(tool)
    ]


def _matches_tool_alias(text: str, tool: Any) -> bool:
    normalized = str(text or "").casefold()
    aliases = _tool_field(tool, "intent_aliases", ()) or ()
    if isinstance(aliases, str):
        aliases = (aliases,)
    return any(
        len(alias_text := str(alias).strip()) >= 3
        and alias_text.casefold() in normalized
        for alias in aliases
    )


def _matches_publisher_target(text: str, tool: Any) -> bool:
    """Match only a Tool-published resource or alias, never its namespace alone."""
    query_terms = _terms(text)
    resource_terms = _terms(_tool_field(tool, "resource_type", ""))
    if resource_terms and resource_terms <= query_terms:
        return True

    namespace_terms = _terms(_tool_field(tool, "namespace", ""))
    action_terms = _terms(" ".join((*_READ_CUES, *_WRITE_CUES)))
    query_core = query_terms - namespace_terms - action_terms
    aliases = _tool_field(tool, "intent_aliases", ()) or ()
    if isinstance(aliases, str):
        aliases = (aliases,)
    for alias in aliases:
        alias_text = str(alias or "").strip().casefold()
        if not alias_text:
            continue
        if alias_text in str(text or "").casefold():
            return True
        if not re.search(r"[\u3400-\u9fff]", alias_text):
            continue
        alias_terms = _terms(alias_text) - namespace_terms - action_terms
        if alias_terms and len(query_core & alias_terms) >= max(
            1, (len(alias_terms) + 1) // 2,
        ):
            return True
        alias_core = alias_text
        query_text = str(text or "").casefold()
        for cue in sorted(
            (*_READ_CUES, *_WRITE_CUES),
            key=len,
            reverse=True,
        ):
            alias_core = alias_core.replace(cue.casefold(), " ")
            query_text = query_text.replace(cue.casefold(), " ")
        for namespace in (
            str(_tool_field(tool, "namespace", "") or "").casefold(),
            str(_tool_field(tool, "namespace", "") or "")
            .replace("-", " ").casefold(),
        ):
            if namespace:
                alias_core = alias_core.replace(namespace, " ")
                query_text = query_text.replace(namespace, " ")
        alias_core = re.sub(r"[\W_]+", "", alias_core)
        query_core_text = re.sub(r"[\W_]+", "", query_text)
        if len(alias_core) >= 2 and alias_core in query_core_text:
            return True

    operational_request = (
        _is_read_only_request(_request_verbs(text, (tool,)))
        or _has_unnegated_write_cue(_request_verbs(text, (tool,)))
    )
    if operational_request:
        intent_types = _tool_field(tool, "intent_types", ()) or ()
        if isinstance(intent_types, str):
            intent_types = (intent_types,)
        for intent in intent_types:
            intent_core = _terms(intent) - namespace_terms - action_terms
            if intent_core and len(query_core & intent_core) >= max(
                1, (len(intent_core) + 1) // 2,
            ):
                return True
    return False


def _matches_short_cjk_alias(text: str, tool: Any) -> bool:
    """Match publisher-declared two-character CJK aliases without fuzzy terms."""
    normalized = str(text or "").casefold()
    aliases = _tool_field(tool, "intent_aliases", ()) or ()
    if isinstance(aliases, str):
        aliases = (aliases,)
    return any(
        re.fullmatch(r"[\u3400-\u9fff]{2}", alias_text)
        and alias_text.casefold() in normalized
        for alias in aliases
        if (alias_text := str(alias).strip())
    )


def _is_knowledge_followup(text: str) -> bool:
    normalized = str(text or "").casefold()
    return any(
        _contains_cue(normalized, cue)
        for cue in _KNOWLEDGE_FOLLOWUP_CUES
    )


def _is_short_comparative_followup(text: str) -> bool:
    normalized = " ".join(str(text or "").casefold().split())
    if not normalized or len(normalized) > 64:
        return False
    if re.match(r"^(?:(?:and|so)\s+)?(?:what|how)\s+about\b", normalized):
        return True
    return re.search(r"(?:呢|怎么样|如何)[?？。！!]*$", normalized) is not None


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


def _explicit_resource_list_tools(
    user_input: str,
    tools: Sequence[Any],
) -> list[Any]:
    """Keep one list Tool per explicitly requested resource and namespace."""
    text = str(user_input or "").casefold()
    query_terms = _terms(user_input)
    selected: dict[tuple[str, str], tuple[int, int, Any]] = {}
    for index, tool in enumerate(tools):
        if (
            not _is_read_tool(tool)
            or str(_tool_field(tool, "action", "")).casefold() != "list"
        ):
            continue
        resource = str(_tool_field(tool, "resource_type", "") or "").strip()
        resource_terms = _terms(resource)
        aliases = _tool_field(tool, "intent_aliases", ()) or ()
        if isinstance(aliases, str):
            aliases = (aliases,)
        explicitly_named = bool(
            resource_terms and resource_terms <= query_terms
        ) or any(
            len(alias_text := str(alias).strip()) >= 3
            and alias_text.casefold() in text
            for alias in aliases
        )
        if not explicitly_named:
            continue
        key = (
            normalize_namespace(_tool_field(tool, "namespace", "")),
            resource,
        )
        score = _relevance_score(query_terms, tool)
        previous = selected.get(key)
        if previous is None or score > previous[1]:
            selected[key] = (index, score, tool)

    matches = sorted(selected.values(), key=lambda item: item[0])
    return [tool for _index, _score, tool in matches]


def _alias_scoped_reads(user_input: str, tools: Sequence[Any]) -> list[Any]:
    """Honor explicit publisher query aliases without a domain vocabulary."""
    text = str(user_input or "").casefold()
    matched = [
        tool for tool in tools if _is_read_tool(tool)
        and any(
            len(str(alias).strip()) >= 3
            and str(alias).strip().casefold() in text
            for alias in _tool_field(tool, "intent_aliases", ()) or ()
        )
    ]
    if not matched:
        return list(tools)
    namespaces = {str(_tool_field(tool, "namespace")) for tool in tools}
    matched_namespaces = {str(_tool_field(tool, "namespace")) for tool in matched}
    if len(namespaces) > 1 and matched_namespaces != namespaces:
        return list(tools)
    matched_resources = {
        str(_tool_field(tool, "resource_type")) for tool in matched
    }
    parent_scopes = {
        str(parent)
        for tool in matched
        if (parent := _tool_field(tool, "parent_resource_type", None))
    }
    has_single_parent_scope = (
        bool(_SCOPE_RELATION.search(text))
        and not _MULTI_TARGET.search(text)
    )
    if not has_single_parent_scope:
        parent_scopes.clear()
    elif parent_scopes:
        matched = [
            tool for tool in matched
            if str(_tool_field(tool, "resource_type")) not in parent_scopes
        ]
        matched_resources = {
            str(_tool_field(tool, "resource_type")) for tool in matched
        }
    namespace_terms = set().union(*(
        _terms(_tool_field(tool, "namespace")) for tool in tools
    ))
    query_terms = _terms(user_input) - namespace_terms
    shared_terms = namespace_terms | _terms(" ".join((*_READ_CUES, *_WRITE_CUES))) | set().union(*(
        _terms(_tool_field(tool, "intent_aliases", ()))
        | _terms(_tool_field(tool, "description"))
        for tool in matched
    ))
    explicit_details = [
        tool for tool in tools if _is_read_tool(tool)
        and str(_tool_field(tool, "resource_type")) in matched_resources
        and bool(query_terms & (
            (
                _terms(_tool_field(tool, "intent_aliases", ()))
                | _terms(_tool_field(tool, "description"))
            ) - shared_terms
        ))
    ]
    other_targets = any(
        resource not in matched_resources | parent_scopes
        and bool(terms := _terms(resource))
        and terms <= query_terms
        for tool in tools
        if (resource := str(_tool_field(tool, "resource_type")))
    )
    if other_targets:
        return list(tools)
    selected_ids = {id(tool) for tool in (*matched, *explicit_details)}
    return [tool for tool in tools if id(tool) in selected_ids]


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
        max_read_tools_per_turn: int = 12,
    ) -> None:
        if max_tools_per_namespace <= 0:
            raise ValueError("max_tools_per_namespace must be positive")
        if max_read_tools_per_turn <= 0:
            raise ValueError("max_read_tools_per_turn must be positive")
        self.policies = list(policies or ())
        self.max_tools_per_namespace = int(max_tools_per_namespace)
        self.max_read_tools_per_turn = int(max_read_tools_per_turn)

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
        conversation_context: Sequence[str] = (),
        contextual_namespaces: Sequence[str] = (),
    ) -> list[Any]:
        """Rank a bounded Tool subset using only publisher-owned metadata.

        A zero-score request receives no executable Tool definitions. This
        keeps unrelated Tools out of model context instead of falling back to
        an arbitrary prefix of the registry. Recent user turns may resolve a
        short follow-up, but the current utterance alone determines whether a
        request is read-only.
        """
        if limit <= 0:
            raise ValueError("limit must be positive")
        if _is_process_explanation_request(user_input, available_tools):
            return []
        if _is_knowledge_explanation_request(user_input, available_tools):
            return _semantic_discovery_tools(available_tools)[:limit]
        text = str(user_input or "").casefold()
        verb_text = _request_verbs(user_input, available_tools)
        if (
            _is_short_comparative_followup(text)
            and not _has_explicit_read_action(verb_text)
            and not _has_unnegated_write_cue(verb_text)
        ):
            return []
        prior_inputs = [
            str(item or "").strip()
            for item in (conversation_context or ())
            if str(item or "").strip()
        ][-4:]
        if not _needs_conversation_context(user_input, available_tools):
            prior_inputs = []
        prior_inputs = _bounded_context_inputs(prior_inputs, max_chars=1200)
        read_only_request = _is_read_only_request(verb_text)
        detected_namespaces = self.detect_namespaces(
            user_input, available_tools,
        )
        allowed_namespaces = set(
            apply_policies(self.policies, detected_namespaces)
        )
        denied_namespaces = set(detected_namespaces) - allowed_namespaces
        known_resource_target = any(
            _matches_publisher_target(user_input, tool)
            for tool in available_tools or ()
        )
        blocked_policy_operation = bool(denied_namespaces) and (
            _has_unnegated_write_cue(verb_text)
            or (
                read_only_request
                and (known_resource_target or _is_explicit_list_request(verb_text))
            )
        )
        if (
            blocked_policy_operation
            and not self.explicitly_requests_discovery(
                user_input, available_tools,
            )
        ):
            return []
        # A namespace names a provider, not an account operation. Route into
        # it only when the current request also matches a published resource.
        active_namespaces = [
            namespace for namespace in detected_namespaces
            if any(
                normalize_namespace(_tool_field(tool, "namespace", ""))
                == normalize_namespace(namespace)
                and _matches_publisher_target(user_input, tool)
                for tool in available_tools or ()
            )
        ]
        if not active_namespaces:
            registered_namespaces = set(
                self.registered_namespaces(available_tools)
            )
            contextual = list(dict.fromkeys(
                normalized
                for namespace in (contextual_namespaces or ())
                if (normalized := normalize_namespace(namespace))
                and normalized in registered_namespaces
            ))
            matching_context = [
                namespace for namespace in contextual
                if any(
                    normalize_namespace(_tool_field(tool, "namespace", ""))
                    == namespace
                    and _is_read_tool(tool)
                    and _matches_publisher_target(user_input, tool)
                    for tool in available_tools or ()
                )
            ]
            active_namespaces = matching_context or (
                contextual if _needs_conversation_context(
                    user_input, available_tools
                ) else []
            )
        if active_namespaces:
            prior_inputs = []
        else:
            for prior_input in reversed(prior_inputs):
                active_namespaces = self.detect_namespaces(
                    prior_input, available_tools,
                )
                if active_namespaces:
                    break

        explicitly_named = [
            tool for tool in (available_tools or ())
            if (name := str(_tool_field(tool, "name", "") or "").strip())
            and name.casefold() in text
        ]
        explicitly_aliased_reads = [
            tool for tool in (available_tools or ())
            if _is_read_tool(tool)
            and _matches_tool_alias(text, tool)
        ]
        explicitly_aliased_writes = [
            tool for tool in (available_tools or ())
            if not _is_read_tool(tool)
            and _matches_short_cjk_alias(text, tool)
        ]
        explicitly_aliased_knowledge = [
            tool for tool in explicitly_aliased_reads
            if _is_knowledge_tool(tool)
        ]
        explicitly_aliased_web_search = [
            tool for tool in explicitly_aliased_reads
            if _is_web_search_tool(tool)
        ]
        explicitly_aliased_transform = [
            tool for tool in explicitly_aliased_reads
            if str(_tool_field(tool, "resource_type", "")).casefold()
            == "json_records"
        ]
        contextual_knowledge = [
            tool for tool in (available_tools or ())
            if _is_read_tool(tool)
            and _is_knowledge_tool(tool)
            and any(
                _matches_tool_alias(previous, tool)
                for previous in prior_inputs
            )
        ]
        if explicitly_named:
            candidates = explicitly_named
        elif explicitly_aliased_web_search:
            candidates = explicitly_aliased_web_search
        elif explicitly_aliased_knowledge:
            candidates = explicitly_aliased_knowledge
        elif contextual_knowledge and _is_knowledge_followup(text):
            candidates = contextual_knowledge
        elif active_namespaces:
            namespace_set = {
                normalize_namespace(item) for item in active_namespaces
            }
            candidates = [
                tool for tool in (available_tools or ())
                if normalize_namespace(
                    _tool_field(tool, "namespace", "")
                ) in namespace_set
            ]
        elif (
            len(explicitly_aliased_writes) == 1
            and _has_unnegated_write_cue(verb_text)
        ):
            candidates = explicitly_aliased_writes
        elif explicitly_aliased_transform:
            candidates = explicitly_aliased_transform
        else:
            candidates = list(available_tools or ())
        targeted_candidates = [
            tool for tool in candidates
            if _matches_publisher_target(user_input, tool)
        ]
        if read_only_request and targeted_candidates:
            candidates = targeted_candidates
        if (
            not _has_unnegated_write_cue(verb_text)
            and not explicitly_named
        ):
            discovery_tools = _semantic_discovery_tools(available_tools)
            if (
                not targeted_candidates
                and not active_namespaces
                and discovery_tools
            ):
                return discovery_tools[:min(
                    limit, self.max_read_tools_per_turn
                )]
        if (
            not explicitly_named
            and not explicitly_aliased_knowledge
            and not explicitly_aliased_transform
            and read_only_request
        ):
            candidates = _alias_scoped_reads(user_input, candidates)
        current_terms = _terms(user_input)
        has_explicit_resource = any(
            (resource_terms := _terms(_tool_field(tool, "resource_type")))
            and resource_terms <= current_terms
            for tool in candidates
        )
        # A current-turn resource mention must outrank stale topics from history.
        query_terms = set(current_terms)
        if prior_inputs and not has_explicit_resource:
            query_terms.update(_terms(" ".join(prior_inputs)))
        if not query_terms:
            return []
        ranked = [
            (_relevance_score(query_terms, tool), index, tool)
            for index, tool in enumerate(candidates)
        ]
        relevant = [item for item in ranked if item[0] > 0]
        if read_only_request:
            relevant = [
                item for item in relevant
                if _is_read_tool(item[2])
            ]
            has_detail_read = any(
                _contains_cue(verb_text, cue) for cue in _DETAIL_READ_CUES
            )
            if _is_explicit_list_request(verb_text) and not has_detail_read:
                list_tools = [
                    item for item in relevant
                    if str(_tool_field(item[2], "action", "")).casefold() == "list"
                ]
                if list_tools:
                    explicit_resource_tools = [
                        item for item in list_tools
                        if (resource_terms := _terms(
                            _tool_field(item[2], "resource_type")
                        ))
                        and resource_terms <= current_terms
                    ]
                    relevant = explicit_resource_tools or list_tools
        relevant.sort(key=lambda item: (-item[0], item[1]))
        effective_limit = (
            min(limit, self.max_read_tools_per_turn)
            if read_only_request
            else limit
        )
        ranked_tools = [tool for _score, _index, tool in relevant]
        explicit_resources = {
            str(_tool_field(tool, "resource_type", "") or "")
            for tool in _explicit_resource_list_tools(
                user_input, candidates,
            )
        }
        has_multi_resource_list = (
            read_only_request
            and not any(
                _contains_cue(verb_text, cue) for cue in _DETAIL_READ_CUES
            )
            and len(explicit_resources) >= 2
        )
        if has_multi_resource_list:
            priority_tools = _explicit_resource_list_tools(
                user_input, candidates,
            )
            priority_ids = {id(tool) for tool in priority_tools}
            ranked_tools = [
                *priority_tools,
                *(tool for tool in ranked_tools if id(tool) not in priority_ids),
            ]
        if (
            not active_namespaces
            and not explicitly_named
            and not explicitly_aliased_reads
            and not explicitly_aliased_writes
            and not read_only_request
            and not _has_unnegated_write_cue(verb_text)
        ):
            discovery = _semantic_discovery_tools(available_tools)
            discovery_ids = {id(tool) for tool in discovery}
            ranked_tools = [
                *discovery,
                *(tool for tool in ranked_tools if id(tool) not in discovery_ids),
            ]
        return ranked_tools[:effective_limit]

    @staticmethod
    def is_read_only_request(
        user_input: str,
        tools: Sequence[Any] = (),
    ) -> bool:
        """Expose the selector's read/write classification to app adapters."""
        return _is_read_only_request(_request_verbs(user_input, tools))

    def requires_tool_call(
        self,
        user_input: str,
        selected_tools: Sequence[Any],
        *,
        conversation_context: Sequence[str] = (),
    ) -> bool:
        """Require fresh execution for operational reads and explicit writes."""
        verb_text = _request_verbs(user_input, selected_tools)
        write_request = _has_unnegated_write_cue(verb_text)
        read_request = not write_request and _is_read_only_request(verb_text)
        text = str(user_input or "").casefold()
        selected_knowledge = [
            tool for tool in (selected_tools or ())
            if _is_read_tool(tool) and _is_knowledge_tool(tool)
        ]
        if selected_knowledge and any(
            _matches_tool_alias(text, tool)
            for tool in selected_knowledge
        ):
            return True
        if (
            selected_knowledge
            and _is_knowledge_followup(text)
            and any(
                _matches_tool_alias(str(previous or ""), tool)
                for previous in conversation_context
                for tool in selected_knowledge
            )
        ):
            return True
        if read_request and any(cue in text for cue in (
            "支持", "能力", "capabilities", "support",
        )):
            return False
        historical_summary = any(cue in text for cue in (
            "汇总", "总结", "summarize", "summary",
        )) and any(cue in text for cue in (
            "刚才", "之前", "上述", "previous", "earlier",
        ))
        web_search_match = any(
            _is_read_tool(tool)
            and _is_web_search_tool(tool)
            and _matches_tool_alias(text, tool)
            for tool in (selected_tools or ())
        )
        if web_search_match and not historical_summary:
            if any(cue in text for cue in (
                "支持", "能力", "capabilities", "support",
            )):
                return False
            return True
        if (
            read_request and not historical_summary
            and (
                _is_knowledge_explanation_request(user_input, selected_tools)
                or any(
                    _contains_cue(verb_text, cue)
                    for cue in _READ_ACTION_CUES
                    if cue not in {"有哪些", "有啥", "哪几个", "哪些"}
                )
            )
            and any(_is_web_search_tool(tool) for tool in (selected_tools or ()))
        ):
            return True
        if historical_summary or not (write_request or read_request):
            return False
        terms = _terms(user_input)
        for cue in (*_WRITE_CUES, *_READ_CUES):
            terms.difference_update(_terms(cue))
        if not terms:
            return False
        return any(
            (_is_read_tool(tool) if read_request else not _is_read_tool(tool))
            and bool(
                terms & (
                    _terms(_tool_field(tool, "name"))
                    | _terms(_tool_field(tool, "resource_type"))
                    | _terms(_tool_field(tool, "intent_types", ()))
                    | _terms(_tool_field(tool, "intent_aliases", ()))
                )
            )
            for tool in (selected_tools or ())
        )

    def registered_namespaces(
        self, available_tools: Sequence[ToolDefinition]
    ) -> list[str]:
        return sorted({
            normalize_namespace(_tool_field(tool, "namespace", ""))
            for tool in (available_tools or ())
            if normalize_namespace(_tool_field(tool, "namespace", ""))
        })

    @staticmethod
    def has_declared_resource_target(
        user_input: str,
        tools: Sequence[Any],
    ) -> bool:
        """Report whether the request matches a Tool-published resource."""
        return any(
            _matches_publisher_target(user_input, tool)
            for tool in tools or ()
        )

    @staticmethod
    def explicitly_requests_discovery(
        user_input: str,
        tools: Sequence[Any],
    ) -> bool:
        """Recognize discovery requests only through registered Tool aliases."""
        return any(
            _is_semantic_discovery_tool(tool)
            and _matches_tool_alias(user_input, tool)
            for tool in tools or ()
        )

    def detect_namespaces(
        self,
        user_input: str,
        available_tools: Sequence[ToolDefinition],
    ) -> list[str]:
        text = str(user_input or "").casefold()
        mentions: list[tuple[int, str]] = []
        declared_namespaces: list[str] = self.registered_namespaces(
            available_tools
        )
        for policy in self.policies:
            known_namespaces = getattr(policy, "known_namespaces", None)
            if callable(known_namespaces):
                declared_namespaces.extend(
                    str(item).strip()
                    for item in (known_namespaces() or ())
                    if str(item).strip()
                )
        for namespace in dict.fromkeys(declared_namespaces):
            namespace = normalize_namespace(namespace)
            if not namespace:
                continue
            aliases = {
                namespace,
                namespace.replace("-", " "),
                namespace.replace("_", " "),
            }
            aliases.update(
                term for term in _terms(namespace)
                if len(term) >= 4
            )
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


def _bounded_context_inputs(
    values: Sequence[str],
    *,
    max_chars: int,
) -> list[str]:
    """Keep the newest conversational hints within a small selection budget."""
    selected: list[str] = []
    remaining = max(0, int(max_chars))
    for value in reversed(values):
        if remaining <= 0:
            break
        bounded = str(value or "").strip()[-remaining:]
        if bounded:
            selected.append(bounded)
            remaining -= len(bounded)
    return list(reversed(selected))


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
