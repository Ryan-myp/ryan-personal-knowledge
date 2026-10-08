"""Application-result assembly for the advertising Harness adapter.

The generic Harness owns Run lifecycle and Tool execution.  This module owns
the advertising application's result boundary: it turns Tool messages into
business results, asks the selected feature for analysis, renders the reply,
finishes any already-created workflow, and exports safe ``application_data``.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

from agents.agent_harness import AgentMessage, ModelTurn


logger = logging.getLogger(__name__)

_MEMORY_ERROR_CODES = frozenset({
    "AUTH_EXPIRED",
    "TIMEOUT",
    "RATE_LIMIT",
    "PROVIDER_RESULT_UNKNOWN",
    "PROVIDER_TEMPORARY_ERROR",
    "PROVIDER_5XX",
    "INVALID_REQUEST",
    "TOOL_EXECUTION_ERROR",
})


class AdvertisingResultAssembler:
    """Assemble one advertising turn without owning Runtime lifecycle."""

    _PUBLIC_STATE_KEYS = (
        "last_reply",
        "last_results",
        "policy_errors",
        "tool_selection",
        "memory",
        "memory_updates",
        "execution_plan",
        "workflow_id",
        "ui",
        "response_source",
        "resource_results",
        "cross_channel_summary",
        "cross_channel_insights",
        "cross_channel_budget_plan",
        "cross_channel_export",
        "clarification",
        "creation_validation",
        "needs_input",
        "needs_confirmation",
        "confirmation_payload",
        "error_type",
        "reason",
        "tool_plan",
    )

    def __init__(
        self,
        owner: Any,
    ) -> None:
        self.owner = owner

    def export_application_state(self, state: Mapping[str, Any]) -> dict[str, Any]:
        """Expose only response data through the generic RunResult extension."""
        intent = state.get("intent")
        if callable(getattr(intent, "to_dict", None)):
            intent = intent.to_dict()
        calls = []
        for call in state.get("calls") or ():
            to_dict = getattr(call, "to_dict", None)
            calls.append(to_dict() if callable(to_dict) else dict(call))
        result = {
            key: state[key]
            for key in self._PUBLIC_STATE_KEYS
            if key in state
        }
        result["intent"] = intent
        result["calls"] = calls
        return result

    def finish_turn(
        self,
        state: dict[str, Any],
        request: Any,
        tool_messages: list[AgentMessage],
    ) -> ModelTurn:
        intent = state.get("intent")
        results = self._results_from_messages(tool_messages)
        self.decorate_results(results)
        analysis = self._analyze_results(state, request, intent, results)
        state.update(analysis)
        reply, response_source = self._render_reply(
            state, request, intent, results, analysis,
        )
        state["last_results"] = results
        state["last_reply"] = reply
        state["response_source"] = response_source
        state["needs_input"] = any(
            item.get("needs_input") or item.get("needs_confirmation")
            for item in results
        )
        state.setdefault("ui", {})
        state.setdefault("workflow_id", None)
        self.finish_workflow(state, results, intent)
        self._remember_runtime_events(request, results)
        return ModelTurn(
            content=reply,
            stop_reason="awaiting_input" if state["needs_input"] else "stop",
        )

    def _analyze_results(
        self,
        state: dict[str, Any],
        request: Any,
        intent: Any,
        results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        feature = self.owner._feature_for_intent(intent) if intent is not None else None
        handles_analysis = getattr(feature, "handles_analysis", None)
        if not callable(handles_analysis):
            return {}
        try:
            if not handles_analysis(intent):
                return {}
            feature.collect_metrics(
                services=self.owner.services,
                intent=intent,
                tool_plan={
                    platform: [
                        self.owner.registry.get(name)[0]
                        for name in names
                    ]
                    for platform, names in self.tool_plan_names(results).items()
                },
                results=results,
                session=state.get("session"),
                turn_id=str(request.turn_id or ""),
                request_clients=self.owner._build_request_clients(
                    request.context.get("credentials")
                    if isinstance(request.context, Mapping) else None
                ),
                account_scope=getattr(request.principal, "account_scope", None),
                granted_permissions=self.owner._granted_permissions,
            )
            analysis = feature.analyze(intent, results)
            self.decorate_results(results)
            state["tool_plan"] = self.tool_plan_names(results)
            return analysis if isinstance(analysis, dict) else {}
        except Exception as error:
            logger.debug("业务分析阶段失败: %s", type(error).__name__)
            return {}

    def _render_reply(
        self,
        state: Mapping[str, Any],
        request: Any,
        intent: Any,
        results: list[dict[str, Any]],
        analysis: dict[str, Any],
    ) -> tuple[str, str]:
        if intent is None:
            return "工具执行完成，但无法生成结构化业务回复。", "renderer"
        return self.owner._render_response(
            request.user_input,
            intent,
            results,
            any(item.get("requires_confirmation") for item in results),
            analysis=analysis,
            session=state.get("session"),
        )

    def _remember_runtime_events(
        self,
        request: Any,
        results: list[Mapping[str, Any]],
    ) -> None:
        """Persist only concise outcomes from non-simulated live write Tools."""
        manager = getattr(self.owner, "_memory_manager", None)
        remember = getattr(manager, "remember_runtime_event", None)
        mode = getattr(request, "execution_mode", "")
        mode = str(getattr(mode, "value", mode) or "").strip().lower()
        if not callable(remember) or mode != "live":
            return
        tenant_id = str(getattr(request, "tenant_id", "default") or "default")
        user_id = str(getattr(request, "user_id", "anonymous") or "anonymous")
        session_id = str(getattr(request, "session_id", "") or "")
        run_id = str(getattr(request, "run_id", "") or "")
        if not session_id or not run_id:
            return
        for index, result in enumerate(results):
            self._remember_one_runtime_event(
                remember,
                request,
                result,
                index=index,
            )

    def _remember_one_runtime_event(
        self,
        remember: Any,
        request: Any,
        result: Mapping[str, Any],
        *,
        index: int,
    ) -> None:
        tenant_id = str(getattr(request, "tenant_id", "default") or "default")
        user_id = str(getattr(request, "user_id", "anonymous") or "anonymous")
        session_id = str(getattr(request, "session_id", "") or "")
        run_id = str(getattr(request, "run_id", "") or "")
        name = str(result.get("tool") or "").strip()
        if not name:
            return
        try:
            definition, _handler = self.owner.registry.get(name)
        except (KeyError, AttributeError):
            return
        if not getattr(definition, "is_write_tool", False):
            return
        event = self._runtime_event_summary(definition, result)
        if event is None:
            return
        event_type, summary, outcome = event
        try:
            remember(
                summary,
                tenant_id=tenant_id,
                user_id=user_id,
                session_id=session_id,
                event_type=event_type,
                dedupe_key=f"{run_id}:{name}:{index}",
                outcome=outcome,
                tags=[f"tool:{name}", f"channel:{definition.namespace}"],
            )
        except Exception as error:
            logger.debug("运行事件记忆写入失败: %s", type(error).__name__)

    @staticmethod
    def _runtime_event_summary(
        definition: Any,
        result: Mapping[str, Any],
    ) -> tuple[str, str, str] | None:
        data = result.get("data")
        data = data if isinstance(data, Mapping) else {}
        if (
            result.get("simulated")
            or data.get("simulated")
            or str(data.get("mode") or "").strip().lower() == "dry_run"
            or result.get("requires_confirmation")
            or result.get("needs_confirmation")
            or result.get("needs_input")
        ):
            return None
        name = str(definition.name)
        namespace = str(definition.namespace)
        if result.get("success"):
            return (
                "operation_succeeded",
                f"Live write succeeded: {name} on {namespace}.",
                "succeeded",
            )
        detail = result.get("error_detail")
        code = str(detail.get("code") or "") if isinstance(detail, Mapping) else ""
        if code not in _MEMORY_ERROR_CODES:
            return None
        return (
            "operation_failed",
            f"Live write failed: {name} on {namespace}; code={code}.",
            code,
        )

    def finish_policy_blocked_run(
        self,
        request: Any,
        tool_results: tuple[dict[str, Any], ...],
        state: dict[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        """Finalize a Run stopped by the generic Tool policy gate."""
        if state is None:
            return {}
        results = self._results_from_policy_items(tool_results)
        self.decorate_results(results)
        state["last_results"] = results
        state["last_reply"] = next(
            (
                str(item["confirmation_payload"]["question"])
                for item in results
                if isinstance(item.get("confirmation_payload"), Mapping)
                and item["confirmation_payload"].get("question")
            ),
            "工具调用被执行策略阻断，请根据返回的提示补充信息后重试。",
        )
        state["response_source"] = "tool_policy"
        state["needs_input"] = any(
            item.get("needs_input") or item.get("needs_confirmation")
            for item in results
        )
        state["needs_confirmation"] = any(
            item.get("needs_confirmation") for item in results
        )
        state["confirmation_payload"] = next(
            (
                item.get("confirmation_payload")
                for item in results
                if item.get("confirmation_payload")
            ),
            None,
        )
        state.setdefault("workflow_id", None)
        self.finish_workflow(state, results, state.get("intent"))
        return self.export_application_state(state)

    def finish_workflow(
        self,
        state: Mapping[str, Any],
        results: list[dict[str, Any]],
        intent: Any,
    ) -> None:
        workflow_id = state.get("workflow_id")
        if not workflow_id:
            return
        tool_plan: dict[str, list[Any]] = {}
        for platform, names in (state.get("tool_plan") or {}).items():
            for name in names or ():
                try:
                    definition, _handler = self.owner.registry.get(str(name))
                except KeyError:
                    continue
                tool_plan.setdefault(str(platform), []).append(definition)
        workflow_inputs = {
            index: dict(call.arguments)
            for index, call in enumerate(state.get("calls") or (), 1)
        }
        try:
            self.owner.workflow.finish(
                str(workflow_id),
                tool_plan,
                results,
                workflow_inputs,
                intent=intent,
                session=state.get("session"),
            )
        except Exception as error:
            # Workflow completion is durable best effort here; the Run
            # lifecycle remains authoritative and recovery can reconcile it.
            logger.debug("Workflow finalization deferred: %s", type(error).__name__)
            return

    def decorate_results(self, results: list[dict[str, Any]]) -> None:
        for result in results:
            name = str(result.get("tool") or "")
            if not name:
                continue
            try:
                definition, _ = self.owner.registry.get(name)
            except KeyError:
                continue
            for key in (
                "action",
                "resource_type",
                "resource_id_field",
                "parent_resource_type",
                "parent_resource_id_field",
                "result_items_key",
                "result_id_fields",
                "related_resource_type",
                "related_resource_id_fields",
            ):
                value = getattr(definition, key, None)
                if value not in (None, "", [], ()):
                    result.setdefault(key, value)

    def tool_plan_names(
        self, results: list[dict[str, Any]],
    ) -> dict[str, list[str]]:
        plan: dict[str, list[str]] = {}
        for result in results:
            name = str(result.get("tool") or "")
            platform = str(result.get("platform") or "")
            if name and platform:
                plan.setdefault(platform, []).append(name)
        return plan

    def _results_from_messages(
        self, tool_messages: list[AgentMessage],
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for message in tool_messages:
            content = message.content
            if isinstance(content, Mapping):
                result = dict(content)
            else:
                result = {"success": False, "error": str(content)}
            if isinstance(message.metadata, Mapping):
                for key in (
                    "needs_input",
                    "needs_confirmation",
                    "confirmation_payload",
                ):
                    if key in message.metadata:
                        result[key] = message.metadata[key]
            result.setdefault("tool", message.name or "")
            result.setdefault(
                "platform",
                getattr(
                    self.owner.registry.get(message.name)[0],
                    "namespace",
                    "",
                ) if message.name else "",
            )
            results.append(result)
        return results

    def _results_from_policy_items(
        self, tool_results: tuple[dict[str, Any], ...],
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for item in tool_results:
            name = str(item.get("name") or "")
            content = item.get("content")
            if isinstance(content, Mapping):
                result = dict(content)
            else:
                result = {
                    "success": not bool(item.get("is_error")),
                    "error": str(content or ""),
                }
            result.update({
                "tool": name,
                "platform": (
                    getattr(self.owner.registry.get(name)[0], "namespace", "")
                    if name else ""
                ),
            })
            for key in ("needs_input", "needs_confirmation", "confirmation_payload"):
                if key in item:
                    result[key] = item[key]
            results.append(result)
        return results
