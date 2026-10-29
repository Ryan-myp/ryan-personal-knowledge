from agents.agent_harness import (
    AgentApplication,
    ModelTurn,
    SkillBinding,
    StaticSkillSource,
)
from types import SimpleNamespace

from agents.agent_harness.core.tool_selector import DynamicToolSelector


def test_context_provider_can_follow_the_actual_model_tool_set():
    seen = []
    class Context:
        def build_tool_context(self, request, messages, tools):
            seen.append([tool.name for tool in tools])
            return {"prompt": "CURRENT TOOLS"}

    application = AgentApplication.create(
        model=lambda *_: ModelTurn(content="ok"), context_provider=Context(),
    )
    try:
        result = application.prompt("hello")
        assert result.status.value == "succeeded"
        assert seen == [[]]
    finally:
        application.close()


def test_explicit_tool_skill_context_does_not_rerank_discovered_tools(monkeypatch):
    selector = DynamicToolSelector(SimpleNamespace(list_all=lambda: {}))
    tool = SimpleNamespace(skill_refs=["new-skill"])
    monkeypatch.setattr(selector, "_merge_expert_knowledge", lambda tools: "bound" if tools == [tool] else "")
    monkeypatch.setattr(selector, "_triggered_skill_context", lambda *a, **k: str(k["skill_refs"]))
    monkeypatch.setattr(selector, "_managed_skill_context", lambda *a, **k: "managed")
    result = selector.build_selected_skill_context("继续", [tool], tenant_id="tenant")
    assert "new-skill" in result and "bound" in result and "managed" in result


def test_model_messages_keep_stable_instructions_ahead_of_dynamic_context():
    class ContextProvider:
        @staticmethod
        def build_context(_request, _messages):
            return {"prompt": "APPLICATION CONTEXT"}

    class Model:
        def __init__(self):
            self.messages = []

        def complete(self, messages, _tools, _request):
            self.messages = list(messages)
            return ModelTurn(content="ready")

    model = Model()
    application = AgentApplication.create(
        model=model,
        system_prompt="STABLE AGENT POLICY",
        context_provider=ContextProvider(),
    )
    application.register_skill_source(StaticSkillSource(
        "test-skills",
        [SkillBinding(
            name="test-skill",
            instructions="SKILL GUIDANCE",
            metadata={"always_on": True},
        )],
    ))
    try:
        result = application.prompt("hello")
    finally:
        application.close()

    assert result.status.value == "succeeded", result.to_dict()
    system_messages = [
        str(message.content)
        for message in model.messages
        if message.role == "system"
    ]
    assert "[STABLE AGENT CONTRACT]" in system_messages[0]
    assert (
        "invent or claim a personal name, model identity, provider, or developer"
        in system_messages[0]
    )
    assert "latest unresolved question" in system_messages[0]
    assert "requests for description, not instructions to execute" in system_messages[0]
    assert "do not ask for the same choice again" in system_messages[0]
    assert "STABLE AGENT POLICY" in system_messages[0]
    assert system_messages[1] == "APPLICATION CONTEXT"
    assert "SKILL GUIDANCE" in system_messages[2]
    assert model.messages[-1].role == "user"


def test_preparse_context_does_not_duplicate_knowledge_inside_skill_guidance(monkeypatch):
    selector = DynamicToolSelector(SimpleNamespace(list_all=lambda: {}))
    selection = SimpleNamespace(
        selected_tools=[], expert_knowledge="registered guidance", namespaces=[],
    )
    knowledge = [{
        "document_id": "doc", "namespace": "general", "topic": "topic",
        "source": "source", "version": "1", "confidence": 1,
        "excerpt": "UNIQUE RETRIEVED PASSAGE",
    }]
    monkeypatch.setattr(selector, "select_tools", lambda *_: selection)
    monkeypatch.setattr(selector._selector, "select_relevant", lambda *_: [])
    monkeypatch.setattr(selector, "_merge_expert_knowledge", lambda *_: "registered guidance")
    monkeypatch.setattr(selector, "_query_knowledge", lambda *_args, **_kwargs: knowledge)
    monkeypatch.setattr(selector, "_triggered_skill_context", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(selector, "_managed_skill_context", lambda *_args, **_kwargs: "")
    context = selector.build_context_for_input("question", [])
    assert context["knowledge"] == knowledge
    assert "UNIQUE RETRIEVED PASSAGE" not in context["expert_knowledge"]
    assert "registered guidance" in context["expert_knowledge"]
