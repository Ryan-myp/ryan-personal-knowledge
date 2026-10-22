from agents.agent_harness.core.tool_selection import ToolSelector
from agents.agent_platform.tools.knowledge import knowledge_search_tool_source
from agents.agent_platform.tools.web_search import web_search_tool_source
import pytest


def test_generic_fallback_tool_availability_does_not_force_a_lookup():
    binding, = knowledge_search_tool_source(
        object(), required_permission="knowledge.read",
    ).list_bindings()
    selector = ToolSelector()
    assert selector.requires_tool_call(
        "我刚开始用这个工作台，它可以帮我处理哪些任务？", [binding.definition],
    ) is False


def test_explicit_knowledge_lookup_still_requires_tool_evidence():
    binding, = knowledge_search_tool_source(
        object(), required_permission="knowledge.read",
    ).list_bindings()
    assert ToolSelector().requires_tool_call(
        "请查询知识库，解释程序化广告", [binding.definition],
    ) is True


@pytest.mark.parametrize("question", [
    "我刚开始用这个工作台，它可以帮我处理哪些任务？",
    "Which tasks can this workspace handle?",
])
def test_web_fallback_does_not_turn_a_question_into_mandatory_execution(question):
    knowledge, = knowledge_search_tool_source(
        object(), required_permission="knowledge.read",
    ).list_bindings()
    web, = web_search_tool_source(
        configuration_provider=lambda: {}, required_permission="knowledge.read",
    ).list_bindings()
    assert ToolSelector().requires_tool_call(
        question, [knowledge.definition, web.definition],
    ) is False
