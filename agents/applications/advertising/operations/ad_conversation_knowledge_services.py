"""Knowledge search, catalog and advisory summary services for conversations."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from agents.agent_harness.core.context import ContextQuery


class AdConversationKnowledgeServices:
    """Own read-only knowledge operations exposed through conversation APIs."""

    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime

    def search_knowledge(
        self,
        query: str,
        *,
        tenant_id: str = "default",
        platform: Optional[str] = None,
        knowledge_type: Optional[str] = None,
        limit: int = 10,
        max_excerpt_chars: int = 1200,
    ) -> list[dict[str, Any]]:
        """Search built-in and published tenant Wiki documents."""
        provider = self.runtime.knowledge_provider
        if provider is None:
            return []
        request = ContextQuery(
            text=query,
            namespaces=(platform,) if platform else (),
            filters={
                "knowledge_types": (knowledge_type,),
            } if knowledge_type else {},
            tenant_id=tenant_id,
            limit=limit,
            max_excerpt_chars=max_excerpt_chars,
        )
        query_context = getattr(provider, "query_context", None)
        if callable(query_context):
            documents = query_context(request)
        else:
            documents = provider.query(
                request.text,
                platforms=request.namespaces or None,
                knowledge_types=request.filters.get("knowledge_types"),
                limit=request.limit,
                max_excerpt_chars=request.max_excerpt_chars,
            )
        return [document.to_dict() for document in documents]

    def catalog_knowledge(
        self,
        *,
        tenant_id: str = "default",
        platform: Optional[str] = None,
        knowledge_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List complete Wiki documents for navigation without chunk ranking."""
        provider = self.runtime.knowledge_provider
        if provider is None:
            return []
        catalog_context = getattr(provider, "catalog_context", None)
        if callable(catalog_context):
            documents = catalog_context(
                ContextQuery(
                    text="",
                    namespaces=(platform,) if platform else (),
                    filters={
                        "knowledge_types": (knowledge_type,),
                    } if knowledge_type else {},
                    tenant_id=tenant_id,
                    limit=limit,
                )
            )
        else:
            documents = provider.catalog(
                platforms=[platform] if platform else None,
                knowledge_types=[knowledge_type] if knowledge_type else None,
                limit=limit,
            )
        return [document.to_dict() for document in documents]

    def semantic_index_status(self, *, tenant_id: str) -> dict[str, Any]:
        provider = self.runtime.knowledge_provider
        getter = getattr(provider, "semantic_index_status", None)
        if not callable(getter):
            raise RuntimeError("knowledge semantic index status is unavailable")
        return getter(tenant_id=str(tenant_id))

    def rebuild_semantic_index(self, *, tenant_id: str) -> dict[str, Any]:
        provider = self.runtime.knowledge_provider
        rebuild = getattr(provider, "rebuild_semantic_search_index", None)
        if not callable(rebuild):
            raise RuntimeError("knowledge semantic index rebuild is unavailable")
        return rebuild(tenant_id=str(tenant_id))

    def summarize(
        self,
        query: str,
        documents: list[dict[str, Any]],
        *,
        use_llm: bool = True,
    ) -> str:
        """Create an advisory summary without executing any Tool."""
        safe_documents = self.runtime._redact_for_persistence(documents or [])
        if not safe_documents:
            return "暂时没有找到匹配的知识内容。可以换一个关键词，或扩大平台范围。"
        fallback_parts = []
        for document in safe_documents[:3]:
            title = str(document.get("title") or document.get("topic") or "相关知识")
            excerpt = re.sub(r"[#>*`|-]+", " ", str(document.get("excerpt") or ""))
            excerpt = " ".join(excerpt.split())[:180]
            fallback_parts.append(f"{title}：{excerpt}" if excerpt else title)
        fallback = "根据检索到的资料，重点参考：" + "；".join(fallback_parts) + "。"
        if not use_llm or self.runtime._llm is None:
            return fallback[:1200]
        prompt = (
            "你是广告运营知识助手。请根据用户问题和检索到的 Markdown Wiki 资料，"
            "用中文写一段面向广告运营人员的简短总结，先给结论，再给 2 到 4 条关键点。"
            "不要提及模型、Runtime、Tool、API、检索过程或内部字段；不要编造资料中没有的事实。"
            "只返回总结正文，不要包裹 JSON。\n\n"
            f"用户问题：{str(query or '')[:2000]}\n"
            f"资料：{json.dumps(safe_documents[:6], ensure_ascii=False, default=str)[:12000]}"
        )
        try:
            try:
                answer = self.runtime._llm.call(
                    [
                        {"role": "system", "content": "只输出业务总结。"},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                )
            except TypeError:
                answer = self.runtime._llm.call(
                    [
                        {"role": "system", "content": "只输出业务总结。"},
                        {"role": "user", "content": prompt},
                    ],
                )
            answer = self.runtime._redact_for_persistence(
                str(answer or "")
            ).strip()
            internal_terms = (
                "runtime", "tool", "provider", "intent_type", "access_token",
            )
            if not answer or len(answer) > 1600 or any(
                term in answer.lower() for term in internal_terms
            ):
                return fallback[:1200]
            return answer
        except Exception:
            return fallback[:1200]


__all__ = ["AdConversationKnowledgeServices"]
