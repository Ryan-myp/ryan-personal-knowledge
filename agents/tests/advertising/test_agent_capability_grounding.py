from pathlib import Path
from types import SimpleNamespace

from agents.agent_harness import ModelTurn, SkillBinding, TurnRequest
from agents.agent_harness.core.interfaces import (
    ToolDefinition,
    ToolEffect,
    ToolSchema,
)
from agents.agent_harness.core.tool_selection import ToolSelector
from agents.applications.advertising.composition.ad_application_assembly import (
    AdApplicationAssembly,
)
from agents.applications.advertising.composition.ad_application import (
    AdvertisingComposition,
)
from agents.applications.advertising.integrations.integration import (
    AdvertisingContextProvider,
)
from agents.scenarios.advertising import advertising_agent_definition


def _tool(
    name,
    action,
    resource_type,
    description,
    *,
    effect_class=ToolEffect.READ,
    live_support=None,
):
    return ToolDefinition(
        name=name,
        skill="campaign-management",
        namespace="google-ads",
        description=description,
        input_schema=ToolSchema(properties={
            "campaign_id": {"type": "string"},
            "access_token": {"type": "string"},
        }),
        action=action,
        resource_type=resource_type,
        effect_class=effect_class,
        live_support=live_support,
    )


def test_advertising_system_prompt_grounds_capability_claims_in_registered_sources():
    prompt = advertising_agent_definition().system_prompt

    assert "AI Ops Agent" in prompt
    assert "能力目录" in prompt
    assert "Skills" in prompt
    assert "Tools" in prompt
    assert "预训练知识" in prompt
    assert "执行结果" in prompt
    assert "普通问候" in prompt
    assert "2-3 项" in prompt
    assert "不得自称底层模型" in prompt
    assert "不得自行编造字段清单" in prompt
    assert "没有返回创建卡片时不得声称已生成创建表单" in prompt


def test_core_agent_contract_forbids_inventing_model_identity():
    runtime = AdvertisingComposition(
        require_llm=False,
        offline_mode=True,
        start_background_workers=False,
    )
    try:
        prompt = runtime.platform_application.agent.system_prompt
    finally:
        runtime.close(wait=True)

    assert "Do not" in prompt
    assert "invent or claim a personal name, model identity, provider, or developer" in prompt


def test_capability_catalog_uses_scenario_registry_and_respects_tool_allowlist():
    skills = [
        SkillBinding(
            name="google-ads",
            description="Google Ads campaigns and reporting",
            instructions="advisory instructions",
        ),
    ]
    tools = [
        _tool(
            "google_ads_list_campaigns",
            "list",
            "campaign",
            "List campaigns in the selected account.",
        ),
        _tool(
            "google_ads_update_campaign",
            "update",
            "campaign",
            "Update a campaign.",
        ),
    ]
    owner = SimpleNamespace(
        platform_application=SimpleNamespace(
            skills=SimpleNamespace(list_skills=lambda: skills),
            tools=SimpleNamespace(list_tools=lambda: tools),
        ),
    )
    provider = AdvertisingContextProvider(owner)
    request = TurnRequest(
        user_input="What can you do?",
        tool_allowlist=("google_ads_list_campaigns",),
    )

    catalog = provider._capability_catalog(request)

    assert "google-ads" in catalog
    assert "Google Ads campaigns and reporting" in catalog
    assert "campaign" in catalog
    assert "list" in catalog
    assert "update" not in catalog
    assert "access_token" not in catalog


def test_capability_catalog_includes_builtin_and_only_request_tenant_skills():
    builtin = SimpleNamespace(
        name="google-ads",
        description="Google Ads campaign guidance.",
    )
    tenant_skill = SimpleNamespace(
        name="tenant-growth-playbook",
        description="Tenant-specific growth advice.",
    )
    other_tenant_skill = SimpleNamespace(
        name="other-tenant-secret-skill",
        description="Must never cross tenant boundary.",
    )
    owner = SimpleNamespace(
        skill_loader=SimpleNamespace(list_all=lambda: {"google-ads": builtin}),
        get_managed_skills=lambda tenant_id: {
            "tenant-growth-playbook": tenant_skill,
        } if tenant_id == "tenant-a" else {
            "other-tenant-secret-skill": other_tenant_skill,
        },
        platform_application=SimpleNamespace(
            skills=SimpleNamespace(list_skills=lambda: []),
            tools=SimpleNamespace(list_tools=lambda: []),
        ),
    )

    catalog = AdvertisingContextProvider(owner)._capability_catalog(
        TurnRequest(user_input="What can you do?", tenant_id="tenant-a")
    )

    assert "google-ads" in catalog
    assert "tenant-growth-playbook" in catalog
    assert "other-tenant-secret-skill" not in catalog
    assert "advisory" in catalog.lower()


def test_capability_catalog_distinguishes_dry_run_from_declared_live_adapter():
    tools = [
        _tool(
            "google_ads_create_campaign",
            "create",
            "campaign",
            "Create a campaign.",
            effect_class=ToolEffect.WRITE,
            live_support=False,
        ),
        _tool(
            "google_ads_list_campaigns",
            "list",
            "campaign",
            "List campaigns.",
            live_support=True,
        ),
    ]
    owner = SimpleNamespace(
        execution_mode="live",
        platform_application=SimpleNamespace(
            skills=SimpleNamespace(list_skills=lambda: []),
            tools=SimpleNamespace(list_tools=lambda: tools),
        ),
    )

    catalog = AdvertisingContextProvider(owner)._capability_catalog(
        TurnRequest(user_input="What can you do?", execution_mode="dry_run")
    )

    assert "Current execution mode: dry_run" in catalog
    assert "create(W,D)" in catalog
    assert "list(R,L)" in catalog
    assert "D=dry-run only" in catalog
    assert "L=live adapter declared only" in catalog
    assert "does not verify account access or live API success" in catalog


def test_capability_catalog_does_not_claim_tools_outside_request_allowlist():
    tools = [
        _tool("google_ads_list_campaigns", "list", "campaign", "List campaigns."),
        _tool("google_ads_get_report", "get", "report", "Get a report."),
    ]
    owner = SimpleNamespace(
        platform_application=SimpleNamespace(
            skills=SimpleNamespace(list_skills=lambda: []),
            tools=SimpleNamespace(list_tools=lambda: tools),
        ),
    )

    catalog = AdvertisingContextProvider(owner)._capability_catalog(
        TurnRequest(
            user_input="What can you do?",
            tool_allowlist=("google_ads_list_campaigns",),
        )
    )

    assert "campaign" in catalog
    assert "-> get(" not in catalog


def test_capability_catalog_truncation_stays_within_context_budget():
    skills = [
        SimpleNamespace(
            name=f"skill-{index}",
            description="Detailed advisory skill description. " * 4,
        )
        for index in range(20)
    ]
    owner = SimpleNamespace(
        platform_application=SimpleNamespace(
            skills=SimpleNamespace(list_skills=lambda: skills),
            tools=SimpleNamespace(list_tools=lambda: []),
        ),
    )

    catalog = AdvertisingContextProvider(owner)._capability_catalog(
        TurnRequest(user_input="What can you do?"),
        max_chars=280,
    )

    assert len(catalog) <= 280
    assert "[catalog truncated;" in catalog


def test_registered_provider_capabilities_fit_default_catalog_budget():
    runtime = AdvertisingComposition(
        require_llm=False,
        offline_mode=True,
        start_background_workers=False,
    )
    try:
        skills_root = (
            Path(__file__).resolve().parents[3]
            / "agents"
            / "skills"
            / "advertising"
        )
        runtime.auto_load_skills(
            str(skills_root),
            {},
            allow_provider_tool_discovery=True,
        )

        catalog = AdvertisingContextProvider(runtime)._capability_catalog(
            TurnRequest(user_input="你好，你有什么能力？")
        )

        assert len(runtime.registry.list_all()) == 300
        assert len(catalog) <= 9_000
        assert "[catalog truncated;" not in catalog
        assert all(
            f"- {provider}:" in catalog
            for provider in ("dv360", "google-ads", "meta", "tiktok")
        )
        assert "dv360: line_item" in catalog
        assert "google-ads: campaign" in catalog
        assert "meta: ad_set" in catalog
        assert "tiktok: video" in catalog
    finally:
        runtime.close(wait=True)


def test_capability_catalog_is_injected_into_the_application_context():
    prompt = AdvertisingContextProvider._render_prompt(
        skill_context={},
        capability_catalog=(
            "[REGISTERED CAPABILITIES]\n"
            "Skills: google-ads\n"
            "Tools: google-ads campaign (list)"
        ),
    )

    assert "[REGISTERED CAPABILITIES]" in prompt
    assert "google-ads campaign (list)" in prompt
    assert "only" in prompt.lower() or "仅" in prompt


def test_plain_greeting_receives_registered_capabilities_and_intro_policy():
    class Model:
        def __init__(self):
            self.calls = []

        def complete(self, messages, tools, _request):
            self.calls.append((list(messages), list(tools)))
            return ModelTurn(
                content="你好，我是 AI Ops Agent，可以介绍当前已接入的能力。"
            )

    class Executor:
        @staticmethod
        def execute(*_args, **_kwargs):
            return {"success": True}

    model = Model()
    runtime = AdvertisingComposition(
        require_llm=True,
        llm_client=model,
        features=[],
    )
    runtime.register_tool(
        _tool(
            "google_ads_list_campaigns",
            "list",
            "campaign",
            "List campaigns in the selected account.",
        ),
        Executor(),
    )
    try:
        result = runtime.run("你好", user_id="operator")
    finally:
        runtime.close(wait=True)

    assert result["status"] == "succeeded"
    assert len(model.calls) == 1
    messages, tools = model.calls[0]
    system_text = "\n".join(
        str(message.content) for message in messages if message.role == "system"
    )
    assert "google-ads: campaign -> list(" in system_text
    assert "Skills (advisory guidance only" in system_text
    assert "AI Ops Agent" in system_text
    assert "普通问候" in system_text
    assert "2-3 项" in system_text
    assert "不得自称底层模型" in system_text
    assert tools == []


def test_ad_selector_exposes_specific_tools_beyond_the_old_sixteen_tool_prefix():
    from agents.tools.advertising.providers.tiktok import create_tiktok_tool_source

    tools = [
        definition
        for definition, _handler in create_tiktok_tool_source().register_tools()
    ]
    select_tools = AdApplicationAssembly._tool_selector(
        SimpleNamespace(),
        ToolSelector(),
    )
    request = TurnRequest(
        user_input="创建一个 TikTok App 转化广告，使用我的 App",
        context={},
    )

    visible = select_tools(request, tools)

    assert "tiktok_smart_plus_create_campaign" in {
        item.name for item in visible
    }
