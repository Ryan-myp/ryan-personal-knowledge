import hashlib

import pytest

from agents.ad_agent.knowledge_ingest import (
    KnowledgeIngestError,
    KnowledgeIngestService,
    RawKnowledgeManager,
)
from agents.ad_agent.knowledge_management import ManagedKnowledgeManager
from agents.ad_agent.domain.ad.auth import RequestPrincipal
from agents.ad_agent.persistence.store import AdAgentStore
from agents.ad_agent.persistence.models import TaskRecord
from agents.ad_agent.runtime.ad_task_services import AdTaskServices


class FakeLLM:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def call_json(self, messages, temperature=0.1):
        self.calls.append(messages)
        if self.error:
            raise self.error
        return self.response


@pytest.fixture
def store():
    value = AdAgentStore(":memory:")
    try:
        yield value
    finally:
        value.close()


def test_raw_source_is_immutable_and_deduplicated_by_tenant_hash(store):
    manager = RawKnowledgeManager(store)
    content = "# Meta 素材经验\n\n优先测试首屏素材。"

    first = manager.create_source(
        tenant_id="tenant-a",
        filename="meta.md",
        content=content,
        created_by="user-a",
        source_ref="upload://first",
    )
    duplicate = manager.create_source(
        tenant_id="tenant-a",
        filename="renamed.md",
        content=content,
        created_by="user-a",
        source_ref="upload://second",
    )
    other_tenant = manager.create_source(
        tenant_id="tenant-b",
        filename="meta.md",
        content=content,
        created_by="user-b",
    )

    assert first["source_id"] == duplicate["source_id"]
    assert duplicate["duplicate"] is True
    assert first["sha256"] == hashlib.sha256(content.encode()).hexdigest()
    assert other_tenant["source_id"] != first["source_id"]
    assert store.get_raw_knowledge_source(first["source_id"], tenant_id="tenant-a").content == content
    with pytest.raises(KnowledgeIngestError):
        manager.update_source(first["source_id"], tenant_id="tenant-a", content="tampered")


def test_ingest_creates_drafts_with_source_lineage_and_keeps_raw_out_of_runtime(store):
    raw = RawKnowledgeManager(store).create_source(
        tenant_id="tenant-a",
        filename="meta.md",
        content="Meta 的素材经验和测试方法。",
        created_by="user-a",
    )
    llm = FakeLLM({
        "summary": "从原始文档提炼出的摘要",
        "contradictions": [],
        "pages_to_create": [{
            "title": "Meta 素材测试",
            "wiki_type": "concept",
            "platform": "meta",
            "layer": "business",
            "knowledge_type": "best_practice",
            "content": "# Meta 素材测试\n\n优先测试首屏素材。",
            "version": "1.0.0",
            "confidence": 0.86,
            "tags": ["素材", "测试"],
            "wikilinks": ["[[Meta Ads]]"],
        }],
        "pages_to_update": [],
    })

    result = KnowledgeIngestService(
        store=store,
        llm=llm,
        knowledge_manager=ManagedKnowledgeManager(store),
    ).ingest(raw["source_id"], tenant_id="tenant-a", created_by="user-a")

    assert result["status"] == "draft_ready"
    assert result["created_document_ids"]
    source = store.get_raw_knowledge_source(raw["source_id"], tenant_id="tenant-a")
    assert source.status == "draft_ready"
    assert source.sha256 == raw["sha256"]
    draft = store.get_knowledge_document(
        result["created_document_ids"][0], tenant_id="tenant-a"
    )
    assert draft.status == "draft"
    assert draft.source_ref == f"raw://{raw['source_id']}"
    assert draft.derived_from == raw["source_id"]
    assert draft.raw_sha256 == raw["sha256"]
    assert draft.wikilinks == ["[[Meta Ads]]"]
    assert all("raw" not in message[0]["content"].lower() for message in llm.calls)


def test_ingest_rejects_untrusted_paths_and_marks_source_failed(store):
    raw = RawKnowledgeManager(store).create_source(
        tenant_id="tenant-a",
        filename="source.md",
        content="可靠内容",
        created_by="user-a",
    )
    llm = FakeLLM({
        "pages_to_create": [{
            "title": "恶意页面",
            "path": "../../outside.md",
            "content": "不能写入任意路径",
        }],
        "pages_to_update": [],
    })

    with pytest.raises(KnowledgeIngestError):
        KnowledgeIngestService(
            store=store,
            llm=llm,
            knowledge_manager=ManagedKnowledgeManager(store),
        ).ingest(raw["source_id"], tenant_id="tenant-a", created_by="user-a")

    source = store.get_raw_knowledge_source(raw["source_id"], tenant_id="tenant-a")
    assert source.status == "failed"
    assert source.ingest_error
    assert store.list_knowledge_documents("tenant-a", limit=20) == []


def test_ingest_llm_failure_does_not_publish_or_create_partial_pages(store):
    raw = RawKnowledgeManager(store).create_source(
        tenant_id="tenant-a",
        filename="source.md",
        content="可靠内容",
        created_by="user-a",
    )
    llm = FakeLLM(error=TimeoutError("model timeout"))

    with pytest.raises(KnowledgeIngestError):
        KnowledgeIngestService(
            store=store,
            llm=llm,
            knowledge_manager=ManagedKnowledgeManager(store),
        ).ingest(raw["source_id"], tenant_id="tenant-a", created_by="user-a")

    source = store.get_raw_knowledge_source(raw["source_id"], tenant_id="tenant-a")
    assert source.status == "failed"
    assert store.list_knowledge_documents("tenant-a", limit=20) == []


def test_raw_source_claim_is_atomic_and_failed_sources_can_retry(store):
    raw = RawKnowledgeManager(store).create_source(
        tenant_id="tenant-a",
        filename="retry.md",
        content="可重试内容",
        created_by="user-a",
    )

    first = store.claim_raw_knowledge_source(
        raw["source_id"],
        tenant_id="tenant-a",
        task_id="task-1",
        started_at="2026-09-20T10:00:00+00:00",
    )
    assert first is not None
    assert first.status == "ingesting"
    assert first.ingest_attempts == 1
    assert first.ingest_task_id == "task-1"

    assert store.claim_raw_knowledge_source(
        raw["source_id"],
        tenant_id="tenant-a",
        task_id="task-2",
        started_at="2026-09-20T10:01:00+00:00",
    ) is None

    failed = store.update_raw_knowledge_source(
        raw["source_id"],
        tenant_id="tenant-a",
        data={
            "status": "failed",
            "updated_at": "2026-09-20T10:02:00+00:00",
            "ingest_finished_at": "2026-09-20T10:02:00+00:00",
            "ingest_error": "TimeoutError: ingestion failed",
        },
    )
    assert failed is not None
    retried = store.claim_raw_knowledge_source(
        raw["source_id"],
        tenant_id="tenant-a",
        task_id="task-3",
        started_at="2026-09-20T10:03:00+00:00",
    )
    assert retried is not None
    assert retried.ingest_attempts == 2
    assert retried.ingest_task_id == "task-3"


def test_completed_raw_source_is_not_ingested_twice(store):
    raw = RawKnowledgeManager(store).create_source(
        tenant_id="tenant-a",
        filename="completed.md",
        content="已完成内容",
        created_by="user-a",
    )
    store.update_raw_knowledge_source(
        raw["source_id"],
        tenant_id="tenant-a",
        data={"status": "draft_ready", "updated_at": "2026-09-20T10:00:00+00:00"},
    )
    with pytest.raises(KnowledgeIngestError, match="已完成 ingest"):
        KnowledgeIngestService(
            store=store,
            llm=FakeLLM({"pages_to_create": [], "pages_to_update": []}),
            knowledge_manager=ManagedKnowledgeManager(store),
        ).ingest(raw["source_id"], tenant_id="tenant-a", created_by="user-a")


def test_stale_raw_source_claim_can_be_recovered_for_retry(store):
    raw = RawKnowledgeManager(store).create_source(
        tenant_id="tenant-a",
        filename="stale.md",
        content="worker 可能中断的内容",
        created_by="user-a",
    )
    claimed = store.claim_raw_knowledge_source(
        raw["source_id"],
        tenant_id="tenant-a",
        task_id="dead-task",
        started_at="2026-09-20T10:00:00+00:00",
    )
    assert claimed is not None

    recovered = store.recover_stale_raw_knowledge_sources(
        tenant_id="tenant-a",
        stale_after_seconds=60,
        recovered_at="2026-09-20T10:10:00+00:00",
    )
    assert recovered == 1
    source = store.get_raw_knowledge_source(raw["source_id"], tenant_id="tenant-a")
    assert source.status == "failed"
    assert source.ingest_finished_at == "2026-09-20T10:10:00+00:00"
    assert source.ingest_error == "worker lease expired; retry required"


def test_ingest_failure_restores_existing_draft_instead_of_deleting_it(store):
    manager = ManagedKnowledgeManager(store)
    existing = manager.create_document(
        "tenant-a",
        {
            "title": "Existing draft",
            "content": "原始 draft 内容",
            "platform": "meta",
            "layer": "business",
            "knowledge_type": "best_practice",
            "version": "1.0.0",
        },
        "user-a",
    )
    second_existing = manager.create_document(
        "tenant-a",
        {
            "title": "Second draft",
            "content": "第二张原始 draft 内容",
            "platform": "meta",
            "layer": "business",
            "knowledge_type": "best_practice",
            "version": "1.0.0",
        },
        "user-a",
    )
    raw = RawKnowledgeManager(store).create_source(
        tenant_id="tenant-a",
        filename="rollback.md",
        content="会触发部分失败的内容",
        created_by="user-a",
    )
    llm = FakeLLM({
        "summary": "partial failure",
        "contradictions": [],
        "pages_to_create": [],
        "pages_to_update": [
            {
                "document_id": existing["document_id"],
                "title": "Existing draft",
                "content": "不应留下的更新",
            },
            {
                "document_id": second_existing["document_id"],
                "title": "Existing draft",
                "content": "同标题同版本应失败",
            },
        ],
    })

    with pytest.raises(KnowledgeIngestError):
        KnowledgeIngestService(
            store=store,
            llm=llm,
            knowledge_manager=manager,
        ).ingest(raw["source_id"], tenant_id="tenant-a", created_by="user-a")

    restored = store.get_knowledge_document(
        existing["document_id"], tenant_id="tenant-a"
    )
    assert restored is not None
    assert restored.status == "draft"
    assert restored.content == "原始 draft 内容"
    assert restored.platform == "meta"
    restored_second = store.get_knowledge_document(
        second_existing["document_id"], tenant_id="tenant-a"
    )
    assert restored_second is not None
    assert restored_second.content == "第二张原始 draft 内容"
    assert len(store.list_knowledge_documents("tenant-a", status="draft", limit=20)) == 2


def test_ingest_update_preserves_metadata_and_versions_published_document(store):
    manager = ManagedKnowledgeManager(store)
    published = manager.create_document(
        "tenant-a",
        {
            "title": "Published guide",
            "content": "旧版本",
            "platform": "google-ads",
            "layer": "platform",
            "knowledge_type": "workflow",
            "version": "2.4.0",
            "tags": ["stable"],
        },
        "user-a",
    )
    manager.publish("tenant-a", published["document_id"])
    raw = RawKnowledgeManager(store).create_source(
        tenant_id="tenant-a",
        filename="version.md",
        content="更新已发布知识页",
        created_by="user-a",
    )
    llm = FakeLLM({
        "summary": "versioned update",
        "contradictions": [],
        "pages_to_create": [],
        "pages_to_update": [{
            "document_id": published["document_id"],
            "title": "Published guide",
            "content": "新版本",
        }],
    })

    result = KnowledgeIngestService(
        store=store,
        llm=llm,
        knowledge_manager=manager,
    ).ingest(raw["source_id"], tenant_id="tenant-a", created_by="user-a")

    assert result["updated_document_ids"]
    updated = store.get_knowledge_document(
        result["updated_document_ids"][0], tenant_id="tenant-a"
    )
    assert updated is not None
    assert updated.status == "draft"
    assert updated.version == "2.4.1"
    assert updated.platform == "google-ads"
    assert updated.layer == "platform"
    assert updated.knowledge_type == "workflow"
    assert updated.tags == ["stable"]
    assert store.get_knowledge_document(
        published["document_id"], tenant_id="tenant-a"
    ).status == "published"


def test_terminal_knowledge_ingest_task_can_be_requeued(store):
    source = RawKnowledgeManager(store).create_source(
        tenant_id="tenant-a",
        filename="retry-task.md",
        content="需要任务重试的内容",
        created_by="user-a",
    )

    class FakeTaskExecutor:
        def __init__(self):
            self.calls = []
            self.counter = 0

        def submit(self, kind, payload, **kwargs):
            self.calls.append((kind, payload, kwargs))
            self.counter += 1
            return TaskRecord(
                task_id=f"task-{self.counter}",
                tenant_id=kwargs["tenant_id"],
                user_id=kwargs["user_id"],
                kind=kind,
                status="queued",
                payload=payload,
                idempotency_key=kwargs["idempotency_key"],
            ), True

    executor = FakeTaskExecutor()
    first_task = TaskRecord(
        task_id="task-old",
        tenant_id="tenant-a",
        user_id="user-a",
        kind="knowledge.ingest",
        status="failed",
        payload={"source_id": source["source_id"]},
        idempotency_key="old-key",
    )
    store.update_raw_knowledge_source(
        source["source_id"],
        tenant_id="tenant-a",
        data={
            "ingest_task_id": first_task.task_id,
            "updated_at": "2026-09-20T10:00:00+00:00",
        },
    )
    original_get_task = store.get_task
    store.get_task = lambda task_id, tenant_id=None, user_id=None: (
        first_task if str(task_id) == first_task.task_id else original_get_task(
            task_id, tenant_id=tenant_id, user_id=user_id
        )
    )
    runtime = type(
        "Runtime",
        (),
        {"persistence_store": store, "task_executor": executor},
    )()
    services = AdTaskServices(runtime)
    principal = RequestPrincipal(
        user_id="user-a",
        tenant_id="tenant-a",
        permissions=frozenset({"knowledge.write"}),
    )

    first, first_created = services.submit_knowledge_ingest(
        source["source_id"], principal=principal
    )

    assert first_created is True
    assert first["task_id"] != first_task.task_id
    assert len(executor.calls) == 1
    assert executor.calls[0][2]["idempotency_key"] != first_task.idempotency_key
