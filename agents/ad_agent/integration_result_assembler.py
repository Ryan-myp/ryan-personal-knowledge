"""Application-result assembly for the advertising Harness adapter.

The generic Harness owns Run lifecycle and Tool execution.  This module owns
the advertising application's result boundary: it turns Tool messages into
business results, asks the selected feature for analysis, renders the reply,
finishes any already-created workflow, and exports safe ``application_data``.
"""

from __future__ import annotations

from typing import Any, Mapping

from agents.agent_harness import AgentMessage, ModelTurn


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
        turns: dict[str, dict[str, Any]] | None = None,
        completed: dict[str, dict[str, Any]] | None = None,
        *,
        max_completed: int = 256,
    ) -> None:
        self.owner = owner
        self.turns = turns if turns is not None else {}
        self.completed = completed if completed is not None else {}
        self.max_completed = max_completed

    def prune_completed(self) -> None:
        """Bound results when a caller disconnects before reading a Run."""
        while len(self.completed) > self.max_completed:
            oldest = next(iter(self.completed), None)
            if oldest is None:
                return
            self.completed.pop(oldest, None)

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

        feature = (
            self.owner._feature_for_intent(intent)
            if intent is not None else None
        )
        analysis: dict[str, Any] = {}
        if (
            feature is not None
            and callable(getattr(feature, "handles_analysis", None))
            and feature.handles_analysis(intent)
        ):
            try:
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
                        (
                            request.context.get("credentials")
                            if isinstance(request.context, Mapping) else None
                        )
                    ),
                    account_scope=getattr(
                        request.principal, "account_scope", None
                    ),
                    granted_permissions=self.owner._granted_permissions,
                )
                analysis = feature.analyze(intent, results)
                self.decorate_results(results)
                state["tool_plan"] = self.tool_plan_names(results)
            except Exception:
                analysis = {}

        state.update(analysis)
        if intent is None:
            reply = "工具执行完成，但无法生成结构化业务回复。"
            response_source = "renderer"
        else:
            reply, response_source = self.owner._render_response(
                request.user_input,
                intent,
                results,
                any(item.get("requires_confirmation") for item in results),
                analysis=analysis,
                session=state.get("session"),
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
        run_id = str(request.run_id or "")
        self.completed[run_id] = dict(state)
        self.turns.pop(run_id, None)
        return ModelTurn(
            content=reply,
            stop_reason="awaiting_input" if state["needs_input"] else "stop",
        )

    def finish_policy_blocked_run(
        self,
        request: Any,
        tool_results: tuple[dict[str, Any], ...],
    ) -> Mapping[str, Any]:
        """Finalize a Run stopped by the generic Tool policy gate."""
        run_id = str(request.run_id or "")
        if run_id in self.completed:
            return self.export_application_state(self.completed[run_id])
        state = self.turns.get(run_id)
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
        self.completed[run_id] = dict(state)
        self.turns.pop(run_id, None)
        self.prune_completed()
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
        except Exception:
            # Workflow completion is durable best effort here; the Run
            # lifecycle remains authoritative and recovery can reconcile it.
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
