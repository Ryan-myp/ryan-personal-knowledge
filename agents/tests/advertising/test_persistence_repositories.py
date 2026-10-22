import ast
from pathlib import Path

import pytest

from agents.applications.advertising.persistence import (
    knowledge_store, memory_store, session_store, extension_store, workflow_store,
)
from agents.applications.advertising.persistence.store import AdAgentStore
from agents.applications.advertising.persistence import store as store_module
from agents.applications.advertising.persistence.schema import DATABASE_SCHEMA, SCHEMA_VERSION
from agents.applications.advertising.persistence.sqlite_migrations import (
    MIGRATIONS, apply_sqlite_migration,
)


@pytest.mark.parametrize("module,repository,method,kwargs", [
    (knowledge_store, "KnowledgeRepository", "list_knowledge_documents", {"tenant_id": "tenant"}),
    (memory_store, "MemoryRepository", "search_memories", {
        "query": "budget", "tenant_id": "tenant", "user_id": "user",
    }),
    (session_store, "SessionRepository", "get_session", {"session_id": "session"}),
    (extension_store, "ExtensionRepository", "list_skill_versions", {"tenant_id": "tenant"}),
    (workflow_store, "WorkflowRepository", "list_workflow_items", {"workflow_id": "workflow"}),
])
def test_facade_routes_each_domain_through_its_repository(
    monkeypatch, module, repository, method, kwargs,
):
    called = []
    sentinel = object()

    def operation(self, *args, **options):
        called.append((self, args, options))
        return sentinel

    monkeypatch.setattr(getattr(module, repository), method, operation)
    store = AdAgentStore(":memory:")
    try:
        assert getattr(store, method)(**kwargs) is sentinel
        assert len(called) == 1
        assert called[0][0]._get_conn() is store._get_conn()
        assert called[0][0]._lock is store._lock
    finally:
        store.close()


def test_schema_and_versioned_migrations_have_one_owner():
    assert AdAgentStore.SCHEMA == DATABASE_SCHEMA
    assert AdAgentStore.SCHEMA_VERSION == SCHEMA_VERSION
    assert set(MIGRATIONS) == set(range(1, SCHEMA_VERSION + 1))
    for version in (0, True, SCHEMA_VERSION + 1):
        with pytest.raises(ValueError):
            apply_sqlite_migration(None, version)


def test_domain_facade_methods_do_not_retain_inline_sql():
    tree = ast.parse(Path(store_module.__file__).read_text())
    owner = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    names = {"search_memories", "create_session", "list_skill_versions",
             "create_knowledge_document", "list_workflow_items"}
    for method in owner.body:
        if not isinstance(method, ast.FunctionDef) or method.name not in names:
            continue
        assert not any(
            isinstance(node, ast.Attribute) and node.attr in {"execute", "executemany"}
            for node in ast.walk(method)
        ), method.name
