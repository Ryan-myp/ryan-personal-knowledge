"""Focused contracts for Google reporting and keyword-planning reads."""

import pytest

from agents.agent_harness.core.interfaces import (
    ReplayPolicy,
    ToolContext,
    ToolEffect,
)
from agents.agent_harness.core.tool_registry import validate_tool_input
from agents.agent_harness.skills.contract import SkillLoader
from agents.tools.advertising.clients.google_ads_client import GoogleAdsAPIClient
from agents.tools.advertising.providers.google.provider import create_google_tool_source


def _tool_source_with(client):
    return {
        definition.name: (definition, handler)
        for definition, handler in create_google_tool_source(client).register_tools()
    }


def test_keyword_research_skill_is_discoverable_as_standard_advisory_context():
    skill = SkillLoader().load_skill_dir(
        "agents/skills/advertising/practices/keyword-research"
    )

    assert skill is not None
    assert skill.name == "keyword-research"
    assert skill.namespace == "advertising"
    assert not skill.tools


def test_google_ad_report_is_registered_as_bounded_read_tool():
    definition, _handler = _tool_source_with(None)["google_get_ad_report"]

    assert definition.action == "report"
    assert definition.resource_type == "ad"
    assert definition.effect_class == ToolEffect.READ
    assert definition.replay_policy == ReplayPolicy.SAFE
    assert definition.intent_types == ["get_ad_report"]
    assert definition.integration_api_version == "v24"
    assert definition.input_schema.required == ["campaign_id"]
    assert definition.input_schema.properties["limit"]["maximum"] == 10000


def test_google_asset_reports_are_registered_with_distinct_resource_contracts():
    tools = _tool_source_with(None)
    ad_asset, _ = tools["google_get_ad_asset_report"]
    pmax_asset, _ = tools["google_get_asset_group_asset_report"]

    assert ad_asset.action == "report"
    assert ad_asset.resource_type == "asset"
    assert ad_asset.effect_class == ToolEffect.READ
    assert ad_asset.replay_policy == ReplayPolicy.SAFE
    assert ad_asset.intent_types == ["get_ad_asset_report"]
    assert ad_asset.input_schema.required == ["campaign_id"]
    assert ad_asset.input_schema.properties["limit"]["maximum"] == 10000

    assert pmax_asset.action == "report"
    assert pmax_asset.resource_type == "asset_group_asset"
    assert pmax_asset.effect_class == ToolEffect.READ
    assert pmax_asset.replay_policy == ReplayPolicy.SAFE
    assert pmax_asset.intent_types == ["get_asset_group_asset_report"]
    assert pmax_asset.input_schema.required == ["campaign_id"]
    assert pmax_asset.input_schema.properties["asset_group_ids"]["maxItems"] == 100


def test_google_ad_asset_report_builds_scoped_gaql_and_rejects_unsafe_filters():
    client = GoogleAdsAPIClient({"access_token": "test"}, customer_id="123")
    calls = []

    def search_all(query, page_size):
        calls.append((query, page_size))
        return [{"asset": {"id": "88"}}]

    client._search_all = search_all
    rows = client.get_ad_asset_report(
        campaign_id="456",
        ad_group_ids=["12"],
        ad_ids=["34"],
        date_from="2026-10-01",
        date_to="2026-10-07",
        limit=30,
    )

    assert rows == [{"asset": {"id": "88"}}]
    query, limit = calls[0]
    assert "FROM ad_group_ad_asset_view" in query
    assert "campaign.id = 456" in query
    assert "ad_group.id IN (12)" in query
    assert "ad_group_ad.ad.id IN (34)" in query
    assert "segments.date BETWEEN '2026-10-01' AND '2026-10-07'" in query
    assert "asset.image_asset.full_size.url" in query
    assert "metrics.impressions" in query
    assert "metrics.clicks" in query
    assert "metrics.cost_micros" in query
    assert limit == 30

    with pytest.raises(ValueError, match="digits only"):
        client.get_ad_asset_report(campaign_id="456 OR 1=1")
    with pytest.raises(ValueError, match="report limit"):
        client.get_ad_asset_report(campaign_id="456", limit=10001)


def test_google_pmax_asset_group_asset_report_is_scoped_and_bounded():
    client = GoogleAdsAPIClient({"access_token": "test"}, customer_id="123")
    calls = []

    def search_all(query, page_size):
        calls.append((query, page_size))
        return [{"assetGroupAsset": {"fieldType": "HEADLINE"}}]

    client._search_all = search_all
    rows = client.get_asset_group_asset_report(
        campaign_id="456",
        asset_group_ids=["78"],
        field_types=["HEADLINE", "MARKETING_IMAGE"],
        date_from="LAST_7_DAYS",
        date_to="TODAY",
        limit=50,
    )

    assert rows == [{"assetGroupAsset": {"fieldType": "HEADLINE"}}]
    query, limit = calls[0]
    assert "FROM asset_group_asset" in query
    assert "campaign.id = 456" in query
    assert "asset_group.id IN (78)" in query
    assert "asset_group_asset.field_type IN ('HEADLINE', 'MARKETING_IMAGE')" in query
    assert "asset_group_asset.performance_label" not in query
    assert "metrics.conversions, metrics.conversions_value" in query
    assert "metrics.impressions" not in query
    assert "metrics.clicks" not in query
    assert "metrics.cost_micros" not in query
    assert "segments.date DURING LAST_7_DAYS" in query
    assert limit == 50

    with pytest.raises(ValueError, match="field_types"):
        client.get_asset_group_asset_report(
            campaign_id="456", field_types=["HEADLINE' OR 1=1"]
        )
    with pytest.raises(ValueError, match="asset_group_id"):
        client.get_asset_group_asset_report(
            campaign_id="456", asset_group_ids=["78,79"]
        )


def test_google_keyword_ideas_is_registered_as_bounded_read_tool():
    definition, _handler = _tool_source_with(None)["google_generate_keyword_ideas"]

    assert definition.action == "search"
    assert definition.resource_type == "keyword_idea"
    assert definition.effect_class == ToolEffect.READ
    assert definition.replay_policy == ReplayPolicy.SAFE
    assert definition.intent_types == ["generate_keyword_ideas"]
    assert definition.integration_api_version == "v24"
    assert definition.input_schema.required == ["keywords"]
    assert definition.input_schema.properties["keywords"]["maxItems"] == 20
    assert definition.input_schema.properties["limit"]["maximum"] == 1000
    assert "customer_id" not in definition.input_schema.properties
    assert validate_tool_input(
        definition.input_schema,
        {
            "keywords": ["running shoes"],
            "geo_target_constants": ["geoTargetConstants/2840"],
            "language": "languageConstants/1000",
            "url": "https://example.com/shoes",
            "network": "GOOGLE_SEARCH",
            "limit": 100,
        },
    ) == []
    assert validate_tool_input(
        definition.input_schema,
        {"keywords": ["running shoes"], "network": "UNSUPPORTED_NETWORK"},
    )


def test_google_ad_report_builds_scoped_gaql_and_enforces_limit():
    client = GoogleAdsAPIClient({"access_token": "test"}, customer_id="123")
    calls = []

    def search_all(query, page_size):
        calls.append((query, page_size))
        return [{"adGroupAd": {"ad": {"id": "9"}}}]

    client._search_all = search_all
    rows = client.get_ad_report(
        campaign_id="1234",
        ad_group_ids=["56"],
        ad_ids=["9"],
        date_from="2026-10-01",
        date_to="2026-10-07",
        limit=25,
    )

    assert rows == [{"adGroupAd": {"ad": {"id": "9"}}}]
    query, limit = calls[0]
    assert "FROM ad_group_ad" in query
    assert "campaign.id = 1234" in query
    assert "ad_group.id IN (56)" in query
    assert "ad_group_ad.ad.id IN (9)" in query
    assert "segments.date BETWEEN '2026-10-01' AND '2026-10-07'" in query
    assert limit == 25

    with pytest.raises(ValueError, match="report limit"):
        client.get_ad_report(campaign_id="1234", limit=10001)
    with pytest.raises(ValueError, match="digits only"):
        client.get_ad_report(campaign_id="1234 OR 1=1")


def test_google_keyword_ideas_validates_inputs_and_normalizes_response():
    client = GoogleAdsAPIClient({"access_token": "test"}, customer_id="123")
    calls = []

    def request_raw(method, endpoint, **kwargs):
        calls.append((method, endpoint, kwargs))
        return {
            "status_code": 200,
            "data": {
                "results": [{
                    "text": "running shoes",
                    "keywordIdeaMetrics": {
                        "avgMonthlySearches": "12000",
                        "competition": "MEDIUM",
                        "competitionIndex": 47,
                        "lowTopOfPageBidMicros": "1200000",
                        "highTopOfPageBidMicros": "5400000",
                    },
                }],
                "nextPageToken": "next-page",
            },
            "headers": {},
        }

    client.request_raw = request_raw
    result = client.generate_keyword_ideas(
        ["running shoes"],
        geo_target_constants=["geoTargetConstants/2840"],
        language="languageConstants/1000",
        url="https://example.com/shoes",
        limit=50,
    )

    assert calls[0][0] == "POST"
    assert calls[0][1].endswith(
        "/customers/123:generateKeywordIdeas"
    )
    body = calls[0][2]["data"]
    assert body["keywordAndUrlSeed"] == {
        "keywords": ["running shoes"],
        "url": "https://example.com/shoes",
    }
    assert body["geoTargetConstants"] == ["geoTargetConstants/2840"]
    assert body["language"] == "languageConstants/1000"
    assert body["pageSize"] == 50
    assert result["ideas"] == [{
        "text": "running shoes",
        "average_monthly_searches": 12000,
        "competition": "MEDIUM",
        "competition_index": 47,
        "low_top_of_page_bid_micros": 1200000,
        "high_top_of_page_bid_micros": 5400000,
    }]
    assert result["next_page_token"] == "next-page"

    with pytest.raises(ValueError, match="between 1 and 20"):
        client.generate_keyword_ideas([""] * 21)
    with pytest.raises(ValueError, match="geoTargetConstants"):
        client.generate_keyword_ideas(
            ["shoes"], geo_target_constants=["geoTargetConstants/1 OR 1=1"]
        )
    with pytest.raises(ValueError, match="HTTP or HTTPS"):
        client.generate_keyword_ideas(["shoes"], url="javascript:alert(1)")


def test_google_keyword_ideas_tool_uses_run_account_and_live_provider_call():
    client = GoogleAdsAPIClient({"access_token": "test"}, customer_id="fallback")
    calls = []

    def request_raw(method, endpoint, **kwargs):
        calls.append((method, endpoint, kwargs))
        return {
            "status_code": 200,
            "data": {"results": [{"text": "running shoes"}]},
            "headers": {},
        }

    client.request_raw = request_raw
    _definition, handler = _tool_source_with(client)["google_generate_keyword_ideas"]

    result = handler.execute(
        ToolContext(
            session_id="keyword-ideas-test",
            user_id="qa",
            account_id="123456",
        ),
        {
            "keywords": ["running shoes"],
            "geo_target_constants": ["geoTargetConstants/2840"],
            "limit": 25,
        },
    )

    assert result.success is True
    assert calls[0][0] == "POST"
    assert calls[0][1].endswith("/customers/123456:generateKeywordIdeas")
    assert calls[0][2]["data"]["keywordSeed"]["keywords"] == ["running shoes"]
    assert calls[0][2]["data"]["geoTargetConstants"] == [
        "geoTargetConstants/2840"
    ]
    assert calls[0][2]["data"]["pageSize"] == 25
