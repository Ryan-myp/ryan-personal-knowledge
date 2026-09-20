"""Reusable Agent Harness primitives.

The package contains application-neutral Run, Pipeline, Tool Source and
Runtime contracts. Applications provide their own domain stages and executors.
"""

from .agent import Agent, AgentState, ModelAdapter, ToolCallContext
from .agent_runtime import AgentRuntime
from .messages import AgentMessage, ModelTurn, ToolCall
from .ports import RuntimePorts
from .results import RunResult, RunStatus
from .run_store import RunStore
from .runtime_kernel import (
    AgentRuntimeKernel,
    RuntimeSessionBusyError,
    RuntimeSessionLeaseLostError,
    SessionLease,
    TurnRequest,
)
from .tool_sources import StaticToolSource, ToolBinding, ToolExecutor, ToolSource
from .tool_catalog import InMemoryToolCatalog, ToolCatalog
from .turn_pipeline import (
    SequentialTurnPipeline,
    TurnExecutionContext,
    TurnPipeline,
    TurnStage,
    TurnStageResult,
)

__all__ = [
    "AgentRuntime",
    "Agent",
    "AgentMessage",
    "AgentState",
    "AgentRuntimeKernel",
    "InMemoryToolCatalog",
    "ModelAdapter",
    "ModelTurn",
    "RuntimePorts",
    "RuntimeSessionBusyError",
    "RuntimeSessionLeaseLostError",
    "RunResult",
    "RunStatus",
    "RunStore",
    "SequentialTurnPipeline",
    "SessionLease",
    "StaticToolSource",
    "ToolBinding",
    "ToolCall",
    "ToolCallContext",
    "ToolCatalog",
    "ToolExecutor",
    "ToolSource",
    "TurnExecutionContext",
    "TurnPipeline",
    "TurnRequest",
    "TurnStage",
    "TurnStageResult",
]
