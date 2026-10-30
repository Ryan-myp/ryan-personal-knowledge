"""Safe draft diagnostics backed by the same validator used for Tool execution."""

import re
from typing import Any, Mapping

from agents.agent_harness.core.interfaces import ToolSchema
from agents.agent_harness.core.tool_registry import validate_tool_input


_MESSAGES = (
    (r"^Missing required field:", "对象内的必填子字段尚未填写。"),
    (r"^Field '[^']+' expected ", "字段或子字段的类型不正确。"),
    (r"^Field '[^']+' must be one of ", "字段或子字段包含不支持的选项。"),
    (r"^Field '[^']+' is not allowed$", "对象包含未声明的子字段。"),
    (r"^Field '[^']+' must contain unique items$", "列表不能包含重复项。"),
    (r"^Field '[^']+' must be a finite number$", "必须填写有效的有限数字。"),
    (r"^Field '[^']+' .*validation pattern$|^Field '[^']+' does not match the required format$",
     "字段或子字段的格式不符合要求。"),
)
_LIMIT_MESSAGES = (
    (r" must contain at least (\d+) items/characters$", "字段或子字段至少需要 {} 项/字符。"),
    (r" must contain at most (\d+) items/characters$", "字段或子字段最多允许 {} 项/字符。"),
    (r" must be >= ([0-9.eE+-]+)$", "字段或子字段不能小于 {}。"),
    (r" must be <= ([0-9.eE+-]+)$", "字段或子字段不能大于 {}。"),
)


def _safe_message(error: str) -> str:
    # Validator errors can contain supplied values and unknown keys. Never
    # forward those strings; only expose a fixed category or numeric limit.
    for pattern, message in _MESSAGES:
        if re.search(pattern, error):
            return message
    for pattern, message in _LIMIT_MESSAGES:
        match = re.search(pattern, error)
        if match:
            return message.format(match.group(1))
    return "参数未通过 Tool Schema 校验，请检查字段及子字段约束。"


def blueprint_field_errors(schema: Mapping[str, Any] | None, value: Any) -> list[str]:
    if not schema:
        return ["字段合同暂不可用，请刷新后重试。"]
    errors = validate_tool_input(ToolSchema(properties={"value": dict(schema)}), {"value": value})
    return list(dict.fromkeys(_safe_message(error) for error in errors))[:4]
