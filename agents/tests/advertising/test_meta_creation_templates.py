"""Meta demo templates must be complete, paused, and account-scoped."""

import shutil
import subprocess
from pathlib import Path

import pytest

from agents.agent_harness import TurnRequest
from agents.agent_harness.core.interfaces import ParsedIntent
from agents.agent_harness.core.tool_selection import ToolSelector
from agents.applications.advertising.composition.ad_application import AdvertisingComposition
from agents.applications.advertising.composition.ad_application_assembly import AdApplicationAssembly
from agents.applications.advertising.creation.templates import load_builtin_template_definitions
from agents.applications.advertising.integrations.integration import AdvertisingContextProvider
from agents.applications.advertising.persistence.store import AdAgentStore
from agents.agent_platform.governance.identity.principal import RequestPrincipal
from agents.tools.advertising.providers.meta import create_meta_tool_source


ACCOUNT = "2806375919473667"
USER_FIELDS = {
    "campaign.name", "campaign.daily_budget",
    "ad_set.start_time", "ad_set.end_time",
}
TEMPLATE_KEYS = (
    "meta.test.traffic", "meta.test.catalog-sales",
    "meta.test.conversion", "meta.test.app-promotion",
)


@pytest.fixture
def runtime():
    owner = AdvertisingComposition(
        require_llm=False, offline_mode=True,
        persistence_store=AdAgentStore(":memory:"), start_background_workers=False,
    )
    owner.whitelist_validator.allowed_accounts = {"meta": [ACCOUNT]}
    owner.register_tool_source(create_meta_tool_source())
    yield owner
    owner.close(wait=True)


@pytest.mark.parametrize("key", TEMPLATE_KEYS)
def test_meta_template_only_requires_name_schedule_and_budget(runtime, key):
    template = next(row for row in load_builtin_template_definitions() if row["key"] == key)
    assert template["account_id"] == ACCOUNT
    assert set(template.get("required_input_fields") or ()) == USER_FIELDS
    assert len(template["required_inputs"]) == 4
    values = template["values"]
    assert USER_FIELDS.isdisjoint(values)
    assert all(values[f"{resource}.status"] == "PAUSED" for resource in ("campaign", "ad_set", "ad"))

    scope = {"meta": {ACCOUNT}}
    manager = runtime._creation_template_manager_for_request(scope)
    template_id = manager._builtin_id(template)
    intent = runtime.apply_creation_template_to_intent(
        ParsedIntent("create_campaign", "使用模板创建暂停广告", ["meta"]),
        template_id, account_id=ACCOUNT, account_scope=scope,
    )
    card = runtime.build_creation_ui(
        intent, account_id=ACCOUNT, account_scope=scope,
    )["cards"][0]
    assert set(card["user_input_fields"]) == USER_FIELDS
    fields = {field["path"]: field for field in card["fields"]}
    for path in USER_FIELDS:
        assert fields[path]["user_required"] is True, (key, path)
    for path, value in values.items():
        assert fields[path]["value"] == value, (key, path)
        assert fields[path]["user_required"] is False, (key, path)


@pytest.mark.parametrize("key", TEMPLATE_KEYS)
def test_meta_template_preserves_explicit_form_values_and_paused_children(runtime, key):
    template = next(row for row in load_builtin_template_definitions() if row["key"] == key)
    scope = {"meta": {ACCOUNT}}
    template_id = runtime._creation_template_manager_for_request(scope)._builtin_id(template)
    overrides = {
        "campaign.name": "QA_META_TEMPLATE_EXPLICIT",
        "campaign.daily_budget": 30,
        "ad_set.start_time": "2026-10-18T00:00:00+08:00",
        "ad_set.end_time": "2026-10-20T23:59:59+08:00",
    }
    intent = runtime.apply_creation_template_to_intent(
        ParsedIntent(
            "create_campaign", "提交创建计划", ["meta"],
            scoped_parameters={"meta": overrides},
        ),
        template_id, account_id=ACCOUNT, account_scope=scope,
    )
    params = intent.scoped_parameters["meta"]
    assert params["meta_create_campaign"]["name"] == overrides["campaign.name"]
    assert params["meta_create_campaign"]["daily_budget"] == 30
    assert params["meta_create_adset"]["start_time"] == overrides["ad_set.start_time"]
    assert params["meta_create_adset"]["end_time"] == overrides["ad_set.end_time"]
    for name in runtime.creation_blueprints.get(template["blueprint_id"]).tools:
        assert params[name]["status"] == "PAUSED"


@pytest.mark.parametrize("key", TEMPLATE_KEYS)
def test_live_template_exposes_only_creation_tools_and_declared_same_channel_lookups(runtime, key):
    template = next(row for row in load_builtin_template_definitions() if row["key"] == key)
    blueprint = runtime.creation_blueprints.get(template["blueprint_id"])
    request = TurnRequest(
        user_input="使用模板创建暂停广告",
        execution_mode="live",
        context={
            "creation_blueprint_id": blueprint.blueprint_id,
            "creation_blueprint_version": blueprint.version,
            "creation_template_id": "selected-template",
        },
    )
    selected = AdApplicationAssembly._tool_selector(runtime, ToolSelector())(
        request, runtime.registry.list_all(),
    )
    names = {tool.name for tool in selected}
    assert set(blueprint.tools) <= names
    assert "meta_list_pages" in names
    if key != "meta.test.catalog-sales":
        assert "meta_list_image_assets" in names
    else:
        assert {"meta_list_catalogs", "meta_list_product_sets"} <= names
    assert {tool.namespace for tool in selected} == {"meta"}
    assert all(tool.is_read_tool for tool in selected if tool.name not in blueprint.tools)
    assert not ({"meta_list_campaigns", "meta_get_report", "meta_create_creative"} & names)
    assert "agent_web_search" not in names
    assert len(selected) <= 32


def test_template_context_lists_every_prefilled_asset_that_requires_a_live_lookup(runtime):
    template = next(row for row in runtime.list_creation_templates(
        provider="meta", account_id=ACCOUNT,
    ) if row["catalog_key"] == "meta.test.traffic")
    request = TurnRequest(
        user_input="使用流量模板", user_id="anonymous",
        principal=RequestPrincipal(
            user_id="anonymous", tenant_id="default",
            permissions=frozenset({"ads.read", "ads.plan"}),
            account_scope={"meta": {ACCOUNT}},
        ),
    )
    context = AdvertisingContextProvider(runtime)._creation_selection({
        "account_id": ACCOUNT, "creation_template_id": template["template_id"],
        "creation_blueprint_id": template["blueprint_id"],
    }, request)
    requirements = {
        item["field"]: item for item in context.get("resource_lookup_requirements", ())
        if item["tool"] == "meta_create_traffic_ad"
    }
    assert requirements["page_id"]["value"] == template["values"]["ad.page_id"]
    assert requirements["page_id"]["lookup_tool"] == "meta_list_pages"
    assert requirements["image_hash"]["value"] == template["values"]["ad.image_hash"]
    assert requirements["image_hash"]["lookup_tool"] == "meta_list_image_assets"


def test_app_template_store_links_match_the_app_creative_https_contract():
    template = next(row for row in load_builtin_template_definitions() if row["key"] == "meta.test.app-promotion")
    values = template["values"]
    urls = [
        values["ad.object_store_url"],
        values["ad_set.promoted_object.object_store_url"],
        values["ad_set.promoted_object"]["object_store_url"],
    ]
    assert all(url.startswith("https://play.google.com/store/apps/details?") for url in urls)
    assert len(set(urls)) == 1


@pytest.mark.parametrize("key", TEMPLATE_KEYS)
def test_demo_templates_explicitly_preserve_the_selected_audience_automation(key):
    template = next(row for row in load_builtin_template_definitions() if row["key"] == key)
    assert template["values"]["ad_set.targeting"]["targeting_automation"][
        "advantage_audience"
    ] == (1 if key == "meta.test.traffic" else 0)


@pytest.mark.parametrize("key", TEMPLATE_KEYS)
def test_verified_meta_templates_record_the_complete_paused_hierarchy_scope(key):
    template = next(row for row in load_builtin_template_definitions() if row["key"] == key)
    assert template["verification_status"] == "live_verified"
    assert "Creative" in template["verified_scope"]
    assert "2026-10-15" in template["verified_scope"]


def test_template_hydration_frontend_regression():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for frontend regressions")
    result = subprocess.run(
        [node, "--test", str(Path(__file__).parent / "static/test_template_hydration.js")],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
