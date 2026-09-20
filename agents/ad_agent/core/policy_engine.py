"""Reusable Tool/Scope/Effect policy decisions.

This module computes deterministic execution eligibility from publisher-owned
Tool metadata and trusted request inputs. It does not create permissions,
resolve identities, execute handlers, or render confirmation UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from .interfaces import ExecutionMode, ToolDefinition
from .scope import ResourceScope, ScopePolicy


@dataclass(frozen=True)
class PolicyRequest:
    """Trusted inputs required for one Tool policy decision."""

    tool: ToolDefinition
    execution_mode: str = ExecutionMode.DRY_RUN.value
    granted_permissions: frozenset[str] | set[str] = field(default_factory=frozenset)
    scope: Optional[ResourceScope] = None
    principal: Any = None
    allow_live_writes: bool = False
    live_approved_tools: frozenset[str] | set[str] = field(default_factory=frozenset)
    write_guard_configured: bool = False
    confirmed: bool = False
    scope_policy: Optional[ScopePolicy] = None
    require_confirmation: bool = True


@dataclass(frozen=True)
class PolicyDecision:
    """Stable, serializable outcome of a policy evaluation."""

    allowed: bool
    errors: tuple[str, ...] = ()
    requires_confirmation: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def reason(self) -> str:
        if self.errors:
            return self.errors[0]
        if self.requires_confirmation:
            return "confirmation_required"
        return "allowed" if self.allowed else "denied"

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "errors": list(self.errors),
            "requires_confirmation": self.requires_confirmation,
            "reason": self.reason,
            "metadata": dict(self.metadata),
        }


class PolicyEngine:
    """Evaluate generic Tool execution gates without domain vocabulary."""

    def required_permissions(
        self, tool: ToolDefinition, execution_mode: str,
    ) -> frozenset[str]:
        permissions = {
            str(value).strip()
            for value in (getattr(tool, "required_permissions", None) or ())
            if str(value).strip()
        }
        if (
            getattr(tool, "is_write_tool", False)
            and str(execution_mode or "").strip().lower()
            == ExecutionMode.LIVE.value
        ):
            live_permission = str(getattr(tool, "live_permission", "") or "").strip()
            if live_permission:
                permissions.add(live_permission)
        return frozenset(permissions)

    def check_permissions(
        self,
        tool: ToolDefinition,
        *,
        execution_mode: str = ExecutionMode.DRY_RUN.value,
        granted_permissions: Iterable[str] = (),
    ) -> tuple[str, ...]:
        required = self.required_permissions(tool, execution_mode)
        granted = {
            str(value).strip()
            for value in (granted_permissions or ())
            if str(value).strip()
        }
        missing = sorted(required - granted)
        if not missing:
            return ()
        return ("缺少工具所需权限：" + ", ".join(missing),)

    def evaluate(self, request: PolicyRequest) -> PolicyDecision:
        """Return a fail-closed decision for a trusted Tool request."""
        tool = request.tool
        mode = str(request.execution_mode or "").strip().lower()
        errors = list(self.check_permissions(
            tool,
            execution_mode=mode,
            granted_permissions=request.granted_permissions,
        ))

        if getattr(tool, "scope_required", False) and request.scope is None:
            errors.append("工具需要已解析的资源 scope")
        if request.scope is not None and request.scope_policy is not None:
            try:
                allowed, message = request.scope_policy.validate_scope(
                    request.scope,
                    principal=request.principal,
                    tool=tool,
                    effect=getattr(tool, "effect_class", None),
                )
            except Exception:
                allowed, message = False, "资源 scope 校验失败"
            if not allowed:
                errors.append(str(message or "资源 scope 不被允许"))

        metadata = {
            "tool": str(getattr(tool, "name", "") or ""),
            "effect": str(getattr(
                getattr(tool, "effect_class", None), "value",
                getattr(tool, "effect_class", ""),
            )),
            "scope_type": str(getattr(tool, "scope_type", "") or ""),
        }
        if errors:
            return PolicyDecision(
                allowed=False,
                errors=tuple(dict.fromkeys(errors)),
                metadata=metadata,
            )

        if getattr(tool, "is_write_tool", False) and mode == ExecutionMode.LIVE.value:
            if not request.allow_live_writes:
                errors.append("Runtime 全局 allow_live_writes 未开启")
            if not bool(getattr(tool, "live_support", False)):
                errors.append("该 Tool 当前仅支持 dry-run")
            approved = {
                str(value).strip()
                for value in (request.live_approved_tools or ())
                if str(value).strip()
            }
            if str(getattr(tool, "name", "") or "") not in approved:
                errors.append("该 Tool 未加入 live 执行批准清单")
            if not request.write_guard_configured:
                errors.append("live 写操作必须配置 WriteGuard；已拒绝执行")
            if errors:
                return PolicyDecision(
                    allowed=False,
                    errors=tuple(dict.fromkeys(errors)),
                    metadata=metadata,
                )
            if request.require_confirmation and not request.confirmed:
                return PolicyDecision(
                    allowed=False,
                    requires_confirmation=True,
                    metadata=metadata,
                )

        return PolicyDecision(allowed=True, metadata=metadata)


__all__ = ["PolicyDecision", "PolicyEngine", "PolicyRequest"]
