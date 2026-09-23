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
from .integration_result_assembler import AdvertisingResultAssembler
from .integration_turn_planner import AdvertisingTurnPlanner


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
        self._max_completed = 256
        self._results = AdvertisingResultAssembler(
            owner,
            self._turns,
            self._completed,
            max_completed=self._max_completed,
        )
        self._planner = AdvertisingTurnPlanner(owner)

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
        return self._results.finish_turn(state, request, tool_messages)

    def _start_turn(self, state: dict[str, Any], request: Any) -> ModelTurn:
        run_id = str(request.run_id or "")
        request_context = (
            dict(request.context) if isinstance(request.context, Mapping) else {}
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
                "cancellation_event": request.cancellation_event,
                "lease_lost_event": request.lease_lost_event,
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
            template_id = str(
                request_context.get("creation_template_id") or ""
            ).strip()
            if template_id:
                try:
                    intent = self.owner.apply_creation_template_to_intent(
                        intent,
                        template_id,
                        account_id=request_context.get("account_id"),
                        account_scope=getattr(
                            request.principal, "account_scope", None,
                        ),
                        tenant_id=str(request.tenant_id or "default"),
                        user_id=str(request.user_id or "anonymous"),
                    )
                except Exception as exc:
                    state.update({
                        "intent": intent,
                        "calls": (),
                        "next_index": 0,
                        "session": session,
                        "policy_errors": ["creation_template_invalid"],
                        "last_results": [],
                        "last_reply": f"❌ 无法应用创建模板：{exc}",
                        "response_source": "policy",
                        "ui": {},
                    })
                    self._completed[run_id] = dict(state)
                    self._turns.pop(run_id, None)
                    return ModelTurn(
                        content=state["last_reply"],
                        stop_reason="policy_blocked",
                    )
                template_blueprint_id = str(
                    getattr(intent, "metadata", {}).get(
                        "creation_blueprint_id", ""
                    ) or ""
                ).strip()
                requested_blueprint_id = str(
                    request_context.get("creation_blueprint_id") or ""
                ).strip()
                if (
                    requested_blueprint_id
                    and template_blueprint_id
                    and requested_blueprint_id != template_blueprint_id
                ):
                    state.update({
                        "intent": intent,
                        "calls": (),
                        "next_index": 0,
                        "session": session,
                        "policy_errors": ["creation_template_blueprint_mismatch"],
                        "last_results": [],
                        "last_reply": "❌ 创建模板与当前广告类型不一致，请重新选择模板。",
                        "response_source": "policy",
                        "ui": {},
                    })
                    self._completed[run_id] = dict(state)
                    self._turns.pop(run_id, None)
                    return ModelTurn(
                        content=state["last_reply"],
                        stop_reason="policy_blocked",
                    )
                if template_blueprint_id:
                    request_context["creation_blueprint_id"] = template_blueprint_id
                    request_context["creation_blueprint_version"] = str(
                        getattr(intent, "metadata", {}).get(
                            "creation_blueprint_version", ""
                        ) or ""
                    ) or None
                if not request_context.get("account_id"):
                    template_account_id = str(
                        getattr(intent, "metadata", {}).get(
                            "creation_template_account_id", ""
                        ) or ""
                    ).strip()
                    if template_account_id:
                        request_context["account_id"] = template_account_id
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
                intent = self._planner.merge_platform_params(
                    intent,
                    platform_params,
                )
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
            if isinstance(request.context, dict):
                request.context["_agent_intent_namespaces"] = list(
                    getattr(intent, "namespaces", []) or []
                )
            if isinstance(request.context, dict) and request.context.get("account_id") in (None, ""):
                context_updates: dict[str, Any] = {}
                routed_platforms = {
                    self.owner._canonical_platform(platform)
                    for platform in routed
                }
                if len(routed_platforms) == 1:
                    definitions = next(iter(routed.values()), [])
                    if not any(
                        getattr(item, "is_write_tool", False)
                        for item in definitions
                    ):
                        accounts = self.owner._available_accounts_for_request(
                            definitions[0].namespace if definitions else "",
                            getattr(request.principal, "account_scope", None),
                        ) if definitions else []
                        if len(accounts) == 1:
                            request.context["account_id"] = accounts[0]
                            context_updates["account_id"] = accounts[0]
                            session.ctx.account_id = accounts[0]
                        elif len(accounts) > 1:
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
                    intent,
                    tool_plan=routed,
                    account_scope=getattr(
                        request.principal, "account_scope", None,
                    ),
                    tenant_id=str(request.tenant_id or "default"),
                    user_id=str(request.user_id or "anonymous"),
                    account_id=request_context.get("account_id"),
                ) or {}
            if (
                self.owner.creation_card_builder.is_creation_intent(intent)
                and not request_context.get("creation_blueprint_id")
            ):
                creation_ui = self.owner.build_creation_ui(
                    intent,
                    account_scope=getattr(
                        request.principal, "account_scope", None,
                    ),
                    tenant_id=str(request.tenant_id or "default"),
                    user_id=str(request.user_id or "anonymous"),
                    account_id=request_context.get("account_id"),
                ) or {}
                cards = creation_ui.get("cards") if isinstance(
                    creation_ui.get("cards"), list
                ) else []
                selector_cards = [
                    card for card in cards
                    if isinstance(card, Mapping)
                    and card.get("type") == "ad_creation_selector"
                ]
                rich_selector = any(
                    card.get("account_options") or card.get("template_options")
                    for card in selector_cards
                )
                if selector_cards and not rich_selector:
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
            turn_plan = self._planner.build_plan(
                routed,
                intent,
                session.ctx,
            )
            calls = list(turn_plan.calls)
            state.update({
                "intent": intent,
                "calls": tuple(calls),
                "next_index": 0,
                "session": session,
                "ui": creation_ui,
                "workflow_id": None,
                "tool_plan": {
                    platform: list(names)
                    for platform, names in turn_plan.tool_plan.items()
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
            execution_plan = turn_plan.execution_plan
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
        """Delegate application result assembly to its dedicated boundary."""
        return self._results.finish_turn(state, request, tool_messages)

    def on_run_end(
        self,
        request: Any,
        _model_turn: ModelTurn,
        tool_results: tuple[dict[str, Any], ...],
        _agent_state: Any,
    ) -> Mapping[str, Any]:
        """Finalize application data when Harness stops on a Tool gate."""
        return self._results.finish_policy_blocked_run(
            request,
            tool_results,
        )

    def on_run_cleanup(self, request: Any, _state: Any = None) -> None:
        """Release in-flight state even when the generic loop is interrupted."""
        run_id = str(getattr(request, "run_id", "") or "")
        self._turns.pop(run_id, None)
        self._results.prune_completed()

    def _hydrate_dependency_call(
        self,
        call: ToolCall,
        tool_messages: list[AgentMessage],
    ) -> ToolCall:
        return self._planner.hydrate_dependency_call(call, tool_messages)

__all__ = [
    "AdvertisingContextProvider",
    "AdvertisingModelAdapter",
    "AdvertisingToolCatalog",
    "AdvertisingToolExecutor",
    "advertising_skill_source",
    "advertising_tool_source",
]
