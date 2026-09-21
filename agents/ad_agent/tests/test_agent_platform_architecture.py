"""Contract tests for the six-layer Agent Platform architecture."""

import ast
from pathlib import Path

import pytest

from agents.agent_harness import StaticSkillSource, StaticToolSource, ToolBinding
from agents.agent_platform import (
    AgentDefinition,
    AgentPlatform,
    PlatformLayer,
    ScenarioDefinition,
)
from agents.agent_platform.runtime import (
    DataLayer,
    InfrastructureLayer,
    PlatformApplication,
    PlatformDependencies,
)
from agents.agent_platform.tools.policy import ToolExecutionPolicy


def _sources():
    skills = StaticSkillSource("skill:general", [])
    tools = StaticToolSource("tool:general", [])
    return skills, tools


def test_platform_exposes_the_six_primary_layers_and_cross_cutting_concerns():
    assert tuple(layer.value for layer in PlatformLayer) == (
        "application_scenarios",
        "agents",
        "core",
        "data",
        "integrations",
        "infrastructure",
    )

    platform = AgentPlatform()
    architecture = platform.architecture
    assert architecture.layer_names() == tuple(layer.value for layer in PlatformLayer)
    assert "governance_operations" in architecture.cross_cutting
    assert "agent_market" in architecture.cross_cutting


def test_platform_is_single_agent_with_multiple_scenarios():
    skills, tools = _sources()
    platform = AgentPlatform()
    platform.register_agent(AgentDefinition(
        agent_id="default-agent",
        display_name="General Agent",
        skill_sources=(skills,),
        tool_sources=(tools,),
    ))
    platform.register_scenario(ScenarioDefinition(
        scenario_id="knowledge-qa",
        agent_id="default-agent",
    ))
    platform.register_scenario(ScenarioDefinition(
        scenario_id="marketing-assistant",
        agent_id="default-agent",
    ))

    assert platform.agent_id == "default-agent"
    assert len(platform.list_agents()) == 1
    assert [item.scenario_id for item in platform.list_scenarios()] == [
        "knowledge-qa",
        "marketing-assistant",
    ]
    with pytest.raises(ValueError, match="single-Agent"):
        platform.register_agent(AgentDefinition(agent_id="second-agent"))


def test_platform_composes_a_generic_agent_from_definition_and_scenario():
    skills, tools = _sources()
    platform = AgentPlatform()
    platform.register_agent(AgentDefinition(
        agent_id="default-agent",
        display_name="General Agent",
        system_prompt="Answer with sourced context.",
        skill_sources=(skills,),
        tool_sources=(tools,),
    ))
    platform.register_scenario(ScenarioDefinition(
        scenario_id="knowledge-qa",
        agent_id="default-agent",
        display_name="Knowledge Q&A",
    ))

    application = platform.create_application(
        "knowledge-qa",
        model=lambda _messages, _tools, _request: "done",
    )
    try:
        assert isinstance(application, PlatformApplication)
        assert application.runtime is not None
        assert application.agent.system_prompt == "Answer with sourced context."
        assert application.skills.list_skills() == []
        assert application.tools.list_tools() == []
    finally:
        application.close()


def test_platform_application_is_the_real_six_layer_runtime_boundary():
    skills, tools = _sources()
    events = []

    class Infrastructure:
        def start(self):
            events.append("start")

        def close(self):
            events.append("close")

    platform = AgentPlatform()
    platform.register_agent(AgentDefinition(
        agent_id="default-agent",
        system_prompt="Analyze the supplied data.",
        skill_sources=(skills,),
        tool_sources=(tools,),
    ))
    platform.register_scenario(ScenarioDefinition(
        scenario_id="data-analysis",
        agent_id="default-agent",
    ))

    application = platform.create_application(
        "data-analysis",
        model=lambda _messages, _tools, _request: "analysis complete",
        dependencies=PlatformDependencies(
            data=DataLayer(),
            infrastructure=InfrastructureLayer(resources=(Infrastructure(),)),
        ),
    )
    try:
        assert isinstance(application, PlatformApplication)
        assert application.layer_snapshot() == (
            "application_scenarios",
            "agents",
            "core",
            "data",
            "integrations",
            "infrastructure",
        )
        result = application.prompt("analyze")
        assert result.reply == "analysis complete"
        assert events == ["start"]
    finally:
        application.close()
    assert events == ["start", "close"]


def test_scenario_can_select_a_subset_of_agent_sources():
    selected_skills = StaticSkillSource("skill:selected", [])
    selected_tools = StaticToolSource("tool:selected", [])
    unused_skills = StaticSkillSource("skill:unused", [])
    unused_tools = StaticToolSource("tool:unused", [])
    platform = AgentPlatform()
    platform.register_agent(AgentDefinition(
        agent_id="default-agent",
        skill_sources=(selected_skills, unused_skills),
        tool_sources=(selected_tools, unused_tools),
    ))
    platform.register_scenario(ScenarioDefinition(
        scenario_id="workflow-automation",
        agent_id="default-agent",
        skill_source_ids=("skill:selected",),
        tool_source_ids=("tool:selected",),
    ))

    application = platform.create_application(
        "workflow-automation",
        model=lambda _messages, _tools, _request: "done",
    )
    try:
        assert application.skills.list_skills() == []
        assert application.tools.list_tools() == []
        assert application.agent is not None
    finally:
        application.close()


def test_scenario_rejects_unknown_sources_instead_of_silently_dropping_them():
    skill, tool = _sources()
    platform = AgentPlatform()
    platform.register_agent(AgentDefinition(
        agent_id="default-agent",
        skill_sources=(skill,),
        tool_sources=(tool,),
    ))
    platform.register_scenario(ScenarioDefinition(
        scenario_id="support",
        agent_id="default-agent",
        skill_source_ids=("skill:missing",),
    ))

    with pytest.raises(ValueError, match="skill:missing"):
        platform.create_application(
            "support",
            model=lambda _messages, _tools, _request: "done",
        )


def test_platform_package_has_no_business_or_provider_dependency():
    root = Path(__file__).resolve().parents[2] / "agent_platform"
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in root.rglob("*.py")
    ).lower()
    assert "agents.ad_agent" not in source
    assert "google_ads" not in source
    assert "tiktok" not in source
    assert "dv360" not in source

    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(
                    not alias.name.startswith("agents.ad_agent")
                    for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("agents.ad_agent")


def test_advertising_is_published_as_a_product_definition():
    from agents.ad_agent import advertising_agent_definition

    definition = advertising_agent_definition()

    assert definition.agent_id == "default-agent"
    assert definition.metadata["scenario_domain"] == "advertising"
    assert definition.source_ids()["skills"] == ("ad-skills",)
    assert definition.source_ids()["tools"] == ()


def test_platform_tool_policy_enforces_schema_permissions_live_gate_and_audit():
    audits = []
    calls = []
    source = StaticToolSource("tool:write", [
        ToolBinding(
            {
                "name": "update_record",
                "description": "Update one record",
                "effect_class": "write",
                "risk_level": "high",
                "required_permissions": ["records.write"],
                "input_schema": {
                    "type": "object",
                    "required": ["record_id"],
                    "properties": {"record_id": {"type": "string"}},
                    "additionalProperties": False,
                },
            },
            lambda _context, value: calls.append(value) or {"ok": True},
        ),
    ])
    model_calls = []

    def model(messages, _tools, _request):
        model_calls.append(len(messages))
        if len(model_calls) == 1:
            return {
                "tool_calls": [{
                    "id": "call-1",
                    "name": "update_record",
                    "arguments": {"record_id": "r-1", "unexpected": True},
                }]
            }
        return "blocked"

    platform = AgentPlatform()
    platform.register_agent(AgentDefinition(
        agent_id="default-agent",
        tool_sources=(source,),
    ))
    platform.register_scenario(ScenarioDefinition(
        scenario_id="records",
        agent_id="default-agent",
    ))
    application = platform.create_application(
        "records",
        model=model,
        options={
            "max_turns": 2,
            "tool_policy": ToolExecutionPolicy(
                permissions=frozenset({"records.write"}),
                audit_sink=audits.append,
            ),
        },
    )
    try:
        result = application.prompt("update", execution_mode="live")
        assert result.data["tool_results"][0]["is_error"] is True
        assert "unknown fields" in result.data["tool_results"][0]["content"]
        assert calls == []
        assert any(
            event["decision"] == "blocked"
            and event["reason_code"] == "input_schema"
            for event in audits
        )
    finally:
        application.close()


def test_platform_tool_policy_blocks_live_write_before_executor():
    calls = []
    audits = []
    source = StaticToolSource("tool:live", [
        ToolBinding(
            {
                "name": "delete_record",
                "effect_class": "write",
                "required_permissions": ["records.write"],
                "input_schema": {
                    "type": "object",
                    "required": ["record_id"],
                    "properties": {"record_id": {"type": "string"}},
                },
            },
            lambda _context, value: calls.append(value),
        ),
    ])
    model_calls = 0

    def model(_messages, _tools, _request):
        nonlocal model_calls
        model_calls += 1
        if model_calls == 1:
            return {
                "tool_calls": [{
                    "id": "call-1",
                    "name": "delete_record",
                    "arguments": {"record_id": "r-1"},
                }]
            }
        return "blocked"

    platform = AgentPlatform()
    platform.register_agent(AgentDefinition(
        agent_id="default-agent",
        tool_sources=(source,),
    ))
    platform.register_scenario(ScenarioDefinition(
        scenario_id="records-live",
        agent_id="default-agent",
    ))
    application = platform.create_application(
        "records-live",
        model=model,
        options={
            "tool_policy": ToolExecutionPolicy(
                permissions=frozenset({"records.write"}),
                audit_sink=audits.append,
            ),
        },
    )
    try:
        result = application.prompt("delete", execution_mode="live")
        assert result.data["tool_results"][0]["is_error"] is True
        assert calls == []
        assert any(event["reason_code"] == "live_disabled" for event in audits)
    finally:
        application.close()
