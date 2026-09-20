"""Backward-compatible imports for the standalone Agent Harness."""

from agents.agent_harness.agent_runtime import AgentRuntime

GenericAgentRuntime = AgentRuntime

__all__ = ["AgentRuntime", "GenericAgentRuntime"]
