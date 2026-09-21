"""Advertising Agent product definition for the generic platform catalog."""

from __future__ import annotations

from typing import Any, Sequence

from agents.agent_harness import ToolSource
from agents.agent_platform import AgentDefinition

from .integration import advertising_skill_source


def advertising_agent_definition(
    *,
    tool_sources: Sequence[ToolSource] = (),
    skill_source_id: str = "ad-skills",
) -> AgentDefinition:
    """Describe advertising as a product without creating a second Runtime.

    The returned definition can be registered in ``AgentPlatform`` and its
    standard Skill/Tool sources can be selected by any compatible scenario.
    """
    return AgentDefinition(
        agent_id="default-agent",
        version="1.0.0",
        display_name="General Agent",
        description="One general Agent configured for the advertising scenario.",
        system_prompt=(
            "Use the registered advertising Skills and Tools. "
            "Respect each Tool contract and execution policy."
        ),
        skill_sources=(advertising_skill_source(source_id=skill_source_id),),
        tool_sources=tuple(tool_sources),
        metadata={"scenario_domain": "advertising"},
    )


__all__ = ["advertising_agent_definition"]
