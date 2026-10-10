import pytest

from agents.tools.advertising.clients.tiktok_client import TikTokAPIClient


@pytest.mark.parametrize("kind", ["campaign", "adgroup"])
def test_updates_preserve_names_and_major_currency_budget_in_flat_payloads(kind):
    client = TikTokAPIClient({"access_token": "fixture"})
    calls = []
    client.request = lambda method, endpoint, **kwargs: (
        calls.append((endpoint, kwargs["data"])) or {"code": 0, "data": {}}
    )
    if kind == "campaign":
        client.update_campaign(
            "123",
            "234",
            {"name": "QA updated", "daily_budget": 60, "status": 0},
            live=True,
        )
        name_field, id_field, resource_id = "campaign_name", "campaign_id", "234"
    else:
        client.update_adgroup(
            "123",
            "234",
            "345",
            {"name": "QA updated", "budget": 60, "status": 0},
            live=True,
        )
        name_field, id_field, resource_id = "adgroup_name", "adgroup_id", "345"
    content = next(data for path, data in calls if path == kind + "/update/")
    assert content[name_field] == "QA updated"
    assert content["budget"] == 60
    assert not any(key in content for key in ("campaign", "ad_group"))
    status = next(data for path, data in calls if path == kind + "/status/update/")
    assert status[id_field + "s"] == [resource_id]
    assert status["operation_status"] == "DISABLE"


@pytest.mark.parametrize(
    "updates",
    [
        {"status": 0, "campaign_group_status": 1},
        {"daily_budget": 60, "budget": 6000},
    ],
)
def test_conflicting_updates_are_rejected_before_any_provider_mutation(updates):
    client = TikTokAPIClient({"access_token": "fixture"})
    calls = []
    client.request = lambda *args, **kwargs: calls.append((args, kwargs))
    with pytest.raises(ValueError, match="conflicting"):
        client.update_campaign("123", "234", updates, live=True)
    assert calls == []


def test_landing_url_update_uses_complete_creative_and_preserves_paused_delivery():
    client = TikTokAPIClient({"access_token": "fixture"})
    client.get_ad = lambda *_args: {
        "ad_id": "456", "ad_name": "old", "ad_format": "SINGLE_VIDEO",
        "operation_status": "DISABLE", "video_id": "video", "image_ids": ["cover"],
        "identity_type": "BC_AUTH_TT", "identity_id": "identity",
        "identity_authorized_bc_id": "private-bc", "ad_text": "old text",
        "landing_page_url": "https://example.com",
    }
    calls = []
    client.request = lambda method, endpoint, **kwargs: (
        calls.append(kwargs["data"]) or {"code": 0, "data": {}}
    )
    client.update_creative("123", "345", "456", {
        "ad_name": "new", "ad_text": "new text", "landing_page_url": "https://example.com/?updated=1",
    }, live=True)
    data = calls[0]
    assert data["patch_update"] is False
    creative = data["creatives"][0]
    assert creative["video_id"] == "video"
    assert creative["image_ids"] == ["cover"]
    assert creative["operation_status"] == "DISABLE"
    assert creative["landing_page_url"] == "https://example.com/?updated=1"
