from pathlib import Path
from types import SimpleNamespace

from agents.agent_harness.core.tool_registry import SimpleToolRegistry
from agents.agent_platform.tools.policy import ToolExecutionPolicy
from agents.applications.advertising.composition.ad_application_assembly import (
    _select_blueprint_tools,
)
from agents.applications.advertising.execution.ad_tool_policy_factory import (
    AdvertisingToolPolicyFactory,
)
from agents.applications.advertising.persistence.errors import PersistenceError
from agents.tools.advertising.providers.source_factory import create_tool_source
from agents.tools.advertising.providers.tiktok import create_tiktok_tool_source
from agents.tools.advertising.shared.domain.blueprint import load_blueprint_file
from agents.tools.advertising.shared.domain.creation_card import CreationCardBuilder


ROOT = Path(__file__).resolve().parents[3]
BLUEPRINT = load_blueprint_file(
    ROOT
    / "agents"
    / "tools"
    / "advertising"
    / "providers"
    / "meta"
    / "blueprints"
    / "traffic_link.v1.json"
)
TEST_ACCOUNT = "2806375919473667"
TIKTOK_BLUEPRINT = load_blueprint_file(
    ROOT
    / "agents"
    / "tools"
    / "advertising"
    / "providers"
    / "tiktok"
    / "blueprints"
    / "product_sales_video.v1.json"
)


class _Security:
    @staticmethod
    def validate_input_redline(_arguments):
        return []


class _BlueprintRegistry:
    @staticmethod
    def get(blueprint_id, version=None):
        if blueprint_id != BLUEPRINT.blueprint_id:
            return None
        if version and version != BLUEPRINT.version:
            return None
        return BLUEPRINT


class _TemplateManager:
    live_create_supported = True

    @staticmethod
    def get(*_args, **_kwargs):
        return {
            "template_id": "builtin-meta-traffic",
            "status": "active",
            "provider": "meta",
            "blueprint_id": BLUEPRINT.blueprint_id,
            "blueprint_version": BLUEPRINT.version,
            "account_id": TEST_ACCOUNT,
            "live_create_supported": _TemplateManager.live_create_supported,
            "live_create_block_reason": "当前模板不能执行完整暂停层级的 live 创建",
        }


def _factory():
    card_tools = SimpleToolRegistry()
    card_tools.register_source(create_tool_source("meta"))
    card_builder = CreationCardBuilder(_BlueprintRegistry(), card_tools)
    runtime = SimpleNamespace(
        _granted_permissions=frozenset({"ads.read", "ads.plan", "ads.write"}),
        _live_approved_tools=frozenset(),
        allow_live_writes=False,
        write_guard=None,
        enforce_account_scope=True,
        security=_Security(),
        policy_engine=ToolExecutionPolicy(),
        creation_blueprints=_BlueprintRegistry(),
        creation_card_builder=card_builder,
        registry=SimpleNamespace(list_all=lambda: []),
        _canonical_platform=lambda value: str(value).lower(),
        _resolve_platform_identifier=lambda value: str(value).lower(),
        _validate_account_for_tool=lambda *_args: (True, ""),
        _creation_template_manager_for_request=lambda *_args: _TemplateManager(),
        _parent_resource_id_field_for_tool=lambda tool: (
            {
                "meta_create_adset": "campaign_id",
                "meta_create_traffic_ad": "adset_id",
            }.get(tool.name)
        ),
    )
    factory = AdvertisingToolPolicyFactory(runtime)
    factory.interactions = SimpleNamespace(
        creation_input_required=lambda _context: False,
    )
    return factory


def _adset_tool():
    return next(
        binding.definition
        for binding in create_tool_source("meta").list_bindings()
        if binding.definition.name == "meta_create_adset"
    )


def _campaign_tool():
    return next(
        binding.definition
        for binding in create_tool_source("meta").list_bindings()
        if binding.definition.name == "meta_create_campaign"
    )


def _traffic_ad_tool():
    return next(
        binding.definition
        for binding in create_tool_source("meta").list_bindings()
        if binding.definition.name == "meta_create_traffic_ad"
    )


def _request(context, *, execution_mode="dry_run"):
    return SimpleNamespace(
        context={"account_id": TEST_ACCOUNT, **context},
        execution_mode=execution_mode,
        principal=SimpleNamespace(
            account_scope=None,
            permissions=frozenset({"ads.read", "ads.plan", "ads.write"}),
        ),
        tenant_id="test-tenant",
        user_id="test-user",
        session_id="test-session",
    )


def _valid_adset_arguments():
    return {
        "campaign_id": "campaign-test-id",
        "name": "QA_TEMPLATE_ADSET",
        "optimization_goal": "LANDING_PAGE_VIEWS",
        "billing_event": "IMPRESSIONS",
        "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
        "start_time": "2026-10-13T00:00:00+08:00",
        "end_time": "2026-10-20T00:00:00+08:00",
        "targeting": {"geo_locations": {"countries": ["US"]}},
        "status": "PAUSED",
    }


def test_selected_blueprint_blocks_nested_fields_owned_by_another_tool():
    arguments = {
        **_valid_adset_arguments(),
        "campaign": {"daily_budget": 1},
    }

    result = _factory().check_scope_and_confirmation(
        _adset_tool(),
        _request({"creation_blueprint_id": BLUEPRINT.blueprint_id}),
        arguments,
    )

    assert result is not None
    assert result[0] == "creation_input_required"
    assert "campaign" in result[1]


def test_template_accepts_schema_fields_exposed_by_the_creation_card():
    factory = _factory()
    expanded = factory.runtime.creation_card_builder.expand_blueprint(BLUEPRINT)
    assert any(
        field.get("tool_ref") == "meta_create_campaign.bid_strategy"
        for field in expanded.fields
    )
    arguments = {
        "account_id": TEST_ACCOUNT,
        "name": "QA_TEMPLATE_CAMPAIGN",
        "objective": "OUTCOME_TRAFFIC",
        "special_ad_categories": ["NONE"],
        "buying_type": "AUCTION",
        "daily_budget": 1000,
        "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
        "status": "PAUSED",
    }

    result = factory.check_scope_and_confirmation(
        _campaign_tool(),
        _request({
            "creation_blueprint_id": BLUEPRINT.blueprint_id,
            "creation_template_id": "builtin-meta-traffic",
        }),
        arguments,
    )

    assert result is None


def test_blueprint_fields_parent_reference_and_paused_status_are_allowed():
    result = _factory().check_scope_and_confirmation(
        _adset_tool(),
        _request({"creation_blueprint_id": BLUEPRINT.blueprint_id}),
        _valid_adset_arguments(),
    )

    assert result is None


def test_template_only_request_resolves_its_blueprint_before_tool_validation():
    result = _factory().check_scope_and_confirmation(
        _adset_tool(),
        _request({"creation_template_id": "builtin-meta-traffic"}),
        {**_valid_adset_arguments(), "campaign": {"daily_budget": 1}},
    )

    assert result is not None
    assert result[0] == "creation_input_required"
    assert "campaign" in result[1]


def test_provider_limited_template_blocks_live_create_before_provider_writes(monkeypatch):
    monkeypatch.setattr(_TemplateManager, "live_create_supported", False)
    factory = _factory()
    factory.runtime.allow_live_writes = True
    factory.runtime.write_guard = object()

    result = factory.check_scope_and_confirmation(
        _campaign_tool(),
        _request({
            "creation_blueprint_id": BLUEPRINT.blueprint_id,
            "creation_template_id": "builtin-meta-traffic",
        }, execution_mode="live"),
        {"account_id": TEST_ACCOUNT, "name": "QA campaign", "status": "PAUSED"},
    )

    assert result is not None
    assert result[0] == "creation_input_required"
    assert "不能执行完整暂停层级的 live 创建" in result[1]


def test_template_store_failure_fails_closed_before_creation():
    factory = _factory()

    def unavailable(_scope):
        raise PersistenceError("store unavailable")

    factory.runtime._creation_template_manager_for_request = unavailable
    result = factory.check_scope_and_confirmation(
        _adset_tool(),
        _request({"creation_template_id": "builtin-meta-traffic"}),
        _valid_adset_arguments(),
    )

    assert result is not None
    assert result[0] == "creation_input_required"
    assert "模板存储暂不可用" in result[1]


def test_traffic_blueprint_allows_optional_copy_and_call_to_action_fields():
    arguments = {
        "adset_id": "adset-test-id",
        "name": "QA_TEMPLATE_TRAFFIC_AD",
        "page_id": "page-test-id",
        "link": "https://example.com/",
        "media_type": "IMAGE",
        "image_hash": "image-hash-test",
        "message": "Paused QA test creative.",
        "headline": "Template verification",
        "description": "Optional template-backed description.",
        "call_to_action_type": "LEARN_MORE",
        "status": "PAUSED",
    }

    result = _factory().check_scope_and_confirmation(
        _traffic_ad_tool(),
        _request({"creation_blueprint_id": BLUEPRINT.blueprint_id}),
        arguments,
    )

    assert result is None


def test_selected_blueprint_confirmation_only_includes_its_registered_write_tools():
    factory = _factory()
    registry = SimpleToolRegistry()
    registry.register_source(create_tool_source("meta"))
    factory.runtime.registry = registry
    factory.runtime.security = SimpleNamespace(
        confirmation_chain_plan=lambda *_args, **kwargs: {"preview": kwargs["preview"]},
        prepare_confirmation=lambda expected, **_kwargs: expected,
    )
    request = _request({"creation_blueprint_id": BLUEPRINT.blueprint_id})
    context = SimpleNamespace(request=request)
    confirmation = factory.build_confirmation(
        context, _campaign_tool(), {"name": "Demo", "status": "PAUSED"},
    )
    assert set(confirmation["preview"]["tools"]) == set(BLUEPRINT.tools)
    assert "meta_create_conversion_ad" not in confirmation["preview"]["tools"]


def test_tiktok_template_context_excludes_web_search_from_creation_tools():
    class Blueprints:
        @staticmethod
        def get(blueprint_id, version=None):
            if blueprint_id != TIKTOK_BLUEPRINT.blueprint_id:
                return None
            if version and version != TIKTOK_BLUEPRINT.version:
                return None
            return TIKTOK_BLUEPRINT

    tools = [
        binding.definition
        for binding in create_tiktok_tool_source().list_bindings()
    ]
    tools.append(SimpleNamespace(
        name="agent_web_search",
        namespace="web",
        action="search",
        is_write_tool=False,
    ))
    runtime = SimpleNamespace(
        creation_blueprints=Blueprints(),
        _canonical_platform=lambda value: str(value or "").lower(),
    )

    selected = _select_blueprint_tools(
        runtime,
        {
            "creation_blueprint_id": TIKTOK_BLUEPRINT.blueprint_id,
            "creation_blueprint_version": TIKTOK_BLUEPRINT.version,
            "creation_template_id": "tiktok.test.sales",
        },
        tools,
    )

    assert {tool.name for tool in selected} == set(TIKTOK_BLUEPRINT.tools)
    assert "agent_web_search" not in {tool.name for tool in selected}
