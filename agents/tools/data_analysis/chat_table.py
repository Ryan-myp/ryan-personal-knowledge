"""Identity-scoped, read-only aggregation of user-uploaded chat tables."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any, Callable

from agents.agent_harness import StaticToolSource, ToolBinding
from agents.agent_harness.core.interfaces import (
    ReplayPolicy,
    RiskLevel,
    ToolDefinition,
    ToolEffect,
    ToolResult,
    ToolSchema,
)
from agents.agent_harness.core.security import redact_sensitive_text
from agents.agent_harness.redaction import is_sensitive_key


MAX_GROUPS = 1_000
MAX_GROUPS_PER_PAGE = 100
MAX_OUTPUT_BYTES = 32_000


def _trusted_scope(context: Any) -> dict[str, str]:
    request = getattr(context, "request", None)
    principal = getattr(request, "principal", None)
    scope = {
        "tenant_id": str(getattr(principal, "tenant_id", "") or "").strip(),
        "user_id": str(getattr(principal, "user_id", "") or "").strip(),
        "session_id": str(getattr(request, "session_id", "") or "").strip(),
    }
    if not all(scope.values()):
        raise PermissionError("缺少可信的会话和身份")
    return scope


def _options(arguments: dict[str, Any]) -> tuple[str, dict[str, str], int, int]:
    operation = arguments.get("operation")
    if operation not in {"inspect", "aggregate"}:
        raise ValueError("operation 只能是 inspect 或 aggregate")
    attachment_id = arguments.get("attachment_id")
    if not isinstance(attachment_id, str) or not attachment_id:
        raise ValueError("attachment_id 必须是当前会话附件 ID")
    for name in ("sheet_name", "group_by", "value_column", "id_column"):
        if name in arguments and (
            not isinstance(arguments[name], str) or len(arguments[name]) > 200
        ):
            raise ValueError(f"{name} 必须是长度不超过 200 的文本")
    selected = {
        name: arguments[name]
        for name in ("group_by", "value_column", "id_column")
        if arguments.get(name)
    }
    if operation == "aggregate" and "group_by" not in selected:
        raise ValueError("聚合需要 group_by")
    offset, limit = arguments.get("group_offset", 0), arguments.get("group_limit", 50)
    if (
        isinstance(offset, bool) or not isinstance(offset, int)
        or offset < 0 or offset > MAX_GROUPS
        or isinstance(limit, bool) or not isinstance(limit, int)
        or limit < 1 or limit > MAX_GROUPS_PER_PAGE
    ):
        raise ValueError("分组分页参数超出允许范围")
    return operation, selected, offset, limit


@dataclass
class _TableStats:
    row_count: int = 0
    missing_groups: int = 0
    missing_values: int = 0
    invalid_values: int = 0
    duplicate_ids: int = 0
    counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    sums: dict[str, Decimal] = field(default_factory=lambda: defaultdict(Decimal))
    numeric_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    ids: set[str] = field(default_factory=set)

    def add(self, row: list[str], indexes: dict[str, int], selected: dict[str, str]) -> None:
        if not any(row):
            return
        self.row_count += 1
        if not selected:
            return
        group = row[indexes[selected["group_by"]]].strip()
        if len(group) > 500:
            raise ValueError("分组值过长，无法提供有界统计")
        if not group:
            self.missing_groups += 1
        if group not in self.counts and len(self.counts) >= MAX_GROUPS:
            raise ValueError("分组超过 1000 个上限，无法提供完整汇总")
        self.counts[group] += 1
        if "id_column" in selected:
            row_id = row[indexes[selected["id_column"]]].strip()
            if len(row_id) > 500:
                raise ValueError("ID 值过长，无法核对重复项")
            if row_id:
                self.duplicate_ids += int(row_id in self.ids)
                self.ids.add(row_id)
        if "value_column" not in selected:
            return
        raw_value = row[indexes[selected["value_column"]]].strip()
        if not raw_value:
            self.missing_values += 1
            return
        if len(raw_value) > 64:
            self.invalid_values += 1
            return
        try:
            value = Decimal(raw_value)
        except InvalidOperation:
            self.invalid_values += 1
            return
        if (
            not value.is_finite()
            or value > Decimal("1e18")
            or value < Decimal("-1e18")
            or value.as_tuple().exponent < -12
        ):
            self.invalid_values += 1
            return
        with localcontext() as context:
            context.prec = 80
            self.sums[group] += value
        self.numeric_counts[group] += 1

    def summary(
        self, selected: dict[str, str], offset: int, limit: int,
    ) -> dict[str, Any]:
        has_value = "value_column" in selected
        ordered = sorted(
            self.counts,
            key=lambda group: (
                -(self.sums[group] if has_value else self.counts[group]), group,
            ),
        )
        result = {
            **selected,
            "missing_group_count": self.missing_groups,
            "duplicate_id_count": self.duplicate_ids,
            "group_count": len(self.counts),
            "group_offset": offset,
            "has_more_groups": offset + limit < len(ordered),
            "groups": [
                {
                    "group": redact_sensitive_text(group) if group else None,
                    "row_count": self.counts[group],
                    **({
                        "numeric_count": self.numeric_counts[group],
                        "value_sum": str(self.sums[group]),
                    } if has_value else {}),
                }
                for group in ordered[offset:offset + limit]
            ],
        }
        if has_value:
            with localcontext() as context:
                context.prec = 80
                total = sum(self.sums.values(), Decimal(0))
            result.update({
                "missing_value_count": self.missing_values,
                "invalid_value_count": self.invalid_values,
                "value_complete": (
                    self.invalid_values == 0 and self.missing_values == 0
                ),
                "total_value_sum": str(total),
            })
        return result


class _ChatTableExecutor:
    def __init__(self, store: Any, open_table: Callable[..., Any]) -> None:
        self._store = store
        self._open_table = open_table

    def execute(self, context: Any, arguments: dict[str, Any]) -> ToolResult:
        try:
            return ToolResult.ok(self._execute(context, arguments))
        except (FileNotFoundError, PermissionError, ValueError) as error:
            return ToolResult.error(f"附件表格分析失败：{error}")

    def _execute(self, context: Any, arguments: dict[str, Any]) -> dict[str, Any]:
        scope = _trusted_scope(context)
        operation, selected, offset, limit = _options(arguments)
        attachment_id = arguments["attachment_id"]
        attachment = self._store.load(
            attachment_id, **scope,
        )
        metadata = attachment.metadata
        with self._open_table(
            attachment.content,
            filename=metadata["filename"],
            media_type=metadata["media_type"],
            sheet_name=arguments.get("sheet_name") or None,
        ) as (headers, rows, sheet_name):
            if any(is_sensitive_key(header) for header in headers):
                raise ValueError("表格含凭证类字段，不能送入模型分析")
            indexes = {name: index for index, name in enumerate(headers)}
            if operation == "aggregate":
                for field, name in selected.items():
                    if name not in indexes:
                        raise ValueError(f"{field} 不在表格列名中")
            stats = _TableStats()
            for row in rows:
                stats.add(row, indexes, selected if operation == "aggregate" else {})
            result: dict[str, Any] = {
                "attachment_id": attachment_id,
                "filename": redact_sensitive_text(metadata["filename"]),
                "sheet_name": redact_sensitive_text(sheet_name),
                "columns": headers,
                "row_count": stats.row_count,
                "complete": True,
                "source": "scoped_uploaded_attachment",
            }
            if operation == "aggregate":
                result.update(stats.summary(selected, offset, limit))
        if len(json.dumps(result, ensure_ascii=False).encode("utf-8")) > MAX_OUTPUT_BYTES:
            raise ValueError("结果超过 32 KB 上限，无法提供完整统计")
        return result


def _table_schema() -> ToolSchema:
    return ToolSchema(
        properties={
            "attachment_id": {"type": "string", "minLength": 1, "maxLength": 100},
            "operation": {"type": "string", "enum": ["inspect", "aggregate"]},
            "sheet_name": {"type": "string", "maxLength": 200},
            "group_by": {"type": "string", "maxLength": 200},
            "value_column": {"type": "string", "maxLength": 200},
            "id_column": {"type": "string", "maxLength": 200},
            "group_offset": {"type": "integer", "minimum": 0, "maximum": MAX_GROUPS},
            "group_limit": {
                "type": "integer", "minimum": 1,
                "maximum": MAX_GROUPS_PER_PAGE,
            },
        },
        required=["attachment_id", "operation"],
        additional_properties=False,
    )


def _table_definition(required_permission: str) -> ToolDefinition:
    return ToolDefinition(
        name="agent_chat_table_analyze",
        skill="data-visualization",
        namespace="data_analysis",
        description=(
            "对当前会话上传的 CSV/XLSX 附件进行全表只读分析。先用 inspect 查看工作表、"
            "列名和完整行数，再用 aggregate 按 group_by 分组计数；"
            "指定 value_column 时额外求和，不指定时只计数。使用聊天附件的 ID，"
            "不要传文件路径或让用户重贴文件；聚合结果报告空值、非数值和重复 ID。"
            "Story Points 不是工时，只有明确的小时/人天列才能报告工时。"
            "附件文本预览可能截断，不可从预览推断全量统计。"
            "分组结果按数值总和排序并分页，has_more_groups 为 true 时"
            "只展示了部分分组，可通过 group_offset 翻页。"
        ),
        input_schema=_table_schema(),
        action="analyze",
        resource_type="chat_attachment_table",
        intent_types=["analyze_uploaded_table"],
        intent_aliases=[
            "分析上传的表格", "按人汇总工时", "按人汇总", "工时", "表格",
            "统计附件的数据",
            "汇总 Excel 数据", "分析 CSV", "analyze uploaded spreadsheet",
        ],
        risk_level=RiskLevel.LOW,
        effect_class=ToolEffect.READ,
        replay_policy=ReplayPolicy.SAFE,
        traits=[
            "read_only", "identity_scoped", "bounded_input", "bounded_output",
            "accepts_media:text/csv",
            "accepts_media:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ],
        timeout_seconds=500,
        max_output_bytes=MAX_OUTPUT_BYTES,
        required_permissions=[required_permission],
        scope_required=False,
        contract_version="1.0.0",
    )


def chat_table_tool_source(
    store: Any,
    open_table: Callable[..., Any],
    *,
    required_permission: str,
) -> StaticToolSource:
    """Publish a fixed, scoped table Tool with no paths or executable input."""
    if not required_permission:
        raise ValueError("required_permission is required")
    return StaticToolSource(
        "data-analysis:chat-table",
        [ToolBinding(
            _table_definition(required_permission),
            _ChatTableExecutor(store, open_table),
        )],
    )
