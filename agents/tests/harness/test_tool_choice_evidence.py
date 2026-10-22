from agents.agent_harness.core.tool_selection import ToolSelector
from agents.agent_platform.tools.knowledge import knowledge_search_tool_source


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
