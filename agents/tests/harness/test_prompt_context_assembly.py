from agents.agent_harness import (
    AgentApplication,
    ModelTurn,
    SkillBinding,
    StaticSkillSource,
)


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
    assert "STABLE AGENT POLICY" in system_messages[0]
    assert system_messages[1] == "APPLICATION CONTEXT"
    assert "SKILL GUIDANCE" in system_messages[2]
    assert model.messages[-1].role == "user"
