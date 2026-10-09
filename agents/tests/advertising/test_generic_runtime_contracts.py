"""Regression tests for the provider-neutral Runtime extension contracts."""

from types import SimpleNamespace

from agents.agent_harness.core.context import ContextQuery
from agents.agent_harness.core.interfaces import (
    ParsedIntent,
    ToolDefinition,
    ToolEffect,
    ToolSchema,
)
from agents.agent_harness.core.scope import ResourceScope
from agents.agent_harness import TurnRequest
from agents.tools.advertising.application.execution.account_context import AccountResolver
from agents.tools.advertising.application.composition.ad_application import AdvertisingComposition


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


def test_tool_definition_publishes_provider_cancellation_contract():
    tool = _tool(cancellation_mode="interruptible")

    assert tool.cancellation_mode == "interruptible"
    assert tool.to_dict()["cancellation_mode"] == "interruptible"


def test_tool_definition_rejects_unknown_cancellation_contract():
    try:
        _tool(cancellation_mode="force_kill")
    except ValueError as exc:
        assert "cancellation_mode" in str(exc)
    else:
        raise AssertionError("invalid cancellation mode was accepted")


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


def test_account_resolver_does_not_propagate_global_account_across_namespaces():
    class InputBuilder:
        @staticmethod
        def platform_params_for_intent(_intent, _namespace):
            return {}

    services = SimpleNamespace(
        input_builder=InputBuilder(),
        canonical_platform=lambda value: {
            "google": "google-ads",
        }.get(value, value),
        available_accounts=lambda platform, _scope: {
            "meta": ["meta-test-account"],
            "google-ads": ["google-test-account"],
        }[platform],
    )
    resolver = AccountResolver(services)
    intent = ParsedIntent(
        "cross_channel_compare",
        "compare",
        ["meta", "google-ads"],
    )
    meta_tool = _tool(
        name="meta_list",
        namespace="meta",
        effect_class=ToolEffect.READ,
        scope_type="account",
        scope_fields=["account_id"],
        input_schema=ToolSchema(properties={"account_id": {"type": "string"}}),
    )
    google_tool = _tool(
        name="google_list",
        namespace="google-ads",
        effect_class=ToolEffect.READ,
        scope_type="account",
        scope_fields=["customer_id"],
        input_schema=ToolSchema(properties={"customer_id": {"type": "string"}}),
    )

    assert resolver.resolve(
        intent,
        "meta",
        [meta_tool],
        "global-meta-account",
    ) == "meta-test-account"
    assert resolver.resolve(
        intent,
        "google-ads",
        [google_tool],
        "global-meta-account",
    ) == "google-test-account"


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


def test_injected_model_is_used_by_the_generic_harness_run():
    from agents.agent_harness import ModelTurn

    class Model:
        def complete(self, _messages, _tools, _request):
            return ModelTurn(content="Harness model is connected.")

    runtime = AdvertisingComposition(require_llm=True, features=[])
    model = Model()
    try:
        runtime.inject_llm(model)

        result = runtime.run("你好", user_id="operator-1")

        assert runtime.platform_application.agent.model is model
        assert result["status"] == "succeeded", result
        assert result["reply"] == "Harness model is connected."
    finally:
        runtime.close(wait=True)


def test_one_harness_run_executes_tools_from_multiple_namespaces():
    from agents.agent_harness import ModelTurn, ToolCall
    from agents.agent_harness.core.interfaces import ToolResult

    class Model:
        def __init__(self):
            self.calls = 0

        def complete(self, _messages, tools, _request):
            self.calls += 1
            names = {item.name for item in tools}
            if self.calls == 1:
                assert {"alpha_read_record", "beta_read_record"} <= names
                return ModelTurn(tool_calls=(
                    ToolCall(id="call-alpha", name="alpha_read_record", arguments={}),
                    ToolCall(id="call-beta", name="beta_read_record", arguments={}),
                ))
            return ModelTurn(content="Both records are ready.")

    executed = []
    runtime = AdvertisingComposition(
        require_llm=True,
        llm_client=Model(),
        features=[],
        enforce_account_scope=False,
    )
    for namespace in ("alpha", "beta"):
        runtime.register_tool(
            _tool(
                name=f"{namespace}_read_record",
                namespace=namespace,
                skill=namespace,
                description=f"Read records from {namespace}",
                action="list",
                effect_class=ToolEffect.READ,
                input_schema=ToolSchema(),
                intent_types=["list_records"],
            ),
            lambda _context, _arguments, source=namespace: (
                executed.append(source) or ToolResult.ok({"source": source})
            ),
            source_id=f"{namespace}-source",
        )

    try:
        result = runtime.run(
            "Read records from alpha and beta",
            user_id="operator-1",
        )

        assert result["status"] == "succeeded", result
        assert result["reply"] == "Both records are ready."
        assert result["tool_plan"] == {
            "alpha": ["alpha_read_record"],
            "beta": ["beta_read_record"],
        }
        assert executed == ["alpha", "beta"]
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


def test_advertising_composition_injects_the_generic_model_directly():
    from agents.agent_harness import ModelTurn

    class Model:
        def complete(self, _messages, _tools, _request):
            return ModelTurn(content="Generic Harness response.")

    model = Model()
    runtime = AdvertisingComposition(
        require_llm=False,
        features=[],
        llm_client=model,
    )
    try:
        assert runtime._platform_application.agent.model is model
        result = runtime.run("hello", session_id="generic-session")
        assert result["reply"] == "Generic Harness response."
        assert result["status"] == "succeeded", result
        assert result["intent"]["intent_type"] == "chat"
    finally:
        runtime.close(wait=True)


def test_generic_run_results_keep_tool_result_and_confirmation_contracts():
    from types import SimpleNamespace

    from agents.tools.advertising.application.run.ad_run_projection import (
        AdvertisingRunProjection,
    )

    definition = SimpleNamespace(
        name="publish_record",
        namespace="records",
        action="publish",
        resource_type="record",
        intent_types=["publish_record"],
    )
    runtime = SimpleNamespace(
        registry=SimpleNamespace(get=lambda _name: (definition, object())),
        _sessions={},
    )

    result = AdvertisingRunProjection.application_state_from_run(
        runtime,
        {
            "needs_input": True,
            "tool_results": [{
                "name": "publish_record",
                "content": {"success": False, "error": "approval required"},
                "needs_confirmation": True,
                "confirmation_payload": {"token": "opaque"},
            }],
        },
        "session-1",
        "Publish record",
    )

    assert result["intent"] == {
        "intent_type": "publish_record",
        "namespaces": ["records"],
        "raw_input": "Publish record",
    }
    assert result["tool_plan"] == {"records": ["publish_record"]}
    assert result["last_results"][0]["action"] == "publish"
    assert result["needs_input"] is True
    assert result["needs_confirmation"] is True
    assert result["confirmation_payload"] == {"token": "opaque"}


def test_generic_run_invokes_registered_advertising_tool_with_scoped_account():
    from agents.agent_harness import ModelTurn, ToolCall

    class MetaClient:
        platform = "meta"

        def __init__(self):
            self.accounts = []

        def list_campaigns(self, account_id, limit=25):
            self.accounts.append(account_id)
            return [{"id": "campaign-1", "name": "Test campaign"}]

    class Model:
        def __init__(self):
            self.calls = 0

        def complete(self, _messages, tools, _request):
            self.calls += 1
            if self.calls == 1:
                names = {item.name for item in tools}
                assert "meta_list_campaigns" in names
                return ModelTurn(tool_calls=(ToolCall(
                    id="call-1",
                    name="meta_list_campaigns",
                    arguments={"account_id": "meta-test-account", "limit": 2},
                ),))
            return ModelTurn(content="Found one campaign.")

    from agents.tools.advertising.application.execution.account_policy import (
        AccountWhitelistValidator,
    )
    from agents.tools.advertising.application.composition.ad_application import (
        AdvertisingComposition,
    )
    from agents.tools.advertising.providers.meta import create_meta_tool_source
    from agents.agent_platform.data.persistence.store import AdAgentStore

    client = MetaClient()
    validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
    validator.allowed_accounts = {"meta": ["meta-test-account"]}
    runtime = AdvertisingComposition(
        require_llm=True,
        llm_client=Model(),
        persistence_store=AdAgentStore(":memory:"),
        whitelist_validator=validator,
    )
    runtime.register_tool_source(create_meta_tool_source(client))
    try:
        assert "provider-module:meta" in runtime._platform_application.tool_source_ids
        result = runtime.run(
            "列出 Meta campaign",
            user_id="operator-1",
            account_id="meta-test-account",
        )

        assert result["status"] == "succeeded", result
        assert result["reply"] == "Found one campaign."
        assert result["tool_plan"] == {"meta": ["meta_list_campaigns"]}
        assert result["results"][0]["success"] is True
        assert client.accounts == ["meta-test-account"]
    finally:
        runtime.close(wait=True)


def test_generic_run_rejects_model_selected_account_outside_trusted_scope():
    from agents.agent_harness import ModelTurn, ToolCall

    class MetaClient:
        platform = "meta"

        def __init__(self):
            self.accounts = []

        def list_campaigns(self, account_id, limit=25):
            self.accounts.append(account_id)
            return []

    class Model:
        def __init__(self):
            self.calls = 0

        def complete(self, _messages, tools, _request):
            self.calls += 1
            if self.calls > 1:
                return ModelTurn(content="Done.")
            assert any(item.name == "meta_list_campaigns" for item in tools)
            return ModelTurn(tool_calls=(ToolCall(
                id="call-1",
                name="meta_list_campaigns",
                arguments={"account_id": "other-account", "limit": 1},
            ),))

    from agents.tools.advertising.application.execution.account_policy import (
        AccountWhitelistValidator,
    )
    from agents.tools.advertising.application.composition.ad_application import (
        AdvertisingComposition,
    )
    from agents.tools.advertising.providers.meta import create_meta_tool_source
    from agents.agent_platform.data.persistence.store import AdAgentStore

    client = MetaClient()
    validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
    validator.allowed_accounts = {"meta": ["trusted-account", "other-account"]}
    runtime = AdvertisingComposition(
        require_llm=True,
        llm_client=Model(),
        persistence_store=AdAgentStore(":memory:"),
        whitelist_validator=validator,
    )
    runtime.register_tool_source(create_meta_tool_source(client))
    try:
        result = runtime.run(
            "列出 Meta campaign",
            user_id="operator-1",
            account_id="trusted-account",
        )

        assert result["status"] == "awaiting_input", result
        assert result["results"]
        assert client.accounts == []
    finally:
        runtime.close(wait=True)


def test_generic_run_uses_model_tool_loop_for_follow_up_queries():
    from agents.agent_harness import ModelTurn, ToolCall

    class MetaClient:
        platform = "meta"

        def __init__(self):
            self.calls = []

        def list_campaigns(self, account_id, limit=25):
            self.calls.append(("list", account_id, limit))
            return [{"id": "campaign-1", "name": "Test campaign"}]

        def get_campaign(self, campaign_id):
            self.calls.append(("get", campaign_id))
            return {"id": campaign_id, "name": "Test campaign", "status": "PAUSED"}

    class Model:
        def __init__(self):
            self.calls = 0

        def complete(self, messages, tools, _request):
            self.calls += 1
            names = {item.name for item in tools}
            assert {"meta_list_campaigns", "meta_get_campaign"} <= names
            if self.calls == 1:
                return ModelTurn(tool_calls=(ToolCall(
                    id="list-call",
                    name="meta_list_campaigns",
                    arguments={"account_id": "meta-test-account", "limit": 1},
                ),))
            if self.calls == 2:
                previous = next(
                    item for item in reversed(messages)
                    if item.role == "tool" and item.name == "meta_list_campaigns"
                )
                assert "campaign-1" in str(previous.content)
                return ModelTurn(tool_calls=(ToolCall(
                    id="get-call",
                    name="meta_get_campaign",
                    arguments={"campaign_id": "campaign-1"},
                ),))
            return ModelTurn(content="Campaign details retrieved.")

    from agents.tools.advertising.application.execution.account_policy import (
        AccountWhitelistValidator,
    )
    from agents.tools.advertising.application.composition.ad_application import (
        AdvertisingComposition,
    )
    from agents.tools.advertising.providers.meta import create_meta_tool_source
    from agents.agent_platform.data.persistence.store import AdAgentStore

    client = MetaClient()
    validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
    validator.allowed_accounts = {"meta": ["meta-test-account"]}
    model = Model()
    runtime = AdvertisingComposition(
        require_llm=True,
        llm_client=model,
        persistence_store=AdAgentStore(":memory:"),
        whitelist_validator=validator,
    )
    runtime.register_tool_source(create_meta_tool_source(client))
    try:
        result = runtime.run(
            "查询 Meta campaign 列表和详情",
            user_id="operator-1",
            account_id="meta-test-account",
        )

        assert result["status"] == "succeeded", result
        assert result["reply"] == "Campaign details retrieved."
        assert model.calls == 3
        assert client.calls == [
            ("list", "meta-test-account", 1),
            ("get", "campaign-1"),
        ]
        assert result["tool_plan"] == {
            "meta": ["meta_list_campaigns", "meta_get_campaign"],
        }
    finally:
        runtime.close(wait=True)


def test_ad_runtime_has_no_ad_pipeline_modules_or_legacy_executor_boundary():
    from pathlib import Path

    root = Path("agents/tools/advertising/application")
    assert not (root / "ad_turn_pipeline.py").exists()
    assert not (root / "ad_turn_stages.py").exists()
    assert not (root / "ad_turn_state.py").exists()
    assembly = (root / "composition/ad_application_assembly.py").read_text(encoding="utf-8")
    assert "AdvertisingTurnHandler" not in assembly
    assert "AdTurnPipeline" not in assembly
    assert "AdvertisingModelAdapter" not in assembly


def test_ad_run_rejects_invalid_request_envelopes_before_model():
    from agents.agent_harness import ModelTurn
    from agents.agent_platform.data.persistence.store import AdAgentStore

    class Model:
        def __init__(self):
            self.calls = 0

        def complete(self, _messages, _tools, _request):
            self.calls += 1
            return ModelTurn(content="unexpected model call")

    model = Model()
    runtime = AdvertisingComposition(
        require_llm=True,
        llm_client=model,
        persistence_store=AdAgentStore(":memory:"),
    )
    cases = (
        ("查询广告数据", "not-an-object", "platform_params 必须是对象"),
        (
            "查询广告数据",
            {"meta": {"access_token": "test-secret"}},
            "access_token",
        ),
        ("使用 access_token=test-secret 查询数据", None, "access_token"),
    )
    try:
        for user_input, platform_params, expected in cases:
            result = runtime.run(
                user_input,
                user_id="operator-1",
                platform_params=platform_params,
            )

            assert result["status"] == "failed", result
            assert result["run_id"] and result["turn_id"]
            assert any(expected in item for item in result["policy_errors"])
            assert "test-secret" not in str(result)
        assert model.calls == 0
    finally:
        runtime.close(wait=True)
