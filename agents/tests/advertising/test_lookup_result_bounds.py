from agents.agent_harness.core.interfaces import ToolContext, ToolResult
from agents.applications.advertising.composition.ad_application import (
    AdvertisingComposition,
)
from agents.tools.advertising.providers.source_factory import create_tool_source


def test_large_query_retains_business_rows_but_bounds_picker_options():
    app = AdvertisingComposition(require_llm=False, offline_mode=True)
    app.register_tool_source(create_tool_source("google-ads"))
    tool, _ = app.registry.get("google_list_campaigns")
    result = ToolResult.ok(
        {
            "data_status": "live",
            "campaigns": [{"id": str(i), "name": f"Campaign {i}"} for i in range(150)],
        }
    )
    context = ToolContext(
        session_id="test", user_id="test", scope={"account_id": "test"}
    )
    try:
        decorated = app.input_builder.parameter_selection.decorate_lookup_result(
            tool, result, context, "google-ads"
        )
        assert len(decorated.data["campaigns"]) == 150
        assert all(
            len(item["options"]) <= 20
            for item in decorated.data["parameter_selections"]
        )
    finally:
        app.close()
