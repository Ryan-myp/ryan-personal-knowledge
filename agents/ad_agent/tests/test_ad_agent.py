"""
tests/test_ad_agent.py - ad-agent 测试套件（只读查询模式）

运行：
    python -m pytest agents/ad_agent/tests/ -v
"""

import pytest
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.ad_agent.persistence.store import AdAgentStore
from agents.ad_agent.persistence.session_manager import SessionManager
from agents.ad_agent.capabilities.meta import MetaCapability, MetaListCampaignsHandler
from agents.ad_agent.capabilities.google import GoogleCapability, GoogleListCampaignsHandler
from agents.ad_agent.capabilities.tiktok import TikTokCapability, TikTokListCampaignsHandler
from agents.ad_agent.capabilities.dv360 import (
    DV360Capability,
    DV360ListCampaignsHandler,
    DV360GetLineItemReportHandler,
)
from agents.ad_agent.runtime.runtime import AgentRuntime, AccountWhitelistValidator
from agents.ad_agent.core.tool_selector import BusinessContext
from agents.ad_agent.core.interfaces import (
    ToolContext, ToolResult, RiskLevel, ToolEffect, ReplayPolicy, ToolSchema,
    ToolDefinition
)
from agents.ad_agent.core.tool_registry import SimpleToolRegistry
from agents.ad_agent.core.intent import LLMIntentParser
from agents.ad_agent.core.interfaces import ExecutionMode
from agents.ad_agent.core.cross_channel import CrossChannelAggregator, CrossChannelAnalyzer
from agents.ad_agent.api_clients.google_ads_client import GoogleAdsAPIClient
from agents.ad_agent.api_clients.base import (
    BasePlatformClient, RetryConfig, TemporaryError, APIError,
    AuthError, RateLimitError,
)
from agents.ad_agent.api_clients.meta_client import MetaAPIClient
from agents.ad_agent.api_clients.tiktok_client import TikTokAPIClient
from agents.ad_agent.api_clients.dv360_client import DV360APIClient


# ─── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def store():
    return AdAgentStore(":memory:")


@pytest.fixture
def runtime():
    """创建只读模式的 runtime"""
    store = AdAgentStore(":memory:")
    rt = AgentRuntime(persistence_store=store, read_only_mode=True)
    rt.register_capability(create_meta_capability_mock())
    rt.register_capability(create_google_capability_mock())
    rt.register_capability(create_tiktok_capability_mock())
    rt.register_capability(create_dv360_capability_mock())
    rt.enable_read_only_mode()
    # 设置测试账户白名单
    rt.whitelist_validator.allowed_accounts = {
        "meta": ["2806375919473667"],
        "google-ads": ["9055507554"],
        "tiktok": ["7397068114548195329"],
        "dv360": ["5110831"],
    }
    return rt


def create_meta_capability_mock():
    from agents.ad_agent.capabilities.meta import create_meta_capability
    cap = create_meta_capability()
    return cap


def create_google_capability_mock():
    from agents.ad_agent.capabilities.google import create_google_capability
    cap = create_google_capability()
    return cap


def create_tiktok_capability_mock():
    from agents.ad_agent.capabilities.tiktok import create_tiktok_capability
    cap = create_tiktok_capability()
    return cap


def create_dv360_capability_mock():
    from agents.ad_agent.capabilities.dv360 import create_dv360_capability
    cap = create_dv360_capability()
    return cap


# ─── 工具注册表测试 ────────────────────────────────────────────

class TestToolRegistry:
    def test_register_and_get(self):
        registry = SimpleToolRegistry()
        tool_def = ToolDefinition(
            name="test_tool",
            skill="test",
            platform="meta",
            description="Test tool",
            input_schema=ToolSchema(),
        )
        handler = lambda ctx, inp: ToolResult.ok({"result": "ok"})
        registry.register(tool_def, handler)
        retrieved_def, retrieved_handler = registry.get("test_tool")
        assert retrieved_def.name == "test_tool"
        assert retrieved_handler is not None

    def test_unregister(self):
        registry = SimpleToolRegistry()
        tool_def = ToolDefinition(
            name="test_tool",
            skill="test",
            platform="meta",
            description="Test tool",
            input_schema=ToolSchema(),
        )
        handler = lambda ctx, inp: ToolResult.ok({})
        registry.register(tool_def, handler)
        assert len(registry.list_all()) == 1
        registry.unregister("test_tool")
        assert len(registry.list_all()) == 0

    def test_unregister_nonexistent(self):
        registry = SimpleToolRegistry()
        registry.unregister("nonexistent")  # Should not raise
        assert len(registry.list_all()) == 0

    def test_list_by_platform(self):
        registry = SimpleToolRegistry()
        for i in range(3):
            tool_def = ToolDefinition(
                name=f"meta_tool_{i}",
                skill="meta",
                platform="meta",
                description=f"Tool {i}",
                input_schema=ToolSchema(),
            )
            registry.register(tool_def, lambda ctx, inp: ToolResult.ok({}))
        tools = registry.list_by_platform("meta")
        assert len(tools) == 3

    def test_execute(self):
        registry = SimpleToolRegistry()
        tool_def = ToolDefinition(
            name="test_tool",
            skill="test",
            platform="meta",
            description="Test tool",
            input_schema=ToolSchema(required=["x"], properties={"x": {"type": "string"}}),
        )
        class _Handler:
            def execute(self, ctx, inp):
                return ToolResult.ok({"x": inp.get("x")})
        registry.register(tool_def, _Handler())
        ctx = ToolContext(session_id="s1", user_id="u1")
        result = registry.execute(ctx, "test_tool", {"x": "hello"})
        assert result.success
        assert result.data["x"] == "hello"


# ─── 账户白名单测试 ────────────────────────────────────────────

class TestAccountWhitelistValidator:
    def test_allowed_account(self):
        validator = AccountWhitelistValidator()
        validator.allowed_accounts = {"meta": ["123", "456"]}
        allowed, msg = validator.validate_account("meta", "123")
        assert allowed
        assert msg == ""

    def test_denied_account(self):
        validator = AccountWhitelistValidator()
        validator.allowed_accounts = {"meta": ["123"]}
        allowed, msg = validator.validate_account("meta", "999")
        assert not allowed
        assert "999" in msg

    def test_empty_whitelist_denies_all(self):
        # 手动创建空白名单（跳过 config.yaml 加载）
        validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
        validator.allowed_accounts = {}
        allowed, msg = validator.validate_account("meta", "any_account")
        assert not allowed
        assert "白名单" in msg

    def test_normalize_act_prefix(self):
        validator = AccountWhitelistValidator()
        validator.allowed_accounts = {"meta": ["2806375919473667"]}
        allowed, _ = validator.validate_account("meta", "act_2806375919473667")
        assert allowed


# ─── 只读模式测试 ──────────────────────────────────────────────

class TestReadOnlyMode:
    def test_write_tools_filtered(self, runtime):
        """只读模式下，写工具不应存在于注册表中"""
        all_tools = runtime.registry.list_all()
        write_tool_names = [t.name for t in all_tools if t.effect_class in (ToolEffect.WRITE, ToolEffect.EXTERNAL_WRITE)]
        assert len(write_tool_names) == 0, f"只读模式下仍存在写工具: {write_tool_names}"

    def test_read_tools_present(self, runtime):
        """只读模式下，读工具应正常存在"""
        all_tools = runtime.registry.list_all()
        read_tools = [t for t in all_tools if t.effect_class == ToolEffect.READ]
        assert len(read_tools) > 0, "应该至少有读工具"

    def test_non_readonly_keeps_write_tools(self):
        """非只读模式下，写工具应保留"""
        rt = AgentRuntime(read_only_mode=False)
        rt.register_capability(create_meta_capability_mock())
        all_tools = rt.registry.list_all()
        write_tools = [t for t in all_tools if t.is_write_tool]
        assert len(write_tools) > 0, "非只读模式应保留写工具"

    def test_tool_count_decreases_after_filter(self):
        """过滤前后工具数量应对比"""
        rt_full = AgentRuntime(read_only_mode=False)
        rt_full.register_capability(create_meta_capability_mock())
        count_full = len(rt_full.registry.list_all())

        rt_readonly = AgentRuntime(read_only_mode=True)
        rt_readonly.register_capability(create_meta_capability_mock())
        rt_readonly.enable_read_only_mode()
        count_readonly = len(rt_readonly.registry.list_all())

        assert count_readonly < count_full, f"只读模式工具数({count_readonly})应少于全量({count_full})"


# ─── 意图解析测试 ──────────────────────────────────────────────

class TestIntentParser:
    def test_list_campaigns_meta(self):
        from agents.ad_agent.core.intent import LLMIntentParser
        parser = LLMIntentParser()
        intent = parser.parse("列出 Meta campaign 列表", None)
        assert intent.intent_type == "list_campaigns"
        assert "meta" in intent.platforms

    def test_list_campaigns_google(self):
        from agents.ad_agent.core.intent import LLMIntentParser
        parser = LLMIntentParser()
        intent = parser.parse("查询 Google Ads 广告系列", None)
        assert intent.intent_type == "list_campaigns"
        assert "google" in intent.platforms

    def test_report_query(self):
        from agents.ad_agent.core.intent import LLMIntentParser
        parser = LLMIntentParser()
        intent = parser.parse("查一下 TikTok 最近7天的报表", None)
        assert intent.intent_type == "download_report"

    def test_create_intent_not_matching_in_readonly(self):
        """创建意图在只读模式下会被路由到不存在的工具（因为写工具已过滤）"""
        from agents.ad_agent.core.intent import LLMIntentParser
        parser = LLMIntentParser()
        intent = parser.parse("创建 Meta 广告系列", None)
        assert intent.intent_type == "create_campaign"

    def test_cross_channel_create_selects_all_registered_platforms(self):
        parser = LLMIntentParser()
        intent = parser.parse("跨渠道创建 campaign", None)

        assert intent.intent_type == "create_campaign"
        assert intent.platforms == ["dv360", "google", "meta", "tiktok"]

    def test_cross_channel_update_selects_all_registered_platforms(self):
        parser = LLMIntentParser()
        intent = parser.parse("跨平台更新 campaign", None)

        assert intent.intent_type == "update_campaign"
        assert intent.platforms == ["dv360", "google", "meta", "tiktok"]

    def test_single_channel_create_does_not_expand_to_all_platforms(self):
        parser = LLMIntentParser()
        intent = parser.parse("创建 campaign", None)

        assert intent.intent_type == "create_campaign"
        assert intent.platforms == []

    def test_chat_intent(self):
        from agents.ad_agent.core.intent import LLMIntentParser
        parser = LLMIntentParser()
        intent = parser.parse("你好", None)
        assert intent.intent_type == "chat"

    def test_extract_budget(self):
        from agents.ad_agent.core.intent import LLMIntentParser
        parser = LLMIntentParser()
        intent = parser._parse_with_rules("预算 500 元投放 Google")
        assert intent.budget == 500.0

    def test_extract_platforms(self):
        from agents.ad_agent.core.intent import LLMIntentParser
        parser = LLMIntentParser()
        # 使用小写关键词确保匹配
        platforms = parser._detect_platforms("帮我查 meta 和 google 的 campaign")
        assert "meta" in platforms
        assert "google" in platforms

    def test_extract_report_date_range(self):
        from agents.ad_agent.core.intent import LLMIntentParser
        parser = LLMIntentParser()
        intent = parser.parse("查询 Google 最近7天的报表", None)
        assert intent.date_range == "LAST_7_DAYS"

    def test_normalize_llm_aliases_and_ignores_unknown_fields(self):
        from agents.ad_agent.core.intent import LLMIntentParser
        parser = LLMIntentParser()
        normalized = parser._normalize_intent({
            "intent_type": "create_campaign",
            "platforms": ["google"],
            "budget_daily": 100,
            "unsupported_model_field": "must be ignored",
        })
        assert normalized["budget"] == 100
        assert "budget_daily" not in normalized
        assert "unsupported_model_field" not in normalized

    def test_llm_result_gets_raw_input_default(self):
        from agents.ad_agent.core.intent import LLMIntentParser

        class FakeLLM:
            def call(self, messages):
                return '{"intent_type":"list_campaigns","platforms":["google"]}'

        intent = LLMIntentParser(FakeLLM()).parse("查询 Google campaign", None)
        assert intent.intent_type == "list_campaigns"
        assert intent.raw_input == "查询 Google campaign"

    def test_llm_parser_receives_bounded_skill_context(self):
        from agents.ad_agent.core.intent import LLMIntentParser

        class FakeLLM:
            def __init__(self):
                self.calls = []

            def call(self, messages):
                self.calls.append(messages)
                return '{"intent_type":"list_campaigns","platforms":["meta"]}'

        llm = FakeLLM()
        parser = LLMIntentParser(llm)
        parser.parse(
            "查询 Meta campaign",
            ToolContext(
                session_id="s1",
                user_id="u1",
                metadata={"skill_context": {
                    "tool_prompt": "meta_list_campaigns",
                    "expert_knowledge": "Meta campaign scope",
                }},
            ),
        )
        prompt_text = "\n".join(
            message["content"] for message in llm.calls[0]
            if message["role"] == "system"
        )
        assert "meta_list_campaigns" in prompt_text
        assert "Meta campaign scope" in prompt_text

    def test_direct_multi_platform_comparison(self):
        from agents.ad_agent.core.intent import LLMIntentParser
        parser = LLMIntentParser()
        intent = parser.parse("比较 Meta 和 Google 的 campaign", None)
        assert intent.intent_type == "cross_channel_compare"
        assert intent.platforms == ["meta", "google"]

    def test_cross_channel_create_routes_to_create_workflow(self):
        from agents.ad_agent.core.intent import LLMIntentParser

        intent = LLMIntentParser().parse("跨渠道创建 Meta 和 TikTok campaign", None)

        assert intent.intent_type == "create_campaign"
        assert intent.platforms == ["meta", "tiktok"]

    def test_rule_parser_extracts_tiktok_creation_parameters(self):
        from agents.ad_agent.core.intent import LLMIntentParser

        intent = LLMIntentParser().parse(
            "创建 TikTok campaign name=AndroidTest "
            "objective_type=APP_PROMOTION campaign_type=REGULAR_CAMPAIGN "
            "budget_mode=BUDGET_MODE_DAY",
            None,
        )

        assert intent.platform_params["tiktok"]["objective_type"] == "APP_PROMOTION"
        assert intent.platform_params["tiktok"]["campaign_type"] == "REGULAR_CAMPAIGN"
        assert intent.platform_params["tiktok"]["budget_mode"] == "BUDGET_MODE_DAY"

    def test_bare_campaign_phrase_is_not_copied_between_channels(self):
        parser = LLMIntentParser()
        intent = parser.parse("跨渠道暂停 Meta 和 Google campaign 12345", None)
        assert all(
            "campaign_id" not in intent.platform_params[platform]
            for platform in ("meta", "google")
        )

    def test_cross_platform_pause_is_not_misrouted_to_overview(self):
        from agents.ad_agent.core.intent import LLMIntentParser
        parser = LLMIntentParser()
        intent = parser.parse("跨渠道暂停 Meta 和 TikTok campaign campaign_id=123", None)
        assert intent.intent_type == "cross_channel_batch_pause"
        assert intent.platforms == ["meta", "tiktok"]

    def test_cross_platform_pause_routes_update_tools(self):
        from agents.ad_agent.core.intent import LLMIntentParser
        from agents.ad_agent.capabilities.meta import create_meta_capability
        from agents.ad_agent.capabilities.tiktok import create_tiktok_capability

        validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
        validator.allowed_accounts = {"meta": ["m1"], "tiktok": ["t1"]}
        rt = AgentRuntime(
            persistence_store=AdAgentStore(":memory:"),
            whitelist_validator=validator,
        )
        rt.register_capability(create_meta_capability())
        rt.register_capability(create_tiktok_capability())
        result = rt.run(
            "跨渠道暂停 Meta campaign_id=111 和 TikTok campaign_id=222",
            user_id="u1",
            platform_params={"meta": {"account_id": "m1"}, "tiktok": {"account_id": "t1"}},
        )
        assert result["intent"]["intent_type"] == "cross_channel_batch_pause"
        assert {item["tool"] for item in result["results"]} == {
            "meta_update_campaign", "tiktok_update_campaign",
        }
        assert all(item["data"]["simulated"] for item in result["results"])

    def test_bare_campaign_id_is_not_copied_between_channels(self):
        from agents.ad_agent.core.intent import LLMIntentParser

        intent = LLMIntentParser().parse(
            "跨渠道暂停 Meta 和 TikTok，campaign_id=123",
            None,
        )
        assert "campaign_id" not in intent.platform_params["meta"]
        assert "campaign_id" not in intent.platform_params["tiktok"]

    def test_platform_qualified_campaign_ids_are_not_copied_between_channels(self):
        from agents.ad_agent.core.intent import LLMIntentParser

        intent = LLMIntentParser().parse(
            "跨渠道暂停 Meta campaign_id=111 和 Google campaign_id=222",
            None,
        )
        assert intent.platform_params["meta"]["campaign_id"] == "111"
        assert intent.platform_params["google"]["campaign_id"] == "222"

    def test_platform_qualified_single_campaign_id_is_kept_in_batch_request(self):
        parser = LLMIntentParser()
        intent = parser.parse(
            "批量暂停 Meta campaign_ids=10001,10002 和 Google campaign_ids=20001",
            ToolContext(session_id="s1", user_id="u1"),
        )
        assert intent.platform_params["meta"]["campaign_ids"] == ["10001", "10002"]
        assert intent.platform_params["google"]["campaign_ids"] == ["20001"]


# ─── Runtime 集成测试 ──────────────────────────────────────────

class TestRuntimeQuery:
    def test_runtime_injects_skill_context_before_llm_parsing(self):
        from agents.ad_agent.capabilities.meta import create_meta_capability

        class FakeLLM:
            def __init__(self):
                self.calls = []

            def call(self, messages):
                self.calls.append(messages)
                return '{"intent_type":"list_campaigns","platforms":["meta"]}'

        llm = FakeLLM()
        validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
        validator.allowed_accounts = {"meta": ["m1"]}
        rt = AgentRuntime(
            llm_client=llm,
            whitelist_validator=validator,
            offline_mode=True,
        )
        rt.register_capability(create_meta_capability())
        result = rt.run(
            "查询 Meta campaign",
            user_id="u1",
            account_id="m1",
        )
        assert result["intent"]["intent_type"] == "list_campaigns"
        all_prompt_text = "\n".join(
            message["content"]
            for message in llm.calls[0]
            if message["role"] == "system"
        )
        assert "meta_list_campaigns" in all_prompt_text

    def test_list_campaigns_meta(self, runtime):
        """查询 Meta campaign 列表"""
        result = runtime.run(
            user_input="列出 Meta campaign 列表",
            user_id="test_user",
        )
        assert result["session_id"] is not None
        assert result["intent"]["intent_type"] == "list_campaigns"
        # 应该有工具计划
        tool_plan = result.get("tool_plan", {})
        assert "meta" in tool_plan or result["reply"]

    def test_list_campaigns_google(self, runtime):
        """查询 Google campaign 列表"""
        result = runtime.run(
            user_input="列出 Google Ads campaign 列表",
            user_id="test_user",
        )
        assert result["session_id"] is not None
        assert result["intent"]["intent_type"] == "list_campaigns"

    def test_greeting(self, runtime):
        """问候语回复"""
        result = runtime.run(user_input="你好", user_id="test_user")
        assert "ad-agent" in result["reply"].lower() or "你好" in result["reply"]

    def test_help(self, runtime):
        """帮助信息"""
        result = runtime.run(user_input="帮助", user_id="test_user")
        assert len(result["reply"]) > 0

    def test_unknown_intent(self, runtime):
        """未知意图返回闲聊回复"""
        result = runtime.run(user_input="random stuff", user_id="test_user")
        assert result["reply"] is not None

    def test_cross_platform_query(self, runtime):
        """跨平台查询"""
        result = runtime.run(
            user_input="查询 Meta 和 TikTok 的 campaign",
            user_id="test_user",
        )
        assert result["session_id"] is not None

    def test_account_auto_selected(self, runtime):
        """未指定账户时自动使用白名单中的测试账户"""
        result = runtime.run(
            user_input="列出 Meta campaign",
            user_id="test_user",
        )
        # 应该成功执行（mock handler 不需要真实账户）
        assert result["session_id"] is not None

    def test_multiple_whitelisted_accounts_require_explicit_selection(self):
        from agents.ad_agent.capabilities.meta import create_meta_capability
        validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
        validator.allowed_accounts = {"meta": ["m1", "m2"]}
        rt = AgentRuntime(whitelist_validator=validator, offline_mode=True)
        rt.register_capability(create_meta_capability())

        result = rt.run("列出 Meta campaign", user_id="multi-account-user")

        assert result["needs_confirmation"] is True
        assert result["results"][0]["confirmation_payload"]["type"] == "ask_account"
        assert result["results"][0]["data"] == {}

    def test_runtime_rejects_offline_read_fixtures_by_default(self):
        from agents.ad_agent.capabilities.meta import create_meta_capability
        validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
        validator.allowed_accounts = {"meta": ["m1"]}
        rt = AgentRuntime(whitelist_validator=validator, offline_mode=False)
        rt.register_capability(create_meta_capability())
        result = rt.run(
            "列出 Meta campaign 列表",
            user_id="offline-boundary",
            platform_params={"meta": {"account_id": "m1"}},
        )
        assert result["results"]
        assert result["results"][0]["success"] is False
        assert "offline_mode" in result["results"][0]["error"]

    def test_runtime_can_explicitly_enable_offline_read_fixtures(self):
        from agents.ad_agent.capabilities.meta import create_meta_capability
        validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
        validator.allowed_accounts = {"meta": ["m1"]}
        rt = AgentRuntime(whitelist_validator=validator, offline_mode=True)
        rt.register_capability(create_meta_capability())
        result = rt.run(
            "列出 Meta campaign 列表",
            user_id="offline-explicit",
            platform_params={"meta": {"account_id": "m1"}},
        )
        assert result["results"][0]["success"] is True
        assert result["results"][0]["data"]["data_status"] == "offline_mock"

    def test_business_context_blocks_disallowed_channel(self):
        validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
        validator.allowed_accounts = {"tiktok": ["t1"]}
        rt = AgentRuntime(
            whitelist_validator=validator,
            business_context=BusinessContext(
                business_name="app",
                allowed_channels=["google"],
                disallowed_channels=["tiktok"],
                business_rules={"min_budget": 50, "max_budget": 50000},
            ),
        )
        result = rt.run("列出 TikTok campaign", account_id="t1")
        assert result["results"] == []
        assert "不允许使用 tiktok" in result["policy_errors"][0]

    def test_secret_text_is_redacted_before_llm_and_session(self):
        seen = []

        class LLM:
            def call(self, messages):
                seen.extend(messages)
                return '{"intent_type":"chat","platforms":[]}'

        rt = AgentRuntime(intent_parser=__import__(
            "agents.ad_agent.core.intent", fromlist=["LLMIntentParser"]
        ).LLMIntentParser(LLM()))
        result = rt.run(
            "你好 access_token=SECRET partnerId=PARTNER private_key=KEY",
            session_id="redaction-session",
        )
        serialized = str(seen) + str(rt._sessions["redaction-session"].messages)
        assert "SECRET" not in serialized
        assert "PARTNER" not in serialized
        assert "KEY" not in serialized
        assert "<redacted>" in serialized


class TestSafeWriteExecution:
    class FakeClient:
        def __init__(self, platform):
            self.platform = platform
            self.calls = []

        def __getattr__(self, name):
            def call(*args, **kwargs):
                self.calls.append((name, args, kwargs))
                if name == "list_campaigns":
                    return []
                return "live-id"
            return call

    def _runtime(self, platform, client=None, mode="dry_run"):
        from agents.ad_agent.capabilities.meta import create_meta_capability
        from agents.ad_agent.capabilities.google import create_google_capability
        from agents.ad_agent.capabilities.tiktok import create_tiktok_capability
        from agents.ad_agent.capabilities.dv360 import create_dv360_capability
        validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
        validator.allowed_accounts = {
            "meta": ["m1"], "google-ads": ["g1"],
            "tiktok": ["t1"], "dv360": ["d1"],
        }
        rt = AgentRuntime(
            persistence_store=AdAgentStore(":memory:"),
            whitelist_validator=validator,
            execution_mode=mode,
            allow_live_writes=(mode == ExecutionMode.LIVE.value),
            granted_permissions={"ads.read", "ads.plan", "ads.write"}
            if mode == ExecutionMode.LIVE.value else None,
        )
        factory = {
            "meta": lambda: create_meta_capability(client),
            "google": lambda: create_google_capability(client),
            "tiktok": lambda: create_tiktok_capability(client),
            "dv360": create_dv360_capability,
        }[platform]
        rt.register_capability(factory())
        if mode == ExecutionMode.LIVE.value:
            # Explicit test fixture: production write adapters stay disabled
            # until each provider path is separately verified.
            for tool in rt.registry.list_all():
                if tool.is_write_tool:
                    tool.live_support = True
            # Live execution is an explicit code-side approval.  The fixture
            # opts in only to adapters declared as live-capable.
            rt._live_approved_tools = {
                tool.name for tool in rt.registry.list_all()
                if tool.is_write_tool and tool.live_support
            }
        return rt

    def test_dry_run_never_calls_client_and_preserves_parent_ids(self):
        client = self.FakeClient("meta")
        rt = self._runtime("meta", client)
        result = rt.run("创建 Meta 广告系列 名称=Smoke", account_id="m1")
        assert all(item["success"] for item in result["results"])
        assert all(item["data"]["simulated"] for item in result["results"])
        assert client.calls == []
        assert result["results"][1]["data"]["input"]["campaign_id"].startswith("dry_meta_")
        assert result["results"][2]["data"]["input"]["adset_id"].startswith("dry_meta_")

    def test_cross_platform_create_does_not_share_parent_ids(self):
        from agents.ad_agent.capabilities.meta import create_meta_capability
        from agents.ad_agent.capabilities.google import create_google_capability

        validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
        validator.allowed_accounts = {"meta": ["m1"], "google-ads": ["g1"]}
        rt = AgentRuntime(
            persistence_store=AdAgentStore(":memory:"),
            whitelist_validator=validator,
        )
        rt.register_capability(create_meta_capability())
        rt.register_capability(create_google_capability())
        result = rt.run(
            "创建 Meta 和 Google 广告系列",
            user_id="u1",
            platform_params={
                "meta": {"account_id": "m1", "name": "Meta campaign"},
                "google": {"customer_id": "g1", "campaign_name": "Google campaign"},
            },
        )
        assert all(item["success"] for item in result["results"])
        meta_adset = next(item for item in result["results"] if item["tool"] == "meta_create_adset")
        google_adgroup = next(item for item in result["results"] if item["tool"] == "google_create_ad_group")
        assert meta_adset["data"]["input"]["campaign_id"].startswith("dry_meta_")
        assert google_adgroup["data"]["input"]["campaign_id"].startswith("dry_google-ads_")

    def test_live_write_requires_explicit_confirmation(self):
        client = self.FakeClient("meta")
        rt = self._runtime("meta", client, mode=ExecutionMode.LIVE.value)
        result = rt.run(
            "更新 Meta campaign campaign_id=123 status=PAUSED",
            account_id="m1",
        )
        assert result["needs_confirmation"] is True
        assert result["results"][0]["confirmation_payload"]["type"] == "confirm_write"
        assert client.calls == []

    def test_live_write_idempotency_uses_normalized_input(self):
        client = self.FakeClient("meta")
        rt = self._runtime("meta", client, mode=ExecutionMode.LIVE.value)
        planned = rt.run(
            "更新 Meta campaign campaign_id=123 status=PAUSED",
            session_id="idempotency-session", user_id="same-user", account_id="m1",
        )
        payload = planned["results"][0]["confirmation_payload"]
        first = rt.run(
            "更新 Meta campaign campaign_id=123 status=PAUSED",
            session_id="idempotency-session", user_id="same-user", account_id="m1", confirmed=True,
            confirmation_payload=payload,
        )
        second = rt.run(
            "更新 Meta campaign campaign_id=123 status=PAUSED",
            session_id="idempotency-session", user_id="same-user", account_id="m1", confirmed=True,
            confirmation_payload=payload,
        )
        assert first["results"][0]["success"] is True
        assert second["results"][0]["success"] is False
        assert (
            "approval has already been consumed" in second["results"][0]["error"]
            or "Duplicate write detected" in second["results"][0]["error"]
        )
        assert len(client.calls) == 1

    def test_live_create_chain_stops_after_parent_failure(self):
        class FailingParentClient(self.FakeClient):
            def __getattr__(self, name):
                if name == "create_campaign":
                    def fail(*args, **kwargs):
                        self.calls.append((name, args, kwargs))
                        raise RuntimeError("parent create failed")
                    return fail
                return super().__getattr__(name)

        client = FailingParentClient("meta")
        rt = self._runtime("meta", client, mode=ExecutionMode.LIVE.value)
        planned = rt.run(
            "创建 Meta 广告系列 名称=StopAfterFailure",
            session_id="create-failure-session", account_id="m1",
            platform_params={
                "meta": {
                    "objective": "OUTCOME_SALES",
                    "special_ad_categories": "NONE",
                    "budget": 100,
                }
            },
        )
        result = rt.run(
            "创建 Meta 广告系列 名称=StopAfterFailure",
            session_id="create-failure-session", account_id="m1", confirmed=True,
            confirmation_payload=planned["results"][0]["confirmation_payload"],
            platform_params={
                "meta": {
                    "objective": "OUTCOME_SALES",
                    "special_ad_categories": "NONE",
                    "budget": 100,
                }
            },
        )
        assert result["results"][0]["success"] is False
        assert result["results"][1]["skipped"] is True
        assert result["results"][2]["skipped"] is True
        assert [call[0] for call in client.calls] == ["create_campaign"]

    def test_platform_accounts_are_resolved_independently(self):
        from agents.ad_agent.capabilities.meta import create_meta_capability
        from agents.ad_agent.capabilities.google import create_google_capability
        meta = self.FakeClient("meta")
        google = self.FakeClient("google-ads")
        validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
        validator.allowed_accounts = {"meta": ["m1"], "google-ads": ["g1"]}
        rt = AgentRuntime(persistence_store=AdAgentStore(":memory:"), whitelist_validator=validator)
        rt.register_capability(create_meta_capability(meta))
        rt.register_capability(create_google_capability(google))
        result = rt.run(
            "跨渠道查询 Meta 和 Google campaign",
            platform_params={"meta": {"account_id": "m1"}, "google": {"customer_id": "g1"}},
        )
        assert [call[1][0] for call in meta.calls] == ["m1"]
        assert google.calls == [("list_campaigns", (), {})]

    def test_persistent_session_rejects_different_user_and_account(self):
        store = AdAgentStore(":memory:")
        validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
        validator.allowed_accounts = {"meta": ["meta-test"]}
        first_runtime = AgentRuntime(
            persistence_store=store,
            whitelist_validator=validator,
        )
        first_runtime.register_capability(create_meta_capability_mock())
        first = first_runtime.run(
            "列出 Meta Campaign 列表",
            user_id="owner",
            account_id="meta-test",
        )

        second_runtime = AgentRuntime(
            persistence_store=store,
            whitelist_validator=validator,
        )
        second_runtime.register_capability(create_meta_capability_mock())
        with pytest.raises(PermissionError):
            second_runtime.run(
                "列出 Meta Campaign 列表",
                session_id=first["session_id"],
                user_id="attacker",
                account_id="meta-test",
            )
        with pytest.raises(PermissionError):
            second_runtime.run(
                "列出 Meta Campaign 列表",
                session_id=first["session_id"],
                user_id="owner",
                account_id="other-account",
            )

    def test_runtime_credentials_are_read_only_and_caller_owned_input_is_unchanged(self):
        credentials = {"meta": {"access_token": "caller-token"}}
        rt = AgentRuntime(enforce_account_scope=False)
        rt.register_capability(create_meta_capability_mock())
        result = rt.run("你好", user_id="u1", credentials=credentials)
        assert credentials == {"meta": {"access_token": "caller-token"}}
        session = rt._sessions[result["session_id"]]
        with pytest.raises(TypeError):
            session.ctx.credentials["meta"] = {}

    def test_pause_resume_platform_status_mapping(self):
        rt = self._runtime("tiktok")
        result = rt.run("恢复 TikTok campaign campaign_id=123", account_id="t1")
        assert result["results"][0]["data"]["input"]["updates"] == {"campaign_group_status": 1}

    def test_batch_pause_expands_ids_without_calling_client(self):
        client = self.FakeClient("meta")
        rt = self._runtime("meta", client)
        result = rt.run(
            "批量暂停 Meta campaign_ids=101,102",
            user_id="batch-user",
            platform_params={
                "meta": {"account_id": "m1", "campaign_ids": ["101", "102"]}
            },
        )
        assert result["intent"]["intent_type"] == "cross_channel_batch_pause"
        assert [item["data"]["campaign_id"] for item in result["results"]] == ["101", "102"]
        assert all(item["data"]["input"]["updates"] == {"status": "PAUSED"} for item in result["results"])
        assert client.calls == []
        workflow = rt._session_manager.get_workflow(result["workflow_id"])
        assert workflow["status"] == "planned"
        assert len(workflow["items"]) == 2

    def test_batch_budget_requires_positive_budget(self):
        rt = self._runtime("meta")
        result = rt.run(
            "批量更新 Meta campaign_ids=101,102 预算0元/天",
            user_id="batch-user",
            platform_params={
                "meta": {"account_id": "m1", "campaign_ids": ["101", "102"]}
            },
        )
        assert result["intent"]["intent_type"] == "cross_channel_batch_update_budget"
        assert all(not item["success"] for item in result["results"])
        assert "大于 0" in result["results"][0]["error"]


# ─── Mock Handler 测试 ─────────────────────────────────────────

class TestMockHandlers:
    def test_meta_child_listing_rejects_foreign_parent_before_provider_query(self):
        from agents.ad_agent.capabilities.meta.ad_sets import MetaListAdSetsHandler

        client = MetaAPIClient({"access_token": "caller-token"})
        client.resource_belongs_to_account = lambda *args, **kwargs: False
        client.list_adsets = lambda *args, **kwargs: pytest.fail("foreign parent must be rejected")
        result = MetaListAdSetsHandler(client).execute(
            ToolContext(session_id="s1", user_id="u1", account_id="account-a"),
            {"campaign_id": "campaign-from-b"},
        )
        assert result.success is False
        assert "does not belong" in result.error

    def test_meta_list_campaigns_handler(self):
        handler = MetaListCampaignsHandler()
        ctx = ToolContext(session_id="s1", user_id="u1", account_id="2806375919473667")
        result = handler.execute(ctx, {"account_id": "2806375919473667"})
        assert result.success
        assert "campaigns" in result.data or result.data  # mock data

    def test_google_list_campaigns_handler(self):
        handler = GoogleListCampaignsHandler()
        ctx = ToolContext(session_id="s1", user_id="u1", account_id="9055507554")
        result = handler.execute(ctx, {"customer_id": "9055507554"})
        assert result.success

    def test_tiktok_list_campaigns_handler(self):
        handler = TikTokListCampaignsHandler()
        ctx = ToolContext(session_id="s1", user_id="u1", account_id="7397068114548195329")
        result = handler.execute(ctx, {"account_id": "7397068114548195329"})
        assert result.success

    def test_dv360_list_campaigns_handler(self):
        handler = DV360ListCampaignsHandler()
        ctx = ToolContext(session_id="s1", user_id="u1", account_id="5110831")
        result = handler.execute(ctx, {"advertiser_id": "5110831"})
        assert result.success


# ─── Session 管理测试 ──────────────────────────────────────────

class TestSessionManager:
    def test_create_and_get_session(self, store):
        sm = SessionManager(store)
        sm.create_session("sess-1", "user-1", "acc-1")
        session = sm.get_session("sess-1")
        assert session is not None
        assert session["user_id"] == "user-1"
        assert session["account_id"] == "acc-1"

    def test_list_sessions(self, store):
        sm = SessionManager(store)
        sm.create_session("sess-1", "user-1")
        sm.create_session("sess-2", "user-1")
        sessions = sm.list_sessions("user-1")
        assert len(sessions) == 2

    def test_tool_call_recording(self, store):
        sm = SessionManager(store)
        sm.create_session("sess-1", "user-1")
        from agents.ad_agent.persistence.store import ToolCallRecord
        record = ToolCallRecord(
            id="tc-1", session_id="sess-1", turn_id="turn-1",
            tool_name="meta_list_campaigns", platform="meta",
            input_data={"account_id": "123"}, success=True,
            started_at="2026-01-01T00:00:00", ended_at="2026-01-01T00:00:01",
        )
        sm.record_tool_call("sess-1", "turn-1", record)
        calls = sm.get_session_history("sess-1")
        assert len(calls) == 1
        assert calls[0].tool_name == "meta_list_campaigns"

    def test_campaign_state_is_scoped_by_account(self, store):
        sm = SessionManager(store)
        sm.save_campaign("google-ads", "42", "A", account_id="customer-a")
        sm.save_campaign("google-ads", "42", "B", account_id="customer-b")

        first = sm.get_campaign("google-ads", "42", "customer-a")
        second = sm.get_campaign("google-ads", "42", "customer-b")
        assert first.name == "A"
        assert second.name == "B"
        assert len(sm.list_campaigns("google-ads", account_id="customer-a")) == 1


class TestIterationContracts:
    def test_dv360_uses_line_item_report_contract(self):
        capability = DV360Capability()
        definitions = {definition.name: definition for definition, _ in capability.register_tools()}
        assert "dv360_get_line_item_report" in definitions
        assert "dv360_get_campaign_report" not in definitions
        assert definitions["dv360_get_line_item_report"].input_schema.required == [
            "advertiser_id", "line_item_id"
        ]

    def test_dv360_line_item_report_normalizes_relative_dates(self):
        class DV360Client:
            platform = "dv360"

            def __init__(self):
                self.calls = []

            def get_line_item_report(self, advertiser_id, line_item_id, date_from=None, date_to=None):
                self.calls.append((advertiser_id, line_item_id, date_from, date_to))
                return [{"line_item_id": line_item_id, "impressions": 1}]

        client = DV360Client()
        result = DV360GetLineItemReportHandler(client).execute(
            ToolContext(session_id="s1", user_id="u1", account_id="adv-1"),
            {
                "advertiser_id": "adv-1",
                "line_item_id": "li-1",
                "date_range": {"start_date": "LAST_7_DAYS", "end_date": "TODAY"},
            },
        )
        assert result.success is True
        assert client.calls[0][0:2] == ("adv-1", "li-1")
        assert client.calls[0][2].count("-") == 2
        assert client.calls[0][3].count("-") == 2

    def test_dv360_report_routes_with_line_item_id(self):
        from agents.ad_agent.capabilities.dv360 import create_dv360_capability

        rt = AgentRuntime(enforce_account_scope=True, offline_mode=True)
        rt.register_capability(create_dv360_capability())
        result = rt.run(
            "下载 DV360 line_item_id=li-1 最近7天报表",
            user_id="u1",
            account_id="5110831",
        )
        assert result["tool_plan"] == {"dv360": ["dv360_get_line_item_report"]}
        assert result["results"][0]["success"] is True

    def test_tiktok_http_statuses_are_classified_by_failure_type(self):
        client = TikTokAPIClient({"access_token": "caller-token"})
        assert isinstance(client._handle_error({"data": {}}, 400), APIError)
        assert not isinstance(client._handle_error({"data": {}}, 400), TemporaryError)
        assert isinstance(client._handle_error({"data": {}}, 401), AuthError)
        assert isinstance(client._handle_error({"data": {}}, 403), AuthError)
        assert isinstance(client._handle_error({"data": {}}, 429), RateLimitError)
        assert isinstance(client._handle_error({"data": {}}, 503), TemporaryError)

    def test_all_provider_clients_preserve_http_failures_and_do_not_retry_post(self):
        clients = [
            MetaAPIClient({"access_token": "caller-token"}),
            GoogleAdsAPIClient({"access_token": "caller-token"}),
            TikTokAPIClient({"access_token": "caller-token"}),
            DV360APIClient({"access_token": "caller-token"}),
        ]
        for client in clients:
            calls = []

            def fake_request(method, url, **kwargs):
                calls.append(method)
                return {"status_code": 400, "data": {}, "headers": {}}

            client._do_request = fake_request
            with pytest.raises(APIError):
                client.request_raw("GET", "/resource")
            assert calls == ["GET"]

        # POST is non-idempotent by default. A transient response must not be
        # retried unless the caller opts into retry_non_idempotent explicitly.
        client = TikTokAPIClient(
            {"access_token": "caller-token"},
            retry_config=RetryConfig(max_retries=2, base_delay=0, max_delay=0, jitter=False),
        )
        calls = []

        def transient_request(method, url, **kwargs):
            calls.append(method)
            return {"status_code": 503, "data": "upstream unavailable", "headers": {}}

        client._do_request = transient_request
        with pytest.raises(TemporaryError):
            client.request_raw("POST", "/write")
        assert calls == ["POST"]

    def test_request_raw_preserves_envelope_and_retries(self):
        class EnvelopeClient(BasePlatformClient):
            def __init__(self):
                super().__init__(
                    {}, "fake",
                    RetryConfig(max_retries=1, base_delay=0, max_delay=0, jitter=False),
                )
                self.responses = [
                    {"status_code": 503, "data": {}, "headers": {}},
                    {"status_code": 200, "data": {"value": 7}, "headers": {"x": "1"}},
                ]

            def _do_request(self, method, url, **kwargs):
                return self.responses.pop(0)

            def _extract_data(self, response):
                return response["data"]

            def _handle_error(self, response, status_code):
                return TemporaryError("temporary") if status_code >= 500 else None

        client = EnvelopeClient()
        raw = client.request_raw("GET", "/resource")
        assert raw["headers"]["x"] == "1"
        data = EnvelopeClient().request("GET", "/resource")
        assert data["value"] == 7

    def test_google_update_surfaces_raw_http_failure(self):
        client = GoogleAdsAPIClient({"access_token": "caller-token", "customer_id": "c1"})
        client.request_raw = lambda *args, **kwargs: {
            "status_code": 400,
            "data": {"error": {"message": "bad request"}},
            "headers": {},
        }
        with pytest.raises(APIError):
            client.update_campaign("123", {"status": "PAUSED"})

    def test_meta_ad_requires_explicit_creative(self):
        client = MetaAPIClient({"access_token": "caller-token"})
        with pytest.raises(ValueError, match="creative"):
            client.create_ad("act_test", "adset-1", {"name": "unsafe-default"})

    def test_capability_tools_publish_route_metadata(self):
        from agents.ad_agent.capabilities.meta import create_meta_capability
        from agents.ad_agent.capabilities.google import create_google_capability
        from agents.ad_agent.capabilities.tiktok import create_tiktok_capability
        from agents.ad_agent.capabilities.dv360 import create_dv360_capability
        registry = SimpleToolRegistry()
        for capability in [
            create_meta_capability(),
            create_google_capability(),
            create_tiktok_capability(),
            create_dv360_capability(),
        ]:
            runtime = capability.configure(type("Context", (), {"registry": registry})())
            assert runtime is not None
        assert all(tool.intent_types for tool in registry.list_all())
        # DV360 IO/Line Item reads and Google PMax Asset Group planning are
        # now part of the executable capability contract.
        assert len(registry.list_all()) == 122

    def test_google_access_token_is_local_and_caller_credentials_unchanged(self):
        credentials = {"access_token": "caller-token", "customer_id": "g1"}
        client = GoogleAdsAPIClient(credentials)
        assert client._ensure_valid_token() == "caller-token"
        assert credentials == {"access_token": "caller-token", "customer_id": "g1"}

    def test_dv360_uses_caller_managed_access_token_without_refresh(self):
        credentials = {"access_token": "caller-token", "advertiser_id": "adv-1"}
        client = DV360APIClient(credentials)
        client._exchange_token = lambda assertion: pytest.fail(
            "caller-managed access token must not trigger JWT exchange"
        )
        assert client._get_access_token() == "caller-token"
        assert credentials == {"access_token": "caller-token", "advertiser_id": "adv-1"}

    def test_extended_creative_capabilities_are_real_registry_tools(self):
        from agents.ad_agent.capabilities.meta import create_meta_capability
        from agents.ad_agent.capabilities.tiktok import create_tiktok_capability

        registry = SimpleToolRegistry()
        for capability in (create_meta_capability(), create_tiktok_capability()):
            capability.configure(type("Context", (), {"registry": registry})())
        names = {tool.name for tool in registry.list_all()}
        assert "meta_create_creative" in names
        assert {"tiktok_list_creatives", "tiktok_list_videos", "tiktok_list_images"} <= names

    def test_tiktok_media_handler_uses_provider_client_and_preserves_filter(self):
        from agents.ad_agent.capabilities.tiktok.creatives import TikTokListCreativesHandler

        class TikTokClient:
            def __init__(self):
                self.calls = []

            def list_creatives(self, advertiser_id, filtering=None, page_size=20):
                self.calls.append((advertiser_id, filtering, page_size))
                return [{"creative_id": "c1"}]

        client = TikTokClient()
        result = TikTokListCreativesHandler(client).execute(
            ToolContext(session_id="s1", user_id="u1", account_id="a1"),
            {"filtering": [{"field": "status", "operator": "IN", "values": ["ENABLE"]}], "limit": 7},
        )
        assert result.success is True
        assert result.data["creatives"] == [{"creative_id": "c1"}]
        assert client.calls[0][0] == "a1"
        assert client.calls[0][2] == 7

    def test_google_keyword_query_preserves_hierarchy_filters(self):
        from agents.ad_agent.capabilities.google.keywords import GoogleListKeywordsHandler

        client = GoogleAdsAPIClient({"access_token": "caller-token", "customer_id": "g1"})
        queries = []
        client._search_all = lambda query, page_size=100: (
            queries.append((query, page_size)) or [{
                "campaign": {"id": "10"},
                "adGroup": {"id": "20"},
                "adGroupCriterion": {
                    "criterionId": "30",
                    "status": "ENABLED",
                    "keyword": {"text": "shoes", "matchType": "EXACT"},
                },
            }]
        )
        result = GoogleListKeywordsHandler(client).execute(
            ToolContext(session_id="s1", user_id="u1", account_id="g1"),
            {"campaign_id": "10", "ad_group_id": "20", "limit": 11},
        )
        assert result.success is True
        assert result.data["keywords"][0]["text"] == "shoes"
        assert "campaign.id = 10" in queries[0][0]
        assert "ad_group.id = 20" in queries[0][0]
        assert queries[0][1] == 11

    def test_custom_skill_registers_only_declared_tools_and_can_unload(self):
        from agents.ad_agent.core.interfaces import Skill as CoreSkill

        class CustomSkill(CoreSkill):
            name = "custom-meta-insights"
            platform = "meta"
            description = "Custom read-only extension"

            def __init__(self):
                self.definition = ToolDefinition(
                    name="custom_meta_insight",
                    skill=self.name,
                    platform=self.platform,
                    description="Read a custom local insight",
                    input_schema=ToolSchema(),
                    intent_types=["custom_meta_insight_intent"],
                )

            def get_tools(self):
                return [self.definition]

            def get_tool_handler(self, tool_name):
                if tool_name != self.definition.name:
                    return None

                class Handler:
                    def execute(self, ctx, input_data):
                        return ToolResult.ok({"source": "custom"})

                return Handler()

        rt = AgentRuntime(enforce_account_scope=False)
        skill = CustomSkill()
        rt.register_skill(skill, "meta")
        assert [tool.name for tool in rt.registry.list_all()] == ["custom_meta_insight"]
        assert rt._execute_tool(ToolContext("s1", "u1"), "custom_meta_insight", {}).data == {
            "source": "custom"
        }
        from agents.ad_agent.core.interfaces import ParsedIntent
        routed = rt.intent_router.route(
            ParsedIntent("custom_meta_insight_intent", "", ["meta"]),
            rt.registry,
        )
        assert [tool.name for tool in routed["meta"]] == ["custom_meta_insight"]
        assert rt.unload_skill("meta") is True
        assert rt.registry.list_all() == []

    def test_skill_directory_plugin_is_auto_discovered(self, tmp_path):
        skill_root = tmp_path / "skills"
        skill_dir = skill_root / "channels" / "custom-insights"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: custom-insights\nplatform: meta\n---\n"
            "# Custom local Skill\n",
            encoding="utf-8",
        )
        (skill_dir / "tools.py").write_text(
            "from agents.ad_agent.core.interfaces import ToolDefinition, ToolSchema, ToolResult\n"
            "from agents.ad_agent.core.interfaces import Skill as CoreSkill\n"
            "class LocalSkill(CoreSkill):\n"
            "    name = 'custom-insights'\n"
            "    platform = 'meta'\n"
            "    description = 'Local insight extension'\n"
            "    def __init__(self):\n"
            "        self.definition = ToolDefinition(name='custom_insight', skill=self.name, platform=self.platform, description='local insight', input_schema=ToolSchema(), intent_types=['custom_insight'])\n"
            "    def get_tools(self):\n"
            "        return [self.definition]\n"
            "    def get_tool_handler(self, tool_name):\n"
            "        if tool_name != self.definition.name:\n"
            "            return None\n"
            "        class Handler:\n"
            "            def execute(self, ctx, input_data):\n"
            "                return ToolResult.ok({'source': 'plugin'})\n"
            "        return Handler()\n"
            "def create_skill(api_client=None):\n"
            "    return LocalSkill()\n",
            encoding="utf-8",
        )

        rt = AgentRuntime(enforce_account_scope=False)
        assert rt.auto_load_skills(str(skill_root)) == 1
        assert [tool.name for tool in rt.registry.list_all()] == ["custom_insight"]
        result = rt._execute_tool(
            ToolContext("s1", "u1"), "custom_insight", {}
        )
        assert result.success is True
        assert result.data == {"source": "plugin"}

    def test_skill_loader_supports_nested_frontmatter_metadata(self, tmp_path):
        from agents.ad_agent.runtime.skill import SkillLoader

        skill_dir = tmp_path / "channels" / "nested-insights"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            "skill:\n"
            "  name: nested-insights\n"
            "  platform: meta\n"
            "  description: Nested metadata extension\n"
            "  version: '2.0'\n"
            "---\n"
            "# Nested Skill\n",
            encoding="utf-8",
        )

        skills = SkillLoader(str(tmp_path)).load_all()

        assert skills["nested-insights"].platform == "meta"
        assert skills["nested-insights"].description == "Nested metadata extension"
        assert skills["nested-insights"].version == "2.0"

    def test_declarative_skill_contract_preserves_full_input_schema(self, tmp_path):
        from agents.ad_agent.runtime.skill import BaseSkill, SkillContract

        skill_dir = tmp_path / "channels" / "schema-insights"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: schema-insights\nplatform: meta\n---\n",
            encoding="utf-8",
        )
        (skill_dir / "contract.yaml").write_text(
            "tools:\n"
            "  schema_insight:\n"
            "    description: Schema-aware extension\n"
            "    risk: low\n"
            "    effect: read\n"
            "    resource_type: custom_child\n"
            "    parent_resource_type: custom_parent\n"
            "    resource_id_field: child_key\n"
            "    parent_resource_id_field: parent_key\n"
            "    input_schema:\n"
            "      required: [mode]\n"
            "      properties:\n"
            "        mode:\n"
            "          type: string\n"
            "          enum: [FAST, SAFE]\n"
            "      conditional_rules:\n"
            "        - if: {mode: SAFE}\n"
            "          required: [audit_id]\n",
            encoding="utf-8",
        )

        contract = SkillContract(str(skill_dir)).load()
        definition = BaseSkill(contract).get_tools()[0]

        assert definition.input_schema.properties["mode"]["enum"] == ["FAST", "SAFE"]
        assert definition.input_schema.conditional_rules[0]["required"] == ["audit_id"]
        assert definition.resource_id_field == "child_key"
        assert definition.parent_resource_id_field == "parent_key"

    def test_provider_list_pagination_is_consumed(self):
        meta = MetaAPIClient({"access_token": "caller-token"})
        meta_pages = iter([
            {"data": [{"id": "m1"}], "paging": {"cursors": {"after": "next"}}},
            {"data": [{"id": "m2"}], "paging": {}},
        ])
        meta.request = lambda *args, **kwargs: next(meta_pages)
        assert [x["id"] for x in meta.list_campaigns("account-1")] == ["m1", "m2"]

        tiktok = TikTokAPIClient({"access_token": "caller-token"})
        tiktok_pages = iter([
            {"status_code": 200, "data": {"code": 0, "data": {
                "list": [{"campaign_id": "t1"}],
                "page_info": {"total_page": 2},
            }}},
            {"status_code": 200, "data": {"code": 0, "data": {
                "list": [{"campaign_id": "t2"}],
                "page_info": {"total_page": 2},
            }}},
        ])
        tiktok.request_raw = lambda *args, **kwargs: next(tiktok_pages)
        assert [x["campaign_id"] for x in tiktok.list_campaigns("advertiser-1")] == ["t1", "t2"]

        dv360 = DV360APIClient({"access_token": "caller-token"})
        dv_pages = iter([
            {"data": {"campaigns": [{"name": "d1"}], "nextPageToken": "next"}},
            {"data": {"campaigns": [{"name": "d2"}]}},
        ])
        dv360.request_raw = lambda *args, **kwargs: next(dv_pages)
        assert [x["name"] for x in dv360.list_campaigns("advertiser-1")] == ["d1", "d2"]

        google = GoogleAdsAPIClient({"access_token": "caller-token", "customer_id": "c1"})
        google_pages = iter([
            {"data": {"results": [{"campaign": {"id": "g1", "name": "G1"}}], "nextPageToken": "next"}},
            {"data": {"results": [{"campaign": {"id": "g2", "name": "G2"}}]}},
        ])
        google._search = lambda *args, **kwargs: next(google_pages)
        assert [x["id"] for x in google.list_campaigns()] == ["g1", "g2"]

    def test_cross_channel_aggregation_preserves_metrics_and_status(self):
        summary = CrossChannelAggregator().aggregate([
            {
                "platform": "meta",
                "data": {
                    "data_status": "live",
                    "campaigns": [{
                        "id": "1", "name": "m", "metrics": {
                            "impressions": 100, "clicks": 10, "spend": 20, "conversions": 2,
                        }, "currency": "USD",
                    }],
                },
            },
            {
                "platform": "google",
                "data": {
                    "data_status": "offline_mock",
                    "campaigns": [{
                        "id": "2", "name": "g", "metrics": {
                            "impressions": 200, "clicks": 20, "spend": 30, "conversions": 3,
                        }, "currency": "USD",
                    }],
                },
            },
        ])
        assert summary["total_campaigns"] == 2
        assert summary["totals"]["spend"] == 50
        assert summary["totals"]["ctr"] == 30 / 300
        assert summary["platforms"]["google"]["data_status"] == "offline_mock"

    def test_cross_channel_does_not_add_different_currencies(self):
        summary = CrossChannelAggregator().aggregate([
            {"platform": "meta", "data": {"campaigns": [{"metrics": {"spend": 10}, "currency": "USD"}]}},
            {"platform": "tiktok", "data": {"campaigns": [{"metrics": {"spend": 10}, "currency": "CNY"}]}},
        ])
        assert "spend" not in summary["totals"]
        assert summary["comparability"]["status"] == "partial"

    def test_cross_channel_does_not_infer_report_currency_from_listing_row(self):
        summary = CrossChannelAggregator().aggregate([
            {"platform": "meta", "data": {"campaigns": [{
                "id": "m1", "name": "Meta", "currency": "USD",
            }]}},
            {"platform": "meta", "data": {"report": [{
                "campaign_id": "m1", "spend": 25, "impressions": 10,
            }]}},
        ])
        record = summary["platforms"]["meta"]["records"][0]
        assert record["metrics"]["impressions"] == 10
        assert "spend" not in record["metrics"]
        assert "spend" not in summary["totals"]

    def test_cross_channel_does_not_merge_unknown_currency_with_known_currency(self):
        summary = CrossChannelAggregator().aggregate([
            {"platform": "meta", "data": {"campaigns": [{
                "id": "m1", "metrics": {"spend": 10, "currency": "USD"},
            }]}},
            {"platform": "tiktok", "data": {"campaigns": [{
                "id": "t1", "metrics": {"spend": 20},
            }]}},
        ])
        assert "spend" not in summary["totals"]
        assert summary["comparability"]["status"] == "partial"
        assert "未知货币" in summary["comparability"]["reason"]

    def test_cross_channel_compare_collects_campaign_scoped_reports(self):
        from agents.ad_agent.capabilities.meta import create_meta_capability
        from agents.ad_agent.capabilities.google import create_google_capability

        class MetaClient:
            platform = "meta"

            def __init__(self):
                self.report_calls = []

            def list_campaigns(self, account_id):
                return [{"id": "m1", "name": "Meta 1", "currency": "USD"}]

            def get_campaign_report(self, account_id, campaign_ids, time_range=None):
                self.report_calls.append((account_id, campaign_ids, time_range))
                return [{"campaign_id": "m1", "impressions": 100, "clicks": 10, "spend": 20, "currency": "USD"}]

        class GoogleClient:
            platform = "google"

            def __init__(self):
                self.customer_id = None
                self.report_calls = []

            def list_campaigns(self):
                return [{"id": "g1", "campaign_name": "Google 1"}]

            def get_campaign_report(self, campaign_ids, date_from="LAST_30_DAYS", date_to="TODAY"):
                self.report_calls.append((campaign_ids, date_from, date_to))
                return [{"campaign": {"id": "g1", "name": "Google 1"}, "metrics": {
                    "impressions": 200, "clicks": 20, "cost_micros": 30000000,
                }}]

        meta = MetaClient()
        google = GoogleClient()
        validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
        validator.allowed_accounts = {"meta": ["m1"], "google-ads": ["g1"]}
        rt = AgentRuntime(
            persistence_store=AdAgentStore(":memory:"),
            whitelist_validator=validator,
        )
        rt.register_capability(create_meta_capability(meta))
        rt.register_capability(create_google_capability(google))
        result = rt.run(
            "比较 Meta 和 Google 的 campaign",
            user_id="u1",
            platform_params={
                "meta": {"account_id": "m1"},
                "google": {"customer_id": "g1"},
            },
        )
        assert "meta_get_campaign_report" in result["tool_plan"]["meta"]
        assert "google_get_campaign_report" in result["tool_plan"]["google"]
        assert meta.report_calls == [("m1", ["m1"], None)]
        assert google.report_calls == [(["g1"], "LAST_30_DAYS", "TODAY")]
        assert result["cross_channel_summary"]["totals"]["impressions"] == 300
        # Google's fixture omits currency; do not add its spend to Meta USD.
        assert "spend" not in result["cross_channel_summary"]["totals"]
        assert result["cross_channel_summary"]["platforms"]["meta"]["campaigns"] == 1
        assert result["cross_channel_summary"]["platforms"]["meta"]["records"][0]["name"] == "Meta 1"
        assert result["cross_channel_summary"]["platforms"]["google"]["campaigns"] == 1
        assert result["cross_channel_summary"]["platforms"]["google"]["records"][0]["name"] == "Google 1"

    def test_tiktok_report_preserves_campaign_filter(self):
        from agents.ad_agent.capabilities.tiktok.reports import TikTokGetReportHandler

        class TikTokClient:
            def __init__(self):
                self.campaign_report_calls = []

            def get_campaign_report(self, advertiser_id, campaign_ids, time_range=None):
                self.campaign_report_calls.append((advertiser_id, campaign_ids, time_range))
                return [{"campaign_group_id": "t1", "impressions": 10}]

            def get_report(self, **kwargs):
                raise AssertionError("account-level report must not be used for filtered comparison")

        client = TikTokClient()
        handler = TikTokGetReportHandler(client)
        result = handler.execute(
            ToolContext(session_id="s1", user_id="u1", account_id="a1"),
            {"account_id": "a1", "campaign_ids": ["t1"]},
        )
        assert result.success is True
        assert client.campaign_report_calls == [("a1", ["t1"], None)]

    def test_tiktok_report_sends_json_body_through_data_argument(self):
        client = TikTokAPIClient({"access_token": "caller-token"})
        calls = []

        def fake_request(method, endpoint, **kwargs):
            calls.append((method, endpoint, kwargs))
            return {"data": {}}

        client.request = fake_request
        assert client.get_report("a1", date_preset="LAST_30_DAYS") == {}
        assert calls[0][0:2] == ("POST", "statistics/get/")
        assert calls[0][2]["data"] == {
            "advertiser_id": "a1",
            "report_type": "CAMPAIGN",
            "date_preset": "LAST_30_DAYS",
        }
        assert "json" not in calls[0][2]

    def test_tiktok_campaign_report_normalizes_string_date_preset(self):
        client = TikTokAPIClient({"access_token": "caller-token"})
        normalized = client._normalize_time_range("LAST_30_DAYS")
        assert normalized["start_date"].count("-") == 2
        assert normalized["end_date"].count("-") == 2
        normalized_object = client._normalize_time_range(
            {"start_date": "LAST_30_DAYS", "end_date": "TODAY"}
        )
        assert normalized_object["start_date"].count("-") == 2
        assert normalized_object["end_date"].count("-") == 2

    def test_dv360_line_item_report_accepts_string_date_preset(self):
        from agents.ad_agent.capabilities.dv360.reports import DV360GetLineItemReportHandler
        from agents.ad_agent.core.tool_registry import validate_tool_input

        class DV360Client:
            platform = "dv360"

            def __init__(self):
                self.calls = []

            def get_line_item_report(self, advertiser_id, line_item_id, date_from=None, date_to=None):
                self.calls.append((advertiser_id, line_item_id, date_from, date_to))
                return []

        capability = DV360Capability()
        definition = next(
            definition for definition, _ in capability.register_tools()
            if definition.name == "dv360_get_line_item_report"
        )
        input_data = {
            "advertiser_id": "d1",
            "line_item_id": "li-1",
            "date_range": "LAST_7_DAYS",
        }
        assert validate_tool_input(definition.input_schema, input_data) == []
        client = DV360Client()
        result = DV360GetLineItemReportHandler(client).execute(
            ToolContext(session_id="s1", user_id="u1", account_id="d1"),
            input_data,
        )
        assert result.success is True
        assert client.calls[0][2].count("-") == 2
        assert client.calls[0][3].count("-") == 2

    def test_google_child_handler_uses_runtime_customer_id(self):
        from agents.ad_agent.capabilities.google.ad_groups import GoogleListAdGroupsHandler

        class GoogleClient:
            customer_id = "credential-default"

            def list_ad_groups(self, campaign_id):
                assert self.customer_id == "runtime-customer"
                return []

        result = GoogleListAdGroupsHandler(GoogleClient()).execute(
            ToolContext(session_id="s1", user_id="u1", account_id="runtime-customer"),
            {"campaign_id": "c1"},
        )
        assert result.success is True

    def test_unavailable_live_adapter_is_rejected_before_client(self):
        class FakeClient:
            platform = "google-ads"
            calls = []

        client = FakeClient()
        validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
        validator.allowed_accounts = {"google-ads": ["g1"]}
        rt = AgentRuntime(
            persistence_store=AdAgentStore(":memory:"),
            whitelist_validator=validator,
            execution_mode=ExecutionMode.LIVE.value,
            live_approved_tools={"google_update_campaign"},
            allow_live_writes=True,
            granted_permissions={"ads.read", "ads.plan", "ads.write"},
        )
        from agents.ad_agent.capabilities.google import create_google_capability
        rt.register_capability(create_google_capability(client))
        result = rt.run(
            "更新 Google ad group ad_group_id=123 campaign_id=456 status=PAUSED",
            user_id="u1", account_id="g1", confirmed=True,
        )
        assert result["results"][0]["success"] is False
        assert "仅支持 dry-run" in result["results"][0]["error"]
        assert client.calls == []

    def test_google_campaign_update_accepts_client_platform_alias(self):
        class GoogleClient:
            platform = "google"
            customer_id = None

            def update_campaign(self, campaign_id, updates):
                return {"campaign_id": campaign_id, "updates": updates}

        validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
        validator.allowed_accounts = {"google-ads": ["g1"]}
        rt = AgentRuntime(
            persistence_store=AdAgentStore(":memory:"),
            whitelist_validator=validator,
            execution_mode=ExecutionMode.LIVE.value,
            live_approved_tools={"google_update_campaign"},
            allow_live_writes=True,
            granted_permissions={"ads.read", "ads.plan", "ads.write"},
        )
        from agents.ad_agent.capabilities.google import create_google_capability
        rt.register_capability(create_google_capability(GoogleClient()))
        rt.registry.get("google_update_campaign")[0].live_support = True
        planned = rt.run(
            "更新 Google campaign campaign_id=123 status=PAUSED",
            session_id="google-alias-session", user_id="u1", account_id="g1",
        )
        result = rt.run(
            "更新 Google campaign campaign_id=123 status=PAUSED",
            session_id="google-alias-session", user_id="u1", account_id="g1", confirmed=True,
            confirmation_payload=planned["results"][0]["confirmation_payload"],
        )
        assert result["results"][0]["success"] is True


class TestCrossChannelAnalysis:
    def test_analysis_intents_are_parsed_and_routed(self):
        parser = LLMIntentParser()
        assert parser.parse("跨渠道分析 Meta 和 Google 的表现", None).intent_type == (
            "cross_channel_performance_insights"
        )
        assert parser.parse("跨渠道优化预算 Meta 和 Google，总预算 1000", None).intent_type == (
            "cross_channel_optimize_budget"
        )
        assert parser.parse("跨渠道导出 Meta 和 Google 报表 CSV", None).intent_type == (
            "cross_channel_export_report"
        )

    def test_analyzer_preserves_partial_metrics_and_currency_boundaries(self):
        aggregate = CrossChannelAggregator().aggregate([
            {"platform": "meta", "data": {"campaigns": [{
                "id": "m1", "name": "Meta", "currency": "USD",
                "metrics": {"impressions": 1000, "clicks": 20, "spend": 100,
                             "conversions": 4, "revenue": 400},
            }]}},
            {"platform": "google", "data": {"campaigns": [{
                "id": "g1", "name": "Google", "currency": "CNY",
                "metrics": {"impressions": 500, "clicks": 5},
            }]}},
        ])
        insights = CrossChannelAnalyzer.performance_insights(aggregate)
        assert insights["status"] == "partial"
        assert len(insights["insights"]) == 2
        # A single known currency can still be totaled, while the overall
        # comparison remains partial because Google omitted spend.
        assert aggregate["totals"]["spend"] == 100

        plan = CrossChannelAnalyzer.budget_plan(aggregate, 1000, minimum_budget=100)
        assert plan["status"] == "partial"
        assert sum(row["recommended_budget"] for row in plan["recommendations"]) == 1000

    def test_export_csv_contains_normalized_rows_without_credentials(self):
        aggregate = CrossChannelAggregator().aggregate([{
            "platform": "meta",
            "data": {"campaigns": [{
                "id": "m1", "name": "Campaign", "account_id": "a1",
                "metrics": {"impressions": 10}, "currency": "USD",
                "access_token": "must-not-export",
            }]},
        }])
        exported = CrossChannelAnalyzer.export_csv(aggregate)
        assert "platform,account_id,campaign_id" in exported
        assert "Campaign" in exported
        assert "must-not-export" not in exported

    def test_runtime_offline_insights_are_explicitly_marked(self):
        from agents.ad_agent.capabilities.meta import create_meta_capability

        validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
        validator.allowed_accounts = {"meta": ["m1"]}
        rt = AgentRuntime(
            persistence_store=AdAgentStore(":memory:"),
            whitelist_validator=validator,
            offline_mode=True,
        )
        rt.register_capability(create_meta_capability())
        result = rt.run(
            "跨渠道分析 Meta campaign 表现",
            user_id="analysis-user",
            platform_params={"meta": {"account_id": "m1"}},
        )
        assert result["intent"]["intent_type"] == "cross_channel_performance_insights"
        assert result["cross_channel_insights"]["insights"][0]["data_status"] == "offline_mock"
        assert "不会自动修改" in result["reply"]


def test_meta_get_account_builds_flat_fields_query():
    client = MetaAPIClient({"access_token": "caller-token"})
    calls = {}

    def fake_request(method, endpoint, **kwargs):
        calls.update(method=method, endpoint=endpoint, kwargs=kwargs)
        return {"id": "a1"}

    client.request = fake_request
    assert client.get_account("act_a1", ["id", "name"]) == {"id": "a1"}
    assert calls == {
        "method": "GET",
        "endpoint": "/act_a1",
        "kwargs": {"extra_params": {"fields": "id,name"}},
    }


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
