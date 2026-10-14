"""Tests for account-aware, data-only creation templates."""

import pytest
import glob
import json
from pathlib import Path
from types import SimpleNamespace
from fastapi.testclient import TestClient

import agents.deployments.advertising.api_server as api_server
from agents.agent_harness.core.interfaces import ParsedIntent
from agents.applications.advertising.creation.ad_creation_template_services import (
    AdCreationTemplateServicesMixin,
)
from agents.applications.advertising.creation.templates import (
    CreationTemplateError,
    CreationTemplateManager,
    load_builtin_template_definitions,
)
from agents.applications.advertising.persistence.store import AdAgentStore
from agents.applications.advertising.execution.input_builder import ToolInputBuilder
from agents.tools.advertising.shared.domain.blueprint import load_blueprint_file
from agents.applications.advertising.composition.ad_application import (
    AdvertisingComposition,
)
from agents.tools.advertising.providers.tiktok.provider import (
    create_tiktok_tool_source,
)


BLUEPRINT = {
    "id": "demo.leads",
    "version": "1.0.0",
    "provider": "meta",
    "ad_format": "LEAD",
    "fields": [
        {"path": "campaign.objective"},
        {"path": "campaign.daily_budget"},
    ],
}


def manager():
    return CreationTemplateManager(
        AdAgentStore(":memory:"),
        lambda blueprint_id, version=None: (
            BLUEPRINT
            if blueprint_id == BLUEPRINT["id"]
            and (version is None or version == BLUEPRINT["version"])
            else None
        ),
    )


def payload(**overrides):
    value = {
        "name": "北美获客默认模板",
        "provider": "meta",
        "blueprint_id": "demo.leads",
        "blueprint_version": "1.0.0",
        "ad_format": "LEAD",
        "scope_type": "account",
        "account_id": "act_123",
        "region": "US",
        "tags": ["北美", "获客"],
        "values": {"campaign.objective": "LEADS", "campaign.daily_budget": 50},
    }
    value.update(overrides)
    return value


def test_template_crud_is_scoped_to_authenticated_user():
    templates = manager()
    created = templates.create("tenant-a", "user-a", payload())
    assert created["scope_label"] == "指定账户"
    assert created["covered_fields"] == 2
    assert templates.get("tenant-a", "user-b", created["template_id"]) is None
    listed = templates.list("tenant-a", "user-a")
    assert [item["name"] for item in listed] == ["北美获客默认模板"]

    updated = templates.update(
        "tenant-a", "user-a", created["template_id"],
        {"description": "稳定获客基线", "status": "inactive"},
    )
    assert updated["description"] == "稳定获客基线"
    assert updated["status"] == "inactive"
    assert templates.apply("tenant-a", "user-a", created["template_id"]) is None


def test_template_applies_schema_fields_exposed_by_the_expanded_blueprint():
    from agents.tools.advertising.providers.meta import create_meta_tool_source

    store = AdAgentStore(":memory:")
    runtime = AdvertisingComposition(require_llm=False, persistence_store=store)
    runtime.register_tool_source(create_meta_tool_source())
    account = "2806375919473667"
    scope = {"meta": {account}}
    template = runtime._creation_template_manager_for_request(scope).create(
        "default", "template-user", {
            "name": "Paused traffic",
            "provider": "meta",
            "blueprint_id": "meta.traffic_link",
            "scope_type": "account",
            "account_id": account,
            "values": {"campaign.status": "PAUSED", "ad_set.status": "PAUSED", "ad.status": "PAUSED"},
        },
    )
    try:
        intent = runtime.apply_creation_template_to_intent(
            ParsedIntent("create_campaign", "Create", ["meta"]),
            template["template_id"],
            account_id=account,
            account_scope=scope,
            user_id="template-user",
        )
        values = intent.scoped_parameters["meta"]
        assert values["meta_create_campaign"]["status"] == "PAUSED"
        assert values["meta_create_adset"]["status"] == "PAUSED"
        assert values["meta_create_traffic_ad"]["status"] == "PAUSED"
    finally:
        runtime.close(wait=True)
        store.close()


def test_meta_conversion_template_uses_a_real_sales_objective():
    from agents.tools.advertising.providers.meta.parameters import meta_campaign_schema

    template = next(
        item for item in load_builtin_template_definitions() if item["key"] == "meta.test.conversion"
    )
    objective = template["values"]["campaign.objective"]
    assert objective == "OUTCOME_SALES"
    assert "OUTCOME_CONVERSIONS" not in meta_campaign_schema()["properties"]["objective"]["enum"]


def test_template_rejects_unknown_or_sensitive_fields():
    templates = manager()
    with pytest.raises(CreationTemplateError, match="不支持的字段"):
        templates.create("tenant-a", "user-a", payload(values={"not_in_blueprint": "x"}))
    with pytest.raises(CreationTemplateError, match="凭证"):
        templates.create(
            "tenant-a", "user-a",
            payload(values={"campaign.objective": {"access_token": "secret"}}),
        )


def test_template_allows_description_fields_but_rejects_script_fields():
    blueprint = {
        **BLUEPRINT,
        "id": "demo.copy",
        "fields": [{
            "path": "ad.descriptions",
            "tool_ref": "meta_create_ad.descriptions",
        }],
    }
    templates = CreationTemplateManager(
        AdAgentStore(":memory:"),
        lambda blueprint_id, version=None: (
            blueprint if blueprint_id == blueprint["id"] else None
        ),
    )
    accepted = templates.create(
        "tenant-a",
        "user-a",
        payload(
            blueprint_id=blueprint["id"],
            values={"ad.descriptions": ["A valid ad description"]},
        ),
    )
    assert accepted["values"] == {
        "ad.descriptions": ["A valid ad description"],
    }

    with pytest.raises(CreationTemplateError, match="凭证或可执行配置"):
        templates.create(
            "tenant-a",
            "user-a",
            payload(
                blueprint_id=blueprint["id"],
                values={"ad.descriptions": {"script": "print(1)"}},
            ),
        )


@pytest.mark.parametrize("token_key", ["selection_token", "selection_tokens"])
def test_template_rejects_lookup_authorization_tokens_at_any_depth(token_key):
    templates = manager()
    with pytest.raises(CreationTemplateError, match="凭证"):
        templates.create(
            "tenant-a",
            "user-a",
            payload(values={"campaign.objective": {"nested": {token_key: "signed-token"}}}),
        )


def test_template_rejects_signed_selection_token_embedded_in_a_value():
    templates = manager()
    token = f"ps1.eyJ2IjoxfQ.{('a' * 64)}"
    with pytest.raises(CreationTemplateError, match="凭证"):
        templates.create(
            "tenant-a",
            "user-a",
            payload(values={"campaign.objective": token}),
        )


def test_account_and_region_scopes_require_their_matching_selector():
    templates = manager()
    with pytest.raises(CreationTemplateError, match="account_id"):
        templates.create("tenant-a", "user-a", payload(account_id=""))
    with pytest.raises(CreationTemplateError, match="region"):
        templates.create("tenant-a", "user-a", payload(scope_type="region", region=""))


def test_duplicate_creates_an_active_independent_template():
    templates = manager()
    created = templates.create("tenant-a", "user-a", payload())
    duplicate = templates.duplicate("tenant-a", "user-a", created["template_id"], "复制版")
    assert duplicate["template_id"] != created["template_id"]
    assert duplicate["name"] == "复制版"
    assert duplicate["status"] == "active"


def test_only_one_default_is_kept_per_blueprint_scope():
    templates = manager()
    first = templates.create("tenant-a", "user-a", payload(name="第一版", is_default=True))
    second = templates.create("tenant-a", "user-a", payload(name="第二版", is_default=True))
    records = templates.list("tenant-a", "user-a")
    defaults = [item for item in records if item["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["template_id"] == second["template_id"]
    assert first["template_id"] != second["template_id"]


def test_template_http_contract_uses_trusted_principal_and_blueprint_registry(monkeypatch):
    class Registry:
        def get(self, blueprint_id, version=None):
            if blueprint_id != BLUEPRINT["id"]:
                return None
            if version and version != BLUEPRINT["version"]:
                return None
            return BLUEPRINT

    class Runtime:
        persistence_store = AdAgentStore(":memory:")
        creation_blueprints = Registry()
        creation_card_builder = None
        _granted_permissions = {"ads.read", "ads.plan"}

    monkeypatch.setattr(api_server, "runtime", Runtime())
    monkeypatch.setattr(api_server, "API_KEY", "template-key")
    monkeypatch.setattr(api_server, "ALLOW_UNAUTHENTICATED", False)
    with TestClient(api_server.app) as client:
        response = client.post(
            "/creation-templates",
            headers={"X-API-Key": "template-key"},
            json=payload(),
        )
        assert response.status_code == 201
        template_id = response.json()["template_id"]
        listed = client.get("/creation-templates", headers={"X-API-Key": "template-key"})
        assert listed.status_code == 200
        assert listed.json()["templates"][0]["template_id"] == template_id
        applied = client.post(
            f"/creation-templates/{template_id}/apply",
            headers={"X-API-Key": "template-key"},
        )
    assert applied.status_code == 200
    assert applied.json()["usage_count"] == 1


def test_builtin_template_is_account_bound_read_only_and_duplicable():
    definitions = [{
        "key": "meta.test.leads",
        "name": "Meta 测试获客",
        "description": "受控测试账号的标准获客参数。",
        "provider": "meta",
        "blueprint_id": BLUEPRINT["id"],
        "blueprint_version": BLUEPRINT["version"],
        "ad_format": BLUEPRINT["ad_format"],
        "account_id": "act_123",
        "verification_status": "live_verified",
        "required_inputs": ["campaign.daily_budget"],
        "values": {"campaign.objective": "LEADS"},
    }]
    templates = CreationTemplateManager(
        AdAgentStore(":memory:"),
        lambda blueprint_id, version=None: (
            BLUEPRINT
            if blueprint_id == BLUEPRINT["id"]
            and (version is None or version == BLUEPRINT["version"])
            else None
        ),
        builtin_templates=definitions,
        allowed_accounts={"meta": ["act_123"]},
    )

    listed = templates.list("tenant-a", "user-a")
    assert len(listed) == 1
    builtin = listed[0]
    assert builtin["source"] == "builtin"
    assert builtin["editable"] is False
    assert builtin["account_id"] == "act_123"
    assert builtin["verification_status"] == "live_verified"
    assert builtin["template_id"].startswith("builtin_")
    assert templates.apply("tenant-a", "user-a", builtin["template_id"])["usage_count"] == 0

    with pytest.raises(CreationTemplateError, match="不可修改"):
        templates.update("tenant-a", "user-a", builtin["template_id"], {"name": "不应修改"})
    with pytest.raises(CreationTemplateError, match="不可删除"):
        templates.delete("tenant-a", "user-a", builtin["template_id"])

    duplicate = templates.duplicate("tenant-a", "user-a", builtin["template_id"], "我的获客模板")
    assert duplicate["source"] == "user"
    assert duplicate["template_id"] != builtin["template_id"]
    assert duplicate["name"] == "我的获客模板"


def test_builtin_templates_are_filtered_by_whitelisted_test_accounts():
    definitions = load_builtin_template_definitions()
    assert len(definitions) == 13
    templates_by_key = {item["key"]: item for item in definitions}
    assert templates_by_key["google.test.app"]["values"]["campaign.app_campaign_setting"] == {
        "app_id": "959841107",
        "app_store": "APPLE_APP_STORE",
        "bidding_strategy_goal_type": "OPTIMIZE_IN_APP_CONVERSIONS_TARGET_CONVERSION_COST",
    }
    assert templates_by_key["google.test.app"]["values"][
        "campaign.selective_optimization"
    ] == {
        "conversion_actions": [
            "customers/9055507554/conversionActions/453201534",
            "customers/9055507554/conversionActions/6497810605",
        ]
    }
    assert templates_by_key["google.test.shopping"]["values"][
        "campaign.shopping_setting.merchant_id"
    ] == 115791065
    assert templates_by_key["google.test.shopping"]["values"][
        "product_group.partition_type"
    ] == "UNIT"
    assert templates_by_key["meta.test.traffic"]["values"]["ad.page_id"] == "1266166123254225"
    assert templates_by_key["tiktok.test.traffic"]["values"]["ad.video_id"] == (
        "v10033g50000d8nltv7og65nd6868v7g"
    )
    assert templates_by_key["tiktok.test.traffic"]["values"]["ad.identity_id"] == (
        "15efada4-8fb9-54aa-b5c6-3b82529b947d"
    )
    assert templates_by_key["tiktok.test.traffic"]["values"]["ad.identity_type"] == "BC_AUTH_TT"
    tiktok_sales = templates_by_key["tiktok.test.sales"]["values"]
    assert tiktok_sales["campaign.objective_type"] == "PRODUCT_SALES"
    assert tiktok_sales["campaign.catalog_enabled"] is True
    assert tiktok_sales["campaign.sales_destination"] == "WEBSITE"
    assert tiktok_sales["ad_group.promotion_type"] == "CATALOG"
    assert tiktok_sales["ad_group.catalog_id"] == "6964618698963289858"
    assert tiktok_sales["ad_group.product_set_id"] == "3229"
    assert "ad_group.pixel_id" not in tiktok_sales
    tiktok_app = templates_by_key["tiktok.test.app-promotion"]["values"]
    assert tiktok_app["campaign.app_id"] == "6816285226570924038"
    assert tiktok_app["ad_group.app_id"] == tiktok_app["campaign.app_id"]
    assert all(
        "selection_token" not in json.dumps(item["values"])
        for item in definitions
    )
    assert {item["provider"] for item in definitions} == {
        "meta", "google-ads", "tiktok", "dv360",
    }
    requested_blueprints = {
        "google-ads.performance_max",
        "google-ads.shopping",
        "google-ads.app",
        "meta.catalog_sales",
        "meta.traffic_link",
        "meta.conversion_link",
        "meta.app_promotion",
        "tiktok.product_sales_video",
        "tiktok.traffic_video",
        "tiktok.app_conversion_video",
    }
    assert requested_blueprints <= {
        item["blueprint_id"] for item in definitions
    }
    blueprint_paths = glob.glob("agents/tools/advertising/providers/*/blueprints/*.json")
    blueprint_versions = {
        blueprint["id"]: blueprint["version"]
        for path in blueprint_paths
        for blueprint in [json.loads(Path(path).read_text(encoding="utf-8"))]
    }
    assert all(
        item["blueprint_version"] == blueprint_versions[item["blueprint_id"]]
        for item in definitions
        if item["blueprint_id"] in requested_blueprints
    )
    assert all(item["account_id"] for item in definitions)
    assert all(item["verification_status"] in {
        "live_verified", "partial_live_verified",
        "live_verified_with_provider_limits", "dry_run_only", "provider_limited",
    } for item in definitions)

    templates = CreationTemplateManager(
        AdAgentStore(":memory:"),
        lambda blueprint_id, version=None: next((
            {
                "id": blueprint_id,
                "version": item["blueprint_version"],
                "provider": item["provider"],
                "ad_format": item["ad_format"],
                "fields": [{"path": path} for path in item["values"]],
            }
            for item in definitions
            if item["blueprint_id"] == blueprint_id
            and (version is None or version == item["blueprint_version"])
        ), None),
        builtin_templates=definitions,
        allowed_accounts={"meta": ["2806375919473667"]},
    )
    listed = templates.list("tenant-a", "user-a")
    assert listed
    assert {item["provider"] for item in listed} == {"meta"}
    assert {item["account_id"] for item in listed} == {"2806375919473667"}


def test_requested_ad_type_templates_bind_only_to_the_confirmed_test_account():
    definitions = load_builtin_template_definitions()
    expected_accounts = {
        "google-ads.performance_max": "9055507554",
        "google-ads.shopping": "9055507554",
        "google-ads.app": "9055507554",
        "meta.catalog_sales": "2806375919473667",
        "meta.traffic_link": "2806375919473667",
        "meta.conversion_link": "2806375919473667",
        "meta.app_promotion": "2806375919473667",
        "tiktok.product_sales_video": "7397068114548195329",
        "tiktok.traffic_video": "7397068114548195329",
        "tiktok.app_conversion_video": "7397068114548195329",
    }
    templates = {
        item["blueprint_id"]: item
        for item in definitions
        if item["blueprint_id"] in expected_accounts
    }

    assert set(templates) == set(expected_accounts)
    assert {
        blueprint_id: template["account_id"]
        for blueprint_id, template in templates.items()
    } == expected_accounts


def test_builtin_template_http_catalog_uses_runtime_whitelist(monkeypatch):
    from agents.tools.advertising.providers.source_factory import create_tool_source

    composition = AdvertisingComposition(
        require_llm=False, offline_mode=True, persistence_store=AdAgentStore(":memory:"),
    )
    for provider in ("meta", "google-ads", "tiktok", "dv360"):
        composition.register_tool_source(create_tool_source(provider))

    class Validator:
        allowed_accounts = {
            "meta": ["2806375919473667"],
            "google-ads": ["9055507554"],
            "tiktok": ["7397068114548195329"],
            "dv360": ["5110831"],
        }

    class Runtime:
        persistence_store = AdAgentStore(":memory:")
        creation_blueprints = composition.creation_blueprints
        creation_card_builder = composition.creation_card_builder
        whitelist_validator = Validator()
        _granted_permissions = {"ads.read", "ads.plan"}

    monkeypatch.setattr(api_server, "runtime", Runtime())
    monkeypatch.setattr(api_server, "API_KEY", "builtin-key")
    monkeypatch.setattr(api_server, "ALLOW_UNAUTHENTICATED", False)
    with TestClient(api_server.app) as client:
        response = client.get(
            "/creation-templates",
            headers={"X-API-Key": "builtin-key"},
        )
        assert response.status_code == 200
        templates = response.json()["templates"]
        assert len(templates) == 13
        assert all(item["source"] == "builtin" for item in templates)
        assert {item["account_id"] for item in templates} == {
            "2806375919473667", "9055507554",
            "7397068114548195329", "5110831",
        }
        builtin_id = templates[0]["template_id"]
        duplicate = client.post(
            f"/creation-templates/{builtin_id}/duplicate",
            headers={"X-API-Key": "builtin-key"},
            json={},
        )
        assert duplicate.status_code == 201
        assert duplicate.json()["source"] == "user"
        protected = client.patch(
            f"/creation-templates/{builtin_id}",
            headers={"X-API-Key": "builtin-key"},
            json={"name": "不能改"},
        )
        assert protected.status_code == 422


def test_google_builtin_templates_prefill_everything_except_name_schedule_and_budget():
    definitions = {
        item["key"]: item
        for item in load_builtin_template_definitions()
        if item["key"] in {
            "google.test.performance-max",
            "google.test.shopping",
            "google.test.app",
        }
    }
    user_inputs = {
        "campaign.campaign_name",
        "campaign.start_date",
        "campaign.end_date",
        "campaign.daily_budget",
    }
    expected_input_labels = {
        "广告系列名称",
        "投放开始日期",
        "投放结束日期",
        "日预算",
    }

    assert set(definitions) == {
        "google.test.performance-max",
        "google.test.shopping",
        "google.test.app",
    }

    for key, template in definitions.items():
        blueprint_path = (
            Path("agents/tools/advertising/providers/google/blueprints")
            / f"{template['blueprint_id'].rsplit('.', 1)[-1]}.v1.json"
        )
        blueprint = json.loads(blueprint_path.read_text(encoding="utf-8"))
        required_paths = {
            field["path"]
            for field in blueprint["fields"]
            if field.get("required") is True
        }

        assert set(template["required_inputs"]) == expected_input_labels, key
        assert required_paths - user_inputs <= set(template["values"]), key
        assert user_inputs <= {
            field["path"]
            for field in blueprint["fields"]
            if field.get("required") is True
        }, key
        assert template["values"]["campaign.status"] == "PAUSED", key

    expected_statuses = {
        "google.test.performance-max": "live_verified_with_provider_limits",
        "google.test.shopping": "live_verified_with_provider_limits",
        "google.test.app": "partial_live_verified",
    }
    for key, template in definitions.items():
        assert template["verification_status"] == expected_statuses[key]
        assert template["account_id"] == "9055507554"

    assert "AssetGroupAsset" in definitions[
        "google.test.performance-max"
    ]["verified_scope"]
    assert "UNIT_INCLUDED" in definitions[
        "google.test.performance-max"
    ]["verified_scope"]
    assert "Product Group" in definitions["google.test.shopping"]["verified_scope"]
    assert "ENABLED" in definitions["google.test.shopping"]["verified_scope"]
    assert "App Ad" in definitions["google.test.app"]["verified_scope"]
    assert "ENABLED" in definitions["google.test.app"]["verified_scope"]

    pmax = definitions["google.test.performance-max"]["values"]
    assert type(pmax["campaign.shopping_setting"]["merchant_id"]) is int
    assert len(pmax["asset_group.headlines"]) >= 3
    assert len(pmax["asset_group.long_headlines"]) >= 1
    assert len(pmax["asset_group.descriptions"]) >= 2
    assert pmax["asset_group.final_urls"]
    assert pmax["asset_group.images"]
    assert pmax["asset_group.square_marketing_images"]
    assert pmax["asset_group.logos"]
    assert pmax["asset_group.business_names"]
    assert pmax["asset_group.status"] == "PAUSED"
    assert pmax["listing_group_filter.filter_type"] == "UNIT_INCLUDED"
    assert pmax["listing_group_filter.listing_source"] == "SHOPPING"
    assert "listing_group_filter.product_dimension" not in pmax
    assert pmax["asset_group.long_headlines"] == [
        {"text": "Shopee Choice mang đến sản phẩm đảm bảo với mức giá siêu hời"},
    ]
    assert pmax["asset_group.descriptions"][0] == {
        "text": "Shopee Choice mang đến sản phẩm đảm bảo với mức giá siêu hời, lại còn freeship",
    }
    assert all(
        isinstance(item, dict) and item.get("text") and not item.get("asset_id")
        for item in pmax["asset_group.headlines"]
    )
    assert pmax["asset_group.images"] == [
        "customers/9055507554/assets/194802085984",
    ]
    assert pmax["asset_group.square_marketing_images"] == [
        "customers/9055507554/assets/194802072931",
    ]
    assert pmax["asset_group.logos"] == [
        "customers/9055507554/assets/194784955410",
    ]
    assert pmax["asset_group.business_names"] == [{"text": "蝦皮購物"}]

    shopping = definitions["google.test.shopping"]["values"]
    assert type(shopping["campaign.shopping_setting.merchant_id"]) is int
    assert shopping["campaign.bidding_strategy"] == "MAXIMIZE_CLICKS"
    assert shopping["ad_group.name"]
    assert shopping["ad_group.status"] == "PAUSED"
    assert shopping["ad_group.cpc_bid_micros"] == 500000
    assert shopping["product_group.cpc_bid_micros"] == 500000
    assert shopping["product_group.status"] == "PAUSED"
    assert shopping["ad.name"]
    assert shopping["ad.status"] == "PAUSED"

    app = definitions["google.test.app"]["values"]
    assert app["campaign.bidding_strategy"] == "TARGET_CPA"
    assert app["campaign.target_cpa_micros"] == 11010000
    assert len(app["ad.headlines"]) >= 2
    assert len(app["ad.descriptions"]) >= 2
    assert app["ad.images"] == [
        "customers/9055507554/assets/312078053811",
    ]
    assert app["ad_group.name"]
    assert app["ad_group.status"] == "PAUSED"
    assert app["ad.name"]
    assert app["ad.status"] == "PAUSED"


def test_google_template_user_inputs_are_projected_into_campaign_tool_arguments():
    definitions = {
        item["key"]: item
        for item in load_builtin_template_definitions()
    }
    template = definitions["google.test.app"]
    blueprint_paths = glob.glob(
        "agents/tools/advertising/providers/*/blueprints/*.json"
    )
    blueprints = {
        blueprint.blueprint_id: blueprint
        for blueprint in (
            load_blueprint_file(path) for path in blueprint_paths
        )
    }

    class Registry:
        def get(self, blueprint_id, version=None):
            blueprint = blueprints.get(blueprint_id)
            if blueprint is None or (
                version is not None and version != blueprint.version
            ):
                return None
            return blueprint

    class Validator:
        allowed_accounts = {"google-ads": ["9055507554"]}

    class Runtime(AdCreationTemplateServicesMixin):
        persistence_store = AdAgentStore(":memory:")
        creation_blueprints = Registry()
        creation_card_builder = None
        whitelist_validator = Validator()

        @staticmethod
        def _canonical_platform(value):
            return str(value)

    runtime = Runtime()
    intent = ParsedIntent(
        "create_campaign",
        "创建 App Campaign",
        ["google-ads"],
        scoped_parameters={
            "google-ads": {
                "campaign_name": "QA App Template 20261012",
                "end_date": "2026-10-31",
                "google_create_campaign": {
                    "start_date": "2026-10-13",
                    "daily_budget": 50,
                },
            }
        },
    )
    applied = runtime.apply_creation_template_to_intent(
        intent,
        CreationTemplateManager._builtin_id(template),
        account_id="9055507554",
    )
    tool_definition = SimpleNamespace(
        name="google_create_campaign",
        action="create",
        input_schema=SimpleNamespace(
            properties={
                "campaign_name": {"type": "string"},
                "start_date": {"type": "string"},
                "end_date": {"type": "string"},
                "daily_budget": {"type": "number"},
                "bidding_strategy": {"type": "string"},
                "target_cpa_micros": {"type": "integer"},
                "app_campaign_setting": {"type": "object"},
                "selective_optimization": {"type": "object"},
                "status": {"type": "string"},
            },
            required=["campaign_name", "start_date", "end_date", "daily_budget"],
            conditional_rules=[],
        ),
    )
    input_builder = ToolInputBuilder(SimpleNamespace(
        normalize_namespace=lambda value: str(value),
        is_dry_run=lambda: False,
    ))

    arguments = input_builder.build(tool_definition, applied, "google-ads")

    assert arguments["campaign_name"] == "QA App Template 20261012"
    assert arguments["start_date"] == "2026-10-13"
    assert arguments["end_date"] == "2026-10-31"
    assert arguments["daily_budget"] == 50
    assert arguments["bidding_strategy"] == "TARGET_CPA"
    assert arguments["target_cpa_micros"] == 11010000
    assert arguments["app_campaign_setting"] == template["values"][
        "campaign.app_campaign_setting"
    ]
    assert arguments["selective_optimization"] == template["values"][
        "campaign.selective_optimization"
    ]
    assert arguments["status"] == "PAUSED"


def test_tiktok_template_blueprints_bind_registered_smart_plus_tools_by_resource():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_tiktok_tool_source())

    expected_tools = (
        "tiktok_smart_plus_create_campaign",
        "tiktok_smart_plus_create_adgroup",
        "tiktok_smart_plus_create_ad",
    )
    for blueprint_id in (
        "tiktok.traffic_video",
        "tiktok.product_sales_video",
        "tiktok.app_conversion_video",
    ):
        blueprint = runtime.creation_blueprints.get(blueprint_id)
        assert blueprint is not None
        assert blueprint.tools == expected_tools

        for field in blueprint.fields:
            tool_name, schema_path = field["tool_ref"].split(".", 1)
            definition, _handler = runtime.registry.get(tool_name)
            assert tool_name in expected_tools
            assert definition.resource_type == field["path"].split(".", 1)[0]

            schema = definition.input_schema.properties
            parts = schema_path.split(".")
            for index, part in enumerate(parts):
                assert part in schema, (blueprint_id, field["tool_ref"])
                child = schema[part]
                if index < len(parts) - 1:
                    schema = child.get("properties", {})


def test_tiktok_templates_only_ask_for_name_schedule_and_one_budget():
    account_id = "7397068114548195329"
    expected_inputs = {
        "Campaign 名称",
        "开始时间（UTC）",
        "结束时间（UTC）",
        "总预算（USD）",
    }
    runtime = AdvertisingComposition(
        require_llm=False,
        offline_mode=True,
        persistence_store=AdAgentStore(":memory:"),
    )
    runtime.whitelist_validator.allowed_accounts = {"tiktok": [account_id]}
    runtime.register_tool_source(create_tiktok_tool_source())
    templates = {
        item["key"]: item
        for item in load_builtin_template_definitions()
        if item["key"] in {
            "tiktok.test.traffic",
            "tiktok.test.sales",
            "tiktok.test.app-promotion",
        }
    }
    assert set(templates) == {
        "tiktok.test.traffic",
        "tiktok.test.sales",
        "tiktok.test.app-promotion",
    }

    for template in templates.values():
        assert template["account_id"] == account_id
        assert set(template["required_inputs"]) == expected_inputs
        values = template["values"]
        assert values["ad_group.budget_mode"] == "BUDGET_MODE_TOTAL"
        assert values["ad_group.schedule_type"] == "SCHEDULE_START_END"
        assert values["campaign.operation_status"] == "DISABLE"
        assert values["ad_group.operation_status"] == "DISABLE"
        assert values["ad.operation_status"] == "DISABLE"
        assert "campaign.budget" not in values
        assert "ad_group.budget" not in values

        blueprint = runtime.creation_blueprints.get(template["blueprint_id"])
        assert blueprint is not None
        required_paths = {
            field["path"]
            for field in blueprint.fields
            if field.get("required") is True
        }
        user_paths = {
            "campaign.campaign_name",
            "ad_group.budget",
            "ad_group.schedule_start_time",
            "ad_group.schedule_end_time",
        }
        assert user_paths <= required_paths
        generated_paths = {
            field["path"]
            for field in blueprint.fields
            if field.get("default_strategy") == "generated_name"
        }
        assert required_paths - user_paths <= set(values) | generated_paths

        template_id = runtime._creation_template_manager_for_request(
            {"tiktok": {account_id}},
        )._builtin_id(template)
        intent = ParsedIntent(
            "create_campaign",
            f"创建 {template['name']}",
            ["tiktok"],
            scoped_parameters={"tiktok": {"account_id": account_id}},
        )
        applied = runtime.apply_creation_template_to_intent(
            intent,
            template_id,
            account_id=account_id,
            account_scope={"tiktok": {account_id}},
        )
        card = runtime.build_creation_ui(
            applied,
            account_id=account_id,
            account_scope={"tiktok": {account_id}},
        )["cards"][0]
        assert set(card["user_input_fields"]) == user_paths
        assert card["ready"] is False
        assert card["template_id"] == template_id
        fields = {field["path"]: field for field in card["fields"]}
        for path, value in values.items():
            assert fields[path]["value"] == value, (template["key"], path)
            assert fields[path]["user_required"] is False, (
                template["key"],
                path,
            )
        assert fields["campaign.campaign_name"]["user_required"] is True
        assert fields["ad.video_id"]["input_mode"] == "auto_default"
        assert fields["ad.video_id"]["lookup"]["tool"] == "tiktok_get_video"
        assert fields["ad.video_id"]["lookup"]["query_field"] == "video_id"
        assert fields["ad_group.bid_price"]["required"] is False
        assert fields["ad_group.conversion_bid_price"]["required"] is False

        # A template ID by itself is not enough to suppress required inputs.
        # The server-side apply operation must carry the actual covered paths.
        unproven_template_intent = ParsedIntent(
            applied.intent_type,
            applied.raw_input,
            applied.namespaces,
            attributes=applied.attributes,
            parameters=applied.parameters,
            scoped_parameters=applied.scoped_parameters,
            metadata={
                key: value
                for key, value in applied.metadata.items()
                if key != "creation_template_prefilled_fields"
            },
        )
        unproven_card = runtime.build_creation_ui(
            unproven_template_intent,
            account_id=account_id,
            account_scope={"tiktok": {account_id}},
        )["cards"][0]
        unproven_fields = {
            field["path"]: field for field in unproven_card["fields"]
        }
        assert unproven_fields["ad.identity_id"]["user_required"] is True
        assert unproven_fields["ad.ad_text"]["user_required"] is True

    traffic = templates["tiktok.test.traffic"]
    sales = templates["tiktok.test.sales"]
    app = templates["tiktok.test.app-promotion"]
    assert traffic["values"]["ad_group.location_ids"] == ["1880251"]
    assert traffic["values"]["ad_group.optimization_goal"] == "CLICK"
    assert traffic["values"]["ad_group.billing_event"] == "CPC"
    assert traffic["values"]["ad.call_to_action"] == "LEARN_MORE"
    assert traffic["values"]["ad.landing_page_url"] == "https://shopee.sg/"
    assert sales["values"]["ad_group.catalog_id"] == "6964618698963289858"
    assert sales["values"]["ad_group.product_set_id"] == "3229"
    assert app["values"]["campaign.app_id"] == "6816285226570924038"
    assert app["values"]["ad_group.app_id"] == "6816285226570924038"

    for template in templates.values():
        values = template["values"]
        assert values["ad.video_id"] == "v10033g50000d8nltv7og65nd6868v7g"
        assert values["ad.image_web_uris"]
        assert values["ad.identity_type"] == "BC_AUTH_TT"
        assert values["ad.identity_id"] == "15efada4-8fb9-54aa-b5c6-3b82529b947d"

        intent = ParsedIntent(
            "create_campaign",
            "创建测试广告",
            ["tiktok"],
            scoped_parameters={
                "tiktok": {
                    "account_id": account_id,
                    "campaign": {"campaign_name": "QA TikTok 20261012"},
                    "ad_group": {
                        "budget": 50,
                        "schedule_start_time": "2026-10-13 00:00:00",
                        "schedule_end_time": "2026-10-15 00:00:00",
                    },
                }
            },
        )
        template_id = runtime._creation_template_manager_for_request(
            {"tiktok": {account_id}},
        )._builtin_id(template)
        applied = runtime.apply_creation_template_to_intent(
            intent,
            template_id,
            account_id=account_id,
            account_scope={"tiktok": {account_id}},
        )
        definitions = {
            tool_name: runtime.registry.get(tool_name)[0]
            for tool_name in (
                "tiktok_smart_plus_create_campaign",
                "tiktok_smart_plus_create_adgroup",
                "tiktok_smart_plus_create_ad",
            )
        }
        ctx = SimpleNamespace(
            account_id=account_id,
            session_id="tiktok-template-test",
            user_id="test-user",
            protected_state={},
        )
        campaign_args = runtime.input_builder.build(
            definitions["tiktok_smart_plus_create_campaign"],
            applied,
            "tiktok",
            ctx,
        )
        adgroup_args = runtime.input_builder.build(
            definitions["tiktok_smart_plus_create_adgroup"],
            applied,
            "tiktok",
            ctx,
        )
        ad_args = runtime.input_builder.build(
            definitions["tiktok_smart_plus_create_ad"],
            applied,
            "tiktok",
            ctx,
        )

        assert campaign_args["campaign_name"] == "QA TikTok 20261012"
        assert campaign_args["operation_status"] == "DISABLE"
        assert "budget" not in campaign_args
        assert adgroup_args["budget"] == 50
        assert adgroup_args["budget_mode"] == "BUDGET_MODE_TOTAL"
        assert adgroup_args["schedule_type"] == "SCHEDULE_START_END"
        assert adgroup_args["schedule_start_time"] == "2026-10-13 00:00:00"
        assert adgroup_args["schedule_end_time"] == "2026-10-15 00:00:00"
        assert adgroup_args["operation_status"] == "DISABLE"
        assert ad_args["operation_status"] == "DISABLE"
