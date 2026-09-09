"""Contract tests for the model-backed intent boundary.

The fake model is deliberately used through ``LLMIntentParser.parse``. These
tests do not claim model quality; they verify that untrusted model output is
constrained by the live Registry and provider schemas before it can become a
Tool plan.
"""

from agents.ad_agent.core.interfaces import ToolContext
from agents.ad_agent.core.intent import LLMIntentParser
from agents.ad_agent.runtime.runtime import AgentRuntime
from agents.ad_agent.capabilities.tiktok import create_tiktok_capability


class _SequenceLLM:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def call(self, messages):
        self.calls.append(messages)
        return self.responses.pop(0)


def _parser_with_tiktok(llm):
    runtime = AgentRuntime(
        require_llm=True,
        llm_client=llm,
        enforce_account_scope=False,
    )
    runtime.register_capability(create_tiktok_capability())
    return runtime, runtime.intent_parser


def test_model_generated_resource_ids_are_removed_until_explicitly_selected():
    llm = _SequenceLLM(
        '{"intent_type":"create_campaign","namespaces":["tiktok"],'
        '"scoped_parameters":{"tiktok":{'
        '"account_id":"my-account","app_id":"my-app",'
        '"pixel_id":"pixel-placeholder","audience_id":"audience-placeholder"}}}'
    )
    runtime, parser = _parser_with_tiktok(llm)
    try:
        intent = parser.parse("创建 TikTok App 转化广告，使用我的 App", ToolContext("s1", "u1"))
    finally:
        runtime.close(wait=True)

    params = intent.scoped_parameters["tiktok"]
    assert "account_id" not in params
    assert "app_id" not in params
    assert "pixel_id" not in params
    assert "audience_id" not in params


def test_explicit_resource_ids_override_model_placeholders():
    llm = _SequenceLLM(
        '{"intent_type":"create_campaign","namespaces":["tiktok"],'
        '"scoped_parameters":{"tiktok":{'
        '"account_id":"model-account","app_id":"model-app"}}}'
    )
    runtime, parser = _parser_with_tiktok(llm)
    try:
        intent = parser.parse(
            "创建 TikTok App 广告，account_id=7397068114548195329，app_id=app-123",
            ToolContext("s1", "u1"),
        )
    finally:
        runtime.close(wait=True)

    params = intent.scoped_parameters["tiktok"]
    assert params["account_id"] == "7397068114548195329"
    assert params["app_id"] == "app-123"


def test_unknown_model_intent_is_repaired_against_active_registry():
    llm = _SequenceLLM(
        '{"intent_type":"invented_operation","namespaces":["tiktok"]}',
        '{"intent_type":"list_campaigns","namespaces":["tiktok"]}',
    )
    runtime, parser = _parser_with_tiktok(llm)
    try:
        intent = parser.parse("查询 TikTok campaign 列表", ToolContext("s1", "u1"))
    finally:
        runtime.close(wait=True)

    assert intent.intent_type == "list_campaigns"
    assert intent.namespaces == ["tiktok"]
    assert len(llm.calls) == 2


def test_repaired_model_output_cannot_reintroduce_a_guessed_resource_id():
    llm = _SequenceLLM(
        '{"intent_type":"chat","namespaces":["tiktok"]}',
        '{"intent_type":"create_campaign","namespaces":["tiktok"],'
        '"scoped_parameters":{"tiktok":{"app_id":"repair-placeholder"}}}',
    )
    runtime, parser = _parser_with_tiktok(llm)
    try:
        intent = parser.parse("创建 TikTok App 转化广告，使用我的 App", ToolContext("s1", "u1"))
    finally:
        runtime.close(wait=True)

    assert intent.intent_type == "create_campaign"
    assert "app_id" not in intent.scoped_parameters["tiktok"]


def test_parser_without_active_registry_cannot_create_executable_scope():
    llm = _SequenceLLM('{"intent_type":"list_campaigns","namespaces":["tiktok"]}')
    parser = LLMIntentParser(llm, allow_rule_fallback=False)

    intent = parser.parse("查询 TikTok campaign", ToolContext("s1", "u1"))

    assert intent.intent_type == "chat"
    assert intent.namespaces == []
