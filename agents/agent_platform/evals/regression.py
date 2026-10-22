"""Closed, non-executable assertions for conversation regression evidence."""

from typing import Annotated, Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, StrictBool


_Text = Annotated[str, Field(min_length=1, max_length=200)]
_ToolName = Annotated[str, Field(min_length=1, max_length=200, pattern=r"^[\w.:-]+$")]


class RegressionAssertions(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    required_tools: list[_ToolName] = Field(default_factory=list, max_length=64)
    forbidden_tools: list[_ToolName] = Field(default_factory=list, max_length=64)
    reply_contains: list[_Text] = Field(default_factory=list, max_length=32)
    reply_not_contains: list[_Text] = Field(default_factory=list, max_length=32)
    reply_nonempty: StrictBool | None = None
    max_tool_calls: int | None = Field(default=None, ge=0, le=64)
    intent_type: _Text | None = None
    needs_input: StrictBool | None = None
    needs_confirmation: StrictBool | None = None

    @property
    def executable(self) -> bool:
        return any(
            value is not None and value != []
            for value in self.model_dump().values()
        )


def evaluate_regression(
    response: Mapping[str, Any], assertions: RegressionAssertions,
) -> dict[str, Any]:
    if not assertions.executable:
        return {"status": "ungraded", "failures": [], "checks": 0}
    if not isinstance(response, Mapping):
        raise ValueError("regression response must be an object")
    rows = response.get("results", [])
    if not isinstance(rows, list) or len(rows) > 64:
        raise ValueError("regression response calls must be a bounded list")
    if any(not isinstance(row, Mapping) for row in rows):
        raise ValueError("regression response call must be an object")
    tools = [str(row.get("tool") or "") for row in rows]
    successful = {str(row.get("tool") or "") for row in rows if row.get("success") is True}
    checks: list[bool] = []
    labels: list[str] = []

    def check(condition: bool, label: str) -> None:
        checks.append(condition)
        labels.append(label)

    for name in assertions.required_tools:
        check(name in successful, f"required_tool:{name}")
    for name in assertions.forbidden_tools:
        check(name not in tools, f"forbidden_tool:{name}")
    reply = response.get("reply", "")
    if not isinstance(reply, str):
        raise ValueError("regression reply must be text")
    reply = reply.casefold()
    if assertions.reply_nonempty is not None:
        check(bool(reply.strip()) == assertions.reply_nonempty, "reply_nonempty")
    for index, term in enumerate(assertions.reply_contains):
        check(term.casefold() in reply, f"reply_contains:{index}")
    for index, term in enumerate(assertions.reply_not_contains):
        check(term.casefold() not in reply, f"reply_not_contains:{index}")
    if assertions.max_tool_calls is not None:
        check(len(rows) <= assertions.max_tool_calls, "max_tool_calls")
    if assertions.intent_type is not None:
        intent = response.get("intent") or {}
        if not isinstance(intent, Mapping):
            raise ValueError("regression intent must be an object")
        check(intent.get("intent_type") == assertions.intent_type, "intent_type")
    for name in ("needs_input", "needs_confirmation"):
        expected = getattr(assertions, name)
        if expected is not None:
            check(bool(response.get(name)) == expected, name)
    failures = [label for passed, label in zip(checks, labels) if not passed]
    return {
        "status": "failed" if failures else "passed",
        "failures": failures, "checks": len(checks),
    }
