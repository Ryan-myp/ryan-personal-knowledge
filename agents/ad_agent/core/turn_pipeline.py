"""Application-neutral turn pipeline contracts.

The pipeline owns stage sequencing and terminal/error semantics.  Stages own
the application work: parsing, context retrieval, planning, policy checks,
execution, persistence, and rendering can all be supplied by an embedding
without adding domain branches to the Core.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional, Protocol, Sequence

from .runtime_kernel import TurnRequest


@dataclass
class TurnExecutionContext:
    """Mutable, request-scoped state shared by pipeline stages."""

    request: TurnRequest
    state: dict[str, Any] = field(default_factory=dict)
    result: Any = None


@dataclass(frozen=True)
class TurnStageResult:
    """Optional stage decision used to continue or terminate a turn."""

    stop: bool = False
    value: Any = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def complete(
        cls, value: Any = None, *, metadata: Optional[Mapping[str, Any]] = None,
    ) -> "TurnStageResult":
        return cls(stop=True, value=value, metadata=dict(metadata or {}))

    @classmethod
    def continue_with(
        cls, value: Any = None, *, metadata: Optional[Mapping[str, Any]] = None,
    ) -> "TurnStageResult":
        return cls(stop=False, value=value, metadata=dict(metadata or {}))


class TurnStage(Protocol):
    """One application-owned step in a turn."""

    def execute(self, context: TurnExecutionContext) -> Any:
        """Return a stage result, a value, or None to continue."""
        ...


class TurnPipeline(Protocol):
    """Executable pipeline accepted by the generic Runtime."""

    def execute(self, request: TurnRequest) -> Any:
        """Execute one normalized Runtime request."""
        ...


class SequentialTurnPipeline:
    """Deterministic stage runner shared by all embedding applications."""

    def __init__(
        self,
        stages: Sequence[TurnStage | Callable[[TurnExecutionContext], Any]],
        *,
        on_error: Optional[Callable[[TurnExecutionContext, Exception], Any]] = None,
        on_complete: Optional[Callable[[TurnExecutionContext], Any]] = None,
    ) -> None:
        self._stages = tuple(stages)
        self._on_error = on_error
        self._on_complete = on_complete

    @staticmethod
    def _run_stage(stage: Any, context: TurnExecutionContext) -> Any:
        execute = getattr(stage, "execute", None)
        if callable(execute):
            return execute(context)
        if callable(stage):
            return stage(context)
        raise TypeError("turn pipeline stage must be callable or expose execute()")

    def execute(self, request: TurnRequest) -> Any:
        context = TurnExecutionContext(request=request)

        def complete() -> Any:
            if self._on_complete is not None:
                value = self._on_complete(context)
                if value is not None:
                    context.result = value
            return context.result

        try:
            for stage in self._stages:
                value = self._run_stage(stage, context)
                if isinstance(value, TurnStageResult):
                    if value.value is not None:
                        context.result = value.value
                    stage_name = self._stage_name(stage)
                    metadata = dict(value.metadata or {})
                    if metadata:
                        stage_metadata = context.state.setdefault(
                            "stage_metadata", {}
                        )
                        stage_metadata[stage_name] = metadata
                    context.state.setdefault("stage_results", []).append({
                        "stage": stage_name,
                        "stop": bool(value.stop),
                        "metadata": metadata,
                    })
                    if value.stop:
                        return complete()
                    continue
                if value is not None:
                    context.result = value
            return complete()
        except Exception as error:
            if self._on_error is None:
                raise
            return self._on_error(context, error)

    @staticmethod
    def _stage_name(stage: Any) -> str:
        name = getattr(stage, "name", None)
        if name:
            return str(name)
        if callable(stage) and getattr(stage, "__name__", None):
            return str(stage.__name__)
        return type(stage).__name__


__all__ = [
    "SequentialTurnPipeline",
    "TurnExecutionContext",
    "TurnPipeline",
    "TurnStage",
    "TurnStageResult",
]
