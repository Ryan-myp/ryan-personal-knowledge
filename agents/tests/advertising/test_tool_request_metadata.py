from types import SimpleNamespace

from agents.agent_harness import TurnRequest
from agents.agent_harness.core.interfaces import (
    ToolContext,
    ToolDefinition,
    ToolSchema,
    ToolResult,
    ToolEffect,
)
from agents.applications.advertising.integrations.integration import (
    AdvertisingToolExecutor,
)
from agents.applications.advertising.execution.ad_tool_policy_factory import (
    AdvertisingToolPolicyFactory,
)


def test_provider_executor_receives_trusted_run_mode_and_identity():
    seen = {}

    def execute(context, *_args):
        seen.update(context.metadata)
        return ToolResult.ok({"id": "new-test-resource"})

    selection = SimpleNamespace(
        decorate_lookup_result=lambda _tool, result, *_args: result
    )
    owner = SimpleNamespace(
        tool_executor=SimpleNamespace(execute=execute),
        write_guard=None,
        input_builder=SimpleNamespace(parameter_selection=selection),
        _build_request_clients=lambda *_: {},
    )
    tool = ToolDefinition(
        name="test_create",
        skill="test",
        namespace="test",
        description="Create test resource",
        action="create",
        resource_type="campaign",
        input_schema=ToolSchema(),
        effect_class=ToolEffect.WRITE,
    )
    request = TurnRequest(
        user_input="create",
        session_id="test-session",
        run_id="test-run",
        turn_id="test-turn",
        execution_mode="live",
    )
    session = SimpleNamespace(
        ctx=ToolContext(session_id="test-session", user_id="test-user")
    )
    executor = AdvertisingToolExecutor(owner, tool)
    result = executor._run_tool(request, {}, session, {})
    assert seen["execution_mode"] == "live"
    assert seen["run_id"] == "test-run"
    assert seen["turn_id"] == "test-turn"
    assert result.data["execution_mode"] == "live"
    assert result.data["execution_status"] == "executed"


def test_candidate_tool_namespaces_do_not_turn_a_scoped_request_into_multi_account():
    owner = SimpleNamespace(
        _canonical_platform=lambda value: value,
        _resolve_platform_identifier=lambda value: value,
    )
    factory = AdvertisingToolPolicyFactory(owner)
    tool = SimpleNamespace(scope_fields=("customer_id",))
    request_context = {
        "account_id": "test-google",
        "platform_params": {"google-ads": {"campaign_id": "test-campaign"}},
        "_agent_tool_namespaces": ["google-ads", "meta", "tiktok"],
    }
    assert factory._accounts_for_call(tool, "google-ads", {}, request_context) == (
        "test-google",
        None,
    )
