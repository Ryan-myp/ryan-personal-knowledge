import pytest

from agents.agent_harness.core.tool_selection import ToolSelector


def tools():
    return [
        {
            "name": "list_accounts", "namespace": "sample", "action": "list",
            "resource_type": "account", "effect_class": "read",
            "description": "Query accounts",
            "intent_aliases": ["账户列表", "查询账户"],
        },
        {
            "name": "create_record", "namespace": "sample", "action": "create",
            "resource_type": "record", "effect_class": "write",
            "intent_aliases": ["创建广告"],
        },
        {
            "name": "list_workflows", "namespace": "sample", "action": "list",
            "resource_type": "workflow", "effect_class": "read",
            "description": "List stored workflow records",
        },
        {
            "name": "search_reference", "namespace": "reference", "action": "search",
            "resource_type": "knowledge", "effect_class": "read",
            "traits": ["semantic_discovery"],
            "intent_aliases": ["search reference", "查询知识库"],
        },
    ]


@pytest.mark.parametrize("prompt", [
    "画一个创建广告的通用流程图，只解释流程，不执行创建，也不用查询账户。",
    "Explain a workflow, do not query account data.",
    "说明处理流程，不用获取真实数据。",
    "画个从选模板到创建 Campaign、Ad Set、Ad 的流程示意图，不必获取账户数据。",
])
def test_negative_read_clause_does_not_turn_process_explanation_into_an_operation(prompt):
    assert ToolSelector().select_relevant(prompt, tools()) == []


def test_explicit_workflow_data_query_remains_operational():
    selected = ToolSelector().select_relevant("list sample workflow records", tools())
    assert [item["name"] for item in selected] == ["list_workflows"]


def test_process_explanation_can_still_be_combined_with_an_explicit_query():
    selected = ToolSelector().select_relevant(
        "Explain a workflow, then list sample accounts.", tools(),
    )
    assert "list_accounts" in [item["name"] for item in selected]


@pytest.mark.parametrize("prompt", [
    "看下比如用户说创建Google campaign，是这个流程不",
    "我说广告创建，agent里面执行的流程，是不是跟这个图里面的一样",
])
def test_process_comparison_question_does_not_route_mentioned_actions(prompt):
    assert ToolSelector().select_relevant(prompt, tools()) == []


def test_explicit_create_command_stays_routable_when_followed_by_process_question():
    selected = ToolSelector().select_relevant(
        "帮我创建广告，然后告诉我这个流程是不是跟图片一致", tools(),
    )
    assert "create_record" in [item["name"] for item in selected]


def test_negative_action_scope_does_not_leak_across_separate_clauses():
    selector = ToolSelector()
    assert selector.is_read_only_request("不要创建记录，然后查询账户", tools())
    assert selector.is_read_only_request("Do not create records, then query accounts", tools())
    assert not selector.is_read_only_request("不执行查询", tools())
    assert not selector.is_read_only_request("不查询账户", tools())
    assert not selector.is_read_only_request("不必获取账户数据", tools())


@pytest.mark.parametrize("prompt", [
    "Do not search reference; explain the workflow.",
    "不要查询知识库，只说明方法。",
])
def test_negated_registered_alias_cannot_force_a_tool_call(prompt):
    assert not ToolSelector().requires_tool_call(prompt, [tools()[-1]])


def test_registered_alias_after_a_separate_negative_clause_remains_actionable():
    assert ToolSelector().requires_tool_call(
        "不要创建记录，然后查询知识库", [tools()[-1]],
    )
