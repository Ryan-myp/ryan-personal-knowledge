from agents.tools.advertising.source import advertising_tool_source
from agents.agent_harness import (
    InMemoryToolCatalog,
    StaticToolSource,
    ToolBinding,
    TurnRequest,
)
from agents.agent_harness.core.interfaces import ToolDefinition, ToolSchema
from agents.agent_harness.core.tool_registry import SimpleToolRegistry
from agents.applications.advertising.composition.ad_application import (
    AdvertisingComposition,
)


class ToolSource:
    platform_name = "example"

    def register_tools(self):
        return [
            (
                {"name": "example_lookup"},
                lambda _ctx, data: {"value": data["value"]},
            )
        ]


def test_ad_tool_source_can_be_consumed_as_a_generic_tool_source():
    catalog = InMemoryToolCatalog()
    catalog.register_source(advertising_tool_source(ToolSource()))

    binding = catalog.get_binding("example_lookup")
    context = type(
        "Context",
        (),
        {
            "request": TurnRequest(
                user_input="lookup",
                session_id="session-1",
                execution_mode="dry_run",
            )
        },
    )()
    assert binding.executor.execute(context, {"value": "ok"}) == {"value": "ok"}


def test_advertising_tool_source_uses_the_standard_source_namespace():
    assert advertising_tool_source(ToolSource()).source_id == "advertising:example"


def test_registered_provider_source_is_part_of_platform_dependencies():
    definition = ToolDefinition(
        name="example_lookup",
        skill="example",
        namespace="example",
        description="Read an example",
        input_schema=ToolSchema(),
    )
    registry = SimpleToolRegistry()
    registry.register_source(
        StaticToolSource(
            "provider-module:example",
            [ToolBinding(definition, lambda *_: None)],
        )
    )
    runtime = AdvertisingComposition(
        require_llm=False,
        offline_mode=True,
        registry=registry,
    )
    sources = runtime._platform_application.dependencies.integrations.tool_sources
    assert [source.source_id for source in sources] == ["provider-module:example"]
    assert [
        tool.name for tool in runtime._platform_application.harness.tools.list_tools()
    ] == ["example_lookup"]


def test_dynamic_provider_source_updates_platform_dependency_snapshot():
    definition = ToolDefinition(
        name="dynamic_lookup",
        skill="example",
        namespace="example",
        description="Read a dynamic example",
        input_schema=ToolSchema(),
    )
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    source = StaticToolSource(
        "provider-module:dynamic",
        [ToolBinding(definition, lambda *_: None)],
    )
    runtime.register_tool_source(source)
    sources = runtime._platform_application.dependencies.integrations.tool_sources
    assert "provider-module:dynamic" in [item.source_id for item in sources]


def test_provider_publishes_standard_bindings_without_application_configuration():
    from agents.tools.advertising.providers.tiktok.provider import (
        create_tiktok_tool_source,
    )

    provider = create_tiktok_tool_source()
    assert provider.source_id == "provider-module:tiktok"
    bindings = provider.list_bindings()
    assert bindings
    assert all(binding.definition.required_permissions for binding in bindings)
    catalog = InMemoryToolCatalog()
    catalog.register_source(provider)
    assert catalog.list_tools()
