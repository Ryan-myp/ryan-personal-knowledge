"""Advertising request adapter over the generic PlatformApplication."""

from __future__ import annotations

import logging
import threading
import uuid
from typing import Any, Mapping, Optional

from agents.agent_harness import InputMedia, TurnRequest
from agents.agent_harness.core.execution_trace import ExecutionEventCallback
from agents.agent_platform.governance.identity.principal import RequestPrincipal
from .ad_run_memory import AdvertisingRunMemoryRecorder
from .ad_run_projection import AdvertisingRunProjection
from .ad_run_media import media_gallery_from_results
from agents.tools.advertising.shared.domain.conversation import visible_run_reply

logger = logging.getLogger(__name__)


class AdvertisingRunService:
    """Translate the advertising request envelope into one generic Run."""

    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime
        self.memory_recorder = AdvertisingRunMemoryRecorder(runtime)

    def _initial_tool_choice(
        self, blueprint_id: Any, version: Any, confirmed: bool, payload: Any,
        tool_allowlist: Optional[list[str]] = None,
    ) -> Any:
        if confirmed and isinstance(payload, Mapping) and payload.get("type") == "confirm_write":
            tool = payload.get("tool")
            if isinstance(tool, str) and tool and (
                tool_allowlist is None or tool in tool_allowlist
            ):
                return {"type": "function", "function": {"name": tool}}
        if not blueprint_id:
            return None
        blueprint = self.runtime.creation_blueprints.get(blueprint_id, version or None)
        preview = payload.get("preview") if isinstance(payload, Mapping) else None
        pending = preview.get("pending_tool") if isinstance(preview, Mapping) else None
        if confirmed and blueprint is not None and pending in blueprint.tools:
            return {"type": "function", "function": {"name": pending}}
        return "required"

    def run(
        self,
        user_input: str,
        session_id: str = None,
        user_id: str = "anonymous",
        account_id: str = None,
        interaction_response: Optional[dict] = None,
        credentials: dict = None,
        platform_params: dict = None,
        confirmed: bool = False,
        confirmation_payload: Optional[dict] = None,
        creation_blueprint_id: Optional[str] = None,
        creation_blueprint_version: Optional[str] = None,
        creation_template_id: Optional[str] = None,
        principal: Optional[RequestPrincipal] = None,
        tenant_id: Optional[str] = None,
        cancellation_event: Optional[threading.Event] = None,
        event_callback: Optional[ExecutionEventCallback] = None,
        execution_mode: Optional[str] = None,
        tool_allowlist: Optional[list[str]] = None,
        task_id: Optional[str] = None,
        input_media: tuple[InputMedia, ...] = (),
        streaming: bool = False,
    ) -> dict:
        runtime = self.runtime
        effective_session_id = str(session_id or uuid.uuid4())
        result = runtime.platform_application.run(TurnRequest(
            user_input=user_input,
            session_id=effective_session_id,
            user_id=user_id,
            tenant_id=tenant_id or "default",
            context={
                "account_id": account_id,
                "_agent_interaction_response": interaction_response,
                "credentials": credentials,
                "platform_params": platform_params,
                "confirmed": confirmed,
                "confirmation_payload": confirmation_payload,
                "creation_blueprint_id": creation_blueprint_id,
                "creation_blueprint_version": creation_blueprint_version,
                "creation_template_id": creation_template_id,
            },
            principal=principal,
            cancellation_event=cancellation_event,
            event_callback=event_callback,
            execution_mode=execution_mode,
            input_media=input_media,
            tool_allowlist=(
                tuple(tool_allowlist) if tool_allowlist is not None else None
            ),
            initial_tool_choice=self._initial_tool_choice(
                creation_blueprint_id, creation_blueprint_version,
                confirmed, confirmation_payload, tool_allowlist,
            ),
            task_id=task_id,
            streaming=bool(streaming),
        ))
        application_state = dict(getattr(result, "application_data", None) or {})
        to_dict = getattr(result, "to_dict", None)
        payload = to_dict() if callable(to_dict) else result
        if not isinstance(payload, dict):
            return payload
        if not application_state:
            application_state = AdvertisingRunProjection.application_state_from_run(
                runtime, payload, effective_session_id, user_input,
            )

        completed = application_state
        self.memory_recorder.capture(
            completed.get("last_results") or (),
            execution_mode=execution_mode or runtime.execution_mode,
            run_id=str(payload.get("run_id") or ""),
            session_id=effective_session_id,
            user_id=str(user_id or "anonymous"),
            tenant_id=str(tenant_id or "default"),
        )
        payload.setdefault("session_id", effective_session_id)
        if not payload.get("reply") and completed.get("last_reply"):
            payload["reply"] = str(completed["last_reply"])
        payload.setdefault(
            "intent",
            (
                dict(completed["intent"])
                if isinstance(completed.get("intent"), dict)
                else (
                    completed.get("intent").to_dict()
                    if callable(getattr(completed.get("intent"), "to_dict", None))
                    else None
                )
            ),
        )
        payload.setdefault("results", list(completed.get("last_results") or []))
        payload.setdefault("policy_errors", list(completed.get("policy_errors") or []))
        for key, default in (
            ("tool_selection", None),
            ("memory", []),
            ("memory_updates", []),
            ("knowledge_context", {}),
            ("execution_plan", {}),
            ("workflow_id", None),
            ("ui", {}),
            ("response_source", "renderer"),
        ):
            payload.setdefault(key, completed.get(key, default))
        for key in ("resource_results", "clarification", "creation_validation"):
            if key in completed:
                payload.setdefault(key, completed[key])
        media_gallery = media_gallery_from_results(payload.get("results"))
        if media_gallery:
            ui = payload.get("ui")
            projected_ui = dict(ui) if isinstance(ui, Mapping) else {}
            projected_ui["media_gallery"] = media_gallery
            payload["ui"] = projected_ui
        if creation_template_id:
            ui = payload.get("ui")
            cards = ui.get("cards") if isinstance(ui, Mapping) else None
            if isinstance(cards, list):
                for card in cards:
                    if (
                        not isinstance(card, dict)
                        or card.get("type") != "ad_creation_form"
                    ):
                        continue
                    if (
                        creation_blueprint_id
                        and card.get("blueprint_id") != creation_blueprint_id
                    ):
                        continue
                    if (
                        account_id
                        and card.get("account_id")
                        and str(card["account_id"]) != str(account_id)
                    ):
                        continue
                    card.setdefault("template_id", str(creation_template_id))
        if completed.get("error_type"):
            payload.setdefault("run_metadata", {
                "error_type": str(completed["error_type"]),
            })
        if completed.get("reason"):
            payload.setdefault("run_metadata", {})
            if isinstance(payload["run_metadata"], dict):
                payload["run_metadata"].setdefault("reason", str(completed["reason"]))

        tool_plan: dict[str, list[str]] = {}
        for call in completed.get("calls") or ():
            name = str(
                call.get("name") if isinstance(call, Mapping)
                else getattr(call, "name", "") or ""
            )
            if not name:
                continue
            try:
                definition, _handler = runtime.registry.get(name)
            except KeyError:
                continue
            tool_plan.setdefault(str(definition.namespace), []).append(name)
        payload.setdefault("tool_plan", completed.get("tool_plan") or tool_plan)
        payload.setdefault(
            "needs_confirmation",
            any(item.get("needs_confirmation") for item in payload["results"]),
        )
        payload.setdefault(
            "confirmation_payload",
            next((
                item.get("confirmation_payload") for item in payload["results"]
                if isinstance(item, dict) and item.get("confirmation_payload")
            ), None),
        )
        payload.setdefault(
            "needs_input",
            bool(
                completed.get("needs_input")
                or completed.get("needs_confirmation")
                or any(
                    item.get("needs_input") or item.get("needs_confirmation")
                    for item in payload["results"] if isinstance(item, dict)
                )
            ),
        )
        payload["reply"] = runtime.redact_for_persistence(visible_run_reply(payload))
        session = runtime.sessions.get(effective_session_id)
        if session is not None:
            raw_ui = payload.get("ui")
            persisted_ui = dict(raw_ui) if isinstance(raw_ui, dict) else {}
            if payload.get("confirmation_payload"):
                persisted_ui["confirmation"] = {
                    "payload": payload.get("confirmation_payload"),
                    "original_request": {
                        "user_input": user_input,
                        "session_id": effective_session_id,
                        "account_id": account_id,
                        "platforms": [
                            item.get("platform") for item in (payload.get("results") or [])
                            if isinstance(item, dict) and item.get("platform")
                        ],
                        "platform_params": platform_params or {},
                        "creation_blueprint_id": creation_blueprint_id,
                        "creation_blueprint_version": creation_blueprint_version,
                        "creation_template_id": creation_template_id,
                        "execution_mode": execution_mode,
                        "tool_allowlist": tool_allowlist,
                    },
                }
                payload["ui"] = persisted_ui
            execution_trace = self._load_execution_trace(
                runtime,
                str(payload.get("run_id") or ""),
                str(payload.get("turn_id") or ""),
                str(payload.get("status") or ""),
            )
            runtime.persistence_services.persist_conversation_turn(
                session,
                str(payload.get("turn_id") or ""),
                runtime.redact_for_persistence(user_input),
                str(payload.get("reply") or ""),
                execution_trace=execution_trace,
                ui=persisted_ui if persisted_ui else None,
                persist_messages=False,
            )
        return payload

    @staticmethod
    def _load_execution_trace(
        runtime: Any, run_id: str, turn_id: str, status: str,
    ) -> dict[str, Any]:
        """Reuse the generic RunStore events as the durable conversation trace."""
        manager = runtime.session_manager
        if manager is not None:
            list_events = getattr(manager, "list_execution_run_events", None)
            if callable(list_events):
                try:
                    events = list_events(run_id, after_seq=0, limit=512)
                    if events:
                        normalized_events = [
                            dict(item) for item in events if isinstance(item, dict)
                        ]
                        if not normalized_events or normalized_events[-1].get("type") != "done":
                            normalized_events.append({
                                "type": "done",
                                "event_type": "done",
                                "trace_id": f"run:{run_id}",
                                "turn_id": turn_id,
                                "seq": max(
                                    [int(item.get("seq", 0)) for item in normalized_events]
                                    or [0]
                                ) + 1,
                                "status": status or "unknown",
                            })
                        return {
                            "trace_id": f"run:{run_id}",
                            "turn_id": turn_id,
                            "status": status or "unknown",
                            "events": normalized_events,
                        }
                except Exception as error:
                    logger.debug(
                        "failed to load durable Run events for conversation trace: %s",
                        type(error).__name__,
                    )
        return {
            "trace_id": f"run:{run_id}",
            "turn_id": turn_id,
            "status": status or "unknown",
            "events": [],
        }


__all__ = ["AdvertisingRunService"]
