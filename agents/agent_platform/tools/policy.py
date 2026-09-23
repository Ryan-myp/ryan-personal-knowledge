"""Generic Tool execution policy for Platform applications."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
import hashlib
import json
import time
from typing import Any, Callable, Iterable, Mapping, Optional

from agents.agent_harness import ToolCallContext


def _value(definition: Any, name: str, default: Any = None) -> Any:
    if isinstance(definition, Mapping):
        return definition.get(name, default)
    return getattr(definition, name, default)


def _schema(definition: Any) -> dict[str, Any]:
    value = _value(definition, "input_schema", {})
    if hasattr(value, "to_dict") and callable(value.to_dict):
        value = value.to_dict()
    return dict(value) if isinstance(value, Mapping) else {}


def _is_write(definition: Any) -> bool:
    effect = _value(definition, "effect_class", _value(definition, "effect", "read"))
    effect = getattr(effect, "value", effect)
    if str(effect or "").strip().lower() in {"write", "external_write"}:
        return True
    return bool(_value(definition, "is_write_tool", False))


def _permissions(request: Any) -> frozenset[str]:
    principal = getattr(request, "principal", None)
    values = getattr(principal, "permissions", None)
    if isinstance(values, str):
        values = [values]
    return frozenset(str(item).strip() for item in (values or ()) if str(item).strip())


def _confirmed(request: Any) -> bool:
    context = getattr(request, "context", {})
    return bool(context.get("confirmed")) if isinstance(context, Mapping) else False


def _mode(request: Any) -> str:
    return str(getattr(request, "execution_mode", None) or "dry_run").strip().lower()


class IdempotencyStoreUnavailable(RuntimeError):
    """The durable replay boundary could not make a safe decision."""


@dataclass(frozen=True)
class PolicyRequest:
    """Trusted inputs for a provider-neutral Tool policy decision."""

    tool: Any
    execution_mode: str = "dry_run"
    granted_permissions: frozenset[str] | set[str] = frozenset()
    scope: Any = None
    principal: Any = None
    allow_live_writes: bool = False
    live_approved_tools: frozenset[str] | set[str] = frozenset()
    write_guard_configured: bool = False
    confirmed: bool = False
    scope_policy: Any = None
    require_confirmation: bool = True
    idempotency_store_configured: Optional[bool] = None


@dataclass(frozen=True)
class PolicyDecision:
    """Stable serializable result shared by all application embeddings."""

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


@dataclass
class ToolExecutionPolicy:
    """Schema, authorization, risk, live and replay gate for Tool calls."""

    permissions: frozenset[str] = frozenset()
    allow_live_writes: bool = False
    live_approved_tools: frozenset[str] = frozenset()
    write_guard_configured: bool = False
    require_confirmation_for_risk: bool = True
    require_confirmation_for_writes: bool = False
    require_durable_idempotency: bool = True
    require_audit: bool = False
    before_check: Optional[
        Callable[[Any, Any, Mapping[str, Any]], Optional[tuple[str, str]]]
    ] = None
    confirmation_builder: Optional[
        Callable[[ToolCallContext, Any, Mapping[str, Any]], Mapping[str, Any] | None]
    ] = None
    audit_sink: Optional[Callable[[dict[str, Any]], None]] = None
    live_approved_tools_provider: Optional[Callable[[], Iterable[str]]] = None
    idempotency_store: Any = None
    idempotency_ttl_seconds: float = 3600.0
    max_idempotency_entries: int = 10_000
    _seen_idempotency: dict[tuple[str, str, str], float] = field(
        default_factory=dict, init=False, repr=False,
    )
    _reservations_by_call: dict[
        tuple[str, str, str], set[tuple[str, str]]
    ] = field(
        default_factory=dict, init=False, repr=False,
    )
    _lock: threading.RLock = field(
        default_factory=threading.RLock, init=False, repr=False,
    )

    def __post_init__(self) -> None:
        if self.idempotency_ttl_seconds <= 0:
            raise ValueError("idempotency_ttl_seconds must be positive")
        if self.max_idempotency_entries <= 0:
            raise ValueError("max_idempotency_entries must be positive")

    def _approved_live_tools(self) -> frozenset[str]:
        source: Iterable[str] = self.live_approved_tools
        if callable(self.live_approved_tools_provider):
            try:
                source = self.live_approved_tools_provider() or ()
            except Exception:
                # A deployment approval source is security-sensitive. If it
                # cannot be read, fail closed instead of using stale state.
                source = ()
        return frozenset(
            str(item).strip() for item in source if str(item).strip()
        )

    def before_tool_call(self, context: ToolCallContext) -> Optional[dict[str, Any]]:
        definition = context.tool_definition
        request = context.request
        call = context.tool_call
        reason = self._check(
            definition,
            request,
            dict(call.arguments),
            call_id=str(call.id or ""),
        )
        if reason is None:
            return None
        reason_code, message = reason
        audit_ok = self._audit(
            request,
            call.name,
            decision="blocked",
            reason_code=reason_code,
        )
        result = {
            "block": True,
            "reason": message,
            "terminate": True,
            "needs_input": reason_code == "confirmation_required",
            "needs_confirmation": reason_code == "confirmation_required",
            **self._confirmation_payload(
                context, definition, dict(call.arguments), reason_code,
            ),
        }
        if not audit_ok:
            result["runtime_signals"] = {"audit_error": True}
            result["recovery_required"] = True
        elif reason_code == "idempotency_store_error":
            result["runtime_signals"] = {"idempotency_store_error": True}
            result["recovery_required"] = True
        return result

    def after_tool_call(
        self, context: ToolCallContext, result: Mapping[str, Any],
    ) -> Optional[Mapping[str, Any]]:
        tool_data = result.get("data")
        uncertain = (
            result.get("success") is False
            or result.get("effect_state") in {"unknown", "recovery_required"}
            or (
                isinstance(tool_data, Mapping)
                and tool_data.get("execution_status") in {
                    "unknown", "timed_out", "provider_result_unknown",
                }
            )
        )
        if result.get("is_error"):
            call_key = (
                str(context.request.run_id or ""),
                str(context.request.turn_id or ""),
                str(context.tool_call.id or ""),
            )
            with self._lock:
                reservations = self._reservations_by_call.pop(call_key, set())
                release_failed = any(
                    not self._release_idempotency(*identity)
                    for identity in reservations
                )
        elif uncertain:
            call_key = (
                str(context.request.run_id or ""),
                str(context.request.turn_id or ""),
                str(context.tool_call.id or ""),
            )
            with self._lock:
                self._reservations_by_call.pop(call_key, None)
            release_failed = False
        else:
            call_key = (
                str(context.request.run_id or ""),
                str(context.request.turn_id or ""),
                str(context.tool_call.id or ""),
            )
            with self._lock:
                reservations = self._reservations_by_call.pop(call_key, set())
            release_failed = any(
                not self._mark_idempotency_executed(*identity)
                for identity in reservations
            )
        if release_failed:
            return {
                "runtime_signals": {"idempotency_store_error": True},
                "recovery_required": True,
            }
        audit_ok = self._audit(
            context.request,
            context.tool_call.name,
            decision=(
                "failed" if result.get("is_error")
                else "unknown" if uncertain
                else "executed"
            ),
            reason_code=(
                "executor_error" if result.get("is_error")
                else "provider_result_unknown" if uncertain
                else "ok"
            ),
        )
        if not audit_ok:
            return {
                "runtime_signals": {"audit_error": True},
                "recovery_required": True,
            }
        if uncertain:
            return {
                "runtime_signals": {"effect_state": "unknown"},
                "recovery_required": True,
            }
        return None

    def required_permissions(
        self, definition: Any, execution_mode: str = "dry_run",
    ) -> frozenset[str]:
        required = {
            str(item).strip()
            for item in (_value(definition, "required_permissions", ()) or ())
            if str(item).strip()
        }
        if _is_write(definition) and str(execution_mode).strip().lower() == "live":
            live_permission = str(
                _value(definition, "live_permission", "") or ""
            ).strip()
            if live_permission:
                required.add(live_permission)
        return frozenset(required)

    def check_permissions(
        self,
        definition: Any,
        *,
        execution_mode: str = "dry_run",
        granted_permissions: Iterable[str] = (),
    ) -> tuple[str, ...]:
        required = self.required_permissions(definition, execution_mode)
        granted = {
            str(item).strip() for item in (granted_permissions or ())
            if str(item).strip()
        }
        missing = sorted(required - granted - self.permissions)
        return (
            ("缺少工具所需权限：" + ", ".join(missing),)
            if missing else ()
        )

    def evaluate(self, request: PolicyRequest) -> PolicyDecision:
        """Evaluate the same gates used by the Harness ``before_tool_call``."""
        definition = request.tool
        mode = str(request.execution_mode or "dry_run").strip().lower()
        errors = list(self.check_permissions(
            definition,
            execution_mode=mode,
            granted_permissions=request.granted_permissions,
        ))
        if bool(_value(definition, "scope_required", False)) and request.scope is None:
            errors.append("工具需要已解析的资源 scope")
        if request.scope is not None and request.scope_policy is not None:
            try:
                allowed, message = request.scope_policy.validate_scope(
                    request.scope,
                    principal=request.principal,
                    tool=definition,
                    effect=_value(definition, "effect_class"),
                )
            except Exception:
                allowed, message = False, "资源 scope 校验失败"
            if not allowed:
                errors.append(str(message or "资源 scope 不被允许"))
        metadata = {
            "tool": str(_value(definition, "name", "") or ""),
            "effect": str(getattr(
                _value(definition, "effect_class", ""), "value",
                _value(definition, "effect_class", ""),
            )),
            "durable_idempotency": (
                request.idempotency_store_configured
                if request.idempotency_store_configured is not None
                else self.idempotency_store is not None
            ),
        }
        if errors:
            return PolicyDecision(
                allowed=False,
                errors=tuple(dict.fromkeys(errors)),
                metadata=metadata,
            )
        if _is_write(definition) and mode == "live":
            if not request.allow_live_writes:
                return PolicyDecision(
                    allowed=False,
                    errors=("Runtime 全局 allow_live_writes 未开启",),
                    metadata=metadata,
                )
            if not bool(_value(definition, "live_support", False)):
                return PolicyDecision(
                    allowed=False,
                    errors=("该 Tool 当前仅支持 dry-run",),
                    metadata=metadata,
                )
            approved = (
                frozenset(
                    str(item).strip()
                    for item in request.live_approved_tools
                    if str(item).strip()
                )
                if request.live_approved_tools
                else self._approved_live_tools()
            )
            if not approved or str(_value(definition, "name", "")) not in approved:
                return PolicyDecision(
                    allowed=False,
                    errors=("该 Tool 未加入 live 执行批准清单",),
                    metadata=metadata,
                )
            if not request.write_guard_configured:
                return PolicyDecision(
                    allowed=False,
                    errors=("live 写操作必须配置 WriteGuard；已拒绝执行",),
                    metadata=metadata,
                )
            if request.require_confirmation and not request.confirmed:
                return PolicyDecision(
                    allowed=False,
                    requires_confirmation=True,
                    metadata=metadata,
                )
            if (
                request.confirmed
                and self.require_durable_idempotency
                and not bool(metadata["durable_idempotency"])
            ):
                return PolicyDecision(
                    allowed=False,
                    errors=("live writes require a durable idempotency store",),
                    metadata=metadata,
                )
        return PolicyDecision(allowed=True, metadata=metadata)

    def _check(
        self,
        definition: Any,
        request: Any,
        arguments: dict[str, Any],
        *,
        call_id: str = "",
    ) -> Optional[tuple[str, str]]:
        if callable(self.before_check):
            custom = self.before_check(definition, request, arguments)
            if custom is not None:
                return custom

        schema_error = self._validate_schema(definition, arguments)
        if schema_error:
            return "input_schema", schema_error

        request_context = getattr(request, "context", {})
        if not isinstance(request_context, Mapping):
            request_context = {}
        scope = request_context.get("scope")
        if bool(_value(definition, "scope_required", False)) and scope is None:
            return "scope_required", "Tool requires a resolved resource scope"
        scope_policy = request_context.get("scope_policy")
        if scope is not None and scope_policy is not None:
            validate_scope = getattr(scope_policy, "validate_scope", None)
            if not callable(validate_scope):
                return "scope_invalid", "resource scope policy is not executable"
            try:
                allowed, message = validate_scope(
                    scope,
                    principal=getattr(request, "principal", None),
                    tool=definition,
                    effect=_value(definition, "effect_class"),
                )
            except Exception:
                return "scope_invalid", "resource scope validation failed"
            if not allowed:
                return "scope_denied", str(
                    message or "resource scope is not allowed"
                )

        missing = sorted(
            self.required_permissions(definition, _mode(request))
            - self.permissions
            - _permissions(request)
        )
        if missing:
            return "permission_denied", (
                "missing required Tool permissions: " + ", ".join(missing)
            )

        mode = _mode(request)
        if _is_write(definition) and mode == "live":
            if not self.allow_live_writes:
                return (
                    "live_disabled",
                    "allow_live_writes is disabled; live Tool writes are disabled",
                )
            if not bool(_value(definition, "live_support", False)):
                return "live_unsupported", "Tool does not support live execution"
            approved = self._approved_live_tools()
            if not approved or str(_value(definition, "name", "")) not in approved:
                return "live_not_approved", "Tool is not in the live approval list"
            if _is_write(definition) and not self.write_guard_configured:
                return "write_guard_missing", "live writes require a write guard"
            risk = _value(definition, "risk_level", "low")
            risk = str(getattr(risk, "value", risk) or "low").lower()
            if (
                (
                    self.require_confirmation_for_writes
                    or (
                        self.require_confirmation_for_risk
                        and risk in {"high", "critical"}
                    )
                )
                and not _confirmed(request)
            ):
                return "confirmation_required", "high-risk live Tool calls require confirmation"
            if (
                self.require_confirmation_for_writes
                and _confirmed(request)
                and not (
                    isinstance(getattr(request, "context", None), Mapping)
                    and request.context.get("confirmation_payload")
                )
            ):
                return (
                    "confirmation_required",
                    "confirmed=true 必须携带当前计划的 confirmation_payload",
                )

        if _is_write(definition):
            if mode == "live" and _confirmed(request):
                if (
                    self.require_durable_idempotency
                    and self.idempotency_store is None
                ):
                    return (
                        "idempotency_store_error",
                        "live writes require a durable idempotency store",
                    )
                try:
                    normalized = json.dumps(
                        arguments, ensure_ascii=False, sort_keys=True, default=str,
                    )
                except (TypeError, ValueError):
                    normalized = repr(sorted(arguments.items()))
            field = _value(definition, "idempotency_key_field")
            key = arguments.get(str(field)) if field else None
            if key not in (None, ""):
                normalized_key = str(key)
                try:
                    duplicate = self._reserve_idempotency(
                        self._durable_identity(
                            definition, request, normalized_key,
                        ),
                        self._request_hash(arguments),
                        request,
                        call_id,
                    )
                except IdempotencyStoreUnavailable:
                    return (
                        "idempotency_store_error",
                        "durable idempotency store is unavailable",
                    )
                if duplicate:
                    return "duplicate_request", (
                        "Duplicate Tool idempotency key for the request"
                    )
            elif mode == "live" and _confirmed(request):
                try:
                    duplicate = self._reserve_idempotency(
                        self._durable_identity(
                            definition, request, normalized,
                        ),
                        self._request_hash(arguments),
                        request,
                        call_id,
                    )
                except IdempotencyStoreUnavailable:
                    return (
                        "idempotency_store_error",
                        "durable idempotency store is unavailable",
                    )
                if duplicate:
                    return "duplicate_request", (
                        "Duplicate write detected for the normalized Tool request"
                    )
        return None

    @staticmethod
    def _request_hash(arguments: Mapping[str, Any]) -> str:
        normalized = json.dumps(
            dict(arguments), ensure_ascii=False, sort_keys=True, default=str,
        )
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def _durable_identity(
        definition: Any, request: Any, value: str,
    ) -> tuple[str, str]:
        tenant = str(getattr(request, "tenant_id", "") or "default")
        user = str(getattr(request, "user_id", "") or "anonymous")
        tool = str(_value(definition, "name", "") or "")
        raw_key = f"{tenant}\x1f{user}\x1f{tool}\x1f{value}"
        return (
            "tool:" + hashlib.sha256(raw_key.encode("utf-8")).hexdigest(),
            "",
        )

    def _reserve_idempotency(
        self,
        identity: tuple[str, str],
        request_hash: str,
        request: Any,
        call_id: str,
    ) -> bool:
        store = self.idempotency_store
        if store is not None:
            key = identity[0]
            try:
                reserved = bool(store.reserve(
                    key,
                    request_hash=str(request_hash),
                    ttl_seconds=self.idempotency_ttl_seconds,
                ))
            except Exception as error:
                # A durable replay store is a safety boundary. Never execute
                # an external write when it cannot answer the reservation.
                raise IdempotencyStoreUnavailable(
                    "idempotency reservation failed",
                ) from error
            if reserved:
                call_key = (
                    str(getattr(request, "run_id", "") or ""),
                    str(getattr(request, "turn_id", "") or ""),
                    str(call_id or ""),
                )
                with self._lock:
                    self._reservations_by_call.setdefault(call_key, set()).add(
                        (key, str(request_hash)),
                    )
            return not reserved

        legacy_identity = (
            str(getattr(request, "run_id", "") or ""),
            identity[0],
            str(request_hash),
        )
        now = time.monotonic()
        with self._lock:
            expired = [
                key for key, timestamp in self._seen_idempotency.items()
                if now - timestamp >= self.idempotency_ttl_seconds
            ]
            for key in expired:
                self._seen_idempotency.pop(key, None)
            if legacy_identity in self._seen_idempotency:
                return True
            if len(self._seen_idempotency) >= self.max_idempotency_entries:
                oldest = min(
                    self._seen_idempotency,
                    key=self._seen_idempotency.get,
                )
                self._seen_idempotency.pop(oldest, None)
            self._seen_idempotency[legacy_identity] = now
            call_key = (
                str(getattr(request, "run_id", "") or ""),
                str(getattr(request, "turn_id", "") or ""),
                str(call_id or ""),
            )
            self._reservations_by_call.setdefault(call_key, set()).add(
                (legacy_identity[1], legacy_identity[2]),
            )
            return False

    def _mark_idempotency_executed(self, key: str, request_hash: str) -> bool:
        if self.idempotency_store is not None:
            try:
                self.idempotency_store.mark_executed(
                    key, request_hash=request_hash,
                )
            except Exception:
                return False
            return True
        # In-memory reservations are already durable for the lifetime of the
        # policy object; keeping them in the seen set preserves replay safety.
        return True

    def _release_idempotency(self, key: str, request_hash: str) -> bool:
        if self.idempotency_store is not None:
            try:
                self.idempotency_store.release(
                    key, request_hash=request_hash,
                )
            except Exception:
                return False
            return True
        with self._lock:
            for identity in list(self._seen_idempotency):
                if identity[1] == key and identity[2] == request_hash:
                    self._seen_idempotency.pop(identity, None)
        return True

    def _confirmation_payload(
        self,
        context: ToolCallContext,
        definition: Any,
        arguments: Mapping[str, Any],
        reason_code: str,
    ) -> dict[str, Any]:
        if reason_code != "confirmation_required" or not callable(
            self.confirmation_builder
        ):
            return {}
        try:
            payload = self.confirmation_builder(context, definition, arguments)
        except Exception:
            return {}
        return (
            {"confirmation_payload": dict(payload)}
            if isinstance(payload, Mapping) else {}
        )

    @staticmethod
    def _validate_schema(
        definition: Any, arguments: dict[str, Any],
    ) -> Optional[str]:
        schema = _schema(definition)
        required = schema.get("required") or ()
        missing = [
            str(name) for name in required
            if str(name) not in arguments
        ]
        if missing:
            return "missing required fields: " + ", ".join(missing)
        properties = schema.get("properties")
        if not isinstance(properties, Mapping):
            return None
        if schema.get("additionalProperties", schema.get("additional_properties", False)) is False:
            unknown = sorted(set(arguments) - set(properties))
            if unknown:
                return "unknown fields: " + ", ".join(unknown)
        for name, value in arguments.items():
            spec = properties.get(name)
            if not isinstance(spec, Mapping):
                continue
            expected = spec.get("type")
            if expected == "string" and not isinstance(value, str):
                return f"field '{name}' must be a string"
            if expected == "boolean" and not isinstance(value, bool):
                return f"field '{name}' must be a boolean"
            if expected == "object" and not isinstance(value, Mapping):
                return f"field '{name}' must be an object"
            if expected == "array" and not isinstance(value, list):
                return f"field '{name}' must be an array"
            if expected == "integer" and (isinstance(value, bool) or not isinstance(value, int)):
                return f"field '{name}' must be an integer"
            if expected == "number" and (
                isinstance(value, bool) or not isinstance(value, (int, float))
            ):
                return f"field '{name}' must be a number"
            enum = spec.get("enum")
            if isinstance(enum, list) and value not in enum:
                return f"field '{name}' has an unsupported value"
        return None

    def _audit(
        self,
        request: Any,
        tool_name: str,
        *,
        decision: str,
        reason_code: str,
    ) -> bool:
        event = {
            "run_id": str(getattr(request, "run_id", "") or ""),
            "turn_id": str(getattr(request, "turn_id", "") or ""),
            "tool_name": str(tool_name),
            "decision": decision,
            "reason_code": reason_code,
        }
        try:
            if callable(self.audit_sink):
                self.audit_sink(event)
            elif self.require_audit:
                callback = getattr(request, "event_callback", None)
                if not callable(callback):
                    return False
                callback({"type": "tool_audit", **event})
        except Exception:
            return False
        return True


__all__ = ["IdempotencyStoreUnavailable", "ToolExecutionPolicy"]
