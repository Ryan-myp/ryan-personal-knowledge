import pytest

from agents.agent_harness.core.interfaces import ToolContext
from agents.tools.advertising.clients.meta_client import MetaAPIClient
from agents.tools.advertising.providers.meta.campaigns import (
    MetaGetCampaignHandler,
    MetaListCampaignsHandler,
)


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


def test_campaign_detail_maps_generic_end_time_to_meta_stop_time():
    client = MetaAPIClient({"access_token": "fixture"})
    calls = []
    client.request = lambda method, endpoint, **kwargs: (
        calls.append((method, endpoint, kwargs))
        or {"id": "456", "name": "QA", "stop_time": "2026-10-31T23:59:00+0000"}
    )

    result = client.get_campaign(
        "456",
        fields=["id", "name", "end_time", "stop_time", "status"],
    )

    fields = calls[0][2]["extra_params"]["fields"].split(",")
    assert fields == ["id", "name", "stop_time", "status"]
    assert "end_time" not in fields
    assert result["stop_time"] == "2026-10-31T23:59:00+0000"


def test_campaign_detail_default_fields_use_meta_stop_time():
    client = MetaAPIClient({"access_token": "fixture"})
    calls = []
    client.request = lambda method, endpoint, **kwargs: (
        calls.append((method, endpoint, kwargs)) or {"id": "456"}
    )

    client.get_campaign("456")

    fields = calls[0][2]["extra_params"]["fields"].split(",")
    assert "stop_time" in fields
    assert "end_time" not in fields


def test_campaign_detail_rejects_unsupported_field_before_graph_request():
    client = MetaAPIClient({"access_token": "fixture"})
    client.request = lambda *_args, **_kwargs: pytest.fail("invalid field reached Graph")

    with pytest.raises(ValueError, match="Unsupported Meta Campaign fields"):
        client.get_campaign("456", fields=["id", "is_active"])


def test_campaign_detail_tool_fields_match_provider_contract():
    from agents.tools.advertising.providers.meta import create_meta_tool_source

    definition = next(
        binding.definition
        for binding in create_meta_tool_source(None).list_bindings()
        if binding.definition.name == "meta_get_campaign"
    )
    allowed = definition.input_schema.properties["fields"]["items"]["enum"]
    assert "stop_time" in allowed
    assert "is_active" not in allowed


def test_campaign_selection_queries_exact_id_without_scanning_account_edge():
    class Client(MetaAPIClient):
        def __init__(self):
            super().__init__({"access_token": "fixture"})

        def list_campaigns(self, *_args, **_kwargs):
            pytest.fail("exact lookup must not scan the Campaign edge")

        def resource_belongs_to_account(self, account_id, resource_type, resource_id):
            return (account_id, resource_type, resource_id) == ("123", "campaign", "456")

        def get_campaign(self, campaign_id, fields=None):
            return {"id": campaign_id, "name": "Exact Campaign", "status": "PAUSED"}

    handler = MetaListCampaignsHandler(Client())
    result = handler.execute(
        ToolContext(session_id="qa", user_id="qa", account_id="123"),
        {"campaign_id": "456", "limit": 1000},
    )
    assert result.success is True
    assert [row["id"] for row in result.data["campaigns"]] == ["456"]
    assert handler.execute(
        ToolContext(session_id="qa", user_id="qa", account_id="999"),
        {"campaign_id": "456"},
    ).success is False


def test_campaign_selection_declares_exact_lookup_query():
    from agents.tools.advertising.providers.meta import create_meta_tool_source

    definition = next(
        binding.definition
        for binding in create_meta_tool_source(None).list_bindings()
        if binding.definition.name == "meta_update_campaign"
    )
    assert definition.input_schema.properties["campaign_id"]["lookup_query_field"] == "campaign_id"


def test_ad_detail_rejects_campaign_only_fields_before_graph_request():
    client = MetaAPIClient({"access_token": "fixture"})
    client.request = lambda *_args, **_kwargs: pytest.fail("invalid field reached Graph")

    with pytest.raises(ValueError, match="Unsupported Meta Ad fields"):
        client.get_ad("456", fields=["id", "promoted_object"])


def test_ad_detail_tool_fields_match_provider_contract():
    from agents.tools.advertising.providers.meta import create_meta_tool_source

    definition = next(
        binding.definition
        for binding in create_meta_tool_source(None).list_bindings()
        if binding.definition.name == "meta_get_ad"
    )
    allowed = definition.input_schema.properties["fields"]["items"]["enum"]
    assert "creative" in allowed
    assert "promoted_object" not in allowed


def test_adset_detail_rejects_alias_field_before_graph_request():
    client = MetaAPIClient({"access_token": "fixture"})
    client.request = lambda *_args, **_kwargs: pytest.fail("invalid field reached Graph")

    with pytest.raises(ValueError, match="Unsupported Meta Ad Set fields"):
        client.get_adset("456", fields=["id", "adset_name"])


def test_adset_detail_tool_fields_match_provider_contract():
    from agents.tools.advertising.providers.meta import create_meta_tool_source

    definition = next(
        binding.definition
        for binding in create_meta_tool_source(None).list_bindings()
        if binding.definition.name == "meta_get_adset"
    )
    allowed = definition.input_schema.properties["fields"]["items"]["enum"]
    assert "name" in allowed
    assert "adset_name" not in allowed


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


@pytest.mark.parametrize("failure", ["temporary", "rate_limit", "auth"])
def test_account_ownership_does_not_scan_account_on_provider_failure(failure):
    from agents.tools.advertising.clients.base import (
        AuthError, RateLimitError, TemporaryError,
    )

    client = MetaAPIClient({"access_token": "fixture"})
    errors = {
        "temporary": TemporaryError("upstream 504"),
        "rate_limit": RateLimitError("upstream 429"),
        "auth": AuthError("upstream 401"),
    }
    calls = []

    def failing_request(method, endpoint, **kwargs):
        calls.append(endpoint)
        raise errors[failure]

    client.request = failing_request
    client.list_campaigns = lambda *_args, **_kwargs: pytest.fail(
        "transient and authorization failures must not scan the account"
    )
    with pytest.raises(type(errors[failure])):
        client.resource_belongs_to_account("123", "campaign", "456")
    assert calls == ["/456"]


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
