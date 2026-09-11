"""Advertising application turn engine.

The generic Runtime Kernel delegates here after it has completed request
normalization and session concurrency control. This module owns application
workflow policy, not generic Runtime infrastructure.
"""

from __future__ import annotations

import copy
import logging
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Mapping, Optional

from ..domain.ad.auth import RequestPrincipal
from ..core.execution_plan import ExecutionPlan
from ..core.execution_trace import ExecutionEventCallback, ExecutionTrace
from ..persistence.models import ExecutionRunRecord
from .ad_turn_context import AdTurnContextService
from .ad_turn_planning import AdTurnPlanningService
from .ad_tool_execution import AdToolExecutionService
from .ad_turn_result import AdTurnResultService

logger = logging.getLogger(__name__)

# These services are stateless. Reuse one instance per process so request
# handling does not repeatedly construct orchestration objects.
_TURN_CONTEXT = AdTurnContextService()
_TURN_PLANNER = AdTurnPlanningService()
_TOOL_EXECUTION = AdToolExecutionService()
_TURN_RESULT = AdTurnResultService()

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

    def finalize_run(status: str, metadata: Optional[Mapping[str, Any]] = None) -> None:
        """Best-effortly close the durable run for every terminal branch."""
        if not durable_run:
            return
        try:
            merged_metadata = None
            if metadata:
                current = runtime._session_manager.get_execution_run(run_id)
                current_metadata = getattr(current, "metadata", {}) if current else {}
                merged_metadata = {
                    **(current_metadata if isinstance(current_metadata, dict) else {}),
                    **dict(metadata),
                }
            runtime._session_manager.update_execution_run(
                run_id, status=status, metadata=merged_metadata,
            )
        except Exception:
            # A missing final update is observable through the run event repair
            # path and must never replace the user-facing result.
            logger.debug("failed to finalize execution run", exc_info=True)

    input_error = runtime._validate_request_limits(user_input, platform_params)
    if input_error:
        trace.error(reason="request_invalid")
        trace.done("failed", safe_metadata={"reason": "request_invalid"})
        finalize_run("failed", {"reason": "request_invalid"})
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
        finalize_run("failed", {"reason": "protected_input"})
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

    # Memory and Skill context are advisory only. The dedicated context
    # service owns their bounded retrieval and keeps this module focused on
    # turn orchestration and application lifecycle decisions.
    turn_context = _TURN_CONTEXT.prepare(
        runtime=runtime,
        session=session,
        session_id=session_id,
        user_id=user_id,
        tenant_id=tenant_id,
        safe_user_input=safe_user_input,
        trace=trace,
    )
    recalled_memories = turn_context.recalled_memories
    memory_updates = turn_context.memory_updates

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
        safe_input={"request_length": len(safe_user_input)},
    )
    try:
        intent = runtime.intent_parser.parse(safe_user_input, session.ctx)
    except Exception as exc:
        # A model/structured-output failure must not leave a durable run in
        # ``running`` forever. Keep the response generic and persist only the
        # exception class; raw provider/model text may contain sensitive data.
        trace.stage_status(
            "intent", "Intent 识别", "failed",
            subtitle="暂时无法完成意图解析",
            safe_metadata={"error_type": type(exc).__name__},
        )
        trace.reply()
        trace.done("failed", safe_metadata={"reason": "intent_parse_failed"})
        reply = "暂时无法完成请求理解，请稍后重试。"
        runtime.persist_conversation_turn(
            session, turn_id, safe_user_input, reply, execution_trace=trace,
        )
        finalize_run("failed", {"reason": "intent_parse_failed", "error_type": type(exc).__name__})
        return {
            "session_id": session_id, "run_id": run_id, "turn_id": turn_id,
            "timestamp": datetime.now().isoformat(), "intent": None,
            "tool_plan": {}, "execution_plan": {}, "tool_selection": None,
            "results": [], "reply": reply, "needs_confirmation": False,
            "confirmation_payload": None,
            "policy_errors": ["intent parsing failed"],
        }
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
        finalize_run("failed", {"reason": "protected_input"})
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
        finalize_run(
            "awaiting_confirmation" if needs_input else "succeeded" if success else "failed",
        )
        return {
            "session_id": session_id, "run_id": run_id, "turn_id": turn_id,
            "timestamp": datetime.now().isoformat(), "intent": intent.to_dict(),
            "tool_plan": {}, "execution_plan": {}, "tool_selection": None,
            "results": [{"success": success, **{key: value for key, value in control_result.items() if key != "reply"}}],
            "reply": reply, "needs_confirmation": needs_input,
            "needs_input": needs_input, "confirmation_payload": None,
            "workflow_id": None, "ui": {"type": "schedule", **control_result},
        }
    # Refresh only the model-facing Skill slice after parsing. Routing stays
    # authoritative and is deliberately outside the context service.
    _TURN_CONTEXT.enrich(
        runtime=runtime,
        session=session,
        safe_user_input=safe_user_input,
        intent=intent,
        tenant_id=tenant_id,
        context=turn_context,
        trace=trace,
    )

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
            finalize_run("failed", {"reason": "protected_input"})
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
        finalize_run("failed", {"reason": "policy_blocked"})
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
    routing = _TURN_PLANNER.route(
        runtime=runtime,
        intent=intent,
        safe_user_input=safe_user_input,
        session=session,
        creation_blueprint_id=creation_blueprint_id,
        creation_blueprint_version=creation_blueprint_version,
    )
    intent = routing.intent
    tool_plan = routing.tool_plan
    if routing.policy_errors:
        reply = "❌ 业务策略阻止本次请求：" + "；".join(routing.policy_errors)
        trace.stage_status(
            "skill_selection",
            "Skill 选择",
            "failed",
            subtitle="当前请求不满足已注册能力策略",
            safe_metadata={"reason": "policy_blocked"},
        )
        trace.reply()
        trace.done("failed", safe_metadata={"reason": "policy_blocked"})
        runtime.persist_conversation_turn(
            session, turn_id, safe_user_input, reply, execution_trace=trace,
        )
        finalize_run("failed", {"reason": "policy_blocked"})
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
            "policy_errors": routing.policy_errors,
        }
    if routing.blueprint_error:
        reply = "这份广告创建草稿暂时无法继续：" + routing.blueprint_error
        trace.error(reason="creation_blueprint_invalid")
        trace.done("failed", safe_metadata={"reason": "creation_blueprint_invalid"})
        runtime.persist_conversation_turn(
            session, turn_id, safe_user_input, reply, execution_trace=trace,
        )
        finalize_run("failed", {"reason": "creation_blueprint_invalid"})
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
            "policy_errors": [routing.blueprint_error],
            "ui": {},
        }

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
        finalize_run("awaiting_confirmation")
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
        finalize_run("failed", {"reason": "parameter_contract"})
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
            finalize_run("failed", {"reason": "creation_validation_failed"})
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
            finalize_run("failed", {"reason": "preflight_blocked"})
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
        runtime.persist_conversation_turn(
            session, turn_id, safe_user_input,
            str((batch_result or {}).get("reply") or "批量任务已处理。")
            if isinstance(batch_result, dict) else "批量任务已处理。",
            execution_trace=trace,
        )
        finalize_run(
            "awaiting_confirmation"
            if isinstance(batch_result, dict) and batch_result.get("needs_confirmation")
            else "succeeded",
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
        finalize_run(
            "failed" if has_structured_request or intent_type != "chat" else "succeeded",
            {"reason": "no_tool"},
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

    # Step 4: execute the already-planned Tool graph.
    tool_execution = _TOOL_EXECUTION.execute(
        runtime=runtime,
        run_id=run_id,
        tool_plan=tool_plan,
        execution_groups=execution_groups,
        session=session,
        request_clients=request_clients,
        session_id=session_id,
        user_input=safe_user_input,
        safe_user_input=safe_user_input,
        user_id=user_id,
        account_id=account_id,
        account_scope=account_scope,
        effective_permissions=effective_permissions,
        intent=intent,
        confirmed=confirmed,
        incoming_confirmation_payload=incoming_confirmation_payload,
        creation_blueprint_id=creation_blueprint_id,
        creation_blueprint_version=creation_blueprint_version,
        cancellation_event=cancellation_event,
        turn_deadline=turn_deadline,
        turn_id=turn_id,
        trace=trace,
        execution_plan=execution_plan,
    )
    workflow_id = tool_execution.workflow_id
    results = tool_execution.results
    needs_confirmation = tool_execution.needs_confirmation
    confirmation_payload = tool_execution.confirmation_payload
    workflow_inputs = tool_execution.workflow_inputs

    return _TURN_RESULT.complete(
        runtime=runtime,
        feature=feature,
        intent=intent,
        tool_plan=tool_plan,
        results=results,
        session=session,
        turn_id=turn_id,
        request_clients=request_clients,
        account_scope=account_scope,
        effective_permissions=effective_permissions,
        workflow_id=workflow_id,
        workflow_inputs=workflow_inputs,
        trace=trace,
        creation_ui=creation_ui,
        safe_user_input=safe_user_input,
        needs_confirmation=needs_confirmation,
        confirmation_payload=confirmation_payload,
        creation_preflight=creation_preflight,
        recalled_memories=recalled_memories,
        memory_updates=memory_updates,
        tool_selection=tool_selection,
        execution_plan=execution_plan,
        session_id=session_id,
        run_id=run_id,
        finalize_run=finalize_run,
    )
