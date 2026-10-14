"""Page-shaped conversations must not depend on a prefilled account field."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agents.agent_harness.core.interfaces import ToolContext, ToolDefinition, ToolSchema
from agents.agent_harness.core.namespace import normalize_namespace
from agents.agent_harness.messages import ModelTurn
from agents.agent_platform.governance.identity.principal import RequestPrincipal
from agents.applications.advertising.composition.ad_application import AdvertisingComposition
from agents.applications.advertising.execution.account_policy import AccountWhitelistValidator
from agents.applications.advertising.execution.ad_tool_policy_factory import AdvertisingToolPolicyFactory
from agents.applications.advertising.integrations.integration import AdvertisingToolExecutor
from agents.applications.advertising.integrations.ad_capability_catalog import AdvertisingCapabilityCatalog
from agents.applications.advertising.persistence.store import AdAgentStore
from agents.deployments.advertising.api.context import ApiContext
from agents.deployments.advertising.api.routes.chat import create_chat_router
from agents.tests.advertising.harness_models import call, install
from agents.tools.advertising.providers.source_factory import create_tool_source


class QueryClient:
    def __init__(self, namespace):
        self.platform = namespace
        self.calls = []
        self.customer_id = None

    def list_accounts(self, business_id=None, limit=100, authorized_account_ids=None):
        self.calls.append(("accounts", tuple(authorized_account_ids or ())))
        return [{"id": "act_test-account", "account_id": "test-account", "name": "Test"}]

    def list_campaigns(self, account_id=None, limit=25, page_size=100):
        self.calls.append(("campaigns", account_id or self.customer_id))
        return [{"id": "101", "campaign_id": "101", "name": "Test campaign"}]

    def get_campaign(self, *args):
        self.calls.append(("campaign", args))
        return {"id": "101", "name": "Test campaign"}

    def list_adsets(self, account_id, campaign_id, limit=25):
        self.calls.append(("adsets", account_id, campaign_id))
        return [{"id": "201", "campaign_id": campaign_id, "name": "Test ad set"}]

    def list_adgroups(self, account_id, campaign_id, page_size=20):
        self.calls.append(("adgroups", account_id, campaign_id))
        return [{"adgroup_id": "201", "campaign_id": campaign_id}]

    def list_ads(self, account_id, adgroup_id=None, page_size=20):
        self.calls.append(("ads", account_id, adgroup_id))
        return [{"ad_id": "301", "adgroup_id": adgroup_id}]


def _runtime(tmp_path, namespace="meta", client=None):
    validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
    validator.allowed_accounts = {namespace: ["test-account", "second-account"]}
    runtime = AdvertisingComposition(
        require_llm=False,
        persistence_store=AdAgentStore(str(tmp_path / "conversations.db")),
        whitelist_validator=validator,
        start_background_workers=False,
    )
    runtime.register_tool_source(create_tool_source(namespace, client))
    return runtime


def _principal(namespace="meta", accounts=("test-account", "second-account")):
    return RequestPrincipal(
        user_id="operator",
        permissions=frozenset({"ads.read", "ads.plan"}),
        account_scope={namespace: frozenset(accounts)},
    )


def _close(runtime):
    runtime.close(wait=True)
    runtime.persistence_store.close()


def _chat_client(runtime, principal):
    context = ApiContext(
        runtime_getter=lambda: runtime,
        authorize_request=lambda *_: principal,
        require_permission=lambda *_: None,
        activate_tenant_skills=lambda *_: None,
        sync_tenant_extensions=lambda *_: None,
        safe_exception_text=runtime._redact_for_persistence,
        redact=runtime._redact_for_persistence,
    )
    app = FastAPI()
    app.include_router(create_chat_router(context))
    return TestClient(app)


def _prompt(client, text, session="page-conversation", endpoint="/chat"):
    response = client.post(endpoint, json={"user_input": text, "session_id": session})
    assert response.status_code == 200, response.text
    if endpoint == "/chat/stream":
        import json

        events = [
            json.loads(line.removeprefix("data:").strip())
            for line in response.text.splitlines() if line.startswith("data:")
        ]
        reply = next(item for item in events if item.get("type") == "reply")
        done = next(item for item in events if item.get("type") == "done")
        return {**reply, "status": done["status"]}
    return response.json()


@pytest.mark.parametrize("namespace,prefix,field", [
    ("meta", "meta", "account_id"),
    ("google-ads", "google", "customer_id"),
    ("tiktok", "tiktok", "account_id"),
])
def test_model_account_argument_reaches_campaign_handler_without_http_account(
    tmp_path, namespace, prefix, field,
):
    provider = QueryClient(namespace)
    runtime = _runtime(tmp_path, namespace, provider)
    install(
        runtime,
        ModelTurn(tool_calls=(call(f"{prefix}_list_campaigns", {field: "test-account"}),)),
        ModelTurn(content="Campaign query completed."),
    )
    try:
        with _chat_client(runtime, _principal(namespace)) as client:
            result = _prompt(client, f"查询 {namespace} 账户下的 campaign 列表")
        assert result["status"] == "succeeded", result
        assert result["results"][0]["data"]["data_status"] == "live"
        assert provider.calls == [("campaigns", "test-account")]
        assert runtime._sessions["page-conversation"].ctx.account_id is None
    finally:
        _close(runtime)


def test_lookup_selection_token_uses_the_resolved_account_not_the_unselected_session(tmp_path):
    runtime = _runtime(tmp_path, client=QueryClient("meta"))
    install(
        runtime,
        ModelTurn(tool_calls=(call("meta_list_campaigns", {"account_id": "test-account"}),)),
        ModelTurn(content="Campaign query completed."),
    )
    try:
        result = runtime.run(
            "查询 Meta campaign 列表", session_id="scope-token", principal=_principal(),
        )
        assert result["status"] == "succeeded", result
        selection = next(
            item for item in result["results"][0]["data"]["parameter_selections"]
            if item["field"] == "campaign_id"
        )
        option = selection["options"][0]
        claims = {
            "session_id": "scope-token", "user_id": "operator",
            "account_id": "test-account", "platform": "meta",
            "tool_name": selection["tool_name"], "field": "campaign_id",
            "source_tool": "meta_list_campaigns",
        }
        assert runtime._parameter_selection_signer.verify(
            option["selection_token"], **claims,
        ) == "101"
        assert runtime._sessions["scope-token"].ctx.account_id is None
        from agents.tools.advertising.shared.domain.parameter_selection import ParameterSelectionError

        with pytest.raises(ParameterSelectionError, match="account_id"):
            runtime._parameter_selection_signer.verify(
                option["selection_token"], **{**claims, "account_id": "second-account"},
            )
    finally:
        _close(runtime)


@pytest.mark.parametrize("endpoint", ["/chat", "/chat/stream"])
def test_account_directory_then_campaign_then_detail_survives_session_reload(tmp_path, endpoint):
    provider = QueryClient("meta")
    runtime = _runtime(tmp_path, client=provider)
    turns = [
        call("meta_list_accounts"),
        call("meta_list_campaigns", {"account_id": "test-account", "limit": 100}),
        call("meta_get_campaign", {"campaign_id": "101"}),
        call("meta_list_ad_sets", {"campaign_id": "101"}),
    ]
    install(runtime, *[
        turn for tool_call in turns
        for turn in (
            ModelTurn(tool_calls=(tool_call,)),
            ModelTurn(content="Query completed."),
        )
    ])
    try:
        with _chat_client(runtime, _principal()) as client:
            for text in (
                "帮我列出 Meta 账户",
                "查询一下这个 account 下的 campaign 列表",
                "查询 campaign 101 的详情",
                "列出这个 campaign 下的 ad set",
            ):
                result = _prompt(client, text, endpoint=endpoint)
                assert result["status"] == "succeeded", result
                assert result["results"][0]["data"]["data_status"] == "live"
                runtime._sessions.clear()
        assert provider.calls == [
            ("accounts", ("test-account", "second-account")),
            ("campaigns", "test-account"),
            ("campaign", ("101",)),
            ("adsets", "test-account", "101"),
        ]
    finally:
        _close(runtime)


def test_successful_query_account_survives_runtime_restart_without_binding_writes(tmp_path):
    provider = QueryClient("meta")
    runtime = _runtime(tmp_path, client=provider)
    install(
        runtime,
        ModelTurn(tool_calls=(call("meta_list_campaigns", {"account_id": "test-account"}),)),
        ModelTurn(content="Listed."),
    )
    try:
        result = runtime.run(
            "查询 Meta campaign 列表", session_id="s", principal=_principal(),
        )
        assert result["status"] == "succeeded", result
    finally:
        _close(runtime)
    restored = _runtime(tmp_path, client=provider)
    install(
        restored,
        ModelTurn(tool_calls=(call("meta_get_campaign", {"campaign_id": "101"}),)),
        ModelTurn(content="Details."),
    )
    try:
        result = restored.run(
            "查询刚才这个 campaign 的详情", session_id="s", principal=_principal(),
        )
        assert result["status"] == "succeeded", result
        assert provider.calls[-1] == ("campaign", ("101",))
        assert restored._sessions["s"].ctx.account_id is None
    finally:
        _close(restored)


def test_unauthorized_model_account_is_rejected_before_provider_and_not_remembered(tmp_path):
    provider = QueryClient("meta")
    runtime = _runtime(tmp_path, client=provider)
    install(runtime, ModelTurn(tool_calls=(call(
        "meta_list_campaigns", {"account_id": "not-authorized"},
    ),)))
    try:
        result = runtime.run(
            "查询 Meta campaign 列表", session_id="s", principal=_principal(),
        )
        assert result["status"] != "succeeded"
        assert provider.calls == []
        assert not runtime._sessions["s"].ctx.metadata.get("read_account_scopes")
    finally:
        _close(runtime)


def test_remembered_accounts_remain_namespace_scoped_and_never_select_writes():
    owner = SimpleNamespace(
        _canonical_platform=normalize_namespace,
        _resolve_platform_identifier=normalize_namespace,
    )
    scopes = {"meta": "meta-test", "tiktok": "tiktok-test"}
    context = {"_agent_read_account_scopes": scopes}
    for namespace, expected in (("meta", "meta-test"), ("tiktok", "tiktok-test"), ("google-ads", None)):
        tool = ToolDefinition(
            name="query", namespace=namespace, skill="test", description="Query",
            action="get", resource_type="campaign", input_schema=ToolSchema(),
        )
        session = SimpleNamespace(ctx=ToolContext(session_id="s", user_id="operator"))
        executor = AdvertisingToolExecutor(owner, tool)
        assert executor._request_account(context, {}, session) == expected


def test_read_account_candidates_are_principal_filtered_and_bounded():
    owner = SimpleNamespace(
        registry=SimpleNamespace(list_all_namespaces=lambda: ["meta", "tiktok"]),
        _available_accounts_for_request=lambda namespace, scope: [
            value for value in ("allowed-a", "allowed-b", "outside")
            if value in scope.get(namespace, ())
        ],
    )
    request = SimpleNamespace(principal=SimpleNamespace(
        account_scope={"meta": {"allowed-a", "allowed-b"}, "tiktok": set()},
    ))
    candidates = AdvertisingCapabilityCatalog(owner).read_account_candidates(
        request, max_accounts=1,
    )
    assert candidates == {"meta": ["allowed-a"]}
    assert AdvertisingCapabilityCatalog(owner).read_account_candidates(
        SimpleNamespace(principal=None),
    ) == {}


def test_unprefilled_long_tiktok_conversation_keeps_ad_tools_with_all_channels_registered(tmp_path):
    provider = QueryClient("tiktok")
    runtime = _runtime(tmp_path, "tiktok", provider)
    for namespace in ("google-ads", "meta"):
        runtime.register_tool_source(create_tool_source(namespace))
    turns = [
        call("tiktok_list_campaigns", {"account_id": "test-account"}),
        call("tiktok_get_campaign", {"campaign_id": "101"}),
        call("tiktok_list_adgroups", {"campaign_id": "101"}),
        call("tiktok_list_ads", {"adgroup_id": "201"}),
    ]
    install(runtime, *[
        turn for tool_call in turns
        for turn in (
            ModelTurn(tool_calls=(tool_call,)),
            ModelTurn(content="Query completed."),
        )
    ])
    try:
        with _chat_client(runtime, _principal("tiktok")) as client:
            for text in (
                "查询 TikTok campaign 列表",
                "查询 campaign 101 的详情",
                "列出 campaign 101 下的广告组列表",
                "列出广告组 201 下的 ad 列表",
            ):
                result = _prompt(client, text, endpoint="/chat/stream")
                assert result["status"] == "succeeded", result
                runtime._sessions.clear()
        assert provider.calls[-1] == ("ads", "test-account", "201")
    finally:
        _close(runtime)


@pytest.mark.parametrize("requested,expected_status,expected_calls", [
    (["test-account"], "succeeded", [["test-account"]]),
    (["outside"], "failed", []),
])
def test_tiktok_directory_validates_plural_scope_without_a_selected_http_account(
    tmp_path, requested, expected_status, expected_calls,
):
    class TikTokDirectoryClient(QueryClient):
        def list_accounts(self, advertiser_ids):
            self.calls.append(advertiser_ids)
            return [{"advertiser_id": value, "name": "Test"} for value in advertiser_ids]

    provider = TikTokDirectoryClient("tiktok")
    runtime = _runtime(tmp_path, "tiktok", provider)
    install(
        runtime,
        ModelTurn(tool_calls=(call("tiktok_list_accounts", {"advertiser_ids": requested}),)),
        ModelTurn(content="Accounts."),
    )
    try:
        with _chat_client(runtime, _principal("tiktok")) as client:
            result = _prompt(client, "帮我列出 TikTok 账户", endpoint="/chat/stream")
        assert result["status"] == expected_status, result
        assert provider.calls == expected_calls
        assert not runtime._sessions["page-conversation"].ctx.metadata.get("read_account_scopes")
    finally:
        _close(runtime)


@pytest.mark.parametrize("endpoint", ["/chat", "/chat/stream"])
def test_model_rate_limit_has_a_readable_failure_instead_of_empty_content(tmp_path, endpoint):
    class RateLimitError(RuntimeError):
        pass

    class LimitedModel:
        def complete(self, *_args):
            raise RateLimitError("private provider diagnostics must not be shown")

    runtime = _runtime(tmp_path, client=QueryClient("meta"))
    runtime.platform_application.agent.model = LimitedModel()
    try:
        with _chat_client(runtime, _principal()) as client:
            result = _prompt(client, "查询 Meta campaign 列表", endpoint=endpoint)
        assert result["status"] == "failed", result
        content = result.get("content") or result.get("reply")
        assert "限流" in content
        assert "没有数据" in content
        assert "private provider" not in content
        assert result["error"] == "RateLimitError"
    finally:
        _close(runtime)


@pytest.mark.parametrize("scope_fields,arguments,expected", [
    ([], {"account_id": "test-account"}, "test-account"),
    ([], {"customer_id": "test-account"}, "test-account"),
    (["workspace_id"], {"workspace_id": "workspace"}, "workspace"),
    (["workspace_id"], {"account_id": "test-account"}, None),
])
def test_policy_and_executor_resolve_the_same_model_scope(scope_fields, arguments, expected):
    owner = SimpleNamespace(
        _canonical_platform=normalize_namespace,
        _resolve_platform_identifier=normalize_namespace,
    )
    tool = ToolDefinition(
        name="query", namespace="custom", skill="custom", description="Query",
        action="list", resource_type="campaign", scope_fields=scope_fields,
        input_schema=ToolSchema(),
    )
    session = SimpleNamespace(ctx=ToolContext(session_id="s", user_id="operator"))
    factory = AdvertisingToolPolicyFactory(owner)
    executor = AdvertisingToolExecutor(owner, tool)
    request_account, argument_account = factory._accounts_for_call(
        tool, "custom", arguments, {},
    )
    assert (request_account or argument_account) == expected
    assert executor._request_account({}, arguments, session) == expected


def test_multi_namespace_execution_does_not_use_an_unscoped_global_account():
    owner = SimpleNamespace(
        _canonical_platform=normalize_namespace,
        _resolve_platform_identifier=normalize_namespace,
    )
    tool = ToolDefinition(
        name="query", namespace="meta", skill="meta", description="Query",
        action="list", resource_type="campaign", input_schema=ToolSchema(),
    )
    session = SimpleNamespace(
        ctx=ToolContext(session_id="s", user_id="operator", account_id="wrong-global"),
    )
    context = {
        "account_id": "wrong-global",
        "platform_params": {"meta": {}, "tiktok": {}},
    }
    executor = AdvertisingToolExecutor(owner, tool)
    assert executor._request_account(context, {"account_id": "test-account"}, session) == (
        "test-account"
    )


def test_remembered_read_account_is_not_authority_or_write_selection(tmp_path):
    provider = QueryClient("meta")
    runtime = _runtime(tmp_path, client=provider)
    try:
        install(
            runtime,
            ModelTurn(tool_calls=(call("meta_list_campaigns", {"account_id": "test-account"}),)),
            ModelTurn(content="Listed."),
        )
        runtime.run("查询 Meta campaign 列表", session_id="s", principal=_principal())
        request_context = {
            "_agent_read_account_scopes": {"meta": "test-account"},
        }
        policy = AdvertisingToolPolicyFactory(runtime)
        read, _ = runtime.registry.get("meta_get_campaign")
        write, _ = runtime.registry.get("meta_create_campaign")
        request = SimpleNamespace(
            context=request_context,
            principal=_principal(accounts=("second-account",)),
            execution_mode="dry_run",
        )
        assert policy._account_scope_error(
            read, request, {"campaign_id": "101"}, "meta", request_context,
        )[0] == "scope_denied"
        assert policy._accounts_for_call(
            write, "meta", {"name": "test"}, request_context,
        ) == (None, None)
        assert policy._accounts_for_call(
            read, "meta", {"account_id": "second-account"}, request_context,
        ) == (None, "second-account")
    finally:
        _close(runtime)
