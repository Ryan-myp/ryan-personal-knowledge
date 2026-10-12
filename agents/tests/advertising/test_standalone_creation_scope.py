from types import SimpleNamespace

from agents.agent_harness.core.interfaces import ParsedIntent, ToolDefinition, ToolSchema
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


def test_selected_creation_template_is_materialized_into_declared_tool_arguments():
    definition = ToolDefinition(
        name="example_create_campaign",
        skill="example",
        namespace="example",
        description="Create a campaign",
        action="create",
        resource_type="campaign",
        intent_types=["create_campaign"],
        input_schema=ToolSchema(
            properties={
                "name": {"type": "string"},
                "daily_budget": {"type": "number"},
                "status": {"type": "string"},
            }
        ),
    )
    request_context = {
        "account_id": "test-account",
        "creation_blueprint_id": "example.standard",
        "creation_template_id": "template-1",
        "platform_params": {
            "example": {
                "example_create_campaign": {"daily_budget": 12},
            }
        },
    }

    class InputBuilder:
        @staticmethod
        def build(_tool, intent, _namespace, _session_context):
            return dict(
                intent.scoped_parameters["example"]["example_create_campaign"]
            )

    class Runtime:
        _sessions = {}
        input_builder = InputBuilder()
        creation_blueprints = SimpleNamespace(get=lambda *_args: None)

        @staticmethod
        def _canonical_platform(value):
            return str(value).lower()

        @staticmethod
        def apply_creation_template_to_intent(intent, _template_id, **_kwargs):
            values = dict(intent.scoped_parameters["example"])
            values["example_create_campaign"] = {
                **dict(values.get("example_create_campaign") or {}),
                "name": "from-template",
                "status": "PAUSED",
                "not_in_schema": "must-not-reach-tool",
            }
            return ParsedIntent(
                intent.intent_type,
                intent.raw_input,
                intent.namespaces,
                scoped_parameters={"example": values},
                metadata=dict(intent.metadata),
            )

    context = SimpleNamespace(
        request=SimpleNamespace(
            context=request_context,
            user_input="create with template",
            principal=SimpleNamespace(account_scope=None),
            tenant_id="test-tenant",
            user_id="test-user",
            session_id="test-session",
        ),
        tool_call=SimpleNamespace(
            arguments={"daily_budget": 30},
        ),
        tool_definition=definition,
    )
    interaction = AdvertisingToolInteractionProvider(Runtime())

    resolved = interaction.resolve_tool_arguments(context)

    assert resolved == {
        "name": "from-template",
        "status": "PAUSED",
        "daily_budget": 30,
    }


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
