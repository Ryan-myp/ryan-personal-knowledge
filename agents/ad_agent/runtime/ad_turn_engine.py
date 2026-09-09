"""Advertising application turn engine.

The generic Runtime Kernel delegates here after it has completed request
normalization and session concurrency control. This module owns application
workflow policy, not generic Runtime infrastructure.
"""

from __future__ import annotations

import copy
import json
import logging
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Mapping, Optional

from ..domain.ad.auth import RequestPrincipal
from ..core.execution_plan import ExecutionPlan
from ..core.execution_trace import ExecutionEventCallback, ExecutionTrace
from ..core.interfaces import ExecutionMode, ToolResult
from ..core.tool_registry import validate_tool_input
from ..persistence.models import ExecutionRunRecord

logger = logging.getLogger(__name__)

def execute(
    runtime,
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
    granted_permissions: Optional[set[str] | frozenset[str]] = None,
    account_scope: Optional[Mapping[str, Any]] = None,
    tenant_id: str = "default",
    cancellation_event: Optional[threading.Event] = None,
    lease_lost_event: Optional[threading.Event] = None,
    event_callback: Optional[ExecutionEventCallback] = None,
    task_id: Optional[str] = None,
) -> dict:
    """
    执行一次完整的对话回合。

    对应 DAP Agent 的 Core Engine 主循环：
    用户输入 → 意图解析 → 工具路由 → 执行 → 返回结果

    Returns:
        {
            "session_id": str,
            "turn_id": str,
            "intent": dict,           # 解析后的意图
            "tool_calls": [...],       # 计划调用的工具
            "results": [...],          # 各工具执行结果
            "reply": str,              # 给用户的回复
            "needs_confirmation": bool, # 是否需要用户确认
        }
    """
    session_id = session_id or str(uuid.uuid4())
    turn_id = str(uuid.uuid4())[:8]
    run_id = str(uuid.uuid4())
    durable_run = bool(
        runtime._session_manager
        and callable(getattr(runtime._session_manager, "create_execution_run", None))
    )

    def observe_trace(event: dict[str, Any]) -> None:
        if durable_run:
            try:
                accepted = runtime._session_manager.append_execution_run_event(run_id, event)
                if not accepted:
                    enqueue = getattr(runtime._persistence_store, "enqueue_execution_event_repair", None)
                    if callable(enqueue):
                        enqueue(run_id, event)
            except Exception:
                # Replay persistence is important, but it must never make
                # a provider operation fail because an observer backend is
                # temporarily unavailable.
                enqueue = getattr(runtime._persistence_store, "enqueue_execution_event_repair", None)
                if callable(enqueue):
                    try:
                        enqueue(run_id, event)
                    except Exception:
                        logger.warning("failed to enqueue execution event repair", exc_info=True)
                logger.debug("failed to persist execution event", exc_info=True)
        if callable(event_callback):
            try:
                event_callback(event)
            except Exception:
                logger.debug("execution event observer failed", exc_info=True)

    if durable_run:
        try:
            runtime._session_manager.create_execution_run(
                ExecutionRunRecord(
                    run_id=run_id,
                    session_id=session_id,
                    turn_id=turn_id,
                    user_id=str(user_id),
                    tenant_id=str(tenant_id or "default"),
                    execution_mode=runtime.execution_mode,
                    task_id=str(task_id) if task_id else None,
                    metadata={
                        "effect_state": "unknown",
                        "user_input": runtime._redact_for_persistence(user_input),
                    },
                    created_at=datetime.now().isoformat(),
                    updated_at=datetime.now().isoformat(),
                )
            )
        except Exception:
            # Once a persistence backend is configured, a turn must not
            # silently become an in-memory run. That would make a live
            # provider side effect impossible to reconcile after a crash.
            logger.exception("failed to create durable Agent run")
            raise RuntimeError("durable Agent run persistence is unavailable")
    trace = ExecutionTrace(
        observe_trace if (durable_run or event_callback) else None,
        turn_id=turn_id,
        # The Core trace only knows generic credential shapes. The application
        # redactor adds the advertising domain's account/configuration policy
        # at the boundary without polluting the shared trace contract.
        redactor=runtime._redact_for_persistence,
    )
    trace.start()
    input_error = runtime._validate_request_limits(user_input, platform_params)
    if input_error:
        trace.error(reason="request_invalid")
        trace.done("failed", safe_metadata={"reason": "request_invalid"})
        return {
            "session_id": session_id,
            "run_id": run_id,
            "turn_id": turn_id,
            "timestamp": datetime.now().isoformat(),
            "intent": None,
            "tool_plan": {},
            "tool_selection": None,
            "results": [],
            "reply": f"❌ {input_error}",
            "needs_confirmation": False,
            "confirmation_payload": None,
            "policy_errors": [input_error],
        }
    # Secrets must not be sent to the LLM or retained in session history,
    # even when a caller accidentally pastes them into the chat text.
    safe_user_input = runtime._redact_for_persistence(user_input)

    # Step 1: 确保 Session 存在
    request_clients = runtime._build_request_clients(credentials)
    session = runtime._ensure_session(
        session_id, user_id, account_id, credentials, tenant_id=tenant_id
    )
    turn_deadline = time.monotonic() + runtime.turn_timeout_seconds
    session.ctx.metadata["turn_deadline"] = turn_deadline
    session.ctx.metadata["tenant_id"] = str(tenant_id or "default")
    # Make the resolved mode explicit to handlers and trace/persistence
    # adapters without exposing the mutable Runtime default.
    session.ctx.metadata["execution_mode"] = runtime.execution_mode
    # This map is scoped to one execution turn.  Provider handlers use it
    # only to bridge eventual-consistency gaps between a successful parent
    # create and its dependent child create; caller-supplied IDs still go
    # through normal account ownership checks.
    session.ctx.metadata["runtime_created_resource_ids"] = {}
    if cancellation_event is not None:
        session.ctx.metadata["task_cancel_event"] = cancellation_event
    else:
        session.ctx.metadata.pop("task_cancel_event", None)
    if lease_lost_event is not None:
        session.ctx.metadata["session_lease_lost_event"] = lease_lost_event
    else:
        session.ctx.metadata.pop("session_lease_lost_event", None)
    effective_permissions = (
        runtime._granted_permissions
        if granted_permissions is None
        else frozenset(granted_permissions)
    )

    text_protected_paths = runtime.security.validate_text_redline(user_input)
    if text_protected_paths:
        error = (
            "请求包含禁止传入的凭证/账户配置字段："
            + ", ".join(text_protected_paths)
        )
        trace.error(reason="protected_input")
        trace.done("failed", safe_metadata={"reason": "protected_input"})
        runtime.persist_conversation_turn(
            session, turn_id, safe_user_input, error, execution_trace=trace,
        )
        return {
            "session_id": session_id,
            "run_id": run_id,
            "turn_id": turn_id,
            "timestamp": datetime.now().isoformat(),
            "intent": None,
            "tool_plan": {},
            "tool_selection": None,
            "results": [],
            "reply": "❌ 参数契约阻止本次请求：" + error,
            "needs_confirmation": False,
            "confirmation_payload": None,
            "policy_errors": [error],
        }

    # Memory is an advisory context layer, never an execution source.
    # The manager only promotes explicit requests and high-confidence
    # preference statements; normal tool results and chat history remain
    # session/audit state.
    recalled_memories: list[dict[str, Any]] = []
    memory_updates: list[dict[str, Any]] = []
    memory_context = ""
    if runtime._memory_manager:
        try:
            for candidate in runtime._memory_manager.extract_candidates(safe_user_input):
                record = runtime._memory_manager.remember(
                    candidate["content"],
                    tenant_id=tenant_id,
                    user_id=user_id,
                    # Long-lived memory is user-scoped rather than tied to
                    # the current conversation session.
                    session_id=None,
                    kind=candidate.get("kind", "semantic"),
                    source=candidate.get("source", "auto_preference"),
                    importance=candidate.get("importance", 0.7),
                    confidence=candidate.get("confidence", 0.86),
                    memory_key=candidate.get("memory_key"),
                )
                memory_updates.append(record.to_context_dict())
            session.ctx.metadata["memory_updates"] = memory_updates[-20:]
            recalled_memories, memory_context = runtime._memory_manager.build_context(
                safe_user_input,
                tenant_id=tenant_id,
                user_id=user_id,
                session_id=session_id,
            )
        except Exception as exc:
            # Memory failure must never block intent parsing or tool policy.
            logger.debug("构建 Memory 上下文失败: %s", exc)

    # Step 2: 解析用户意图
    # Give an injected LLM the bounded Skill/tool context before it emits
    # an intent.  The post-parse IntentRouter remains authoritative, so
    # this context can improve recognition but cannot grant execution.
    trace.stage_status(
        "intent",
        "Intent 识别",
        "running",
        subtitle="理解用户目标与约束",
        safe_metadata={"phase": "intent_parsing"},
        safe_input={
            "request": safe_user_input,
            "request_length": len(safe_user_input),
        },
    )
    try:
        skill_context = runtime._build_skill_context(
            safe_user_input, runtime.registry.list_all(), None, tenant_id
        )
        skill_context["prior_tool_results"] = runtime._build_prior_tool_results_context(session)
        skill_context["memory"] = recalled_memories
        skill_context["memory_context"] = memory_context
        skill_context["conversation_digest"] = session.ctx.metadata.get(
            "conversation_digest", ""
        )
        session.ctx.metadata["skill_context"] = skill_context
    except Exception as exc:
        logger.debug("构建 Skill 解析上下文失败: %s", exc)
    intent = runtime.intent_parser.parse(safe_user_input, session.ctx)
    trace.stage_status(
        "intent",
        "Intent 识别",
        "succeeded",
        subtitle="已识别请求目标",
        namespace=", ".join(str(item) for item in (intent.namespaces or [])),
        safe_metadata={
            "intent_type": intent.intent_type,
            "platform_count": len(intent.namespaces or []),
        },
        safe_output={
            "intent_type": intent.intent_type,
            "platforms": list(intent.namespaces or []),
            "structured_parameters": bool(intent.scoped_parameters),
            "parameters": runtime._redact_for_persistence(intent.scoped_parameters or {}),
        },
    )
    # A credential-shaped field can arrive through the LLM/parser output
    # even when it was originally pasted in natural language.  Redaction
    # protects the value, but must not turn the request into a normal
    # creation flow.  Reject the structured intent before Skill loading,
    # account resolution, lookup planning, or Tool execution.
    parsed_protected_paths = runtime.security.validate_input_redline(
        intent.scoped_parameters or {}
    )
    if parsed_protected_paths:
        error = (
            "请求包含禁止传入的凭证/账户配置字段："
            + ", ".join(parsed_protected_paths)
        )
        trace.error(reason="protected_input")
        trace.done("failed", safe_metadata={"reason": "protected_input"})
        runtime.persist_conversation_turn(
            session, turn_id, safe_user_input, error,
            execution_trace=trace,
        )
        return {
            "session_id": session_id,
            "run_id": run_id,
            "turn_id": turn_id,
            "timestamp": datetime.now().isoformat(),
            "intent": None,
            "tool_plan": {},
            "tool_selection": None,
            "results": [],
            "reply": "❌ 参数契约阻止本次请求：" + error,
            "needs_confirmation": False,
            "confirmation_payload": None,
            "policy_errors": [error],
        }
    # A control Feature may own a durable conversational draft.  Let the
    # feature adopt a short follow-up such as “Google Ads” or “确认创建”
    # before normal routing, without teaching Runtime any schedule fields.
    for pending_feature in runtime.features:
        adopt_pending = getattr(pending_feature, "adopt_pending_intent", None)
        if not callable(adopt_pending):
            continue
        try:
            adopted = adopt_pending(runtime.services, intent, session_id=session_id)
            if adopted is not None:
                intent = adopted
        except Exception:
            logger.debug("pending feature intent adoption failed", exc_info=True)
    # Runtime control-plane Features (currently scheduling) are handled
    # through the same parsed-intent boundary but do not enter provider
    # Tool routing. Their eventual work is submitted back as agent.turn.
    control_feature = runtime._feature_for_intent(intent)
    control_handler = getattr(control_feature, "handle_turn", None)
    if callable(control_handler):
        feature_principal = RequestPrincipal(
            user_id=str(user_id), tenant_id=str(tenant_id or "default"),
            permissions=frozenset(effective_permissions),
            account_scope=account_scope or {},
        )
        try:
            control_result = control_handler(
                runtime.services, intent, session_id=session_id, user_id=str(user_id),
                tenant_id=str(tenant_id or "default"), account_id=account_id,
                platform_params=platform_params, principal=feature_principal,
            )
        except Exception as exc:
            logger.exception("Runtime control feature failed")
            control_result = {"success": False, "reply": runtime._redact_for_persistence(str(exc))}
        reply = str(control_result.get("reply") or "已处理。")
        success = bool(control_result.get("success"))
        needs_input = bool(control_result.get("needs_input"))
        trace.stage_status(
            "control_feature", "系统能力", "succeeded" if success or needs_input else "failed",
            subtitle="定时任务调度", safe_metadata={"feature": getattr(control_feature, "feature_name", "")},
            safe_output=runtime._redact_for_persistence({
                "schedule": control_result.get("schedule"),
                "schedule_count": len(control_result.get("schedules", []) or []),
            }),
        )
        trace.reply()
        trace.done("awaiting_confirmation" if needs_input else "succeeded" if success else "failed")
        runtime.persist_conversation_turn(session, turn_id, safe_user_input, reply, execution_trace=trace)
        if durable_run:
            try:
                runtime._session_manager.update_execution_run(
                    run_id, status="awaiting_confirmation" if needs_input else "succeeded" if success else "failed",
                )
            except Exception:
                logger.debug("failed to finalize control-plane execution run", exc_info=True)
        return {
            "session_id": session_id, "run_id": run_id, "turn_id": turn_id,
            "timestamp": datetime.now().isoformat(), "intent": intent.to_dict(),
            "tool_plan": {}, "execution_plan": {}, "tool_selection": None,
            "results": [{"success": success, **{key: value for key, value in control_result.items() if key != "reply"}}],
            "reply": reply, "needs_confirmation": needs_input,
            "needs_input": needs_input, "confirmation_payload": None,
            "workflow_id": None, "ui": {"type": "schedule", **control_result},
        }
    # Refresh advisory context with the parsed intent.  This changes only
    # the model-facing explanation/context; IntentRouter remains the sole
    # authority for the executable plan below.
    try:
        skill_context = runtime._build_skill_context(
            safe_user_input,
            runtime.registry.list_all(),
            intent.intent_type,
            tenant_id,
        )
        skill_context["prior_tool_results"] = runtime._build_prior_tool_results_context(session)
        skill_context["memory"] = recalled_memories
        skill_context["memory_context"] = memory_context
        skill_context["conversation_digest"] = session.ctx.metadata.get(
            "conversation_digest", ""
        )
        session.ctx.metadata["skill_context"] = skill_context
    except Exception as exc:
        logger.debug("构建意图级 Skill/知识上下文失败: %s", exc)

    # 如果提供了 platform_params（来自确认请求），合并到意图中
    if platform_params:
        protected_paths = runtime.security.validate_input_redline(platform_params)
        if protected_paths:
            error = "请求包含禁止传入的凭证/账户配置字段：" + ", ".join(protected_paths)
            trace.error(reason="protected_input")
            trace.done("failed", safe_metadata={"reason": "protected_input"})
            runtime.persist_conversation_turn(
                session, turn_id, safe_user_input, error, execution_trace=trace
            )
            return {
            "session_id": session_id,
            "run_id": run_id,
            "turn_id": turn_id,
                "timestamp": datetime.now().isoformat(),
                "intent": None,
                "tool_plan": {},
                "tool_selection": None,
                "results": [],
                "reply": f"❌ {error}",
                "needs_confirmation": False,
                "confirmation_payload": None,
                "policy_errors": [error],
            }
        merged_params = copy.deepcopy(intent.scoped_parameters or {})
        for platform, values in platform_params.items():
            canonical_platform = runtime._resolve_platform_identifier(platform)
            target_platform = next(
                (
                    existing_platform
                    for existing_platform in merged_params
                    if runtime._resolve_platform_identifier(existing_platform) == canonical_platform
                ),
                canonical_platform or str(platform),
            )
            if isinstance(values, dict) and isinstance(merged_params.get(target_platform), dict):
                merged_params[target_platform] = {
                    **(merged_params.get(target_platform) or {}),
                    **runtime._redact_for_persistence(values),
                }
            else:
                merged_params[target_platform] = runtime._redact_for_persistence(values)
        intent.scoped_parameters = merged_params

    # A creation follow-up is often intentionally short (for example
    # “流量广告” after the Agent asked for a TikTok objective). Restore
    # the durable creation intent before loading Skills or routing Tools;
    # the persisted draft is never treated as an execution permission.
    if not creation_blueprint_id:
        intent = runtime._adopt_creation_draft(
            session_id, intent, safe_user_input,
        )
    # A concise answer to a generic action clarification (for example a
    # Campaign ID after “update this campaign”) must remain attached to
    # the original action. The draft is durable session context, not an
    # execution permission.
    if not creation_blueprint_id:
        intent = runtime._adopt_action_draft(
            session_id, intent, safe_user_input,
        )

    # Step 2.5: 动态加载相关平台的 Skill 工具
    runtime._load_required_skills(intent.namespaces)

    policy_errors = runtime._validate_policies(intent)
    if policy_errors:
        reply = "❌ 业务策略阻止本次请求：" + "；".join(policy_errors)
        trace.error(reason="policy_blocked")
        trace.done("failed", safe_metadata={"reason": "policy_blocked"})
        runtime.persist_conversation_turn(
            session, turn_id, safe_user_input, reply,
            execution_trace=trace,
        )
        return {
            "session_id": session_id,
            "run_id": run_id,
            "turn_id": turn_id,
            "timestamp": datetime.now().isoformat(),
            "intent": intent.to_dict(),
            "tool_plan": {},
            "tool_selection": None,
            "results": [],
            "reply": reply,
            "needs_confirmation": False,
            "confirmation_payload": None,
            "policy_errors": policy_errors,
        }

    # Creation is a parameter-collection boundary. Resolve the
    # provider-owned Blueprint before IntentRouter materializes the
    # Campaign -> Ad Group -> Ad chain. This prevents an ambiguous request
    # or an incomplete Blueprint form from being displayed as three
    # independently pending Tool confirmations in the execution panel.
    creation_ui: dict[str, Any] = {}
    creation_requested = runtime.creation_card_builder.is_creation_intent(intent)
    # Resolve the explicit Tool route before constructing a Blueprint. A
    # Campaign-only verification Tool deliberately has no descendant
    # inputs, so expanding a full provider Blueprint here would create a
    # false blocking dependency on Ad Set/Ad/creative fields.
    campaign_only_request = runtime._is_campaign_only_plan(
        runtime.intent_router.route(intent, runtime.registry), intent
    )
    if creation_requested and not creation_blueprint_id and not campaign_only_request:
        # An explicit account is still subject to trusted principal and
        # test-account policy even when the business type is ambiguous.
        # Clarification must not become a way to probe or operate outside
        # the caller's account scope.
        for provider in list(getattr(intent, "namespaces", []) or []):
            canonical_provider = runtime._resolve_platform_identifier(provider)
            provider_values: Mapping[str, Any] = {}
            for raw_provider, values in (getattr(intent, "scoped_parameters", {}) or {}).items():
                if runtime._resolve_platform_identifier(raw_provider) == canonical_provider and isinstance(values, Mapping):
                    provider_values = values
                    break
            explicit_account = account_id
            if explicit_account in (None, ""):
                for account_field in ("account_id", "advertiser_id", "customer_id"):
                    if provider_values.get(account_field) not in (None, ""):
                        explicit_account = provider_values.get(account_field)
                        break
            if explicit_account in (None, ""):
                continue
            allowed, account_error = runtime._validate_account_with_principal(
                canonical_provider, str(explicit_account), True, account_scope,
            )
            if not allowed:
                return runtime._creation_policy_response(
                    session=session,
                    session_id=session_id,
                    run_id=run_id,
                    turn_id=turn_id,
                    user_input=safe_user_input,
                    intent=intent,
                    trace=trace,
                    error=account_error,
                )
        creation_ui = runtime.build_creation_ui(intent)
        if account_id and isinstance(creation_ui, dict):
            for card in creation_ui.get("cards", []) or []:
                if isinstance(card, dict):
                    card["account_id"] = str(account_id)
        selector_cards = [
            card for card in creation_ui.get("cards", []) or []
            if isinstance(card, Mapping)
            and card.get("type") == "ad_creation_selector"
        ]
        if selector_cards:
            clarification = runtime.creation_card_builder.build_clarification(intent)
            clarification_ui = {
                "schema_version": "1.0",
                "needs_input": True,
                "cards": [],
                "clarification": clarification,
            }
            reply = runtime.creation_ui_reply(clarification_ui, safe_user_input)
            return runtime._creation_input_response(
                session=session,
                session_id=session_id,
                run_id=run_id,
                turn_id=turn_id,
                user_input=safe_user_input,
                reply=reply,
                intent=intent,
                ui=clarification_ui,
                trace=trace,
                recalled_memories=recalled_memories,
                memory_updates=memory_updates,
                reason="creation_selector_required",
            )
        if creation_ui.get("cards") and creation_ui.get("needs_input"):
            reply = runtime.creation_ui_reply(creation_ui, safe_user_input)
            return runtime._creation_input_response(
                session=session,
                session_id=session_id,
                run_id=run_id,
                turn_id=turn_id,
                user_input=safe_user_input,
                reply=reply,
                intent=intent,
                ui=creation_ui,
                trace=trace,
                recalled_memories=recalled_memories,
                memory_updates=memory_updates,
                reason="creation_parameters_required",
            )

    # Step 3: discover Tools from their self-described action/resource
    # metadata. Skills provide expert context and SOP; the Runtime orders
    # the returned Tool plan from provider-owned resource metadata.
    trace.stage_status(
        "skill_selection",
        "Skill 选择",
        "running",
        subtitle="根据请求加载相关 Skill 与能力",
        safe_metadata={"phase": "skill_selection"},
        safe_input={
            "intent_type": intent.intent_type,
            "platforms": list(intent.namespaces or []),
        },
    )
    tool_plan = runtime.intent_router.route(intent, runtime.registry)

    # A model may return a semantic synonym or an invalid operation name.
    # Let an LLM-aware parser repair that result against the active Tool
    # catalog once, after the authoritative Router has rejected it. This
    # is deliberately optional for custom parsers and is not a keyword or
    # provider dispatch table.
    routed_platforms = {
        runtime._canonical_platform(platform) for platform in tool_plan
    }
    requested_platforms = {
        runtime._canonical_platform(platform)
        for platform in (getattr(intent, "namespaces", []) or [])
    }
    route_is_incomplete = bool(
        requested_platforms and routed_platforms != requested_platforms
    )
    should_repair_route = bool(
        tool_plan
        or route_is_incomplete
        or str(getattr(intent, "intent_type", "") or "") != "chat"
        or bool(getattr(intent, "namespaces", []) or [])
    )
    if should_repair_route and (not tool_plan or route_is_incomplete):
        repair = getattr(runtime.intent_parser, "repair_for_routing", None)
        repaired_intent = (
            repair(safe_user_input, session.ctx, intent)
            if callable(repair) else None
        )
        if repaired_intent is not None:
            intent = repaired_intent
            runtime._load_required_skills(intent.namespaces)
            policy_errors = runtime._validate_policies(intent)
            if not policy_errors:
                tool_plan = runtime.intent_router.route(intent, runtime.registry)
    if creation_blueprint_id:
        blueprint_tool_plan, blueprint_error = runtime._creation_blueprint_tool_plan(
            creation_blueprint_id, creation_blueprint_version, intent
        )
        if blueprint_error:
            reply = "这份广告创建草稿暂时无法继续：" + blueprint_error
            trace.error(reason="creation_blueprint_invalid")
            trace.done("failed", safe_metadata={"reason": "creation_blueprint_invalid"})
            runtime.persist_conversation_turn(
                session, turn_id, safe_user_input, reply,
                execution_trace=trace,
            )
            return {
            "session_id": session_id,
            "run_id": run_id,
            "turn_id": turn_id,
                "timestamp": datetime.now().isoformat(),
                "intent": intent.to_dict(),
                "tool_plan": {},
                "execution_plan": {},
                "tool_selection": None,
                "results": [],
                "reply": reply,
                "needs_confirmation": False,
                "confirmation_payload": None,
                "policy_errors": [blueprint_error],
                "ui": {},
            }
        # Blueprint submission is an explicit structured continuation.
        # The Blueprint's declared Tool composition is authoritative;
        # preserve the original intent name so custom Capabilities do not
        # need to alias their action to ``create_campaign``.
        intent.namespaces = [next(iter(blueprint_tool_plan))]
        tool_plan = blueprint_tool_plan or {}

    # Ordinary actions use the same schema boundary as creation: if the
    # selected Tool cannot be built from explicit/trusted session values,
    # ask first. This happens before ExecutionPlan/Workflow creation, so
    # an incomplete request is never rendered as an executable Tool node.
    creation_requested = runtime.creation_card_builder.is_creation_intent(
        intent, tool_plan=tool_plan,
    )
    clarification_feature = runtime._feature_for_intent(intent)
    feature_owns_planning = bool(
        clarification_feature is not None
        and callable(getattr(clarification_feature, "is_batch_intent", None))
        and clarification_feature.is_batch_intent(intent)
    )
    if (
        tool_plan
        and not creation_requested
        and not creation_blueprint_id
        and not feature_owns_planning
    ):
        account_by_platform: dict[str, Optional[str]] = {}
        for platform, routed in tool_plan.items():
            has_write = any(tool.is_write_tool for tool in routed)
            account_by_platform[runtime._canonical_platform(platform)] = (
                runtime.account_resolver.resolve(
                    intent,
                    platform,
                    list(routed),
                    account_id,
                    allow_automatic_account=not has_write,
                )
            )
        clarification = runtime.action_clarification_builder.build(
            intent,
            tool_plan,
            runtime.input_builder,
            session.ctx,
            account_by_platform=account_by_platform,
        )
        if clarification:
            clarification_ui = {
                "schema_version": "1.0",
                "needs_input": True,
                "cards": [],
                "clarification": clarification,
            }
            reply = runtime.action_clarification_reply(
                clarification_ui, safe_user_input,
            )
            return runtime._action_clarification_response(
                session=session,
                session_id=session_id,
                run_id=run_id,
                turn_id=turn_id,
                user_input=safe_user_input,
                reply=reply,
                intent=intent,
                ui=clarification_ui,
                trace=trace,
                recalled_memories=recalled_memories,
                memory_updates=memory_updates,
            )

    # The action is now complete enough to enter the normal lifecycle.
    # Do not let a later unrelated chat message inherit this old draft.
    runtime.set_action_draft(session_id, None)

    execution_groups = list(tool_plan.items())
    routed_tools = [
        tool for _platform, tools in execution_groups for tool in tools
    ]
    tool_selection = runtime._optimize_tool_selection(
        safe_user_input, intent, routed_tools, tenant_id
    )
    feature = runtime._feature_for_intent(intent)
    execution_plan = ExecutionPlan.from_tool_plan(
        intent, tool_plan, canonicalize=runtime._canonical_platform
    )
    trace.bind_plan(execution_plan)
    trace.stage_status(
        "skill_selection",
        "Skill 选择",
        "succeeded",
        subtitle=(
            f"已选择 {len(routed_tools)} 个可用 Tool"
            if routed_tools else "未匹配到可执行 Tool"
        ),
        safe_metadata={"tool_count": len(routed_tools)},
        safe_output={
            "tool_count": len(routed_tools),
            "tools": [tool.name for tool in routed_tools[:12]],
        },
    )
    # The card is a structured view of the same Blueprint/Tool contract
    # used by the execution path. It is returned alongside the normal
    # conversation so users can edit fields or continue in natural
    # language; it never invokes a lookup or Provider API.
    if not creation_ui and not campaign_only_request:
        creation_ui = runtime.build_creation_ui(intent, tool_plan=tool_plan)
    if account_id and isinstance(creation_ui, dict):
        for card in creation_ui.get("cards", []) or []:
            if isinstance(card, dict):
                # Keep the explicitly supplied account visible when a
                # later validation response returns the same card. The
                # value still comes from the request, never inference.
                card["account_id"] = str(account_id)

    # A creation Blueprint is a parameter-collection boundary. Do not
    # enter the generic workflow/account loop while the explicit account
    # is missing: that loop would represent a draft as a failed Tool
    # result. Resolve the account through the same schema-driven resolver
    # used by execution so an explicitly supplied provider account (for
    # example Google customer_id) is treated consistently with the
    # top-level account_id. The later card submission is the only
    # continuation into the normal creation lifecycle.
    creation_is_requested = runtime.creation_card_builder.is_creation_intent(
        intent, tool_plan=tool_plan,
    )
    creation_has_write_tools = creation_is_requested and any(
        tool.is_write_tool
        for tools in tool_plan.values()
        for tool in tools
    )
    missing_account_platform = None
    if creation_has_write_tools:
        for platform, tools in execution_groups:
            if not any(tool.is_write_tool for tool in tools):
                continue
            resolved_account = runtime.account_resolver.resolve(
                intent,
                platform,
                tools,
                account_id,
                allow_automatic_account=False,
            )
            if not resolved_account:
                missing_account_platform = runtime._canonical_platform(platform)
                break
    creation_account_missing = missing_account_platform is not None

    # A selected Blueprint is a parameter-collection boundary. If a
    # required field is still missing, stop here before the generic
    # parameter validator/workflow can turn the draft into a failed Tool
    # result. For an unselected natural-language request, retain the
    # existing generic Tool dry-run contract; its provider schema remains
    # the final source of validation.
    creation_needs_input = bool(
        creation_ui.get("cards")
        and (
            creation_account_missing
            or (creation_blueprint_id and creation_ui.get("needs_input"))
        )
    )
    if creation_has_write_tools and (creation_account_missing or creation_needs_input):
        trace.all_nodes_status("awaiting_confirmation", reason="creation_parameters_required")
        trace.reply()
        trace.done(
            "awaiting_confirmation",
            safe_metadata={"reason": "creation_parameters_required", "tool_count": len(routed_tools)},
        )
        account_payload = (
            {
                "type": "ask_account",
                "platform": missing_account_platform,
                "question": f"请提供要操作的 {missing_account_platform} 广告账户 ID。",
            }
            if missing_account_platform
            else None
        )
        reply = (
            runtime.creation_ui_reply(creation_ui, safe_user_input)
            if creation_ui.get("cards")
            else (
                account_payload["question"]
                if account_payload
                else "请先补充广告创建参数。"
            )
        )
        runtime.persist_conversation_turn(
            session, turn_id, safe_user_input, reply,
            execution_trace=trace, ui=creation_ui,
        )
        return {
            "session_id": session_id,
            "run_id": run_id,
            "turn_id": turn_id,
            "timestamp": datetime.now().isoformat(),
            "intent": intent.to_dict(),
            "tool_plan": {k: [t.name for t in v] for k, v in tool_plan.items()},
            "execution_plan": execution_plan.to_dict(),
            "tool_selection": {
                "tool_count": tool_selection["tool_count"],
                "tools": [tool.name for tool in tool_selection["selected_tools"]],
                "platforms": tool_selection["namespaces"],
                "context": tool_selection["context"],
                "tool_prompt": tool_selection["tool_prompt"],
                "expert_knowledge": tool_selection["expert_knowledge"],
                "knowledge": tool_selection.get("knowledge", []),
            },
            "memory": recalled_memories,
            "memory_updates": memory_updates,
            "results": [],
            "response_source": "creation_card",
            "reply": reply,
            # Keep the account request in the machine-readable response
            # even when a form card is present. The web UI intentionally
            # renders the card (rather than a second account popup),
            # while API clients can still use this payload to understand
            # why the plan is paused.
            "needs_confirmation": bool(account_payload),
            "needs_input": True,
            "confirmation_payload": account_payload,
            "workflow_id": None,
            "ui": creation_ui,
        }

    parameter_errors = runtime.input_builder.validate_platform_parameter_contract(
        intent, tool_plan
    )
    if parameter_errors:
        reply = (
            runtime.creation_ui_reply(creation_ui, safe_user_input)
            if creation_ui.get("needs_input")
            else "❌ 参数契约阻止本次请求：" + "；".join(parameter_errors)
        )
        first_tool = next(
            (tool for tools in tool_plan.values() for tool in tools), None
        )
        parameter_result = {
            "tool": first_tool.name if first_tool else "parameter_contract",
            "platform": first_tool.namespace if first_tool else "",
            "success": False,
            "data": {},
            "error": "; ".join(parameter_errors),
            "needs_confirmation": False,
        }
        trace.all_nodes_status("failed", reason="parameter_contract")
        trace.reply()
        trace.done("failed", safe_metadata={"reason": "parameter_contract"})
        runtime.persist_conversation_turn(
            session, turn_id, safe_user_input, reply,
            execution_trace=trace, ui=creation_ui,
        )
        return {
            "session_id": session_id,
            "run_id": run_id,
            "turn_id": turn_id,
            "timestamp": datetime.now().isoformat(),
            "intent": intent.to_dict(),
            "tool_plan": {k: [t.name for t in v] for k, v in tool_plan.items()},
            "execution_plan": execution_plan.to_dict(),
            "tool_selection": None,
            "results": [parameter_result],
            "reply": reply,
            "needs_confirmation": False,
            "confirmation_payload": None,
            "policy_errors": parameter_errors,
            "ui": creation_ui,
        }

    # A submitted Blueprint must pass the complete provider contract
    # before the first parent Tool is executed. This is especially
    # important for creatives: a missing minimum asset count must not
    # leave a campaign or ad group partially created in live mode.
    if creation_blueprint_id and creation_has_write_tools:
        creation_issues = runtime._creation_contract_preflight(
            intent, tool_plan, session, str(account_id or "")
        )
        if creation_issues:
            issue_pairs = {
                (str(item.get("tool") or ""), str(item.get("field") or ""))
                for item in creation_issues
            }
            for card in creation_ui.get("cards", []) if isinstance(creation_ui, dict) else []:
                if not isinstance(card, dict):
                    continue
                invalid_fields = list(card.get("invalid_fields") or [])
                for field in card.get("fields", []) or []:
                    if not isinstance(field, dict):
                        continue
                    key = (str(field.get("tool") or ""), str(field.get("provider_field") or ""))
                    if key in issue_pairs or (
                        key[1]
                        and any(
                            pair[1] == key[1]
                            for pair in issue_pairs
                        )
                    ):
                        field["state"] = "invalid"
                        if field.get("path") not in invalid_fields:
                            invalid_fields.append(field.get("path"))
                card["invalid_fields"] = list(dict.fromkeys(invalid_fields))
                card["ready"] = False
            creation_ui["needs_input"] = True
            creation_reply = runtime._creation_contract_reply(
                creation_ui, creation_issues
            )
            trace.stage_status(
                "creation_validation",
                "创建前检查",
                "running",
                subtitle="核对广告素材和平台必填规则",
                safe_metadata={"phase": "creation_contract_validation"},
            )
            trace.stage_status(
                "creation_validation",
                "创建前检查",
                "failed",
                subtitle="参数未满足，尚未进入创建",
                safe_metadata={
                    "phase": "creation_contract_validation",
                    "issue_count": len(creation_issues),
                },
                safe_output={
                    "ready": False,
                    "issue_count": len(creation_issues),
                },
            )
            trace.all_nodes_status(
                "skipped", reason="creation_validation_failed"
            )
            trace.reply()
            trace.done(
                "failed",
                safe_metadata={
                    "reason": "creation_validation_failed",
                    "issue_count": len(creation_issues),
                    "tool_count": len(routed_tools),
                },
            )
            runtime.persist_conversation_turn(
                session, turn_id, safe_user_input, creation_reply,
                execution_trace=trace, ui=creation_ui,
            )
            return {
            "session_id": session_id,
            "run_id": run_id,
            "turn_id": turn_id,
                "timestamp": datetime.now().isoformat(),
                "intent": intent.to_dict(),
                "tool_plan": {k: [t.name for t in v] for k, v in tool_plan.items()},
                "execution_plan": execution_plan.to_dict(),
                "tool_selection": {
                    "tool_count": tool_selection["tool_count"],
                    "tools": [tool.name for tool in tool_selection["selected_tools"]],
                    "platforms": tool_selection["namespaces"],
                    "context": tool_selection["context"],
                    "tool_prompt": tool_selection["tool_prompt"],
                    "expert_knowledge": tool_selection["expert_knowledge"],
                    "knowledge": tool_selection.get("knowledge", []),
                },
                "memory": recalled_memories,
                "results": [],
                "resource_results": [],
                "response_source": "creation_validation",
                "reply": creation_reply,
                "needs_confirmation": False,
                "confirmation_payload": None,
                "policy_errors": ["creation_validation_failed"],
                "creation_validation": {"status": "blocked", "issue_count": len(creation_issues)},
                "workflow_id": None,
                "ui": creation_ui,
            }

    # Cross-channel creation is preflighted as one provider-neutral plan.
    # This must happen before workflow creation or any provider Tool is
    # invoked, otherwise one channel could be committed/planned before a
    # later channel reveals a missing objective, app, targeting or asset.
    creation_preflight = None
    if (
        feature is not None
        and callable(getattr(feature, "preflight_creation", None))
        and callable(getattr(feature, "handles_creation_preflight", None))
        and feature.handles_creation_preflight(intent)
    ):
        creation_preflight = feature.preflight_creation(
            runtime.services,
            intent,
            tool_plan,
            session,
            account_id,
            account_scope,
            effective_permissions,
        )
        if not creation_preflight.ready:
            preflight_results = feature.preflight_results(creation_preflight)
            preflight_reply = getattr(feature, "preflight_failure_reply", None)
            reply = (
                preflight_reply(intent, creation_preflight)
                if callable(preflight_reply)
                else "跨渠道创建 preflight 未通过；已停止所有渠道的创建。"
            )
            if creation_ui.get("needs_input") and not any(
                isinstance(item.get("confirmation_payload"), dict)
                and item["confirmation_payload"].get("type") == "ask_account"
                for item in preflight_results
            ):
                reply = runtime.creation_ui_reply(creation_ui, safe_user_input)
            trace.all_nodes_status("failed", reason="preflight_blocked")
            trace.reply()
            trace.done("failed", safe_metadata={"reason": "preflight_blocked"})
            runtime.persist_conversation_turn(
                session, turn_id, safe_user_input, reply,
                execution_trace=trace, ui=creation_ui,
            )
            return {
            "session_id": session_id,
            "run_id": run_id,
            "turn_id": turn_id,
                "timestamp": datetime.now().isoformat(),
                "intent": intent.to_dict(),
                "tool_plan": {k: [t.name for t in v] for k, v in tool_plan.items()},
                    "tool_selection": {
                    "tool_count": tool_selection["tool_count"],
                    "tools": [tool.name for tool in tool_selection["selected_tools"]],
                    "platforms": tool_selection["namespaces"],
                    "context": tool_selection["context"],
                    "tool_prompt": tool_selection["tool_prompt"],
                    "expert_knowledge": tool_selection["expert_knowledge"],
                        "knowledge": tool_selection.get("knowledge", []),
                    },
                    "execution_plan": execution_plan.to_dict(),
                    "results": preflight_results,
                "resource_results": [],
                "workflow_id": None,
                **(
                    feature.preflight_payload(creation_preflight)
                    if callable(getattr(feature, "preflight_payload", None))
                    else {"preflight": creation_preflight.to_dict()}
                ),
                "reply": reply,
                "needs_confirmation": any(
                    item.get("needs_confirmation")
                    for item in preflight_results
                ),
                "confirmation_payload": next(
                    (
                        item.get("confirmation_payload")
                        for item in preflight_results
                        if item.get("confirmation_payload")
                    ),
                    None,
                ),
                "policy_errors": list(creation_preflight.errors),
                "ui": creation_ui,
            }

    # Batch management is a first-class planning operation.  It expands
    # IDs into independent items while retaining the normal whitelist and
    # workflow audit boundaries; no provider Handler is called here.
    if feature is not None and callable(
        getattr(feature, "is_batch_intent", None)
    ) and feature.is_batch_intent(intent):
        workflow_id = runtime.workflow.start(
            session,
            intent,
            tool_plan,
            register_items=not feature.is_batch_intent(intent),
            execution_plan=execution_plan,
        )
        runtime._bind_execution_run_workflow(run_id, workflow_id)
        batch_result = feature.run_batch_plan(
            runtime.services,
            safe_user_input, session, turn_id, intent, tool_plan,
            account_id, workflow_id,
            account_scope=account_scope,
            granted_permissions=effective_permissions,
        )
        if isinstance(batch_result, dict):
            batch_result.setdefault("run_id", run_id)
        for result in batch_result.get("results", []) if isinstance(batch_result, dict) else []:
            node = trace.node_for(result.get("platform", ""), result.get("tool", ""))
            trace.node_status(
                node,
                "succeeded" if result.get("success") else "failed",
                safe_metadata={"simulated": True, "reason": "batch_plan"},
            )
        trace.reply(needs_confirmation=bool(batch_result.get("needs_confirmation")) if isinstance(batch_result, dict) else False)
        trace.done(
            "awaiting_confirmation" if isinstance(batch_result, dict) and batch_result.get("needs_confirmation") else "succeeded",
            safe_metadata={"batch_plan": True},
        )
        return batch_result

    # 检查是否需要执行任何工具
    if not tool_plan:
        runtime.set_action_draft(session_id, None)
        intent_type = str(getattr(intent, "intent_type", "") or "")
        platform_params = getattr(intent, "scoped_parameters", {}) or {}
        has_structured_request = bool(
            getattr(intent, "namespaces", None)
            or any(
                isinstance(values, dict) and any(
                    value not in (None, "", {}, [])
                    for value in values.values()
                )
                for values in platform_params.values()
            )
        )
        if intent_type == "chat" and not has_structured_request:
            no_tool_reply = runtime.response_renderer.render_chat(safe_user_input)
        elif has_structured_request:
            no_tool_reply = (
                "我理解你想查询广告数据，但还无法确定具体的查询对象。"
                "请补充当前已注册的执行渠道、资源对象和操作，例如查询某个资源列表，"
                "或查询最近一段时间的报表。"
            )
        else:
            no_tool_reply = (
                "这次请求还没有匹配到可用的广告能力。请说明平台、对象和操作，"
                "例如查询某个广告账户下的资源列表。"
            )
        # There is no provider evidence at this point. Structured
        # requests must use the deterministic message; sending an empty
        # result set to the final-answer LLM could make it claim that a
        # query was attempted or that a report was empty. Ordinary chat
        # still gets the normal conversational synthesizer so controlled
        # Memory context remains useful.
        if intent_type == "chat" and not has_structured_request:
            no_tool_reply, response_source = runtime._render_response(
                safe_user_input,
                intent,
                [],
                False,
                session=session,
                fallback_reply=no_tool_reply,
            )
        else:
            response_source = "renderer"
        if creation_ui.get("needs_input"):
            no_tool_reply = runtime.creation_ui_reply(creation_ui, safe_user_input)
            response_source = "creation_card"
        trace.stage_status(
            "reply",
            "回复生成",
            "running",
            subtitle="生成面向业务人员的结果说明",
            safe_metadata={"phase": "response_rendering"},
            safe_input={
                "result_count": 0,
                "structured_request": has_structured_request,
            },
        )
        # The chat renderer is the actual response boundary even when no
        # executable Tool was selected. Keep this stage conditional on
        # reaching the branch; it is not a prebuilt workflow step.
        trace.stage_status(
            "reply",
            "回复生成",
            "succeeded",
            subtitle="已生成本轮回复",
            safe_metadata={"response_source": response_source},
            safe_output={
                "response_source": response_source,
                "available": True,
                "preview": runtime._redact_for_persistence(no_tool_reply),
            },
        )
        trace.reply()
        trace.done(
            "failed" if has_structured_request or intent_type != "chat" else "succeeded",
            safe_metadata={"tool_count": 0},
        )
        runtime.persist_conversation_turn(
            session, turn_id, safe_user_input, no_tool_reply,
            execution_trace=trace, ui=creation_ui,
        )
        return {
            "session_id": session_id,
            "run_id": run_id,
            "turn_id": turn_id,
            "timestamp": datetime.now().isoformat(),
            "intent": intent.to_dict(),
            "tool_plan": {},
            "execution_plan": execution_plan.to_dict(),
            "tool_selection": {
                "tool_count": tool_selection["tool_count"],
                "tools": [tool.name for tool in tool_selection["selected_tools"]],
                "platforms": tool_selection["namespaces"],
                "context": tool_selection["context"],
                "tool_prompt": tool_selection["tool_prompt"],
                "expert_knowledge": tool_selection["expert_knowledge"],
                "knowledge": tool_selection.get("knowledge", []),
            },
            "memory": recalled_memories,
            "results": [],
            "response_source": response_source,
            "reply": no_tool_reply,
            "needs_confirmation": False,
            "confirmation_payload": None,
            "workflow_id": None,
            "ui": creation_ui,
        }

    # Keep the caller's approval separate from the response payload that
    # is built during this turn.  Reusing the same variable would erase a
    # supplied plan token before the live validation branch.
    incoming_confirmation_payload = confirmation_payload

    # Step 4: 执行工具（按平台顺序）
    results = []
    needs_confirmation = False
    confirmation_payload = None
    workflow_id = runtime.workflow.start(
        session, intent, tool_plan, execution_plan=execution_plan
    )
    runtime._bind_execution_run_workflow(run_id, workflow_id)
    # Keep sensitive execution inputs local; they are only copied through
    # the redaction path when a workflow is persisted and are never added
    # to the public result payload.
    workflow_inputs: dict[int, dict] = {}
    workflow_sequence = 0

    tool_call_count = 0
    for platform, tools in execution_groups:
        if cancellation_event is not None and cancellation_event.is_set():
            break
        # 转换平台名称
        actual_platform = runtime._canonical_platform(platform)

        account_stage_id = f"account_scope:{actual_platform}"
        trace.stage_status(
            account_stage_id,
            "账户范围",
            "running",
            subtitle=f"校验 {actual_platform} 账户与访问范围",
            namespace=actual_platform,
            safe_metadata={"phase": "account_scope"},
            safe_input={"platform": actual_platform},
        )

        # 每个平台使用自己的账户（不跨平台共享）。读请求可以在
        # 单账户白名单下方便地兜底；写请求必须由本回合显式提供账户，
        # 绝不能因为白名单恰好只有一个账户就静默选中目标广告主。
        platform_has_write = any(tool.is_write_tool for tool in tools)
        per_platform_account = runtime.account_resolver.resolve(
            intent,
            platform,
            tools,
            account_id,
            allow_automatic_account=not platform_has_write,
        )
        if not per_platform_account:
            test_accounts = runtime._available_accounts_for_request(
                actual_platform, account_scope
            )
            if not platform_has_write and len(test_accounts) == 1:
                per_platform_account = test_accounts[0]
            else:
                results.append({
                    "tool": tools[0].name if tools else "unknown",
                    "platform": actual_platform,
                    "success": False,
                    "data": {},
                    "error": "缺少账户ID",
                    "needs_confirmation": True,
                    "confirmation_payload": {
                        "type": "ask_account",
                        "platform": actual_platform,
                        "question": (
                            f"请提供要操作的 {actual_platform} 广告账户 ID。"
                            if platform_has_write else
                            f"请提供 {actual_platform} 账户 ID（当前仅允许查询受控账户）。"
                        ),
                    },
                })
                for tool_def in tools:
                    trace.node_status(
                        trace.node_for(actual_platform, tool_def.name),
                        "awaiting_confirmation",
                        safe_metadata={"reason": "account_required"},
                    )
                needs_confirmation = True
                confirmation_payload = results[-1]["confirmation_payload"]
                trace.stage_status(
                    account_stage_id,
                    "账户范围",
                    "awaiting_confirmation",
                    subtitle="等待补充账户范围",
                    namespace=actual_platform,
                    safe_metadata={"reason": "account_required"},
                    safe_output={"validated": False, "account_required": True},
                )
                continue

        # 只读模式验证所有操作；写操作在 dry-run/live 两种模式下都必须
        # 命中显式测试账户白名单。
        if runtime._read_only_mode or platform_has_write or runtime.enforce_account_scope:
            allowed, error_msg = runtime._validate_account_with_principal(
                actual_platform, per_platform_account, platform_has_write,
                account_scope,
            )
            if not allowed:
                results.append({
                    "tool": tools[0].name if tools else "unknown",
                    "platform": actual_platform,
                    "success": False,
                    "error": f"账户不在白名单中: {error_msg}",
                })
                for tool_def in tools:
                    trace.node_status(
                        trace.node_for(actual_platform, tool_def.name),
                        "failed",
                        safe_metadata={"reason": "account_scope_denied"},
                    )
                trace.stage_status(
                    account_stage_id,
                    "账户范围",
                    "failed",
                    subtitle="账户不在允许范围内",
                    namespace=actual_platform,
                    safe_metadata={"reason": "account_scope_denied"},
                    safe_output={"validated": False, "account_allowed": False},
                )
                continue

        trace.stage_status(
            account_stage_id,
            "账户范围",
            "succeeded",
            subtitle="账户范围校验通过",
            namespace=actual_platform,
            safe_metadata={"validated": True},
            safe_output={
                "validated": True,
                "account_selected": bool(per_platform_account),
            },
        )

        # A dependent Campaign creation is one operator decision.  Build
        # a stable, provider-neutral approval envelope for the complete
        # write chain before entering the Tool loop.  Parent IDs are
        # provider-generated during execution and therefore are not part
        # of the operator-authored manifest.
        write_chain_tools = [tool for tool in tools if tool.is_write_tool]
        plan_confirmation_mode = (
            runtime.execution_mode == ExecutionMode.LIVE.value
            and len(write_chain_tools) > 1
            and len({runtime._canonical_platform(getattr(tool, "namespace", actual_platform))
                     for tool in write_chain_tools}) == 1
        )
        plan_confirmation_expected = None
        plan_confirmation_authorized = False
        if plan_confirmation_mode:
            intent_snapshot = (
                intent.to_dict() if callable(getattr(intent, "to_dict", None))
                else vars(intent) if hasattr(intent, "__dict__") else {}
            )
            plan_confirmation_expected = runtime.security.confirmation_chain_plan(
                session_id,
                session.ctx.user_id,
                per_platform_account,
                actual_platform,
                write_chain_tools,
                runtime._redact_for_persistence({
                    "user_input": safe_user_input,
                    "intent": intent_snapshot,
                    "creation_blueprint_id": creation_blueprint_id,
                    "creation_blueprint_version": creation_blueprint_version,
                }),
                preview={
                    "platform": actual_platform,
                    "account_id": per_platform_account,
                    "steps": [
                        {
                            "tool": tool.name,
                            "resource_type": getattr(tool, "resource_type", None),
                            "parent_resource_type": getattr(tool, "parent_resource_type", None),
                        }
                        for tool in write_chain_tools
                    ],
                },
            )

        # 非只读模式：写操作需要白名单 + 幂等保护
        chain_blocked = False
        chain_blocker = None
        for tool_def in tools:
            node = trace.node_for(actual_platform, tool_def.name)
            if cancellation_event is not None and cancellation_event.is_set():
                chain_blocked = True
                chain_blocker = tool_def.name
                trace.node_status(node, "skipped", safe_metadata={"reason": "cancelled"})
                break
            runtime.workflow.heartbeat(workflow_id)
            if workflow_id and tool_def.is_write_tool:
                workflow_sequence += 1
                runtime._session_manager.record_workflow_item(
                    workflow_id=workflow_id,
                    sequence=workflow_sequence,
                    platform=actual_platform,
                    tool_name=tool_def.name,
                    status="running",
                    input_data={},
                    scope=per_platform_account,
                    parent_resource_type=getattr(tool_def, "parent_resource_type", None),
                )
            tool_call_count += 1
            turn_budget_error = runtime._check_turn_budget(
                turn_deadline, tool_call_count, runtime.max_tool_calls
            )
            if turn_budget_error:
                results.append({
                    "tool": tool_def.name,
                    "platform": platform,
                    "success": False,
                    "data": {"execution_status": "budget_exceeded"},
                    "error": turn_budget_error,
                    "needs_confirmation": False,
                })
                trace.node_status(node, "failed", safe_metadata={"reason": "turn_budget_exceeded"})
                chain_blocked = True
                chain_blocker = tool_def.name
                continue
            if chain_blocked:
                results.append({
                    "tool": tool_def.name,
                    "platform": platform,
                    "success": False,
                    "data": {"skipped": True, "mode": runtime.execution_mode},
                    "error": f"前置工具 {chain_blocker} 未成功，已停止后续依赖步骤",
                    "skipped": True,
                })
                trace.node_status(node, "skipped", safe_metadata={"reason": "dependency_blocked"})
                continue
            permission_error = runtime._check_tool_permissions(
                tool_def, effective_permissions
            )
            if permission_error:
                results.append({
                    "tool": tool_def.name,
                    "platform": platform,
                    "success": False,
                    "data": {},
                    "error": permission_error,
                    "needs_confirmation": False,
                })
                trace.node_status(node, "failed", safe_metadata={"reason": "permission_denied"})
                chain_blocked = True
                chain_blocker = tool_def.name
                continue
            if not runtime._read_only_mode:
                if tool_def.is_write_tool and per_platform_account:
                    allowed, error_msg = runtime.whitelist_validator.validate_account(actual_platform, per_platform_account)
                    if not allowed:
                        results.append({
                            "tool": tool_def.name,
                            "platform": actual_platform,
                            "success": False,
                            "error": f"账户验证失败: {error_msg}",
                        })
                        trace.node_status(node, "failed", safe_metadata={"reason": "account_not_allowed"})
                        continue
            # 为当前平台临时设置账户上下文
            original_account = session.ctx.account_id
            session.ctx.account_id = per_platform_account

            # 构建执行输入
            tool_input = runtime.input_builder.build(
                tool_def, intent, platform, session.ctx
            )
            if workflow_id and tool_def.is_write_tool:
                runtime._session_manager.record_workflow_item(
                    workflow_id=workflow_id,
                    sequence=workflow_sequence,
                    platform=actual_platform,
                    tool_name=tool_def.name,
                    status="running",
                    input_data=runtime._redact_for_persistence(tool_input),
                        scope=per_platform_account,
                    parent_resource_type=getattr(tool_def, "parent_resource_type", None),
                )

            protected_paths = runtime.security.validate_input_redline(tool_input)
            if protected_paths:
                error = "请求包含禁止传入的凭证/账户配置字段：" + ", ".join(protected_paths)
                results.append({
                    "tool": tool_def.name,
                    "platform": platform,
                    "success": False,
                    "data": {},
                    "error": error,
                    "needs_confirmation": False,
                })
                trace.node_status(node, "failed", safe_metadata={"reason": "protected_input"})
                chain_blocked = True
                chain_blocker = tool_def.name
                session.ctx.account_id = original_account
                continue

            unknown_params = tool_input.pop("_unknown_params", None)
            if unknown_params:
                results.append({
                    "tool": tool_def.name,
                    "platform": platform,
                    "success": False,
                    "data": {},
                    "error": (
                        "工具参数契约不支持以下字段："
                        + ", ".join(unknown_params)
                        + "；请使用该工具 Schema 中声明的参数"
                    ),
                    "needs_confirmation": False,
                })
                trace.node_status(node, "failed", safe_metadata={"reason": "unknown_parameters"})
                chain_blocked = True
                chain_blocker = tool_def.name
                session.ctx.account_id = original_account
                continue

            selection_errors = tool_input.pop("_selection_errors", None)
            if selection_errors:
                results.append({
                    "tool": tool_def.name,
                    "platform": platform,
                    "success": False,
                    "data": {"execution_status": "invalid_parameter_selection"},
                    "error": "参数选择凭证无效：" + "; ".join(selection_errors),
                    "needs_confirmation": False,
                })
                trace.node_status(node, "failed", safe_metadata={"reason": "invalid_parameter_selection"})
                chain_blocked = True
                chain_blocker = tool_def.name
                session.ctx.account_id = original_account
                continue

            # 检查必需参数是否齐全，不齐全则询问用户
            missing_params = tool_input.pop("_missing_params", None)
            if missing_params:
                lookup_tools = runtime.input_builder.lookup_tools_for_fields(
                    tool_def, missing_params
                )
                results.append({
                    "tool": tool_def.name,
                    "platform": platform,
                    "success": False,
                    "error": f"缺少必需参数: {', '.join(missing_params)}",
                    "needs_confirmation": True,
                    "confirmation_payload": {
                        "type": "ask_params",
                        "tool": tool_def.name,
                        "missing": missing_params,
                        "lookup_tools": lookup_tools,
                        "question": f"⚠️ 执行 {tool_def.name} 需要以下参数：{', '.join(missing_params)}，请提供这些参数",
                    },
                })
                trace.confirmation(node, reason="missing_parameters")
                needs_confirmation = True
                confirmation_payload = results[-1]["confirmation_payload"]
                chain_blocked = True
                chain_blocker = tool_def.name
                session.ctx.account_id = original_account
                continue

            schema_errors = (
                validate_tool_input(tool_def.input_schema, tool_input)
                if tool_def.input_schema else []
            )
            if schema_errors:
                results.append({
                    "tool": tool_def.name,
                    "platform": platform,
                    "success": False,
                    "error": f"Input validation failed: {schema_errors}",
                    "needs_confirmation": False,
                })
                trace.node_status(node, "failed", safe_metadata={"reason": "schema_invalid"})
                chain_blocked = True
                chain_blocker = tool_def.name
                session.ctx.account_id = original_account
                continue

            # Provider-specific requirements are stricter than the
            # fields needed to generate a dry-run plan.  Validate them
            # before confirmation/client execution only in the live path,
            # so dry-run can still preview an incomplete plan while live
            # can fail with an actionable error before any API call.
            if tool_def.is_write_tool and runtime.execution_mode == ExecutionMode.LIVE.value:
                provider_errors = validate_tool_input(
                    tool_def.input_schema,
                    tool_input,
                    include_capability_contract=True,
                )
                if provider_errors:
                    results.append({
                        "tool": tool_def.name,
                        "platform": platform,
                        "success": False,
                        "error": f"Provider contract validation failed: {provider_errors}",
                        "needs_confirmation": False,
                    })
                    trace.node_status(node, "failed", safe_metadata={"reason": "provider_contract_invalid"})
                    chain_blocked = True
                    chain_blocker = tool_def.name
                    session.ctx.account_id = original_account
                    continue

            if tool_def.is_write_tool and runtime.execution_mode == ExecutionMode.LIVE.value and (
                not runtime.allow_live_writes
                or not tool_def.live_support
                or tool_def.name not in runtime._live_approved_tools
            ):
                if not runtime.allow_live_writes:
                    reason = "Runtime 全局 allow_live_writes 未开启"
                elif not tool_def.live_support:
                    reason = "该 Tool 当前仅支持 dry-run"
                else:
                    reason = "该 Tool 未加入 live 执行批准清单"
                results.append({
                    "tool": tool_def.name,
                    "platform": platform,
                    "success": False,
                    "error": f"{tool_def.name} 当前禁止 live 执行：{reason}",
                    "needs_confirmation": False,
                })
                trace.node_status(node, "failed", safe_metadata={"reason": "live_write_blocked"})
                chain_blocked = True
                chain_blocker = tool_def.name
                session.ctx.account_id = original_account
                continue

            if (
                tool_def.is_write_tool
                and runtime.execution_mode == ExecutionMode.LIVE.value
                and runtime.write_guard is None
            ):
                results.append({
                    "tool": tool_def.name,
                    "platform": platform,
                    "success": False,
                    "error": "live 写操作必须配置 WriteGuard；已拒绝执行",
                    "needs_confirmation": False,
                })
                trace.node_status(node, "failed", safe_metadata={"reason": "write_guard_missing"})
                chain_blocked = True
                chain_blocker = tool_def.name
                session.ctx.account_id = original_account
                continue

            # live 写入必须由调用方显式确认；dry-run 不需要确认，因为不会
            # 触发外部写 API。确认状态只来自受信任的请求字段，不从自然语言推断。
            expected_confirmation = None
            if tool_def.is_write_tool and runtime.execution_mode == ExecutionMode.LIVE.value:
                if plan_confirmation_mode:
                    expected_confirmation = runtime.security.prepare_confirmation(
                        plan_confirmation_expected or {}, create=not confirmed,
                    )
                    if confirmed and incoming_confirmation_payload is None:
                        error = "confirmed=true 必须携带当前创建计划的 confirmation_payload"
                        reason = "confirmation_payload_required"
                    elif confirmed and not runtime.security.confirmation_matches(
                        incoming_confirmation_payload, expected_confirmation,
                    ):
                        error = "确认信息与当前创建计划不匹配，已拒绝执行"
                        reason = "confirmation_mismatch"
                    elif confirmed and not plan_confirmation_authorized:
                        approval_ok, approval_error = runtime.security.validate_confirmation_record(
                            expected_confirmation, incoming_confirmation_payload,
                        )
                        if not approval_ok:
                            error = f"确认记录无效：{approval_error}"
                            reason = "confirmation_invalid"
                        elif not runtime._session_manager or runtime._session_manager.consume_approval(
                            expected_confirmation["plan_fingerprint"],
                            expected_confirmation["confirmation_token"],
                        ):
                            plan_confirmation_authorized = True
                            error = ""
                            reason = ""
                        else:
                            error = "确认记录已被使用，请重新生成计划并确认"
                            reason = "confirmation_consumed"
                    elif not confirmed:
                        error = "live 创建计划等待显式确认"
                        reason = "live_confirmation_required"
                    else:
                        error = ""
                        reason = ""

                    if error:
                        results.append({
                            "tool": tool_def.name,
                            "platform": platform,
                            "success": False,
                            "error": error,
                            "needs_confirmation": True,
                            "confirmation_payload": {
                                **expected_confirmation,
                                "input": runtime._redact_for_persistence(tool_input),
                                "question": (
                                    "请确认整条创建计划（Campaign 及其下层级）后再提交。"
                                    if reason == "live_confirmation_required"
                                    else "请使用当前创建计划返回的确认信息。"
                                ),
                            },
                        })
                        trace.confirmation(node, reason=reason)
                        needs_confirmation = True
                        confirmation_payload = results[-1]["confirmation_payload"]
                        chain_blocked = True
                        chain_blocker = tool_def.name
                        session.ctx.account_id = original_account
                        continue
                else:
                    expected_confirmation = runtime.security.prepare_confirmation(
                        runtime.security.confirmation_plan(
                            session_id, session.ctx.user_id, session.ctx.account_id,
                            tool_def, tool_input,
                            preview={
                                "tool": tool_def.name,
                                "platform": actual_platform,
                                "account_id": session.ctx.account_id,
                                "input": runtime._redact_for_persistence(tool_input),
                            },
                        ),
                        create=not confirmed,
                    )

                    if confirmed and incoming_confirmation_payload is None:
                        results.append({
                            "tool": tool_def.name,
                            "platform": platform,
                            "success": False,
                            "error": "confirmed=true 必须携带当前写入计划的 confirmation_payload",
                            "needs_confirmation": True,
                            "confirmation_payload": {
                                "type": "confirm_write",
                                **(expected_confirmation or {}),
                                "input": runtime._redact_for_persistence(tool_input),
                                "question": "请使用当前计划返回的 confirmation_payload 确认。",
                            },
                        })
                        trace.confirmation(node, reason="confirmation_payload_required")
                        needs_confirmation = True
                        confirmation_payload = results[-1]["confirmation_payload"]
                        chain_blocked = True
                        chain_blocker = tool_def.name
                        session.ctx.account_id = original_account
                        continue

                    if confirmed and incoming_confirmation_payload is not None and not runtime.security.confirmation_matches(
                        incoming_confirmation_payload, expected_confirmation or {}
                    ):
                        results.append({
                            "tool": tool_def.name,
                            "platform": platform,
                            "success": False,
                            "error": "确认信息与当前写入计划不匹配，已拒绝执行",
                            "needs_confirmation": True,
                            "confirmation_payload": {
                                "type": "confirm_write",
                                **(expected_confirmation or {}),
                                "input": runtime._redact_for_persistence(tool_input),
                                "question": "写入计划已变化，请使用最新计划重新确认。",
                            },
                        })
                        trace.confirmation(node, reason="confirmation_mismatch")
                        needs_confirmation = True
                        confirmation_payload = results[-1]["confirmation_payload"]
                        chain_blocked = True
                        chain_blocker = tool_def.name
                        session.ctx.account_id = original_account
                        continue

                    if confirmed and incoming_confirmation_payload is not None:
                        approval_ok, approval_error = runtime.security.validate_confirmation_record(
                            expected_confirmation or {}, incoming_confirmation_payload
                        )
                        if not approval_ok:
                            results.append({
                                "tool": tool_def.name,
                                "platform": platform,
                                "success": False,
                                "error": f"确认记录无效：{approval_error}",
                                "needs_confirmation": True,
                                "confirmation_payload": {
                                    "type": "confirm_write",
                                    **(expected_confirmation or {}),
                                    "input": runtime._redact_for_persistence(tool_input),
                                    "question": "确认记录已过期或已使用，请重新生成计划并确认。",
                                },
                            })
                            trace.confirmation(node, reason="confirmation_invalid")
                            needs_confirmation = True
                            confirmation_payload = results[-1]["confirmation_payload"]
                            chain_blocked = True
                            chain_blocker = tool_def.name
                            session.ctx.account_id = original_account
                            continue

                    if not confirmed:
                        results.append({
                            "tool": tool_def.name,
                            "platform": platform,
                            "success": False,
                            "error": "live 写操作等待显式确认",
                            "needs_confirmation": True,
                            "confirmation_payload": {
                                "type": "confirm_write",
                                "tool": tool_def.name,
                                "platform": actual_platform,
                                "input": runtime._redact_for_persistence(tool_input),
                                **(expected_confirmation or {}),
                                "question": f"即将对 {actual_platform} 执行 live 写操作 {tool_def.name}，请确认。",
                            },
                        })
                        trace.confirmation(node, reason="live_confirmation_required")
                        needs_confirmation = True
                        confirmation_payload = results[-1]["confirmation_payload"]
                        chain_blocked = True
                        chain_blocker = tool_def.name
                        session.ctx.account_id = original_account
                        continue

            # 使用最终规范化后的输入生成幂等键，保证 reserve 与成功后的
            # mark_executed 使用同一组字段；不能使用原始自然语言参数。
            write_reservation = None
            if (
                runtime.execution_mode == ExecutionMode.LIVE.value
                and not runtime._read_only_mode
                and tool_def.is_write_tool
                and runtime.write_guard
            ):
                reserve_record = getattr(runtime.write_guard, "reserve_write_record", None)
                if callable(reserve_record):
                    allowed, reason, write_reservation = reserve_record(
                        session.ctx, tool_def, tool_input
                    )
                else:
                    allowed, reason = runtime.write_guard.reserve_write(
                        session.ctx, tool_def, tool_input
                    )
                if not allowed:
                    results.append({
                        "tool": tool_def.name,
                        "platform": platform,
                        "success": False,
                        "error": f"Write guard blocked: {reason}",
                    })
                    trace.node_status(node, "failed", safe_metadata={"reason": "write_guard_blocked"})
                    chain_blocked = True
                    chain_blocker = tool_def.name
                    session.ctx.account_id = original_account
                    continue

            # dry-run 下写工具只生成本地模拟结果，绝不触发 API Client。
            started_at = datetime.now().isoformat()
            trace.node_status(
                node,
                "running",
                safe_input=runtime._redact_for_persistence(tool_input),
            )
            try:
                if tool_def.is_write_tool and runtime.is_dry_run:
                    schema_errors = validate_tool_input(tool_def.input_schema, tool_input) if tool_def.input_schema else []
                    if schema_errors:
                        result = ToolResult.error(f"Input validation failed: {schema_errors}")
                    else:
                        result = runtime._simulate_write(tool_def, tool_input, actual_platform)
                else:
                    result = runtime.tool_executor.execute(
                        session.ctx, tool_def.name, tool_input, request_clients
                    )
            except Exception as exc:
                logger.exception("工具执行失败: %s", tool_def.name)
                result = ToolResult.error(f"工具执行失败: {exc}")

            result = runtime.security.normalize_read_result_evidence(tool_def, result)
            result = runtime.input_builder.decorate_lookup_result(
                tool_def, result, session.ctx, actual_platform
            )
            result = runtime.security.enforce_result_limit(result, tool_def)
            if runtime.security.is_uncertain_provider_failure(tool_def, result):
                # A transport/temporary error does not prove that the
                # provider rejected the write. Persist an explicit
                # unknown outcome so workflow recovery and reconciliation
                # do not depend on parsing the human-readable error.
                result.data = {
                    **(result.data if isinstance(result.data, dict) else {}),
                    "execution_status": "unknown",
                }
            runtime.workflow.heartbeat(workflow_id)

            resource_type = getattr(tool_def, "resource_type", None)
            resource_id_field = runtime._resource_id_field_for_tool(tool_def)
            parent_type = getattr(tool_def, "parent_resource_type", None)
            parent_field = runtime._parent_resource_id_field_for_tool(tool_def)
            parent_id = tool_input.get(parent_field) if parent_field else None
            # Keep hierarchy metadata next to the provider result. This
            # is especially important for live adapters whose response
            # only contains the newly created object's ID.
            if resource_type and isinstance(result.data, dict):
                result.data = {
                    **result.data,
                    "resource_type": resource_type,
                    "parent_resource_type": parent_type,
                    "parent_resource_id_field": parent_field,
                    "parent_resource_id": (
                        str(parent_id) if parent_id not in (None, "") else None
                    ),
                }
                if resource_id_field:
                    result.data["resource_id_field"] = resource_id_field

            result_index = len(results)
            safe_result_data = runtime._redact_for_persistence(result.data)
            safe_result_error = runtime._redact_for_persistence(result.error)
            safe_error_detail = runtime._redact_for_persistence(
                result.error_detail.to_dict()
                if getattr(result, "error_detail", None) else None
            )
            results.append({
                "tool": tool_def.name,
                "platform": platform,
                "resource_type": resource_type,
                "resource_id_field": resource_id_field,
                "parent_resource_type": parent_type,
                "parent_resource_id_field": parent_field,
                "action": getattr(tool_def, "action", ""),
                "result_items_key": getattr(tool_def, "result_items_key", None),
                "result_id_fields": list(
                    getattr(tool_def, "result_id_fields", []) or []
                ),
                "related_resource_type": getattr(
                    tool_def, "related_resource_type", None
                ),
                "related_resource_id_fields": list(
                    getattr(tool_def, "related_resource_id_fields", []) or []
                ),
                "parent_resource_id": (
                    str(parent_id) if parent_id not in (None, "") else None
                ),
                "account_id": per_platform_account,
                "success": result.success,
                "data": safe_result_data,
                "error": safe_result_error,
                "error_detail": safe_error_detail,
                "needs_confirmation": result.requires_confirmation,
            })
            execution_status = (
                result.data.get("execution_status")
                if isinstance(result.data, dict) else None
            )
            result_status = (
                "awaiting_confirmation" if result.requires_confirmation
                else "succeeded" if result.success
                else "unknown" if execution_status == "unknown"
                else "failed"
            )
            trace.node_status(
                node,
                result_status,
                safe_metadata={
                    "simulated": bool(result.simulated),
                    "execution_status": execution_status,
                },
                safe_input=runtime._redact_for_persistence(tool_input),
                safe_output={
                    "success": bool(result.success),
                    "data": safe_result_data,
                    "has_error": bool(safe_result_error),
                    "execution_status": execution_status,
                },
            )
            workflow_inputs[result_index] = copy.deepcopy(tool_input)

            if not result.success or result.requires_confirmation:
                chain_blocked = True
                chain_blocker = tool_def.name

            if result.requires_confirmation:
                needs_confirmation = True
                confirmation_payload = result.card_payload

            # 保存执行结果到会话上下文（跨 Tool 传递）
            safe_result = ToolResult(
                success=result.success,
                data=safe_result_data,
                error=safe_result_error,
                error_detail=result.error_detail,
                requires_confirmation=result.requires_confirmation,
                card_payload=runtime._redact_for_persistence(result.card_payload),
                simulated=result.simulated,
            )
            session.save_result(tool_def.name, safe_result, platform=actual_platform)

            if (
                result.success
                and not result.simulated
                and tool_def.action == "create"
                and isinstance(result.data, dict)
            ):
                created_id = (
                    result.data.get(resource_id_field)
                    if resource_id_field else None
                )
                if created_id not in (None, ""):
                    created_map = session.ctx.metadata.setdefault(
                        "runtime_created_resource_ids", {}
                    )
                    if isinstance(created_map, dict):
                        created_map.setdefault(resource_type, []).append(
                            str(created_id)
                        )

            # 将 protected_state 同步回 ctx，使后续 Tool 可以读取
            session.ctx.protected_state.update(session.protected_state)

            # 成功的 live 写入才进入幂等记录；dry-run 不污染 live 去重状态。
            if (
                result.success and not result.simulated and not result.requires_confirmation
                and tool_def.is_write_tool
                and runtime.write_guard and hasattr(runtime.write_guard, "mark_executed")
            ):
                if write_reservation is not None and hasattr(runtime.write_guard, "finalize"):
                    runtime.write_guard.finalize(write_reservation, result)
                else:
                    runtime.write_guard.mark_executed(tool_def.name, tool_input, session.ctx.user_id)
                if (
                    expected_confirmation
                    and incoming_confirmation_payload
                    and not plan_confirmation_mode
                ):
                    if runtime._session_manager:
                        runtime._session_manager.consume_approval(
                            expected_confirmation["plan_fingerprint"],
                            expected_confirmation["confirmation_token"],
                        )
            elif (
                (not result.success or result.requires_confirmation)
                and runtime.execution_mode == ExecutionMode.LIVE.value
                and tool_def.is_write_tool
                and runtime.write_guard
                and hasattr(runtime.write_guard, "release_write")
                and not runtime.security.is_uncertain_provider_failure(tool_def, result)
            ):
                if write_reservation is not None and hasattr(runtime.write_guard, "finalize"):
                    runtime.write_guard.finalize(write_reservation, result)
                else:
                    runtime.write_guard.release_write(
                        tool_def.name, tool_input, session.ctx.user_id
                    )

            # 记录安全审计信息，并保存本地模拟 Campaign 状态。
            runtime._persist_tool_result(
                session, turn_id, tool_def, actual_platform,
                tool_input, result,
            )

            # 恢复原始账户上下文
            session.ctx.account_id = original_account

    # Cross-channel comparison is a two-phase read workflow: first list
    # campaigns, then collect campaign-scoped report rows.
    analysis_owner = getattr(feature, "handles_analysis", None) if feature is not None else None
    analysis_stage_active = bool(
        feature is not None
        and callable(analysis_owner)
        and analysis_owner(intent)
    )
    if analysis_stage_active:
        trace.stage_status(
            "analysis",
            "结果分析",
            "running",
            subtitle="整理工具结果并提取业务信息",
            safe_metadata={"phase": "result_analysis"},
            safe_input={"result_count": len(results)},
        )
    if feature is not None and callable(
        getattr(feature, "collect_metrics", None)
    ):
        feature.collect_metrics(
            runtime.services,
            intent, tool_plan, results, session, turn_id, request_clients,
            account_scope=account_scope,
            granted_permissions=effective_permissions,
            execution_trace=trace,
        )
    runtime.workflow.finish(
        workflow_id, tool_plan, results, workflow_inputs,
        intent=intent, session=session,
    )
    resource_results = runtime._build_resource_results(results)

    analysis: dict[str, Any] = {}
    if feature is not None and callable(getattr(feature, "analyze", None)):
        analysis = feature.analyze(intent, results)
    if analysis_stage_active:
        trace.stage_status(
            "analysis",
            "结果分析",
            "succeeded",
            subtitle="结果已整理完成",
            safe_metadata={"result_count": len(results)},
            safe_input={"result_count": len(results)},
            safe_output={
                "result_count": len(results),
                "analysis_available": bool(analysis),
                "summary": runtime._redact_for_persistence(analysis or {}),
            },
        )
    trace.stage_status(
        "reply",
        "回复生成",
        "running",
        subtitle="生成面向业务人员的结果说明",
        safe_metadata={"phase": "response_rendering"},
        safe_input={
            "result_count": len(results),
            "needs_confirmation": needs_confirmation,
        },
    )
    if creation_ui.get("needs_input") and not any(
        isinstance(item.get("confirmation_payload"), dict)
        and item["confirmation_payload"].get("type") == "ask_account"
        for item in results
    ):
        reply, response_source = runtime.creation_ui_reply(creation_ui, safe_user_input), "creation_card"
    else:
        reply, response_source = runtime._render_response(
            safe_user_input,
            intent,
            results,
            needs_confirmation,
            analysis=analysis,
            session=session,
        )
    trace.stage_status(
        "reply",
        "回复生成",
        "succeeded",
        subtitle="已生成本轮回复",
        safe_metadata={"response_source": response_source},
        safe_output={
            "response_source": response_source,
            "available": True,
            "preview": runtime._redact_for_persistence(reply),
        },
    )
    trace.reply(needs_confirmation=needs_confirmation)
    has_failure = any(
        not item.get("success", False) and not item.get("skipped", False)
        for item in results
    )
    trace.done(
        "awaiting_confirmation" if needs_confirmation else "failed" if has_failure else "succeeded",
        safe_metadata={"tool_count": len(results)},
    )

    # Step 6: 记录消息历史
    runtime.persist_conversation_turn(
        session, turn_id, safe_user_input, reply,
        execution_trace=trace, ui=creation_ui,
    )

    return {
        "session_id": session_id,
        "run_id": run_id,
        "turn_id": turn_id,
        "timestamp": datetime.now().isoformat(),
        "intent": intent.to_dict(),
        "tool_plan": {k: [t.name for t in v] for k, v in tool_plan.items()},
        "tool_selection": {
            "tool_count": tool_selection["tool_count"],
            "tools": [tool.name for tool in tool_selection["selected_tools"]],
            "platforms": tool_selection["namespaces"],
            "context": tool_selection["context"],
            "tool_prompt": tool_selection["tool_prompt"],
            "expert_knowledge": tool_selection["expert_knowledge"],
            "knowledge": tool_selection.get("knowledge", []),
        },
        "memory": recalled_memories,
        "memory_updates": memory_updates,
        "response_source": response_source,
        "execution_plan": execution_plan.to_dict(),
        "results": results,
        "resource_results": resource_results,
        "workflow_id": workflow_id,
        **(
            feature.preflight_payload(creation_preflight)
            if creation_preflight is not None
            and callable(getattr(feature, "preflight_payload", None))
            else (
                {"preflight": creation_preflight.to_dict()}
                if creation_preflight is not None
                else {}
            )
        ),
        **(analysis if isinstance(analysis, dict) else {}),
        "reply": reply,
        "needs_confirmation": needs_confirmation,
        "confirmation_payload": confirmation_payload,
        "ui": creation_ui,
    }
