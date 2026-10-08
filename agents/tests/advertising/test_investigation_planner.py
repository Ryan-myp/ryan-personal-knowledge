"""Read-only follow-up planning stays within published Tool contracts."""

import json
from types import SimpleNamespace

from agents.agent_harness import AgentMessage, ModelTurn, ToolCall
from agents.agent_harness.core.interfaces import (
    ParsedIntent,
    ToolDefinition,
    ToolEffect,
    ToolSchema,
)
from agents.tools.advertising.application.integration import AdvertisingModelAdapter
from agents.tools.advertising.application.integration_investigation import ReadOnlyInvestigationPlanner


class _Registry:
    def __init__(self, definitions):
        self.definitions = list(definitions)

    def list_all(self):
        return list(self.definitions)

    def get(self, name):
        for definition in self.definitions:
            if definition.name == name:
                return definition, None
        raise KeyError(name)


def _tool(name, namespace="meta", effect=ToolEffect.READ):
    return ToolDefinition(
        name=name,
        skill="reports",
        namespace=namespace,
        description=f"Read {name.replace('.', ' ')} report data",
        action="list" if effect == ToolEffect.READ else "update",
        resource_type="report",
        resource_id_field="report_id" if effect != ToolEffect.READ else None,
        intent_types=["performance_analysis"],
        effect_class=effect,
        input_schema=ToolSchema(
            required=["account_id", "limit"],
            properties={
                "account_id": {"type": "string", "description": "Private scope"},
                "campaign_id": {"type": "string"},
                "limit": {"type": "integer"},
            },
        ),
        scope_fields=["account_id"],
    )


class _LLM:
    def __init__(self, reply):
        self.reply = reply
        self.messages = None

    def call(self, messages):
        self.messages = messages
        return self.reply


def _planner(reply, definitions=None):
    llm = _LLM(reply)

    class InputBuilder:
        @staticmethod
        def build(_definition, _intent, _namespace, _session):
            return {"account_id": "account-secret", "limit": 5}

    owner = SimpleNamespace(
        registry=_Registry(definitions or [_tool("meta.get_report")]),
        input_builder=InputBuilder(),
        _llm=llm,
        _canonical_platform=lambda value: str(value).lower(),
        _resolve_platform_identifier=lambda value: str(value).lower(),
    )
    from agents.tools.advertising.application.integration_turn_planner import AdvertisingTurnPlanner
    return ReadOnlyInvestigationPlanner(
        owner,
        turn_planner=AdvertisingTurnPlanner(owner),
    ), llm


def _intent():
    return ParsedIntent(
        "performance_analysis",
        "分析 TikTok campaign 转化趋势",
        ["meta"],
        metadata={"planning_mode": "investigate"},
    )


def test_planner_selects_one_registered_read_tool_and_keeps_scope_trusted():
    planner, llm = _planner(json.dumps({
        "calls": [{
            "name": "meta.get_report",
            "arguments": {"limit": 10},
        }],
    }))

    calls = planner.plan(
        intent=_intent(),
        session_context=object(),
        prior_results=[{"tool": "meta.list_campaigns", "success": True}],
        already_called={"meta.list_campaigns"},
    )

    assert len(calls) == 1
    assert calls[0].name == "meta.get_report"
    assert calls[0].arguments == {"account_id": "account-secret", "limit": 10}
    assert "account-secret" not in json.dumps(llm.messages)
    assert "account_id" not in json.dumps(llm.messages)


def test_investigation_requires_explicit_mode_and_read_only_initial_plan():
    planner, _llm = _planner(
        "{\"calls\": []}",
        [
            _tool("meta.get_report"),
            _tool("meta.mutate_campaign", effect=ToolEffect.EXTERNAL_WRITE),
        ],
    )
    read = ToolCall(id="read", name="meta.get_report", arguments={})
    write = ToolCall(id="write", name="meta.mutate_campaign", arguments={})
    direct_intent = SimpleNamespace(metadata={"planning_mode": "direct"})

    assert planner.eligible(_intent(), [read]) is True
    assert planner.eligible(direct_intent, [read]) is False
    assert planner.eligible(_intent(), [write]) is False


def test_planner_rejects_writes_unknown_tools_cross_namespace_and_scope_changes():
    write = _tool("meta.mutate_campaign", effect=ToolEffect.EXTERNAL_WRITE)
    other = _tool("google.get_report", namespace="google")
    read = _tool("meta.get_report")
    planner, _llm = _planner(json.dumps({
        "calls": [
            {"name": "meta.mutate_campaign", "arguments": {"limit": 1}},
            {"name": "google.get_report", "arguments": {"limit": 1}},
            {"name": "made.up", "arguments": {}},
            {"name": "meta.get_report", "arguments": {"account_id": "other"}},
        ],
    }), [write, other, read])

    calls = planner.plan(
        intent=_intent(),
        session_context=object(),
        prior_results=[],
        already_called=set(),
    )

    assert calls == []


def test_planner_fails_closed_on_bad_json_or_unmet_schema():
    malformed, _ = _planner("not json")
    invalid, _ = _planner(json.dumps({
        "calls": [{"name": "meta.get_report", "arguments": {"limit": "many"}}],
    }))

    assert malformed.plan(
        intent=_intent(), session_context=object(), prior_results=[], already_called=set(),
    ) == []
    assert invalid.plan(
        intent=_intent(), session_context=object(), prior_results=[], already_called=set(),
    ) == []


def test_adapter_replans_from_each_result_but_stops_after_two_read_calls():
    definitions = [
        _tool("meta.list_campaigns"),
        _tool("meta.get_report"),
        _tool("meta.get_conversion_breakdown"),
    ]
    replies = [
        json.dumps({
            "calls": [{"name": "meta.get_report", "arguments": {"limit": 10}}],
        }),
        json.dumps({
            "calls": [{
                "name": "meta.get_conversion_breakdown",
                "arguments": {"limit": 10},
            }],
        }),
    ]

    class SequencedLLM:
        def __init__(self):
            self.calls = []

        def call(self, messages):
            self.calls.append(messages)
            return replies[len(self.calls) - 1]

    llm = SequencedLLM()
    registry = _Registry(definitions)

    class InputBuilder:
        @staticmethod
        def build(_definition, _intent, _namespace, _session):
            return {"account_id": "account-secret", "limit": 5}

    owner = SimpleNamespace(
        registry=registry,
        input_builder=InputBuilder(),
        _llm=llm,
        _sessions={},
        _canonical_platform=lambda value: str(value).lower(),
        _resolve_platform_identifier=lambda value: str(value).lower(),
    )
    adapter = AdvertisingModelAdapter(owner)
    state = {
        "calls": (ToolCall(
            id="initial",
            name="meta.list_campaigns",
            arguments={"account_id": "account-secret", "limit": 5},
        ),),
        "intent": _intent(),
        "session": SimpleNamespace(ctx=object()),
        "tool_plan": {"meta": ["meta.list_campaigns"]},
        "investigation_enabled": True,
        "investigation_steps": 0,
    }
    completed = []
    adapter._results.finish_turn = lambda *_args: (
        completed.append(True) or ModelTurn(content="done")
    )

    def tool_message(name):
        return AgentMessage.tool(
            {"success": True, "data": {"rows": [{"campaign_id": "c-1"}]}},
            tool_call_id=name,
            name=name,
        )

    messages = [AgentMessage.user("分析转化下降原因"), tool_message("meta.list_campaigns")]
    request = SimpleNamespace(
        run_id="run-42",
        session_id="session-42",
        context={
            adapter.STATE_CONTEXT_KEY: adapter._serialize_state(state),
        },
    )
    first = adapter.complete(messages, [], request)
    request.context.update(first.context_updates)
    assert first.tool_calls[0].name == "meta.get_report"

    messages.append(tool_message("meta.get_report"))
    second = adapter.complete(messages, [], request)
    request.context.update(second.context_updates)
    assert second.tool_calls[0].name == "meta.get_conversion_breakdown"

    messages.append(tool_message("meta.get_conversion_breakdown"))
    final = adapter.complete(messages, [], request)
    request.context.update(final.context_updates)

    assert final.content == "done"
    assert len(llm.calls) == 2
    assert completed == [True]
    assert request.context[adapter.STATE_CONTEXT_KEY][
        "investigation_enabled"
    ] is False
