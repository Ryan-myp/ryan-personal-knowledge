from types import SimpleNamespace

from agents.applications.advertising.integrations.integration import AdvertisingContextProvider


def test_selected_template_presets_are_visible_to_the_model_in_the_authorized_scope():
    seen = {}
    blueprint = SimpleNamespace(
        blueprint_id="example.complete", version="1.0.0", provider="example",
        title="Complete hierarchy", ad_format="EXAMPLE", tools=["example_create"],
    )

    def get(_tenant, _user, _template, **kwargs):
        seen.update(kwargs)
        return {"values": {
            "child.name": "Preset child",
            "child.headlines": [{"text": "Preset headline"}],
        }}

    owner = SimpleNamespace(
        creation_blueprints=SimpleNamespace(get=lambda *_: blueprint),
        _creation_template_manager_for_request=lambda _scope: SimpleNamespace(get=get),
        _redact_for_persistence=lambda value: value,
    )
    request = SimpleNamespace(
        user_id="operator", tenant_id="tenant",
        principal=SimpleNamespace(account_scope={"example": {"test-account"}}),
    )
    selection = AdvertisingContextProvider(owner)._creation_selection({
        "creation_blueprint_id": "example.complete", "creation_template_id": "preset",
        "account_id": "test-account",
    }, request)
    assert selection["preset_values"]["child.name"] == "Preset child"
    assert selection["preset_values"]["child.headlines"] == [{"text": "Preset headline"}]
    assert seen["account_id"] == "test-account"
    assert seen["account_scope"] == {"example": {"test-account"}}


def test_unavailable_template_does_not_supply_model_presets():
    blueprint = SimpleNamespace(
        blueprint_id="example.complete", version="1.0.0", provider="example",
        title="Complete hierarchy", ad_format="EXAMPLE", tools=["example_create"],
    )
    owner = SimpleNamespace(
        creation_blueprints=SimpleNamespace(get=lambda *_: blueprint),
        _creation_template_manager_for_request=lambda _scope: SimpleNamespace(get=lambda *_a, **_k: None),
    )
    request = SimpleNamespace(
        user_id="operator", tenant_id="tenant",
        principal=SimpleNamespace(account_scope={"example": set()}),
    )
    selection = AdvertisingContextProvider(owner)._creation_selection({
        "creation_blueprint_id": "example.complete", "creation_template_id": "outside",
        "account_id": "test-account",
    }, request)
    assert selection["available"] is False
    assert "preset_values" not in selection
