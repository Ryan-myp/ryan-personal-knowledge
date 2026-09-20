"""Application-owned execution of a planned Tool graph.

This service is deliberately downstream of planning. It does not parse user
input, discover capabilities, choose a provider, or render a response. It
only applies the shared execution gates to a Tool plan and returns sanitized
application results for the turn orchestrator.
"""

from __future__ import annotations

import copy
import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Optional

from ..core.execution_trace import ExecutionEventCallback
from ..core.interfaces import ExecutionMode, ToolResult
from ..core.tool_registry import validate_tool_input

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolExecutionResult:
    """State produced by executing one already-planned Tool graph."""

    workflow_id: Optional[str]
    results: list[dict[str, Any]]
    needs_confirmation: bool
    confirmation_payload: Optional[dict[str, Any]]
    workflow_inputs: dict[int, dict[str, Any]]


class AdToolExecutionService:
    """Execute a planned graph through the advertising application's gates."""

    def execute(
        self,
        *,
        runtime: Any,
        run_id: str,
        tool_plan: dict[str, list[Any]],
        execution_groups: list[tuple[str, list[Any]]],
        session: Any,
        request_clients: Mapping[str, Any],
        session_id: str,
        user_input: str,
        safe_user_input: str,
        user_id: str,
        account_id: Optional[str],
        account_scope: Optional[Mapping[str, Any]],
        effective_permissions: frozenset[str] | set[str],
        intent: Any,
        confirmed: bool,
        incoming_confirmation_payload: Optional[dict[str, Any]],
        creation_blueprint_id: Optional[str],
        creation_blueprint_version: Optional[str],
        cancellation_event: Optional[threading.Event],
        turn_deadline: float,
        turn_id: str,
        trace: Any,
        execution_plan: Any,
    ) -> ToolExecutionResult:
        results: list[dict[str, Any]] = []
        needs_confirmation = False
        confirmation_payload: Optional[dict[str, Any]] = None
        workflow_id = runtime.workflow.start(
            session,
            intent,
            tool_plan,
            execution_plan=execution_plan,
        )
        runtime._bind_execution_run_workflow(run_id, workflow_id)
        workflow_inputs: dict[int, dict[str, Any]] = {}
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
            resolved_scope = runtime.account_resolver.resolve_scope(
                intent,
                tools,
                per_platform_account,
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

                if (
                    tool_def.is_write_tool
                    and runtime.execution_mode == ExecutionMode.LIVE.value
                ):
                    policy_decision = runtime._evaluate_tool_policy(
                        tool_def,
                        granted_permissions=effective_permissions,
                        scope=resolved_scope,
                        require_confirmation=False,
                    )
                    if not policy_decision.allowed:
                        reason = "; ".join(policy_decision.errors)
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
                    started_at=started_at,
                    ended_at=datetime.now().isoformat(),
                )

                # 恢复原始账户上下文
                session.ctx.account_id = original_account

        return ToolExecutionResult(
            workflow_id=workflow_id,
            results=results,
            needs_confirmation=needs_confirmation,
            confirmation_payload=confirmation_payload,
            workflow_inputs=workflow_inputs,
        )

__all__ = ["AdToolExecutionService", "ToolExecutionResult"]
