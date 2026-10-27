import json

import pytest

from agents.tools.advertising.clients.meta_client import MetaAPIClient
from agents.tools.advertising.providers.meta import create_meta_tool_source
from agents.agent_harness.core.tool_registry import validate_tool_input


def test_catalog_ownership_uses_the_exact_node_not_a_truncated_business_list():
    client = MetaAPIClient({"business_id": "123"})
    calls = []
    def request(method, endpoint, **kwargs):
        calls.append((method, endpoint, kwargs))
        return {"id": "456", "business": {"id": "123"}}
    client.request = request
    client._list_graph_pages = lambda *_a, **_kw: pytest.fail("Do not scan a truncated catalog list")
    assert client.resource_belongs_to_account("789", "catalog", "456") is True
    assert calls[0][1] == "/456"


def test_catalog_from_another_business_never_authorizes_product_set_queries():
    client = MetaAPIClient({"business_id": "123"})
    client.request = lambda *_a, **_kw: {"id": "456", "business": {"id": "999"}}
    client._list_graph_pages = lambda *_a, **_kw: pytest.fail("Foreign catalog must be rejected")
    assert client.resource_belongs_to_account("789", "catalog", "456") is False
    with pytest.raises(PermissionError, match="does not belong"):
        client.list_product_sets("789", "456")


def test_catalog_picker_can_resolve_a_template_id_beyond_its_initial_page():
    client = MetaAPIClient({"business_id": "123"})
    def request(_method, endpoint, **_kwargs):
        assert endpoint == "/456"
        return {"id": "456", "name": "Exact template catalog", "business": {"id": "123"}}
    client.request = request
    client._list_graph_pages = lambda *_a, **_kw: pytest.fail("Exact lookup must not list all catalogs")
    assert client.list_catalogs("789", catalog_id="456") == [{
        "id": "456", "name": "Exact template catalog",
    }]


def test_catalog_lookup_metadata_uses_the_declared_exact_id_query():
    definitions = {item.definition.name: item.definition for item in create_meta_tool_source().list_bindings()}
    assert "catalog_id" in definitions["meta_list_catalogs"].input_schema.properties
    assert definitions["meta_create_campaign"].input_schema.properties["catalog_id"][
        "lookup_query_field"
    ] == "catalog_id"


def test_image_pickers_use_exact_hash_lookup_instead_of_listing_all_assets():
    definitions = {
        item.definition.name: item.definition
        for item in create_meta_tool_source().list_bindings()
    }
    for tool_name in (
        "meta_create_traffic_ad",
        "meta_create_conversion_ad",
        "meta_create_app_promotion_ad",
    ):
        field = definitions[tool_name].input_schema.properties["image_hash"]
        assert field["lookup_tool"] == "meta_list_image_assets"
        assert field["lookup_query_field"] == "hash"
    nested = definitions["meta_create_ad"].input_schema.properties[
        "object_story_spec"
    ]["properties"]["link_data"]["properties"]["image_hash"]
    assert nested["lookup_query_field"] == "hash"


def test_app_template_uses_account_scoped_application_lookup_at_both_levels():
    definitions = {item.definition.name: item.definition for item in create_meta_tool_source().list_bindings()}
    assert definitions["meta_create_adset"].input_schema.properties["promoted_object"][
        "properties"
    ]["application_id"]["lookup_tool"] == "meta_list_apps"
    assert definitions["meta_create_app_promotion_ad"].input_schema.properties[
        "application_id"
    ]["lookup_tool"] == "meta_list_apps"


def test_catalog_campaign_maps_catalog_reference_to_graph_promoted_object():
    client = MetaAPIClient({})
    plan = client.create_campaign("789", {
        "name": "Paused catalog template", "objective": "OUTCOME_SALES",
        "special_ad_categories": ["NONE"], "daily_budget": 30,
        "catalog_id": "456", "status": "PAUSED",
    })
    payload = plan["operation"]["/act_789/campaigns"]["create"]
    assert "catalog_id" not in payload
    assert json.loads(payload["promoted_object"]) == {"product_catalog_id": "456"}


def test_adset_preserves_existing_account_regional_declarations_on_the_wire():
    client = MetaAPIClient({})
    identities = {
        "singapore_universal_beneficiary": "123",
        "singapore_universal_payer": "123",
    }
    plan = client.create_adset("789", "456", {
        "name": "Paused SG template", "status": "PAUSED",
        "regional_regulated_categories": ["SINGAPORE_UNIVERSAL"],
        "regional_regulation_identities": identities,
    })
    payload = plan["operation"]["/act_789/adsets"]["create"]
    assert json.loads(payload["regional_regulated_categories"]) == ["SINGAPORE_UNIVERSAL"]
    assert json.loads(payload["regional_regulation_identities"]) == identities


def test_regional_category_cannot_be_declared_without_its_real_identities():
    definition = next(
        item.definition for item in create_meta_tool_source().list_bindings()
        if item.definition.name == "meta_create_adset"
    )
    arguments = {
        "campaign_id": "456", "name": "Paused SG template",
        "regional_regulated_categories": ["SINGAPORE_UNIVERSAL"],
    }
    errors = validate_tool_input(definition.input_schema, arguments)
    assert any("regional_regulation_identities" in error for error in errors)


def test_catalog_creative_keeps_its_product_set_outside_template_story_data():
    client = MetaAPIClient({})
    plan = client.create_catalog_ad("789", "456", {
        "name": "Paused catalog ad", "status": "PAUSED",
        "page_id": "123", "product_set_id": "111", "link": "https://example.com/",
        "ad_style": "CAROUSEL",
    })
    payload = plan["operation"]["/act_789/ads"]["create"]
    creative = json.loads(payload["creative"])
    assert creative["product_set_id"] == "111"
    assert "product_set_id" not in creative["object_story_spec"]["template_data"]
