from types import SimpleNamespace

from agents.agent_harness import AgentApplication, ModelTurn, SkillBinding, StaticSkillSource
from agents.applications.advertising.integrations.managed_skill_catalog import AdvertisingSkillCatalog


def managed(name, text, version='1.0.1'):
    return SimpleNamespace(name=name, version=version, description='report',
                           raw_markdown=text, reference_documents={})


def catalog_fixture(**options):
    tenants = {}
    owner = SimpleNamespace(get_managed_skills=lambda tenant: dict(tenants.get(tenant, {})))
    catalog = AdvertisingSkillCatalog(owner, max_context_chars=900, max_skills=4, **options)
    catalog.register_source(StaticSkillSource('builtin', [
        SkillBinding(name='report', instructions='ORIGINAL SOP', description='report'),
        SkillBinding(name='guard', instructions='SHARED GUARD', metadata={'always_on': True}),
    ]))
    return catalog, tenants


def context(catalog, tenant='a', sources=None):
    request = SimpleNamespace(user_input='report cohorts', tenant_id=tenant)
    return catalog.build_request_context(request, [SimpleNamespace(skill_refs=['report'])], source_ids=sources)


def test_modified_skill_replaces_builtin_for_only_its_tenant_and_unpublish_restores_it():
    catalog, tenants = catalog_fixture()
    tenants['a'] = {'report': managed('report', 'REVISED SOP')}
    result = context(catalog)
    assert 'REVISED SOP' in result and 'ORIGINAL SOP' not in result
    assert 'SHARED GUARD' in result and len(result) <= 900
    assert 'ORIGINAL SOP' in context(catalog, 'b')
    assert 'REVISED SOP' not in context(catalog, 'b')
    tenants['a'].clear()
    assert 'ORIGINAL SOP' in context(catalog)


def test_published_skill_context_cache_refreshes_when_revision_or_builtin_sources_change():
    catalog, tenants = catalog_fixture()
    tenants['a'] = {'report': managed('report', 'FIRST SOP')}
    assert 'FIRST SOP' in context(catalog)
    first = catalog._tenant_catalogs['a'][-1]
    assert 'FIRST SOP' in context(catalog)
    assert catalog._tenant_catalogs['a'][-1] is first
    tenants['a']['report'] = managed('report', 'SECOND SOP', '1.0.2')
    assert 'SECOND SOP' in context(catalog) and 'FIRST SOP' not in context(catalog)
    catalog.register_source(StaticSkillSource('extra', [
        SkillBinding(name='extra', instructions='EXTRA GUARD', metadata={'always_on': True}),
    ]))
    assert 'EXTRA GUARD' in context(catalog)


def test_tenant_catalog_cache_is_bounded_and_respects_source_restrictions():
    catalog, tenants = catalog_fixture(max_tenant_catalogs=2)
    for tenant in ('a', 'b', 'c'):
        tenants[tenant] = {'report': managed('report', tenant + ' SOP')}
        context(catalog, tenant)
    assert list(catalog._tenant_catalogs) == ['b', 'c']
    tenants['c']['custom-report'] = managed('custom-report', 'CUSTOM REPORT SOP')
    assert 'CUSTOM REPORT SOP' in context(catalog, 'c', sources=['builtin'])
    assert context(catalog, 'c', sources=[]) == ''
    assert context(catalog, 'c', sources=['missing']) == ''


def test_advisory_revisions_share_one_budget_and_preserve_relevant_references():
    catalog, tenants = catalog_fixture()
    tenants['a'] = {
        'report': managed('report', 'REVISED SOP ' * 1000),
        'z-report': managed('z-report', 'SECOND GUIDANCE'),
    }
    tenants['a']['report'].reference_documents = {'references/cohorts.md': 'COHORTS REFERENCE'}
    result = context(catalog)
    assert 'COHORTS REFERENCE' in result
    assert 'SECOND GUIDANCE' in result
    assert 'SHARED GUARD' in result
    assert len(result) <= 900


def test_harness_uses_request_aware_catalog_without_mutating_shared_skill_sources():
    catalog, tenants = catalog_fixture()
    tenants['a'] = {'report': managed('report', 'REVISED SOP')}
    captured = []
    def complete(messages, _tools, request):
        captured.append((request.tenant_id, '\n'.join(str(m.content) for m in messages)))
        return ModelTurn(content='ok')
    app = AgentApplication.create(model=complete, skill_catalog=catalog)
    try:
        assert app.prompt('report', tenant_id='a').status.value == 'succeeded'
        assert app.prompt('report', tenant_id='b').status.value == 'succeeded'
    finally:
        app.close()
    assert 'REVISED SOP' in captured[0][1] and 'ORIGINAL SOP' not in captured[0][1]
    assert 'ORIGINAL SOP' in captured[1][1] and 'REVISED SOP' not in captured[1][1]
    assert catalog.list_skills()[0].instructions == 'ORIGINAL SOP'
