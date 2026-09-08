"""Cross-channel feature implementation.

This module owns cross-channel business orchestration.  It consumes a narrow
Runtime service object for generic execution, persistence and policy gates;
the Runtime itself does not decide what "cross-channel" means.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Mapping, Optional

from ..core.cross_channel import (
    CreationPreflight,
    CreationPreflightItem,
    CrossChannelAggregator,
    CrossChannelAnalyzer,
    build_batch_operations,
)
from ..core.tool_registry import validate_tool_input
from ..core.interfaces import ToolContext
from ..core.platform import normalize_platform


class CrossChannelFeature:
    """Provider-neutral cross-channel campaign and reporting workflows."""

    feature_name = "cross-channel"

    BATCH_INTENTS = frozenset({
        "cross_channel_batch_pause",
        "cross_channel_batch_resume",
        "cross_channel_batch_update_budget",
        "cross_channel_batch_delete",
    })
    ANALYSIS_INTENTS = frozenset({
        "cross_channel_compare",
        "cross_channel_performance_insights",
        "cross_channel_optimize_budget",
        "cross_channel_export_report",
    })

    _INTENT_DESCRIPTORS = {
        "cross_channel_overview": {
            "description": "查看多个已注册渠道的广告概览",
            "aliases": [
                "跨渠道概览", "跨平台概览", "跨渠道查询", "跨平台查询",
                "channel overview", "cross channel overview",
            ],
        },
        "cross_channel_compare": {
            "description": "比较多个已注册渠道的广告表现",
            "priority": 100,
            "aliases": [
                "跨渠道对比", "跨平台比较", "比较多个渠道", "比较多个平台",
                "比较渠道", "对比渠道", "比较",
                "channel comparison", "cross channel compare",
            ],
        },
        "cross_channel_performance_insights": {
            "description": "生成多个渠道的表现洞察和优化建议",
            "priority": 100,
            "aliases": ["跨渠道分析", "跨平台洞察", "performance insights", "cross channel analysis"],
        },
        "cross_channel_optimize_budget": {
            "description": "在多个渠道之间制定预算优化建议",
            "priority": 100,
            "aliases": [
                "跨渠道预算优化", "跨渠道优化预算", "跨平台预算分配",
                "budget optimization",
            ],
        },
        "cross_channel_export_report": {
            "description": "导出多个渠道的汇总报表",
            "priority": 100,
            "aliases": [
                "跨渠道导出报表", "跨渠道导出", "跨平台报表导出",
                "export cross channel report",
            ],
        },
        "cross_channel_batch_pause": {
            "description": "批量暂停多个渠道的资源",
            "priority": 100,
            "aliases": [
                "跨渠道批量暂停", "跨平台批量停用", "跨渠道暂停", "跨平台暂停",
                "批量暂停", "批量停用", "batch pause",
            ],
        },
        "cross_channel_batch_resume": {
            "description": "批量恢复多个渠道的资源",
            "priority": 100,
            "aliases": ["跨渠道批量恢复", "跨平台批量启用", "跨渠道恢复", "批量恢复", "批量启用", "batch resume"],
        },
        "cross_channel_batch_update_budget": {
            "description": "批量更新多个渠道的预算",
            "priority": 100,
            "aliases": ["跨渠道批量更新预算", "跨平台预算更新", "批量更新预算", "batch update budget"],
        },
        "cross_channel_batch_delete": {
            "description": "批量删除多个渠道的资源",
            "priority": 100,
            "aliases": ["跨渠道批量删除", "跨平台批量移除", "跨渠道删除", "批量删除", "batch delete"],
        },
    }

    def intent_descriptors(self) -> dict[str, dict[str, Any]]:
        return {
            intent: {**descriptor, "aliases": list(descriptor.get("aliases", []))}
            for intent, descriptor in self._INTENT_DESCRIPTORS.items()
        }

    def can_handle(self, intent: Any) -> bool:
        intent_type = str(getattr(intent, "intent_type", "") or "")
        if intent_type in self.BATCH_INTENTS or intent_type in self.ANALYSIS_INTENTS:
            return True
        return self.is_multi_platform_create(intent)

    def is_batch_intent(self, intent: Any) -> bool:
        return str(getattr(intent, "intent_type", "") or "") in self.BATCH_INTENTS

    def handles_analysis(self, intent: Any) -> bool:
        """Declare whether this Feature owns the result-analysis phase."""
        return str(getattr(intent, "intent_type", "") or "") in self.ANALYSIS_INTENTS

    def handles_creation_preflight(self, intent: Any) -> bool:
        return self.is_multi_platform_create(intent)

    @staticmethod
    def preflight_failure_reply(_intent: Any, _preflight: Any) -> str:
        errors = list(getattr(_preflight, "errors", ()) or ())
        if any("缺少账户ID" in str(error) for error in errors):
            return "请先提供每个投放渠道对应的广告账户 ID，再继续创建。"
        return (
            "跨渠道创建 preflight 未通过；已停止所有渠道的创建。"
            "请先补齐各渠道/层级的参数后重试。"
        )

    @staticmethod
    def preflight_payload(preflight: CreationPreflight) -> dict[str, Any]:
        return {"creation_preflight": preflight.to_dict()}

    @classmethod
    def is_multi_platform_create(
        cls, intent: Any, runtime: Any = None
    ) -> bool:
        canonicalize = (
            runtime.canonical_platform
            if runtime is not None
            else normalize_platform
        )
        platforms = {
            canonicalize(platform)
            for platform in (getattr(intent, "platforms", []) or [])
        }
        return (
            getattr(intent, "intent_type", "") == "create_campaign"
            and len(platforms) > 1
        )

    @staticmethod
    def select_batch_campaign_tool(
        tools: Iterable[Any], intent_type: str, runtime: Any,
    ) -> Optional[Any]:
        """Select a unique provider Campaign Tool from its metadata."""
        batch_action = (
            "delete" if intent_type == "cross_channel_batch_delete" else "update"
        )
        candidates = [
            tool for tool in (tools or [])
            if str(getattr(tool, "action", "") or "").lower() == batch_action
            and str(getattr(tool, "resource_type", "") or "").lower() == "campaign"
        ]
        exact = [
            tool for tool in candidates
            if intent_type in (getattr(tool, "intent_types", []) or [])
        ]
        candidates = exact or candidates
        if intent_type == "cross_channel_batch_update_budget":
            candidates = [
                tool for tool in candidates
                if isinstance(
                    (getattr(tool.input_schema, "properties", {}) or {}).get(
                        "updates", {}
                    ),
                    dict,
                )
                and bool({
                    "budget", "daily_budget",
                }.intersection(
                    (
                        getattr(tool.input_schema, "properties", {}) or {}
                    ).get("updates", {}).get("properties", {})
                ))
            ]
        if len(candidates) == 1:
            return candidates[0]
        batch_candidates = [
            tool for tool in candidates
            if "batch" in {
                str(trait or "").strip().lower()
                for trait in (getattr(tool, "traits", []) or [])
            }
        ]
        return batch_candidates[0] if len(batch_candidates) == 1 else None

    @classmethod
    def preflight_creation(
        cls,
        services: Any,
        intent: Any,
        tool_plan: dict[str, list[Any]],
        session: Any,
        account_id: Optional[str],
        account_scope: Optional[Mapping[str, Any]],
        granted_permissions: Optional[set[str] | frozenset[str]],
    ) -> CreationPreflight:
        """Validate every requested creation chain before any Tool runs."""
        items: list[CreationPreflightItem] = []
        errors: list[str] = []
        routes_by_platform: dict[str, tuple[str, list[Any]]] = {}
        for raw_platform, tools in tool_plan.items():
            canonical = services.canonical_platform(raw_platform)
            routes_by_platform.setdefault(canonical, (raw_platform, tools))

        for requested_platform in intent.platforms:
            platform = services.canonical_platform(requested_platform)
            route = routes_by_platform.get(platform)
            if route is None or not route[1]:
                message = f"{platform}: 没有已注册的 create_campaign Tool"
                errors.append(message)
                items.append(CreationPreflightItem(
                    platform=platform,
                    tool_name="<creation_chain>",
                    resource_type=None,
                    parent_resource_type=None,
                    status="blocked",
                    errors=(message,),
                ))
                continue

            raw_platform, tools = route
            account = services.resolve_account(
                intent, raw_platform, tools, account_id
            )

            account_errors: list[str] = []
            if not account:
                account_errors.append(f"{platform}: 缺少账户ID")
            else:
                allowed, account_error = services.validate_account(
                    platform, account, True, account_scope
                )
                if not allowed:
                    account_errors.append(f"{platform}: {account_error}")

            preflight_ctx = ToolContext(
                session_id=session.session_id,
                user_id=session.ctx.user_id,
                account_id=account,
                credentials={},
            )
            prior_failed: Optional[str] = None
            for tool_def in tools:
                tool_errors = list(account_errors)
                missing_fields: list[str] = []
                tool_input: dict[str, Any] = {}
                if not account_errors:
                    tool_input = services.input_builder.build(
                        tool_def, intent, raw_platform, preflight_ctx
                    )
                    missing_fields = list(
                        tool_input.pop("_missing_params", []) or []
                    )
                    unknown_params = list(
                        tool_input.pop("_unknown_params", []) or []
                    )
                    selection_errors = list(
                        tool_input.pop("_selection_errors", []) or []
                    )
                    if missing_fields:
                        tool_errors.extend(
                            f"缺少必需参数: {field}" for field in missing_fields
                        )
                    if unknown_params:
                        tool_errors.append(
                            "工具参数契约不支持以下字段：" + ", ".join(unknown_params)
                        )
                    if selection_errors:
                        tool_errors.append(
                            "参数选择凭证无效：" + "; ".join(selection_errors)
                        )
                    protected_paths = services.validate_input_redline(
                        tool_input
                    )
                    if protected_paths:
                        tool_errors.append(
                            "请求包含禁止传入的凭证/账户配置字段："
                            + ", ".join(protected_paths)
                        )
                    if tool_def.is_write_tool:
                        schema = tool_def.input_schema
                        missing_fields.extend(
                            field_name
                            for field_name in (schema.provider_required or [])
                            if tool_input.get(field_name) in (None, "")
                            and field_name not in missing_fields
                        )
                        for alternatives in (schema.provider_any_of or []):
                            if not any(
                                tool_input.get(field_name)
                                not in (None, "", {}, [])
                                for field_name in alternatives
                            ):
                                missing_fields.append(
                                    "one_of(" + ", ".join(alternatives) + ")"
                                )
                        tool_errors.extend(
                            services.validate_tool_input(tool_def, tool_input)
                        )
                        tool_errors.extend(
                            validate_tool_input(
                                tool_def.input_schema,
                                tool_input,
                                include_provider_contract=True,
                            )
                        )
                        if services.execution_mode == "live":
                            if not services.allow_live_writes:
                                tool_errors.append("Runtime 全局 allow_live_writes 未开启")
                            elif not tool_def.live_support:
                                tool_errors.append("该 Tool 当前仅支持 dry-run")
                            elif tool_def.name not in services.live_approved_tools:
                                tool_errors.append("该 Tool 未加入 live 执行批准清单")
                            if services.write_guard is None:
                                tool_errors.append("live 写操作必须配置 WriteGuard")
                if prior_failed:
                    tool_errors.append(f"前置 Tool {prior_failed} 未通过 preflight")

                normalized_errors = tuple(
                    dict.fromkeys(str(error) for error in tool_errors)
                )
                status = "blocked" if normalized_errors else "ready"
                items.append(CreationPreflightItem(
                    platform=platform,
                    tool_name=tool_def.name,
                    resource_type=getattr(tool_def, "resource_type", None),
                    parent_resource_type=getattr(
                        tool_def, "parent_resource_type", None
                    ),
                    status=status,
                    account_id=account,
                    missing_fields=tuple(dict.fromkeys(missing_fields)),
                    errors=normalized_errors,
                ))
                if normalized_errors and prior_failed is None:
                    prior_failed = tool_def.name
                resource_type = str(
                    getattr(tool_def, "resource_type", "") or ""
                )
                if resource_type:
                    resource_field = services.resource_id_field(tool_def)
                    placeholder = f"preflight:{platform}:{resource_type}"
                    preflight_ctx.protected_state[resource_field] = placeholder
                    preflight_ctx.protected_state[
                        f"{platform}:{resource_field}"
                    ] = placeholder

        unique_errors = tuple(dict.fromkeys(errors + [
            error
            for item in items
            for error in item.errors
            if error and error not in errors
        ]))
        return CreationPreflight(
            ready=not unique_errors,
            items=tuple(items),
            errors=unique_errors,
        )

    @staticmethod
    def preflight_results(preflight: CreationPreflight) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for item in preflight.items:
            error = "; ".join(item.errors) if item.errors else None
            account_required = any(
                "缺少账户ID" in str(value) for value in item.errors
            )
            results.append({
                "tool": item.tool_name,
                "platform": item.platform,
                "resource_type": item.resource_type,
                "parent_resource_type": item.parent_resource_type,
                "account_id": item.account_id,
                "success": False,
                "data": {
                    "preflight": True,
                    "status": item.status,
                    "execution_status": "skipped_before_execution",
                    "missing_fields": list(item.missing_fields),
                    "errors": list(item.errors),
                },
                "error": error,
                "needs_confirmation": account_required,
                "confirmation_payload": ({
                    "type": "ask_account",
                    "platform": item.platform,
                    "question": f"请提供要操作的 {item.platform} 广告账户 ID。",
                } if account_required else None),
                "preflight": True,
                "skipped": True,
            })
        return results

    @classmethod
    def run_batch_plan(
        cls,
        services: Any,
        user_input: str,
        session: Any,
        turn_id: str,
        intent: Any,
        tool_plan: dict[str, list[Any]],
        account_id: Optional[str],
        workflow_id: Optional[str],
        account_scope: Optional[Mapping[str, Any]] = None,
        granted_permissions: Optional[set[str] | frozenset[str]] = None,
    ) -> dict[str, Any]:
        """Build a provider-neutral, auditable batch plan."""
        accounts: dict[str, str] = {}
        errors: list[str] = []
        tool_by_platform: dict[str, Any] = {
            services.canonical_platform(platform): cls.select_batch_campaign_tool(
                tools, intent.intent_type, services
            )
            for platform, tools in tool_plan.items()
        }
        tools_by_platform = {
            services.canonical_platform(platform): tools
            for platform, tools in tool_plan.items()
        }
        blocked_platforms: set[str] = set()

        for requested_platform in intent.platforms:
            actual_platform = services.canonical_platform(requested_platform)
            if actual_platform not in tools_by_platform:
                errors.append(f"{actual_platform}: 没有已注册的 Campaign 批量管理工具")
                blocked_platforms.add(actual_platform)
            elif tool_by_platform.get(actual_platform) is None:
                errors.append(f"{actual_platform}: 没有唯一兼容的 Campaign 批量管理工具")
                blocked_platforms.add(actual_platform)

        for actual_platform, tool_def in tool_by_platform.items():
            if tool_def is None:
                continue
            raw_platform = next(
                (
                    platform for platform in tool_plan
                    if services.canonical_platform(platform) == actual_platform
                ),
                actual_platform,
            )
            resolved = services.resolve_account(
                intent, raw_platform, [tool_def], account_id
            )
            allowed, error = services.validate_account(
                actual_platform, resolved, True, account_scope
            )
            if not allowed:
                errors.append(f"{actual_platform}: {error}")
                blocked_platforms.add(actual_platform)
                continue
            permission_error = services.check_tool_permissions(
                tool_def, granted_permissions
            )
            if permission_error:
                errors.append(f"{actual_platform}: {permission_error}")
                blocked_platforms.add(actual_platform)
                continue
            accounts[actual_platform] = resolved

        supported_platforms = {
            platform for platform, tool in tool_by_platform.items()
            if tool is not None
        }
        operations, planning_errors = build_batch_operations(
            intent,
            accounts,
            supported_platforms=supported_platforms,
            blocked_platforms=blocked_platforms,
        )
        errors = list(dict.fromkeys(errors + planning_errors))
        results: list[dict] = []
        workflow_inputs: dict[int, dict] = {}
        if len(operations) > services.max_tool_calls:
            errors.append(
                "批量操作数量超过本回合上限："
                f"最多允许 {services.max_tool_calls} 项"
            )
            operations = []

        tool_name_by_platform = {
            platform: tool.name
            for platform, tool in tool_by_platform.items()
            if tool is not None
        }
        for message in errors:
            platform = message.split(":", 1)[0]
            results.append({
                "tool": tool_name_by_platform.get(platform, "cross_channel_batch"),
                "platform": platform,
                "success": False,
                "data": {"batch": True, "planned": False},
                "error": message,
                "needs_confirmation": "缺少账户ID" in message,
                "confirmation_payload": ({
                    "type": "ask_account",
                    "platform": platform,
                    "question": f"请提供要操作的 {platform} 广告账户 ID。",
                } if "缺少账户ID" in message else None),
                "batch_planning_error": True,
            })

        operation_sequence = 0
        for operation in operations:
            services.heartbeat(workflow_id)
            tool_name = tool_name_by_platform.get(operation.platform)
            if not tool_name:
                results.append({
                    "tool": "cross_channel_batch",
                    "platform": operation.platform,
                    "success": False,
                    "data": {"batch": True, "planned": False},
                    "error": (
                        "该平台没有唯一兼容的 Campaign 批量管理工具"
                        if tools_by_platform.get(operation.platform)
                        else "该平台没有已注册的 Campaign 批量管理工具"
                    ),
                    "batch_planning_error": True,
                })
                continue
            tool_def = tool_by_platform.get(operation.platform)
            operation_sequence += 1
            resource_id_field = services.resource_id_field(tool_def)
            tool_input = {resource_id_field: operation.campaign_id}
            if operation.action != "delete":
                tool_input["updates"] = services.input_builder.normalize_provider_updates(
                    tool_def, operation.updates
                )
            properties = getattr(tool_def.input_schema, "properties", {}) or {}
            for account_field in ("account_id", "advertiser_id", "customer_id"):
                if account_field in properties:
                    tool_input[account_field] = operation.account_id
                    break
            if workflow_id and services.session_manager:
                services.session_manager.record_workflow_item(
                    workflow_id=workflow_id,
                    sequence=operation_sequence,
                    platform=services.canonical_platform(operation.platform),
                    tool_name=tool_name,
                    status="running",
                    input_data=services.redact(tool_input),
                    account_id=operation.account_id,
                    resource_type=getattr(tool_def, "resource_type", None),
                    parent_resource_type=getattr(
                        tool_def, "parent_resource_type", None
                    ),
                )
            result_index = len(results)
            workflow_inputs[result_index] = tool_input
            protected_paths = services.validate_input_redline(tool_input)
            if protected_paths:
                results.append({
                    "tool": tool_name,
                    "platform": operation.platform,
                    "account_id": operation.account_id,
                    "success": False,
                    "data": {"batch": True, "planned": False},
                    "error": "请求包含禁止传入的凭证/账户配置字段："
                    + ", ".join(protected_paths),
                    "workflow_sequence": operation_sequence,
                })
                continue
            schema_errors = validate_tool_input(tool_def.input_schema, tool_input)
            if schema_errors:
                results.append({
                    "tool": tool_name,
                    "platform": operation.platform,
                    "account_id": operation.account_id,
                    "success": False,
                    "data": {"batch": True, "planned": False},
                    "error": f"Input validation failed: {schema_errors}",
                    "workflow_sequence": operation_sequence,
                })
                continue
            simulated = services.simulate_write(
                tool_def, tool_input, services.canonical_platform(operation.platform)
            )
            data = dict(simulated.data)
            data.update({
                "batch": True,
                "planned": True,
                "action": operation.action,
                "account_id": operation.account_id,
                "campaign_ref": operation.campaign_ref.to_dict(),
                "campaign_id": operation.campaign_id,
            })
            live_batch = services.execution_mode == "live"
            if live_batch:
                data.update({"mode": "live", "execution_status": "unsupported"})
            results.append({
                "tool": tool_name,
                "platform": operation.platform,
                "account_id": operation.account_id,
                "success": not live_batch,
                "data": data,
                "error": (
                    "跨渠道批量 Campaign 更新当前仅支持 dry-run，未调用线上 API"
                    if live_batch else None
                ),
                "needs_confirmation": False,
                "workflow_sequence": operation_sequence,
            })

        account_requests = [
            item for item in results
            if "缺少账户ID" in str(item.get("error") or "")
        ]
        needs_confirmation = bool(account_requests)
        reply = services.response_renderer.render(
            intent, results, needs_confirmation
        )
        services.persist_conversation_turn(session, turn_id, user_input, reply)
        services.finish_workflow(
            workflow_id, tool_plan, results, workflow_inputs,
            planning_errors=errors,
        )
        resource_results = services.build_resource_results(results)
        return {
            "session_id": session.session_id,
            "turn_id": turn_id,
            "timestamp": datetime.now().isoformat(),
            "intent": intent.to_dict(),
            "tool_plan": {key: [tool.name for tool in tools]
                          for key, tools in tool_plan.items()},
            "results": results,
            "resource_results": resource_results,
            "workflow_id": workflow_id,
            "reply": reply,
            "needs_confirmation": needs_confirmation,
            "confirmation_payload": ({
                "type": "ask_account",
                "platform": account_requests[0].get("platform"),
                "question": (
                    f"请提供要操作的 {account_requests[0].get('platform', '对应渠道')} "
                    "广告账户 ID。"
                ),
            } if account_requests else None),
        }

    @classmethod
    def collect_metrics(
        cls,
        services: Any,
        intent: Any,
        tool_plan: dict[str, list[Any]],
        results: list[dict],
        session: Any,
        turn_id: str,
        request_clients: Optional[dict[str, Any]] = None,
        account_scope: Optional[Mapping[str, Any]] = None,
        granted_permissions: Optional[set[str] | frozenset[str]] = None,
        execution_trace: Optional[Any] = None,
    ) -> None:
        """Run the second, read-only reporting phase for comparisons."""
        if intent.intent_type not in cls.ANALYSIS_INTENTS:
            return
        already_collected = {item.get("tool") for item in results}
        listing_results = {
            item.get("platform"): item
            for item in results
            if item.get("success")
            and item.get("action") == "list"
            and item.get("resource_type") == "campaign"
            and item.get("result_items_key")
        }
        for platform, listing in listing_results.items():
            report_def = cls._find_campaign_report_tool(services, platform)
            if not report_def or report_def.name in already_collected:
                continue
            listing_data = (
                listing.get("data")
                if isinstance(listing.get("data"), dict) else {}
            )
            result_key = str(listing.get("result_items_key") or "").strip()
            campaigns = listing_data.get(result_key) or []
            result_id_fields = [
                str(field).strip()
                for field in (listing.get("result_id_fields") or [])
                if str(field).strip()
            ]
            campaign_ids: list[str] = []
            for campaign in campaigns if isinstance(campaigns, list) else []:
                if not isinstance(campaign, dict):
                    continue
                campaign_id = next(
                    (campaign.get(field) for field in result_id_fields
                     if campaign.get(field) not in (None, "")),
                    None,
                )
                if campaign_id is not None and str(campaign_id) not in campaign_ids:
                    campaign_ids.append(str(campaign_id))
            if not campaign_ids:
                continue
            tool_plan.setdefault(platform, []).append(report_def)
            per_platform_account = services.resolve_account(
                intent, platform, [report_def], session.ctx.account_id
            )
            actual_platform = services.canonical_platform(platform)
            permission_error = services.check_tool_permissions(
                report_def, granted_permissions
            )
            if permission_error:
                results.append({
                    "tool": report_def.name,
                    "platform": platform,
                    "success": False,
                    "error": permission_error,
                    "needs_confirmation": False,
                })
                continue
            allowed, account_error = services.validate_account(
                actual_platform, per_platform_account, False, account_scope
            )
            if not allowed:
                results.append({
                    "tool": report_def.name,
                    "platform": platform,
                    "success": False,
                    "error": f"指标采集账户校验失败: {account_error}",
                })
                continue
            platform_params = services.input_builder.platform_params_for_intent(
                intent, platform
            )
            report_input = {
                key: value
                for key, value in platform_params.items()
                if key in report_def.input_schema.properties
                and key not in set(report_def.related_resource_id_fields or [])
            }
            if getattr(intent, "date_range", None):
                if "date_range" in report_def.input_schema.properties:
                    report_input.setdefault("date_range", intent.date_range)
                if "date_preset" in report_def.input_schema.properties:
                    report_input.setdefault(
                        "date_preset",
                        services.input_builder.platform_date_range(
                            platform, intent.date_range, report_def, "date_preset"
                        ),
                    )
            related_fields = [
                str(field).strip()
                for field in (report_def.related_resource_id_fields or [])
                if str(field).strip() in report_def.input_schema.properties
            ]
            if not related_fields:
                results.append({
                    "tool": report_def.name,
                    "platform": platform,
                    "success": False,
                    "error": "报表 Tool 未声明关联资源 ID 输入字段",
                })
                continue
            related_field = related_fields[0]
            related_schema = report_def.input_schema.properties.get(related_field, {})
            related_type = (
                related_schema.get("type")
                if isinstance(related_schema, dict) else None
            )
            report_input[related_field] = (
                campaign_ids if related_type == "array" else campaign_ids[0]
            )
            for account_key in ("account_id", "advertiser_id", "customer_id"):
                if account_key in report_def.input_schema.properties:
                    report_input[account_key] = per_platform_account
                    break
            missing = validate_tool_input(report_def.input_schema, report_input)
            if missing:
                results.append({
                    "tool": report_def.name,
                    "platform": platform,
                    "success": False,
                    "error": f"指标采集参数不完整: {missing}",
                })
                continue
            original_account = session.ctx.account_id
            session.ctx.account_id = per_platform_account
            trace_node = None
            if execution_trace is not None:
                trace_node = execution_trace.register_dynamic_node(
                    actual_platform,
                    report_def.name,
                    action=getattr(report_def, "action", ""),
                    resource_type=getattr(report_def, "resource_type", ""),
                    parent_resource_type=getattr(report_def, "parent_resource_type", None),
                )
                execution_trace.node_status(
                    trace_node,
                    "running",
                    safe_input=services.redact(report_input),
                )
            try:
                report_result = services.execute_tool(
                    session.ctx, report_def.name, report_input, request_clients
                )
                results.append({
                    "tool": report_def.name,
                    "platform": platform,
                    "success": report_result.success,
                    "account_id": per_platform_account,
                    "data": services.redact(report_result.data),
                    "error": services.redact(report_result.error),
                    "needs_confirmation": report_result.requires_confirmation,
                })
                session.save_result(
                    report_def.name, report_result, platform=actual_platform
                )
                session.ctx.protected_state.update(session.protected_state)
                services.persist_tool_result(
                    session, turn_id, report_def, actual_platform,
                    report_input, report_result,
                )
                if trace_node is not None:
                    execution_trace.node_status(
                        trace_node,
                        "succeeded" if report_result.success else "failed",
                        safe_metadata={"simulated": bool(report_result.simulated)},
                        safe_input=services.redact(report_input),
                        safe_output={
                            "success": bool(report_result.success),
                            "data": services.redact(report_result.data),
                            "has_error": bool(report_result.error),
                        },
                    )
            except Exception as exc:
                results.append({
                    "tool": report_def.name,
                    "platform": platform,
                    "success": False,
                    "error": f"跨渠道指标采集失败: {exc}",
                })
                if trace_node is not None:
                    execution_trace.node_status(
                        trace_node, "failed", safe_metadata={"reason": "metrics_collection_failed"}
                    )
            finally:
                session.ctx.account_id = original_account

    @staticmethod
    def _find_campaign_report_tool(services: Any, platform: str):
        normalized = services.canonical_platform(platform)
        candidates = []
        for definition in services.registry.list_all():
            if services.canonical_platform(definition.platform) != normalized:
                continue
            if not definition.is_read_tool:
                continue
            properties = getattr(definition.input_schema, "properties", {}) or {}
            if str(getattr(definition, "related_resource_type", "") or "") != "campaign":
                continue
            if not any(
                str(field).strip() in properties
                for field in (getattr(definition, "related_resource_id_fields", []) or [])
            ):
                continue
            candidates.append(definition)
        if not candidates:
            return None
        return candidates[0] if len(candidates) == 1 else None

    @classmethod
    def analyze(cls, intent: Any, results: list[dict]) -> dict[str, Any]:
        """Return cross-channel analysis payloads for the response layer."""
        if intent.intent_type not in cls.ANALYSIS_INTENTS:
            return {}
        summary = CrossChannelAggregator().aggregate(results)
        result: dict[str, Any] = {"cross_channel_summary": summary}
        if intent.intent_type == "cross_channel_performance_insights":
            result["cross_channel_insights"] = (
                CrossChannelAnalyzer.performance_insights(summary)
            )
        elif intent.intent_type == "cross_channel_optimize_budget":
            params = getattr(intent, "platform_params", {}) or {}
            common = params.get("_common", {}) if isinstance(params, dict) else {}
            common = common if isinstance(common, dict) else {}
            result["cross_channel_budget_plan"] = CrossChannelAnalyzer.budget_plan(
                summary,
                getattr(intent, "budget", None),
                common.get("minimum_budget"),
                common.get("maximum_budget"),
            )
        elif intent.intent_type == "cross_channel_export_report":
            result["cross_channel_export"] = CrossChannelAnalyzer.export_csv(summary)
        return result
