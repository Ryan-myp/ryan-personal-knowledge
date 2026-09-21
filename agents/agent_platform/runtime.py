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
            except Exception:
                for resource in reversed(started):
                    close = getattr(resource, "close", None)
                    if callable(close):
                        try:
                            close()
                        except Exception:
                            pass
                raise
            self._started = True

    def close(self) -> None:
        with self._lock:
            if not self._started:
                return
            first_error: Optional[Exception] = None
            for resource in reversed(self.resources):
                close = getattr(resource, "close", None)
                if not callable(close):
                    continue
                try:
                    close()
                except Exception as error:
                    first_error = first_error or error
            self._started = False
            if first_error is not None:
                raise first_error


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

    def layer_snapshot(self) -> tuple[str, ...]:
        return self.architecture.layer_names()

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self.dependencies.infrastructure.start()
            self._started = True

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

    def unregister_tool_source(self, source_id: str) -> Any:
        unregister = getattr(self.runtime, "unregister_tool_source", None)
        if not callable(unregister):
            raise TypeError("platform runtime does not support Tool Source removal")
        return unregister(source_id)

    def list_tools(self) -> list[Any]:
        list_tools = getattr(self.runtime, "list_tools", None)
        if callable(list_tools):
            return list(list_tools())
        catalog = getattr(self.runtime, "tool_registry", None)
        list_all = getattr(catalog, "list_all", None)
        return list(list_all()) if callable(list_all) else []

    def close(self) -> None:
        with self._lock:
            first_error: Optional[Exception] = None
            try:
                close = getattr(self.harness, "close", None)
                if callable(close):
                    close()
            except Exception as error:
                first_error = error
            try:
                self.dependencies.infrastructure.close()
            except Exception as error:
                first_error = first_error or error
            self._started = False
            if first_error is not None:
                raise first_error


__all__ = [
    "DataLayer",
    "InfrastructureLayer",
    "IntegrationLayer",
    "PlatformApplication",
    "PlatformDependencies",
]
