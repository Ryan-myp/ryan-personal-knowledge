"""Cross-cutting governance defaults for platform products."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GovernancePolicy:
    """Runtime limits and defaults shared by all platform surfaces."""

    require_version: bool = True
    require_audit: bool = True
    default_execution_mode: str = "dry_run"
    max_context_chars: int = 12_000
    max_tools: int = 128
    max_turns: int = 12
    model_max_retries: int = 0
    model_retry_delay_seconds: float = 0.0
    model_timeout_seconds: float | None = None
    tool_timeout_seconds: float | None = 60.0
    tool_max_retries: int = 1
    tool_retry_delay_seconds: float = 0.2
    tool_circuit_failure_threshold: int = 5
    tool_circuit_reset_seconds: float = 30.0
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    max_total_tokens: int | None = None

    def __post_init__(self) -> None:
        if self.default_execution_mode not in {"dry_run", "live"}:
            raise ValueError("default_execution_mode must be dry_run or live")
        if self.max_context_chars <= 0:
            raise ValueError("max_context_chars must be positive")
        if self.max_tools <= 0:
            raise ValueError("max_tools must be positive")
        if self.max_turns <= 0:
            raise ValueError("max_turns must be positive")
        if self.model_max_retries < 0:
            raise ValueError("model_max_retries must be non-negative")
        if self.model_retry_delay_seconds < 0:
            raise ValueError("model_retry_delay_seconds must be non-negative")
        if self.model_timeout_seconds is not None and self.model_timeout_seconds <= 0:
            raise ValueError("model_timeout_seconds must be positive")
        if self.tool_timeout_seconds is not None and self.tool_timeout_seconds <= 0:
            raise ValueError("tool_timeout_seconds must be positive")
        if self.tool_max_retries < 0:
            raise ValueError("tool_max_retries must be non-negative")
        if self.tool_retry_delay_seconds < 0:
            raise ValueError("tool_retry_delay_seconds must be non-negative")
        if self.tool_circuit_failure_threshold <= 0:
            raise ValueError("tool_circuit_failure_threshold must be positive")
        if self.tool_circuit_reset_seconds <= 0:
            raise ValueError("tool_circuit_reset_seconds must be positive")
        for name, value in (
            ("max_input_tokens", self.max_input_tokens),
            ("max_output_tokens", self.max_output_tokens),
            ("max_total_tokens", self.max_total_tokens),
        ):
            if value is not None and value <= 0:
                raise ValueError(f"{name} must be positive")


__all__ = ["GovernancePolicy"]
