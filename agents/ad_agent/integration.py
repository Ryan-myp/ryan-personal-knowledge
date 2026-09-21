"""Adapters that let advertising Skills/Tools plug into any Agent Harness."""

from __future__ import annotations

from typing import Any, Mapping

from agents.agent_harness import (
    AgentMessage,
    ContextProvider,
    ModelTurn,
    MarkdownSkillDirectorySource,
    StaticToolSource,
    ToolCall,
    ToolCatalog,
    ToolBinding,
)
from .core.interfaces import ParsedIntent, ToolContext, ToolResult
from .domain.ad.auth import RequestPrincipal
from .core.execution_plan import ExecutionPlan
from .runtime.ad_turn_context import AdTurnContextService


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

    def _account_from_platform_params(self, request_context: Mapping[str, Any]) -> Any:
        values_by_platform = request_context.get("platform_params")
        if not isinstance(values_by_platform, Mapping):
            return None
        for definition in self.owner.registry.list_all():
            namespace = str(getattr(definition, "namespace", "") or "")
            values = next(
                (
                    candidate
                    for key, candidate in values_by_platform.items()
                    if self.owner._canonical_platform(str(key)) ==
                    self.owner._canonical_platform(namespace)
                ),
                None,
            )
            if not isinstance(values, Mapping):
                continue
            fields = tuple(getattr(definition, "scope_fields", ()) or ())
            for field in fields or ("account_id", "ad_account_id", "advertiser_id", "customer_id"):
                if values.get(field) not in (None, ""):
                    return values[field]
        return None

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
        Path(__file__).resolve().parent / "skills",
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
            scope=dict(request_context),
            credentials=request_context.get("credentials"),
            metadata={
                "execution_mode": str(request.execution_mode or "dry_run"),
                "run_id": str(request.run_id or ""),
                "turn_id": str(request.turn_id or ""),
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
        session = self.owner._sessions.get(str(request.session_id or ""))
        if session is None:
            session = self.owner._ensure_session(
                str(request.session_id or ""),
                request.user_id,
                request_context.get("account_id"),
                request_context.get("credentials"),
                tenant_id=request.tenant_id,
            )
        account_id = (
            self._find_request_scope(request_context)
            or request_context.get("account_id")
            or self._find_scope_value(input_data)
            or getattr(session.ctx, "account_id", None)
        )
        original_account = session.ctx.account_id
        session.ctx.account_id = account_id
        try:
            if (
                getattr(self.definition, "is_write_tool", False)
                and str(request.execution_mode or "dry_run") == "dry_run"
            ):
                result = self.owner._simulate_write(
                    self.definition,
                    dict(input_data),
                    str(getattr(self.definition, "namespace", "") or ""),
                )
            else:
                clients = self.owner._build_request_clients(
                    request_context.get("credentials")
                )
                reservation = None
                if (
                    self.definition.is_write_tool
                    and str(request.execution_mode or "dry_run").lower() == "live"
                    and self.owner.write_guard is not None
                ):
                    reserve_record = getattr(
                        self.owner.write_guard, "reserve_write_record", None
                    )
                    if callable(reserve_record):
                        allowed, reason, reservation = reserve_record(
                            session.ctx, self.definition, dict(input_data)
                        )
                    else:
                        allowed, reason = self.owner.write_guard.reserve_write(
                            session.ctx, self.definition, dict(input_data)
                        )
                    if not allowed:
                        return {
                            "success": False,
                            "error": f"Write guard blocked: {reason}",
                            "data": {"execution_status": "duplicate"},
                        }
                result = self.owner.tool_executor.execute(
                    session.ctx,
                    self.definition.name,
                    dict(input_data),
                    clients,
                )
                result = self.owner.input_builder.decorate_lookup_result(
                    self.definition,
                    result,
                    session.ctx,
                    str(getattr(self.definition, "namespace", "") or ""),
                )
                if (
                    self.definition.is_write_tool
                    and str(request.execution_mode or "dry_run").lower() == "live"
                    and self.owner.write_guard is not None
                    and self.owner.security.is_uncertain_provider_failure(
                        self.definition, result
                    )
                    and isinstance(result.data, dict)
                ):
                    result.data = {
                        **result.data,
                        "execution_status": "unknown",
                        "requires_reconciliation": True,
                        "effect_state": "unknown",
                    }
                if (
                    self.definition.is_write_tool
                    and str(request.execution_mode or "dry_run").lower() == "live"
                    and self.owner.write_guard is not None
                ):
                    if reservation is not None and hasattr(
                        self.owner.write_guard, "finalize"
                    ):
                        self.owner.write_guard.finalize(reservation, result)
                    elif result.success and not result.simulated:
                        self.owner.write_guard.mark_executed(
                            self.definition.name,
                            dict(input_data),
                            session.ctx.user_id,
                        )
                    elif (
                        not result.success
                        and not self.owner.security.is_uncertain_provider_failure(
                            self.definition, result
                        )
                    ):
                        self.owner.write_guard.release_write(
                            self.definition.name,
                            dict(input_data),
                            session.ctx.user_id,
                        )
                if (
                    result.success
                    and request_context.get("confirmed")
                    and isinstance(request_context.get("confirmation_payload"), Mapping)
                ):
                    payload = request_context["confirmation_payload"]
                    expected = self.owner.security.confirmation_plan(
                        str(request.session_id or ""),
                        str(request.user_id or "anonymous"),
                        str(account_id or ""),
                        self.definition,
                        dict(input_data),
                        preview={
                            "tool": self.definition.name,
                            "input": dict(input_data),
                        },
                    )
                    if self.owner._session_manager is not None:
                        self.owner._session_manager.consume_approval(
                            expected["plan_fingerprint"],
                            expected["confirmation_token"],
                        )
            if not isinstance(result, ToolResult):
                result = ToolResult.error(
                    f"Tool '{self.definition.name}' returned an invalid result"
                )
            result = self.owner.security.normalize_read_result_evidence(
                self.definition, result
            )
            result = self.owner.security.enforce_result_limit(
                result, self.definition
            )
            safe = self.owner.security.sanitize_result(result)
            session.save_result(
                self.definition.name,
                safe,
                platform=getattr(self.definition, "namespace", ""),
            )
            return safe.to_dict()
        finally:
            session.ctx.account_id = original_account

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

    The outer loop is the generic Harness Agent.  This adapter only bridges
    the provider-neutral LLM client already used by the advertising Skills to
    the Harness ``ModelTurn`` contract; it does not execute Tools or own Run
    lifecycle.
    """

    def __init__(self, owner: Any) -> None:
        self.owner = owner
        self._turns: dict[str, dict[str, Any]] = {}
        self._completed: dict[str, dict[str, Any]] = {}

    def take_completed(self, run_id: str) -> dict[str, Any]:
        return self._completed.pop(str(run_id or ""), {})

    def complete(
        self,
        messages: list[AgentMessage],
        _tools: list[Any],
        request: Any,
    ) -> ModelTurn:
        run_id = str(request.run_id or "")
        current_user_index = max(
            (
                index for index, item in enumerate(messages)
                if item.role == "user"
            ),
            default=-1,
        )
        current = messages[current_user_index + 1:]
        state = self._turns.setdefault(run_id, {})
        tool_messages = [
            item for item in current
            if item.role == "tool"
        ]
        if not tool_messages:
            return self._start_turn(state, request)
        calls = state.get("calls", ())
        next_index = int(state.get("next_index", 0))
        if next_index < len(calls):
            state["next_index"] = next_index + 1
            call = self._hydrate_dependency_call(
                calls[next_index], tool_messages,
            )
            return ModelTurn(
                tool_calls=(call,),
                stop_reason="tool_call",
            )
        return self._finish_turn(state, request, tool_messages)

    def _start_turn(self, state: dict[str, Any], request: Any) -> ModelTurn:
        run_id = str(request.run_id or "")
        request_context = (
            request.context if isinstance(request.context, Mapping) else {}
        )
        session = self.owner._sessions.get(str(request.session_id or ""))
        if session is None:
            session = self.owner._ensure_session(
                str(request.session_id or ""),
                request.user_id,
                request_context.get("account_id"),
                request_context.get("credentials"),
                tenant_id=request.tenant_id,
            )
        ad_context = ToolContext(
            session_id=str(request.session_id or ""),
            user_id=str(request.user_id or "anonymous"),
            scope=dict(request_context),
            credentials=request_context.get("credentials"),
            protected_state=session.protected_state,
            metadata={
                "execution_mode": str(request.execution_mode or "dry_run"),
                "run_id": str(request.run_id or ""),
                "turn_id": str(request.turn_id or ""),
                "skill_context": (
                    dict(request_context.get("agent_context", {}).get("skill_context", {}))
                    if isinstance(request_context.get("agent_context"), Mapping)
                    and isinstance(
                        request_context.get("agent_context", {}).get("skill_context"),
                        Mapping,
                    )
                    else {}
                ),
            },
        )
        try:
            safe_input = self.owner._redact_for_persistence(request.user_input)
            text_protected = self.owner.security.validate_text_redline(
                request.user_input
            )
            if text_protected:
                error = (
                    "请求包含禁止传入的凭证/账户配置字段："
                    + ", ".join(text_protected)
                )
                state.update({
                    "intent": None,
                    "calls": (),
                    "next_index": 0,
                    "session": session,
                    "policy_errors": [error],
                    "last_results": [],
                    "last_reply": f"❌ 参数契约阻止本次请求：{error}",
                    "response_source": "policy",
                    "ui": {},
                })
                self._completed[run_id] = dict(state)
                self._turns.pop(run_id, None)
                return ModelTurn(
                    content=state["last_reply"],
                    stop_reason="policy_blocked",
                )
            platform_params = request_context.get("platform_params")
            input_error = self.owner._validate_request_limits(
                safe_input, platform_params,
            )
            if input_error:
                state.update({
                    "intent": None,
                    "calls": (),
                    "next_index": 0,
                    "session": session,
                    "policy_errors": [input_error],
                    "last_results": [],
                    "last_reply": f"❌ {input_error}",
                    "ui": {},
                })
                self._completed[run_id] = dict(state)
                self._turns.pop(run_id, None)
                return ModelTurn(
                    content=f"❌ {input_error}",
                    stop_reason="policy_blocked",
                )
            intent = self.owner.intent_parser.parse(safe_input, ad_context)
            if (
                request_context.get("creation_blueprint_id")
                and getattr(intent, "intent_type", "") == "chat"
            ):
                intent = ParsedIntent(
                    "create_campaign",
                    intent.raw_input,
                    list(getattr(intent, "namespaces", []) or []),
                    attributes=dict(getattr(intent, "attributes", {}) or {}),
                    parameters=dict(getattr(intent, "parameters", {}) or {}),
                    scoped_parameters=dict(
                        getattr(intent, "scoped_parameters", {}) or {}
                    ),
                    metadata=dict(getattr(intent, "metadata", {}) or {}),
                )
            if isinstance(platform_params, Mapping):
                protected = self.owner.security.validate_input_redline(platform_params)
                if protected:
                    error = "请求包含禁止传入的凭证/账户配置字段：" + ", ".join(protected)
                    state.update({
                        "intent": None,
                        "calls": (),
                        "next_index": 0,
                        "session": session,
                        "policy_errors": [error],
                        "last_results": [],
                        "last_reply": f"❌ {error}",
                        "ui": {},
                    })
                    self._completed[run_id] = dict(state)
                    self._turns.pop(run_id, None)
                    return ModelTurn(content=f"❌ {error}", stop_reason="policy_blocked")
                merged = dict(getattr(intent, "scoped_parameters", {}) or {})
                for platform, values in platform_params.items():
                    canonical = self.owner._resolve_platform_identifier(platform)
                    target = next(
                        (
                            existing for existing in merged
                            if self.owner._resolve_platform_identifier(existing) == canonical
                        ),
                        canonical or str(platform),
                    )
                    if isinstance(values, Mapping) and isinstance(merged.get(target), Mapping):
                        merged[target] = {**dict(merged[target]), **dict(values)}
                    else:
                        merged[target] = dict(values) if isinstance(values, Mapping) else values
                intent.scoped_parameters = merged
                if len(platform_params) > 1:
                    known = {
                        self.owner._canonical_platform(item)
                        for item in (getattr(intent, "namespaces", []) or [])
                    }
                    for platform in platform_params:
                        canonical = self.owner._resolve_platform_identifier(str(platform))
                        if canonical not in known:
                            intent.namespaces.append(canonical)
                            known.add(canonical)
            for feature in self.owner.features:
                adopt_pending = getattr(feature, "adopt_pending_intent", None)
                if not callable(adopt_pending):
                    continue
                try:
                    adopted = adopt_pending(
                        self.owner.services,
                        intent,
                        session_id=str(request.session_id or ""),
                    )
                    if adopted is not None:
                        intent = adopted
                except Exception:
                    continue
            if not request_context.get("creation_blueprint_id"):
                intent = self.owner._adopt_creation_draft(
                    str(request.session_id or ""), intent, safe_input,
                )
                intent = self.owner._adopt_action_draft(
                    str(request.session_id or ""), intent, safe_input,
                )
            control_feature = self.owner._feature_for_intent(intent)
            control_handler = getattr(control_feature, "handle_turn", None)
            if callable(control_handler):
                principal = request.principal or RequestPrincipal(
                    user_id=str(request.user_id or "anonymous"),
                    tenant_id=str(request.tenant_id or "default"),
                    permissions=frozenset(self.owner._granted_permissions),
                    account_scope={},
                )
                control_result = control_handler(
                    self.owner.services,
                    intent,
                    session_id=str(request.session_id or ""),
                    user_id=str(request.user_id or "anonymous"),
                    tenant_id=str(request.tenant_id or "default"),
                    account_id=request_context.get("account_id"),
                    platform_params=platform_params,
                    principal=principal,
                )
                result = {
                    "success": bool(control_result.get("success")),
                    **{
                        key: value
                        for key, value in control_result.items()
                        if key != "reply"
                    },
                }
                needs_input = bool(control_result.get("needs_input"))
                state.update({
                    "intent": intent,
                    "calls": (),
                    "next_index": 0,
                    "session": session,
                    "last_results": [result],
                    "last_reply": str(control_result.get("reply") or "已处理。"),
                    "needs_input": needs_input,
                    "needs_confirmation": bool(
                        control_result.get("needs_confirmation")
                    ),
                    "response_source": "schedule",
                    "workflow_id": None,
                    "ui": {"type": "schedule", **control_result},
                })
                self._completed[run_id] = dict(state)
                self._turns.pop(run_id, None)
                return ModelTurn(
                    content=state["last_reply"],
                    stop_reason="awaiting_input" if needs_input else "stop",
                    context_updates={},
                )
            self.owner._load_required_skills(intent.namespaces)
            routed = self.owner.intent_router.route(intent, self.owner.registry)
            policy_errors = self.owner._validate_policies(intent)
            if policy_errors:
                reply = "❌ 业务策略阻止本次请求：" + "；".join(policy_errors)
                state.update({
                    "intent": intent,
                    "calls": (),
                    "next_index": 0,
                    "session": session,
                    "policy_errors": list(policy_errors),
                    "last_results": [],
                    "last_reply": reply,
                    "ui": {},
                })
                run_key = str(request.run_id or "")
                self._completed[run_key] = dict(state)
                self._turns.pop(run_key, None)
                return ModelTurn(content=reply, stop_reason="policy_blocked")
            repair = getattr(self.owner.intent_parser, "repair_for_routing", None)
            for _attempt in range(2):
                requested = {
                    self.owner._canonical_platform(item)
                    for item in (getattr(intent, "namespaces", []) or [])
                }
                routed_platforms = {
                    self.owner._canonical_platform(item) for item in routed
                }
                if routed and (not requested or routed_platforms == requested):
                    break
                if not callable(repair):
                    break
                repaired = repair(safe_input, session.ctx, intent)
                if repaired is None:
                    break
                intent = repaired
                self.owner._load_required_skills(intent.namespaces)
                routed = self.owner.intent_router.route(intent, self.owner.registry)
            if isinstance(request.context, dict) and request.context.get("account_id") in (None, ""):
                context_updates: dict[str, Any] = {}
                for definitions in routed.values():
                    if any(getattr(item, "is_write_tool", False) for item in definitions):
                        break
                    accounts = self.owner._available_accounts_for_request(
                        definitions[0].namespace if definitions else "",
                        getattr(request.principal, "account_scope", None),
                    ) if definitions else []
                    if len(accounts) == 1:
                        request.context["account_id"] = accounts[0]
                        context_updates["account_id"] = accounts[0]
                        session.ctx.account_id = accounts[0]
                        break
                    if len(accounts) > 1:
                        state.update({
                            "intent": intent,
                            "calls": (),
                            "next_index": 0,
                            "session": session,
                            "last_results": [{
                                "success": False,
                                "data": {},
                                "needs_confirmation": True,
                                "confirmation_payload": {
                                    "type": "ask_account",
                                    "platform": definitions[0].namespace,
                                    "question": "请提供要操作的广告账户 ID。",
                                },
                            }],
                        })
                        run_key = str(request.run_id or "")
                        self._completed[run_key] = dict(state)
                        self._turns.pop(run_key, None)
                        return ModelTurn(
                            content="请提供要操作的广告账户 ID。",
                            stop_reason="awaiting_input",
                        )
            else:
                context_updates = {}
            skill_context = session.ctx.metadata.get("skill_context", {})
            state["tool_selection"] = {
                "knowledge": list(skill_context.get("knowledge") or [])
                if isinstance(skill_context, Mapping) else [],
                "tools": list(skill_context.get("selected_tools") or [])
                if isinstance(skill_context, Mapping) else [],
            }
            state["memory"] = list(skill_context.get("memory") or []) if isinstance(
                skill_context, Mapping
            ) else []
            state["memory_updates"] = list(
                session.ctx.metadata.get("memory_updates") or []
            )
            feature = self.owner._feature_for_intent(intent)
            if feature is not None and callable(
                getattr(feature, "is_batch_intent", None)
            ) and feature.is_batch_intent(intent):
                workflow_id = self.owner.workflow.start(
                    session,
                    intent,
                    routed,
                    register_items=False,
                    execution_plan=ExecutionPlan.from_tool_plan(
                        intent,
                        routed,
                        canonicalize=self.owner._canonical_platform,
                    ),
                )
                self.owner._bind_execution_run_workflow(run_id, workflow_id)
                batch = feature.run_batch_plan(
                    services=self.owner.services,
                    user_input=safe_input,
                    session=session,
                    turn_id=str(request.turn_id or ""),
                    intent=intent,
                    tool_plan=routed,
                    account_id=(
                        request.context.get("account_id")
                        if isinstance(request.context, Mapping) else None
                    ),
                    workflow_id=workflow_id,
                    account_scope=getattr(
                        request.principal, "account_scope", None
                    ),
                    granted_permissions=self.owner._granted_permissions,
                )
                state.update({
                    "intent": intent,
                    "calls": (),
                    "next_index": 0,
                    "session": session,
                    "last_results": list(batch.get("results") or []),
                    "last_reply": str(batch.get("reply") or ""),
                    "workflow_id": batch.get("workflow_id") or workflow_id,
                    "tool_plan": batch.get("tool_plan") or {},
                    "execution_plan": {},
                    "needs_confirmation": bool(batch.get("needs_confirmation")),
                    "confirmation_payload": batch.get("confirmation_payload"),
                })
                self._completed[run_id] = dict(state)
                self._turns.pop(run_id, None)
                return ModelTurn(
                    content=state["last_reply"],
                    stop_reason=(
                        "awaiting_input"
                        if batch.get("needs_confirmation") else "stop"
                    ),
                    context_updates=context_updates,
                )
            explicit_account = (
                request_context.get("account_id")
                if isinstance(request_context, Mapping) else None
            )
            principal_scope = getattr(
                request.principal, "account_scope", None,
            )
            if explicit_account and principal_scope is not None:
                denied = None
                for definitions in routed.values():
                    for definition in definitions:
                        if not getattr(definition, "is_write_tool", False):
                            continue
                        allowed, message = self.owner._validate_account_with_principal(
                            self.owner._canonical_platform(
                                str(getattr(definition, "namespace", "") or "")
                            ),
                            str(explicit_account),
                            True,
                            principal_scope,
                        )
                        if not allowed:
                            denied = str(message)
                            break
                    if denied:
                        break
                if denied:
                    state.update({
                        "intent": intent,
                        "calls": (),
                        "next_index": 0,
                        "session": session,
                        "policy_errors": [denied],
                        "last_results": [],
                        "last_reply": f"❌ {denied}",
                        "ui": {},
                    })
                    self._completed[run_id] = dict(state)
                    self._turns.pop(run_id, None)
                    return ModelTurn(
                        content=state["last_reply"],
                        stop_reason="policy_blocked",
                        context_updates=context_updates,
                    )
            creation_ui = {}
            if self.owner.creation_card_builder.is_creation_intent(intent):
                creation_ui = self.owner.build_creation_ui(
                    intent, tool_plan=routed
                ) or {}
            if (
                self.owner.creation_card_builder.is_creation_intent(intent)
                and not request_context.get("creation_blueprint_id")
            ):
                creation_ui = self.owner.build_creation_ui(intent) or {}
                cards = creation_ui.get("cards") if isinstance(
                    creation_ui.get("cards"), list
                ) else []
                selector_cards = [
                    card for card in cards
                    if isinstance(card, Mapping)
                    and card.get("type") == "ad_creation_selector"
                ]
                if selector_cards:
                    clarification = self.owner.creation_card_builder.build_clarification(
                        intent
                    )
                    clarification_ui = {
                        "schema_version": "1.0",
                        "needs_input": True,
                        "cards": [],
                        "clarification": clarification,
                    }
                    self.owner.set_creation_draft(
                        str(request.session_id or ""),
                        {"intent": intent.to_dict(), "reason": "creation_selector_required"},
                    )
                    state.update({
                        "intent": intent,
                        "calls": (),
                        "next_index": 0,
                        "session": session,
                        "last_results": [],
                        "tool_plan": {},
                        "execution_plan": {},
                        "tool_selection": None,
                        "ui": clarification_ui,
                        "workflow_id": None,
                        "response_source": "creation_clarification",
                        "needs_input": True,
                        "last_reply": self.owner.creation_ui_reply(
                            clarification_ui, safe_input
                        ),
                    })
                    self._completed[run_id] = dict(state)
                    self._turns.pop(run_id, None)
                    return ModelTurn(
                        content=state["last_reply"],
                        stop_reason="awaiting_input",
                        context_updates=context_updates,
                    )
                creation_incomplete = bool(creation_ui.get("needs_input")) or any(
                    isinstance(card, Mapping)
                    and (
                        card.get("ready") is False
                        or (
                            card.get("account_required")
                            and not str(card.get("account_id") or "").strip()
                        )
                    )
                    for card in cards
                )
                if creation_incomplete:
                    state.update({
                        "intent": intent,
                        "calls": (),
                        "next_index": 0,
                        "session": session,
                        "last_results": [],
                        "ui": {
                            **creation_ui,
                            "clarification": (
                                (creation_ui.get("cards") or [creation_ui])[0]
                            ),
                        },
                        "workflow_id": None,
                        "response_source": "creation_card",
                        "needs_input": True,
                        "last_reply": self.owner.creation_ui_reply(
                            creation_ui, safe_input
                        ),
                    })
                    self.owner.set_creation_draft(
                        str(request.session_id or ""),
                        {"intent": intent.to_dict(), "reason": "creation_parameters_required"},
                    )
                    self._completed[run_id] = dict(state)
                    self._turns.pop(run_id, None)
                    return ModelTurn(
                        content=state["last_reply"],
                        stop_reason="awaiting_input",
                        context_updates=context_updates,
                    )
            calls: list[ToolCall] = []
            for tools in routed.values():
                for definition in tools:
                    arguments = self.owner.input_builder.build(
                        definition, intent, definition.namespace, session.ctx
                    )
                    scoped = getattr(intent, "scoped_parameters", {}) or {}
                    platform_values = None
                    for key, values in (
                        scoped.items() if isinstance(scoped, Mapping) else ()
                    ):
                        if self.owner._resolve_platform_identifier(str(key)) == (
                            self.owner._resolve_platform_identifier(
                                str(definition.namespace)
                            )
                        ) and isinstance(values, Mapping):
                            platform_values = values
                            break
                    if isinstance(platform_values, Mapping):
                        properties = getattr(
                            getattr(definition, "input_schema", None),
                            "properties",
                            {},
                        ) or {}
                        for field in (
                            getattr(definition, "scope_fields", ()) or (
                                "account_id", "ad_account_id",
                                "advertiser_id", "customer_id",
                            )
                        ):
                            if (
                                field in properties
                                and platform_values.get(field) not in (None, "")
                            ):
                                arguments[field] = platform_values[field]
                    for key in (
                        "_missing_params", "_unknown_params",
                        "_selection_errors",
                    ):
                        arguments.pop(key, None)
                    calls.append(ToolCall(
                        id=f"call-{len(calls) + 1}",
                        name=definition.name,
                        arguments=arguments,
                    ))
            state.update({
                "intent": intent,
                "calls": tuple(calls),
                "next_index": 0,
                "session": session,
                "ui": creation_ui,
                "workflow_id": None,
                "tool_plan": {
                    str(platform): [item.name for item in definitions]
                    for platform, definitions in routed.items()
                },
                "execution_plan": {},
            })
            if (
                routed
                and not self.owner.creation_card_builder.is_creation_intent(intent)
                and not request_context.get("creation_blueprint_id")
                and not (
                    self.owner._feature_for_intent(intent)
                    and callable(
                        getattr(self.owner._feature_for_intent(intent), "is_batch_intent", None)
                    )
                    and self.owner._feature_for_intent(intent).is_batch_intent(intent)
                )
            ):
                account_by_platform: dict[str, Any] = {}
                for platform, definitions in routed.items():
                    has_write = any(
                        getattr(item, "is_write_tool", False)
                        for item in definitions
                    )
                    account_by_platform[
                        self.owner._canonical_platform(platform)
                    ] = self.owner.account_resolver.resolve(
                        intent,
                        platform,
                        list(definitions),
                        request_context.get("account_id"),
                        allow_automatic_account=not has_write,
                    )
                clarification = self.owner.action_clarification_builder.build(
                    intent,
                    routed,
                    self.owner.input_builder,
                    session.ctx,
                    account_by_platform=account_by_platform,
                )
                if clarification:
                    clarification_fields = clarification.get("fields") or []
                    account_fields = [
                        item for item in clarification_fields
                        if isinstance(item, Mapping)
                        and str(item.get("path") or "") in {
                            "account_id", "advertiser_id", "customer_id",
                        }
                    ]
                    non_account_fields = [
                        item for item in clarification_fields
                        if item not in account_fields
                    ]
                    confirmation_payload = None
                    response_results: list[dict[str, Any]] = []
                    reply = self.owner.action_clarification_reply(
                        {
                            "clarification": clarification,
                            "cards": [],
                            "needs_input": True,
                        },
                        safe_input,
                    )
                    if account_fields and not non_account_fields:
                        account_field = account_fields[0]
                        platform = str(
                            account_field.get("platform")
                            or next(iter(routed), "target")
                        )
                        confirmation_payload = {
                            "type": "ask_account",
                            "platform": platform,
                            "question": f"请提供要操作的 {platform} 广告账户 ID。",
                        }
                        reply = confirmation_payload["question"]
                        response_results.append({
                            "tool": str(
                                account_field.get("tool") or "account_scope"
                            ),
                            "platform": platform,
                            "success": False,
                            "data": {},
                            "error": "缺少账户ID",
                            "needs_confirmation": True,
                            "confirmation_payload": confirmation_payload,
                        })
                    clarification_ui = {
                        "schema_version": "1.0",
                        "needs_input": True,
                        "cards": [],
                        "clarification": clarification,
                    }
                    self.owner.set_action_draft(
                        str(request.session_id or ""),
                        {
                            "intent": intent.to_dict(),
                            "clarification": clarification,
                        },
                    )
                    state.update({
                        "intent": intent,
                        "calls": (),
                        "next_index": 0,
                        "session": session,
                        "last_results": response_results,
                        "tool_plan": {},
                        "execution_plan": {},
                        "tool_selection": None,
                        "ui": clarification_ui,
                        "workflow_id": None,
                        "response_source": "action_clarification",
                        "needs_input": True,
                        "needs_confirmation": bool(confirmation_payload),
                        "confirmation_payload": confirmation_payload,
                        "last_reply": reply,
                    })
                    self._completed[run_id] = dict(state)
                    self._turns.pop(run_id, None)
                    return ModelTurn(
                        content=state["last_reply"],
                        stop_reason="awaiting_input",
                        context_updates=context_updates,
                    )
            if (
                request_context.get("creation_blueprint_id")
                and creation_ui.get("cards")
            ):
                if creation_ui.get("needs_input"):
                    reply = self.owner.creation_ui_reply(
                        creation_ui, safe_input
                    )
                    state.update({
                        "intent": intent,
                        "calls": (),
                        "next_index": 0,
                        "session": session,
                        "last_results": [],
                        "tool_plan": {},
                        "execution_plan": {},
                        "tool_selection": None,
                        "response_source": "creation_card",
                        "needs_input": True,
                        "ui": {
                            **creation_ui,
                            "clarification": (
                                (creation_ui.get("cards") or [creation_ui])[0]
                            ),
                        },
                        "workflow_id": None,
                        "last_reply": reply,
                    })
                    self.owner.set_creation_draft(
                        str(request.session_id or ""),
                        {
                            "intent": intent.to_dict(),
                            "reason": "creation_parameters_required",
                        },
                    )
                    self._completed[run_id] = dict(state)
                    self._turns.pop(run_id, None)
                    return ModelTurn(
                        content=reply,
                        stop_reason="awaiting_input",
                        context_updates=context_updates,
                    )
                issues = self.owner._creation_contract_preflight(
                    intent,
                    routed,
                    session,
                    str(
                        request_context.get("account_id")
                        or getattr(session.ctx, "account_id", "")
                        or ""
                    ),
                )
                if issues:
                    validation_ui = {
                        **creation_ui,
                        "needs_input": True,
                        "creation_validation": {
                            "status": "blocked",
                            "issues": issues,
                        },
                    }
                    reply = self.owner._creation_contract_reply(
                        validation_ui, issues
                    )
                    state.update({
                        "intent": intent,
                        "calls": (),
                        "next_index": 0,
                        "session": session,
                        "last_results": [],
                        "tool_plan": {},
                        "execution_plan": {},
                        "tool_selection": None,
                        "response_source": "creation_validation",
                        "needs_input": True,
                        "ui": validation_ui,
                        "creation_validation": {
                            "status": "blocked",
                            "issues": issues,
                        },
                        "workflow_id": None,
                        "last_reply": reply,
                    })
                    self.owner.set_creation_draft(
                        str(request.session_id or ""),
                        {"intent": intent.to_dict(), "reason": "creation_validation"},
                    )
                    self._completed[run_id] = dict(state)
                    self._turns.pop(run_id, None)
                    return ModelTurn(
                        content=reply,
                        stop_reason="awaiting_input",
                        context_updates=context_updates,
                    )
            execution_plan = ExecutionPlan.from_tool_plan(
                intent,
                routed,
                canonicalize=self.owner._canonical_platform,
            )
            workflow_id = None
            if any(
                getattr(item, "is_write_tool", False)
                for definitions in routed.values()
                for item in definitions
            ):
                workflow_id = self.owner.workflow.start(
                    session,
                    intent,
                    routed,
                    execution_plan=execution_plan,
                )
                self.owner._bind_execution_run_workflow(run_id, workflow_id)
            state["workflow_id"] = workflow_id
            state["execution_plan"] = execution_plan.to_dict()
            if not calls:
                reply = self.owner.response_renderer.render_chat(
                    request.user_input
                )
                state["last_results"] = []
                state["last_reply"] = reply
                state["ui"] = {}
                state["response_source"] = "chat"
                run_key = str(request.run_id or "")
                self._completed[run_key] = dict(state)
                self._turns.pop(run_key, None)
                return ModelTurn(
                    content=reply,
                    stop_reason="stop",
                    context_updates=context_updates,
                )
            state["next_index"] = 1
            return ModelTurn(
                tool_calls=(calls[0],),
                stop_reason="tool_call",
                context_updates=context_updates,
            )
        except Exception as error:
            state["intent"] = None
            state["reason"] = "intent_parse_failed"
            state["error_type"] = type(error).__name__
            callback = getattr(request, "event_callback", None)
            if callable(callback):
                callback({
                    "type": "stage_status",
                    "stage_id": "intent",
                    "status": "failed",
                    "error_type": type(error).__name__,
                })
            state["last_results"] = [{
                "success": False,
                "error": "暂时无法完成请求理解，请稍后重试。",
            }]
            run_key = str(request.run_id or "")
            self._completed[run_key] = dict(state)
            self._turns.pop(run_key, None)
            return ModelTurn(
                content="暂时无法完成请求理解，请稍后重试。",
                stop_reason="error",
                usage={"error_type": type(error).__name__},
            )

    def _finish_turn(
        self,
        state: dict[str, Any],
        request: Any,
        tool_messages: list[AgentMessage],
    ) -> ModelTurn:
        intent = state.get("intent")
        results: list[dict[str, Any]] = []
        for message in tool_messages:
            content = message.content
            if isinstance(content, Mapping):
                result = dict(content)
            else:
                result = {"success": False, "error": str(content)}
            if isinstance(message.metadata, Mapping):
                for key in (
                    "needs_input", "needs_confirmation", "confirmation_payload",
                ):
                    if key in message.metadata:
                        result[key] = message.metadata[key]
            result.setdefault("tool", message.name or "")
            result.setdefault("platform", getattr(
                self.owner.registry.get(message.name)[0], "namespace", ""
            ) if message.name else "")
            results.append(result)
        self._decorate_results(results)
        feature = self.owner._feature_for_intent(intent) if intent is not None else None
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
                        for platform, names in self._tool_plan_names(results).items()
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
                self._decorate_results(results)
                state["tool_plan"] = self._tool_plan_names(results)
            except Exception:
                analysis = {}
        state.update(analysis)
        if intent is None:
            reply = "工具执行完成，但无法生成结构化业务回复。"
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
        state["response_source"] = response_source if intent is not None else "renderer"
        state["needs_input"] = any(
            item.get("needs_input") or item.get("needs_confirmation")
            for item in results
        )
        state.setdefault("ui", {})
        state.setdefault("workflow_id", None)
        self._finish_workflow(state, results, intent)
        self._completed[str(request.run_id or "")] = dict(state)
        self._turns.pop(str(request.run_id or ""), None)
        return ModelTurn(
            content=reply,
            stop_reason=(
                "awaiting_input"
                if any(
                    item.get("needs_input") or item.get("needs_confirmation")
                    for item in results
                )
                else "stop"
            ),
        )

    def on_run_end(
        self,
        request: Any,
        _model_turn: ModelTurn,
        tool_results: tuple[dict[str, Any], ...],
        _agent_state: Any,
    ) -> None:
        """Finalize application results when Harness stops on a Tool gate."""
        run_id = str(request.run_id or "")
        if run_id in self._completed:
            return
        state = self._turns.get(run_id)
        if state is None:
            return
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
        self._decorate_results(results)
        state["last_results"] = results
        state["last_reply"] = (
            next(
                (
                    str(item.get("confirmation_payload", {}).get("question"))
                    for item in results
                    if isinstance(item.get("confirmation_payload"), Mapping)
                    and item["confirmation_payload"].get("question")
                ),
                "工具调用被执行策略阻断，请根据返回的提示补充信息后重试。",
            )
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
        self._finish_workflow(state, results, state.get("intent"))
        self._completed[run_id] = dict(state)
        self._turns.pop(run_id, None)

    def _finish_workflow(
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
            return

    def _decorate_results(self, results: list[dict[str, Any]]) -> None:
        for result in results:
            name = str(result.get("tool") or "")
            if not name:
                continue
            try:
                definition, _ = self.owner.registry.get(name)
            except KeyError:
                continue
            for key in (
                "action", "resource_type", "resource_id_field",
                "parent_resource_type", "parent_resource_id_field",
                "result_items_key", "result_id_fields",
                "related_resource_type", "related_resource_id_fields",
            ):
                value = getattr(definition, key, None)
                if value not in (None, "", [], ()):
                    result.setdefault(key, value)

    def _hydrate_dependency_call(
        self,
        call: ToolCall,
        tool_messages: list[AgentMessage],
    ) -> ToolCall:
        """Bind a declared parent ID from the preceding Tool result."""
        try:
            definition, _ = self.owner.registry.get(call.name)
        except KeyError:
            return call
        parent_field = str(
            getattr(definition, "parent_resource_id_field", "") or ""
        )
        parent_type = str(
            getattr(definition, "parent_resource_type", "") or ""
        )
        if not parent_field or not parent_type:
            return call
        arguments = dict(call.arguments)
        if arguments.get(parent_field) not in (None, ""):
            return call
        for message in reversed(tool_messages):
            content = message.content
            if not isinstance(content, Mapping):
                continue
            data = content.get("data")
            if not isinstance(data, Mapping) or content.get("success") is False:
                continue
            try:
                parent_definition, _ = self.owner.registry.get(message.name or "")
            except KeyError:
                continue
            if str(getattr(parent_definition, "resource_type", "") or "") != parent_type:
                continue
            resource_field = str(
                getattr(parent_definition, "resource_id_field", "") or ""
            )
            value = data.get(resource_field) if resource_field else None
            if value not in (None, ""):
                arguments[parent_field] = value
                return ToolCall(
                    id=call.id,
                    name=call.name,
                    arguments=arguments,
                )
        return call

    def _tool_plan_names(
        self, results: list[dict[str, Any]],
    ) -> dict[str, list[str]]:
        plan: dict[str, list[str]] = {}
        for result in results:
            name = str(result.get("tool") or "")
            platform = str(result.get("platform") or "")
            if name and platform:
                plan.setdefault(platform, []).append(name)
        return plan


__all__ = [
    "AdvertisingContextProvider",
    "AdvertisingModelAdapter",
    "AdvertisingToolCatalog",
    "AdvertisingToolExecutor",
    "advertising_skill_source",
    "advertising_tool_source",
]
