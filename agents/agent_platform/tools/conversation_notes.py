"""Registered, source-checked conversation memory; never an authorization source."""

from agents.agent_harness import StaticToolSource, ToolBinding
from agents.agent_harness.core.interfaces import (
    ToolDefinition,
    ToolSchema,
    ToolEffect,
    ReplayPolicy,
    RiskLevel,
)


def _note_fields():
    return {
        "expected_revision": {"type": "integer", "minimum": 0},
        "changes": {
            "type": "array",
            "minItems": 1,
            "maxItems": 8,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["operation", "subject", "quote"],
                "properties": {
                    "operation": {"type": "string", "enum": ["add", "replace", "retract"]},
                    "subject": {"type": "string", "minLength": 1, "maxLength": 120},
                    "quote": {"type": "string", "minLength": 1, "maxLength": 240},
                    "replaces": {
                        "type": "array",
                        "maxItems": 16,
                        "uniqueItems": True,
                        "items": {"type": "string", "pattern": "^[a-f0-9]{20}$"},
                    },
                },
            },
        },
    }


def conversation_notes_source(read_notes, update_notes):
    fields = _note_fields()
    bindings = []
    for action, executor in (("get", read_notes), ("update", update_notes)):
        writing = action == "update"
        definition = ToolDefinition(
            name=f"agent_{action}_conversation_notes",
            namespace="agent_platform",
            skill="conversation-continuity",
            skill_refs=["conversation-continuity"],
            description=(
                "读取当前会话的用户约束、来源 ID 和版本。"
                if not writing
                else "用户明确增加、修改或撤销要求时维护会话约束。理解语义相同的要求后引用旧 ID 替换，"
                "不要追加相互冲突的约束；quote 必须逐字引用当前用户消息。仅记忆，不代表授权或已执行。"
            ),
            input_schema=ToolSchema(
                properties=fields if writing else {},
                required=list(fields) if writing else [],
                additional_properties=False,
            ),
            action=action,
            resource_type="conversation_notes",
            intent_types=[f"conversation_notes_{action}"],
            required_permissions=["ads.plan" if writing else "ads.read"],
            scope_required=False,
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.INTERNAL_WRITE if writing else ToolEffect.READ,
            replay_policy=ReplayPolicy.UNSAFE,
            timeout_seconds=5,
            max_output_bytes=12000,
            traits=["local", "advisory_memory", "bounded_output"],
            contract_version="1.0.0",
            live_support=False,
        )
        bindings.append(ToolBinding(definition, executor))
    return StaticToolSource("agent-platform:conversation-notes", bindings)
