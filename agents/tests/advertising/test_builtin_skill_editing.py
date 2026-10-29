from pathlib import Path

from agents.agent_platform.management.skill_management import BuiltinSkillCatalog, ManagedSkillManager
from agents.applications.advertising.composition.ad_application import AdvertisingComposition
from agents.applications.advertising.persistence.store import AdAgentStore


def test_builtin_revision_publishes_as_tenant_guidance_and_unpublishes_without_changing_tools(tmp_path):
    root = Path(__file__).resolve().parents[2] / 'skills/advertising'
    builtin = BuiltinSkillCatalog(root).get_version('account-diagnostics', '1.5.0')
    store = AdAgentStore(':memory:')
    runtime = AdvertisingComposition(persistence_store=store, require_llm=False,
                                     offline_mode=True, start_background_workers=False)
    manager = ManagedSkillManager(store, root=str(tmp_path / 'managed'))
    try:
        runtime.auto_load_skills(str(root), allow_executable_plugins=True, allow_provider_tool_discovery=True)
        tools_before = [tool.name for tool in runtime.registry.list_all()]
        files = dict(builtin['files'])
        import base64
        original = base64.b64decode(files['SKILL.md']['content']).decode()
        files['SKILL.md'] = original + '\n\n修订验证标记：报告先核对统计口径。\n'
        manager.create_version('tenant-a', 'account-diagnostics', '1.5.1', files, 'u')
        published = manager.publish('tenant-a', 'account-diagnostics', '1.5.1', runtime=runtime)
        assert published['status'] == 'published'
        loaded = runtime.get_managed_skills('tenant-a')['account-diagnostics']
        assert '修订验证标记' in loaded.raw_markdown
        assert not runtime.get_managed_skills('tenant-b')
        assert [tool.name for tool in runtime.registry.list_all()] == tools_before
        assert BuiltinSkillCatalog(root).get_version('account-diagnostics', '1.5.0')['sha256'] == builtin['sha256']
        manager.unpublish('tenant-a', 'account-diagnostics', '1.5.1', runtime=runtime)
        assert not runtime.get_managed_skills('tenant-a')
        assert [tool.name for tool in runtime.registry.list_all()] == tools_before
    finally:
        runtime.close(wait=True)
