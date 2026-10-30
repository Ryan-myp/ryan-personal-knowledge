"""Advertising application policy and resource-boundary services.

The generic Agent Harness owns Run/Turn lifecycle and generic Tool policy.
This module contains only the advertising composition's domain policy:
account scope, provider payload simulation, and normalized resource results.
It is intentionally dependency-light so another application can provide a
different policy object without changing the Harness.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Mapping, Optional

from agents.agent_harness.core.interfaces import (
    ExecutionMode,
    ToolEffect,
    ToolResult,
    ToolSchema,
)
from agents.agent_harness.core.tool_registry import validate_tool_input
from agents.tools.advertising.shared.domain.auth import normalize_account_id
from agents.tools.advertising.shared.domain.contracts import ResourceResult
from ..integrations.provider_bindings import ProviderBindings


class AdvertisingRuntimePolicy:
    """Application-owned checks that sit beside, not inside, the Run Kernel."""

    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime

    def validate_request_limits(
        self, user_input: str, platform_params: Optional[dict],
    ) -> Optional[str]:
        if not isinstance(user_input, str) or not user_input.strip():
            return "user_input 不能为空"
        if len(user_input) > self.runtime.max_user_input_chars:
            return (
                "user_input 超过长度限制（最多 "
                f"{self.runtime.max_user_input_chars} 个字符）"
            )
        if platform_params is None:
            return None
        if not isinstance(platform_params, dict):
            return "platform_params 必须是对象"
        try:
            size = len(
                json.dumps(
                    platform_params,
                    ensure_ascii=False,
                    default=str,
                ).encode("utf-8")
            )
        except (TypeError, ValueError):
            return "platform_params 不是可序列化的对象"
        if size > self.runtime.max_platform_params_bytes:
            return (
                "platform_params 超过大小限制（最多 "
                f"{self.runtime.max_platform_params_bytes} 字节）"
            )
        return None

    def check_tool_permissions(
        self,
        tool_def: Any,
        granted_permissions: Optional[set[str] | frozenset[str]] = None,
    ) -> Optional[str]:
        granted = (
            self.runtime._granted_permissions
            if granted_permissions is None
            else frozenset(granted_permissions)
        )
        errors = self.runtime.policy_engine.check_permissions(
            tool_def,
            execution_mode=self.runtime.execution_mode,
            granted_permissions=granted,
        )
        return errors[0] if errors else None

    def evaluate_tool_policy(
        self,
        tool_def: Any,
        *,
        granted_permissions: Optional[set[str] | frozenset[str]] = None,
        scope: Any = None,
        principal: Any = None,
        confirmed: bool = False,
        require_confirmation: bool = True,
    ) -> Any:
        from agents.agent_platform.tools.policy import PolicyRequest

        granted = (
            self.runtime._granted_permissions
            if granted_permissions is None
            else frozenset(granted_permissions)
        )
        return self.runtime.policy_engine.evaluate(
            PolicyRequest(
                tool=tool_def,
                execution_mode=self.runtime.execution_mode,
                granted_permissions=granted,
                scope=scope,
                principal=principal,
                allow_live_writes=self.runtime.allow_live_writes,
                live_approved_tools=self.runtime._live_approved_tools,
                write_guard_configured=self.runtime.write_guard is not None,
                confirmed=confirmed,
                require_confirmation=require_confirmation,
            )
        )

    def validate_account_for_tool(
        self, platform: str, account_id: str, is_write: bool,
    ) -> tuple[bool, str]:
        if not account_id:
            return False, "缺少账户ID"
        allowed = self.runtime.whitelist_validator.get_allowed_accounts(platform)
        if (is_write or self.runtime.enforce_account_scope) and not allowed:
            return False, f"{platform} 未配置受控账户白名单，当前请求被拒绝"
        return self.runtime.whitelist_validator.validate_account(platform, account_id)

    @staticmethod
    def principal_accounts(
        platform: str,
        account_scope: Optional[Mapping[str, Any]],
    ) -> Optional[set[str]]:
        if account_scope is None:
            return None
        normalized = ProviderBindings.normalize_namespace(platform)
        aliases = {normalized, platform}
        accounts: set[str] = set()
        for key in aliases:
            values = account_scope.get(key, ()) if hasattr(account_scope, "get") else ()
            if isinstance(values, (str, bytes)):
                values = (values,)
            accounts.update(normalize_account_id(value) for value in (values or ()))
        return {value for value in accounts if value}

    def validate_account_with_principal(
        self,
        platform: str,
        account_id: str,
        is_write: bool,
        account_scope: Optional[Mapping[str, Any]],
        *,
        provider_read_namespaces: frozenset[str] = frozenset(),
    ) -> tuple[bool, str]:
        if not normalize_account_id(account_id):
            return False, "缺少账户ID"
        namespace = ProviderBindings.normalize_namespace(platform)
        if not is_write and namespace in provider_read_namespaces:
            return True, ""
        if account_scope is not None:
            principal_accounts = self.principal_accounts(platform, account_scope)
            if (
                not principal_accounts
                or normalize_account_id(account_id) not in principal_accounts
            ):
                return False, f"账户 {account_id or '<empty>'} 不在当前身份的授权范围内"
        return self.validate_account_for_tool(platform, account_id, is_write)

    def read_accounts(
        self, platform: str, principal: Any,
    ) -> Optional[list[str]]:
        """None means credential-bounded reads, not an unrestricted write scope."""
        namespace = ProviderBindings.normalize_namespace(platform)
        if namespace in getattr(principal, "provider_read_namespaces", ()):
            return None
        return self.available_accounts(
            platform, getattr(principal, "account_scope", None),
        )

    def available_accounts(
        self,
        platform: str,
        account_scope: Optional[Mapping[str, Any]],
    ) -> list[str]:
        configured = self.runtime.whitelist_validator.get_allowed_accounts(platform)
        principal_accounts = self.principal_accounts(platform, account_scope)
        if principal_accounts is None:
            return list(configured)
        return [
            account for account in configured
            if normalize_account_id(account) in principal_accounts
        ]

    def simulate_write(
        self, tool_def: Any, input_data: dict, platform: str,
    ) -> ToolResult:
        key = (
            self.runtime.registry.generate_idempotency_key(
                tool_def.name, input_data, "dry-run"
            )
            if hasattr(self.runtime.registry, "generate_idempotency_key")
            else uuid.uuid4().hex[:16]
        )
        name = input_data.get("name") or f"dry_run_{key}"
        resource_type = getattr(tool_def, "resource_type", None) or "resource"
        resource_key = self.resource_id_field(tool_def)
        if not resource_key:
            return ToolResult.error(
                f"Tool '{tool_def.name}' must declare resource_id_field"
            )
        parent_type = getattr(tool_def, "parent_resource_type", None)
        parent_field = self.parent_resource_id_field(tool_def)
        parent_id = input_data.get(parent_field) if parent_field else None
        action = str(getattr(tool_def, "action", "") or "").lower()
        is_update = action in {"update", "pause", "resume", "enable", "disable"}
        is_delete = action == "delete"
        resource_id = input_data.get(resource_key) or self._simulation_resource_id(
            tool_def,
            namespace=platform,
            resource_type=resource_type,
            key=key,
        )
        operation = "delete" if is_delete else ("update" if is_update else "create")
        data = {
            "mode": ExecutionMode.DRY_RUN.value,
            "simulated": True,
            "live_support": bool(getattr(tool_def, "live_support", False)),
            "operation": operation,
            resource_key: resource_id,
            "resource_id_field": resource_key,
            "parent_resource_type": parent_type,
            "parent_resource_id_field": parent_field,
            "parent_resource_id": (
                str(parent_id) if parent_id not in (None, "") else None
            ),
            "name": name,
            "status": (
                "SIMULATED_DELETED" if is_delete
                else ("SIMULATED_UPDATED" if is_update else "SIMULATED_DRAFT")
            ),
            "input": {k: v for k, v in input_data.items() if k != "credentials"},
        }
        provider_errors = (
            validate_tool_input(
                tool_def.input_schema,
                input_data,
                include_tool_requirements=True,
            )
            if tool_def.input_schema
            else []
        )
        data["provider_validation"] = {
            "ready": not provider_errors,
            "errors": provider_errors,
        }
        return ToolResult.dry_run(data)

    def _simulation_resource_id(
        self, tool_def: Any, *, namespace: str, resource_type: str, key: str,
    ) -> str:
        fallback = f"dry_{namespace}_{key}"
        registry = getattr(self.runtime, "registry", None)
        list_tools = getattr(registry, "list_all", None)
        if not callable(list_tools):
            return fallback

        child_fields: list[tuple[str, Any]] = []
        for child in list_tools():
            if (
                str(getattr(child, "action", "") or "").lower() != "create"
                or str(getattr(child, "namespace", "") or "").strip().lower()
                != str(namespace).strip().lower()
                or str(getattr(child, "parent_resource_type", "") or "")
                .strip().lower() != str(resource_type).strip().lower()
            ):
                continue
            field_name = str(
                getattr(child, "parent_resource_id_field", "") or ""
            ).strip()
            properties = getattr(
                getattr(child, "input_schema", None), "properties", {},
            )
            if field_name and isinstance(properties, Mapping):
                field_schema = properties.get(field_name)
                if isinstance(field_schema, Mapping):
                    child_fields.append((field_name, field_schema))
        if not child_fields:
            return fallback

        try:
            candidate = str(int(key, 16) % 10**15)
        except (TypeError, ValueError):
            return fallback
        if all(
            not validate_tool_input(
                ToolSchema(properties={field_name: dict(field_schema)}),
                {field_name: candidate},
            )
            for field_name, field_schema in child_fields
        ):
            return candidate
        return fallback

    @staticmethod
    def resource_id_field(tool_def: Any) -> Optional[str]:
        declared = str(getattr(tool_def, "resource_id_field", "") or "").strip()
        return declared or None

    @staticmethod
    def parent_resource_id_field(tool_def: Any) -> Optional[str]:
        declared = str(
            getattr(tool_def, "parent_resource_id_field", "") or ""
        ).strip()
        return declared or None

    @classmethod
    def parent_resource_id_for_tool(
        cls, tool_def: Any, input_data: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        field = cls.parent_resource_id_field(tool_def)
        value = (input_data or {}).get(field) if field else None
        return str(value) if value not in (None, "") else None

    @staticmethod
    def _canonical_platform(platform: str) -> str:
        return ProviderBindings.normalize_namespace(platform)

    @classmethod
    def build_resource_results(cls, results: list[dict]) -> list[dict]:
        resource_items: list[ResourceResult] = []
        id_index: dict[tuple[str, str, str], int] = {}
        sequence = 0
        for item in results or []:
            tool_name = str(item.get("tool") or "")
            if not tool_name or not item.get("resource_type"):
                continue
            data = item.get("data") if isinstance(item.get("data"), dict) else {}
            if not item.get("account_id") and not data and not item.get("error"):
                continue
            sequence += 1
            resource_type = str(item["resource_type"])
            id_field = str(item.get("resource_id_field") or "")
            if not id_field:
                continue
            input_data = (
                data.get("input")
                if isinstance(data.get("input"), dict)
                else {}
            )
            raw_id = (
                data.get(id_field)
                or input_data.get(id_field)
                or item.get(id_field)
            )
            raw_id = str(raw_id) if raw_id not in (None, "") else None
            simulated = bool(data.get("simulated") or item.get("simulated"))
            execution_status = str(data.get("execution_status") or "").lower()
            if item.get("skipped") or data.get("skipped"):
                status = "skipped"
            elif execution_status == "unsupported":
                status = "unsupported"
            elif execution_status in {"unknown", "timed_out", "transport_unknown"}:
                status = "unknown"
            elif item.get("needs_confirmation"):
                status = "awaiting_confirmation"
            elif item.get("success") and simulated:
                status = "planned"
            elif item.get("success"):
                status = "succeeded"
            else:
                status = "failed"

            parent_type = (
                item.get("parent_resource_type")
                or data.get("parent_resource_type")
            )
            parent_id = (
                item.get("parent_resource_id")
                or data.get("parent_resource_id")
            )
            if parent_id in (None, ""):
                parent_field = item.get("parent_resource_id_field")
                parent_id = input_data.get(parent_field) if parent_field else None
            parent_id = str(parent_id) if parent_id not in (None, "") else None
            normalized_platform = cls._canonical_platform(
                str(item.get("platform") or "")
            )
            parent_sequence = None
            if parent_id and parent_type:
                parent_sequence = id_index.get(
                    (normalized_platform, str(parent_type), parent_id)
                )
            local_id = raw_id if simulated else None
            provider_id = raw_id if raw_id and not simulated else None
            logical_id = str(
                data.get("logical_resource_id")
                or local_id
                or provider_id
                or input_data.get(id_field)
                or ""
            ) or None
            normalized = ResourceResult(
                sequence=sequence,
                platform=normalized_platform,
                resource_type=resource_type,
                tool_name=tool_name,
                status=status,
                parent_resource_type=(str(parent_type) if parent_type else None),
                account_id=(
                    str(item.get("account_id"))
                    if item.get("account_id") is not None
                    else None
                ),
                parent_sequence=parent_sequence,
                parent_resource_id=parent_id,
                provider_resource_id=provider_id,
                logical_resource_id=logical_id,
                local_resource_id=local_id,
                error=item.get("error"),
                simulated=simulated,
            )
            resource_items.append(normalized)
            if raw_id:
                id_index[(normalized_platform, resource_type, raw_id)] = sequence
        return [item.to_dict() for item in resource_items]


__all__ = ["AdvertisingRuntimePolicy"]
