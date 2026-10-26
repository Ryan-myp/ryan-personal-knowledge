import json

import pytest

from agents.applications.advertising.composition.ad_application import AdvertisingComposition
from agents.tools.advertising.clients.tiktok_client import TikTokAPIClient
from agents.tools.advertising.providers.tiktok import create_tiktok_tool_source


ACCOUNT = "7397068114548195329"


def test_template_cover_lookup_filters_by_id_before_the_library_page_limit():
    client = TikTokAPIClient({"access_token": "test"})
    client.get_image = lambda account, image_id: {
        "image_id": image_id, "file_name": "Existing template cover",
    }
    client.list_images = lambda *_args, **_kwargs: pytest.fail("Do not scan the newest image page")
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.whitelist_validator.allowed_accounts = {"tiktok": [ACCOUNT]}
    runtime.register_tool_source(create_tiktok_tool_source(client))
    try:
        selection = runtime.resolve_parameter_options(
            "tiktok", "image_web_uris", "tiktok_smart_plus_create_ad",
            account_id=ACCOUNT, session_id="old-template-cover", user_id="test-user",
            account_scope={"tiktok": {ACCOUNT}},
            query="ad-site-i18n-sg/existing-template-cover",
        )
        assert [item["value"] for item in selection["options"]] == [
            "ad-site-i18n-sg/existing-template-cover",
        ]
    finally:
        runtime.close(wait=True)


def test_smart_plus_cover_uses_the_library_uri_not_the_expiring_preview_url():
    client = TikTokAPIClient({"access_token": "test"})
    client.get_image = lambda account, image_id: {
        "image_id": image_id, "image_url": "https://cdn.example/temporary-preview.jpg",
    }
    uri = "ad-site-i18n-sg/existing-cover"
    assert client._smart_plus_image_uris([uri], ACCOUNT, live=True) == [uri]


def test_smart_plus_placements_belong_at_the_provider_top_level():
    client = TikTokAPIClient({"access_token": "test"})
    plan = client.create_smart_plus_adgroup(ACCOUNT, "123", {
        "adgroup_name": "Paused group", "promotion_type": "WEBSITE",
        "objective_type": "TRAFFIC", "optimization_goal": "CLICK",
        "bid_type": "BID_TYPE_NO_BID", "billing_event": "CPC",
        "schedule_type": "SCHEDULE_START_END",
        "schedule_start_time": "2026-10-16 00:00:00",
        "schedule_end_time": "2026-10-18 00:00:00",
        "location_ids": ["1880251"], "placement_type": "PLACEMENT_TYPE_NORMAL",
        "placements": ["PLACEMENT_TIKTOK"],
    })
    payload = plan["operation"]["smart_plus/adgroup/create/"]["create"]
    assert payload["placements"] == ["PLACEMENT_TIKTOK"]
    assert payload["placement_type"] == "PLACEMENT_TYPE_NORMAL"
    assert "placements" not in payload["targeting_spec"]
    assert "placement_type" not in payload["targeting_spec"]


def test_smart_plus_adgroup_rejects_non_numeric_request_id_before_provider_call():
    client = TikTokAPIClient({"access_token": "test"})
    client.request = lambda *_args, **_kwargs: pytest.fail("invalid ID reached Provider")
    with pytest.raises(ValueError, match="request_id must be a decimal int64"):
        client.create_smart_plus_adgroup(ACCOUNT, "123", {
            "request_id": "76308595-d7c8-454f-978d-c2df82778f0f",
            "adgroup_name": "Paused group", "promotion_type": "WEBSITE",
            "objective_type": "TRAFFIC", "optimization_goal": "CLICK",
            "bid_type": "BID_TYPE_NO_BID", "billing_event": "CPC",
            "schedule_type": "SCHEDULE_START_END",
            "schedule_start_time": "2026-10-27 00:00:00",
            "schedule_end_time": "2026-11-05 00:00:00",
            "location_ids": ["1880251"], "operation_status": "DISABLE",
        }, live=True)


def test_smart_plus_explicit_single_video_uses_flat_cover_when_missing():
    client = TikTokAPIClient({"access_token": "test"})
    plan = client.create_smart_plus_ad(ACCOUNT, "123", "456", {
        "ad_name": "Paused video",
        "operation_status": "DISABLE",
        "ad_format": "SINGLE_VIDEO",
        "video_id": "video-one",
        "image_web_uris": ["cover-one"],
        "creative_list": [{
            "creative_info": {
                "ad_format": "SINGLE_VIDEO",
                "video_info": {"video_id": "video-one"},
            },
        }],
    })
    creative = plan["operation"]["smart_plus/ad/create/"]["create"][
        "creative_list"
    ][0]["creative_info"]
    assert creative["image_info"] == [{"web_uri": "cover-one"}]


def test_smart_plus_explicit_cover_takes_precedence_over_flat_alias():
    client = TikTokAPIClient({"access_token": "test"})
    plan = client.create_smart_plus_ad(ACCOUNT, "123", "456", {
        "ad_name": "Paused video",
        "operation_status": "DISABLE",
        "image_web_uris": ["other-cover"],
        "creative_list": [{
            "creative_info": {
                "ad_format": "SINGLE_VIDEO",
                "video_info": {"video_id": "video-one"},
                "image_info": [{"web_uri": "selected-cover"}],
            },
        }],
    })
    creative = plan["operation"]["smart_plus/ad/create/"]["create"][
        "creative_list"
    ][0]["creative_info"]
    assert creative["image_info"] == [{"web_uri": "selected-cover"}]


def test_smart_plus_request_id_contract_requires_decimal_int64():
    from agents.tools.advertising.providers.tiktok.parameters import (
        tiktok_smart_plus_ad_schema,
        tiktok_smart_plus_adgroup_schema,
        tiktok_smart_plus_campaign_schema,
    )

    for schema in (
        tiktok_smart_plus_campaign_schema,
        tiktok_smart_plus_adgroup_schema,
        tiktok_smart_plus_ad_schema,
    ):
        assert schema()["properties"]["request_id"]["pattern"] == "^[0-9]{1,19}$"


def test_ad_queries_read_smart_plus_ads_when_the_regular_endpoint_is_empty():
    client = TikTokAPIClient({"access_token": "test"})
    calls = []

    def request(method, endpoint, params=None, **_kwargs):
        endpoint = endpoint.split("/v1.3/")[-1]
        calls.append((endpoint, params))
        rows = [] if endpoint == "ad/get/" else [{
            "smart_plus_ad_id": "789", "adgroup_id": "456",
            "campaign_id": "123", "operation_status": "DISABLE",
            "creative_list": [{"creative_info": {"video_info": {"video_id": "v1"}}}],
        }]
        return {"status_code": 200, "data": {
            "code": 0, "data": {"list": rows, "page_info": {"total_page": 1}},
        }}

    client.request_raw = request
    result = client.get_ad(ACCOUNT, "456", "789")
    assert result["ad_id"] == result["smart_plus_ad_id"] == "789"
    assert result["creative_list"][0]["creative_info"]["video_info"]["video_id"] == "v1"
    assert [call[0] for call in calls] == ["ad/get/", "smart_plus/ad/get/"]
    assert json.loads(calls[-1][1]["filtering"]) == {
        "adgroup_ids": ["456"], "smart_plus_ad_ids": ["789"],
    }


def test_provider_recording_scope_is_isolated_between_concurrent_requests(tmp_path):
    from contextvars import copy_context
    from scripts.advertising.campaign_service_e2e import ProviderRecorder

    recorder = ProviderRecorder(tmp_path)
    first, second = copy_context(), copy_context()
    first.run(setattr, recorder, "case", {"case_id": "first", "provider": "tiktok"})
    second.run(setattr, recorder, "case", {"case_id": "second", "provider": "tiktok"})
    assert first.run(lambda: recorder.case["case_id"]) == "first"
    assert second.run(lambda: recorder.case["case_id"]) == "second"
    assert recorder.case == {}


def test_smart_plus_catalog_destination_and_age_contracts_match_the_provider():
    from agents.tools.advertising.providers.tiktok.parameters import tiktok_smart_plus_adgroup_schema

    properties = tiktok_smart_plus_adgroup_schema()["properties"]
    assert "CATALOG" not in properties["promotion_type"]["enum"]
    assert "APP_IOS" in properties["promotion_type"]["enum"]
    assert "CATALOG" in properties["product_source"]["enum"]
    assert "AGE_55_100" in properties["age_groups"]["items"]["enum"]
    assert "AGE_65+" not in properties["age_groups"]["items"]["enum"]


def test_smart_plus_product_selection_is_an_ad_configuration_field():
    from agents.tools.advertising.providers.tiktok.parameters import tiktok_smart_plus_ad_schema

    properties = tiktok_smart_plus_ad_schema()["properties"]
    assert "product_set_id" in properties["ad_configuration"]["properties"]


def test_blueprint_policy_allows_declared_related_resource_references():
    from types import SimpleNamespace
    from agents.applications.advertising.execution.ad_tool_policy_factory import AdvertisingToolPolicyFactory
    from agents.agent_harness.core.interfaces import ToolDefinition, ToolSchema

    tool = ToolDefinition(
        name="create_child", namespace="example", skill="example", description="Create child",
        action="create", resource_type="child", parent_resource_id_field="parent_id",
        related_resource_type="root", related_resource_id_fields=["root_id"],
        input_schema=ToolSchema(properties={
            "name": {"type": "string"}, "parent_id": {"type": "string"},
            "root_id": {"type": "string"}, "undeclared": {"type": "string"},
        }),
    )
    factory = AdvertisingToolPolicyFactory(SimpleNamespace(
        _parent_resource_id_field_for_tool=lambda definition: definition.parent_resource_id_field,
    ))
    blueprint = SimpleNamespace(fields=[{"tool_ref": "create_child.name"}])
    assert factory._unowned_creation_argument_error(
        blueprint, tool, {"name": "child", "parent_id": "1", "root_id": "2"},
    ) is None
    assert factory._unowned_creation_argument_error(
        blueprint, tool, {"undeclared": "must still be blocked"},
    )[0] == "creation_input_required"


def test_catalog_lookup_uses_the_official_catalog_id_query_parameter():
    client = TikTokAPIClient({"access_token": "test"})
    calls = []
    client.request = lambda method, endpoint, params=None, **_kwargs: (
        calls.append(params) or {"data": {"list": [{"catalog_id": "7598491157655570192"}]}}
    )
    assert client.get_catalog(ACCOUNT, "7598491157655570192")["catalog_id"] == "7598491157655570192"
    assert calls[-1]["catalog_id"] == "7598491157655570192"
    assert "filtering" not in calls[-1]


def test_app_retargeting_blueprint_uses_the_verified_campaign_endpoint():
    from agents.tools.advertising.shared.domain.blueprint import load_blueprint_file
    from pathlib import Path

    blueprint = load_blueprint_file(
        Path("agents/tools/advertising/providers/tiktok/blueprints/app_conversion_video.v1.json")
    )
    assert blueprint.tools[0] == "tiktok_create_campaign"
    fields = {field["path"]: field for field in blueprint.fields}
    assert fields["campaign.campaign_name"]["tool_ref"] == "tiktok_create_campaign.name"
    assert fields["campaign.status"]["default"] == 0
    assert blueprint.tools == (
        "tiktok_create_campaign", "tiktok_create_adgroup", "tiktok_create_app_ad",
    )


def test_app_ad_contract_exposes_reusable_flat_video_and_identity_inputs():
    from agents.tools.advertising.providers.tiktok.parameters import tiktok_app_ad_schema

    schema = tiktok_app_ad_schema()
    for field in ("video_id", "image_ids", "identity_type", "identity_id"):
        assert field in schema["properties"]
    assert "video_id" in schema["requires_any_of"][0]


@pytest.mark.parametrize("public", [
    "LEARN_MORE", "SHOP_NOW", "CALL_NOW", "SEND_MESSAGE",
])
def test_smart_plus_cta_preserves_api_enum_names_without_mutating_inputs(public):
    client = TikTokAPIClient({"access_token": "test"})
    args = {
        "ad_name": "Paused ad", "ad_format": "SINGLE_IMAGE",
        "image_ids": ["image-1"], "identity_type": "AUTH_CODE",
        "identity_id": "identity-1",
        "call_to_action_list": [{"call_to_action": public}],
    }
    plan = client.create_smart_plus_ad(ACCOUNT, "123", "456", args, live=False)
    actual = plan["operation"]["smart_plus/ad/create/"]["create"]["call_to_action_list"]
    assert actual == [{"call_to_action": public}]
    assert args["call_to_action_list"] == [{"call_to_action": public}]


def test_transport_guard_checks_the_actual_account_in_read_query_parameters(tmp_path):
    from types import SimpleNamespace
    from scripts.advertising.campaign_service_e2e import ProviderRecorder, _request_data

    recorder = ProviderRecorder(tmp_path)
    recorder.case = {"case_id": "query-scope", "provider": "tiktok", "account": ACCOUNT}
    request = SimpleNamespace(
        method="GET", body=None,
        url="https://business-api.tiktok.com/open_api/v1.3/ad/get/?advertiser_id=999999",
    )
    with pytest.raises(PermissionError, match="outside the test account"):
        recorder._guard(request, "tiktok", _request_data(request))
