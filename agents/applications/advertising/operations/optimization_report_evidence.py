"""Resolve direct report metrics from owned audit evidence, never from an API."""

import math
import re

from agents.agent_harness.core.namespace import normalize_namespace
from .optimization_evidence import _validate_live_result, utc_time, value_at
from .optimization_measurements import validate_measurement
from agents.tools.advertising.shared.domain.account_scope import tool_account_fields


def measurement_provenance(store, registry, principal, review, measurement, reference):
    if reference is None:
        return {"status": "user_supplied", "unverified_context_fields": [
            "value", "currency", "timezone", "attribution_days", "unit",
        ]}
    record = _report_record(store, registry, principal, review, reference)
    output = record.output_data
    report, context = output.get("report"), output.get("report_context")
    if isinstance(report, dict):
        report = report.get("list")
    index = reference.get("row_index", 0)
    if (not isinstance(report, list) or not 1 <= len(report) <= 1000
            or type(index) is not int or not 0 <= index < len(report)):
        raise ValueError("报表行不存在或超过核验上限")
    row = report[index]
    if not isinstance(row, dict) or not _same_resource(row, review):
        raise ValueError("报表行的目标资源与优化建议不一致")
    if sum(isinstance(item, dict) and _same_resource(item, review) for item in report) != 1:
        raise ValueError("该资源存在多行分段数据，不能以其中一行代替完整窗口指标")
    metric = measurement["metric"]
    if not re.fullmatch(r"[A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*){0,3}", metric):
        raise ValueError("审计指标使用报表实际字段路径，不接受自由公式或指标别名")
    number = value_at(row, metric)
    if isinstance(number, bool) or not isinstance(number, (str, int, float)):
        raise ValueError("报表指标不是数值")
    try:
        number = float(number)
    except (ValueError, OverflowError) as error:
        raise ValueError("报表指标不能转换为有限数值") from error
    if not math.isfinite(number) or number != measurement["value"]:
        raise ValueError("指标值与报表审计不一致")
    unverified = _verify_context(context, review, measurement)
    validate_measurement(measurement, utc_time(record.ended_at).date())
    return {"status": "audited_value_declared_context" if unverified else "audited_report",
            "record_id": record.id, "reference": dict(reference),
            "captured_at": record.ended_at, "metric_path": metric,
            "unverified_context_fields": unverified}


def _same_resource(row, review):
    kind = review["resource_type"]
    nested = row.get(kind)
    identifier = row.get(f"{kind}_id")
    if identifier is None and isinstance(nested, dict):
        identifier = nested.get("id")
    dimensions = row.get("dimensions")
    if identifier is None and isinstance(dimensions, dict):
        identifier = dimensions.get(f"{kind}_id")
    return identifier is not None and str(identifier) == review["resource_id"]


def _report_record(store, registry, principal, review, reference):
    session = store.get_session(reference["session_id"], user_id=principal.user_id,
                                tenant_id=principal.tenant_id)
    if session is None:
        raise ValueError("报表证据不属于当前身份")
    definition, _ = registry.get(reference["tool_name"])
    if (definition is None or definition.is_write_tool or definition.action != "report"
            or normalize_namespace(definition.namespace) != review["namespace"]):
        raise ValueError("需要同渠道已注册的只读报表 Tool 证据")
    rows = store.list_tool_calls(reference["session_id"], turn_id=reference["turn_id"], limit=101)
    if len(rows) > 100:
        raise ValueError("报表审计记录超过核验上限")
    matches = [row for row in rows if row.tool_name == reference["tool_name"] and any(
        str(row.input_data.get(field, "")) == review["account_id"]
        for field in tool_account_fields(definition)
    )]
    if len(matches) != 1 or not matches[0].success:
        raise ValueError("缺少唯一成功且账户匹配的报表证据")
    _validate_live_result(matches[0].output_data, writing=False)
    return matches[0]


def _verify_context(context, review, measurement):
    if not isinstance(context, dict) or context.get("resource_level") != review["resource_type"]:
        raise ValueError("报表缺少一致的资源层级")
    completeness = context.get("completeness") or {}
    if (not isinstance(completeness, dict) or completeness.get("may_be_truncated") is not False
            or completeness.get("status") != "within_limit"):
        raise ValueError("报表完整性尚未确认，不能用分页片段复盘")
    period_context = context.get("period")
    period = period_context.get("value") if isinstance(period_context, dict) else None
    if not isinstance(period, dict):
        raise ValueError("报表必须使用明确日期范围，不能猜测相对日期")
    start = period.get("start_date", period.get("since", period.get("start")))
    end = period.get("end_date", period.get("until", period.get("end")))
    if start != measurement["start_date"] or end != measurement["end_date"]:
        raise ValueError("报表日期与指标观察窗口不一致")
    unverified = ["unit"]  # Provider field units are not yet normalized by the report contract.
    for field, key in (("currency", "account_currency"), ("timezone", "account_timezone"),
                       ("attribution_days", "attribution")):
        fact = context.get(key) or {}
        if not isinstance(fact, dict):
            raise ValueError("报表口径证据格式不完整")
        value = fact.get("value")
        if value is None or fact.get("status") in {"unknown", "not_returned_by_tool"}:
            unverified.append(field)
        elif type(value) is not type(measurement[field]) or value != measurement[field]:
            raise ValueError(f"报表口径与指标声明不一致：{field}")
    return unverified
