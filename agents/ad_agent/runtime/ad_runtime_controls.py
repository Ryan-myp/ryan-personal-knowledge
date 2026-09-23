"""Runtime control services for the advertising application boundary."""

from __future__ import annotations

import logging
import time
from collections import OrderedDict
from contextvars import ContextVar
from types import MappingProxyType
from typing import Any, Optional

from agents.agent_harness import DeploymentHealth, HealthCheck

from ..core.features import RuntimeFeature
from ..core.intent import LLMIntentParser
from ..core.interfaces import ExecutionMode, ToolEffect
from ..domain.ad.response import LLMResponseSynthesizer
from ..features.factory import feature_for_intent
from ..core.memory import MemoryManager
from .security import RuntimeSecurity

logger = logging.getLogger(__name__)

_EXECUTION_MODE_CACHE_TTL_SECONDS = 5.0
_EXECUTION_MODE_CACHE_MAX_ENTRIES = 1024


class AdvertisingRuntimeControls:
    """Own mutable runtime controls without owning Run execution."""

    def __init__(
        self,
        runtime: Any,
        *,
        mode_context: ContextVar[Optional[str]],
    ) -> None:
        self.runtime = runtime
        self.mode_context = mode_context

    @staticmethod
    def validate_execution_mode(execution_mode: str) -> str:
        mode = str(execution_mode or "").strip().lower()
        if mode not in {item.value for item in ExecutionMode}:
            raise ValueError(f"Unsupported execution_mode: {execution_mode}")
        return mode

    @property
    def execution_mode(self) -> str:
        return self.mode_context.get() or self.runtime._execution_mode

    @execution_mode.setter
    def execution_mode(self, value: str) -> None:
        self.runtime._execution_mode = self.validate_execution_mode(value)

    def set_execution_mode(
        self,
        execution_mode: str,
        *,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        mode = self.validate_execution_mode(execution_mode)
        tenant = str(tenant_id or "").strip()
        user = str(user_id or "").strip()
        with self.runtime._execution_mode_lock:
            if tenant and user:
                self._cache_execution_mode((tenant, user), mode)
                store = self.runtime._persistence_store
                persist = getattr(store, "set_execution_mode", None)
                if callable(persist):
                    try:
                        persist(tenant, user, mode)
                    except Exception:
                        logger.warning(
                            "Failed to persist execution mode preference",
                            extra={"tenant_id": tenant, "user_id": user},
                            exc_info=True,
                        )
            else:
                self.runtime._execution_mode = mode

    def _cache_execution_mode(
        self,
        key: tuple[str, str],
        mode: str,
    ) -> None:
        cache = self.runtime._execution_mode_cache
        cache.pop(key, None)
        cache[key] = (
            mode,
            time.monotonic() + _EXECUTION_MODE_CACHE_TTL_SECONDS,
        )
        while len(cache) > _EXECUTION_MODE_CACHE_MAX_ENTRIES:
            cache.popitem(last=False)

    def get_execution_mode(
        self,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> str:
        tenant = str(tenant_id or "").strip()
        user = str(user_id or "").strip()
        with self.runtime._execution_mode_lock:
            if tenant and user:
                key = (tenant, user)
                cached = self.runtime._execution_mode_cache.get(key)
                if cached:
                    cached_mode, expires_at = cached
                    if time.monotonic() < expires_at:
                        self.runtime._execution_mode_cache.move_to_end(key)
                        return cached_mode
                    self.runtime._execution_mode_cache.pop(key, None)
                persisted = getattr(
                    self.runtime._persistence_store,
                    "get_execution_mode",
                    None,
                )
                if callable(persisted):
                    try:
                        stored = persisted(tenant, user)
                        if stored is not None:
                            mode = self.validate_execution_mode(stored)
                            self._cache_execution_mode(key, mode)
                            return mode
                    except ValueError:
                        logger.warning(
                            "Ignoring invalid persisted execution mode preference",
                            extra={"tenant_id": tenant, "user_id": user},
                        )
                    except Exception:
                        logger.warning(
                            "Failed to load execution mode preference",
                            extra={"tenant_id": tenant, "user_id": user},
                            exc_info=True,
                        )
                return self.runtime._execution_mode
            return self.runtime._execution_mode

    def feature_for_intent(self, intent: Any) -> Optional[RuntimeFeature]:
        return feature_for_intent(self.runtime.features, intent)

    def close(self, wait: bool = False) -> None:
        self.runtime.supervisor.close(wait=wait)

    def readiness(self) -> dict[str, Any]:
        runtime = self.runtime
        try:
            tool_count = len(runtime.registry.list_all())
        except Exception:
            tool_count = 0
        model_ready = not runtime.require_llm or runtime._llm is not None
        supervisor_health = runtime.supervisor.health()
        checks = {
            "runtime": True,
            "llm": model_ready,
            "tool_registry": tool_count > 0,
            "persistence": (
                runtime._persistence_store is None
                or supervisor_health.get("backend", {}).get("status") == "healthy"
            ),
            "workers": (
                runtime._persistence_store is None
                or supervisor_health.get("status") == "healthy"
                or not runtime.supervisor.task_executor
            ),
        }
        report = {
            "status": "ready" if all(checks.values()) else "not_ready",
            "checks": checks,
            "tool_count": tool_count,
            "supervisor": supervisor_health,
        }
        report["deployment_health"] = self.deployment_health().to_dict()
        return report

    def deployment_health(self) -> DeploymentHealth:
        """Aggregate optional deployment adapters without inventing health."""
        runtime = self.runtime
        checks: list[HealthCheck] = [
            HealthCheck(
                "runtime",
                "healthy",
                details={"execution_mode": str(runtime.execution_mode)},
            ),
            HealthCheck(
                "metrics",
                "configured" if getattr(runtime, "metrics", None) else "disabled",
                required=False,
            ),
            HealthCheck(
                "trace",
                "configured" if getattr(runtime, "trace_sink", None) else "disabled",
                required=False,
            ),
            HealthCheck(
                "alerts",
                "configured" if getattr(runtime, "alert_sink", None) else "disabled",
                required=False,
            ),
        ]
        credential_provider = getattr(runtime, "credential_provider", None)
        if credential_provider is not None:
            try:
                raw = credential_provider.healthcheck()
                status = str(raw.get("status") or "unknown")
                details = {
                    key: raw[key]
                    for key in ("component", "version", "latency_ms")
                    if key in raw
                }
            except Exception as exc:
                status = "unhealthy"
                details = {"error_type": type(exc).__name__}
        else:
            status = "configured" if getattr(runtime, "_credentials", {}) else "unconfigured"
            details = {"source": "runtime_config"}
        checks.append(HealthCheck(
            "credentials",
            status,
            required=str(runtime.execution_mode) == "live",
            details=details,
        ))

        quota_provider = getattr(runtime, "quota_provider", None)
        if quota_provider is not None:
            try:
                raw = quota_provider.snapshot()
                status = str(raw.get("status") or "healthy")
                details = {
                    key: raw[key]
                    for key in ("provider", "remaining", "reset_at")
                    if key in raw
                }
            except Exception as exc:
                status = "unhealthy"
                details = {"error_type": type(exc).__name__}
        else:
            status = "disabled"
            details = {}
        checks.append(HealthCheck(
            "quota",
            status,
            required=False,
            details=details,
        ))
        return DeploymentHealth.from_checks(checks)

    @staticmethod
    def default_outbox_delivery(event: Any) -> None:
        logger.info(
            "Outbox event consumed by default sink: event_id=%s run_id=%s type=%s",
            getattr(event, "event_id", ""),
            getattr(event, "run_id", ""),
            getattr(event, "event_type", ""),
        )

    @property
    def memory_manager(self) -> Optional[MemoryManager]:
        return self.runtime._memory_manager

    def set_auto_memory_capture_enabled(self, enabled: bool) -> None:
        self.runtime.auto_memory_capture_enabled = bool(enabled)
        manager = self.runtime._memory_manager
        if manager is not None:
            manager.set_auto_capture_enabled(bool(enabled))

    def inject_llm(self, llm_client: Any) -> None:
        runtime = self.runtime
        runtime._llm = llm_client
        if runtime.response_synthesizer is None and llm_client is not None:
            runtime.response_synthesizer = LLMResponseSynthesizer(
                profile=runtime.agent_profile,
            )
        if isinstance(runtime.intent_parser, LLMIntentParser):
            runtime.intent_parser.inject_llm(llm_client)

    def assert_llm_ready(self) -> None:
        runtime = self.runtime
        if (
            runtime.require_llm
            and isinstance(runtime.intent_parser, LLMIntentParser)
            and runtime._llm is None
        ):
            raise RuntimeError(
                "LLM client is required; configure the model before starting the Agent"
            )

    def enable_read_only_mode(self) -> None:
        self.runtime._read_only_mode = True
        self.filter_write_tools()

    def filter_write_tools(self) -> None:
        runtime = self.runtime
        write_tools = [
            definition.name
            for definition in runtime.registry.list_all()
            if definition.effect_class in (
                ToolEffect.WRITE,
                ToolEffect.EXTERNAL_WRITE,
            )
        ]
        for name in write_tools:
            try:
                runtime.registry.unregister(name)
                logger.debug("只读模式：已移除写工具 %s", name)
            except Exception as error:
                logger.warning("移除工具 %s 失败: %s", name, error)
        logger.info("只读模式已启用，已过滤 %s 个写工具", len(write_tools))

    @staticmethod
    def freeze_credentials(value: Any) -> Any:
        if isinstance(value, dict):
            return MappingProxyType({
                key: AdvertisingRuntimeControls.freeze_credentials(item)
                for key, item in value.items()
            })
        if isinstance(value, list):
            return tuple(
                AdvertisingRuntimeControls.freeze_credentials(item)
                for item in value
            )
        return value

    @staticmethod
    def redact_for_persistence(value: Any) -> Any:
        return RuntimeSecurity.redact_for_persistence(value)


__all__ = [
    "AdvertisingRuntimeControls",
    "_EXECUTION_MODE_CACHE_MAX_ENTRIES",
    "_EXECUTION_MODE_CACHE_TTL_SECONDS",
]
