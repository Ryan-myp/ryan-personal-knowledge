"""Resolve published tenant guidance through the same bounded Skill selector."""

from collections import OrderedDict
from typing import Any

from agents.agent_harness.skills import InMemorySkillCatalog, SkillBinding, StaticSkillSource
from agents.agent_harness.skills.metadata import skill_identity


class AdvertisingSkillCatalog(InMemorySkillCatalog):
    """Keep immutable tenant overlays out of the shared executable registry."""

    handles_managed_guidance = True
    _managed_source = 'tenant-published-guidance'

    def __init__(self, owner: Any, *, max_tenant_catalogs: int = 32, **options):
        super().__init__(**options)
        if type(max_tenant_catalogs) is not int or max_tenant_catalogs < 1:
            raise ValueError('Tenant Skill catalog capacity must be a positive integer')
        self.owner = owner
        self._max_tenant_catalogs = max_tenant_catalogs
        self._tenant_catalogs: OrderedDict[str, tuple] = OrderedDict()

    @staticmethod
    def _binding(skill, original: SkillBinding | None) -> SkillBinding:
        identity = skill_identity(skill.raw_markdown, skill.name)
        return SkillBinding(
            name=skill.name, instructions=skill.raw_markdown,
            description=skill.description, version=skill.version,
            metadata={**(original.metadata if original else {}), **identity['metadata']},
            reference_documents=skill.reference_documents,
        )

    def _overlay(self, managed) -> InMemorySkillCatalog:
        catalog = InMemorySkillCatalog(
            max_context_chars=self.max_context_chars, max_skills=self.max_skills,
            max_cached_contexts=self._max_cached_contexts,
        )
        bindings = dict(self._skills)
        overrides = {
            name: self._binding(skill, bindings.get(name)) for name, skill in managed.items()
        }
        for source, names in self._sources.items():
            catalog.register_source(StaticSkillSource(source, [
                overrides.get(name, bindings[name]) for name in names
            ]))
        standalone = [binding for name, binding in overrides.items() if name not in bindings]
        if standalone:
            catalog.register_source(StaticSkillSource(self._managed_source, standalone))
        return catalog

    def _for_tenant(self, tenant, managed):
        with self._lock:
            cached = self._tenant_catalogs.get(tenant)
            if not (cached and cached[0] == self._revision and cached[1].keys() == managed.keys()
                    and all(cached[1][name] is skill for name, skill in managed.items())):
                cached = (self._revision, dict(managed), self._overlay(managed))
                self._tenant_catalogs[tenant] = cached
            self._tenant_catalogs.move_to_end(tenant)
            while len(self._tenant_catalogs) > self._max_tenant_catalogs:
                self._tenant_catalogs.popitem(last=False)
            return cached[-1]

    def build_request_context(self, request, tools, *, source_ids=None) -> str:
        tenant = str(request.tenant_id or 'default')
        managed = self.owner.get_managed_skills(tenant)
        if not managed:
            with self._lock:
                self._tenant_catalogs.pop(tenant, None)
            return self.build_tool_context(request.user_input, tools, source_ids=source_ids)
        catalog = self._for_tenant(tenant, managed)
        # Preserve explicit source restrictions; add new tenant guidance only
        # when this scenario actually enables a registered Skill source.
        if source_ids is not None and set(source_ids) & self.source_snapshot().keys():
            source_ids = (*source_ids, self._managed_source)
        return catalog.build_tool_context(request.user_input, tools, source_ids=source_ids)
