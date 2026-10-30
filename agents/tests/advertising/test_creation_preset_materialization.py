"""Every generic preset must materialize a valid partial conversation draft."""

import pytest

from agents.agent_harness.core.interfaces import ParsedIntent
from agents.applications.advertising.creation.templates import (
    creation_template_manager_for_runtime, load_builtin_template_definitions,
)
from agents.tools.advertising.shared.domain.creation_card import _safe_default
from scripts.advertising.audit_creation_contracts import build_runtime


PRESETS = [
    row for row in load_builtin_template_definitions()
    if row.get("scope_type") == "general" and not row.get("catalog_hidden")
    and row["provider"] in {"meta", "tiktok", "google-ads"}
]


@pytest.fixture(scope="module")
def runtime():
    value = build_runtime()
    for provider in ("meta", "tiktok", "google-ads"):
        value.whitelist_validator.allowed_accounts[provider] = ["offline-account"]
    yield value
    value.close(wait=True)


@pytest.mark.parametrize("preset", PRESETS, ids=lambda row: row["key"])
def test_generic_preset_materializes_without_invalid_defaults(runtime, preset):
    manager = creation_template_manager_for_runtime(runtime)
    saved = next(row for row in manager.list("test", "test", source="builtin", limit=200)
                 if row["catalog_key"] == preset["key"])
    provider = preset["provider"]
    scope = {provider: ["offline-account"]}
    intent = runtime.apply_creation_template_to_intent(
        ParsedIntent("create_campaign", "Create from preset", [provider]),
        saved["template_id"], account_id="offline-account", account_scope=scope,
        tenant_id="test", user_id="test",
    )
    ui = runtime.build_creation_ui(
        intent, account_id="offline-account", account_scope=scope,
        tenant_id="test", user_id="test",
    )
    card = next(item for item in ui["cards"] if item.get("blueprint_id") == preset["blueprint_id"])
    assert card["type"] == "ad_creation_form"
    assert card["blueprint_version"] == preset["blueprint_version"]
    assert card["invalid_fields"] == []
    assert not [field for field in card["fields"] if field.get("validation_errors")]


def test_empty_evaluated_options_never_fall_back_to_full_schema_enum():
    intent = ParsedIntent("create_campaign", "Create", ["example"])
    field = {"path": "ad.optimization_goal", "tool_ref": "create.optimization_goal"}
    schema = {"type": "string", "enum": ["CONVERT", "CLICK"]}
    assert _safe_default(intent, {}, field, schema, options_override=[])[0] is None


def test_conditional_default_waits_for_evaluated_options():
    intent = ParsedIntent("create_campaign", "Create", ["example"])
    field = {
        "path": "ad.optimization_goal", "tool_ref": "create.optimization_goal",
        "option_rules": [{"when": {"field": "campaign.goal", "equals": "CLICKS"}, "options": ["CLICK"]}],
    }
    schema = {"type": "string", "enum": ["CONVERT", "CLICK"]}
    assert _safe_default(intent, {}, field, schema)[0] is None
    assert _safe_default(intent, {}, field, schema, options_override=["CLICK"])[0] == "CLICK"
