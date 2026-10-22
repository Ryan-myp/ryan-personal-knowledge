from types import SimpleNamespace

from agents.agent_harness import TurnRequest
from agents.agent_harness.core.interfaces import ToolDefinition, ToolSchema, ToolEffect
from agents.agent_platform.governance.identity.principal import RequestPrincipal
from agents.applications.advertising.integrations.ad_capability_catalog import AdvertisingCapabilityCatalog


def tool(name, permission, *, effect=ToolEffect.READ, live_permission="", scope=False):
    return ToolDefinition(
        name=name, namespace="sample", skill="sample", description=name,
        input_schema=ToolSchema(properties={}), action=name, resource_type=name,
        effect_class=effect, required_permissions=[permission],
        live_permission=live_permission, scope_required=scope,
    )


def catalog(tools, principal, *, mode="dry_run", max_chars=9000):
    owner = SimpleNamespace(platform_application=SimpleNamespace(
        skills=SimpleNamespace(list_skills=lambda: []),
        tools=SimpleNamespace(list_tools=lambda: tools),
    ))
    return AdvertisingCapabilityCatalog(owner).build(
        TurnRequest(user_input="capabilities", principal=principal, execution_mode=mode),
        max_chars=max_chars,
    )


def test_capability_catalog_uses_current_principal_not_the_service_permissions():
    principal = RequestPrincipal(user_id="reader", permissions=frozenset({"records.read"}))
    text = catalog([
        tool("allowed", "records.read"),
        tool("forbidden", "records.write", effect=ToolEffect.WRITE),
    ], principal)
    assert "allowed" in text
    assert "forbidden" not in text


def test_live_capabilities_include_the_contracts_additional_live_permission():
    definition = tool(
        "change", "records.plan", effect=ToolEffect.WRITE, live_permission="records.live",
    )
    principal = RequestPrincipal(user_id="planner", permissions=frozenset({"records.plan"}))
    assert "change(" in catalog([definition], principal)
    assert "change(" not in catalog([definition], principal, mode="live")


def test_explicit_account_scope_requirement_is_respected_without_exposing_account_ids():
    definition = tool("scoped", "records.read", scope=True)
    denied = RequestPrincipal(user_id="reader", permissions=frozenset({"records.read"}))
    assert "scoped(" not in catalog([definition], denied)
    allowed = RequestPrincipal(
        user_id="reader", permissions=denied.permissions,
        account_scope={"sample": frozenset({"authorized-account"})},
    )
    text = catalog([definition], allowed)
    assert "scoped(" in text
    assert "authorized-account" not in text


def test_execution_boundary_remains_visible_when_catalog_details_are_truncated():
    principal = RequestPrincipal(user_id="reader", permissions=frozenset({"read"}))
    text = catalog(
        [tool(f"entry-{index}", "read") for index in range(50)],
        principal, max_chars=500,
    )
    assert len(text) <= 500
    assert "Current execution mode: dry_run" in text
    assert "previews only" in text
    assert "truncated" in text


def test_tenant_skill_listing_uses_trusted_principal_over_request_text_identity():
    calls = []
    owner = SimpleNamespace(
        get_managed_skills=lambda tenant_id: calls.append(tenant_id) or {},
    )
    principal = RequestPrincipal(user_id="reader", tenant_id="trusted")
    AdvertisingCapabilityCatalog(owner).build(TurnRequest(
        user_input="capabilities", principal=principal, tenant_id="untrusted",
    ))
    assert calls == ["trusted"]
