from agents.ad_agent.integration import capability_tool_source
from agents.agent_harness import InMemoryToolCatalog, TurnRequest


class Capability:
    platform_name = "example"

    def register_tools(self):
        return [
            (
                {"name": "example_lookup"},
                lambda _ctx, data: {"value": data["value"]},
            )
        ]


def test_ad_capability_can_be_consumed_as_a_generic_tool_source():
    catalog = InMemoryToolCatalog()
    catalog.register_source(capability_tool_source(Capability()))

    binding = catalog.get_binding("example_lookup")
    context = type("Context", (), {
        "request": TurnRequest(
            user_input="lookup",
            session_id="session-1",
            execution_mode="dry_run",
        )
    })()
    assert binding.executor.execute(context, {"value": "ok"}) == {"value": "ok"}
