"""Adapters that let advertising Skills/Tools plug into any Agent Harness."""

from __future__ import annotations

import logging
from typing import Any, Mapping

from agents.agent_harness import (
    AgentMessage,
    ContextProvider,
    ModelTurn,
    MarkdownSkillDirectorySource,
    StaticToolSource,
    ToolArgumentBinding,
    ToolCall,
    ToolCatalog,
    ToolBinding,
)
from agents.agent_harness.core.llm_client import capture_llm_usage
from agents.agent_harness.core.interfaces import ParsedIntent, ToolContext, ToolResult
from .ad_turn_context import AdTurnContextService
from .integration_result_assembler import AdvertisingResultAssembler
from .integration_investigation import ReadOnlyInvestigationPlanner
from .integration_turn_planner import AdvertisingTurnPlanner
from .integration_turn_handler import AdvertisingTurnHandler


logger = logging.getLogger(__name__)


class _ContextTrace:
    """Minimal observer for the generic context-provider boundary."""

    def stage_status(self, *_args: Any, **_kwargs: Any) -> None:
        return None


class AdvertisingContextProvider:
    """Adapt advertising advisory context to the generic Harness port."""

    def __init__(self, owner: Any) -> None:
        self.owner = owner
        self._service = AdTurnContextService()
        self._contexts: dict[str, dict[str, Any]] = {}

    def build_context(
        self, request: Any, _messages: list[AgentMessage],
    ) -> dict[str, Any]:
        run_id = str(request.run_id or "")
        if run_id in self._contexts:
            return dict(self._contexts[run_id])
        request_context = (
            request.context if isinstance(request.context, Mapping) else {}
        )
        account_id = request_context.get("account_id")
        if account_id in (None, ""):
            account_id = self._account_from_platform_params(request_context)
        session = self.owner._sessions.get(str(request.session_id or ""))
        if session is None:
            session = self.owner._ensure_session(
                str(request.session_id or ""),
                request.user_id,
                account_id,
                request_context.get("credentials"),
                tenant_id=request.tenant_id,
            )
        if account_id not in (None, ""):
            session.ctx.account_id = str(account_id)
            if isinstance(request.context, dict):
                request.context["account_id"] = str(account_id)
        safe_input = self.owner._redact_for_persistence(request.user_input)
        self._service.prepare(
            runtime=self.owner,
            session=session,
            session_id=str(request.session_id or ""),
            user_id=str(request.user_id or "anonymous"),
            tenant_id=str(request.tenant_id or "default"),
            safe_user_input=safe_input,
            trace=_ContextTrace(),
        )
        skill_context = session.ctx.metadata.get("skill_context", {})
        if not isinstance(skill_context, dict):
            skill_context = {}
        result = {
            "skill_context": dict(skill_context),
            "prompt": self._render_prompt(skill_context),
        }
        self._contexts[run_id] = result
        return dict(result)

    def cleanup(self, request: Any, _state: Any = None) -> None:
        """Release the bounded context snapshot owned by one Run."""
        self._contexts.pop(str(getattr(request, "run_id", "") or ""), None)

    def _account_from_platform_params(self, request_context: Mapping[str, Any]) -> Any:
        values_by_platform = request_context.get("platform_params")
        if not isinstance(values_by_platform, Mapping):
            return None
        scoped_accounts: dict[str, Any] = {}
        for raw_platform, values in values_by_platform.items():
            if not isinstance(values, Mapping):
                continue
            platform = self.owner._canonical_platform(str(raw_platform))
            definitions = self.owner.registry.list_by_namespace(platform)
            fields = {
                field
                for definition in definitions
                for field in (getattr(definition, "scope_fields", ()) or ())
            } or {
                "account_id", "ad_account_id", "advertiser_id", "customer_id",
            }
            for field in fields:
                if values.get(field) not in (None, ""):
                    scoped_accounts[platform] = values[field]
                    break
        # The request-level account is a single-scope convenience. A
        # multi-platform request must keep account IDs namespace-scoped.
        return next(iter(scoped_accounts.values())) if len(scoped_accounts) == 1 else None

    @staticmethod
    def _render_prompt(skill_context: Mapping[str, Any]) -> str:
        parts = []
        for key, label, limit in (
            ("tool_prompt", "Available Tool contracts", 6000),
            ("expert_knowledge", "Advisory Skill and knowledge context", 6000),
            ("knowledge", "Retrieved knowledge", 6000),
        ):
            value = skill_context.get(key)
            if isinstance(value, list):
                value = "\n".join(str(item) for item in value)
            if value:
                parts.append(f"{label}:\n{str(value)[:limit]}")
        return "\n\n".join(parts)


def advertising_tool_source(
    provider_tools: Any, *, source_id: str | None = None,
) -> StaticToolSource:
    """Expose advertising Tools as a generic Tool Source.

    The input only needs to publish ``register_tools()``. It may be a local
    provider adapter, SDK/HTTP connector or MCP-backed publisher. The generic
    Agent Harness sees only the resulting Tool bindings.
    """
    register_tools = getattr(provider_tools, "register_tools", None)
    if not callable(register_tools):
        raise TypeError("provider_tools must expose register_tools()")
    bindings = []
    for definition, executor in register_tools():
        bindings.append(ToolBinding(
            definition,
            _GenericContextExecutor(executor),
        ))
    platform = str(
        getattr(provider_tools, "platform_name", "advertising") or "advertising"
    ).strip()
    return StaticToolSource(source_id or f"advertising:{platform}", bindings)


def advertising_skill_source(*, source_id: str = "ad-skills") -> MarkdownSkillDirectorySource:
    """Expose the ad Skill Markdown tree to any generic Agent."""
    from pathlib import Path

    return MarkdownSkillDirectorySource(
        Path(__file__).resolve().parents[3] / "skills" / "advertising",
        source_id=source_id,
    )


class _GenericContextExecutor:
    """Bridge generic ToolCallContext into the ad ToolContext contract."""

    def __init__(self, executor: Any) -> None:
        self.executor = executor

    def execute(self, context: Any, input_data: dict[str, Any]) -> Any:
        request = context.request
        request_context = (
            request.context if isinstance(request.context, Mapping) else {}
        )
        ad_context = ToolContext(
            session_id=str(request.session_id or ""),
            user_id=str(request.user_id or "anonymous"),
            scope={
                key: value
                for key, value in request_context.items()
                if key != AdvertisingModelAdapter.STATE_CONTEXT_KEY
            },
            credentials=request_context.get("credentials"),
            metadata={
                "execution_mode": str(request.execution_mode or "dry_run"),
                "run_id": str(request.run_id or ""),
                "turn_id": str(request.turn_id or ""),
                "cancellation_event": request.cancellation_event,
                "lease_lost_event": request.lease_lost_event,
            },
        )
        execute = getattr(self.executor, "execute", None)
        if callable(execute):
            return execute(ad_context, input_data)
        if callable(self.executor):
            return self.executor(ad_context, input_data)
        raise TypeError("advertising Tool executor is not callable")


class AdvertisingToolCatalog:
    """Live generic catalog backed by the verified advertising Tool Registry.

    The catalog is intentionally a read-only view.  Provider registration and
    removal remain owned by the advertising integration boundary, while the
    Harness only asks for current contracts and bindings.
    """

    def __init__(self, owner: Any) -> None:
        self.owner = owner

    def list_tools(self) -> list[Any]:
        return list(self.owner.registry.list_all())

    def list_all(self) -> list[Any]:
        return self.list_tools()

    def source_snapshot(self) -> dict[str, list[str]]:
        snapshot = getattr(self.owner.registry, "source_snapshot", None)
        if not callable(snapshot):
            return {}
        return dict(snapshot())

    def get_binding(self, name: str) -> ToolBinding:
        definition, _handler = self.owner.registry.get(str(name))
        return ToolBinding(definition, AdvertisingToolExecutor(self.owner, definition))


class AdvertisingToolExecutor:
    """Adapt one registered provider Tool to the generic Tool executor port."""

    def __init__(self, owner: Any, definition: Any) -> None:
        self.owner = owner
        self.definition = definition

    def execute(self, context: Any, input_data: dict[str, Any]) -> dict[str, Any]:
        request = context.request
        request_context = (
            request.context if isinstance(request.context, Mapping) else {}
        )
        session = self._request_session(request, request_context)
        account_id = self._request_account(request_context, input_data, session)
        original_account = session.ctx.account_id
        session.ctx.account_id = account_id
        try:
            result = self._run_tool(request, request_context, session, input_data)
            if not self._is_dry_run_write(request):
                self._consume_confirmation(
                    request, request_context, account_id, input_data, result,
                )
            return self._save_safe_result(session, result)
        finally:
            session.ctx.account_id = original_account

    def _is_dry_run_write(self, request: Any) -> bool:
        return (
            bool(getattr(self.definition, "is_write_tool", False))
            and str(request.execution_mode or "dry_run") == "dry_run"
        )

    def _request_session(
        self, request: Any, request_context: Mapping[str, Any],
    ) -> Any:
        session_id = str(request.session_id or "")
        session = self.owner._sessions.get(session_id)
        if session is not None:
            return session
        return self.owner._ensure_session(
            session_id, request.user_id, request_context.get("account_id"),
            request_context.get("credentials"), tenant_id=request.tenant_id,
        )

    def _request_account(
        self, request_context: Mapping[str, Any], input_data: Mapping[str, Any],
        session: Any,
    ) -> Any:
        return (
            self._find_request_scope(request_context)
            or request_context.get("account_id")
            or self._find_scope_value(input_data)
            or getattr(session.ctx, "account_id", None)
        )

    def _run_tool(
        self, request: Any, request_context: Mapping[str, Any],
        session: Any, input_data: Mapping[str, Any],
    ) -> ToolResult:
        if self._is_dry_run_write(request):
            return self.owner._simulate_write(
                self.definition, dict(input_data),
                str(getattr(self.definition, "namespace", "") or ""),
            )
        clients = self.owner._build_request_clients(
            request_context.get("credentials"),
        )
        result = self.owner.tool_executor.execute(
            session.ctx, self.definition.name, dict(input_data), clients,
        )
        result = self.owner.input_builder.decorate_lookup_result(
            self.definition, result, session.ctx,
            str(getattr(self.definition, "namespace", "") or ""),
        )
        if self._is_uncertain_live_write(request, result):
            result.data = {
                **result.data, "execution_status": "unknown",
                "requires_reconciliation": True, "effect_state": "unknown",
            }
        return result

    def _is_uncertain_live_write(self, request: Any, result: Any) -> bool:
        return (
            bool(getattr(self.definition, "is_write_tool", False))
            and str(request.execution_mode or "dry_run").lower() == "live"
            and self.owner.write_guard is not None
            and self.owner.security.is_uncertain_provider_failure(
                self.definition, result,
            )
            and isinstance(getattr(result, "data", None), dict)
        )

    def _consume_confirmation(
        self, request: Any, request_context: Mapping[str, Any],
        account_id: Any, input_data: Mapping[str, Any], result: Any,
    ) -> None:
        payload = request_context.get("confirmation_payload")
        if not (result.success and request_context.get("confirmed")):
            return
        if not isinstance(payload, Mapping) or self.owner._session_manager is None:
            return
        expected = self.owner.security.confirmation_plan(
            str(request.session_id or ""),
            str(request.user_id or "anonymous"),
            str(account_id or ""),
            self.definition,
            dict(input_data),
            preview={"tool": self.definition.name, "input": dict(input_data)},
        )
        self.owner._session_manager.consume_approval(
            expected["plan_fingerprint"], expected["confirmation_token"],
        )

    def _save_safe_result(self, session: Any, result: Any) -> dict[str, Any]:
        if not isinstance(result, ToolResult):
            result = ToolResult.error(
                f"Tool '{self.definition.name}' returned an invalid result"
            )
        result = self.owner.security.normalize_read_result_evidence(
            self.definition, result,
        )
        result = self.owner.security.enforce_result_limit(result, self.definition)
        safe = self.owner.security.sanitize_result(result)
        session.save_result(
            self.definition.name, safe,
            platform=getattr(self.definition, "namespace", ""),
        )
        return safe.to_dict()

    def _find_scope_value(self, values: Mapping[str, Any]) -> Any:
        for field in getattr(self.definition, "scope_fields", ()) or ():
            value = values.get(field)
            if value not in (None, ""):
                return value
        return None

    def _find_request_scope(self, request_context: Mapping[str, Any]) -> Any:
        platform_params = request_context.get("platform_params")
        if not isinstance(platform_params, Mapping):
            return None
        namespace = self.owner._resolve_platform_identifier(
            str(getattr(self.definition, "namespace", "") or "")
        )
        for key, values in platform_params.items():
            if self.owner._resolve_platform_identifier(str(key)) != namespace:
                continue
            if not isinstance(values, Mapping):
                continue
            for field in getattr(self.definition, "scope_fields", ()) or (
                "account_id", "ad_account_id", "advertiser_id", "customer_id",
            ):
                if values.get(field) not in (None, ""):
                    return values[field]
        return None


class AdvertisingModelAdapter:
    """Translate the advertising model contract into standard Tool Calls.

    Application policy and turn preparation are delegated to
    ``AdvertisingTurnHandler``. The generic Harness still owns Tool scheduling,
    dependency resolution, transcript persistence, and Run lifecycle.
    """

    STATE_CONTEXT_KEY = "_agent_application_state"
    STATE_SCHEMA_VERSION = 1

    def __init__(self, owner: Any) -> None:
        self.owner = owner
        self._results = AdvertisingResultAssembler(owner)
        self._planner = AdvertisingTurnPlanner(owner)
        self._investigator = ReadOnlyInvestigationPlanner(
            owner,
            turn_planner=self._planner,
        )
        self._turn_handler = AdvertisingTurnHandler(
            owner,
            self._planner,
            self._investigator,
        )

    def complete(
        self,
        messages: list[AgentMessage],
        _tools: list[Any],
        request: Any,
    ) -> ModelTurn:
        state = self._restore_state(request)
        with capture_llm_usage() as usage_collector:
            result = self._complete(messages, _tools, request, state)
        context_updates = dict(result.context_updates or {})
        if state:
            context_updates[self.STATE_CONTEXT_KEY] = self._serialize_state(state)
        usage = dict(result.usage or {})
        for key, value in usage_collector.snapshot().items():
            if value:
                usage[key] = int(usage.get(key, 0) or 0) + int(value)
        if not usage and context_updates == dict(result.context_updates or {}):
            return result
        return ModelTurn(
            content=result.content,
            tool_calls=result.tool_calls,
            stop_reason=result.stop_reason,
            usage=usage,
            context_updates=context_updates,
        )

    def _restore_state(self, request: Any) -> dict[str, Any]:
        context = request.context if isinstance(request.context, Mapping) else {}
        payload = context.get(self.STATE_CONTEXT_KEY)
        if not isinstance(payload, Mapping):
            return {}
        if payload.get("schema_version") != self.STATE_SCHEMA_VERSION:
            return {}
        state = {
            key: value
            for key, value in payload.items()
            if key != "schema_version"
        }
        raw_intent = state.get("intent")
        if isinstance(raw_intent, Mapping):
            state["intent"] = ParsedIntent(**dict(raw_intent))
        raw_calls = state.get("calls")
        if isinstance(raw_calls, list):
            state["calls"] = tuple(
                ToolCall(
                    id=str(item.get("id") or ""),
                    name=str(item.get("name") or ""),
                    arguments=dict(item.get("arguments") or {}),
                    depends_on=tuple(item.get("depends_on") or ()),
                    argument_bindings=tuple(
                        ToolArgumentBinding(**binding)
                        for binding in item.get("argument_bindings") or ()
                        if isinstance(binding, Mapping)
                    ),
                )
                for item in raw_calls
                if isinstance(item, Mapping)
            )
        state["session"] = self.owner._sessions.get(
            str(request.session_id or "")
        )
        return state

    def _serialize_state(self, state: Mapping[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {"schema_version": self.STATE_SCHEMA_VERSION}
        for key, value in state.items():
            if key == "session":
                continue
            if key == "intent":
                value = value.to_dict() if callable(
                    getattr(value, "to_dict", None)
                ) else value
            elif key == "calls":
                value = [
                    item.to_dict() if callable(getattr(item, "to_dict", None))
                    else dict(item)
                    for item in value or ()
                ]
            payload[key] = value
        return payload

    def _complete(
        self,
        messages: list[AgentMessage],
        _tools: list[Any],
        request: Any,
        state: dict[str, Any],
    ) -> ModelTurn:
        current_user_index = max(
            (
                index for index, item in enumerate(messages)
                if item.role == "user"
            ),
            default=-1,
        )
        current = messages[current_user_index + 1:]
        tool_messages = [
            item for item in current
            if item.role == "tool"
        ]
        if not tool_messages:
            return self._start_turn(state, request)
        calls = state.get("calls", ())
        follow_up_turn = self._continue_with_investigation(
            state,
            calls,
            tool_messages,
        )
        if follow_up_turn is not None:
            return follow_up_turn
        return self._results.finish_turn(state, request, tool_messages)

    def _continue_with_investigation(
        self,
        state: dict[str, Any],
        calls: tuple[ToolCall, ...],
        tool_messages: list[AgentMessage],
    ) -> ModelTurn | None:
        if not state.get("investigation_enabled") or not tool_messages:
            return None
        steps = int(state.get("investigation_steps", 0))
        if steps >= self._investigator.MAX_STEPS:
            state["investigation_enabled"] = False
            return None
        try:
            follow_up = self._investigator.plan(
                intent=state.get("intent"),
                session_context=getattr(state.get("session"), "ctx", None),
                prior_results=self._results._results_from_messages(tool_messages),
                already_called={
                    str(item.name or "")
                    for item in tool_messages
                    if item.name
                },
            )
        except Exception as error:
            logger.debug(
                "只读补充取证失败，采用当前证据: %s",
                type(error).__name__,
            )
            follow_up = []
        state["investigation_steps"] = steps + 1
        if not follow_up:
            state["investigation_enabled"] = False
            return None
        return self._append_follow_up_call(
            state,
            calls,
            tool_messages,
            follow_up[0],
        )

    def _append_follow_up_call(
        self,
        state: dict[str, Any],
        calls: tuple[ToolCall, ...],
        tool_messages: list[AgentMessage],
        planned_call: ToolCall,
    ) -> ModelTurn | None:
        try:
            definition, _handler = self.owner.registry.get(planned_call.name)
        except KeyError:
            state["investigation_enabled"] = False
            return None
        call = planned_call
        state["calls"] = tuple(calls) + (call,)
        namespace = str(definition.namespace)
        state.setdefault("tool_plan", {}).setdefault(namespace, []).append(call.name)
        return ModelTurn(tool_calls=(call,), stop_reason="tool_call")

    def _start_turn(self, state: dict[str, Any], request: Any) -> ModelTurn:
        return self._turn_handler.start_turn(state, request)

    def on_run_end(
        self,
        request: Any,
        _model_turn: ModelTurn,
        tool_results: tuple[dict[str, Any], ...],
        _agent_state: Any,
    ) -> Mapping[str, Any]:
        """Finalize application data when Harness stops on a Tool gate."""
        state = self._restore_state(request)
        if not tool_results:
            return self._results.export_application_state(state) if state else {}
        return self._results.finish_policy_blocked_run(request, tool_results, state)

__all__ = [
    "AdvertisingContextProvider",
    "AdvertisingModelAdapter",
    "AdvertisingToolCatalog",
    "AdvertisingToolExecutor",
    "advertising_skill_source",
    "advertising_tool_source",
]
