"""Offline management pagination; all persistence is in memory."""

from types import SimpleNamespace
from dataclasses import replace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from agents.agent_platform.governance.identity.principal import RequestPrincipal
from agents.applications.advertising.knowledge.knowledge_management import (
    KnowledgeCatalogQuery, ManagedKnowledgeManager,
)
from agents.applications.advertising.knowledge.wiki import KnowledgeDocument
from agents.applications.advertising.persistence.models import KnowledgeDocumentRecord
from agents.applications.advertising.persistence.store import AdAgentStore
from agents.deployments.advertising.api.context import ApiContext
from agents.deployments.advertising.api.routes.knowledge import create_knowledge_router


@pytest.fixture
def store():
    backend = AdAgentStore(':memory:')
    for index in range(125):
        backend.create_knowledge_document(KnowledgeDocumentRecord(
            document_id=f'doc-{index:03}', tenant_id='a', title=f'文档 {index}',
            content='只有正文含有的 Needle 100%_\\' if index == 124 else '普通正文',
            platform='meta', knowledge_type='workflow' if index == 124 else 'general',
            tags=['旧标签'] if index == 124 else [],
            updated_at='2020-01-01' if index == 124 else '2026-01-01',
            source_ref='https://example.com/reference', derived_from='builtin:guide',
            wikilinks=['[[参考]]'],
        ))
    backend.create_knowledge_document(KnowledgeDocumentRecord(
        document_id='foreign', tenant_id='b', title='Needle 租户隔离',
        content='秘密正文', knowledge_type='constraint',
    ))
    yield backend
    backend.close()


@pytest.fixture
def client(store):
    # Exercise the domain repository independently of the separately-owned facade.
    repository = store._knowledge
    builtin = KnowledgeDocument(
        document_id='guide', platform='meta', topic='内置', title='内置',
        excerpt='内置完整正文 Needle', source='official', version='1.0.0',
        confidence=1.0, updated_at='2026-01-01', category='operations',
    )
    identity = SimpleNamespace(principal=RequestPrincipal(user_id='u', tenant_id='a', permissions=frozenset({'ads.read', 'knowledge.read'})))

    def permission(user, name):
        if name not in user.permissions:
            raise HTTPException(403, 'forbidden')

    context = ApiContext(
        runtime_getter=lambda: SimpleNamespace(knowledge_provider=SimpleNamespace(documents=[builtin])),
        persistence_store_getter=lambda: repository, authorize_request=lambda *_: identity.principal,
        require_permission=permission, activate_tenant_skills=lambda *_: None,
        sync_tenant_extensions=lambda *_: None, safe_exception_text=str, redact=lambda value: value,
    )
    app = FastAPI()
    app.include_router(create_knowledge_router(context))
    with TestClient(app) as http:
        yield http, identity


def test_repository_pages_past_100_stably_without_leaking_body_or_tenants(store):
    repository = store._knowledge
    first = repository.page_knowledge_documents('a', limit=100)
    last = repository.page_knowledge_documents('a', limit=100, offset=100)
    assert first['total'] == last['total'] == 125
    assert [row.document_id for row in first['documents']] == [f'doc-{i:03}' for i in range(100)]
    assert [row.document_id for row in last['documents']] == [f'doc-{i:03}' for i in range(100, 125)]
    assert all(not row.content for row in first['documents'] + last['documents'])
    assert 'constraint' not in first['categories']
    assert repository.page_knowledge_documents('b')['total'] == 1
    assert repository.page_knowledge_documents('empty')['total'] == 0


@pytest.mark.parametrize('query', ['Needle', 'needle', '旧标签', '100%_\\', '文档 124'])
def test_search_and_intersecting_filters_find_old_draft_before_limit(client, query):
    http, _ = client
    response = http.get('/knowledge/documents', params={
        'q': query, 'platform': 'meta', 'category': 'workflow', 'status': 'draft', 'limit': 10,
        'tenant_id': 'b',
    })
    assert response.status_code == 200
    page = response.json()
    assert page['total'] == 1
    assert [item['document_id'] for item in page['documents']] == ['doc-124']
    assert page['has_more'] is False
    assert page['offset'] == 0 and page['limit'] == 10
    assert not {'content', 'markdown', 'excerpt'} & page['documents'][0].keys()
    detail = http.get('/knowledge/documents/doc-124').json()
    assert 'Needle' in detail['content'] and detail['markdown']
    for field in ('source_ref', 'derived_from', 'wikilinks', 'knowledge_type'):
        assert page['documents'][0][field] == detail[field]
    assert http.get('/knowledge/documents/foreign').status_code == 404


def test_mixed_sources_total_boundaries_and_full_detail(client):
    http, _ = client
    first = http.get('/knowledge/documents', params={'source': 'all', 'limit': 10}).json()
    last = http.get('/knowledge/documents', params={'source': 'all', 'limit': 10, 'offset': 120}).json()
    beyond = http.get('/knowledge/documents', params={'source': 'all', 'offset': 999}).json()
    assert first['total'] == last['total'] == beyond['total'] == 126
    assert first['has_more'] is True and last['has_more'] is False
    assert len(first['documents']) == 10 and len(last['documents']) == 6
    assert first['documents'][0]['catalog_source'] == 'builtin'
    assert first['documents'][1]['catalog_source'] == 'managed'
    assert not {'content', 'markdown', 'excerpt'} & first['documents'][0].keys()
    assert beyond['documents'] == [] and beyond['has_more'] is False
    assert set(first['categories']) == {'operations', 'general', 'workflow'}
    assert http.get('/knowledge/builtin/guide').json()['content'] == '内置完整正文 Needle'
    assert http.get('/knowledge/documents', params={'source': 'builtin'}).json()['total'] == 1
    assert http.get('/knowledge/documents', params={'source': 'all', 'status': 'draft'}).json()['total'] == 125
    assert http.get('/knowledge/documents', params={'source': 'all', 'category': 'operations'}).json()['total'] == 1
    assert http.get('/knowledge/documents').json()['total'] == 125


@pytest.mark.parametrize('params', [
    {'offset': -1}, {'limit': 0}, {'limit': 201}, {'source': 'user'},
    {'status': 'bad'}, {'q': 'x' * 2001},
])
def test_invalid_pagination_is_rejected(client, params):
    http, _ = client
    assert http.get('/knowledge/documents', params=params).status_code == 422


def test_literal_search_and_empty_intersection(client):
    http, _ = client
    for params in ({'q': "' OR 1=1 --"}, {'platform': 'tiktok'}, {'status': 'published'}, {'category': 'missing'}):
        page = http.get('/knowledge/documents', params=params).json()
        assert page['total'] == 0 and page['documents'] == [] and page['has_more'] is False


def test_permission_checked_before_repository_access(client):
    http, identity = client
    identity.principal = RequestPrincipal(user_id='u', tenant_id='a', permissions=frozenset())
    assert http.get('/knowledge/documents').status_code == 403


def test_facade_exposes_management_page_port(store):
    # This forwarding method is intentionally supplied by the owner of store.py.
    assert callable(getattr(store, 'page_knowledge_documents', None))
    page = ManagedKnowledgeManager(store).page_documents('a', query=KnowledgeCatalogQuery(offset=120))
    assert page['total'] == 125


def test_page_crossing_builtin_managed_boundary_has_no_gaps_or_duplicates(store):
    builtin = KnowledgeDocument(
        document_id='base', platform='all', topic='内置', excerpt='正文', source='official',
        version='1.0.0', confidence=1.0, updated_at='2026-01-01',
    )
    documents = [replace(builtin, document_id=f'builtin-{i:02}') for i in reversed(range(23))]
    manager = ManagedKnowledgeManager(store._knowledge)
    pages = [manager.page_documents('a', builtin_documents=documents,
                                   query=KnowledgeCatalogQuery(source='all', limit=10, offset=offset))
             for offset in (0, 10, 20, 30)]
    ids = [row['document_id'] for page in pages for row in page['documents']]
    assert ids == [f'builtin-{i:02}' for i in range(23)] + [f'doc-{i:03}' for i in range(17)]
    assert all(page['total'] == 148 and page['has_more'] for page in pages)


def test_builtin_only_does_not_query_tenant_documents(store, monkeypatch):
    def unexpected_query(*args, **kwargs):
        raise AssertionError('builtin pages must not load tenant documents')
    monkeypatch.setattr(store._knowledge, 'page_knowledge_documents', unexpected_query)
    page = ManagedKnowledgeManager(store._knowledge).page_documents(
        'a', query=KnowledgeCatalogQuery(source='builtin'),
    )
    assert page['total'] == 0 and page['documents'] == [] and page['has_more'] is False


def test_published_archived_and_draft_versions_are_separately_filterable(client, store):
    http, _ = client
    for status in ('published', 'deprecated'):
        store.create_knowledge_document(KnowledgeDocumentRecord(
            document_id=status, tenant_id='a', title='旧版本', content='全文', status=status,
            version='1.0.0' if status == 'published' else '0.1.0',
        ))
        page = http.get('/knowledge/documents', params={'status': status}).json()
        assert page['total'] == 1
        assert page['documents'][0]['document_id'] == status
        assert not {'content', 'excerpt', 'markdown'} & page['documents'][0].keys()
