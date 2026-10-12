from types import SimpleNamespace

from agents.agent_harness.core.interfaces import ToolContext, ToolResult
from agents.applications.advertising.execution.input_builder import ToolInputBuilder
from agents.tools.advertising.providers.source_factory import create_tool_source
from agents.tools.advertising.providers.google import create_google_tool_source


class _SelectionSigner:
    def issue(self, **_kwargs):
        return "signed-selection", 1_800_000_000


def test_google_asset_lookup_decorates_union_typed_selection_fields():
    definitions = [
        definition
        for definition, _handler in create_google_tool_source().register_tools()
    ]
    services = SimpleNamespace(
        registry=SimpleNamespace(list_all=lambda: definitions),
        selection_signer=_SelectionSigner(),
    )
    builder = ToolInputBuilder(
        services,
        scope_value_resolver=lambda context: context.account_id,
    )
    asset_tool = next(
        definition for definition in definitions
        if definition.name == "google_list_assets"
    )
    result = ToolResult.ok({
        "assets": [{"id": "asset-1", "name": "Logo", "type": "IMAGE"}],
        "data_status": "live",
    })

    decorated = builder.parameter_selection.decorate_lookup_result(
        asset_tool,
        result,
        ToolContext(
            session_id="asset-picker",
            user_id="test-user",
            scope={"account_id": "google-test-account"},
        ),
        "google-ads",
    )

    selection = next(
        item for item in decorated.data["parameter_selections"]
        if item["tool_name"] == "google_create_demand_gen_carousel_ad"
        and item["field"] == "logo_image"
    )
    assert selection["options"] == [{
        "value": "asset-1",
        "label": "Logo",
        "selection_token": "signed-selection",
    }]


def test_creation_blueprint_does_not_project_campaign_budget_into_meta_adset():
    definitions = {
        binding.definition.name: binding.definition
        for binding in create_tool_source("meta").list_bindings()
    }
    services = SimpleNamespace(
        normalize_namespace=lambda namespace: str(namespace).lower(),
        is_dry_run=lambda: False,
    )
    builder = ToolInputBuilder(services)
    intent = SimpleNamespace(
        intent_type="create_campaign",
        attributes={},
        metadata={"creation_blueprint_id": "meta.traffic_link"},
        scoped_parameters={
            "meta": {
                "daily_budget": 1,
                "meta_create_campaign": {
                    "account_id": "2806375919473667",
                    "name": "QA_TEMPLATE_CAMPAIGN",
                    "objective": "OUTCOME_TRAFFIC",
                    "special_ad_categories": ["NONE"],
                    "buying_type": "AUCTION",
                    "daily_budget": 1,
                    "status": "PAUSED",
                },
                "meta_create_adset": {
                    "campaign_id": "__planned_campaign_id__",
                    "name": "QA_TEMPLATE_ADSET",
                    "optimization_goal": "LANDING_PAGE_VIEWS",
                    "billing_event": "IMPRESSIONS",
                    "targeting": {"geo_locations": {"countries": ["US"]}},
                    "status": "PAUSED",
                },
                "meta_create_traffic_ad": {
                    "name": "QA_TEMPLATE_AD",
                    "page_id": "test-page",
                    "link": "https://example.test",
                    "media_type": "IMAGE",
                    "image_hash": "test-image",
                },
            }
        },
    )

    campaign = builder.build(
        definitions["meta_create_campaign"], intent, "meta",
    )
    adset = builder.build(
        definitions["meta_create_adset"], intent, "meta",
    )
    ad = builder.build(
        definitions["meta_create_traffic_ad"], intent, "meta",
    )

    assert campaign["daily_budget"] == 1
    assert "daily_budget" not in adset
    assert "daily_budget" not in ad


def test_standalone_tool_still_accepts_provider_level_parameters():
    definition = next(
        binding.definition
        for binding in create_tool_source("meta").list_bindings()
        if binding.definition.name == "meta_create_campaign"
    )
    builder = ToolInputBuilder(SimpleNamespace(
        normalize_namespace=lambda namespace: str(namespace).lower(),
        is_dry_run=lambda: False,
    ))
    intent = SimpleNamespace(
        intent_type="create_campaign",
        attributes={},
        metadata={},
        scoped_parameters={"meta": {"daily_budget": 1}},
    )

    result = builder.build(definition, intent, "meta")

    assert result["daily_budget"] == 1
