import pytest

from agents.ad_agent.domain.ad.knowledge import MarkdownWikiKnowledgeProvider
from agents.ad_agent.knowledge_management import (
    KnowledgeDocumentError,
    ManagedKnowledgeManager,
    ManagedKnowledgeProvider,
)
from agents.ad_agent.core.memory import MemoryManager
from agents.ad_agent.core.intent import LLMIntentParser
from agents.ad_agent.domain.ad.response import LLMResponseSynthesizer
from agents.ad_agent.core.interfaces import ParsedIntent, ToolContext
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
        "category: platform_foundation\n"
        "subcategory: campaign-hierarchy\n"
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
    assert result[0].category == "platform_foundation"
    assert result[0].subcategory == "campaign-hierarchy"
    assert result[0].to_dict()["category"] == "platform_foundation"
    assert provider.validate() == []


def test_builtin_wiki_exposes_navigation_categories_for_each_platform():
    provider = MarkdownWikiKnowledgeProvider("agents/ad_agent/knowledge_base")

    assert all(document.excerpt.strip() for document in provider.documents)

    categories = {
        document.platform: {document.category for document in provider.documents}
        for document in provider.documents
        if document.platform in {"google-ads", "meta", "tiktok", "dv360"}
    }

    assert all(categories.get(platform) for platform in {"google-ads", "meta", "tiktok", "dv360"})
    assert "platform_foundation" in categories["google-ads"]
    assert "measurement" in categories["meta"]
    assert "optimization" in categories["tiktok"]
    assert "campaign_operations" in categories["dv360"]


def test_markdown_wiki_retrieves_the_matching_heading_from_long_documents(tmp_path):
    (tmp_path / "platforms").mkdir()
    (tmp_path / "platforms" / "bidding.md").write_text(
        "---\n"
        "id: bidding-guide\n"
        "title: 出价策略指南\n"
        "platform: all\n"
        "status: published\n"
        "---\n\n"
        "# 出价策略指南\n\n"
        "## 预算准备\n\n"
        "先确认日预算、账户余额和学习期状态。\n\n"
        "## tCPA 学习期\n\n"
        "tCPA 调整后需要观察转化量，避免频繁改动目标成本。\n\n"
        "## 素材配合\n\n"
        "素材应保持稳定，方便判断出价变化带来的影响。",
        encoding="utf-8",
    )
    provider = MarkdownWikiKnowledgeProvider(tmp_path)

    result = provider.query("tCPA 学习期", limit=1, max_excerpt_chars=300)

    assert len(result) == 1
    assert result[0].document_id == "bidding-guide"
    assert result[0].section == "tCPA 学习期"
    assert result[0].heading_path == ("出价策略指南", "tCPA 学习期")
    assert result[0].chunk_count == 3
    assert "避免频繁改动" in result[0].excerpt


def test_markdown_wiki_catalog_returns_the_complete_document(tmp_path):
    (tmp_path / "guide.md").write_text(
        "---\nid: full-guide\ntitle: 完整指南\nplatform: all\nstatus: published\n---\n\n"
        "# 完整指南\n\n## 第一节\n\n开头说明。\n\n## 第二节\n\n这里是目录不应丢失的正文。",
        encoding="utf-8",
    )
    provider = MarkdownWikiKnowledgeProvider(tmp_path)

    result = provider.catalog(limit=10)

    assert len(result) == 1
    assert "第二节" in result[0].excerpt
    assert "目录不应丢失的正文" in result[0].excerpt


def test_markdown_wiki_weights_title_and_heading_matches_without_vectors(tmp_path):
    (tmp_path / "a.md").write_text(
        "---\nid: title-hit\ntitle: Meta 广告类型选择\nplatform: meta\nstatus: published\n---\n\n选择规则。",
        encoding="utf-8",
    )
    (tmp_path / "b.md").write_text(
        "---\nid: body-hit\ntitle: Meta 投放经验\nplatform: meta\nstatus: published\n---\n\n"
        "广告类型相关经验：广告类型需要结合目标选择。",
        encoding="utf-8",
    )
    provider = MarkdownWikiKnowledgeProvider(tmp_path)

    result = provider.query("Meta 广告类型", platforms=["meta"], limit=2)

    assert [item.document_id for item in result] == ["title-hit", "body-hit"]
    assert all(item.retrieval_method == "lexical_bm25" for item in result)


def test_markdown_wiki_exposes_match_evidence_for_result_quality(tmp_path):
    (tmp_path / "meta.md").write_text(
        "---\nid: meta-insights\ntitle: Meta Insights 报表诊断\n"
        "platform: meta\nstatus: published\ntags: [insights, report]\n---\n\n"
        "检查日期、字段、归因窗口和数据延迟。",
        encoding="utf-8",
    )
    provider = MarkdownWikiKnowledgeProvider(tmp_path)

    result = provider.query("Meta Insights 报表", limit=1)

    assert result[0].matched_terms
    assert "insights" in result[0].matched_terms
    assert 0 < result[0].match_coverage <= 1
    assert result[0].to_dict()["matched_terms"] == list(result[0].matched_terms)


def test_markdown_wiki_uses_sqlite_fts5_when_a_store_is_available(tmp_path):
    (tmp_path / "google.md").write_text(
        "---\nid: google-search\ntitle: Google Search 广告\ncategory: measurement\nsubcategory: conversion\nplatform: google\nstatus: published\n---\n\n"
        "## 搜索广告结构\n\nCampaign、Ad Group 和 Ad 的层级结构。",
        encoding="utf-8",
    )
    store = AdAgentStore(":memory:")
    provider = MarkdownWikiKnowledgeProvider(tmp_path, search_index=store)

    result = provider.query("Google Search 广告结构", limit=1)

    assert provider._fts_available is True
    assert result[0].retrieval_method == "sqlite_fts5_bm25"
    assert result[0].section == "搜索广告结构"
    assert result[0].citation["chunk_count"] == 1
    category_result = provider.query("measurement", limit=1)
    assert category_result[0].document_id == "google-search"


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


def test_managed_wiki_supports_draft_edit_versioned_edit_and_safe_delete():
    store = AdAgentStore(":memory:")
    manager = ManagedKnowledgeManager(store)
    try:
        created = manager.create_document(
            "tenant-a",
            {
                "title": "Google 搜索优化手册",
                "content": "# 初版\n\n先检查转化追踪。",
                "platform": "google-ads",
                "version": "1.0.0",
            },
            "user-a",
        )

        edited_draft = manager.update_document(
            "tenant-a",
            created["document_id"],
            {
                "title": "Google 搜索优化手册",
                "content": "# 草稿版\n\n先检查转化追踪，再检查搜索词。",
                "platform": "google-ads",
                "version": "1.0.0",
            },
            "user-a",
        )
        assert edited_draft["document_id"] == created["document_id"]
        assert edited_draft["content"].endswith("搜索词。")
        assert manager.update_document(
            "tenant-b", created["document_id"], edited_draft, "user-b"
        ) is None

        published = manager.publish("tenant-a", created["document_id"])
        versioned = manager.update_document(
            "tenant-a",
            created["document_id"],
            {
                "title": "Google 搜索优化手册",
                "content": "# 迭代版\n\n同时检查搜索词与落地页。",
                "platform": "google-ads",
                "version": "1.1.0",
            },
            "user-a",
        )
        assert published["status"] == "published"
        assert versioned["version_mode"] == "new_draft"
        assert versioned["document_id"] != published["document_id"]
        assert manager.get_document("tenant-a", published["document_id"])["content"].endswith("搜索词。")

        assert manager.delete_document("tenant-b", versioned["document_id"]) is None
        deleted_draft = manager.delete_document("tenant-a", versioned["document_id"])
        assert deleted_draft["hard_deleted"] is True
        assert store.get_knowledge_document(versioned["document_id"], tenant_id="tenant-a") is None

        archived = manager.delete_document("tenant-a", published["document_id"])
        assert archived["archived"] is True
        assert archived["hard_deleted"] is False
        assert manager.get_document("tenant-a", published["document_id"])["status"] == "deprecated"
    finally:
        store.close()


def test_managed_wiki_reuses_tenant_fts_index_for_unchanged_documents():
    store = AdAgentStore(":memory:")
    manager = ManagedKnowledgeManager(store)
    created = manager.create_document(
        "tenant-a",
        {"title": "缓存测试", "content": "# 缓存测试\n\n关键词检索正文。"},
        "user-a",
    )
    manager.publish("tenant-a", created["document_id"])
    provider = ManagedKnowledgeProvider(
        MarkdownWikiKnowledgeProvider("/path/that/does/not/exist"), store
    )
    calls = []
    original_rebuild = provider.base._rebuild_search_index

    def count_rebuild(chunks, *, scope):
        calls.append(scope)
        return original_rebuild(chunks, scope=scope)

    provider.base._rebuild_search_index = count_rebuild
    try:
        provider.query("缓存测试", tenant_id="tenant-a")
        provider.query("关键词检索", tenant_id="tenant-a")
        assert calls == ["tenant:tenant-a"]
    finally:
        store.close()


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


def test_memory_versions_are_deduplicated_and_superseded_by_logical_key():
    store = AdAgentStore(":memory:")
    manager = MemoryManager(store)
    first = manager.remember(
        "默认使用中文回答", tenant_id="tenant-a", user_id="user-a",
        memory_key="response.language",
    )
    duplicate = manager.remember(
        "默认使用中文回答", tenant_id="tenant-a", user_id="user-a",
        memory_key="response.language",
    )
    second = manager.remember(
        "默认使用英文回答", tenant_id="tenant-a", user_id="user-a",
        memory_key="response.language",
    )

    assert duplicate.memory_id == first.memory_id
    assert second.memory_id != first.memory_id
    old = store._get_conn().execute(
        "SELECT status, superseded_by FROM memories WHERE memory_id = ?", (first.memory_id,)
    ).fetchone()
    assert old["status"] == "superseded"
    assert old["superseded_by"] == second.memory_id
    assert [item.memory_id for item in manager.recall(
        "英文回答", tenant_id="tenant-a", user_id="user-a"
    )] == [second.memory_id]


def test_auto_memory_candidates_are_conservative():
    assert MemoryManager.extract_candidates("我的偏好是优先使用 Google Ads")
    assert MemoryManager.extract_candidates("以后请优先使用 dry-run")
    assert MemoryManager.extract_candidates("帮我查询今天的 Campaign") == []
    assert MemoryManager.extract_candidates("工具返回了一个 Campaign") == []


def test_session_window_and_digest_restore_after_restart():
    store = AdAgentStore(":memory:")
    runtime = AgentRuntime(require_llm=False, persistence_store=store, features=[])
    session = runtime._ensure_session("session-1", "user-1", None, {}, tenant_id="tenant-1")
    for index in range(12):
        runtime.persist_conversation_turn(
            session, f"turn-{index}", f"用户请求 {index}", f"助手回复 {index}"
        )
    persisted = store.get_session("session-1")
    metadata = __import__("json").loads(persisted["metadata"])
    assert len(metadata["messages"]) == 20
    assert "用户请求 0" in metadata["conversation_digest"]

    restarted = AgentRuntime(require_llm=False, persistence_store=store, features=[])
    restored = restarted._ensure_session("session-1", "user-1", None, {}, tenant_id="tenant-1")
    assert len(restored.messages) == 20
    assert restored.messages[0]["content"] == "用户请求 2"
    assert restored.messages[-1]["content"] == "助手回复 11"
    assert "用户请求 0" in restored.ctx.metadata["conversation_digest"]
    if restarted.task_executor:
        restarted.task_executor.shutdown(wait=True)
    if runtime.task_executor:
        runtime.task_executor.shutdown(wait=True)


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
        for call in llm.calls
        for message in call
    )
    assert result["tool_plan"] == {}


def test_intent_prompt_keeps_stable_prefix_when_context_changes():
    class FakeLLM:
        def __init__(self):
            self.calls = []

        def call(self, messages):
            self.calls.append(messages)
            return '{"intent_type":"list_campaigns","platforms":[]}'

    llm = FakeLLM()
    parser = LLMIntentParser(llm, allow_rule_fallback=False)
    parser._parse_with_llm(
        "你好",
        ToolContext("s1", "u1", metadata={"skill_context": {
            "tool_prompt": "tool-a", "memory_context": "偏好 A",
        }}),
    )
    parser._parse_with_llm(
        "谢谢",
        ToolContext("s1", "u1", metadata={"skill_context": {
            "tool_prompt": "tool-b", "memory_context": "偏好 B",
        }}),
    )

    assert llm.calls[0][0] == llm.calls[1][0]
    assert llm.calls[0][0]["role"] == "system"
    assert "你好" not in llm.calls[0][0]["content"]
    assert "谢谢" not in llm.calls[0][0]["content"]
    # Request-specific Tool/Memory context must not sit in the cacheable
    # Registry prefix. It remains available in the volatile tail.
    assert "tool-a" not in llm.calls[0][1]["content"]
    assert "tool-a" in "\n".join(message["content"] for message in llm.calls[0][2:])
    assert "偏好 A" in "\n".join(message["content"] for message in llm.calls[0][2:])
    assert llm.calls[0][-1]["role"] == "user"
    assert "你好" in llm.calls[0][-1]["content"]
    assert "谢谢" in llm.calls[1][-1]["content"]


def test_session_working_memory_has_character_budget_and_preserves_digest():
    store = AdAgentStore(":memory:")
    runtime = AgentRuntime(require_llm=False, persistence_store=store, features=[])
    session = runtime._ensure_session("budget-session", "user-1", None, {}, tenant_id="tenant-1")

    for index in range(10):
        runtime.persist_conversation_turn(
            session,
            f"turn-{index}",
            f"用户请求 {index} " + ("x" * 5000),
            f"助手回复 {index} " + ("y" * 5000),
        )

    assert sum(len(item["content"]) for item in session.messages) <= session.MAX_CONTEXT_CHARS
    assert all(len(item["content"]) <= session.MAX_MESSAGE_CHARS for item in session.messages)
    assert "用户请求 0" in session.ctx.metadata["conversation_digest"]
    runtime.close(wait=True)


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
