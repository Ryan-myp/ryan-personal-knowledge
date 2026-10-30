"""Local optimization-review Tools; external mutations still use channel Tools."""

from agents.agent_harness import StaticToolSource, ToolBinding
from agents.agent_harness.core.interfaces import (
    ToolDefinition,
    ToolSchema,
    ToolEffect,
    ReplayPolicy,
    RiskLevel,
)


def text_field(limit=200):
    return {"type": "string", "minLength": 1, "maxLength": limit}


def report_evidence_schema():
    return {"type": "object", "additionalProperties": False, "properties": {
        **{key: text_field() for key in ("session_id", "turn_id", "tool_name")},
        "row_index": {"type": "integer", "minimum": 0, "maximum": 999},
    }, "required": ["session_id", "turn_id", "tool_name", "row_index"]}


def measurement_schema():
    fields = {key: text_field() for key in ("metric", "unit", "currency", "timezone", "source")}
    fields.update(
        {
            "value": {"type": "number", "minimum": 0},
            "attribution_days": {"type": "integer", "minimum": 0, "maximum": 90},
            "start_date": {**text_field(10), "pattern": r"^\d{4}-\d{2}-\d{2}$"},
            "end_date": {**text_field(10), "pattern": r"^\d{4}-\d{2}-\d{2}$"},
        }
    )
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": fields,
        "required": list(fields),
    }


def _create_fields():
    scalar = {"type": ["string", "number", "boolean"], "maxLength": 500}
    create_fields = {
        key: text_field()
        for key in ("namespace", "account_id", "resource_type", "resource_id", "field")
    }
    create_fields.update(
        {
            "proposal": text_field(1000),
            "expected_value": scalar,
            "baseline": measurement_schema(),
            "baseline_evidence": report_evidence_schema(),
            "cooldown_days": {"type": "integer", "minimum": 1, "maximum": 90},
            "observation_days": {"type": "integer", "minimum": 7, "maximum": 90},
        }
    )
    return create_fields


def _update_fields():
    scalar = {"type": ["string", "number", "boolean"], "maxLength": 500}
    return {
        "review_id": text_field(64),
        "expected_version": {"type": "integer", "minimum": 1},
        "action": {
            "type": "string",
            "enum": ["link_execution", "verify_readback", "review", "reopen"],
        },
        "evidence": {
            "type": "object",
            "additionalProperties": False,
            "properties": {key: text_field() for key in ("session_id", "turn_id", "tool_name")},
            "required": ["session_id", "turn_id", "tool_name"],
        },
        "readback_path": text_field(),
        "outcome": measurement_schema(),
        "outcome_evidence": report_evidence_schema(),
        "proposal": text_field(1000),
        "expected_value": scalar,
    }


def _review_specs(service):
    create_fields = _create_fields()
    update_fields = _update_fields()
    return (
        (
            "create",
            service.create,
            create_fields,
            [key for key in create_fields if key != "baseline_evidence"],
            "登记广告优化建议与成熟基线，跨轮次去重；不会调整广告。可附 baseline_evidence 核验既有报表审计；"
            "metric 使用该报表实际字段路径，数值、资源和日期必须一致；未知币种、时区、归因口径保留缺口。",
        ),
        (
            "get",
            service.read,
            {
                "review_id": text_field(64),
                "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                "offset": {"type": "integer", "minimum": 0, "maximum": 10000},
            },
            [],
            "查询当前用户的广告优化复盘记录、状态、执行回读证据和效果；支持分页。",
        ),
        (
            "update",
            service.update,
            update_fields,
            ["review_id", "expected_version", "action"],
            "推进优化复盘：link_execution 验证既有 live 审计，verify_readback 核验预期字段，review 比较成熟同口径数据，"
            "reopen 在冷却结束后开启下一轮。执行和回读传 evidence，回读再传 readback_path，复盘传 outcome，"
            "新一轮传 outcome 作为基线以及 proposal/expected_value。可传 outcome_evidence 核验报表审计行，"
            "outcome.metric 使用报表实际字段路径。不能以模型声明替代证据；不调用渠道 API。",
        ),
    )


def optimization_review_source(service):
    bindings = []
    for action, executor, fields, required, description in _review_specs(service):
        writing = action != "get"
        definition = ToolDefinition(
            name=f"agent_{action}_optimization_review",
            namespace="agent_platform",
            skill="ad-growth-operations",
            description=description,
            action="record" if action == "create" else action,
            resource_type="optimization_review",
            intent_types=[f"optimization_review_{action}"],
            skill_refs=["ad-growth-operations"],
            input_schema=ToolSchema(
                properties=fields, required=required, additional_properties=False
            ),
            effect_class=ToolEffect.INTERNAL_WRITE if writing else ToolEffect.READ,
            risk_level=RiskLevel.LOW,
            replay_policy=ReplayPolicy.UNSAFE,
            required_permissions=["ads.plan" if writing else "ads.read"],
            scope_required=False,
            traits=["local", "durable", "scoped_local_state", "bounded_output"],
            live_support=False,
            timeout_seconds=10,
            max_output_bytes=64000,
            contract_version="1.1.0" if writing else "1.0.0",
        )
        bindings.append(ToolBinding(definition, executor))
    return StaticToolSource("advertising:optimization-reviews", bindings)
