"""Advertising request adapter over the generic PlatformApplication."""

from __future__ import annotations

import threading
import uuid
from typing import Any, Optional

from agents.agent_harness import TurnRequest

from ..core.execution_trace import ExecutionEventCallback, ExecutionTrace
from ..domain.ad.auth import RequestPrincipal


class AdvertisingRunService:
    """Translate the advertising request envelope into one generic Run."""

    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime

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
        platform_application = runtime._platform_application
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
        to_dict = getattr(result, "to_dict", None)
        payload = to_dict() if callable(to_dict) else result
        if not isinstance(payload, dict):
            return payload

        adapter = getattr(getattr(platform_application, "agent", None), "model", None)
        completed = (
            adapter.take_completed(str(payload.get("run_id") or ""))
            if callable(getattr(adapter, "take_completed", None))
            else {}
        )
        payload.setdefault("session_id", effective_session_id)
        if not payload.get("reply") and completed.get("last_reply"):
            payload["reply"] = str(completed["last_reply"])
        payload.setdefault(
            "intent",
            (
                completed.get("intent").to_dict()
                if callable(getattr(completed.get("intent"), "to_dict", None))
                else None
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
        for key in (
            "resource_results",
            "cross_channel_summary",
            "cross_channel_insights",
            "cross_channel_budget_plan",
            "cross_channel_export",
            "clarification",
            "creation_validation",
        ):
            if key in completed:
                payload.setdefault(key, completed[key])
        if completed.get("error_type"):
            payload.setdefault(
                "run_metadata",
                {"error_type": str(completed["error_type"])},
            )
        if completed.get("reason") and runtime._session_manager is not None:
            runtime._session_manager.append_execution_run_event(
                str(payload.get("run_id") or ""),
                {
                    "type": "stage_status",
                    "stage_id": "intent",
                    "status": "failed",
                    "run_id": str(payload.get("run_id") or ""),
                    "turn_id": str(payload.get("turn_id") or ""),
                },
            )
            runtime._session_manager.update_execution_run(
                str(payload.get("run_id") or ""),
                status="failed",
                metadata={"reason": str(completed["reason"])},
            )

        tool_plan: dict[str, list[str]] = {}
        for call in completed.get("calls") or ():
            name = str(getattr(call, "name", "") or "")
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
        session = runtime._sessions.get(effective_session_id)
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
            trace = ExecutionTrace(
                turn_id=str(payload.get("turn_id") or ""),
                redactor=runtime._redact_for_persistence,
            )
            trace.start()
            trace.reply()
            trace.done(
                "failed" if payload.get("status") == "failed" else "succeeded"
            )
            runtime.persistence_services.persist_conversation_turn(
                session,
                str(payload.get("turn_id") or ""),
                runtime._redact_for_persistence(user_input),
                str(payload.get("reply") or ""),
                execution_trace=trace,
                ui=persisted_ui if persisted_ui else None,
                persist_messages=False,
            )
        return payload


__all__ = ["AdvertisingRunService"]
