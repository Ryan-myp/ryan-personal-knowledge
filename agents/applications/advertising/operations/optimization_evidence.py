"""Read existing scoped audit records; never contact a Provider."""

from datetime import datetime, timezone
from agents.agent_harness.core.namespace import normalize_namespace

_MAX_EVIDENCE_CALLS = 100


def utc_time(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    # Legacy audit rows used server-local naive timestamps. astimezone applies
    # the local zone to those rows, preserving their actual chronology.
    return parsed.astimezone(timezone.utc)


def value_at(value, path):
    for key in str(path).split("."):
        if not isinstance(value, dict) or key not in value:
            raise ValueError("证据中不存在所指定字段")
        value = value[key]
    return value


def same_value(actual, expected):
    if isinstance(actual, bool) != isinstance(expected, bool):
        return False
    return actual == expected


def load_evidence(store, registry, principal, reference, review, *, writing):
    session = store.get_session(
        reference["session_id"], user_id=principal.user_id, tenant_id=principal.tenant_id
    )
    if not session:
        raise ValueError("找不到当前身份拥有的执行证据")
    definition, _ = registry.get(reference["tool_name"])
    if definition is None:
        raise ValueError("工具未注册")
    same_namespace = normalize_namespace(definition.namespace) == review["namespace"]
    if bool(definition.is_write_tool) != writing or not same_namespace:
        raise ValueError("执行证据的操作类型或渠道不一致")
    if definition.resource_type != review["resource_type"] or not definition.resource_id_field:
        raise ValueError("执行证据的资源类型不匹配")
    records = store.list_tool_calls(
        reference["session_id"], turn_id=reference["turn_id"], limit=_MAX_EVIDENCE_CALLS + 1
    )
    if len(records) > _MAX_EVIDENCE_CALLS:
        raise ValueError("该轮执行记录超过复盘证据检查上限，不能确认唯一证据")
    matches = [row for row in records if row.tool_name == reference["tool_name"]
               and _matches_target(row.input_data, definition, review)]
    if len(matches) != 1:
        raise ValueError("目标证据缺失或同轮有多个同目标调用，请提供无歧义的执行记录")
    record = matches[0]
    if not record.success:
        raise ValueError("该次执行失败")
    _validate_live_result(record.output_data, writing=writing)
    return record, definition


def _matches_target(data, definition, review):
    try:
        resource_id = value_at(data, definition.resource_id_field)
    except ValueError:
        return False  # A call without an explicit target cannot establish evidence.
    return str(resource_id) == review["resource_id"] and any(
        str(data.get(field, "")) == review["account_id"] for field in definition.scope_fields
    )


def _validate_live_result(output, *, writing):
    output = output if isinstance(output, dict) else {}
    if writing and (
        output.get("execution_mode") != "live" or output.get("execution_status") != "executed"
    ):
        raise ValueError("缺少真实 live 执行成功的证据")
    if (
        output.get("simulated")
        or output.get("execution_mode") == "dry_run"
        or output.get("data_status") in {"simulated", "dry_run", "offline"}
    ):
        raise ValueError("模拟结果不能作为真实执行或回读证据")
    if not writing and output.get("data_status") != "live":
        raise ValueError("缺少真实 live 回读数据来源，不能确认预期变更")
