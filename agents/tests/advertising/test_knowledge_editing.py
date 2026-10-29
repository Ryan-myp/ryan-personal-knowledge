import pytest

from agents.applications.advertising.knowledge.knowledge_management import (
    ManagedKnowledgeManager, ManagedKnowledgeProvider,
)
from agents.applications.advertising.knowledge.wiki import MarkdownWikiKnowledgeProvider
from agents.applications.advertising.persistence.store import AdAgentStore


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / 'business').mkdir()
    (tmp_path / 'business' / 'guide.md').write_text(
        '---\nid: campaign-guide\ntitle: Campaign 指南\nplatform: meta\n'
        'layer: business\nknowledge_type: workflow\nstatus: published\n---\n'
        '# Campaign 指南\n\nCampaign 优化原始说明。\n', encoding='utf-8',
    )
    store = AdAgentStore(':memory:')
    provider = ManagedKnowledgeProvider(MarkdownWikiKnowledgeProvider(tmp_path), store)
    manager = ManagedKnowledgeManager(store)
    yield manager, provider, store
    store.close()


def override(manager, version='1.0.1', title='Campaign 指南'):
    return manager.create_document('a', {
        'title': title, 'content': 'Campaign 优化修改后的说明。', 'platform': 'meta',
        'derived_from': 'builtin:campaign-guide', 'version': version,
    }, 'u')


def test_all_builtin_documents_can_be_saved_as_edits_without_changing_their_metadata(workspace):
    from pathlib import Path

    manager, _, _ = workspace
    root = Path(__file__).resolve().parents[2] / 'knowledge/advertising/wiki'
    documents = MarkdownWikiKnowledgeProvider(root).documents
    assert documents
    for document in documents:
        saved = manager.create_document('a', {
            **document.to_dict(), 'title': document.title, 'content': document.excerpt,
            'derived_from': f'builtin:{document.document_id}',
        }, 'u')
        assert saved['knowledge_type'] == document.knowledge_type
        assert saved['content'] == document.excerpt.strip()
        assert saved['layer'] == document.layer
        assert saved['source_ref'] == document.source_ref


def test_builtin_edit_published_override_is_tenant_scoped_and_reversible(workspace):
    manager, provider, _ = workspace
    draft = override(manager)
    assert provider.catalog(tenant_id='a')[0].document_id == 'campaign-guide'
    provider.query('Campaign 优化', tenant_id='a')  # Prime the cache before publication.
    manager.publish('a', draft['document_id'])
    assert [row.document_id for row in provider.catalog(tenant_id='a')] == [f"managed:{draft['document_id']}"]
    results = provider.query('Campaign 优化', tenant_id='a')
    assert results and all(row.document_id != 'campaign-guide' for row in results)
    assert provider.catalog(tenant_id='b')[0].document_id == 'campaign-guide'
    assert provider.base.documents[0].excerpt.endswith('Campaign 优化原始说明。')
    manager.unpublish('a', draft['document_id'])
    assert provider.query('Campaign 优化', tenant_id='a')[0].document_id == 'campaign-guide'


def test_renamed_override_replaces_previous_revision_and_catalog_applies_limit_after_override(workspace):
    manager, provider, _ = workspace
    first = override(manager)
    manager.publish('a', first['document_id'])
    second = override(manager, '1.0.2', '重命名指南')
    manager.publish('a', second['document_id'])
    assert manager.get_document('a', first['document_id'])['status'] == 'draft'
    assert provider.catalog(tenant_id='a', limit=1)[0].document_id == f"managed:{second['document_id']}"


def test_published_edit_increments_version_and_preserves_hidden_metadata(workspace):
    manager, _, _ = workspace
    created = manager.create_document('a', {
        'title': '原文', 'content': '完整内容', 'platform': 'meta', 'version': '1.2.3',
        'source_ref': 'https://example.com/guide', 'layer': 'experience', 'confidence': 0.95,
        'derived_from': 'builtin:campaign-guide', 'wiki_type': 'concept', 'wikilinks': ['[[参考]]'],
    }, 'u')
    manager.publish('a', created['document_id'])
    updated = manager.update_document('a', created['document_id'], {
        'title': '原文', 'content': '修改内容', 'version': '1.2.3',
    }, 'u')
    assert updated['version'] == '1.2.4'
    for field in ('source_ref', 'layer', 'confidence', 'derived_from', 'wiki_type', 'wikilinks', 'platform'):
        assert updated[field] == created[field]
    assert manager.get_document('a', created['document_id'])['content'] == '完整内容'
    manager.publish('a', updated['document_id'])
    old_edit = manager.update_document('a', created['document_id'], {'title': '原文', 'content': '从旧版再修改'}, 'u')
    assert old_edit['document_id'] not in {created['document_id'], updated['document_id']}
    assert old_edit['version'] == '1.2.5'


def test_foreign_or_archived_publish_does_not_unpublish_existing_release(workspace):
    manager, _, _ = workspace
    own = manager.create_document('a', {'title': '相同标题', 'content': '本租户内容'}, 'u')
    foreign = manager.create_document('b', {'title': '相同标题', 'content': '其他内容'}, 'v')
    manager.publish('a', own['document_id'])
    assert manager.publish('a', foreign['document_id']) is None
    assert manager.get_document('a', own['document_id'])['status'] == 'published'
    old = manager.create_document('a', {'title': '相同标题', 'content': '旧版内容', 'version': '0.1.0'}, 'u')
    manager.publish('a', old['document_id'])
    manager.delete_document('a', old['document_id'])
    manager.publish('a', own['document_id'])
    assert manager.publish('a', old['document_id']) is None
    assert manager.get_document('a', own['document_id'])['status'] == 'published'


def test_http_builtin_editor_reads_full_document_and_put_preserves_unset_metadata(workspace):
    from types import SimpleNamespace
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient
    from agents.deployments.advertising.api.context import ApiContext
    from agents.deployments.advertising.api.routes.knowledge import create_knowledge_router
    from agents.agent_platform.governance.identity.principal import RequestPrincipal

    manager, provider, store = workspace
    principal = RequestPrincipal(user_id='u', tenant_id='a', permissions=frozenset({'knowledge.read','knowledge.write'}))
    def permission(user, name):
        if name not in user.permissions:
            raise HTTPException(status_code=403, detail='forbidden')
    context = ApiContext(runtime_getter=lambda: SimpleNamespace(knowledge_provider=provider),
        persistence_store_getter=lambda: store, authorize_request=lambda *_: principal,
        require_permission=permission, activate_tenant_skills=lambda *_: None,
        sync_tenant_extensions=lambda *_: None, safe_exception_text=str, redact=lambda value: value)
    app = FastAPI()
    app.include_router(create_knowledge_router(context))
    with TestClient(app) as client:
        response = client.get('/knowledge/builtin/campaign-guide')
        assert response.status_code == 200
        assert response.json()['content'] == provider.base.documents[0].excerpt
        assert client.get('/knowledge/builtin/missing').status_code == 404
        draft = override(manager)
        changed = client.put('/knowledge/documents/'+draft['document_id'], json={'title':'新标题','content':'新内容'})
        assert changed.status_code == 200
        assert changed.json()['derived_from'] == 'builtin:campaign-guide'
        assert changed.json()['platform'] == 'meta'
        principal = RequestPrincipal(user_id='u', tenant_id='a', permissions=frozenset())
        assert client.get('/knowledge/builtin/campaign-guide').status_code == 403
        assert client.put('/knowledge/documents/'+draft['document_id'], json={'title':'拒绝','content':'拒绝'}).status_code == 403
