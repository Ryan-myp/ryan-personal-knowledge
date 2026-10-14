"""Explicit App Ad enablement must never enable either delivery parent."""

import pytest

from agents.tools.advertising.clients.google_ads_client import GoogleAdsAPIClient
from agents.tools.advertising.providers.google import create_google_tool_source


def client_fixture(*, group_status="PAUSED", campaign_status="PAUSED", campaign_customer="123"):
    client = GoogleAdsAPIClient({"access_token": "test"}, customer_id="123")
    events = []
    row = {
        "adGroup": {
            "id": "77", "name": "App group", "status": group_status,
            "campaign": f"customers/{campaign_customer}/campaigns/99",
        },
        "campaign": {"id": "99", "status": campaign_status},
    }
    client._search = lambda query: (events.append(("read", query)) or {"results": [row]})
    client._mutate = lambda resource, operation: (
        events.append(("write", resource, operation)) or {
            "results": [{"resourceName": "customers/123/adGroupAds/77~88"}],
        }
    )
    return client, events, row


def create(client, **kwargs):
    return client.create_app_ad(
        "77", "Demo App Ad", ["Install now", "Shop in the app"],
        ["Fast checkout", "Download today"], **kwargs,
    )


def test_enabled_app_ad_creation_checks_both_paused_parents_in_one_read():
    client, events, _row = client_fixture()
    result = create(client, status="ENABLED", live=True)
    assert [event[0] for event in events] == ["read", "write"]
    assert "ad_group.campaign" in events[0][1]
    assert "campaign.status" in events[0][1]
    assert result["status"] == result["requested_status"] == "ENABLED"
    assert result["ad_resource_name"] == "customers/123/adGroupAds/77~88"
    assert result["delivery_guard"]["required_status"] == "PAUSED"
    assert result["delivery_guard"]["campaign_required_status"] == "PAUSED"
    assert result["delivery_guard"]["campaign_id"] == "99"
    assert events[1][1] == "adGroupAds"
    assert events[1][2]["create"]["status"] == "ENABLED"
    assert events[1][2]["create"]["adGroup"] == "customers/123/adGroups/77"
    assert "appAd" in events[1][2]["create"]["ad"]


@pytest.mark.parametrize("group_status", ["ENABLED", "REMOVED", None])
def test_app_ad_creation_refuses_an_active_or_unverified_ad_group(group_status):
    client, events, _row = client_fixture(group_status=group_status)
    with pytest.raises(ValueError, match="PAUSED.*Ad Group"):
        create(client, status="ENABLED", live=True)
    assert [event[0] for event in events] == ["read"]


@pytest.mark.parametrize("campaign_status", ["ENABLED", "REMOVED", None])
def test_app_ad_creation_refuses_an_active_or_unverified_campaign(campaign_status):
    client, events, _row = client_fixture(campaign_status=campaign_status)
    with pytest.raises(ValueError, match="PAUSED.*Campaign"):
        create(client, status="ENABLED", live=True)
    assert [event[0] for event in events] == ["read"]


def test_app_ad_creation_refuses_a_campaign_reference_from_another_account():
    client, events, _row = client_fixture(campaign_customer="999")
    with pytest.raises(ValueError, match="customer"):
        create(client, status="ENABLED", live=True)
    assert [event[0] for event in events] == ["read"]


def test_app_ad_creation_refuses_an_unverified_parent_relationship():
    client, events, row = client_fixture()
    row["campaign"]["id"] = "100"
    with pytest.raises(ValueError, match="Campaign"):
        create(client, status="ENABLED", live=True)
    assert [event[0] for event in events] == ["read"]


@pytest.mark.parametrize("status", [None, "", "PAUSED", "REMOVED"])
def test_app_ad_creation_does_not_silently_enable_a_missing_or_different_status(status):
    client, events, _row = client_fixture()
    with pytest.raises(ValueError, match="explicit ENABLED"):
        create(client, status=status, live=True)
    assert events == []


def test_app_ad_dry_run_discloses_enabled_ad_and_both_paused_parent_requirements():
    client, events, _row = client_fixture()
    plan = create(client, status="ENABLED", live=False)
    assert events == []
    assert plan["operation"]["adGroupAds"]["create"]["status"] == "ENABLED"
    assert plan["status"] == "ENABLED"
    assert plan["delivery_guard"]["required_status"] == "PAUSED"
    assert plan["delivery_guard"]["campaign_required_status"] == "PAUSED"


def test_app_ad_tool_requires_explicit_enabled_status():
    definition = next(
        binding.definition for binding in create_google_tool_source().list_bindings()
        if binding.definition.name == "google_create_app_ad"
    )
    assert "status" in definition.input_schema.required
    assert definition.input_schema.properties["status"]["enum"] == ["ENABLED"]
    assert "default" not in definition.input_schema.properties["status"]
    assert definition.required_permissions
    assert definition.is_write_tool
    assert definition.readback_tool == "google_get_ad"


@pytest.mark.parametrize(
    ("parent_status", "blocked", "delivery_state"),
    [("PAUSED", True, "BLOCKED_BY_PARENT"), ("ENABLED", False, "NOT_VERIFIED")],
)
def test_app_ad_readback_discloses_actual_parent_states_without_claiming_serving(
    parent_status, blocked, delivery_state,
):
    client, events, row = client_fixture(
        group_status=parent_status, campaign_status=parent_status,
    )
    row["adGroupAd"] = {
        "resourceName": "customers/123/adGroupAds/77~88",
        "status": "ENABLED",
        "ad": {"id": "88", "name": "Demo App Ad", "type": "APP_AD", "appAd": {}},
    }
    result = client.get_ad("77~88")
    assert len(events) == 1
    assert "ad_group.id = 77" in events[0][1]
    assert "campaign.status" in events[0][1]
    assert result["status"] == "ENABLED"
    assert result["ad_group_id"] == "77"
    assert result["campaign_id"] == "99"
    assert result["ad_group_status"] == result["campaign_status"] == parent_status
    assert result["delivery_blocked_by_parent"] is blocked
    assert result["delivery_state"] == delivery_state
