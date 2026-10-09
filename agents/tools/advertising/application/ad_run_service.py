"""Advertising request adapter over the generic PlatformApplication."""

from __future__ import annotations

import threading
import uuid
import logging
from typing import Any, Mapping, Optional

from agents.agent_harness import TurnRequest, redact_for_persistence

from agents.agent_harness.core.execution_trace import ExecutionEventCallback
from agents.agent_platform.governance.identity.principal import RequestPrincipal
from .ad_run_memory import AdvertisingRunMemoryRecorder

logger = logging.getLogger(__name__)


class AdvertisingRunService:
    """Translate the advertising request envelope into one generic Run."""

    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime
        self.memory_recorder = AdvertisingRunMemoryRecorder(runtime)

    def run(
        self,
        user_input: str,
        session_id: str = None,
        user_id: str = "anonymous",
        account_id: str = None,
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
        task_id: Optional[str] = None,
    ) -> dict:
        runtime = self.runtime
        platform_application = runtime.platform_application
        effective_session_id = str(session_id or uuid.uuid4())
        result = platform_application.run(
            TurnRequest(
                user_input=user_input,
                session_id=effective_session_id,
                user_id=user_id,
                tenant_id=tenant_id or "default",
                context={
                    "account_id": account_id,
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
                task_id=task_id,
            )
        )
        application_state = dict(
            getattr(result, "application_data", None) or {}
        )
        to_dict = getattr(result, "to_dict", None)
        payload = to_dict() if callable(to_dict) else result
        if not isinstance(payload, dict):
            return payload
        if not application_state:
            application_state = self._application_state_from_run(
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
            ("execution_plan", {}),
            ("workflow_id", None),
            ("ui", {}),
            ("response_source", "renderer"),
        ):
            payload.setdefault(key, completed.get(key, default))
        for key in ("resource_results", "clarification", "creation_validation"):
            if key in completed:
                payload.setdefault(key, completed[key])
        if completed.get("error_type"):
            payload.setdefault(
                "run_metadata",
                {"error_type": str(completed["error_type"])},
            )
        if completed.get("reason"):
            payload.setdefault("run_metadata", {})
            if isinstance(payload["run_metadata"], dict):
                payload["run_metadata"].setdefault(
                    "reason", str(completed["reason"]),
                )

        tool_plan: dict[str, list[str]] = {}
        for call in completed.get("calls") or ():
            name = str(
                call.get("name")
                if isinstance(call, Mapping)
                else getattr(call, "name", "")
                or ""
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
            next(
                (
                    item.get("confirmation_payload")
                    for item in payload["results"]
                    if isinstance(item, dict) and item.get("confirmation_payload")
                ),
                None,
            ),
        )
        payload.setdefault(
            "needs_input",
            bool(
                completed.get("needs_input")
                or completed.get("needs_confirmation")
                or any(
                    item.get("needs_input") or item.get("needs_confirmation")
                    for item in payload["results"]
                    if isinstance(item, dict)
                )
            ),
        )
        session = runtime.sessions.get(effective_session_id)
        if session is not None:
            raw_ui = payload.get("ui")
            persisted_ui = dict(raw_ui) if isinstance(raw_ui, dict) else {}
            if payload.get("confirmation_payload"):
                persisted_ui["confirmation"] = {
                    "payload": payload.get("confirmation_payload"),
                    "original_request": {
                        "user_input": user_input,
                        "account_id": account_id,
                        "platforms": [
                            item.get("platform")
                            for item in (payload.get("results") or [])
                            if isinstance(item, dict) and item.get("platform")
                        ],
                        "platform_params": platform_params or {},
                        "creation_blueprint_id": creation_blueprint_id,
                        "creation_blueprint_version": creation_blueprint_version,
                        "creation_template_id": creation_template_id,
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
    def _application_state_from_run(
        runtime: Any,
        payload: Mapping[str, Any],
        session_id: str,
        user_input: str,
    ) -> dict[str, Any]:
        """Project generic Harness results into the advertising HTTP envelope."""
        results: list[dict[str, Any]] = []
        tool_types: list[tuple[str, ...]] = []
        for item in payload.get("tool_results") or ():
            if not isinstance(item, Mapping):
                continue
            name = str(item.get("name") or "").strip()
            raw = item.get("content")
            result = dict(raw) if isinstance(raw, Mapping) else {
                "success": not bool(item.get("is_error")),
                "error": str(raw or "") if item.get("is_error") else "",
            }
            if name:
                result.setdefault("tool", name)
                try:
                    definition, _handler = runtime.registry.get(name)
                except (KeyError, AttributeError):
                    definition = None
                if definition is not None:
                    namespace = str(getattr(definition, "namespace", "") or "")
                    result.setdefault("platform", namespace)
                    result.setdefault("action", getattr(definition, "action", ""))
                    result.setdefault(
                        "resource_type",
                        getattr(definition, "resource_type", ""),
                    )
                    tool_types.append(tuple(
                        str(value) for value in (
                            getattr(definition, "intent_types", ()) or ()
                        ) if str(value)
                    ))
            for key in (
                "needs_input", "needs_confirmation", "confirmation_payload",
            ):
                if key in item:
                    result[key] = item[key]
            results.append(result)

        tool_plan: dict[str, list[str]] = {}
        for item in results:
            name = str(item.get("tool") or "")
            namespace = str(item.get("platform") or "")
            if name and namespace:
                tool_plan.setdefault(namespace, []).append(name)
        namespaces = list(tool_plan)
        common_intents = set(tool_types[0]) if tool_types else set()
        for values in tool_types[1:]:
            common_intents.intersection_update(values)
        intent_type = next(iter(tool_types[0]), "tool_calls") if tool_types else "chat"
        if common_intents:
            intent_type = next(
                item for item in tool_types[0] if item in common_intents
            )

        session = runtime._sessions.get(str(session_id or ""))
        metadata = getattr(getattr(session, "ctx", None), "metadata", {})
        skill_context = (
            metadata.get("skill_context", {})
            if isinstance(metadata, Mapping) else {}
        )
        skill_context = skill_context if isinstance(skill_context, Mapping) else {}
        confirmation = next(
            (
                item.get("confirmation_payload") for item in results
                if isinstance(item.get("confirmation_payload"), Mapping)
            ),
            None,
        )
        request_error = str(payload.get("request_validation_error") or "")
        ui = next(
            (dict(item["ui"]) for item in results if isinstance(item.get("ui"), Mapping)),
            {},
        )
        return {
            "intent": {
                "intent_type": intent_type,
                "namespaces": namespaces,
                "raw_input": redact_for_persistence(str(user_input or "")),
            },
            "last_results": results,
            "tool_plan": tool_plan,
            "tool_selection": {"tools": [item.get("tool") for item in results]},
            "memory": list(skill_context.get("memory") or []),
            "memory_updates": list(metadata.get("memory_updates") or [])
            if isinstance(metadata, Mapping) else [],
            "needs_input": bool(
                payload.get("needs_input")
                or any(
                    item.get("needs_input") or item.get("needs_confirmation")
                    for item in results
                )
            ),
            "needs_confirmation": any(
                bool(item.get("needs_confirmation")) for item in results
            ),
            "confirmation_payload": confirmation,
            "ui": ui,
            "policy_errors": [request_error] if request_error else [],
            "response_source": "policy" if request_error else "harness",
        }

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
                            dict(item) for item in events
                            if isinstance(item, dict)
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
