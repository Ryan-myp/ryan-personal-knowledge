import pytest

from agents.agent_harness.core.interfaces import ToolContext
from agents.tools.advertising.clients.meta_client import MetaAPIClient
from agents.tools.advertising.providers.meta.campaigns import MetaGetCampaignHandler


def test_exact_name_lookup_uses_provider_filter_instead_of_first_account_page():
    client = MetaAPIClient({"access_token": "fixture"})
    calls = []
    client.request = lambda method, endpoint, **kwargs: (
        calls.append((method, endpoint, kwargs))
        or {"data": [{"id": "456", "name": "Unique QA"}]}
    )
    assert client.find_campaigns_by_name("123", "Unique QA") == [
        {"id": "456", "name": "Unique QA"}
    ]
    assert calls[0][2]["extra_params"]["filtering"] == (
        '[{"field": "name", "operator": "EQUAL", "value": "Unique QA"}]'
    )
    assert calls[0][2]["extra_params"]["limit"] == 2


def test_name_lookup_rejects_partial_matches_and_ambiguous_exact_names():
    class Client:
        def list_campaigns(self, account_id, limit=25):
            return [
                {"id": "1", "name": "QA"},
                {"id": "2", "name": "Unique QA"},
                {"id": "3", "name": "Unique QA"},
            ]

        def get_campaign(self, campaign_id):
            raise AssertionError("must not select an ambiguous campaign")

    result = MetaGetCampaignHandler(Client()).execute(
        ToolContext(session_id="qa", user_id="qa", account_id="123"),
        {"campaign_name": "Unique QA"},
    )
    assert result.success is False
    assert "多个" in result.error


def test_name_lookup_never_accepts_substring_as_unknown_write_reconciliation():
    class Client:
        def list_campaigns(self, account_id, limit=25):
            return [{"id": "1", "name": "QA"}]

    result = MetaGetCampaignHandler(Client()).execute(
        ToolContext(session_id="qa", user_id="qa", account_id="123"),
        {"campaign_name": "QA new campaign"},
    )
    assert result.success is False


def test_budgeted_campaign_declares_and_sends_its_bid_strategy():
    from agents.tools.advertising.providers.meta.parameters import meta_campaign_schema
    from agents.tools.advertising.providers.update_contracts import meta_updates

    assert "bid_strategy" in meta_campaign_schema()["properties"]
    assert "bid_strategy" in meta_updates("campaign")["properties"]
    client = MetaAPIClient({"access_token": "fixture"})
    result = client.create_campaign(
        "123",
        {
            "name": "QA",
            "objective": "OUTCOME_TRAFFIC",
            "daily_budget": 10,
            "special_ad_categories": ["NONE"],
            "status": "PAUSED",
            "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
        },
    )
    data = result["operation"]["/act_123/campaigns"]["create"]
    assert data["bid_strategy"] == "LOWEST_COST_WITHOUT_CAP"


@pytest.mark.parametrize("kind", ["campaign", "ad_set", "ad", "creative"])
@pytest.mark.parametrize("owner,expected", [("123", True), ("999", False)])
def test_account_ownership_is_checked_on_the_exact_node(kind, owner, expected):
    client = MetaAPIClient({"access_token": "fixture"})
    calls = []
    client.request = lambda method, endpoint, **kwargs: (
        calls.append((method, endpoint, kwargs)) or {"id": "456", "account_id": owner}
    )
    assert client.resource_belongs_to_account("act_123", kind, "456") is expected
    assert len(calls) == 1
    assert calls[0][1] == "/456"


def test_ad_readback_includes_campaign_and_creative_relationships():
    client = MetaAPIClient({"access_token": "fixture"})
    calls = []
    client.request = lambda method, endpoint, **kwargs: (
        calls.append(kwargs) or {"id": "456", "campaign_id": "234", "creative": {"id": "789"}}
    )
    result = client.get_ad("456")
    fields = calls[0]["extra_params"]["fields"].split(",")
    assert "creative" in fields
    assert "campaign_id" in fields
    assert result["creative"]["id"] == "789"
