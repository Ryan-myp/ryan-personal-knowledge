import pytest

from agents.tools.advertising.clients.tiktok_client import TikTokAPIClient


def test_live_ad_cannot_override_paused_status_with_enabled_wire_status():
    client = TikTokAPIClient({"access_token": "fixture"})
    calls = []
    client.request = lambda *args, **kwargs: (
        calls.append((args, kwargs)) or {"code": 0, "data": {"ad_id": "456"}}
    )
    with pytest.raises(ValueError, match="paused"):
        client.create_ad(
            "123",
            "234",
            "345",
            {
                "name": "QA",
                "status": 0,
                "operation_status": "ENABLE",
            },
            live=True,
        )
    assert calls == []


def test_no_bid_adgroup_defaults_to_smooth_delivery():
    client = TikTokAPIClient({"access_token": "fixture"})
    plan = client.create_adgroup("123", "234", {
        "name": "QA", "bid_type": "BID_TYPE_NO_BID", "status": 0,
    })
    assert plan["operation"]["adgroup/create/"]["pacing"] == "PACING_MODE_SMOOTH"


def test_no_bid_adgroup_cannot_request_accelerated_delivery():
    client = TikTokAPIClient({"access_token": "fixture"})
    client.request = lambda *_args, **_kwargs: pytest.fail("invalid input must not reach transport")
    with pytest.raises(ValueError, match="No-Bid"):
        client.create_adgroup("123", "234", {
            "name": "QA", "bid_type": "BID_TYPE_NO_BID", "pacing": "PACING_MODE_FAST", "status": 0,
        }, live=True)


def test_no_bid_pacing_constraint_is_published_in_tool_schema():
    from agents.agent_harness.core.interfaces import ToolSchema
    from agents.agent_harness.core.tool_registry import validate_tool_input
    from agents.tools.advertising.providers.tiktok.parameters import tiktok_adgroup_schema

    schema = ToolSchema(**tiktok_adgroup_schema())
    errors = validate_tool_input(schema, {
        "campaign_id": "234", "name": "QA", "promotion_type": "WEBSITE",
        "billing_event": "CPC", "budget_mode": "BUDGET_MODE_DAY", "budget": 50,
        "location_ids": ["1880251"], "placement_type": "PLACEMENT_TYPE_NORMAL",
        "bid_type": "BID_TYPE_NO_BID", "pacing": "PACING_MODE_FAST",
    })
    assert any("No-Bid" in error for error in errors)


def test_identity_lookup_supports_the_account_existing_bc_auth_type():
    from agents.tools.advertising.providers.tiktok.parameters import tiktok_identity_list_schema

    assert "BC_AUTH_TT" in tiktok_identity_list_schema()["properties"]["identity_type"]["enum"]
    client = TikTokAPIClient({"access_token": "fixture"})
    calls = []
    client.request = lambda method, endpoint, **kwargs: (
        calls.append(kwargs["params"]) or {"code": 0, "data": {"list": [{"identity_id": "identity"}]}}
    )
    assert client.list_identities("123", "BC_AUTH_TT")[0]["identity_id"] == "identity"
    assert calls[0]["identity_type"] == "BC_AUTH_TT"


def test_identity_lookup_reads_the_real_identity_list_envelope():
    client = TikTokAPIClient({"access_token": "fixture"})
    client.request = lambda *_args, **_kwargs: {
        "code": 0, "data": {"identity_list": [{"identity_id": "available"}], "page_info": {"total_number": 1}},
    }
    assert client.list_identities("123", "BC_AUTH_TT") == [{"identity_id": "available"}]


def test_live_bc_identity_is_bound_privately_from_account_scoped_lookup():
    client = TikTokAPIClient({"access_token": "fixture"})
    client.list_identities = lambda advertiser_id, identity_type, page_size: [{
        "identity_id": "identity", "identity_type": "BC_AUTH_TT",
        "available_status": "AVAILABLE", "identity_authorized_bc_id": "private-bc",
    }]
    calls = []
    client.request = lambda method, endpoint, **kwargs: (
        calls.append(kwargs["data"]) or {"code": 0, "data": {"ad_id": "456"}}
    )
    result = client.create_ad("123", "234", "345", {
        "name": "QA", "identity_type": "BC_AUTH_TT", "identity_id": "identity", "status": 0,
    }, live=True)
    assert result == "456"
    assert calls[0]["creatives"][0]["identity_authorized_bc_id"] == "private-bc"
    assert "private-bc" not in str(result)


def test_caller_cannot_supply_private_bc_authorization_in_advanced_creatives():
    client = TikTokAPIClient({"access_token": "fixture"})
    client.request = lambda *_args, **_kwargs: pytest.fail("must reject before transport")
    with pytest.raises(ValueError, match="privately"):
        client.create_ad("123", "234", "345", {
            "name": "QA", "identity_type": "BC_AUTH_TT", "identity_id": "identity",
            "creatives": [{"identity_authorized_bc_id": "caller-bc"}], "status": 0,
        }, live=True)
