"""Tests for account-aware, data-only creation templates."""

import pytest
import glob
from fastapi.testclient import TestClient

from agents.ad_agent import api_server
from agents.ad_agent.creation_templates import (
    CreationTemplateError,
    CreationTemplateManager,
    load_builtin_template_definitions,
)
from agents.ad_agent.persistence.store import AdAgentStore
from agents.ad_agent.domain.ad.blueprint import load_blueprint_file


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


def test_template_rejects_unknown_or_sensitive_fields():
    templates = manager()
    with pytest.raises(CreationTemplateError, match="不支持的字段"):
        templates.create("tenant-a", "user-a", payload(values={"not_in_blueprint": "x"}))
    with pytest.raises(CreationTemplateError, match="凭证"):
        templates.create(
            "tenant-a", "user-a",
            payload(values={"campaign.objective": {"access_token": "secret"}}),
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
    assert len(definitions) == 11
    assert {item["provider"] for item in definitions} == {
        "meta", "google-ads", "tiktok", "dv360",
    }
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


def test_builtin_template_http_catalog_uses_runtime_whitelist(monkeypatch):
    blueprint_paths = glob.glob("agents/ad_agent/tools/providers/*/blueprints/*.json")
    blueprints = {
        load_blueprint_file(path).blueprint_id: load_blueprint_file(path)
        for path in blueprint_paths
    }

    class Registry:
        def get(self, blueprint_id, version=None):
            blueprint = blueprints.get(blueprint_id)
            return blueprint if blueprint and (
                version is None or version == blueprint.version
            ) else None

    class Validator:
        allowed_accounts = {
            "meta": ["2806375919473667"],
            "google-ads": ["9055507554"],
            "tiktok": ["7397068114548195329"],
            "dv360": ["5110831"],
        }

    class Runtime:
        persistence_store = AdAgentStore(":memory:")
        creation_blueprints = Registry()
        creation_card_builder = None
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
        assert len(templates) == 11
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
