"""Metadata-only scheduled prompt preflight for the advertising application."""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

logger = logging.getLogger(__name__)


class AdSchedulingPreflightMixin:
    def preflight_scheduled_prompt(
        self,
        prompt: str,
        *,
        session_id: str,
        platforms: Optional[list[str]] = None,
        account_id: Optional[str] = None,
        platform_params: Optional[dict[str, Any]] = None,
        permissions: Optional[set[str] | frozenset[str]] = None,
        account_scope: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        """Check a scheduled instruction without calling a Tool or Provider."""
        text = str(prompt or "").strip()
        if not text:
            return {
                "status": "needs_input",
                "missing": ["instruction"],
                "reason": "请补充到期后要执行的具体指令。",
            }
        session = self._sessions.get(str(session_id or ""))
        if session is None:
            return {
                "status": "needs_input",
                "missing": ["session"],
                "reason": "当前会话上下文尚未准备好，无法完成能力预检。",
            }
        try:
            candidate = self.intent_parser.parse(text, session.ctx)
        except Exception as exc:
            logger.info("scheduled prompt preflight parse failed", exc_info=True)
            return {
                "status": "unsupported",
                "missing": [],
                "reason": "无法识别定时任务到期后的具体业务动作，请说明查询、分析、创建或其他动作。",
                "parse_error": type(exc).__name__,
            }
        supplied_platforms = [
            str(item).strip() for item in (platforms or []) if str(item).strip()
        ]
        if supplied_platforms:
            candidate.namespaces = list(dict.fromkeys(supplied_platforms))
        if platform_params:
            merged_params = dict(getattr(candidate, "scoped_parameters", {}) or {})
            for platform, values in platform_params.items():
                if isinstance(values, dict):
                    merged = dict(merged_params.get(platform, {}) or {})
                    merged.update(values)
                    merged_params[str(platform)] = merged
            candidate.scoped_parameters = merged_params
        is_control_intent = any(
            bool(getattr(feature, "is_control_intent", lambda _intent: False)(candidate))
            for feature in self.features
        )
        if str(getattr(candidate, "intent_type", "") or "") == "chat" or is_control_intent:
            return {
                "status": "needs_input",
                "missing": ["action"],
                "reason": "请明确到期后要执行的业务动作，例如查询资源 performance 或创建资源。",
            }
        if not candidate.namespaces:
            return {
                "status": "needs_input",
                "missing": ["platform"],
                "reason": "请明确一个当前已注册的执行渠道，或说明需要跨渠道处理。",
                "intent_type": candidate.intent_type,
            }
        plan = self.intent_router.route(candidate, self.registry)
        if not plan:
            return {
                "status": "unsupported",
                "missing": [],
                "reason": "当前已注册的 Tool/Tool Source 没有匹配该动作和渠道的执行能力。",
                "intent_type": candidate.intent_type,
                "platforms": list(candidate.namespaces),
            }
        account_values = []
        if account_id not in (None, ""):
            account_values.append(str(account_id))
        for values in (getattr(candidate, "scoped_parameters", {}) or {}).values():
            if not isinstance(values, dict):
                continue
            for field_name in ("account_id", "advertiser_id", "customer_id"):
                if values.get(field_name) not in (None, ""):
                    account_values.append(str(values[field_name]))
        account_values = list(dict.fromkeys(account_values))
        if len(account_values) > 1:
            return {
                "status": "needs_input",
                "missing": ["account"],
                "reason": "请求中出现多个不同广告账户，请明确每个渠道使用的账户。",
                "intent_type": candidate.intent_type,
                "platforms": list(plan),
                "account_candidates": account_values[:10],
            }
        matched_tools = [
            definition for definitions in plan.values() for definition in definitions
        ]
        account_fields = {
            "account_id", "ad_account_id", "advertiser_id", "customer_id"
        }
        account_scoped = any(
            account_fields.intersection(
                set(
                    (
                        getattr(
                            getattr(definition, "input_schema", None),
                            "properties",
                            {},
                        )
                        or {}
                    ).keys()
                )
            )
            for definition in matched_tools
        )
        if account_scoped and not account_values:
            return {
                "status": "needs_input",
                "missing": ["account"],
                "reason": "请明确要使用的广告账户，并确保当前身份有该账户权限。",
                "intent_type": candidate.intent_type,
                "platforms": list(plan),
            }
        permission_errors = []
        for definition in matched_tools:
            error = self._check_tool_permissions(definition, permissions)
            if error and error not in permission_errors:
                permission_errors.append(error)
        if permission_errors:
            return {
                "status": "unsupported",
                "missing": [],
                "reason": "；".join(permission_errors),
                "intent_type": candidate.intent_type,
                "platforms": list(plan),
            }
        write_tools = [
            definition for definition in matched_tools if definition.is_write_tool
        ]
        account_errors = []
        if account_values and (account_scope is not None or self.enforce_account_scope):
            for platform in plan:
                allowed, account_error = self._validate_account_with_principal(
                    platform, account_values[0], bool(write_tools), account_scope,
                )
                if not allowed and account_error not in account_errors:
                    account_errors.append(account_error)
        if account_errors:
            return {
                "status": "unsupported",
                "missing": [],
                "reason": "；".join(account_errors),
                "intent_type": candidate.intent_type,
                "platforms": list(plan),
            }
        platform_params_by_canonical: dict[str, dict[str, Any]] = {}
        for platform_name, values in (
            getattr(candidate, "scoped_parameters", {}) or {}
        ).items():
            if not isinstance(values, dict):
                continue
            canonical = self._canonical_platform(str(platform_name))
            current = platform_params_by_canonical.setdefault(canonical, {})
            current.update(values)
        missing_parameters: dict[str, list[str]] = {}
        ready_tools: list[Any] = []
        for platform, definitions in plan.items():
            canonical = self._canonical_platform(str(platform))
            supplied = dict(platform_params_by_canonical.get(canonical, {}))
            candidates_ready = False
            platform_missing: set[str] = set()
            for definition in definitions:
                schema = getattr(definition, "input_schema", None)
                properties = getattr(schema, "properties", {}) if schema else {}
                properties = properties if isinstance(properties, Mapping) else {}
                candidate_input = {
                    key: value for key, value in supplied.items() if key in properties
                }
                for field_name in ("account_id", "advertiser_id", "customer_id"):
                    if field_name in properties and account_values:
                        candidate_input.setdefault(field_name, account_values[0])
                required = [
                    str(field_name)
                    for field_name in (getattr(schema, "required", []) or [])
                ]
                required.extend(
                    str(field_name)
                    for field_name in (getattr(schema, "requires", []) or [])
                    if str(field_name) not in required
                )
                missing = {
                    field_name for field_name in required
                    if candidate_input.get(field_name) in (None, "", {}, [])
                }
                for alternatives in (
                    (getattr(schema, "requires_any_of", []) or [])
                    if schema else ()
                ):
                    if not any(
                        candidate_input.get(str(field_name))
                        not in (None, "", {}, [])
                        for field_name in alternatives
                    ):
                        missing.add("one_of:" + "|".join(
                            str(field_name) for field_name in alternatives
                        ))
                if not missing:
                    candidates_ready = True
                    ready_tools.append(definition)
                else:
                    platform_missing.update(missing)
            if not candidates_ready and platform_missing:
                missing_parameters[canonical] = sorted(platform_missing)
        if missing_parameters:
            formatted = [
                f"{platform}: {', '.join(fields)}"
                for platform, fields in sorted(missing_parameters.items())
            ]
            return {
                "status": "needs_input",
                "missing": [
                    "parameter:" + field
                    for fields in missing_parameters.values()
                    for field in fields
                ],
                "reason": "匹配的 Tool 还缺少必填参数：" + "；".join(formatted),
                "intent_type": candidate.intent_type,
                "platforms": list(plan),
                "missing_parameters": missing_parameters,
            }
        if ready_tools:
            matched_tools = ready_tools
            write_tools = [
                definition for definition in matched_tools if definition.is_write_tool
            ]
        return {
            "status": "ready",
            "intent_type": candidate.intent_type,
            "platforms": list(plan),
            "tool_names": [str(definition.name) for definition in matched_tools],
            "effects": ["write" if write_tools else "read"],
            "write_tools": [str(definition.name) for definition in write_tools],
            "account_id": account_values[0] if account_values else None,
            "execution_mode": "dry_run",
            "reason": "已匹配当前 Registry 的 Tool/Tool Source；到期执行仍会重新校验。",
        }


__all__ = ["AdSchedulingPreflightMixin"]
