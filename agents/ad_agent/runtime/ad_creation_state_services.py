"""Bounded session drafts and action clarification for advertising creation."""

from __future__ import annotations

import copy
import json
import logging
from datetime import datetime
from typing import Any, Mapping, Optional

from ..core.execution_trace import ExecutionTrace
from ..core.interfaces import ParsedIntent
from .account_context import AccountResolver

logger = logging.getLogger(__name__)


class AdCreationStateServicesMixin:
    def get_schedule_draft(self, session_id: str) -> Optional[dict[str, Any]]:
        session = self._sessions.get(str(session_id or ""))
        if not session:
            return None
        draft = session.ctx.metadata.get("schedule_draft")
        return copy.deepcopy(draft) if isinstance(draft, dict) else None

    def set_schedule_draft(
        self, session_id: str, draft: Optional[Mapping[str, Any]],
    ) -> None:
        session = self._sessions.get(str(session_id or ""))
        if not session:
            return
        if draft is None:
            session.ctx.metadata.pop("schedule_draft", None)
            return
        safe = self._redact_for_persistence(dict(draft))
        if len(json.dumps(safe, ensure_ascii=False, default=str).encode("utf-8")) > 32_000:
            raise ValueError("scheduled task draft exceeds persistence limit")
        session.ctx.metadata["schedule_draft"] = safe

    def get_creation_draft(self, session_id: str) -> Optional[dict[str, Any]]:
        session = self._sessions.get(str(session_id or ""))
        if not session:
            return None
        draft = session.ctx.metadata.get("creation_draft")
        return copy.deepcopy(draft) if isinstance(draft, dict) else None

    def set_creation_draft(
        self, session_id: str, draft: Optional[Mapping[str, Any]],
    ) -> None:
        session = self._sessions.get(str(session_id or ""))
        if not session:
            return
        if draft is None:
            session.ctx.metadata.pop("creation_draft", None)
            return
        safe = self._redact_for_persistence(dict(draft))
        if len(json.dumps(safe, ensure_ascii=False, default=str).encode("utf-8")) > 48_000:
            raise ValueError("creation draft exceeds persistence limit")
        session.ctx.metadata["creation_draft"] = safe

    def get_action_draft(self, session_id: str) -> Optional[dict[str, Any]]:
        session = self._sessions.get(str(session_id or ""))
        if not session:
            return None
        draft = session.ctx.metadata.get("action_draft")
        return copy.deepcopy(draft) if isinstance(draft, dict) else None

    def set_action_draft(
        self, session_id: str, draft: Optional[Mapping[str, Any]],
    ) -> None:
        session = self._sessions.get(str(session_id or ""))
        if not session:
            return
        if draft is None:
            session.ctx.metadata.pop("action_draft", None)
            return
        safe = self._redact_for_persistence(dict(draft))
        if len(json.dumps(safe, ensure_ascii=False, default=str).encode("utf-8")) > 32_000:
            raise ValueError("action clarification draft exceeds persistence limit")
        session.ctx.metadata["action_draft"] = safe

    @staticmethod
    def _creation_intent_from_draft(
        draft: Optional[Mapping[str, Any]],
    ) -> Optional[ParsedIntent]:
        if not isinstance(draft, Mapping):
            return None
        raw = draft.get("intent") if isinstance(draft.get("intent"), Mapping) else draft
        if not isinstance(raw, Mapping):
            return None
        fields = getattr(ParsedIntent, "__dataclass_fields__", {})
        values = {
            key: copy.deepcopy(value)
            for key, value in raw.items()
            if key in fields
        }
        values.setdefault("attributes", {
            str(key): copy.deepcopy(value)
            for key, value in raw.items()
            if key not in fields and key not in {"scoped_parameters"}
        })
        values.setdefault("scoped_parameters", copy.deepcopy(
            raw.get("scoped_parameters") or {}
        ))
        values.setdefault(
            "raw_input",
            str(raw.get("raw_input") or draft.get("raw_input") or ""),
        )
        try:
            return ParsedIntent(**values)
        except (TypeError, ValueError):
            return None

    def _adopt_creation_draft(
        self, session_id: str, intent: ParsedIntent, follow_up_text: str,
    ) -> ParsedIntent:
        draft = self.get_creation_draft(session_id)
        pending = self._creation_intent_from_draft(draft)
        if pending is None:
            return intent
        try:
            adopted = self.creation_card_builder.merge_pending_intent(
                pending, intent, follow_up_text,
            )
        except Exception:
            logger.debug("failed to merge pending creation draft", exc_info=True)
            return intent
        return adopted if adopted is not None else intent

    def _adopt_action_draft(
        self, session_id: str, intent: ParsedIntent, follow_up_text: str,
    ) -> ParsedIntent:
        draft = self.get_action_draft(session_id)
        pending = self._creation_intent_from_draft(draft)
        if pending is None or self.creation_card_builder.is_creation_intent(pending):
            return intent
        current_type = str(getattr(intent, "intent_type", "") or "")
        current_platforms = list(getattr(intent, "namespaces", []) or [])
        pending_platforms = list(getattr(pending, "namespaces", []) or [])
        if current_type not in {"", "chat"} and current_type != pending.intent_type:
            return intent
        if current_platforms and set(current_platforms) != set(pending_platforms):
            return intent
        merged = pending.to_dict()
        merged["raw_input"] = str(getattr(pending, "raw_input", "") or "")
        merged_params = copy.deepcopy(getattr(pending, "scoped_parameters", {}) or {})
        current_params = getattr(intent, "scoped_parameters", {}) or {}
        if isinstance(current_params, Mapping):
            for platform, values in current_params.items():
                if not isinstance(values, Mapping):
                    continue
                destination = dict(merged_params.get(platform, {}) or {})
                destination.update(copy.deepcopy(dict(values)))
                merged_params[platform] = destination
        if pending_platforms:
            try:
                extracted = self.intent_parser.extract_parameters(
                    follow_up_text, pending_platforms
                )
            except Exception:
                extracted = {}
            if isinstance(extracted, Mapping):
                for platform, values in extracted.items():
                    if not isinstance(values, Mapping):
                        continue
                    destination = dict(merged_params.get(platform, {}) or {})
                    destination.update(copy.deepcopy(dict(values)))
                    merged_params[platform] = destination
        merged["attributes"] = {
            **dict(merged.get("attributes") or {}),
            **copy.deepcopy(getattr(intent, "attributes", {}) or {}),
        }
        merged["scoped_parameters"] = merged_params
        merged["intent_type"] = pending.intent_type
        merged["namespaces"] = pending_platforms
        try:
            return ParsedIntent(**{
                key: value for key, value in merged.items()
                if key in ParsedIntent.__dataclass_fields__
            })
        except (TypeError, ValueError):
            return intent

    def _action_clarification_response(
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
    ) -> dict[str, Any]:
        clarification = ui.get("clarification") if isinstance(ui, Mapping) else {}
        confirmation_payload = None
        fields = (
            clarification.get("fields", [])
            if isinstance(clarification, Mapping) else []
        )
        account_fields = [
            item for item in fields
            if isinstance(item, Mapping)
            and str(item.get("path") or "") in set(AccountResolver.ACCOUNT_FIELDS)
        ]
        non_account_fields = [item for item in fields if item not in account_fields]
        if account_fields and not non_account_fields:
            platform = str(account_fields[0].get("platform") or "目标平台")
            confirmation_payload = {
                "type": "ask_account",
                "platform": platform,
                "question": f"请提供要操作的 {platform} 广告账户 ID。",
            }
            reply = confirmation_payload["question"]
        trace.stage_status(
            "action_clarification",
            "补充执行信息",
            "awaiting_confirmation",
            subtitle="等待用户明确资源范围和必填参数",
            safe_metadata={"reason": "required_parameters"},
            safe_output={
                "field_count": len(fields) if isinstance(clarification, Mapping) else 0,
            },
        )
        self.set_action_draft(session_id, {
            "intent": intent.to_dict(),
            "clarification": clarification,
        })
        trace.reply()
        trace.done("awaiting_confirmation", safe_metadata={
            "reason": "action_clarification", "tool_count": 0,
        })
        self.persist_conversation_turn(
            session, turn_id, user_input, reply, execution_trace=trace, ui=ui,
        )
        results = []
        if confirmation_payload:
            results.append({
                "tool": str(account_fields[0].get("tool") or "account_scope"),
                "platform": str(account_fields[0].get("platform") or ""),
                "success": False,
                "data": {},
                "error": "缺少账户ID",
                "needs_confirmation": True,
                "confirmation_payload": confirmation_payload,
            })
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
            "results": results,
            "response_source": "action_clarification",
            "reply": reply,
            "needs_confirmation": bool(confirmation_payload),
            "needs_input": True,
            "confirmation_payload": confirmation_payload,
            "workflow_id": None,
            "ui": dict(ui),
        }


__all__ = ["AdCreationStateServicesMixin"]
