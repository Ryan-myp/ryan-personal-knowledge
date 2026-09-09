"""No-network preflight for controlled advertising Provider API tests.

This module intentionally does not call a client or validate a live token. It
checks the local contract and deployment configuration that must be true
before an operator starts a separately approved real-account test.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional

from ...core.platform import normalize_platform


def _schema_properties(tool: Any) -> Mapping[str, Any]:
    schema = getattr(tool, "input_schema", None)
    properties = getattr(schema, "properties", {}) if schema else {}
    return properties if isinstance(properties, Mapping) else {}


def _account_field(tool: Any) -> str:
    properties = _schema_properties(tool)
    for name in ("account_id", "advertiser_id", "customer_id"):
        if name in properties:
            return name
    return ""


def _account_required(tool: Any) -> bool:
    schema = getattr(tool, "input_schema", None)
    required = getattr(schema, "required", []) if schema else []
    return _account_field(tool) in set(str(item) for item in (required or []))


def _safe_id(value: Any) -> str:
    """Show enough account identity for an operator without echoing secrets."""
    text = str(value or "")
    return f"…{text[-4:]}" if len(text) > 4 else ("configured" if text else "missing")


def _readback_error(runtime: Any, tool: Any) -> Optional[str]:
    if not getattr(tool, "is_write_tool", False):
        return None
    resolver = getattr(runtime, "_resolve_readback_definition", None)
    if not callable(resolver):
        return "Runtime 没有提供 read-back 契约解析器"
    readback = resolver(tool.name)
    if readback is None:
        return "没有唯一、同渠道、同资源类型的只读回查 Tool"
    if not getattr(readback, "is_read_tool", False):
        return "read-back Tool 不是只读操作"
    return None


def build_provider_preflight(
    runtime: Any,
    *,
    platform: str,
    tool_names: Optional[Iterable[str]] = None,
    account_id: Any = None,
    credential_configured: Optional[bool] = None,
    live_requested: bool = False,
    live_environment_enabled: bool = False,
) -> dict[str, Any]:
    """Return a redacted, JSON-safe preflight report without Provider I/O."""
    canonical = normalize_platform(platform)
    requested = [str(name).strip() for name in (tool_names or ()) if str(name).strip()]
    if not requested:
        requested = [tool.name for tool in runtime.registry.list_by_platform(canonical)]
    definitions: list[Any] = []
    missing_tools: list[str] = []
    for name in requested:
        try:
            definition, _handler = runtime._get_registered_tool(name)
        except (KeyError, TypeError):
            missing_tools.append(name)
            continue
        if normalize_platform(getattr(definition, "platform", "")) != canonical:
            missing_tools.append(f"{name} (platform mismatch)")
            continue
        definitions.append(definition)

    configured_accounts = list(
        getattr(getattr(runtime, "whitelist_validator", None), "get_allowed_accounts", lambda _p: [])(canonical)
        or []
    )
    normalized_account = str(account_id or "").strip()
    account_ok = False
    account_error = "未提供测试账户 ID"
    account_required = any(_account_required(tool) for tool in definitions)
    if normalized_account:
        validator = getattr(runtime, "whitelist_validator", None)
        if validator is not None:
            account_ok, account_error = validator.validate_account(canonical, normalized_account)
        else:
            account_error = "Runtime 未配置账户白名单校验器"
    elif not account_required:
        account_ok = True
        account_error = ""

    permissions = set(getattr(runtime, "_granted_permissions", set()) or set())
    env_live = bool(live_environment_enabled)
    rows: list[dict[str, Any]] = []
    issues: list[str] = []
    if missing_tools:
        issues.append("目标 Tool 未注册：" + ", ".join(missing_tools))
    if credential_configured is False:
        issues.append("目标渠道未发现本地凭证配置（预检未读取或打印凭证内容）")
    if not account_ok:
        issues.append(account_error)
    if "ads.read" not in permissions:
        issues.append("当前 principal 缺少 ads.read 权限")
    if live_requested and "ads.write" not in permissions:
        issues.append("live 测试需要 ads.write 权限")

    for definition in definitions:
        is_write = bool(getattr(definition, "is_write_tool", False))
        required_permissions = set(getattr(definition, "required_permissions", ()) or ())
        effective_live_permissions = set(required_permissions)
        if is_write:
            # Tool contracts declare the base planning grant. Runtime adds
            # the separate live mutation grant at execution time; preflight
            # must inspect that same effective set instead of forcing every
            # write Tool to carry live authority in its static metadata.
            effective_live_permissions.add("ads.write")
        row: dict[str, Any] = {
            "tool": definition.name,
            "platform": canonical,
            "action": getattr(definition, "action", ""),
            "resource_type": getattr(definition, "resource_type", ""),
            "effect": getattr(getattr(definition, "effect_class", None), "value", ""),
            "account_field": _account_field(definition),
            "account": _safe_id(normalized_account),
            "live_support": bool(getattr(definition, "live_support", False)),
            "required_permissions": sorted(required_permissions),
            "live_required_permissions": sorted(effective_live_permissions),
            "readback_tool": getattr(definition, "readback_tool", None),
            "status": "ready",
            "issues": [],
        }
        if _account_required(definition) and not row["account_field"]:
            row["issues"].append("Tool schema 未声明标准账户字段")
        if is_write:
            readback_issue = _readback_error(runtime, definition)
            if readback_issue:
                row["issues"].append(readback_issue)
            if live_requested:
                if not bool(getattr(definition, "live_support", False)):
                    row["issues"].append("该 Tool 尚未批准 live 执行")
                if not bool(getattr(runtime, "allow_live_writes", False)):
                    row["issues"].append("Runtime allow_live_writes 未开启")
                if not env_live:
                    row["issues"].append("AD_AGENT_ENABLE_LIVE 未显式开启")
                approved = set(getattr(runtime, "_live_approved_tools", set()) or set())
                if definition.name not in approved:
                    row["issues"].append("Tool 不在 live 批准清单")
                if "ads.write" not in effective_live_permissions:
                    row["issues"].append("live 有效权限未包含 ads.write")
        if row["issues"]:
            row["status"] = "blocked"
            issues.extend(f"{definition.name}: {item}" for item in row["issues"])
        rows.append(row)

    if not definitions:
        issues.append("没有可检查的已注册 Tool")
    blocked = bool(issues)
    return {
        "format_version": 1,
        "platform": canonical,
        "tools": rows,
        "requested_tools": requested,
        "configured_account_count": len(configured_accounts),
        "configured_account_preview": [_safe_id(item) for item in configured_accounts[:10]],
        "credential_configured": credential_configured,
        "live_requested": bool(live_requested),
        "provider_calls": 0,
        "network_called": False,
        "status": "blocked" if blocked else "ready_for_controlled_api_test",
        "next_step": (
            "先修复预检项，再进入受控 Provider 测试"
            if blocked else "可进入单独批准的 Provider API 测试；仍需按测试用例逐项执行"
        ),
        "issues": list(dict.fromkeys(issues)),
    }
