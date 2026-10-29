"""Persist scoped advisory notes through the existing Session store."""

from agents.agent_harness.core.interfaces import ToolResult
from .conversation_state import valid_conversation_state
from .semantic_constraints import apply_note_patch, note_id


class ConversationNotesService:
    def __init__(self, runtime):
        self.runtime = runtime

    def _session(self, context):
        principal = getattr(context, "principal", None)
        if principal is None:
            raise PermissionError("缺少可信身份")
        session = self.runtime._sessions.get(context.session_id)
        if session is None or not self.runtime._session_manager:
            raise ValueError("会话存储不可用")
        owned = self.runtime._session_manager.get_session(
            context.session_id,
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
        )
        if not owned:
            raise PermissionError("会话不属于当前身份")
        return session

    def read(self, context, _arguments):
        try:
            state = valid_conversation_state(
                self._session(context).ctx.metadata.get("conversation_state")
            )
        except (PermissionError, ValueError) as error:
            return ToolResult.error(str(error))
        return ToolResult.ok(
            {
                "revision": state.get("semantic", {}).get("revision", 0),
                "entries": [{**row, "id": note_id(row)} for row in state["entries"]]
                + state.get("semantic", {}).get("entries", []),
                "advisory_only": True,
            }
        )

    def update(self, context, arguments):
        try:
            session = self._session(context)
            state = apply_note_patch(
                session.ctx.metadata.get("conversation_state"),
                context.metadata.get("source_user_input", ""),
                context.metadata.get("turn_id", ""),
                arguments["expected_revision"],
                arguments["changes"],
            )
            self.runtime._session_manager.update_session(
                context.session_id,
                metadata={**session.ctx.metadata, "conversation_state": state},
            )
            session.ctx.metadata["conversation_state"] = state
        except (PermissionError, ValueError) as error:
            return ToolResult.error(str(error))
        return self.read(context, {})
