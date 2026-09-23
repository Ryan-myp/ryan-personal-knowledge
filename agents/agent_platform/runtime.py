"""The concrete six-layer Agent Platform runtime boundary."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field, replace
from typing import Any, Mapping, Optional

from agents.agent_harness import AgentApplication, RunStore, TurnRequest

from .architecture import PlatformArchitecture
from .definitions import AgentDefinition, ScenarioDefinition
from .governance.policy import GovernancePolicy
from .integrations.ports import ToolSource


_SAFE_HEALTH_KEYS = frozenset({
    "status",
    "ready",
    "latency_ms",
    "version",
    "component",
    "queue_depth",
    "in_flight",
})


def _safe_health_fields(value: Mapping[str, Any]) -> dict[str, Any]:
    """Keep health endpoints structured without copying arbitrary payloads."""
    result: dict[str, Any] = {}
    for key in _SAFE_HEALTH_KEYS:
        if key not in value:
            continue
        item = value[key]
        if item is None or isinstance(item, (bool, int, float, str)):
            result[key] = item
    return result


@dataclass(frozen=True)
class DataLayer:
    """Data dependencies injected into one platform application."""

    knowledge_store: Any = None
    memory_store: Any = None
    session_store: Any = None
    run_store: Optional[RunStore] = None


@dataclass(frozen=True)
class IntegrationLayer:
    """Selected external Tool Sources for one scenario."""

    tool_sources: tuple[ToolSource, ...] = ()
    registry: Any = None
    integrations: tuple[Any, ...] = ()

    def __post_init__(self) -> None:
        sources = tuple(self.tool_sources)
        integrations = tuple(self.integrations)
        ids: list[str] = []
        for integration in integrations:
            integration_id = str(
                getattr(integration, "integration_id", "") or ""
            ).strip()
            if not integration_id:
                raise ValueError(
                    "external integrations require a non-empty integration_id"
                )
            ids.append(integration_id)
        if len(set(ids)) != len(ids):
            raise ValueError("external integration ids must be unique")
        object.__setattr__(self, "tool_sources", sources)
        object.__setattr__(self, "integrations", integrations)


@dataclass
class InfrastructureLayer:
    """Lifecycle-managed deployment resources.

    Resources are intentionally opaque to the platform.  A deployment can
    provide queue consumers, protocol servers, connection pools or metrics
    exporters without teaching the Agent Runtime their implementation.
    """

    resources: tuple[Any, ...] = ()
    _started: bool = field(default=False, init=False, repr=False)
    _lock: threading.RLock = field(
        default_factory=threading.RLock, init=False, repr=False,
    )

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            started: list[Any] = []
            try:
                for resource in self.resources:
                    start = getattr(resource, "start", None)
                    if callable(start):
                        start()
                    started.append(resource)
            except Exception as error:
                for resource in reversed(started):
                    try:
                        self._stop_resource(resource)
                    except Exception as cleanup_error:
                        if hasattr(error, "add_note"):
                            error.add_note(
                                "infrastructure rollback failed: "
                                f"{type(cleanup_error).__name__}"
                            )
                raise
            self._started = True

    @property
    def started(self) -> bool:
        with self._lock:
            return self._started

    @staticmethod
    def _stop_resource(resource: Any) -> None:
        stop = getattr(resource, "stop", None)
        close = getattr(resource, "close", None)
        action = stop if callable(stop) else close
        if callable(action):
            action()

    def close(self) -> None:
        with self._lock:
            if not self._started:
                return
            first_error: Optional[Exception] = None
            for resource in reversed(self.resources):
                try:
                    self._stop_resource(resource)
                except Exception as error:
                    first_error = first_error or error
            self._started = False
            if first_error is not None:
                raise first_error

    def healthcheck(self) -> dict[str, Any]:
        """Return bounded status for deployment resources without leaking data."""
        with self._lock:
            resources = tuple(self.resources)
            started = self._started
        checks: list[dict[str, Any]] = []
        for index, resource in enumerate(resources):
            check = getattr(resource, "check", None)
            if not callable(check):
                check = getattr(resource, "healthcheck", None)
            item: dict[str, Any] = {
                "name": type(resource).__name__,
                "index": index,
                "status": "unknown",
            }
            if not started:
                item["status"] = "not_started"
            elif not callable(check):
                item["status"] = "ok"
            else:
                try:
                    result = check()
                    if isinstance(result, Mapping):
                        item.update(_safe_health_fields(result))
                    item["status"] = str(item.get("status") or "ok")
                except Exception as error:
                    item["status"] = "unhealthy"
                    item["error_type"] = type(error).__name__
            checks.append(item)
        overall = "ok"
        if any(item["status"] == "unhealthy" for item in checks):
            overall = "unhealthy"
        elif not started:
            overall = "not_started"
        elif any(item["status"] == "unknown" for item in checks):
            overall = "degraded"
        return {
            "status": overall,
            "started": started,
            "resources": checks,
        }


@dataclass(frozen=True)
class PlatformDependencies:
    """The six-layer dependency bundle for one concrete application."""

    data: DataLayer = field(default_factory=DataLayer)
    integrations: IntegrationLayer = field(default_factory=IntegrationLayer)
    infrastructure: InfrastructureLayer = field(
        default_factory=InfrastructureLayer,
    )

    def with_tool_sources(
        self, tool_sources: tuple[ToolSource, ...],
    ) -> "PlatformDependencies":
        return replace(
            self,
            integrations=replace(
                self.integrations,
                tool_sources=tuple(tool_sources),
            ),
        )


@dataclass
class PlatformApplication:
    """Concrete runtime assembled from all six platform layers."""

    definition: AgentDefinition
    scenario: ScenarioDefinition
    harness: Any
    architecture: PlatformArchitecture
    governance: GovernancePolicy
    dependencies: PlatformDependencies
    _started: bool = field(default=False, init=False, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)
    _started_integrations: tuple[Any, ...] = field(
        default=(),
        init=False,
        repr=False,
    )
    _lock: threading.RLock = field(
        default_factory=threading.RLock, init=False, repr=False,
    )

    @property
    def runtime(self) -> Any:
        return getattr(self.harness, "runtime", self.harness)

    @property
    def agent(self) -> Any:
        return getattr(self.harness, "agent", None)

    @property
    def skills(self) -> Any:
        return getattr(self.harness, "skills", None)

    @property
    def tools(self) -> Any:
        return getattr(self.harness, "tools", None)

    @property
    def data(self) -> DataLayer:
        """Injected data ports for application-specific services."""
        return self.dependencies.data

    @property
    def integrations(self) -> IntegrationLayer:
        """Injected Tool Sources and external integration ports."""
        return self.dependencies.integrations

    @property
    def infrastructure(self) -> InfrastructureLayer:
        """Lifecycle-managed deployment resources."""
        return self.dependencies.infrastructure

    def layer_snapshot(self) -> tuple[str, ...]:
        return self.architecture.layer_names()

    @property
    def started(self) -> bool:
        with self._lock:
            return self._started

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed

    def start(self) -> None:
        with self._lock:
            if self._closed:
                raise RuntimeError("Platform application is closed")
            if self._started:
                return
            started_integrations: list[Any] = []
            infrastructure_started = False
            try:
                for integration in self.dependencies.integrations.integrations:
                    started_integrations.append(integration)
                    start = getattr(integration, "start", None)
                    if callable(start):
                        start()
                self.dependencies.infrastructure.start()
                infrastructure_started = True
                self._started_integrations = tuple(started_integrations)
                self._started = True
            except Exception:
                if infrastructure_started:
                    try:
                        self.dependencies.infrastructure.close()
                    except Exception:
                        pass
                for integration in reversed(started_integrations):
                    self._close_component(integration)
                self._started_integrations = ()
                raise

    def prompt(self, user_input: str, **kwargs: Any) -> Any:
        self.start()
        return self.harness.prompt(user_input, **kwargs)

    def run(self, request: TurnRequest) -> Any:
        self.start()
        return self.runtime.run(request)

    def register_tool(
        self, definition: Any, executor: Any, *, source_id: str = "local",
    ) -> Any:
        register = getattr(self.runtime, "register_tool", None)
        if not callable(register):
            raise TypeError("platform runtime does not support Tool registration")
        return register(definition, executor, source_id=source_id)

    def register_tool_source(self, source: Any) -> Any:
        register = getattr(self.runtime, "register_tool_source", None)
        if not callable(register):
            raise TypeError("platform runtime does not support Tool Source registration")
        return register(source)

    def register_skill_source(self, source: Any) -> Any:
        register = getattr(self.runtime, "register_skill_source", None)
        if not callable(register):
            raise TypeError(
                "platform runtime does not support Skill source registration"
            )
        return register(source)

    def unregister_tool_source(self, source_id: str) -> Any:
        unregister = getattr(self.runtime, "unregister_tool_source", None)
        if not callable(unregister):
            raise TypeError("platform runtime does not support Tool Source removal")
        return unregister(source_id)

    def unregister_skill_source(self, source_id: str) -> Any:
        unregister = getattr(self.runtime, "unregister_skill_source", None)
        if not callable(unregister):
            raise TypeError(
                "platform runtime does not support Skill source removal"
            )
        return unregister(source_id)

    def list_tools(self) -> list[Any]:
        list_tools = getattr(self.runtime, "list_tools", None)
        if callable(list_tools):
            return list(list_tools())
        catalog = getattr(self.runtime, "tool_registry", None)
        list_all = getattr(catalog, "list_all", None)
        return list(list_all()) if callable(list_all) else []

    def list_skills(self) -> list[Any]:
        list_skills = getattr(self.runtime, "list_skills", None)
        return list(list_skills()) if callable(list_skills) else []

    @staticmethod
    def _close_component(component: Any) -> None:
        close = getattr(component, "close", None)
        if not callable(close):
            close = getattr(component, "stop", None)
        if callable(close):
            close()

    @staticmethod
    def _integration_health(
        integration: Any,
        *,
        started: bool,
    ) -> dict[str, Any]:
        item = {
            "integration_id": str(
                getattr(integration, "integration_id", type(integration).__name__)
            ),
            "status": "not_started" if not started else "unknown",
        }
        if not started:
            return item
        check = getattr(integration, "healthcheck", None)
        if not callable(check):
            item["status"] = "ok"
            return item
        try:
            result = check()
            if isinstance(result, Mapping):
                item.update(_safe_health_fields(result))
            item["status"] = str(item.get("status") or "ok")
        except Exception as error:
            item["status"] = "unhealthy"
            item["error_type"] = type(error).__name__
        return item

    def healthcheck(self) -> dict[str, Any]:
        """Return safe health data for all six-layer runtime components."""
        runtime_health = {}
        check = getattr(self.runtime, "healthcheck", None)
        if callable(check):
            result = check()
            if isinstance(result, Mapping):
                runtime_health = dict(result)
        integrations = [
            self._integration_health(item, started=self.started)
            for item in self.dependencies.integrations.integrations
        ]
        infrastructure = self.dependencies.infrastructure.healthcheck()
        statuses = [
            str(runtime_health.get("status") or "ok"),
            str(infrastructure.get("status") or "ok"),
            *[str(item.get("status") or "unknown") for item in integrations],
        ]
        status = "ok"
        if "unhealthy" in statuses:
            status = "unhealthy"
        elif "not_started" in statuses or "unknown" in statuses:
            status = "degraded"
        return {
            "status": status,
            "started": self.started,
            "closed": self.closed,
            "runtime": runtime_health,
            "integrations": integrations,
            "infrastructure": infrastructure,
            "tools": len(self.list_tools()),
            "skills": len(self.list_skills()),
        }

    def readiness(self) -> dict[str, Any]:
        """Return whether the application can accept a new Run."""
        health = self.healthcheck()
        ready = (
            self.started
            and not self.closed
            and health["status"] != "unhealthy"
            and health["runtime"].get("status", "ok") != "closed"
        )
        return {
            "ready": ready,
            "status": "ready" if ready else "not_ready",
            "reason": (
                None
                if ready
                else (
                    "closed"
                    if self.closed
                    else ("not_started" if not self.started else health["status"])
                )
            ),
            "health": health,
        }

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            first_error: Optional[Exception] = None
            try:
                close = getattr(self.harness, "close", None)
                if callable(close):
                    close()
            except Exception as error:
                first_error = error
            for integration in reversed(self._started_integrations):
                try:
                    self._close_component(integration)
                except Exception as error:
                    first_error = first_error or error
            try:
                self.dependencies.infrastructure.close()
            except Exception as error:
                first_error = first_error or error
            self._started = False
            self._started_integrations = ()
            self._closed = True
            if first_error is not None:
                raise first_error


__all__ = [
    "DataLayer",
    "InfrastructureLayer",
    "IntegrationLayer",
    "PlatformApplication",
    "PlatformDependencies",
]
