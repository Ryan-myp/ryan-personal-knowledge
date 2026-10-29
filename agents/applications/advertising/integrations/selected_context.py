"""Selected-tool and advisory-revision context assembly, cached within one Run."""

from typing import Any

from .ad_capability_catalog import AdvertisingCapabilityCatalog
from .ad_turn_context import AdTurnContextService


def _selected_guidance(owner, request, tools):
    # Registered packages are already selected by the Harness using these tools.
    app = getattr(owner, "platform_application", None)
    catalog = getattr(getattr(app, "agent", None), "skill_catalog", None)
    if getattr(catalog, "handles_managed_guidance", False):
        return ""
    if catalog is not None and catalog.list_skills():
        return owner.tool_selector._managed_skill_context(
            request.user_input,
            tenant_id=request.tenant_id,
            skill_refs=owner.tool_selector._associated_skill_refs(list(tools)),
        )
    return owner.tool_selector.build_selected_skill_context(
        request.user_input,
        list(tools),
        tenant_id=request.tenant_id,
    )


def build_selected_context(provider, request, messages, tools) -> dict[str, Any]:
    """Refresh bounded advisory guidance when the Run's visible capabilities change."""
    base = provider.build_context(request, messages)
    run_id = str(request.run_id or "")
    session = provider.owner._sessions.get(str(request.session_id or ""))
    notes = session.ctx.metadata.get("conversation_state", {}) if session else {}
    signature = (
        notes.get("semantic", {}).get("revision", 0),
        tuple(
            sorted(
                (tool.name, str(tool.contract_version), tuple(tool.skill_refs or ()))
                for tool in tools
            )
        ),
    )
    cached = provider._selected_contexts.get(run_id)
    if cached and cached[0] == signature:
        return dict(cached[1])
    skill_context = dict(base["skill_context"])
    skill_context["expert_knowledge"] = _selected_guidance(provider.owner, request, tools)
    if session:
        skill_context["conversation_state"] = provider._service.render_user_constraints(
            notes, request.user_input,
        )
    skill_context["selected_tool_names"] = [tool.name for tool in tools]
    AdTurnContextService.refresh_budget(skill_context)
    prompt, evidence = provider._render_context(
        skill_context,
        base["structured_input"],
        base["capability_catalog"],
        AdvertisingCapabilityCatalog(provider.owner).read_account_candidates(request),
    )
    skill_context["knowledge_context"] = evidence
    skill_context["knowledge_context_run_id"] = run_id
    result = {
        **base,
        "skill_context": skill_context,
        "prompt": prompt,
        "knowledge_context": evidence,
    }
    if session is not None:
        session.ctx.metadata["skill_context"] = skill_context
    provider._selected_contexts[run_id] = (signature, result)
    return dict(result)
