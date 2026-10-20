from types import SimpleNamespace
from pathlib import Path

import pytest

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
    security = SimpleNamespace(
        filter_account_discovery_result=lambda _tool, result, _scope: result
    )
    owner = SimpleNamespace(
        tool_executor=SimpleNamespace(execute=execute),
        security=security,
        write_guard=None,
        input_builder=SimpleNamespace(parameter_selection=selection),
        _build_request_clients=lambda *_: {},
        _canonical_platform=lambda value: value,
        _resolve_platform_identifier=lambda value: value,
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


def test_provider_executor_resolves_creative_asset_only_for_trusted_identity():
    asset_id = "11111111111141118111111111111111"
    media_path = Path("/private/creative-assets/generated.png")
    observed = {}

    class AssetStore:
        def get(
            self, requested_id, *, tenant_id, user_id, include_content=True,
        ):
            assert requested_id == asset_id
            assert (tenant_id, user_id) == ("tenant-a", "user-a")
            assert include_content is False
            return SimpleNamespace(
                path=media_path,
                content=None,
                metadata={
                    "asset_id": asset_id,
                    "status": "ready",
                    "media_type": "image/png",
                },
            )

    def execute(_context, _name, arguments, _clients):
        observed.update(arguments)
        return ToolResult.ok({"image_asset": {"hash": "meta-hash"}})

    owner = SimpleNamespace(
        creative_asset_store=AssetStore(),
        tool_executor=SimpleNamespace(execute=execute),
        write_guard=None,
        security=SimpleNamespace(
            filter_account_discovery_result=lambda _tool, result, _scope: result,
        ),
        input_builder=SimpleNamespace(parameter_selection=SimpleNamespace(
            decorate_lookup_result=lambda _tool, result, *_args: result,
        )),
        _build_request_clients=lambda *_args: {},
        _canonical_platform=lambda value: value,
        _resolve_platform_identifier=lambda value: value,
        _sessions={},
        _ensure_session=lambda *_args, **_kwargs: session,
    )
    tool = ToolDefinition(
        name="meta_upload_image_asset",
        skill="meta-marketing-api",
        namespace="meta",
        description="Upload a creative asset",
        action="upload",
        resource_type="image_asset",
        input_schema=ToolSchema(
            properties={
                "account_id": {"type": "string"},
                "creative_asset_id": {
                    "type": "string",
                    "x-creative-asset": {
                        "target_field": "file_path",
                        "media_types": ["image/png"],
                    },
                },
            },
        ),
        scope_fields=["account_id"],
        effect_class=ToolEffect.EXTERNAL_WRITE,
    )
    request = TurnRequest(
        user_input="upload generated image",
        session_id="test-session",
        user_id="user-a",
        tenant_id="tenant-a",
        context={"account_id": "account-1"},
        principal=SimpleNamespace(
            user_id="user-a",
            tenant_id="tenant-a",
            account_scope={"meta": frozenset({"account-1"})},
        ),
        execution_mode="live",
    )
    session = SimpleNamespace(
        ctx=ToolContext(
            session_id="test-session",
            user_id="user-a",
            scope={},
            metadata={},
        )
    )
    executor = AdvertisingToolExecutor(owner, tool)

    result = executor._run_tool(request, request.context, session, {
        "account_id": "account-1",
        "creative_asset_id": asset_id,
    })

    assert result.success
    assert observed == {
        "account_id": "account-1",
        "file_path": str(media_path),
    }
    assert "creative_asset_id" not in observed
    assert str(media_path) not in repr(result.to_dict())


def test_provider_executor_rejects_cross_user_or_unready_creative_assets():
    from agents.agent_platform.governance.identity.principal import RequestPrincipal

    asset_id = "11111111111141118111111111111111"
    calls = []

    class AssetStore:
        def get(
            self, _asset_id, *, tenant_id, user_id, include_content=True,
        ):
            calls.append((tenant_id, user_id))
            raise FileNotFoundError("not found")

    owner = SimpleNamespace(
        creative_asset_store=AssetStore(),
        write_guard=None,
        _canonical_platform=lambda value: value,
        _resolve_platform_identifier=lambda value: value,
        _build_request_clients=lambda *_args: {},
    )
    tool = ToolDefinition(
        name="meta_upload_image_asset",
        skill="meta-marketing-api",
        namespace="meta",
        description="Upload a creative asset",
        action="upload",
        resource_type="image_asset",
        input_schema=ToolSchema(properties={
            "creative_asset_id": {
                "type": "string",
                "x-creative-asset": {
                    "target_field": "file_path",
                    "media_types": ["image/png"],
                },
            },
        }),
        effect_class=ToolEffect.EXTERNAL_WRITE,
    )
    request = TurnRequest(
        user_input="upload generated image",
        session_id="test-session",
        user_id="user-b",
        tenant_id="tenant-b",
        principal=RequestPrincipal(user_id="user-b", tenant_id="tenant-b"),
        execution_mode="live",
    )
    session = SimpleNamespace(
        ctx=ToolContext(session_id="test-session", user_id="user-b"),
    )

    result = AdvertisingToolExecutor(owner, tool)._run_tool(
        request,
        {},
        session,
        {"creative_asset_id": asset_id},
    )

    assert not result.success
    assert "不存在" in result.error
    assert calls == [("tenant-b", "user-b")]


def test_provider_executor_rejects_user_supplied_server_file_paths():
    definition = ToolDefinition(
        name="meta_upload_image_asset",
        skill="meta-marketing-api-expert",
        namespace="meta",
        description="Upload an image asset",
        input_schema=ToolSchema(
            properties={
                "file_path": {"type": "string"},
                "creative_asset_id": {
                    "type": "string",
                    "x-creative-asset": {
                        "target_field": "file_path",
                        "media_types": ["image/png"],
                    },
                },
            },
            additional_properties=False,
        ),
    )
    owner = SimpleNamespace(
        creative_asset_store=None,
        tool_executor=SimpleNamespace(execute=lambda *_args: pytest.fail(
            "untrusted file path must not reach provider executor"
        )),
    )
    executor = AdvertisingToolExecutor(owner, definition)
    request = SimpleNamespace(
        principal=SimpleNamespace(tenant_id="tenant-a", user_id="user-a"),
        lease_lost_event=None,
    )

    resolved, paths, error = executor._creative_asset_arguments(
        request,
        {"file_path": "/etc/passwd"},
    )

    assert resolved == {}
    assert paths == ()
    assert "素材库" in error


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


def test_account_authorized_on_another_channel_is_reported_as_channel_mismatch():
    owner = SimpleNamespace(
        _canonical_platform=lambda value: value,
        _resolve_platform_identifier=lambda value: value,
        _validate_account_with_principal=lambda *_args: (
            False, "账户不在当前身份的授权范围内",
        ),
    )
    factory = AdvertisingToolPolicyFactory(owner)
    request = SimpleNamespace(
        principal=SimpleNamespace(
            account_scope={"tiktok": frozenset({"test-tiktok-account"})},
        )
    )

    error = factory._account_authorization_error(
        request,
        "meta",
        "test-tiktok-account",
        False,
    )

    assert error is not None
    assert error[0] == "scope_mismatch"
    assert "tiktok" in error[1]
    assert "meta" in error[1]
    assert "授权范围内" not in error[1]
