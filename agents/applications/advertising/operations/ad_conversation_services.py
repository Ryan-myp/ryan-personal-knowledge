"""Conversation and run-query application services.

All reads are scoped by the authenticated tenant/user through the persistence
port. This module owns presentation-facing query assembly, not execution.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Optional

from agents.agent_harness.core.conversation_title import ConversationTitleGenerator
from agents.applications.advertising.persistence.models import ConversationMessagePage
from agents.tools.advertising.shared.domain.conversation import project_conversation_messages
from .ad_conversation_feedback_services import AdConversationFeedbackServices
from .ad_conversation_knowledge_services import AdConversationKnowledgeServices
from .session_context import SessionContext


def _cached_sidebar_messages(metadata: Mapping[str, Any]) -> list[Mapping[str, Any]] | None:
    """Use the bounded presentation window written when a Run finishes."""
    messages = metadata.get("messages")
    if not isinstance(messages, list) or not 0 < len(messages) <= SessionContext.MAX_MESSAGES:
        return None
    if not all(
        isinstance(row, Mapping) and row.get("role") in {"user", "assistant"}
        and isinstance(row.get("content"), str)
        for row in messages
    ):
        return None
    if not messages[-1]["content"].strip():
        return None
    return messages


class AdConversationServices:
    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime
        self.feedback_services = AdConversationFeedbackServices(runtime)
        self.knowledge_services = AdConversationKnowledgeServices(runtime)

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
        self,
        user_id: str,
        tenant_id: str = "default",
        limit: int = 50,
        before_updated_at: Optional[str] = None,
        before_session_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """List only the authenticated principal's durable conversations."""
        if not self.runtime._session_manager:
            return []
        page_limit = min(max(1, int(limit)), 256)
        sessions = self.runtime._session_manager.list_sessions(
            user_id,
            limit=page_limit,
            tenant_id=tenant_id,
            before_updated_at=before_updated_at,
            before_session_id=before_session_id,
        )
        prepared = []
        for session in sessions:
            metadata = AdConversationServices._decode_session_metadata(session)
            prepared.append(({**session, "metadata": metadata}, _cached_sidebar_messages(metadata)))
        legacy_ids = [str(session["session_id"]) for session, cached in prepared if cached is None]
        pages = self.runtime._session_manager.list_conversation_preview_messages(
            legacy_ids, user_id=user_id, tenant_id=tenant_id,
        ) if legacy_ids else {}
        return [
            self._sidebar_summary(session, cached, pages.get(str(session["session_id"])))
            for session, cached in prepared
        ]

    def _sidebar_summary(
        self, session: Mapping[str, Any], cached: list[Mapping[str, Any]] | None,
        page: ConversationMessagePage | None,
    ) -> dict[str, Any]:
        metadata = session["metadata"]
        messages = cached if cached is not None else project_conversation_messages(
            [record.to_dict() for record in page.records] if page else [],
            metadata.get("conversation_ui"),
        )
        summary = self._conversation_summary(session, messages)
        turns = metadata.get("conversation_turn_count")
        partial = (page is not None and page.has_more) or (
            cached is not None and type(turns) is int and turns * 2 > len(cached)
        )
        if partial:
            summary.pop("message_count", None)
        return self.runtime._redact_for_persistence(summary)

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

    def submit_conversation_feedback(self, **kwargs: Any) -> bool:
        return self.feedback_services.submit_conversation_feedback(**kwargs)

    def get_conversation_feedback_trend(self, **kwargs: Any) -> dict[str, Any]:
        return self.feedback_services.get_conversation_feedback_trend(**kwargs)

    def page_conversation_feedback_review_queue(self, filters: Any) -> dict[str, Any]:
        return self.feedback_services.page_conversation_feedback_review_queue(filters)

    def list_conversation_feedback_review_queue(
        self, **kwargs: Any,
    ) -> list[dict[str, Any]]:
        return self.feedback_services.list_conversation_feedback_review_queue(
            **kwargs
        )

    def review_conversation_feedback(self, **kwargs: Any) -> bool:
        return self.feedback_services.review_conversation_feedback(**kwargs)

    def search_knowledge(
        self, *args: Any, **kwargs: Any,
    ) -> list[dict[str, Any]]:
        return self.knowledge_services.search_knowledge(*args, **kwargs)

    def catalog_knowledge(
        self, *args: Any, **kwargs: Any,
    ) -> list[dict[str, Any]]:
        return self.knowledge_services.catalog_knowledge(*args, **kwargs)

    def get_knowledge_semantic_index_status(
        self, *args: Any, **kwargs: Any,
    ) -> dict[str, Any]:
        return self.knowledge_services.semantic_index_status(*args, **kwargs)

    def rebuild_knowledge_semantic_index(
        self, *args: Any, **kwargs: Any,
    ) -> dict[str, Any]:
        return self.knowledge_services.rebuild_semantic_index(*args, **kwargs)

    def summarize_knowledge(
        self, *args: Any, **kwargs: Any,
    ) -> str:
        return self.knowledge_services.summarize(*args, **kwargs)

    def get_conversation(
        self, session_id: str, user_id: str, tenant_id: str = "default",
        limit: int = 10, before_message_id: Optional[str] = None,
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
        page = self.runtime._session_manager.list_conversation_message_page(
            session_id,
            limit=limit,
            before_message_id=before_message_id,
        )
        messages = self.runtime._redact_for_persistence(project_conversation_messages(
            [record.to_dict() for record in page.records],
            metadata.get("conversation_ui"),
        ))
        summary = AdConversationServices._conversation_summary(session, messages)
        if page.has_more:
            summary.pop("message_count", None)
        traces = metadata.get("execution_traces")
        return {
            **summary,
            "messages": messages,
            "loaded_message_count": len(messages),
            "has_more": page.has_more,
            "next_cursor": page.next_cursor,
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
        from .run_event_page import run_event_page
        result.update(run_event_page(self.runtime._session_manager, result["run_id"], 0, 511))
        result["recovery_message"] = (
            "服务中断导致本次执行状态未知，请先回查 Provider/工作流后再继续。"
            if result.get("status") == "recovery_required" else None
        )
        return result

    def get_latest_run_status(
        self, session_id: str, user_id: str, tenant_id: str = "default",
    ) -> Optional[dict[str, str]]:
        """Read only the latest Run status without loading its event history."""
        manager = self.runtime._session_manager
        getter = getattr(manager, "get_latest_execution_run", None)
        if not callable(getter):
            return None
        record = getter(session_id, user_id=user_id, tenant_id=tenant_id)
        if record is None:
            return None
        value = record.get("status") if isinstance(record, Mapping) else getattr(
            record, "status", None,
        )
        status = str(value or "").strip().lower()
        return {"status": status} if status else None

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
        from .run_event_page import run_event_page
        result.update(run_event_page(self.runtime._session_manager, run_id, after_seq, limit))
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
