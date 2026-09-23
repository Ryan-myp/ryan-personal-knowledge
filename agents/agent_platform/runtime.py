"""The concrete six-layer Agent Platform runtime boundary."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field, replace
from typing import Any, Mapping, Optional

from agents.agent_harness import TurnRequest

from .architecture import PlatformArchitecture
from .definitions import AgentDefinition, ScenarioDefinition
from .governance.policy import GovernancePolicy
from .integrations.ports import ToolSource
from .data.ports import (
    KnowledgeStore,
    MemoryStore,
    RunStore as DataRunStore,
    SessionStore,
)


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

    knowledge_store: Optional[KnowledgeStore] = None
    memory_store: Optional[MemoryStore] = None
    session_store: Optional[SessionStore] = None
    run_store: Optional[DataRunStore] = None

    def components(self) -> tuple[tuple[str, Any], ...]:
        """Return configured stores once, preserving declaration order."""
        values = (
            ("knowledge", self.knowledge_store),
            ("memory", self.memory_store),
            ("session", self.session_store),
            ("run", self.run_store),
        )
        seen: set[int] = set()
        result: list[tuple[str, Any]] = []
        for name, component in values:
            if component is None or id(component) in seen:
                continue
            seen.add(id(component))
            result.append((name, component))
        return tuple(result)

    def healthcheck(self, *, started: bool) -> dict[str, Any]:
        """Check configured stores without probing them with a data operation."""
        components = self.components()
        if not components:
            return {
                "status": "not_configured",
                "started": started,
                "configured": 0,
                "stores": [],
            }
        checks: list[dict[str, Any]] = []
        for name, component in components:
            item: dict[str, Any] = {
                "name": name,
                "component": type(component).__name__,
                "status": "not_started" if not started else "unknown",
            }
            if started:
                check = getattr(component, "check", None)
                if not callable(check):
                    check = getattr(component, "healthcheck", None)
                if not callable(check):
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
        statuses = {str(item["status"]) for item in checks}
        return {
            "status": (
                "unhealthy"
                if "unhealthy" in statuses
                else "degraded"
                if "unknown" in statuses
                else "not_started"
                if not started
                else "ok"
            ),
            "started": started,
            "configured": len(checks),
            "stores": checks,
        }

    @staticmethod
    def _close_component(component: Any) -> None:
        close = getattr(component, "close", None)
        if not callable(close):
            close = getattr(component, "stop", None)
        if callable(close):
            close()


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


class _ToolCatalogView:
    """Scenario-scoped read view over the one shared Tool catalog."""

    def __init__(self, catalog: Any, source_ids: tuple[str, ...]) -> None:
        self._catalog = catalog
        self._source_ids = tuple(source_ids)

    def _allowed_names(self) -> set[str]:
        snapshot_getter = getattr(self._catalog, "source_snapshot", None)
        if not callable(snapshot_getter):
            return set()
        snapshot = snapshot_getter()
        return {
            name
            for source_id in self._source_ids
            for name in snapshot.get(source_id, ())
        }

    def list_tools(self) -> list[Any]:
        allowed = self._allowed_names()
        if not allowed and not callable(
            getattr(self._catalog, "source_snapshot", None)
        ):
            return list(self._catalog.list_tools())
        return [
            item for item in self._catalog.list_tools()
            if str(getattr(item, "name", None) or (
                item.get("name") if isinstance(item, Mapping) else ""
            )) in allowed
        ]

    def get_binding(self, name: str) -> Any:
        if (
            callable(getattr(self._catalog, "source_snapshot", None))
            and str(name) not in self._allowed_names()
        ):
            raise KeyError(f"Tool '{name}' is not enabled for this scenario")
        return self._catalog.get_binding(name)

    def source_snapshot(self) -> dict[str, list[str]]:
        snapshot_getter = getattr(self._catalog, "source_snapshot", None)
        if not callable(snapshot_getter):
            return {}
        snapshot = snapshot_getter()
        return {
            source_id: list(snapshot.get(source_id, ()))
            for source_id in self._source_ids
            if source_id in snapshot
        }

    def healthcheck(self) -> dict[str, Any]:
        result = dict(self._catalog.healthcheck())
        result["tools"] = len(self.list_tools())
        result["source_snapshot"] = self.source_snapshot()
        result["sources"] = len(result["source_snapshot"])
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._catalog, name)


class _SkillCatalogView:
    """Scenario-scoped read view over the one shared Skill catalog."""

    def __init__(self, catalog: Any, source_ids: tuple[str, ...]) -> None:
        self._catalog = catalog
        self._source_ids = tuple(source_ids)

    def list_skills(self) -> list[Any]:
        snapshot_getter = getattr(self._catalog, "source_snapshot", None)
        if not callable(snapshot_getter):
            return list(self._catalog.list_skills())
        allowed = {
            name
            for source_id in self._source_ids
            for name in self._catalog.source_snapshot().get(source_id, ())
        }
        return [
            item for item in self._catalog.list_skills()
            if str(getattr(item, "name", "")) in allowed
        ]

    def build_context(self, user_input: str) -> str:
        return self._catalog.build_context(
            user_input,
            source_ids=self._source_ids,
        )

    def source_snapshot(self) -> dict[str, list[str]]:
        snapshot_getter = getattr(self._catalog, "source_snapshot", None)
        if not callable(snapshot_getter):
            return {}
        snapshot = snapshot_getter()
        return {
            source_id: list(snapshot.get(source_id, ()))
            for source_id in self._source_ids
            if source_id in snapshot
        }

    def healthcheck(self) -> dict[str, Any]:
        result = dict(self._catalog.healthcheck())
        result["skills"] = len(self.list_skills())
        result["source_snapshot"] = self.source_snapshot()
        result["sources"] = len(result["source_snapshot"])
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._catalog, name)


@dataclass
class PlatformApplication:
    """Concrete runtime assembled from all six platform layers."""

    definition: AgentDefinition
    scenario: ScenarioDefinition
    harness: Any
    architecture: PlatformArchitecture
    governance: GovernancePolicy
    dependencies: PlatformDependencies
    skill_source_ids: tuple[str, ...] = ()
    tool_source_ids: tuple[str, ...] = ()
    _started: bool = field(default=False, init=False, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)
    _started_data_components: tuple[Any, ...] = field(
        default=(),
        init=False,
        repr=False,
    )
    _started_integrations: tuple[Any, ...] = field(
        default=(),
        init=False,
        repr=False,
    )
    _lock: threading.RLock = field(
        default_factory=threading.RLock, init=False, repr=False,
    )
    _owner: Optional["PlatformApplication"] = field(
        default=None, init=False, repr=False,
    )

    @property
    def _root(self) -> "PlatformApplication":
        return self._owner or self

    @property
    def runtime(self) -> Any:
        return getattr(self.harness, "runtime", self.harness)

    @property
    def agent(self) -> Any:
        return getattr(self.harness, "agent", None)

    @property
    def skills(self) -> Any:
        catalog = getattr(self.harness, "skills", None)
        return _SkillCatalogView(catalog, self.skill_source_ids)

    @property
    def tools(self) -> Any:
        catalog = getattr(self.harness, "tools", None)
        return _ToolCatalogView(catalog, self.tool_source_ids)

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
        root = self._root
        with root._lock:
            return root._started

    @property
    def closed(self) -> bool:
        root = self._root
        with root._lock:
            return root._closed

    def for_scenario(
        self,
        scenario: ScenarioDefinition,
        *,
        skill_source_ids: tuple[str, ...],
        tool_source_ids: tuple[str, ...],
    ) -> "PlatformApplication":
        """Return a scenario view without creating another Runtime."""
        view = PlatformApplication(
            definition=self.definition,
            scenario=scenario,
            harness=self.harness,
            architecture=self.architecture,
            governance=self.governance,
            dependencies=self.dependencies,
            skill_source_ids=skill_source_ids,
            tool_source_ids=tool_source_ids,
        )
        view._owner = self._root
        return view

    def _request_for_scenario(self, request: TurnRequest) -> TurnRequest:
        context = dict(request.context or {})
        context["platform_scenario_id"] = self.scenario.scenario_id
        context["skill_source_ids"] = list(self.skill_source_ids)
        context["tool_source_ids"] = list(self.tool_source_ids)
        return replace(request, context=context)

    def start(self) -> None:
        if self._owner is not None:
            self._root.start()
            return
        with self._lock:
            if self._closed:
                raise RuntimeError("Platform application is closed")
            if self._started:
                return
            started_data: list[Any] = []
            started_integrations: list[Any] = []
            infrastructure_started = False
            try:
                for _name, component in self.dependencies.data.components():
                    start = getattr(component, "start", None)
                    if callable(start):
                        start()
                    started_data.append(component)
                for integration in self.dependencies.integrations.integrations:
                    started_integrations.append(integration)
                    start = getattr(integration, "start", None)
                    if callable(start):
                        start()
                self.dependencies.infrastructure.start()
                infrastructure_started = True
                self._started_data_components = tuple(started_data)
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
                for component in reversed(started_data):
                    self._close_component(component)
                self._started_data_components = ()
                self._started_integrations = ()
                raise

    def prompt(self, user_input: str, **kwargs: Any) -> Any:
        self.start()
        context = dict(kwargs.pop("context", {}) or {})
        context.update({
            "platform_scenario_id": self.scenario.scenario_id,
            "skill_source_ids": list(self.skill_source_ids),
            "tool_source_ids": list(self.tool_source_ids),
        })
        return self.harness.prompt(user_input, context=context, **kwargs)

    def run(self, request: TurnRequest) -> Any:
        self.start()
        return self.runtime.run(self._request_for_scenario(request))

    def register_tool(
        self, definition: Any, executor: Any, *, source_id: str = "local",
    ) -> Any:
        register = getattr(self.runtime, "register_tool", None)
        if not callable(register):
            raise TypeError("platform runtime does not support Tool registration")
        name = (
            definition.get("name")
            if isinstance(definition, Mapping)
            else getattr(definition, "name", "tool")
        )
        result = register(definition, executor, source_id=source_id)
        source_key = f"{source_id}:{name}"
        if source_key not in self.tool_source_ids:
            self.tool_source_ids = (*self.tool_source_ids, source_key)
        return result

    def register_tool_source(self, source: Any) -> Any:
        register = getattr(self.runtime, "register_tool_source", None)
        if not callable(register):
            raise TypeError("platform runtime does not support Tool Source registration")
        result = register(source)
        source_id = str(getattr(source, "source_id", "") or "").strip()
        if source_id and source_id not in self.tool_source_ids:
            self.tool_source_ids = (*self.tool_source_ids, source_id)
        return result

    def register_skill_source(self, source: Any) -> Any:
        register = getattr(self.runtime, "register_skill_source", None)
        if not callable(register):
            raise TypeError(
                "platform runtime does not support Skill source registration"
            )
        result = register(source)
        source_id = str(getattr(source, "source_id", "") or "").strip()
        if source_id and source_id not in self.skill_source_ids:
            self.skill_source_ids = (*self.skill_source_ids, source_id)
        return result

    def unregister_tool_source(self, source_id: str) -> Any:
        unregister = getattr(self.runtime, "unregister_tool_source", None)
        if not callable(unregister):
            raise TypeError("platform runtime does not support Tool Source removal")
        result = unregister(source_id)
        self.tool_source_ids = tuple(
            item for item in self.tool_source_ids
            if item != str(source_id)
        )
        return result

    def unregister_skill_source(self, source_id: str) -> Any:
        unregister = getattr(self.runtime, "unregister_skill_source", None)
        if not callable(unregister):
            raise TypeError(
                "platform runtime does not support Skill source removal"
            )
        result = unregister(source_id)
        self.skill_source_ids = tuple(
            item for item in self.skill_source_ids
            if item != str(source_id)
        )
        return result

    def list_tools(self) -> list[Any]:
        return list(self.tools.list_tools())

    def list_skills(self) -> list[Any]:
        return list(self.skills.list_skills())

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
        if self._owner is not None:
            return self._root.healthcheck()
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
        data = self.dependencies.data.healthcheck(started=self.started)
        infrastructure = self.dependencies.infrastructure.healthcheck()
        statuses = [
            str(runtime_health.get("status") or "ok"),
            str(infrastructure.get("status") or "ok"),
            *[str(item.get("status") or "unknown") for item in integrations],
        ]
        if data["configured"]:
            statuses.append(str(data.get("status") or "unknown"))
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
            "data": data,
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
        if self._owner is not None:
            return
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
            for component in reversed(self._started_data_components):
                try:
                    self._close_component(component)
                except Exception as error:
                    first_error = first_error or error
            try:
                self.dependencies.infrastructure.close()
            except Exception as error:
                first_error = first_error or error
            self._started = False
            self._started_data_components = ()
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
