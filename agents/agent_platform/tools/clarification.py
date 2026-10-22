"""A side-effect-free Tool for explicit, structured clarification."""

from agents.agent_harness import StaticToolSource, ToolBinding
from agents.agent_harness.core.interfaces import (
    ToolDefinition, ToolEffect, ToolResult, ToolSchema, RiskLevel, ReplayPolicy,
)


def clarification_tool_source(*, required_permission: str) -> StaticToolSource:
    if not required_permission.strip():
        raise ValueError("clarification requires an explicit permission")
    definition = ToolDefinition(
        name="agent_request_input", namespace="agent_platform", skill="clarification",
        description=(
            "Ask the user for missing information and pause the Run. Use when the "
            "target namespace, account, objective, or another required choice is "
            "ambiguous. Do not choose the first authorized account or namespace "
            "as a default. The question and choices must come from the actual "
            "request and registered context. This Tool performs no external operation."
        ),
        input_schema=ToolSchema(
            properties={
                "question": {"type": "string", "minLength": 1, "maxLength": 1000},
                "choices": {
                    "type": "array", "maxItems": 12,
                    "items": {"type": "string", "minLength": 1, "maxLength": 160},
                },
            },
            required=["question"], additional_properties=False,
        ),
        action="request", resource_type="clarification", intent_types=["request_input"],
        risk_level=RiskLevel.LOW, effect_class=ToolEffect.READ,
        replay_policy=ReplayPolicy.SAFE, required_permissions=[required_permission],
        traits=["clarification", "interaction", "bounded_output"], scope_required=False,
        timeout_seconds=5, max_output_bytes=8000, contract_version="1.0.0",
    )

    def execute(_context, arguments):
        question = arguments["question"]
        choices = list(arguments.get("choices") or [])
        return ToolResult(
            success=True, needs_input=True,
            data={"message": question, "choices": choices, "status": "awaiting_input"},
            interaction={
                "type": "action_clarification", "prompt": question,
                "payload": {
                    "question": question,
                    "options": [{"label": value, "value": value} for value in choices],
                },
            },
        )

    return StaticToolSource(
        "agent-platform:clarification", [ToolBinding(definition, execute)],
    )
