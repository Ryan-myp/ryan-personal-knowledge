"""Agent and application-scenario definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from agents.agent_harness import SkillSource, ToolSource


def _source_id(source: Any) -> str:
    value = str(getattr(source, "source_id", "") or "").strip()
    if not value:
        raise ValueError("every Skill or Tool source must expose source_id")
    return value


def _unique_source_ids(sources: Sequence[Any], kind: str) -> tuple[str, ...]:
    ids = tuple(_source_id(source) for source in sources)
    if len(set(ids)) != len(ids):
        raise ValueError(f"{kind} source ids must be unique")
    return ids


@dataclass(frozen=True)
class AgentDefinition:
    """Business-neutral metadata and extension sources for the single Agent."""

    agent_id: str
    version: str = "1.0.0"
    display_name: str = ""
    description: str = ""
    system_prompt: str = ""
    skill_sources: tuple[SkillSource, ...] = ()
    tool_sources: tuple[ToolSource, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        agent_id = str(self.agent_id or "").strip()
        version = str(self.version or "").strip()
        if not agent_id:
            raise ValueError("agent_id is required")
        if not version:
            raise ValueError("agent version is required")
        object.__setattr__(self, "agent_id", agent_id)
        object.__setattr__(self, "version", version)
        skills = tuple(self.skill_sources)
        tools = tuple(self.tool_sources)
        _unique_source_ids(skills, "Skill")
        _unique_source_ids(tools, "Tool")
        object.__setattr__(self, "skill_sources", skills)
        object.__setattr__(self, "tool_sources", tools)
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def source_ids(self) -> dict[str, tuple[str, ...]]:
        return {
            "skills": tuple(_source_id(source) for source in self.skill_sources),
            "tools": tuple(_source_id(source) for source in self.tool_sources),
        }

    def select_sources(
        self,
        *,
        skill_source_ids: Sequence[str] = (),
        tool_source_ids: Sequence[str] = (),
    ) -> tuple[tuple[SkillSource, ...], tuple[ToolSource, ...]]:
        """Return the sources selected by an application scenario."""
        skill_ids = tuple(str(item).strip() for item in skill_source_ids)
        tool_ids = tuple(str(item).strip() for item in tool_source_ids)
        skills = self._select(
            self.skill_sources, skill_ids, "Skill",
        )
        tools = self._select(
            self.tool_sources, tool_ids, "Tool",
        )
        return skills, tools

    @staticmethod
    def _select(
        sources: tuple[Any, ...], selected_ids: tuple[str, ...], kind: str,
    ) -> tuple[Any, ...]:
        if not selected_ids:
            return sources
        available = {_source_id(source): source for source in sources}
        unknown = [item for item in selected_ids if item not in available]
        if unknown:
            raise ValueError(
                f"unknown {kind} source(s): {', '.join(unknown)}"
            )
        if len(set(selected_ids)) != len(selected_ids):
            raise ValueError(f"{kind} source ids must be unique")
        return tuple(available[item] for item in selected_ids)


@dataclass(frozen=True)
class ScenarioDefinition:
    """A user-facing scenario composed from the single Agent."""

    scenario_id: str
    agent_id: str
    version: str = "1.0.0"
    display_name: str = ""
    description: str = ""
    skill_source_ids: tuple[str, ...] = ()
    tool_source_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        scenario_id = str(self.scenario_id or "").strip()
        agent_id = str(self.agent_id or "").strip()
        if not scenario_id:
            raise ValueError("scenario_id is required")
        if not agent_id:
            raise ValueError("scenario agent_id is required")
        object.__setattr__(self, "scenario_id", scenario_id)
        object.__setattr__(self, "agent_id", agent_id)
        object.__setattr__(
            self,
            "skill_source_ids",
            tuple(str(item).strip() for item in self.skill_source_ids),
        )
        object.__setattr__(
            self,
            "tool_source_ids",
            tuple(str(item).strip() for item in self.tool_source_ids),
        )
        object.__setattr__(self, "metadata", dict(self.metadata or {}))


__all__ = ["AgentDefinition", "ScenarioDefinition"]
