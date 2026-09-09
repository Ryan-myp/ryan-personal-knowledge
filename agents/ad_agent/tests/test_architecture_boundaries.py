"""Architecture boundary tests for the single-Agent extension model."""

import ast
import pytest
from pathlib import Path

from agents.ad_agent.core.execution_plan import ExecutionPlan, PlanNode
from agents.ad_agent.core.interfaces import (
    ParsedIntent, ToolDefinition, ToolSchema, ToolEffect, ToolContext, ToolResult,
)
from agents.ad_agent.core.tool_selector import DynamicToolSelector
from agents.ad_agent.runtime.runtime import AgentRuntime
from agents.ad_agent.runtime.skill import SkillLoader
from agents.ad_agent.skills.businesses.policy import BusinessSkillPolicy
from agents.ad_agent.runtime.account_policy import AccountWhitelistValidator
from agents.ad_agent.runtime.session_context import SessionContext
from agents.ad_agent.core.intent import LLMIntentParser
from agents.ad_agent.core.intent import SimpleIntentRouter
from agents.ad_agent.features.response import AdAgentResponseRenderer


def test_core_does_not_host_advertising_domain_modules():
    """Advertising models belong below domain/ad, never in generic Core."""
    core = Path(__file__).resolve().parents[1] / "core"
    ad_domain = Path(__file__).resolve().parents[1] / "domain" / "ad"
    moved = {
        "blueprint.py", "creation_card.py", "cross_channel.py",
        "parameter_catalog.py", "provider_preflight.py", "release_readiness.py",
    }
    assert not any((core / name).exists() for name in moved)
    assert all((ad_domain / name).exists() for name in moved)


def test_core_contracts_do_not_publish_advertising_models_or_scope_fields():
    """Core contracts stay opaque; advertising models belong to domain/ad."""
    root = Path(__file__).resolve().parents[1]
    core = root / "core"
    interfaces = (core / "interfaces.py").read_text(encoding="utf-8")

    for name in ("auth.py", "clarification.py", "knowledge.py", "parameter_selection.py"):
        assert not (core / name).exists()
    assert "AdFormatCoverage" not in interfaces
    assert "ad_format_catalogs" not in interfaces
    assert "creation_blueprints" not in interfaces
    assert "account_id: " not in interfaces
    assert "account_id" not in ToolContext.__dataclass_fields__
    assert "scope_key" in __import__(
        "agents.ad_agent.core.interfaces", fromlist=["WriteReservation"]
    ).WriteReservation.__dataclass_fields__


def test_core_has_no_provider_or_advertising_security_catalog():
    """Provider/account credential names belong to the application boundary."""
    root = Path(__file__).resolve().parents[1] / "core"
    source = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in root.glob("*.py")
    )
    for forbidden in (
        "bc_id", "partner_id", "perter_id", "mcc", "campaign",
        "ad_group", "tiktok", "google", "dv360",
    ):
        assert forbidden not in source


def test_core_security_accepts_application_specific_redaction_policy():
    """Shared trace protection is generic and can be extended at the edge."""
    from agents.ad_agent.core.execution_trace import ExecutionTrace

    events = []
    trace = ExecutionTrace(events.append, sensitive_fields=("workspace_key",))
    trace.stage_status(
        "custom", "Custom", "succeeded",
        safe_output={"workspace_key": "secret", "value": "visible"},
    )

    assert events[-1]["safe_output"] == {"value": "visible"}


def test_generic_runtime_adapters_do_not_import_ad_domain_or_name_account_fields():
    """Generic orchestration stays usable for a non-advertising embedding."""
    root = Path(__file__).resolve().parents[1]
    generic_modules = (root / "runtime" / "input_builder.py", root / "runtime" / "workflow.py")
    for path in generic_modules:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append("." * node.level + (node.module or ""))
        assert not any("domain.ad" in item for item in imports)
        source = path.read_text(encoding="utf-8").lower()
        assert "account_id" not in source
        assert "advertiser_id" not in source


def test_runtime_discovers_domain_features_without_a_central_workflow_table():
    runtime = AgentRuntime(require_llm=False)

    assert "cross-channel" in {
        feature.feature_name for feature in runtime.features
    }
    assert not hasattr(runtime, "business_context")
    assert not hasattr(runtime, "load_business_context")
    assert not hasattr(runtime, "_build_tool_input")
    assert not hasattr(runtime, "_apply_selection_tokens")
    assert not hasattr(runtime, "_execute_tool")
    assert not hasattr(runtime, "_start_workflow")
    assert not hasattr(runtime, "_finish_workflow")
    assert not hasattr(runtime, "_validate_tool_input_redline")
    assert runtime.input_builder.services is runtime.services
    assert runtime.services.workflow_lease_owner() == runtime._workflow_lease_owner
    assert runtime.tool_executor.services is runtime.services
    assert runtime.security.runtime is runtime
    assert isinstance(runtime.workflow.services, type(runtime.services))
    assert AccountWhitelistValidator is not None
    assert SessionContext is not None
    assert "runtime._" not in (
        __import__(
            "pathlib"
        ).Path("agents/ad_agent/features/cross_channel.py").read_text(
            encoding="utf-8"
        )
    )
    assert not hasattr(DynamicToolSelector(SkillLoader()), "business_context")


def test_business_skill_policy_is_loaded_and_enforced_outside_runtime(tmp_path):
    skills_root = tmp_path / "skills"
    skill_dir = skills_root / "businesses" / "app"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "business:\n"
        "  name: app\n"
        "  allowed_channels: [google]\n"
        "  allowed_campaign_types: [APP]\n"
        "  business_rules:\n"
        "    min_budget: 50\n"
        "    max_budget: 50000\n"
        "---\n\n# App policy\n",
        encoding="utf-8",
    )

    policy = BusinessSkillPolicy.from_skill_file("app", str(skills_root))
    intent = ParsedIntent(
        intent_type="create_campaign",
        raw_input="create",
        platforms=["tiktok"],
        campaign_type="APP",
        budget=100,
    )

    errors = policy.validate_intent(intent)
    assert errors
    assert "不允许使用 tiktok" in errors[0]

    runtime = AgentRuntime(require_llm=False, policies=[policy])
    assert runtime._validate_policies(intent) == errors


def test_execution_plan_is_provider_neutral_and_validates_dependencies():
    campaign = ToolDefinition(
        name="provider_create_campaign",
        skill="provider",
        platform="provider",
        description="create",
        input_schema=ToolSchema(),
        action="create",
        resource_type="campaign",
        effect_class=ToolEffect.WRITE,
    )
    child = ToolDefinition(
        name="provider_create_child",
        skill="provider",
        platform="provider",
        description="create child",
        input_schema=ToolSchema(),
        action="create",
        resource_type="child",
        parent_resource_type="campaign",
        effect_class=ToolEffect.WRITE,
    )
    plan = ExecutionPlan.from_tool_plan(
        ParsedIntent("create", "create", ["provider"]),
        {"provider": [campaign, child]},
    )

    assert plan.nodes[1].depends_on == (plan.nodes[0].node_id,)
    assert plan.to_dict()["schema_version"] == "1.0"
    assert all("credentials" not in node for node in plan.to_dict()["nodes"])

    cyclic = ExecutionPlan(
        schema_version="1.0",
        intent_type="cycle",
        nodes=(
            PlanNode("a", 1, "provider", "a", "create", "a", depends_on=("b",)),
            PlanNode("b", 2, "provider", "b", "create", "b", depends_on=("a",)),
        ),
    )
    with pytest.raises(ValueError, match="dependency cycle"):
        cyclic.validate()


def test_parsed_intent_is_an_opaque_publisher_extension_envelope():
    """Core must not add one field per business workflow."""
    intent = ParsedIntent(
        "custom_operation",
        "do something",
        ["custom-namespace"],
        attributes={"publisher_value": "v1"},
        scoped_parameters={"custom-namespace": {"resource_key": "r1"}},
    )

    assert {
        "intent_type", "raw_input", "platforms", "attributes", "parameters",
        "scoped_parameters", "metadata",
    } == set(ParsedIntent.__dataclass_fields__)
    assert "campaign_type" not in ParsedIntent.__dataclass_fields__
    assert intent.attributes == {"publisher_value": "v1"}
    assert intent.scoped_parameters["custom-namespace"]["resource_key"] == "r1"


def test_generic_workflow_coordinator_receives_scope_from_application_boundary():
    """Workflow infrastructure must not require an account resolver."""
    from agents.ad_agent.runtime.workflow import WorkflowCoordinator

    class Store:
        def __init__(self):
            self.items = []

        def create_workflow(self, *_args, **_kwargs):
            return None

        def heartbeat_workflow(self, *_args, **_kwargs):
            return True

        def record_workflow_item(self, **kwargs):
            self.items.append(kwargs)

    class Services:
        session_manager = Store()
        execution_mode = "dry_run"

        def is_dry_run(self): return True
        def redact(self, value): return value
        def workflow_lease_owner(self): return "worker"
        def workflow_stale_after_seconds(self): return 60
        def normalize_namespace(self, value): return value.lower()
        def resolve_account(self, *_args):
            raise AssertionError("generic workflow must not resolve accounts")

    tool = ToolDefinition(
        name="custom_write",
        skill="custom",
        platform="custom-namespace",
        description="write",
        input_schema=ToolSchema(),
        action="create",
        resource_type="resource",
        effect_class=ToolEffect.WRITE,
    )
    session = type("Session", (), {"session_id": "s1"})()
    coordinator = WorkflowCoordinator(
        Services(),
        item_scope_resolver=lambda *_args: "opaque-scope",
    )
    workflow_id = coordinator.start(
        session,
        ParsedIntent("custom_operation", "create", ["custom-namespace"]),
        {"custom-namespace": [tool]},
    )

    assert workflow_id
    assert Services.session_manager.items[0]["scope"] == "opaque-scope"


def test_unpublished_intent_is_not_executable():
    """An intent becomes executable only after its publisher registers it."""
    parser = LLMIntentParser()

    normalized = parser._normalize_intent({
        "intent_type": "create_partner_bundle",
        "platforms": [],
        "objective": "retention",
    })

    assert normalized["intent_type"] == "chat"
    assert normalized["objective"] == "retention"


def test_session_context_uses_declared_resource_metadata_only():
    """Session state must not carry a central list of ad resource IDs."""
    session = SessionContext("s1", ToolContext("s1", "u1"))

    session.save_result(
        "custom_create",
        ToolResult.ok({"custom_id": "c1"}),
        platform="new-network",
    )
    assert session.protected_state == {}

    session.save_result(
        "custom_create",
        ToolResult.ok({
            "custom_id": "c1",
            "resource_id_field": "custom_id",
        }),
        platform="new-network",
    )
    assert session.protected_state == {
        "custom_id": "c1",
        "new-network:custom_id": "c1",
    }


def test_router_requires_an_exact_registered_intent():
    registry = __import__(
        "agents.ad_agent.core.tool_registry",
        fromlist=["SimpleToolRegistry"],
    ).SimpleToolRegistry()
    report_tool = ToolDefinition(
        name="new_network_download_report",
        skill="new-network",
        platform="new-network",
        description="Query reports",
        input_schema=ToolSchema(),
        action="report",
        resource_type="report",
        intent_types=["download_report"],
    )
    registry.register(report_tool, lambda _ctx, _data: ToolResult.ok({"report": []}))

    routed = SimpleIntentRouter().route(
        ParsedIntent("query_report", "query report", ["new-network"]),
        registry,
    )

    assert routed == {}


def test_parser_drops_unregistered_routing_metadata_from_platform_params():
    parser = LLMIntentParser()
    parser.register_platforms(["new-network"])
    parser.register_tool_schemas(
        "new-network",
        [{"properties": {"account_id": {"type": "string"}}}],
    )

    normalized = parser._normalize_intent({
        "intent_type": "list_resources",
        "platforms": ["new-network"],
        "platform_params": {
            "new-network": {
                "action": "list",
                "resource_type": "resource",
                "account_id": "a1",
            }
        },
    })

    assert normalized["platform_params"]["new-network"] == {
        "account_id": "a1"
    }


def test_parser_drops_llm_operation_and_note_metadata_from_platform_params():
    parser = LLMIntentParser()
    parser.register_platforms(["new-network"])
    parser.register_tool_schemas(
        "new-network",
        [{"properties": {"account_id": {"type": "string"}}}],
    )

    normalized = parser._normalize_intent({
        "intent_type": "list_resources",
        "platforms": ["new-network"],
        "platform_params": {
            "new-network": {
                "operation": "list",
                "note": "campaign list",
                "account_id": "a1",
            }
        },
    })

    assert normalized["platform_params"]["new-network"] == {
        "account_id": "a1"
    }


def test_non_chat_request_without_a_tool_never_uses_greeting_fallback():
    runtime = AgentRuntime(
        require_llm=False,
        features=[],
        whitelist_validator=__import__(
            "agents.ad_agent.runtime.account_policy",
            fromlist=["AccountWhitelistValidator"],
        ).AccountWhitelistValidator.__new__(
            __import__(
                "agents.ad_agent.runtime.account_policy",
                fromlist=["AccountWhitelistValidator"],
            ).AccountWhitelistValidator
        ),
    )
    runtime.whitelist_validator.allowed_accounts = {}

    class Parser:
        def parse(self, _text, _ctx):
            return ParsedIntent(
                "query_report", "query report", ["new-network"],
                platform_params={"new-network": {}},
            )

    runtime.intent_parser = Parser()
    result = runtime.run("查询新渠道报表")

    assert "还无法确定具体的查询对象" in result["reply"]
    assert "Tool" not in result["reply"]
    assert "Runtime" not in result["reply"]
    assert "你好！我是 ad-agent" not in result["reply"]


def test_read_renderer_does_not_claim_success_for_unknown_data_shape():
    reply = AdAgentResponseRenderer().render(
        ParsedIntent("list_resources", "list", ["new-network"]),
        [{
            "tool": "new_network_list_resources",
            "platform": "new-network",
            "success": True,
            "data": {"unexpected": {"value": 1}},
        }],
        False,
    )

    assert "成功执行查询操作" not in reply
    assert "没有可展示的数据" in reply
