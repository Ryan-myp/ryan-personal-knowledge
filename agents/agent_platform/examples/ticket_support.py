"""Reference non-advertising application assembled from Skills and Tools."""

from __future__ import annotations

from typing import Any, Optional

from agents.agent_harness import (
    SkillBinding,
    StaticSkillSource,
    StaticToolSource,
    ToolBinding,
)

from ..platform import AgentPlatform
from ..definitions import AgentDefinition, ScenarioDefinition
from ..runtime import PlatformApplication, PlatformDependencies


def _lookup_ticket(_context: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    ticket_id = str(arguments.get("ticket_id") or "").strip()
    return {
        "ticket_id": ticket_id,
        "status": "open",
        "source": "reference_support_system",
    }


def create_ticket_support_application(
    *,
    model: Any,
    dependencies: Optional[PlatformDependencies] = None,
) -> PlatformApplication:
    """Create a ticket-support Agent without importing the advertising package."""
    skills = StaticSkillSource(
        "support:skills",
        [
            SkillBinding(
                name="ticket-support",
                instructions=(
                    "Help users find ticket status. Ask for a ticket ID "
                    "before calling the lookup Tool."
                ),
            ),
        ],
    )
    tools = StaticToolSource(
        "support:tools",
        [
            ToolBinding(
                {
                    "name": "lookup_ticket",
                    "description": "Look up one support ticket.",
                    "input_schema": {
                        "type": "object",
                        "required": ["ticket_id"],
                        "properties": {
                            "ticket_id": {"type": "string"},
                        },
                    },
                },
                _lookup_ticket,
            ),
        ],
    )
    platform = AgentPlatform()
    platform.register_agent(AgentDefinition(
        agent_id="default-agent",
        display_name="General Support Agent",
        system_prompt="Resolve support questions with the registered Tools.",
        skill_sources=(skills,),
        tool_sources=(tools,),
    ))
    platform.register_scenario(ScenarioDefinition(
        scenario_id="ticket-support",
        agent_id="default-agent",
        display_name="Ticket Support",
    ))
    return platform.create_application(
        "ticket-support",
        model=model,
        dependencies=dependencies,
    )


__all__ = ["create_ticket_support_application"]
