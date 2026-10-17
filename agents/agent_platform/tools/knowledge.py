"""Generic, bounded read-only knowledge search Tool."""

from __future__ import annotations

import math
from collections.abc import Mapping
from itertools import islice
from typing import Any

from agents.agent_harness import StaticToolSource, ToolBinding
from agents.agent_harness.core.context import ContextQuery
from agents.agent_harness.core.interfaces import (
    ReplayPolicy,
    RiskLevel,
    ToolDefinition,
    ToolEffect,
    ToolResult,
    ToolSchema,
)
from agents.agent_harness.core.security import redact_sensitive_text


MAX_QUERY_CHARS = 1200
MAX_RESULTS = 10
MAX_EXCERPT_CHARS = 1200
MAX_NAMESPACES = 8

_CITATION_FIELDS = (
    "document_id",
    "title",
    "source",
    "source_ref",
    "source_kind",
    "authority",
    "evidence_level",
    "version",
    "updated_at",
    "last_verified_at",
    "section",
    "chunk_index",
    "chunk_count",
)
_RESULT_FIELDS = (
    "document_id",
    "title",
    "namespace",
    "topic",
    "excerpt",
    "source_ref",
    "confidence",
    "updated_at",
    "score",
    "citation",
)


def _trusted_tenant_id(context: Any) -> str:
    """Read tenant scope only from the Runtime-created execution context."""
    request = getattr(context, "request", None)
    principal = getattr(request, "principal", None) if request is not None else None
    value = getattr(principal, "tenant_id", None) if principal is not None else None
    if value in (None, ""):
        metadata = getattr(context, "metadata", None)
        if isinstance(metadata, Mapping):
            value = metadata.get("principal_tenant_id")
    tenant_id = str(value or "").strip()
    if not tenant_id or len(tenant_id) > 256:
        raise PermissionError("知识库查询缺少可信的租户身份")
    return tenant_id


def _document_mapping(document: Any) -> Mapping[str, Any]:
    for method_name in ("to_context_dict", "to_dict"):
        method = getattr(document, method_name, None)
        if callable(method):
            value = method()
            return value if isinstance(value, Mapping) else {}
    return document if isinstance(document, Mapping) else {}


def _safe_string(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return redact_sensitive_text(value)[:limit]


def _safe_citation(value: Any, fallback: Mapping[str, Any]) -> dict[str, Any]:
    source = value if isinstance(value, Mapping) else fallback
    citation: dict[str, Any] = {}
    for field in _CITATION_FIELDS:
        item = source.get(field)
        if item in (None, ""):
            continue
        if (
            field in {"chunk_index", "chunk_count"}
            and isinstance(item, int)
            and not isinstance(item, bool)
        ):
            citation[field] = item
        else:
            text = _safe_string(item, 300)
            if text:
                citation[field] = text
    return citation


def _safe_result(document: Any) -> dict[str, Any]:
    raw = _document_mapping(document)
    namespace = raw.get("namespace") or raw.get("platform")
    title = raw.get("title") or raw.get("topic") or "Untitled"
    values: dict[str, Any] = {
        "document_id": raw.get("document_id"),
        "title": title,
        "namespace": namespace,
        "topic": raw.get("topic"),
        "excerpt": raw.get("excerpt"),
        "source_ref": raw.get("source_ref") or raw.get("source"),
        "confidence": raw.get("confidence"),
        "updated_at": raw.get("updated_at"),
        "score": raw.get("score"),
    }
    result: dict[str, Any] = {}
    for field in _RESULT_FIELDS:
        value = values.get(field)
        if value in (None, ""):
            continue
        if field == "citation":
            result[field] = _safe_citation(raw.get("citation"), raw)
        elif field in {"confidence", "score"}:
            try:
                number = float(value)
            except (TypeError, ValueError, OverflowError):
                continue
            if math.isfinite(number):
                result[field] = number
        else:
            limits = {
                "document_id": 200,
                "title": 300,
                "namespace": 100,
                "topic": 300,
                "excerpt": MAX_EXCERPT_CHARS,
                "source_ref": 500,
                "updated_at": 100,
            }
            result[field] = _safe_string(value, limits[field])
    result["citation"] = _safe_citation(raw.get("citation"), raw)
    return result


class _KnowledgeSearchExecutor:
    def __init__(self, provider: Any) -> None:
        if provider is None:
            raise TypeError("knowledge provider is required")
        self._provider = provider

    def execute(self, context: Any, arguments: dict[str, Any]) -> ToolResult:
        try:
            tenant_id = _trusted_tenant_id(context)
        except PermissionError as error:
            return ToolResult.error(str(error))

        raw_query = arguments.get("query")
        if not isinstance(raw_query, str):
            return ToolResult.error("知识库查询内容必须是文本")
        query = raw_query.strip()
        if not query:
            return ToolResult.error("知识库查询内容不能为空")
        if len(query) > MAX_QUERY_CHARS:
            return ToolResult.error("知识库查询内容超过长度限制")

        namespaces = arguments.get("namespaces") or ()
        if isinstance(namespaces, str):
            namespaces = (namespaces,)
        if not isinstance(namespaces, (list, tuple)):
            return ToolResult.error("知识库范围必须是字符串列表")
        if len(namespaces) > MAX_NAMESPACES:
            return ToolResult.error("知识库范围最多支持 8 个命名空间")
        if any(not isinstance(item, str) for item in namespaces):
            return ToolResult.error("知识库范围必须是字符串列表")
        safe_namespaces = tuple(
            dict.fromkeys(
                item.strip()[:100]
                for item in namespaces
                if item.strip()
            )
        )[:MAX_NAMESPACES]
        raw_limit = arguments.get("limit", 5)
        if isinstance(raw_limit, bool) or not isinstance(raw_limit, int):
            return ToolResult.error("知识库结果数量必须是 1 到 10 的整数")
        limit = max(1, min(raw_limit, MAX_RESULTS))

        request = ContextQuery(
            text=query,
            namespaces=safe_namespaces,
            tenant_id=tenant_id,
            limit=limit,
            max_excerpt_chars=MAX_EXCERPT_CHARS,
        )
        query_context = getattr(self._provider, "query_context", None)
        if callable(query_context):
            documents = query_context(request)
        else:
            query_method = getattr(self._provider, "query", None)
            if not callable(query_method):
                return ToolResult.error("知识库当前不支持搜索")
            documents = query_method(
                request.text,
                namespaces=request.namespaces or None,
                tenant_id=request.tenant_id,
                limit=request.limit,
                max_excerpt_chars=request.max_excerpt_chars,
            )

        results = [_safe_result(item) for item in islice(documents or (), limit)]
        return ToolResult.ok({
            "results": results,
            "count": len(results),
            "data_status": "local",
        })


def knowledge_search_tool_source(
    provider: Any,
    *,
    required_permission: str,
) -> StaticToolSource:
    """Build a generic knowledge-search Source over ``KnowledgeSource``."""
    permission = str(required_permission or "").strip()
    if not permission:
        raise ValueError("required_permission is required")

    definition = ToolDefinition(
        name="agent_knowledge_search",
        skill="agent-knowledge",
        namespace="agent_platform",
        description=(
            "Search the registered read-only knowledge source and return bounded "
            "excerpts with citations. Use when the user explicitly asks to search "
            "or retrieve knowledge; provider/channel names in the query are filters "
            "or search terms, not a request to call provider APIs. The tenant is "
            "taken from trusted Runtime context and cannot be supplied as an argument."
        ),
        input_schema=ToolSchema(
            properties={
                "query": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": MAX_QUERY_CHARS,
                    "description": "Knowledge question or search phrase",
                },
                "namespaces": {
                    "type": "array",
                    "maxItems": MAX_NAMESPACES,
                    "items": {"type": "string", "maxLength": 100},
                    "description": "Optional registered knowledge namespaces",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": MAX_RESULTS,
                    "default": 5,
                    "description": "Maximum number of results",
                },
            },
            required=["query"],
            additional_properties=False,
        ),
        action="search",
        resource_type="knowledge",
        intent_types=["knowledge_search"],
        intent_aliases=[
            "知识库检索",
            "从知识库检索",
            "检索知识库",
            "在知识库中搜索",
            "搜索知识库",
            "查询知识库",
            "检索知识",
            "search the knowledge base",
            "search knowledge",
        ],
        risk_level=RiskLevel.LOW,
        effect_class=ToolEffect.READ,
        replay_policy=ReplayPolicy.SAFE,
        traits=["knowledge", "read_only", "bounded_output"],
        timeout_seconds=15,
        max_output_bytes=32_000,
        required_permissions=[permission],
        scope_required=False,
        result_items_key="results",
        contract_version="1.0.0",
    )
    return StaticToolSource(
        "agent-platform:knowledge-search",
        [ToolBinding(definition, _KnowledgeSearchExecutor(provider))],
    )


__all__ = ["knowledge_search_tool_source"]
