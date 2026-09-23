"""Platform registry and generic Agent application composition."""

from __future__ import annotations

import threading
from typing import Any, Mapping, Optional

from agents.agent_harness import AgentApplication, InMemorySkillCatalog

from .architecture import PlatformArchitecture
from .definitions import AgentDefinition, ScenarioDefinition
from .governance.policy import GovernancePolicy
from .runtime import PlatformApplication, PlatformDependencies
from .tools.policy import ToolExecutionPolicy


def _merge_tool_sources(
    primary: tuple[Any, ...],
    additional: tuple[Any, ...],
) -> tuple[Any, ...]:
    merged = list(primary)
    by_id = {
        str(getattr(source, "source_id", "") or "").strip(): source
        for source in merged
    }
    for source in additional:
        source_id = str(getattr(source, "source_id", "") or "").strip()
        if not source_id:
            raise ValueError("integration Tool Source requires source_id")
        existing = by_id.get(source_id)
        if existing is not None:
            if existing is not source:
                raise ValueError(
                    f"duplicate integration Tool Source '{source_id}'"
                )
            continue
        by_id[source_id] = source
        merged.append(source)
    return tuple(merged)


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
        self._lock = threading.RLock()
        self._application: Optional[PlatformApplication] = None

    def register_agent(self, definition: AgentDefinition) -> None:
        if not isinstance(definition, AgentDefinition):
            raise TypeError("definition must be an AgentDefinition")
        with self._lock:
            if self._agents:
                raise ValueError(
                    "single-Agent platform accepts exactly one Agent definition"
                )
            self._agents[definition.agent_id] = definition

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
        with self._lock:
            existing = self._application
        if existing is not None:
            if model is not getattr(existing.agent, "model", None):
                raise ValueError(
                    "AgentPlatform already has a Runtime; model is immutable"
                )
            if dependencies is not None or options or kwargs:
                raise ValueError(
                    "AgentPlatform already has a Runtime; "
                    "dependencies and options are immutable"
                )
            definition = self.get_agent(scenario.agent_id)
            selected_skills, selected_tools = definition.select_sources(
                skill_source_ids=scenario.skill_source_ids,
                tool_source_ids=scenario.tool_source_ids,
            )
            definition_tool_ids = {
                str(getattr(source, "source_id", "") or "")
                for source in definition.tool_sources
            }
            integration_ids = tuple(
                str(getattr(source, "source_id", "") or "")
                for source in existing.dependencies.integrations.tool_sources
                if str(getattr(source, "source_id", "") or "")
                not in definition_tool_ids
            )
            return existing.for_scenario(
                scenario,
                skill_source_ids=tuple(
                    str(getattr(source, "source_id", "") or "")
                    for source in selected_skills
                ),
                tool_source_ids=(
                    tuple(
                        str(getattr(source, "source_id", "") or "")
                        for source in selected_tools
                    )
                    + integration_ids
                ),
            )
        definition = self.get_agent(scenario.agent_id)
        skill_sources, tool_sources = definition.select_sources(
            skill_source_ids=scenario.skill_source_ids,
            tool_source_ids=scenario.tool_source_ids,
        )
        dependencies = (
            dependencies or PlatformDependencies()
        )
        integration_sources = tuple(dependencies.integrations.tool_sources)
        # Validate the scenario selection above, then register the complete
        # Agent source graph once. Scenario views filter the shared catalogs
        # per Run; they never build another Runtime.
        all_tool_sources = _merge_tool_sources(
            tuple(definition.tool_sources),
            integration_sources,
        )
        dependencies = dependencies.with_tool_sources(all_tool_sources)
        factory_options = dict(options or {})
        factory_options.update(kwargs)
        factory_options.setdefault(
            "tool_policy",
            ToolExecutionPolicy(require_audit=self.governance.require_audit),
        )
        factory_options.setdefault(
            "default_execution_mode",
            self.governance.default_execution_mode,
        )
        factory_options.setdefault("max_tools", self.governance.max_tools)
        factory_options.setdefault("max_turns", self.governance.max_turns)
        factory_options.setdefault(
            "model_max_retries", self.governance.model_max_retries,
        )
        factory_options.setdefault(
            "model_retry_delay_seconds",
            self.governance.model_retry_delay_seconds,
        )
        factory_options.setdefault(
            "model_timeout_seconds", self.governance.model_timeout_seconds,
        )
        factory_options.setdefault(
            "tool_timeout_seconds", self.governance.tool_timeout_seconds,
        )
        factory_options.setdefault(
            "tool_max_retries", self.governance.tool_max_retries,
        )
        factory_options.setdefault(
            "tool_retry_delay_seconds",
            self.governance.tool_retry_delay_seconds,
        )
        factory_options.setdefault(
            "tool_circuit_failure_threshold",
            self.governance.tool_circuit_failure_threshold,
        )
        factory_options.setdefault(
            "tool_circuit_reset_seconds",
            self.governance.tool_circuit_reset_seconds,
        )
        factory_options.setdefault(
            "max_input_tokens", self.governance.max_input_tokens,
        )
        factory_options.setdefault(
            "max_output_tokens", self.governance.max_output_tokens,
        )
        factory_options.setdefault(
            "max_total_tokens", self.governance.max_total_tokens,
        )
        if "skill_catalog" not in factory_options:
            factory_options["skill_catalog"] = InMemorySkillCatalog(
                max_context_chars=self.governance.max_context_chars,
            )
        if dependencies.data.run_store is not None and "run_store" not in factory_options:
            factory_options["run_store"] = dependencies.data.run_store
        application = AgentApplication.create(
            model=model,
            system_prompt=definition.system_prompt,
            **factory_options,
        )
        try:
            for source in skill_sources:
                application.register_skill_source(source)
            for source in definition.skill_sources:
                if source not in skill_sources:
                    application.register_skill_source(source)
            for source in all_tool_sources:
                application.register_tool_source(source)
        except Exception:
            application.close()
            raise
        base_selector = factory_options.get("tool_selector")

        def select_tools(request: Any, tools: Any) -> list[Any]:
            selected = (
                list(base_selector(request, tools))
                if callable(base_selector) else list(tools)
            )
            context = getattr(request, "context", {})
            source_ids = (
                context.get("tool_source_ids")
                if isinstance(context, Mapping) else None
            )
            if source_ids is None:
                return selected
            catalog = getattr(application.runtime, "tool_registry", None)
            snapshot_getter = getattr(catalog, "source_snapshot", None)
            if not callable(snapshot_getter):
                return selected
            snapshot = snapshot_getter()
            allowed = {
                name
                for source_id in source_ids
                for name in snapshot.get(str(source_id), ())
            }
            return [
                item for item in selected
                if str(getattr(item, "name", None) or (
                    item.get("name") if isinstance(item, Mapping) else ""
                )) in allowed
            ]

        application.agent.tool_selector = select_tools
        platform_application = PlatformApplication(
            definition=definition,
            scenario=scenario,
            harness=application,
            architecture=self.architecture,
            governance=self.governance,
            dependencies=dependencies,
            skill_source_ids=tuple(
                str(getattr(source, "source_id", "") or "")
                for source in skill_sources
            ),
            tool_source_ids=tuple(
                str(getattr(source, "source_id", "") or "")
                for source in (
                    *tool_sources,
                    *integration_sources,
                )
            ),
        )
        with self._lock:
            self._application = platform_application
        return platform_application


__all__ = [
    "AgentPlatform",
]
