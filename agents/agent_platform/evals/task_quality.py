"""Declarative, bounded intermediate-turn checks for task-level evaluation."""

from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .regression import RegressionAssertions, evaluate_regression


class TurnCheckpoint(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    turn: int = Field(ge=1, le=50)
    assertions: RegressionAssertions

    @model_validator(mode="after")
    def require_checks(self):
        if not self.assertions.executable:
            raise ValueError("turn checkpoint requires executable assertions")
        return self


def evaluate_task(
    response: Mapping[str, Any], *, turns: int,
    checkpoints: list[TurnCheckpoint], forbidden_tools: list[str],
) -> dict[str, Any]:
    rows = response.get("turn_evidence")
    if not isinstance(rows, list) or len(rows) != turns or not 1 <= turns <= 50:
        raise ValueError("task evaluation requires complete bounded turn evidence")
    checkpoints_by_turn = {item.turn: item.assertions for item in checkpoints}
    failures, checks = [], 0
    for index, row in enumerate(rows, 1):
        if not isinstance(row, Mapping):
            raise ValueError("turn evidence must be an object")
        assertions = checkpoints_by_turn.get(index, RegressionAssertions())
        assertions = assertions.model_copy(update={"forbidden_tools": list(dict.fromkeys([
            *assertions.forbidden_tools, *forbidden_tools,
        ]))})
        result = evaluate_regression(row, assertions)
        checks += result["checks"]
        failures.extend(f"turn:{index}:{label}" for label in result["failures"])
    return {"checks": checks, "failures": failures, "turns": len(rows)}
