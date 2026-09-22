"""Regression tests for the provider-neutral Runtime extension contracts."""

from types import SimpleNamespace

from agents.ad_agent.core.context import ContextQuery
from agents.ad_agent.core.interfaces import (
    ParsedIntent,
    ToolDefinition,
    ToolEffect,
    ToolSchema,
)
from agents.ad_agent.core.scope import ResourceScope
from agents.agent_harness import TurnRequest
from agents.ad_agent.runtime.account_context import AccountResolver
from agents.ad_agent.runtime.runtime import AdvertisingComposition


def _tool(**overrides):
    values = {
        "name": "custom_write",
        "skill": "custom",
        "namespace": "custom",
        "description": "write a custom resource",
        "input_schema": ToolSchema(
            properties={"workspace_id": {"type": "string"}}
        ),
        "action": "update",
        "resource_type": "resource",
        "resource_id_field": "resource_id",
        "intent_types": ["update_resource"],
        "effect_class": ToolEffect.WRITE,
    }
    values.update(overrides)
    return ToolDefinition(**values)


def test_tool_definition_publishes_scope_and_live_permission_metadata():
    tool = _tool(
        scope_type="workspace",
        scope_fields=["workspace_id"],
        scope_required=True,
        live_permission="custom.write",
    )

    contract = tool.to_dict()

    assert contract["scope_type"] == "workspace"
    assert contract["scope_fields"] == ["workspace_id"]
    assert contract["scope_required"] is True
    assert contract["live_permission"] == "custom.write"


def test_account_resolver_prefers_publisher_declared_scope_fields():
    class InputBuilder:
        @staticmethod
        def platform_params_for_intent(_intent, _namespace):
            return {"custom_write": {"workspace_id": "workspace-42"}}

    services = SimpleNamespace(
        input_builder=InputBuilder(),
        canonical_platform=lambda value: value,
        available_accounts=lambda *_args: [],
    )
    resolver = AccountResolver(services)
    tool = _tool(
        scope_type="workspace",
        scope_fields=["workspace_id"],
        scope_required=True,
    )

    resolved = resolver.resolve(
        ParsedIntent(
            "update_resource",
            "update",
            ["custom"],
            scoped_parameters={"custom": {"workspace_id": "workspace-42"}},
        ),
        "custom",
        [tool],
        None,
        allow_automatic_account=False,
    )

    assert resolved == "workspace-42"


def test_account_resolver_exposes_a_provider_neutral_scope():
    class InputBuilder:
        @staticmethod
        def platform_params_for_intent(_intent, _namespace):
            return {"custom_write": {"workspace_id": "workspace-42"}}

    services = SimpleNamespace(
        input_builder=InputBuilder(),
        canonical_platform=lambda value: value,
        available_accounts=lambda *_args: [],
    )
    resolver = AccountResolver(services)
    tool = _tool(
        scope_type="workspace",
        scope_fields=["workspace_id"],
        scope_required=True,
    )

    scope = resolver.resolve_scope(
        ParsedIntent("update_resource", "update", ["custom"]),
        [tool],
    )

    assert isinstance(scope, ResourceScope)
    assert scope.to_dict() == {
        "scope_type": "workspace",
        "scope_id": "workspace-42",
        "namespace": "custom",
        "source": "ad-account-resolver",
    }


def test_live_permission_is_declared_by_tool_not_inferred_as_ads_write():
    runtime = AdvertisingComposition(require_llm=False, enforce_account_scope=False)
    runtime.execution_mode = "live"

    generic_tool = _tool()
    assert runtime._check_tool_permissions(
        generic_tool, granted_permissions=frozenset()
    ) is None

    scoped_tool = _tool(live_permission="custom.write")
    error = runtime._check_tool_permissions(
        scoped_tool, granted_permissions=frozenset()
    )
    assert error == "缺少工具所需权限：custom.write"


def test_context_query_is_immutable_and_bounds_provider_inputs():
    query = ContextQuery(
        text="  hello  ",
        namespaces=["custom"],
        intent_type="update_resource",
        filters={"knowledge_types": ["concept"]},
        tenant_id="tenant-a",
        limit=999,
        max_excerpt_chars=999999,
    )

    assert query.text == "hello"
    assert query.namespaces == ("custom",)
    assert query.filters == {"knowledge_types": ("concept",)}
    assert query.limit == 100
    assert query.max_excerpt_chars == 1800


def test_ad_runtime_exposes_generic_tool_registration_without_tool_source():
    runtime = AdvertisingComposition(require_llm=False, features=[])

    class Executor:
        def execute(self, _ctx, _input_data):
            return {"source": "generic"}

    tool = _tool(name="standalone_tool", namespace="custom")
    try:
        runtime.register_tool(tool, Executor(), source_id="local")
        definition, _handler = runtime._get_registered_tool("standalone_tool")
        assert definition.namespace == "custom"
        assert "standalone_tool" in {
            item.name for item in runtime.registry.list_all()
        }
    finally:
        runtime.close(wait=True)


def test_ad_runtime_uses_the_standard_agent_loop():
    runtime = AdvertisingComposition(require_llm=False, features=[])
    try:
        from agents.agent_harness import Agent, AgentRuntime as HarnessRuntime

        assert isinstance(runtime._platform_application.runtime, HarnessRuntime)
        assert isinstance(runtime._platform_application.agent, Agent)
    finally:
        runtime.close(wait=True)


def test_ad_runtime_has_no_ad_pipeline_modules_or_legacy_executor_boundary():
    from pathlib import Path

    root = Path("agents/ad_agent/runtime")
    assert not (root / "ad_turn_pipeline.py").exists()
    assert not (root / "ad_turn_stages.py").exists()
    assert not (root / "ad_turn_state.py").exists()
    assembly = (root / "ad_runtime_assembly.py").read_text(encoding="utf-8")
    assert "AdvertisingTurnHandler" not in assembly
    assert "AdTurnPipeline" not in assembly
    assert "AdvertisingModelAdapter" in assembly
