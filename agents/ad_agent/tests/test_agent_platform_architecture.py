"""Contract tests for the six-layer Agent Platform architecture."""

import ast
import inspect
from pathlib import Path

import pytest

from agents.agent_harness import (
    AgentMessage,
    AgentState,
    StaticSkillSource,
    StaticToolSource,
    ToolBinding,
    ToolCall,
    ToolCallContext,
    TurnRequest,
)
from agents.agent_platform import (
    AgentDefinition,
    AgentPlatform,
    PlatformLayer,
    ScenarioDefinition,
)
from agents.agent_platform.runtime import (
    DataLayer,
    InfrastructureLayer,
    IntegrationLayer,
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


def test_platform_does_not_expose_a_second_runtime_factory():
    assert "factory" not in inspect.signature(AgentPlatform.register_agent).parameters


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


def test_platform_governance_is_applied_to_the_real_harness():
    skills, tools = _sources()
    from agents.agent_platform.governance.policy import GovernancePolicy

    platform = AgentPlatform(governance=GovernancePolicy(
        default_execution_mode="live",
        max_context_chars=64,
        max_tools=3,
        max_turns=2,
    ))
    platform.register_agent(AgentDefinition(
        agent_id="default-agent",
        skill_sources=(skills,),
        tool_sources=(tools,),
    ))
    platform.register_scenario(ScenarioDefinition(
        scenario_id="governed",
        agent_id="default-agent",
    ))

    application = platform.create_application(
        "governed",
        model=lambda _messages, _tools, request: request.execution_mode,
    )
    try:
        assert application.runtime._kernel.resolve_mode(
            "tenant", "user", None,
        ) == "live"
        assert application.skills.max_context_chars == 64
        assert application.agent.max_tools == 3
        assert application.agent.max_turns == 2
        assert application.prompt("mode").reply == "live"
    finally:
        application.close()


def test_platform_closes_partial_application_when_source_registration_fails():
    events = []

    class Resource:
        def start(self):
            events.append("start")

        def close(self):
            events.append("close")

    valid = StaticToolSource(
        "tool:valid",
        [ToolBinding({"name": "same"}, lambda _context, _data: "ok")],
    )
    duplicate = StaticToolSource(
        "tool:duplicate",
        [ToolBinding({"name": "same"}, lambda _context, _data: "duplicate")],
    )
    platform = AgentPlatform()
    platform.register_agent(AgentDefinition(
        agent_id="default-agent",
        tool_sources=(valid, duplicate),
    ))
    platform.register_scenario(ScenarioDefinition(
        scenario_id="broken",
        agent_id="default-agent",
    ))

    with pytest.raises(ValueError, match="already registered"):
        platform.create_application(
            "broken",
            model=lambda *_args: "done",
            dependencies=PlatformDependencies(
                infrastructure=InfrastructureLayer(resources=(Resource(),)),
            ),
        )
    assert events == []


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


def test_infrastructure_supports_stop_only_resources_and_reverse_order():
    events = []

    class Resource:
        def __init__(self, name):
            self.name = name

        def start(self):
            events.append(f"start:{self.name}")

        def stop(self):
            events.append(f"stop:{self.name}")

    layer = InfrastructureLayer(resources=(
        Resource("first"),
        Resource("second"),
    ))
    layer.start()
    layer.close()

    assert events == [
        "start:first",
        "start:second",
        "stop:second",
        "stop:first",
    ]


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


def test_integration_layer_tool_sources_are_registered_in_the_harness():
    integration_source = StaticToolSource(
        "integration:search",
        [ToolBinding({"name": "search"}, lambda _context, _data: "ok")],
    )
    platform = AgentPlatform()
    platform.register_agent(AgentDefinition(agent_id="default-agent"))
    platform.register_scenario(ScenarioDefinition(
        scenario_id="integration",
        agent_id="default-agent",
    ))

    application = platform.create_application(
        "integration",
        model=lambda _messages, tools, _request: tools[0]["name"],
        dependencies=PlatformDependencies(
            integrations=IntegrationLayer(tool_sources=(integration_source,)),
        ),
    )
    try:
        assert [tool["name"] for tool in application.list_tools()] == ["search"]
        assert application.prompt("find").reply == "search"
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


def test_platform_tool_policy_does_not_trust_permissions_from_request_context():
    calls = []
    source = StaticToolSource("tool:permission", [
        ToolBinding(
            {
                "name": "read_record",
                "required_permissions": ["records.read"],
            },
            lambda _context, value: calls.append(value) or {"ok": True},
        ),
    ])

    def model(_messages, _tools, _request):
        return {
            "tool_calls": [{
                "id": "call-1",
                "name": "read_record",
                "arguments": {},
            }]
        }

    platform = AgentPlatform()
    platform.register_agent(AgentDefinition(
        agent_id="default-agent",
        tool_sources=(source,),
    ))
    platform.register_scenario(ScenarioDefinition(
        scenario_id="permission-boundary",
        agent_id="default-agent",
    ))
    application = platform.create_application(
        "permission-boundary",
        model=model,
        options={"max_turns": 1},
    )
    try:
        result = application.prompt(
            "read",
            context={"permissions": ["records.read"]},
        )
        tool_message = next(
            message for message in result.data["messages"]
            if message["role"] == "tool"
        )
        assert tool_message["metadata"]["is_error"] is True
        assert calls == []
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


def test_platform_tool_policy_enforces_scope_in_the_actual_harness_path():
    calls = []
    source = StaticToolSource("tool:scoped", [
        ToolBinding(
            {
                "name": "read_record",
                "scope_required": True,
                "input_schema": {
                    "type": "object",
                    "required": ["record_id"],
                    "properties": {"record_id": {"type": "string"}},
                },
            },
            lambda _context, value: calls.append(value) or {"ok": True},
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
                    "name": "read_record",
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
        scenario_id="scoped",
        agent_id="default-agent",
    ))
    application = platform.create_application(
        "scoped",
        model=model,
        options={"max_turns": 2},
    )
    try:
        result = application.prompt("read")
        tool_message = next(
            message for message in result.data["messages"]
            if message["role"] == "tool"
        )
        assert "scope" in tool_message["content"].lower()
        assert calls == []
    finally:
        application.close()


def test_platform_tool_policy_audit_failure_marks_run_for_recovery():
    source = StaticToolSource("tool:audit", [
        ToolBinding(
            {"name": "read_record"},
            lambda _context, _value: {"ok": True},
        ),
    ])

    def model(_messages, _tools, _request):
        return {
            "tool_calls": [{
                "id": "call-1",
                "name": "read_record",
                "arguments": {},
            }]
        }

    platform = AgentPlatform()
    platform.register_agent(AgentDefinition(
        agent_id="default-agent",
        tool_sources=(source,),
    ))
    platform.register_scenario(ScenarioDefinition(
        scenario_id="audit-failure",
        agent_id="default-agent",
    ))
    application = platform.create_application(
        "audit-failure",
        model=model,
        options={
            "max_turns": 1,
            "tool_policy": ToolExecutionPolicy(
                audit_sink=lambda _event: (_ for _ in ()).throw(
                    RuntimeError("audit unavailable")
                ),
            ),
        },
    )
    try:
        result = application.prompt("read")
        assert result.status.value == "recovery_required"
        assert result.recovery_required is True
        assert result.runtime_signals["audit_error"] is True
    finally:
        application.close()


def test_required_tool_audit_is_emitted_into_the_generic_run_event_stream():
    events = []
    policy = ToolExecutionPolicy(require_audit=True)
    request = TurnRequest(
        user_input="read",
        run_id="run-audit",
        turn_id="turn-audit",
        event_callback=events.append,
    )
    context = ToolCallContext(
        request=request,
        assistant_message=AgentMessage.assistant(""),
        tool_call=ToolCall("call-1", "read_record", {}),
        state=AgentState(),
        tool_definition={"name": "read_record"},
    )

    assert policy.before_tool_call(context) is None
    assert policy.after_tool_call(context, {"is_error": False}) is None
    assert events == [{
        "type": "tool_audit",
        "run_id": "run-audit",
        "turn_id": "turn-audit",
        "tool_name": "read_record",
        "decision": "executed",
        "reason_code": "ok",
    }]


def test_tool_policy_scopes_idempotency_to_run_and_releases_failed_reservations():
    definition = {
        "name": "update_record",
        "effect_class": "write",
        "live_support": True,
        "idempotency_key_field": "request_id",
        "input_schema": {
            "type": "object",
            "required": ["request_id"],
            "properties": {"request_id": {"type": "string"}},
        },
    }
    policy = ToolExecutionPolicy(
        allow_live_writes=True,
        live_approved_tools=frozenset({"update_record"}),
        write_guard_configured=True,
        require_confirmation_for_writes=True,
    )

    def context(run_id, turn_id, call_id="call-1"):
        request = TurnRequest(
            user_input="update",
            run_id=run_id,
            turn_id=turn_id,
            execution_mode="live",
            context={
                "confirmed": True,
                "confirmation_payload": {"plan": "current"},
            },
        )
        return ToolCallContext(
            request=request,
            assistant_message=AgentMessage.assistant(""),
            tool_call=ToolCall(call_id, "update_record", {"request_id": "same"}),
            state=AgentState(),
            tool_definition=definition,
        )

    first = context("run-1", "turn-1")
    assert policy.before_tool_call(first) is None
    duplicate = policy.before_tool_call(first)
    assert "duplicate" in duplicate["reason"].lower()
    policy.after_tool_call(first, {"is_error": True})
    assert policy.before_tool_call(first) is None
    assert policy.before_tool_call(context("run-2", "turn-2")) is None
