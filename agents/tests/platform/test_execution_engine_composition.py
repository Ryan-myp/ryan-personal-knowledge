"""Scenario reuse and source scoping survive a different decision engine."""
from types import SimpleNamespace

from agents.agent_harness import StaticToolSource, ToolBinding, ToolCall
from agents.agent_platform import AgentPlatform, AgentDefinition, ScenarioDefinition
from agents.tests.harness.test_execution_engines import ScriptEngine
from agents.tests.harness.test_runtime_tool_discovery import definition


def test_scenarios_share_one_engine_but_keep_source_scope():
    invoked = []
    def script(session):
        names = [tool["name"] for tool in session.snapshot().tools]
        assert len(names) == 1
        session.call_tools([ToolCall("read", names[0], {"id": "42"})])
        session.finish(names[0])
    engine = ScriptEngine(script)
    sources = tuple(StaticToolSource(name, [ToolBinding(
        definition(f"get_{name}", name),
        lambda context, _: invoked.append(context.tool_call.name) or {"ok": True},
    )]) for name in ("one", "two"))
    platform = AgentPlatform()
    platform.register_agent(AgentDefinition(agent_id="test", tool_sources=sources))
    for name in ("one", "two"):
        platform.register_scenario(ScenarioDefinition(
            scenario_id=name, agent_id="test", tool_source_ids=(name,),
        ))
    first = platform.create_application("one", model=None, engine=engine)
    second = platform.create_application("two", model=None)
    principal = SimpleNamespace(user_id="u", tenant_id="t", permissions=("read",))
    try:
        assert first.engine is second.engine is engine
        assert first.runtime is second.runtime
        assert first.prompt("查第一个", principal=principal).reply == "get_one"
        assert second.prompt("查第二个", principal=principal).reply == "get_two"
        assert invoked == ["get_one", "get_two"]
    finally:
        first.close()
