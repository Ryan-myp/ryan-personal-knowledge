"""Session restoration and durable session-boundary services."""

from __future__ import annotations

import copy
import json
import logging
from typing import Any, Optional

from ..core.interfaces import ToolContext, ToolResult
from .session_context import SessionContext

logger = logging.getLogger(__name__)


class AdSessionServices:
    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime

    def ensure_session(
        self,
        session_id: str,
        user_id: str,
        account_id: str,
        credentials: dict,
        tenant_id: str = "default",
    ) -> "SessionContext":
        if session_id not in self.runtime._sessions:
            persisted = self.runtime._session_manager.get_session(session_id) if self.runtime._session_manager else None
            if persisted:
                persisted_user = persisted.get("user_id")
                persisted_account = persisted.get("account_id")
                if persisted_user and persisted_user != user_id:
                    raise PermissionError("session belongs to a different user")
                if account_id and persisted_account and str(account_id) != str(persisted_account):
                    raise PermissionError("session belongs to a different account")
            persisted_metadata = {}
            if persisted and persisted.get("metadata"):
                try:
                    persisted_metadata = json.loads(persisted["metadata"])
                except (TypeError, ValueError):
                    persisted_metadata = {}
            # The normalized column is the authorization source of truth.
            # Metadata is only a legacy/display copy.
            persisted_tenant = str(
                persisted.get("tenant_id") if persisted else "default"
            )
            if persisted and persisted_tenant != str(tenant_id or "default"):
                raise PermissionError("session belongs to a different tenant")
            ctx = ToolContext(
                session_id=session_id,
                user_id=user_id,
                account_id=account_id or (persisted or {}).get("account_id"),
                credentials=self.runtime._freeze_credentials(copy.deepcopy(credentials or {})),
            )
            session = SessionContext(session_id, ctx)
            ctx.metadata["tenant_id"] = str(tenant_id or "default")
            stored_title = persisted_metadata.get("conversation_title")
            if isinstance(stored_title, str) and stored_title.strip():
                ctx.metadata["conversation_title"] = stored_title.strip()
                ctx.metadata["conversation_title_source"] = str(
                    persisted_metadata.get("conversation_title_source") or "deterministic"
                )
            stored_traces = persisted_metadata.get("execution_traces")
            if isinstance(stored_traces, dict):
                ctx.metadata["execution_traces"] = stored_traces
            stored_ui = persisted_metadata.get("conversation_ui")
            if isinstance(stored_ui, dict):
                ctx.metadata["conversation_ui"] = stored_ui
            stored_schedule_draft = persisted_metadata.get("schedule_draft")
            if isinstance(stored_schedule_draft, dict):
                ctx.metadata["schedule_draft"] = stored_schedule_draft
            stored_creation_draft = persisted_metadata.get("creation_draft")
            if isinstance(stored_creation_draft, dict):
                ctx.metadata["creation_draft"] = stored_creation_draft
            stored_action_draft = persisted_metadata.get("action_draft")
            if isinstance(stored_action_draft, dict):
                ctx.metadata["action_draft"] = stored_action_draft
            stored_digest = persisted_metadata.get("conversation_digest")
            if isinstance(stored_digest, str):
                ctx.metadata["conversation_digest"] = stored_digest[:2400]
            ctx.metadata["conversation_turn_count"] = int(
                persisted_metadata.get("conversation_turn_count", 0) or 0
            )
            # The normalized conversation table is the only durable source of
            # truth. Runtime metadata never contains a second transcript.
            session.replace_messages([])
            if self.runtime._session_manager and persisted:
                list_messages = getattr(self.runtime._session_manager, "list_conversation_messages", None)
                if callable(list_messages):
                    try:
                        records = list_messages(
                            session_id, limit=SessionContext.MAX_MESSAGES
                        )
                        if records:
                            session.replace_messages([
                                {"role": str(record.role), "content": str(record.content)}
                                for record in records
                            ])
                    except Exception:
                        logger.debug("failed to restore durable conversation window", exc_info=True)
            ctx.messages = list(session.messages)
            if self.runtime._session_manager and persisted:
                for record in reversed(self.runtime._session_manager.get_session_history(session_id, limit=20)):
                    if record.output_data:
                        session.save_result(
                            record.tool_name,
                            ToolResult.ok(record.output_data),
                            platform=record.platform,
                        )
                # Restore resource IDs into the actual ToolContext before the
                # first tool of the new turn, not only after a new tool runs.
                ctx.protected_state.update(session.protected_state)
            self.runtime._sessions[session_id] = session

            # Create only genuinely new sessions. INSERT OR REPLACE here would
            # otherwise erase a persisted account_id when the caller omits it
            # during session restoration.
            if self.runtime._session_manager and not persisted:
                self.runtime._session_manager.create_session(
                    session_id,
                    user_id,
                    account_id,
                    {
                        "execution_mode": self.runtime.execution_mode,
                        "read_only_mode": self.runtime._read_only_mode,
                        "tenant_id": str(tenant_id or "default"),
                    },
                )
        session = self.runtime._sessions[session_id]
        if session.ctx.user_id != user_id:
            raise PermissionError("session belongs to a different user")
        if str(session.ctx.metadata.get("tenant_id", "default")) != str(tenant_id or "default"):
            raise PermissionError("session belongs to a different tenant")
        if account_id and session.ctx.account_id and str(account_id) != str(session.ctx.account_id):
            raise PermissionError("session belongs to a different account")
        if credentials:
            session.ctx.credentials = self.runtime._freeze_credentials(copy.deepcopy(credentials))
        return session

    def refresh_session_for_turn(
        self, session_id: str, user_id: str, account_id: Optional[str],
        credentials: Optional[dict], tenant_id: str = "default",
    ) -> "SessionContext":
        """Reload the durable session after its cross-instance lease is held."""
        if self.runtime._session_manager is None:
            # Without a persistence backend the in-process SessionContext is
            # the only source of truth; evicting it would discard drafts and
            # short-term memory between turns.
            return self.runtime._ensure_session(
                str(session_id), user_id, account_id, credentials,
                tenant_id=tenant_id,
            )
        self.runtime._sessions.pop(str(session_id), None)
        return self.runtime._ensure_session(
            str(session_id), user_id, account_id, credentials,
            tenant_id=tenant_id,
        )
