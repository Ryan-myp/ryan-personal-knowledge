"""Execution deadlines stay aligned across the HTTP Agent and providers."""

import inspect
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from agents.agent_harness.agent import Agent
from agents.agent_harness.core.llm_client import LLMClient, create_llm_client
from agents.agent_platform.governance.policy import GovernancePolicy
from agents.applications.advertising.composition.ad_application import AdvertisingComposition
from agents.applications.advertising.composition.ad_application_assembly import AdApplicationAssembly
from agents.deployments.advertising.api.models import MCPServerRequest, MCPServerPatchRequest
from agents.tools.advertising.clients.meta_client import MetaAPIClient
from agents.tools.advertising.providers.source_factory import create_tool_source


@pytest.mark.parametrize("provider", ("google-ads", "meta", "tiktok", "dv360"))
def test_every_builtin_tool_uses_the_500_second_execution_budget(provider):
    definitions = [
        binding.definition for binding in create_tool_source(provider).list_bindings()
    ]
    assert definitions
    assert {tool.timeout_seconds for tool in definitions} == {500.0}


def test_execution_defaults_are_500_seconds_at_every_layer():
    policy = GovernancePolicy()
    assert policy.model_timeout_seconds == 500.0
    assert policy.tool_timeout_seconds == 500.0
    assert MetaAPIClient({}).request_timeout == 500.0
    for factory, names in (
        (Agent, ("model_timeout_seconds", "tool_timeout_seconds")),
        (LLMClient, ("timeout_seconds",)),
        (create_llm_client, ("timeout_seconds",)),
        (AdvertisingComposition, ("turn_timeout_seconds", "task_timeout_seconds")),
    ):
        defaults = inspect.signature(factory).parameters
        for name in names:
            assert defaults[name].default == 500.0


def test_advertising_composition_passes_the_budget_to_the_generic_harness():
    runtime = SimpleNamespace(
        max_tool_calls=32, turn_timeout_seconds=500.0,
        registry=None, metrics=None, _redact_for_persistence=lambda value: value,
    )
    services = SimpleNamespace(tool_policy=None, run_store=None, security=None)
    options = AdApplicationAssembly._platform_options(
        runtime, SimpleNamespace(persistence_store=None), services, None,
    )
    assert options["model_timeout_seconds"] == 500.0
    assert options["tool_timeout_seconds"] == 500.0
    # Provider retries already consume one bounded request budget.
    assert options["tool_max_retries"] == 0


def test_mcp_execution_accepts_500_seconds_without_a_hidden_120_second_cap():
    assert MCPServerRequest(
        name="test", endpoint="https://example.com/mcp",
    ).timeout_seconds == 500.0
    assert MCPServerPatchRequest(timeout_seconds=500.0).timeout_seconds == 500.0
    for invalid in (0, 501, float("inf"), float("nan")):
        with pytest.raises(ValidationError):
            MCPServerPatchRequest(timeout_seconds=invalid)
