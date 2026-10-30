"""Upgrades preview a new draft; old templates and proof never change in place."""

from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from agents.agent_platform.governance.identity.principal import RequestPrincipal
from agents.applications.advertising.creation.templates import (
    CreationTemplateError, CreationTemplateManager,
)
from agents.applications.advertising.persistence.store import AdAgentStore
from agents.deployments.advertising.api.context import ApiContext
from agents.deployments.advertising.api.routes.catalog import create_catalog_router
from agents.tools.advertising.shared.domain.blueprint import AdCreationBlueprint


@pytest.fixture
def manager():
    old = {
        "id": "demo.traffic", "provider": "meta", "version": "1.0.0",
        "ad_format": "TRAFFIC", "title": "Traffic", "tools": ["create"],
        "fields": [
            {"path": "campaign.name", "tool_ref": "create.name"},
            {"path": "campaign.old", "tool_ref": "create.old"},
        ], "rules": [],
    }
    latest = {
        **old, "version": "1.1.0",
        "fields": [
            {"path": "campaign.name", "tool_ref": "create.name"},
            {"path": "campaign.goal", "tool_ref": "create.goal", "required": True,
             "options": ["TRAFFIC", "LEADS"]},
        ],
    }
    store = AdAgentStore(":memory:")
    value = CreationTemplateManager(
        store, lambda identifier, version=None: deepcopy(
            {"1.0.0": old, "1.1.0": latest}.get(version or "1.1.0")
        ) if identifier == old["id"] else None,
    )
    yield value
    store.close()


def save(manager):
    return manager.create("tenant", "user", {
        "name": "My template", "blueprint_id": "demo.traffic",
        "blueprint_version": "1.0.0", "values": {
            "campaign.name": "Do not overwrite", "campaign.old": "old parameter",
        },
    })


def test_preview_preserves_original_and_reports_removed_and_required_fields(manager):
    saved = save(manager)
    preview = manager.preview_upgrade("tenant", "user", saved["template_id"])
    assert preview["preview_only"] is True
    assert preview["source_version"] == "1.0.0"
    assert preview["target_version"] == "1.1.0"
    assert preview["removed_fields"] == ["campaign.old"]
    assert "campaign.goal" in preview["missing_fields"]
    assert preview["values"] == {"campaign.name": "Do not overwrite"}
    assert manager.get("tenant", "user", saved["template_id"])["values"] == saved["values"]
    assert len(manager.list("tenant", "user")) == 1


def test_upgrade_preview_is_tenant_user_and_account_scoped(manager):
    saved = save(manager)
    assert manager.preview_upgrade("other", "user", saved["template_id"]) is None
    assert manager.preview_upgrade("tenant", "other", saved["template_id"]) is None


def test_blueprint_version_cannot_silently_change_in_place(manager):
    saved = save(manager)
    with pytest.raises(CreationTemplateError, match="升级|新模板"):
        manager.update("tenant", "user", saved["template_id"], {
            "blueprint_version": "1.1.0", "values": {"campaign.name": "new"},
        })
    assert manager.get("tenant", "user", saved["template_id"])["blueprint_version"] == "1.0.0"


def test_new_version_is_saved_separately_without_inheriting_verification(manager):
    saved = save(manager)
    preview = manager.preview_upgrade("tenant", "user", saved["template_id"])
    upgraded = manager.create("tenant", "user", {
        **preview["draft"], "name": "Upgraded",
        "values": {**preview["values"], "campaign.goal": "TRAFFIC"},
        "verification_status": "live_verified",
    })
    assert upgraded["template_id"] != saved["template_id"]
    assert upgraded["blueprint_version"] == "1.1.0"
    assert upgraded.get("verification_status") != "live_verified"
    assert manager.get("tenant", "user", saved["template_id"])["blueprint_version"] == "1.0.0"


def test_missing_target_version_and_non_newer_version_are_rejected(manager):
    saved = save(manager)
    for version in ("9.0.0", "1.0.0"):
        with pytest.raises(CreationTemplateError):
            manager.preview_upgrade("tenant", "user", saved["template_id"], version)


@pytest.fixture
def http(manager):
    identity = SimpleNamespace(principal=RequestPrincipal(
        user_id="user", tenant_id="tenant", permissions=frozenset({"ads.read", "ads.plan"}),
    ))

    def authorize(key, _request):
        if key != "test-key":
            raise HTTPException(401, "authentication required")
        return identity.principal

    def permission(principal, name):
        if name not in principal.permissions:
            raise HTTPException(403, "forbidden")

    def blueprint(identifier, version):
        data = manager.blueprint_getter(identifier, version)
        return AdCreationBlueprint.from_dict(data) if data else None

    runtime = SimpleNamespace(
        creation_blueprints=SimpleNamespace(get=blueprint),
        creation_card_builder=SimpleNamespace(expand_blueprint=lambda bp: bp),
        _creation_blueprint_support=lambda bp: {},
    )
    context = ApiContext(
        runtime_getter=lambda: runtime, authorize_request=authorize, require_permission=permission,
        activate_tenant_skills=lambda _: None, sync_tenant_extensions=lambda _: None,
        safe_exception_text=str, redact=lambda value: value,
        creation_template_manager_getter=lambda _: manager,
    )
    app = FastAPI()
    app.include_router(create_catalog_router(context))
    with TestClient(app, headers={"X-API-Key": "test-key"}) as client:
        yield client, identity


def test_upgrade_api_checks_permission_identity_and_leaves_storage_unchanged(manager, http):
    saved = save(manager)
    client, identity = http
    url = f"/creation-templates/{saved['template_id']}/upgrade-preview"
    assert client.post(url, json={}).status_code == 200
    assert len(manager.list("tenant", "user")) == 1
    assert client.post(url, json={"target_version": "9.0.0"}).status_code == 422
    assert client.post(url, json={"user_id": "other"}).status_code == 422
    assert client.post(url, json={}, headers={"X-API-Key": ""}).status_code == 401
    identity.principal = replace(identity.principal, tenant_id="foreign")
    assert client.post(url, json={}).status_code == 404
    identity.principal = replace(identity.principal, tenant_id="tenant", user_id="other")
    assert client.post(url, json={}).status_code == 404
    identity.principal = replace(identity.principal, user_id="user", permissions=frozenset({"ads.read"}))
    assert client.post(url, json={}).status_code == 403


def test_exact_blueprint_endpoint_rejects_missing_version_and_requires_read(http):
    client, identity = http
    url = "/creation-blueprints/demo.traffic"
    response = client.get(url, params={"version": "1.0.0"})
    assert response.status_code == 200
    assert response.json()["blueprint"]["version"] == "1.0.0"
    assert client.get(url, params={"version": "9.0.0"}).status_code == 404
    assert client.get(url).status_code == 422
    assert client.get(url, params={"version": "1.0.0"},
                      headers={"X-API-Key": ""}).status_code == 401
    identity.principal = replace(identity.principal, permissions=frozenset())
    assert client.get(url, params={"version": "1.0.0"}).status_code == 403


def test_upgrade_api_respects_account_scope(manager, http):
    saved = manager.create("tenant", "user", {
        "name": "Scoped", "blueprint_id": "demo.traffic", "blueprint_version": "1.0.0",
        "scope_type": "account", "account_id": "test-account", "values": {},
    })
    client, _ = http
    manager.account_scope = {"meta": set()}
    assert client.post(f"/creation-templates/{saved['template_id']}/upgrade-preview",
                       json={}).status_code == 404


def test_upgrade_checks_nested_target_contract_without_discarding_original_value(manager):
    from agents.applications.advertising.creation.template_upgrade import preview_template_upgrade
    saved = save(manager)
    saved["values"]["campaign.name"] = {"old_shape": True}
    source = manager.blueprint_getter("demo.traffic", "1.0.0")
    target = manager.blueprint_getter("demo.traffic", "1.1.0")
    preview = preview_template_upgrade(
        saved, source, target,
        field_schema_getter=lambda ref: {"type": "object", "additionalProperties": False,
            "required": ["text"], "properties": {"text": {"type": "string"}}},
    )
    assert "campaign.name" in preview["invalid_fields"]
    assert preview["values"]["campaign.name"] == {"old_shape": True}
