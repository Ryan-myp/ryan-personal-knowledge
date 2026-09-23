"""Clarification response assembly for advertising creation."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Mapping

from ..core.execution_trace import ExecutionTrace
from ..core.interfaces import ParsedIntent

logger = logging.getLogger(__name__)


class AdCreationResponseServicesMixin:
    def _creation_input_response(
        self,
        *,
        session: "SessionContext",
        session_id: str,
        run_id: str,
        turn_id: str,
        user_input: str,
        reply: str,
        intent: ParsedIntent,
        ui: Mapping[str, Any],
        trace: ExecutionTrace,
        recalled_memories: list[dict[str, Any]],
        memory_updates: list[dict[str, Any]],
        reason: str,
    ) -> dict[str, Any]:
        """Finish a clarification turn without materializing Tool nodes."""
        trace.stage_status(
            "creation_clarification",
            "创建需求澄清" if reason == "creation_selector_required" else "创建参数收集",
            "awaiting_confirmation",
            subtitle="等待补充明确的广告类型和必填参数",
            safe_metadata={"reason": reason},
            safe_output={
                "provider": (ui.get("clarification") or {}).get("provider")
                if isinstance(ui, Mapping) else None,
                "card_count": len(ui.get("cards", []) or [])
                if isinstance(ui, Mapping) else 0,
            },
        )
        self.set_creation_draft(
            session_id, {"intent": intent.to_dict(), "reason": reason}
        )
        trace.reply()
        trace.done(
            "awaiting_confirmation",
            safe_metadata={"reason": reason, "tool_count": 0},
        )
        self.persist_conversation_turn(
            session, turn_id, user_input, reply, execution_trace=trace, ui=ui,
        )
        updater = getattr(self._session_manager, "update_execution_run", None)
        if callable(updater):
            try:
                updater(str(run_id), status="awaiting_confirmation")
            except Exception:
                logger.debug(
                    "failed to finalize clarification execution run",
                    exc_info=True,
                )
        return {
            "session_id": session_id,
            "run_id": run_id,
            "turn_id": turn_id,
            "timestamp": datetime.now().isoformat(),
            "intent": intent.to_dict(),
            "tool_plan": {},
            "execution_plan": {},
            "tool_selection": None,
            "memory": recalled_memories,
            "memory_updates": memory_updates,
            "results": [],
            "response_source": (
                "creation_clarification"
                if reason == "creation_selector_required" else "creation_card"
            ),
            "reply": reply,
            "needs_confirmation": False,
            "needs_input": True,
            "confirmation_payload": None,
            "workflow_id": None,
            "ui": dict(ui),
        }

    def _creation_policy_response(
        self,
        *,
        session: "SessionContext",
        session_id: str,
        run_id: str,
        turn_id: str,
        user_input: str,
        intent: ParsedIntent,
        trace: ExecutionTrace,
        error: str,
    ) -> dict[str, Any]:
        """Reject an out-of-scope explicit account before clarification."""
        trace.error(reason="account_scope_denied")
        trace.done("failed", safe_metadata={"reason": "account_scope_denied"})
        reply = "❌ " + str(error)
        self.persist_conversation_turn(
            session, turn_id, user_input, reply, execution_trace=trace,
        )
        updater = getattr(self._session_manager, "update_execution_run", None)
        if callable(updater):
            try:
                updater(str(run_id), status="failed")
            except Exception:
                logger.debug(
                    "failed to finalize creation policy run",
                    exc_info=True,
                )
        return {
            "session_id": session_id,
            "run_id": run_id,
            "turn_id": turn_id,
            "timestamp": datetime.now().isoformat(),
            "intent": intent.to_dict(),
            "tool_plan": {},
            "execution_plan": {},
            "tool_selection": None,
            "results": [],
            "reply": reply,
            "needs_confirmation": False,
            "needs_input": False,
            "confirmation_payload": None,
            "policy_errors": [str(error)],
            "workflow_id": None,
            "ui": {},
        }


__all__ = ["AdCreationResponseServicesMixin"]
