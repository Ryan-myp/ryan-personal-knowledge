from types import SimpleNamespace

import pytest

from agents.agent_harness.core.response_language import (
    infer_response_language, response_language_instruction,
)
from agents.agent_harness.messages import AgentMessage


@pytest.mark.parametrize("text,expected", [
    ("查询 Google Ads 报表", "zh"),
    ("继续", "zh"),
    ("Please query Google Ads reports.", "en"),
    ('Please compare the campaigns named "中文测试" and "English".', "en"),
    ("查询 `campaign_id`，代码保留英文。", "zh"),
])
def test_current_user_prose_determines_language_not_technical_names(text, expected):
    assert infer_response_language(text) == expected


def test_numeric_followup_inherits_only_prior_user_language():
    assert infer_response_language("50", ["Please update the budget."]) == "en"
    assert infer_response_language("50", ["预算是多少？"]) == "zh"


def test_language_instruction_uses_request_not_english_tool_or_document_content():
    request = SimpleNamespace(user_input="查询 Google Ads 报表")
    messages = [
        AgentMessage.user("Please answer in English."),
        AgentMessage.tool({"text": "English documentation"}, tool_call_id="lookup", name="read"),
    ]
    instruction = response_language_instruction(request, messages)
    assert "简体中文" in instruction
    assert "API" in instruction
    assert "内部思维链" in instruction
    assert "English documentation" not in instruction


def test_language_instruction_switches_with_latest_user_request():
    request = SimpleNamespace(user_input="Please summarize this report.")
    instruction = response_language_instruction(request, [AgentMessage.user("请查询报表")])
    assert "English" in instruction
    assert "Do not expose" in instruction
