"""Durable conversation and Tool audit persistence services.

The service owns application persistence orchestration and bounded UI/trace
snapshots. It never calls a Provider and never decides how a Tool is routed.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Mapping, Optional

from ..core.execution_trace import ExecutionTrace
from ..core.interfaces import ToolResult
from ..persistence.models import ToolCallRecord


class AdPersistenceServices:
    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime

    def persist_conversation_turn(
        self, session: "SessionContext", turn_id: str,
        user_input: str, reply: str,
        execution_trace: Optional[ExecutionTrace] = None,
        ui: Optional[Mapping[str, Any]] = None,
        persist_messages: bool = True,
    ) -> None:
        """Persist a complete sanitized turn and keep bounded model context.

        Full history belongs to the persistence backend's message store. The
        session metadata keeps only a small recent window for prompt context,
        so restoring a session never requires loading an unbounded transcript.
        """
        safe_user = self.runtime._redact_for_persistence(user_input)
        safe_reply = self.runtime._redact_for_persistence(reply)
        # SessionContext applies both message-count and character budgets and
        # returns exactly what was evicted. Build the digest from that list so
        # character-based compaction is recoverable too; the durable message
        # table remains the complete source of truth.
        evicted_messages = []
        evicted_messages.extend(session.add_message({"role": "user", "content": safe_user}))
        evicted_messages.extend(session.add_message({"role": "assistant", "content": safe_reply}))
        if evicted_messages:
            digest_lines = [
                str(session.ctx.metadata.get("conversation_digest") or "").strip()
            ]
            for message in evicted_messages:
                role = "用户" if message.get("role") == "user" else "助手"
                content = self.runtime._redact_for_persistence(message.get("content", ""))
                content = " ".join(str(content).split())
                if len(content) > 360:
                    content = content[:220] + "…[中间内容已折叠]…" + content[-110:]
                if content:
                    digest_lines.append(f"- {role}：{content}")
            digest = "\n".join(line for line in digest_lines if line)
            # Keep both the earliest durable constraints and the most recent
            # state. A tail-only slice makes old decisions disappear exactly
            # when repeated compaction is needed most.
            digest_limit = 2400
            if len(digest) > digest_limit:
                marker = "\n…[较早摘要已折叠]…\n"
                side = max(1, (digest_limit - len(marker)) // 2)
                digest = digest[:side] + marker + digest[-side:]
            session.ctx.metadata["conversation_digest"] = digest
        session.ctx.metadata["conversation_turn_count"] = int(
            session.ctx.metadata.get("conversation_turn_count", 0) or 0
        ) + 1
        if not session.ctx.metadata.get("conversation_title"):
            first_user = next(
                (
                    str(message.get("content", ""))
                    for message in session.messages
                    if message.get("role") == "user"
                ),
                safe_user,
            )
            title, title_source = self.runtime.conversation_title_generator.generate(
                first_user,
                self.runtime._llm if self.runtime.conversation_title_use_llm else None,
            )
            session.ctx.metadata["conversation_title"] = self.runtime._redact_for_persistence(title)
            session.ctx.metadata["conversation_title_source"] = title_source
        if not self.runtime._session_manager:
            return
        if persist_messages:
            self.runtime._session_manager.record_conversation_message(
                session.session_id, turn_id, "user", safe_user
            )
            self.runtime._session_manager.record_conversation_message(
                session.session_id, turn_id, "assistant", safe_reply
            )
        metadata = {
            "execution_mode": self.runtime.execution_mode,
            "read_only_mode": self.runtime._read_only_mode,
            "tenant_id": session.ctx.metadata.get("tenant_id", "default"),
            "conversation_title": session.ctx.metadata.get("conversation_title", "新对话"),
            "conversation_title_source": session.ctx.metadata.get(
                "conversation_title_source", "deterministic"
            ),
            # Keep the bounded working window in session metadata for
            # compatibility with older consumers that read session metadata
            # directly. The complete transcript remains in
            # conversation_messages; this bounded copy is not a second
            # durable source of truth.
            "messages": list(session.messages),
            "message_count": len(session.messages),
            "conversation_turn_count": session.ctx.metadata["conversation_turn_count"],
            "conversation_digest": session.ctx.metadata.get("conversation_digest", ""),
            "memory_updates": session.ctx.metadata.get("memory_updates", [])[-20:],
        }
        schedule_draft = session.ctx.metadata.get("schedule_draft")
        if isinstance(schedule_draft, dict):
            metadata["schedule_draft"] = self.runtime._redact_for_persistence(schedule_draft)
        creation_draft = session.ctx.metadata.get("creation_draft")
        if isinstance(creation_draft, dict):
            metadata["creation_draft"] = self.runtime._redact_for_persistence(creation_draft)
        action_draft = session.ctx.metadata.get("action_draft")
        if isinstance(action_draft, dict):
            metadata["action_draft"] = self.runtime._redact_for_persistence(action_draft)
        ui_by_turn = session.ctx.metadata.get("conversation_ui", {})
        ui_by_turn = dict(ui_by_turn) if isinstance(ui_by_turn, dict) else {}
        if isinstance(ui, Mapping) and ui:
            # A2UI is persisted as sanitized message metadata, not as model
            # context. It can be restored for display, but it never grants an
            # execution permission or bypasses the confirmation boundary.
            ui_by_turn[str(turn_id)] = self.runtime._redact_for_persistence(dict(ui))
        ui_by_turn = dict(list(ui_by_turn.items())[-20:])
        session.ctx.metadata["conversation_ui"] = ui_by_turn
        metadata["conversation_ui"] = ui_by_turn
        if execution_trace is not None:
            traces = session.ctx.metadata.get("execution_traces", {})
            traces = dict(traces) if isinstance(traces, dict) else {}
            traces[str(turn_id)] = execution_trace.snapshot()
            # Keep durable trace context bounded just like the recent message
            # window. The full live stream remains available to observers.
            traces = dict(list(traces.items())[-20:])
            session.ctx.metadata["execution_traces"] = traces
            metadata["execution_traces"] = traces
        self.runtime._session_manager.update_session(
            session.session_id,
            metadata,
        )

    def persist_tool_result(
        self, session: "SessionContext", turn_id: str, tool_def: Any,
        platform: str, input_data: dict, result: ToolResult,
        *, started_at: Optional[str] = None, ended_at: Optional[str] = None,
    ) -> None:
        """记录安全的工具审计信息和模拟资源状态。"""
        if not self.runtime._session_manager:
            return
        # The caller starts the clock immediately before invoking the Tool.
        # Do not recreate ``started_at`` here: doing so makes provider latency
        # appear as persistence latency in the monitoring console.
        started = started_at or datetime.now().isoformat()
        ended = ended_at or datetime.now().isoformat()
        safe_input = self.runtime._redact_for_persistence(input_data)
        safe_output = self.runtime._redact_for_persistence(result.data)
        self.runtime._session_manager.record_tool_call(
            session.session_id,
            turn_id,
            ToolCallRecord(
                id=str(uuid.uuid4()), session_id=session.session_id, turn_id=turn_id,
                tool_name=tool_def.name, platform=platform, input_data=safe_input,
                output_data=safe_output, success=result.success,
                error=self.runtime._redact_for_persistence(result.error),
                started_at=started, ended_at=ended,
            ),
        )
