import pytest

from agents.ad_agent.core.knowledge import MarkdownWikiKnowledgeProvider
from agents.ad_agent.knowledge_management import (
    KnowledgeDocumentError,
    ManagedKnowledgeManager,
    ManagedKnowledgeProvider,
)
from agents.ad_agent.core.memory import MemoryManager
from agents.ad_agent.core.response import LLMResponseSynthesizer
from agents.ad_agent.core.interfaces import ParsedIntent
from agents.ad_agent.persistence.store import AdAgentStore
from agents.ad_agent.runtime.runtime import AgentRuntime


def test_markdown_wiki_is_canonical_and_metadata_is_source_addressable(tmp_path):
    (tmp_path / "platforms" / "google").mkdir(parents=True)
    (tmp_path / "platforms" / "google" / "campaigns.md").write_text(
        "---\n"
        "schema_version: \"1\"\n"
        "id: google-campaigns\n"
        "title: Google campaigns\n"
        "layer: platform\n"
        "knowledge_type: hierarchy\n"
        "platform: google\n"
        "source: official\n"
        "source_ref: https://example.invalid/google\n"
        "version: \"1.2.0\"\n"
        "confidence: 0.9\n"
        "updated_at: \"2026-09-01\"\n"
        "tags: [campaign, hierarchy]\n"
        "status: published\n"
        "---\n\nCampaign hierarchy and budget rules.",
        encoding="utf-8",
    )
    provider = MarkdownWikiKnowledgeProvider(tmp_path)
    result = provider.query("campaign hierarchy", platforms=["google"], limit=1)

    assert len(result) == 1
    assert result[0].document_id == "google-campaigns"
    assert result[0].citation["source_ref"] == "https://example.invalid/google"
    assert result[0].knowledge_type == "hierarchy"
    assert provider.validate() == []


def test_wiki_draft_is_not_retrieved_and_compatibility_facade_uses_same_documents(tmp_path):
    (tmp_path / "expertise").mkdir()
    (tmp_path / "expertise" / "draft.md").write_text(
        "---\nstatus: draft\nknowledge_type: tip\n---\nsecret draft", encoding="utf-8"
    )
    provider = MarkdownWikiKnowledgeProvider(tmp_path)
    assert provider.query("secret draft", limit=10) == []


def test_query_platform_name_is_a_hard_boundary_when_selector_is_all(tmp_path):
    (tmp_path / "platforms").mkdir()
    (tmp_path / "platforms" / "meta.md").write_text(
        "---\nplatform: meta\ntitle: Meta 广告类型\nstatus: published\n---\n\nMeta Campaign、Ad Set 和 Ad 层级。",
        encoding="utf-8",
    )
    (tmp_path / "platforms" / "google.md").write_text(
        "---\nplatform: google-ads\ntitle: Google 广告类型\nstatus: published\n---\n\nGoogle Search 广告，也提到 Meta 作为对比。",
        encoding="utf-8",
    )
    (tmp_path / "platforms" / "general.md").write_text(
        "---\nplatform: all\ntitle: 跨平台广告类型总览\nstatus: published\n---\n\nMeta 和 Google 的广告类型总览。",
        encoding="utf-8",
    )
    provider = MarkdownWikiKnowledgeProvider(tmp_path)

    results = provider.query("Meta 广告类型", limit=10)

    assert results
    assert all(item.platform == "meta" for item in results)


def test_managed_wiki_documents_are_versioned_published_and_tenant_scoped():
    store = AdAgentStore(":memory:")
    manager = ManagedKnowledgeManager(store)
    created = manager.create_document(
        "tenant-a",
        {
            "title": "Meta 广告类型选择规则",
            "content": "# 选择建议\n\n- 转化目标优先使用 Conversion\n- 线索目标使用 Lead",
            "platform": "meta",
            "layer": "business",
            "knowledge_type": "best_practice",
            "source": "投放团队",
            "tags": ["Meta", "广告类型"],
        },
        "user-a",
    )
    provider = ManagedKnowledgeProvider(MarkdownWikiKnowledgeProvider("/path/that/does/not/exist"), store)

    assert provider.query("Meta 广告类型", tenant_id="tenant-a") == []
    published = manager.publish("tenant-a", created["document_id"])
    assert published["status"] == "published"
    results = provider.query("Meta 广告类型", tenant_id="tenant-a", limit=5)
    assert results[0].title == "Meta 广告类型选择规则"
    assert provider.query("Meta 广告类型", tenant_id="tenant-b") == []
    assert "schema_version: \"1\"" in published["markdown"]

    unpublished = manager.unpublish("tenant-a", created["document_id"])
    assert unpublished["status"] == "draft"
    assert provider.query("Meta 广告类型", tenant_id="tenant-a") == []


def test_managed_wiki_rejects_credential_content():
    manager = ManagedKnowledgeManager(AdAgentStore(":memory:"))
    with pytest.raises(KnowledgeDocumentError):
        manager.create_document(
            "tenant-a",
            {"title": "不安全文档", "content": "access_token: do-not-store"},
            "user-a",
        )


def test_memory_is_scoped_and_deleted_without_becoming_tool_state():
    store = AdAgentStore(":memory:")
    manager = MemoryManager(store)
    record = manager.remember(
        "团队偏好使用 Google 搜索广告",
        tenant_id="tenant-a",
        user_id="user-a",
        tags=["preference"],
    )

    assert manager.recall("Google 搜索广告", tenant_id="tenant-a", user_id="user-a")[0].memory_id == record.memory_id
    assert manager.recall("Google 搜索广告", tenant_id="tenant-b", user_id="user-a") == []
    assert manager.forget(record.memory_id, tenant_id="tenant-b", user_id="user-a") is False
    assert manager.forget(record.memory_id, tenant_id="tenant-a", user_id="user-a") is True
    assert manager.recall("Google 搜索广告", tenant_id="tenant-a", user_id="user-a") == []


def test_memory_expiry_is_enforced_by_the_backend():
    store = AdAgentStore(":memory:")
    manager = MemoryManager(store)
    manager.remember(
        "临时测试偏好",
        tenant_id="tenant-a",
        user_id="user-a",
        expires_at="2000-01-01T00:00:00+00:00",
    )
    assert manager.recall("临时测试偏好", tenant_id="tenant-a", user_id="user-a") == []


def test_memory_policy_rejects_empty_and_redacts_credential_like_values():
    store = AdAgentStore(":memory:")
    manager = MemoryManager(store)
    assert manager.explicit_memory_text("请记住我的偏好：优先使用 TikTok") == "偏好：优先使用 TikTok"
    record = manager.remember(
        "client_secret=do-not-store",
        tenant_id="tenant-a",
        user_id="user-a",
    )
    assert "do-not-store" not in record.content


def test_runtime_recalls_explicit_memory_across_sessions_without_granting_tools():
    class FakeLLM:
        def __init__(self):
            self.calls = []

        def call(self, messages):
            self.calls.append(messages)
            return '{"intent_type":"chat","platforms":[]}'

    llm = FakeLLM()
    store = AdAgentStore(":memory:")
    runtime = AgentRuntime(
        require_llm=True,
        llm_client=llm,
        persistence_store=store,
        enforce_account_scope=False,
        features=[],
    )
    runtime.run("请记住我的偏好：优先使用 Google 搜索广告", user_id="u1", tenant_id="t1")
    result = runtime.run("我的广告偏好是什么？", user_id="u1", tenant_id="t1")

    assert result["memory"][0]["content"] == "偏好：优先使用 Google 搜索广告"
    assert any(
        "Memory" in str(message.get("content"))
        for message in llm.calls[-1]
    )
    assert result["tool_plan"] == {}


def test_llm_response_synthesizer_is_grounded_and_rejects_internal_protocol():
    class FakeLLM:
        def __init__(self, answer):
            self.answer = answer

        def call(self, _messages):
            return self.answer

    intent = ParsedIntent("list_campaigns", "查询", ["google"])
    result = [{
        "tool": "google_list_campaigns",
        "platform": "google",
        "success": True,
        "data": {"campaigns": [{"name": "Demo", "status": "PAUSED"}]},
    }]
    synthesizer = LLMResponseSynthesizer()
    answer = synthesizer.synthesize(
        FakeLLM("找到 1 个 Campaign：Demo，状态为 PAUSED。"),
        user_input="查询 Google Campaign",
        intent=intent,
        results=result,
        knowledge=[],
        analysis={},
        fallback_reply="fallback",
    )
    assert "PAUSED" in answer
    assert synthesizer.synthesize(
        FakeLLM('{"intent_type":"list_campaigns"}'),
        user_input="查询",
        intent=intent,
        results=result,
        knowledge=[],
        analysis={},
        fallback_reply="fallback",
    ) is None
    assert synthesizer.synthesize(
        FakeLLM("查询未执行任何 dry-run，也未调用 Google Ads API。"),
        user_input="查询 Google Ads 报表",
        intent=intent,
        results=[{
            "tool": "google_list_campaigns",
            "platform": "google",
            "success": False,
            "error": "provider unavailable",
        }],
        knowledge=[],
        analysis={},
        fallback_reply="暂时无法读取 Google Ads 广告账户，请检查账户连接。",
    ) is None


def test_runtime_inject_llm_enables_response_synthesis_after_late_bootstrap():
    class FakeLLM:
        def call(self, _messages):
            return '{"intent_type":"chat","platforms":[]}'

    runtime = AgentRuntime(require_llm=True, features=[])
    assert runtime.response_synthesizer is None
    runtime.inject_llm(FakeLLM())
    assert runtime.response_synthesizer is not None
