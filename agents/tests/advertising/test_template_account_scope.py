"""All template mutations must respect the same scope as reads."""

import pytest

from agents.applications.advertising.creation.templates import CreationTemplateError, CreationTemplateManager
from agents.applications.advertising.persistence.store import AdAgentStore


@pytest.fixture
def templates():
    store = AdAgentStore(":memory:")
    blueprint = {"id": "demo", "provider": "meta", "version": "1.0.0", "ad_format": "TRAFFIC",
                 "fields": [{"path": "campaign.name"}]}
    manager = CreationTemplateManager(store, lambda *_: blueprint)
    saved = manager.create("tenant", "user", {
        "name": "Private", "blueprint_id": "demo", "scope_type": "account",
        "account_id": "account-a", "values": {"campaign.name": "Private name"},
    })
    manager.allowed_accounts = {"meta": {"account-a", "account-b"}}
    manager.account_scope = {"meta": {"account-b"}}
    yield manager, saved
    store.close()


@pytest.mark.parametrize("operation", ["update", "delete", "duplicate", "apply"])
def test_removed_account_scope_cannot_be_bypassed_by_mutation(templates, operation):
    manager, saved = templates
    args = ["tenant", "user", saved["template_id"]]
    if operation == "update":
        args.append({"name": "Changed", "account_id": "account-b"})
    assert manager.get(*args[:3]) is None
    assert getattr(manager, operation)(*args) is None
    stored = manager.store.get_creation_template(saved["template_id"], tenant_id="tenant", user_id="user")
    assert stored.name == "Private"
    assert stored.account_id == "account-a"
    assert stored.usage_count == 0
    assert len(manager.store.list_creation_templates("tenant", "user")) == 1


@pytest.mark.parametrize("scope_type", ["account", "general", "region"])
def test_create_checks_any_bound_account_not_just_scope_label(templates, scope_type):
    manager, _ = templates
    with pytest.raises(CreationTemplateError, match="账户"):
        manager.create("tenant", "user", {
            "name": "Denied", "blueprint_id": "demo", "scope_type": scope_type,
            "region": "US", "account_id": "account-a", "values": {},
        })
    assert len(manager.store.list_creation_templates("tenant", "user")) == 1


def test_visible_template_cannot_be_rebound_to_inaccessible_account(templates):
    manager, saved = templates
    manager.account_scope = {"meta": {"account-a"}}
    with pytest.raises(CreationTemplateError, match="账户"):
        manager.update("tenant", "user", saved["template_id"], {"account_id": "account-b"})
    assert manager.get("tenant", "user", saved["template_id"])["account_id"] == "account-a"


def test_in_scope_template_and_unbound_general_draft_still_work(templates):
    manager, saved = templates
    manager.account_scope = {"meta": {"account-a"}}
    assert manager.update("tenant", "user", saved["template_id"], {"name": "Updated"})["name"] == "Updated"
    assert manager.apply("tenant", "user", saved["template_id"])["usage_count"] == 1
    assert manager.duplicate("tenant", "user", saved["template_id"])["template_id"] != saved["template_id"]
    general = manager.create("tenant", "user", {
        "name": "General", "blueprint_id": "demo", "scope_type": "general", "values": {},
    })
    assert general["account_id"] == ""
    assert manager.delete("tenant", "user", saved["template_id"])
