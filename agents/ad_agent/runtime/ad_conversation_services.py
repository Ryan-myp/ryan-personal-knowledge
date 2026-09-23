"""Conversation and run-query application services.

All reads are scoped by the authenticated tenant/user through the persistence
port. This module owns presentation-facing query assembly, not execution.
"""

from __future__ import annotations

import json
import re
from typing import Any, Mapping, Optional

from ..core.context import ContextQuery
from ..core.conversation_title import ConversationTitleGenerator


class AdConversationServices:
    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime

    @staticmethod
    def _decode_session_metadata(session: Mapping[str, Any]) -> dict[str, Any]:
        value = session.get("metadata")
        if isinstance(value, dict):
            return dict(value)
        if isinstance(value, str):
            try:
                decoded = json.loads(value or "{}")
                return decoded if isinstance(decoded, dict) else {}
            except (TypeError, ValueError):
                return {}
        return {}

    @staticmethod
    def _conversation_summary(
        session: Mapping[str, Any], messages: list[Mapping[str, Any]],
    ) -> dict[str, Any]:
        user_messages = [item for item in messages if item.get("role") == "user"]
        title_source = str((user_messages[0] if user_messages else messages[0]).get("content", "")) if messages else "新对话"
        metadata = AdConversationServices._decode_session_metadata(session)
        title = str(metadata.get("conversation_title") or "").strip()
        if not title:
            title = ConversationTitleGenerator.fallback_title(title_source)
        latest = str(messages[-1].get("content", "")) if messages else ""
        return {
            "session_id": str(session.get("session_id") or ""),
            "title": title,
            "preview": " ".join(latest.split())[:100],
            "message_count": len(messages) or int(session.get("message_count") or 0),
            "created_at": session.get("created_at"),
            "updated_at": session.get("updated_at"),
        }

    def list_conversations(
        self, user_id: str, tenant_id: str = "default", limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List only the authenticated principal's durable conversations."""
        if not self.runtime._session_manager:
            return []
        conversations = []
        for session in self.runtime._session_manager.list_sessions(
            user_id, limit=limit, tenant_id=tenant_id
        ):
            records = self.runtime._session_manager.list_conversation_messages(
                str(session.get("session_id") or ""), limit=500
            )
            messages = [record.to_dict() for record in records]
            conversations.append(AdConversationServices._conversation_summary(session, messages))
        return conversations[:limit]

    def rename_conversation(
        self, session_id: str, title: str, *, user_id: str,
        tenant_id: str = "default",
    ) -> Optional[dict[str, Any]]:
        """Rename one local conversation inside the authenticated scope."""
        if not self.runtime._session_manager:
            return None
        persisted = self.runtime._session_manager.get_session(
            str(session_id), user_id=user_id, tenant_id=tenant_id
        )
        if not persisted:
            return None
        metadata = AdConversationServices._decode_session_metadata(persisted)
        safe_title = self.runtime._redact_for_persistence(str(title or "")).strip()
        if not safe_title:
            raise ValueError("对话标题不能为空")
        if len(safe_title) > ConversationTitleGenerator.MAX_TITLE_CHARS:
            raise ValueError(
                f"对话标题不能超过 {ConversationTitleGenerator.MAX_TITLE_CHARS} 个字符"
            )
        metadata["conversation_title"] = safe_title
        metadata["conversation_title_source"] = "manual"
        self.runtime._session_manager.update_session(str(session_id), metadata)
        session = self.runtime._sessions.get(str(session_id))
        if session is not None:
            session.ctx.metadata.update({
                "conversation_title": safe_title,
                "conversation_title_source": "manual",
            })
        return {"session_id": str(session_id), "title": safe_title}

    def search_knowledge(
        self, query: str, *, tenant_id: str = "default",
        platform: Optional[str] = None, knowledge_type: Optional[str] = None,
        limit: int = 10, max_excerpt_chars: int = 1200,
    ) -> list[dict[str, Any]]:
        """Search built-in and published tenant Wiki documents."""
        if self.runtime.knowledge_provider is None:
            return []
        request = ContextQuery(
            text=query,
            namespaces=(platform,) if platform else (),
            filters={"knowledge_types": (knowledge_type,)} if knowledge_type else {},
            tenant_id=tenant_id,
            limit=limit,
            max_excerpt_chars=max_excerpt_chars,
        )
        query_context = getattr(self.runtime.knowledge_provider, "query_context", None)
        if callable(query_context):
            documents = query_context(request)
        else:
            documents = self.runtime.knowledge_provider.query(
                request.text,
                platforms=request.namespaces or None,
                knowledge_types=request.filters.get("knowledge_types"),
                limit=request.limit,
                max_excerpt_chars=request.max_excerpt_chars,
            )
        return [document.to_dict() for document in documents]

    def catalog_knowledge(
        self, *, tenant_id: str = "default", platform: Optional[str] = None,
        knowledge_type: Optional[str] = None, limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List complete Wiki documents for navigation without chunk ranking."""
        if self.runtime.knowledge_provider is None:
            return []
        # Catalog remains a navigation API, but its tenant boundary is still
        # explicit. Providers that expose only the legacy catalog method keep
        # the built-in-only behavior rather than relying on reflection.
        catalog_context = getattr(
            self.runtime.knowledge_provider, "catalog_context", None
        )
        if callable(catalog_context):
            documents = catalog_context(
                ContextQuery(
                    text="",
                    namespaces=(platform,) if platform else (),
                    filters={"knowledge_types": (knowledge_type,)} if knowledge_type else {},
                    tenant_id=tenant_id,
                    limit=limit,
                )
            )
        else:
            documents = self.runtime.knowledge_provider.catalog(
                platforms=[platform] if platform else None,
                knowledge_types=[knowledge_type] if knowledge_type else None,
                limit=limit,
            )
        return [document.to_dict() for document in documents]

    def summarize_knowledge(
        self, query: str, documents: list[dict[str, Any]], *, use_llm: bool = True,
    ) -> str:
        """Create a business-facing summary without executing any Tool."""
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
                    [{"role": "system", "content": "只输出业务总结。"},
                     {"role": "user", "content": prompt}],
                    temperature=0.2,
                )
            except TypeError:
                answer = self.runtime._llm.call(
                    [{"role": "system", "content": "只输出业务总结。"},
                     {"role": "user", "content": prompt}],
                )
            answer = self.runtime._redact_for_persistence(str(answer or "")).strip()
            internal_terms = ("runtime", "tool", "provider", "intent_type", "access_token")
            if not answer or len(answer) > 1600 or any(
                term in answer.lower() for term in internal_terms
            ):
                return fallback[:1200]
            return answer
        except Exception:
            return fallback[:1200]

    def get_conversation(
        self, session_id: str, user_id: str, tenant_id: str = "default",
        limit: int = 500,
    ) -> Optional[dict[str, Any]]:
        """Load one conversation after enforcing user and tenant ownership."""
        if not self.runtime._session_manager:
            return None
        session = self.runtime._session_manager.get_session(
            session_id, user_id=user_id, tenant_id=tenant_id
        )
        if not session:
            return None
        metadata = AdConversationServices._decode_session_metadata(session)
        records = self.runtime._session_manager.list_conversation_messages(session_id, limit=limit)
        messages = [
            {
                "role": record.role,
                "content": self.runtime._redact_for_persistence(record.content),
                "created_at": record.created_at,
                "turn_id": record.turn_id,
                **(
                    {"ui": self.runtime._redact_for_persistence(record.metadata["ui"])}
                    if isinstance(getattr(record, "metadata", None), dict)
                    and isinstance(record.metadata.get("ui"), dict)
                    else {}
                ),
            }
            for record in records
        ]
        ui_by_turn = metadata.get("conversation_ui", {})
        if isinstance(ui_by_turn, dict):
            for message in messages:
                if message.get("role") != "assistant" or message.get("ui"):
                    continue
                stored_ui = ui_by_turn.get(str(message.get("turn_id")))
                if isinstance(stored_ui, dict) and stored_ui:
                    message["ui"] = self.runtime._redact_for_persistence(stored_ui)
        summary = AdConversationServices._conversation_summary(session, messages)
        traces = metadata.get("execution_traces")
        return {
            **summary,
            "messages": messages,
            "execution_traces": traces if isinstance(traces, dict) else {},
        }

    @staticmethod
    def _execution_run_dict(record: Any) -> Optional[dict[str, Any]]:
        if record is None:
            return None
        if hasattr(record, "to_dict"):
            return record.to_dict()
        if isinstance(record, dict):
            return dict(record)
        return None

    def _bind_execution_run_workflow(self, run_id: str, workflow_id: Optional[str]) -> None:
        if not workflow_id or not self.runtime._session_manager:
            return
        updater = getattr(self.runtime._session_manager, "update_execution_run", None)
        if callable(updater):
            try:
                updater(str(run_id), workflow_id=str(workflow_id))
            except Exception:
                logger.debug("failed to bind workflow to execution run", exc_info=True)

    def get_latest_run(
        self, session_id: str, user_id: str, tenant_id: str = "default",
    ) -> Optional[dict[str, Any]]:
        """Return the latest run plus its currently durable event snapshot."""
        if not self.runtime._session_manager:
            return None
        getter = getattr(self.runtime._session_manager, "get_latest_execution_run", None)
        if not callable(getter):
            return None
        record = getter(session_id, user_id=user_id, tenant_id=tenant_id)
        result = self.runtime._execution_run_dict(record)
        if result is None:
            return None
        events = self.runtime._session_manager.list_execution_run_events(
            result["run_id"], after_seq=0, limit=512
        )
        result["events"] = events
        result["latest_seq"] = max(
            [int(item.get("seq", 0)) for item in events if isinstance(item, dict)]
            or [0]
        )
        result["recovery_message"] = (
            "服务中断导致本次执行状态未知，请先回查 Provider/工作流后再继续。"
            if result.get("status") == "recovery_required" else None
        )
        return result

    def get_run_events(
        self, run_id: str, user_id: str, tenant_id: str = "default",
        after_seq: int = 0, limit: int = 256,
    ) -> Optional[dict[str, Any]]:
        """Read incremental run events after enforcing tenant/user ownership."""
        if not self.runtime._session_manager:
            return None
        getter = getattr(self.runtime._session_manager, "get_execution_run", None)
        if not callable(getter):
            return None
        record = getter(run_id, user_id=user_id, tenant_id=tenant_id)
        result = self.runtime._execution_run_dict(record)
        if result is None:
            return None
        events = self.runtime._session_manager.list_execution_run_events(
            run_id, after_seq=max(0, int(after_seq)), limit=limit
        )
        result["events"] = events
        result["latest_seq"] = max(
            [int(item.get("seq", 0)) for item in events if isinstance(item, dict)]
            or [max(0, int(after_seq))]
        )
        result["recovery_message"] = (
            "服务中断导致本次执行状态未知，请先回查 Provider/工作流后再继续。"
            if result.get("status") == "recovery_required" else None
        )
        return result

    def delete_conversation(
        self, session_id: str, user_id: str, tenant_id: str = "default",
    ) -> bool:
        """Delete one conversation after enforcing its user/tenant scope."""
        if not self.runtime._session_manager:
            return False
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return False
        session = self.runtime._session_manager.get_session(
            normalized_session_id, user_id=user_id, tenant_id=tenant_id
        )
        if not session:
            return False
        deleted = self.runtime._session_manager.delete_session(normalized_session_id)
        if deleted:
            self.runtime._sessions.pop(normalized_session_id, None)
            forget_session = getattr(
                self.runtime._runtime_kernel, "forget_session", None
            )
            if callable(forget_session):
                forget_session(
                    normalized_session_id,
                    user_id=user_id,
                    tenant_id=tenant_id,
                )
        return deleted

    def delete_conversations(
        self, session_ids: list[str], user_id: str,
        tenant_id: str = "default",
    ) -> list[str]:
        """Delete up to the caller-selected conversations in one scoped action."""
        deleted: list[str] = []
        seen: set[str] = set()
        for session_id in session_ids or []:
            normalized_session_id = str(session_id or "").strip()
            if not normalized_session_id or normalized_session_id in seen:
                continue
            seen.add(normalized_session_id)
            if self.runtime.delete_conversation(
                normalized_session_id, user_id=user_id, tenant_id=tenant_id
            ):
                deleted.append(normalized_session_id)
        return deleted
