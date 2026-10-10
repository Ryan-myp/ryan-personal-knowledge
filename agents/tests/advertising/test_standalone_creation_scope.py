from types import SimpleNamespace

from agents.agent_harness.core.interfaces import ToolDefinition, ToolSchema
from agents.applications.advertising.execution.ad_tool_interaction import (
    AdvertisingToolInteractionProvider,
)
from agents.agent_harness.core.tool_registry import validate_tool_input
from agents.tools.advertising.providers.source_factory import create_tool_source


def _context(values):
    tool = ToolDefinition(
        name="example_create_campaign",
        skill="example",
        namespace="example",
        description="Create a campaign",
        action="create",
        resource_type="campaign",
        input_schema=ToolSchema(
            required=["name"], properties={"name": {"type": "string"}}
        ),
    )
    return SimpleNamespace(
        tool_definition=tool,
        tool_call=SimpleNamespace(arguments={"name": "QA_campaign"}),
        request=SimpleNamespace(context=values),
    )


def test_valid_standalone_tool_does_not_require_sibling_blueprint_fields():
    interaction = AdvertisingToolInteractionProvider(object())
    interaction._creation_ui = lambda *_: {"needs_input": True}
    assert interaction.creation_input_required(_context({})) is False


def test_explicit_blueprint_still_requires_the_selected_workflow_inputs():
    interaction = AdvertisingToolInteractionProvider(object())
    interaction._creation_ui = lambda *_: {"needs_input": True}
    assert (
        interaction.creation_input_required(
            _context({"creation_blueprint_id": "example.full"})
        )
        is True
    )


def test_standalone_missing_parameter_does_not_open_a_campaign_type_selector():
    interaction = AdvertisingToolInteractionProvider(object())
    expected = {
        "type": "action_clarification",
        "payload": {"missing_fields": ["schedule_start_time"]},
    }
    interaction._action_interaction = lambda *_: expected
    interaction._creation_ui = lambda *_: {"cards": [{"type": "ad_creation_selector"}]}
    ctx = _context({})
    ctx.tool_definition.resource_type = "ad_group"
    assert interaction._creation_interaction(ctx, ctx.tool_definition) == expected


def test_pmax_campaign_does_not_require_optional_optimization_goals():
    tool = next(
        b.definition
        for b in create_tool_source("google-ads").list_bindings()
        if b.definition.name == "google_create_campaign"
    )
    values = {
        "customer_id": "test",
        "campaign_name": "QA_PMAX",
        "advertising_channel_type": "PERFORMANCE_MAX",
        "bidding_strategy": "MAXIMIZE_CONVERSION_VALUE",
        "daily_budget": 5,
        "status": "PAUSED",
        "brand_guidelines_enabled": False,
        "contains_eu_political_advertising": "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING",
    }
    assert validate_tool_input(tool.input_schema, values) == []
