"""Reusable Agent Harness primitives.

The package contains application-neutral Run, Pipeline, Tool Source and
Runtime contracts. Applications provide their own domain stages and executors.
"""

__version__ = "0.1.0"

from .application import AgentApplication
from .agent import Agent, AgentState, ModelAdapter, ToolCallContext
from .agent_runtime import AgentRuntime
from .context import ContextProvider
from .messages import AgentMessage, ModelTurn, ToolCall
from .observability import InMemoryMetrics, MetricsSink
from .ports import RuntimePorts
from .redaction import redact_for_persistence
from .results import RunResult, RunStatus
from .run_store import RunStore
from .skills import (
    InMemorySkillCatalog,
    MarkdownSkillDirectorySource,
    MarkdownSkillSource,
    SkillBinding,
    SkillCatalog,
    SkillSource,
    StaticSkillSource,
)
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
    CallableTurnPipeline,
    SequentialTurnPipeline,
    TurnExecutionContext,
    TurnPipeline,
    TurnStage,
    TurnStageResult,
)

__all__ = [
    "AgentRuntime",
    "AgentApplication",
    "Agent",
    "ContextProvider",
    "AgentMessage",
    "AgentState",
    "AgentRuntimeKernel",
    "InMemoryToolCatalog",
    "InMemorySkillCatalog",
    "MarkdownSkillSource",
    "ModelAdapter",
    "ModelTurn",
    "InMemoryMetrics",
    "MetricsSink",
    "RuntimePorts",
    "RuntimeSessionBusyError",
    "RuntimeSessionLeaseLostError",
    "RunResult",
    "RunStatus",
    "RunStore",
    "CallableTurnPipeline",
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
    "redact_for_persistence",
    "__version__",
    "SkillBinding",
    "SkillCatalog",
    "SkillSource",
    "StaticSkillSource",
]
