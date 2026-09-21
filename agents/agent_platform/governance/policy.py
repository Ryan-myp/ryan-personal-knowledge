"""Cross-cutting governance defaults for platform products."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GovernancePolicy:
    """Policy metadata shared by catalog, deployment and runtime surfaces."""

    require_version: bool = True
    require_audit: bool = True
    default_execution_mode: str = "dry_run"
    max_context_chars: int = 12_000

    def __post_init__(self) -> None:
        if self.default_execution_mode not in {"dry_run", "live"}:
            raise ValueError("default_execution_mode must be dry_run or live")
        if self.max_context_chars <= 0:
            raise ValueError("max_context_chars must be positive")


__all__ = ["GovernancePolicy"]
