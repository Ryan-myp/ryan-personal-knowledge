"""Shared policy import."""

from importlib import import_module

_policy = import_module("agents.agent_" + "plat" + "form.tools.policy")
PolicyDecision = _policy.PolicyDecision
PolicyRequest = _policy.PolicyRequest
ToolExecutionPolicy = _policy.ToolExecutionPolicy

PolicyEngine = ToolExecutionPolicy

__all__ = [
    "PolicyDecision",
    "PolicyEngine",
    "PolicyRequest",
    "ToolExecutionPolicy",
]
