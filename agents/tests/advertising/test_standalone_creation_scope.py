from types import SimpleNamespace

import pytest
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


def test_explicit_single_tool_structured_input_survives_model_drift():
    class Runtime:
        _sessions = {}
        @staticmethod
        def _canonical_platform(value):
            return value
        input_builder = SimpleNamespace(build=lambda _tool, intent, _ns, _ctx: dict(
            intent.scoped_parameters["example"]["example_create_campaign"]
        ))
    interaction = AdvertisingToolInteractionProvider(Runtime())
    context = _context({
        "platform_params": {
            "example": {
                "example_create_campaign": {
                    "name": "QA_PAUSED",
                    "objective_type": "TRAFFIC",
                }
            }
        }
    })
    context.request.tool_allowlist = ("example_create_campaign",)
    context.request.user_input = "create"
    context.request.session_id = "test"
    context.tool_definition.input_schema.properties["objective_type"] = {"type": "string"}
    context.tool_call.arguments = {"name": "model-name", "campaign_id": "extra"}
    assert interaction.resolve_tool_arguments(context) == {
        "name": "QA_PAUSED",
        "objective_type": "TRAFFIC",
    }


def test_structured_tool_input_does_not_override_unselected_tool_or_plain_chat():
    interaction = AdvertisingToolInteractionProvider(object())
    context = _context({
        "platform_params": {
            "example": {"example_create_campaign": {"name": "structured"}}
        }
    })
    context.request.tool_allowlist = ("another_tool",)
    assert interaction.resolve_tool_arguments(context) == {"name": "QA_campaign"}
    context.request.tool_allowlist = None
    assert interaction.resolve_tool_arguments(context) == {"name": "QA_campaign"}


def test_explicit_structured_input_rejects_builder_selection_errors():
    class Runtime:
        _sessions = {}
        @staticmethod
        def _canonical_platform(value):
            return value
        input_builder = SimpleNamespace(build=lambda *_: {
            "name": "QA", "_selection_errors": ["invalid proof"],
        })
    interaction = AdvertisingToolInteractionProvider(Runtime())
    context = _context({
        "platform_params": {
            "example": {"example_create_campaign": {"name": "QA"}}
        }
    })
    context.request.tool_allowlist = ("example_create_campaign",)
    context.request.user_input = "create"
    context.request.session_id = "test"
    with pytest.raises(ValueError, match="invalid proof"):
        interaction.resolve_tool_arguments(context)


def test_explicit_blueprint_still_requires_the_selected_workflow_inputs():
    interaction = AdvertisingToolInteractionProvider(object())
    interaction._creation_ui = lambda *_: {"needs_input": True}
    assert (
        interaction.creation_input_required(
            _context({"creation_blueprint_id": "example.full"})
        )
        is True
    )


def test_singleton_structured_campaign_does_not_require_blueprint_siblings():
    interaction = AdvertisingToolInteractionProvider(object())
    interaction._creation_ui = lambda *_: {"needs_input": True}
    context = _context({
        "creation_blueprint_id": "example.full",
        "platform_params": {
            "example": {"example_create_campaign": {"name": "QA_campaign"}},
        },
    })
    context.request.tool_allowlist = ("example_create_campaign",)
    assert interaction.creation_input_required(context) is False


def test_singleton_structured_campaign_still_requires_its_own_fields():
    interaction = AdvertisingToolInteractionProvider(object())
    interaction._creation_ui = lambda *_: {"needs_input": False}
    context = _context({
        "creation_blueprint_id": "example.full",
        "platform_params": {
            "example": {"example_create_campaign": {"name": "QA_campaign"}},
        },
    })
    context.request.tool_allowlist = ("example_create_campaign",)
    context.tool_call.arguments = {}
    assert interaction.creation_input_required(context) is True


def test_template_and_structured_values_override_model_tool_suggestions():
    definition = ToolDefinition(
        name="example_create_campaign",
        skill="example",
        namespace="example",
        description="Create a campaign",
        action="create",
        resource_type="campaign",
        parent_resource_id_field="campaign_id",
        intent_types=["create_campaign"],
        input_schema=ToolSchema(
            properties={
                "name": {"type": "string"},
                "daily_budget": {"type": "number"},
                "status": {"type": "string"},
                "bidding_strategy": {"type": "string"},
                "product_dimension": {"type": "string"},
                "campaign_id": {"type": "string"},
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

    blueprint = SimpleNamespace(
        provider="example",
        selector={},
        fields=[
            {
                "path": f"campaign.{field}",
                "tool_ref": f"example_create_campaign.{field}",
            }
            for field in (
                "name",
                "daily_budget",
                "status",
                "bidding_strategy",
                "product_dimension",
            )
        ],
    )

    class Runtime:
        _sessions = {}
        input_builder = InputBuilder()
        creation_blueprints = SimpleNamespace(
            get=lambda *_args: blueprint,
        )

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
                "bidding_strategy": "MAXIMIZE_CLICKS",
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
            arguments={
                "name": "from-model",
                "daily_budget": 30,
                "status": "ENABLED",
                "bidding_strategy": "MAXIMIZE_CONVERSIONS",
                "product_dimension": "PRODUCT_TYPE",
                "campaign_id": "from-parent-tool",
            },
        ),
        tool_definition=definition,
    )
    interaction = AdvertisingToolInteractionProvider(Runtime())

    resolved = interaction.resolve_tool_arguments(context)

    assert resolved == {
        "name": "from-template",
        "status": "PAUSED",
        "daily_budget": 12,
        "bidding_strategy": "MAXIMIZE_CLICKS",
        "campaign_id": "from-parent-tool",
    }


@pytest.mark.parametrize("error_key", ["_selection_errors", "_unknown_params"])
def test_selected_template_does_not_discard_input_builder_validation_errors(error_key):
    context = _context({"creation_blueprint_id": "example.standard"})
    context.request.session_id = "validation-session"
    runtime = SimpleNamespace(
        _sessions={},
        input_builder=SimpleNamespace(
            build=lambda *_: {"name": "QA_campaign", error_key: ["invalid-input"]},
        ),
    )
    interaction = AdvertisingToolInteractionProvider(runtime)
    interaction._intent = lambda *_: (
        ParsedIntent("create_campaign", "create", ["example"]), {}, context.request.context,
    )
    with pytest.raises(ValueError, match="invalid-input"):
        interaction.resolve_tool_arguments(context)


def test_template_arguments_preserve_declared_parent_and_related_resource_bindings():
    definition = ToolDefinition(
        name="example_create_ad", namespace="example", skill="example", description="Create ad",
        action="create", resource_type="ad", parent_resource_type="ad_group",
        parent_resource_id_field="adgroup_id", related_resource_type="campaign",
        related_resource_id_fields=["campaign_id"],
        input_schema=ToolSchema(properties={
            "name": {"type": "string"}, "campaign_id": {"type": "string"},
            "adgroup_id": {"type": "string"},
        }),
    )
    context = SimpleNamespace(
        request=SimpleNamespace(
            session_id="chain", context={"creation_blueprint_id": "example.chain"},
        ),
        tool_definition=definition,
        tool_call=SimpleNamespace(arguments={
            "campaign_id": "created-campaign", "adgroup_id": "created-group",
            "name": "model-name", "undeclared_id": "must-not-survive",
        }),
    )
    runtime = SimpleNamespace(
        _sessions={},
        input_builder=SimpleNamespace(build=lambda *_: {"name": "template-name"}),
    )
    interaction = AdvertisingToolInteractionProvider(runtime)
    interaction._intent = lambda *_: (
        ParsedIntent("create_campaign", "create", ["example"]), {}, context.request.context,
    )
    assert interaction.resolve_tool_arguments(context) == {
        "name": "template-name", "campaign_id": "created-campaign", "adgroup_id": "created-group",
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


def test_pmax_retail_setting_does_not_require_shopping_campaign_priority():
    tool = next(
        binding.definition
        for binding in create_tool_source("google-ads").list_bindings()
        if binding.definition.name == "google_create_campaign"
    )
    base = {
        "customer_id": "test",
        "campaign_name": "QA_PMAX",
        "advertising_channel_type": "PERFORMANCE_MAX",
        "bidding_strategy": "MAXIMIZE_CONVERSION_VALUE",
        "daily_budget": 5,
        "status": "PAUSED",
        "contains_eu_political_advertising": (
            "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING"
        ),
        "shopping_setting": {
            "merchant_id": 115791065,
            "enable_local": True,
        },
    }

    assert validate_tool_input(
        tool.input_schema,
        base,
        include_tool_requirements=True,
    ) == []

    shopping = {
        **base,
        "advertising_channel_type": "SHOPPING",
    }
    errors = validate_tool_input(
        tool.input_schema,
        shopping,
        include_tool_requirements=True,
    )
    assert any("shopping_setting.campaign_priority" in error for error in errors)
