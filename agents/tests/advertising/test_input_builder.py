from types import SimpleNamespace

from agents.agent_harness.core.interfaces import ToolContext, ToolResult
from agents.applications.advertising.execution.input_builder import ToolInputBuilder
from agents.tools.advertising.providers.google import create_google_tool_source


class _SelectionSigner:
    def issue(self, **_kwargs):
        return "signed-selection", 1_800_000_000


def test_google_asset_lookup_decorates_union_typed_selection_fields():
    definitions = [
        definition
        for definition, _handler in create_google_tool_source().register_tools()
    ]
    services = SimpleNamespace(
        registry=SimpleNamespace(list_all=lambda: definitions),
        selection_signer=_SelectionSigner(),
    )
    builder = ToolInputBuilder(
        services,
        scope_value_resolver=lambda context: context.account_id,
    )
    asset_tool = next(
        definition for definition in definitions
        if definition.name == "google_list_assets"
    )
    result = ToolResult.ok({
        "assets": [{"id": "asset-1", "name": "Logo", "type": "IMAGE"}],
        "data_status": "live",
    })

    decorated = builder.parameter_selection.decorate_lookup_result(
        asset_tool,
        result,
        ToolContext(
            session_id="asset-picker",
            user_id="test-user",
            scope={"account_id": "google-test-account"},
        ),
        "google-ads",
    )

    selection = next(
        item for item in decorated.data["parameter_selections"]
        if item["tool_name"] == "google_create_demand_gen_carousel_ad"
        and item["field"] == "logo_image"
    )
    assert selection["options"] == [{
        "value": "asset-1",
        "label": "Logo",
        "selection_token": "signed-selection",
    }]
