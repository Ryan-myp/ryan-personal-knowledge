"""Deployment-owned evaluator bindings, never loaded from Skill packages."""

from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Mapping
from typing import Any
import sys
import json


@dataclass(frozen=True)
class ManagedEvaluationEngine:
    adapter_path: Path
    allowed_kwargs: tuple[str, ...] = ()
    environment: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        adapter = Path(self.adapter_path).resolve()
        if not adapter.is_file() or adapter.suffix != ".py":
            raise ValueError(
                "managed evaluation adapter must be a deployed Python file"
            )
        object.__setattr__(self, "adapter_path", adapter)
        object.__setattr__(self, "allowed_kwargs", tuple(self.allowed_kwargs))
        object.__setattr__(
            self, "environment", MappingProxyType(dict(self.environment))
        )


def builtin_evaluation_engines() -> dict[str, ManagedEvaluationEngine]:
    return {
        "claude_sdk": ManagedEvaluationEngine(
            adapter_path=Path(__file__).resolve().parents[1]
            / "evals/claude_sdk_engine.py",
            allowed_kwargs=(
                "max_tokens",
                "file_paths",
                "max_skill_context_chars",
                "max_tool_context_chars",
                "max_file_context_chars",
            ),
        ),
    }


def skill_up_config(
    config: Mapping[str, Any],
    engine: ManagedEvaluationEngine,
    timeout: int,
) -> dict[str, Any]:
    """Generate a fixed deployed command after validating the Skill's data."""
    original = config.get("engine") or {}
    generated = dict(config)
    custom = {
        "transport": "local",
        "response_format": "session_result",
        "timeout_seconds": timeout,
        "local": {
            "command": sys.executable,
            "args": [
                str(engine.adapter_path),
                "--input",
                "${input_file}",
                "--output",
                "${output_file}",
            ],
            "cwd": "${workspace}",
            "input_file": "inputs/agent-session.json",
            "output_file": "outputs/agent-session-result.json",
        },
    }
    if original.get("kwargs"):
        custom["kwargs"] = {
            str(key): json.dumps(value)
            if isinstance(value, (list, dict))
            else str(value)
            for key, value in original["kwargs"].items()
        }
    generated["engine"] = {"name": original["name"], "custom": custom}
    if "model" in original:
        generated["engine"]["model"] = original["model"]
    return generated
