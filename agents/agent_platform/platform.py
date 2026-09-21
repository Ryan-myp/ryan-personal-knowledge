"""Platform registry and generic Agent application composition."""

from __future__ import annotations

import threading
from typing import Any, Mapping, Optional, Protocol

from agents.agent_harness import AgentApplication

from .architecture import PlatformArchitecture
from .definitions import AgentDefinition, ScenarioDefinition
from .governance.policy import GovernancePolicy
from .runtime import PlatformApplication, PlatformDependencies
from .tools.policy import ToolExecutionPolicy


class AgentApplicationFactory(Protocol):
    """Factory seam for products with a specialized application runtime."""

    def create(
        self,
        definition: AgentDefinition,
        *,
        model: Any,
        skill_sources: tuple[Any, ...],
        tool_sources: tuple[Any, ...],
        **options: Any,
    ) -> Any:
        ...


class HarnessApplicationFactory:
    """Default factory backed by the standard Agent Harness."""

    def create(
        self,
        definition: AgentDefinition,
        *,
        model: Any,
        skill_sources: tuple[Any, ...],
        tool_sources: tuple[Any, ...],
        **options: Any,
    ) -> AgentApplication:
        options.setdefault("tool_policy", ToolExecutionPolicy())
        application = AgentApplication.create(
            model=model,
            system_prompt=definition.system_prompt,
            **options,
        )
        for source in skill_sources:
            application.register_skill_source(source)
        for source in tool_sources:
            application.register_tool_source(source)
        return application


class AgentPlatform:
    """Six-layer platform entry point for one Agent and many scenarios."""

    def __init__(
        self,
        *,
        architecture: Optional[PlatformArchitecture] = None,
        governance: Optional[GovernancePolicy] = None,
    ) -> None:
        self.architecture = architecture or PlatformArchitecture()
        self.governance = governance or GovernancePolicy()
        self._agents: dict[str, AgentDefinition] = {}
        self._scenarios: dict[str, ScenarioDefinition] = {}
        self._factory: Optional[AgentApplicationFactory] = None
        self._lock = threading.RLock()

    def register_agent(
        self,
        definition: AgentDefinition,
        *,
        factory: Optional[AgentApplicationFactory] = None,
    ) -> None:
        if not isinstance(definition, AgentDefinition):
            raise TypeError("definition must be an AgentDefinition")
        with self._lock:
            if self._agents:
                raise ValueError(
                    "single-Agent platform accepts exactly one Agent definition"
                )
            self._agents[definition.agent_id] = definition
            self._factory = factory or HarnessApplicationFactory()

    def register_scenario(self, definition: ScenarioDefinition) -> None:
        if not isinstance(definition, ScenarioDefinition):
            raise TypeError("definition must be a ScenarioDefinition")
        with self._lock:
            if definition.scenario_id in self._scenarios:
                raise ValueError(
                    f"Scenario '{definition.scenario_id}' is already registered"
                )
            if definition.agent_id not in self._agents:
                raise ValueError(
                    f"Scenario references unknown Agent '{definition.agent_id}'"
                )
            self._scenarios[definition.scenario_id] = definition

    def get_agent(self, agent_id: str) -> AgentDefinition:
        with self._lock:
            try:
                return self._agents[str(agent_id)]
            except KeyError as exc:
                raise KeyError(f"Agent '{agent_id}' not found") from exc

    @property
    def agent_id(self) -> str:
        with self._lock:
            if not self._agents:
                raise RuntimeError("no Agent definition is registered")
            return next(iter(self._agents))

    def get_scenario(self, scenario_id: str) -> ScenarioDefinition:
        with self._lock:
            try:
                return self._scenarios[str(scenario_id)]
            except KeyError as exc:
                raise KeyError(f"Scenario '{scenario_id}' not found") from exc

    def list_agents(self) -> list[AgentDefinition]:
        with self._lock:
            return list(self._agents.values())

    def list_scenarios(self) -> list[ScenarioDefinition]:
        with self._lock:
            return list(self._scenarios.values())

    def create_application(
        self,
        scenario_id: str,
        *,
        model: Any,
        dependencies: Optional[PlatformDependencies] = None,
        options: Optional[Mapping[str, Any]] = None,
        **kwargs: Any,
    ) -> PlatformApplication:
        """Create the concrete six-layer application for a scenario.

        ``options`` is explicit and merged with keyword options so callers
        cannot accidentally pass platform metadata as a runtime option.
        """
        scenario = self.get_scenario(scenario_id)
        definition = self.get_agent(scenario.agent_id)
        skill_sources, tool_sources = definition.select_sources(
            skill_source_ids=scenario.skill_source_ids,
            tool_source_ids=scenario.tool_source_ids,
        )
        factory = self._factory
        if factory is None:
            raise RuntimeError("no Agent application factory is registered")
        dependencies = (
            dependencies or PlatformDependencies()
        ).with_tool_sources(tool_sources)
        factory_options = dict(options or {})
        factory_options.update(kwargs)
        if dependencies.data.run_store is not None and "run_store" not in factory_options:
            factory_options["run_store"] = dependencies.data.run_store
        application = factory.create(
            definition,
            model=model,
            skill_sources=skill_sources,
            tool_sources=tool_sources,
            **factory_options,
        )
        return PlatformApplication(
            definition=definition,
            scenario=scenario,
            harness=application,
            architecture=self.architecture,
            governance=self.governance,
            dependencies=dependencies,
        )


__all__ = [
    "AgentApplicationFactory",
    "AgentPlatform",
    "HarnessApplicationFactory",
]
