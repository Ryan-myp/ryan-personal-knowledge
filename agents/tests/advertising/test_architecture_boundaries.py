"""Architecture boundary tests for the single-Agent extension model."""

import ast
import pytest
from pathlib import Path

from agents.agent_harness.core.execution_plan import ExecutionPlan, PlanNode
from agents.agent_harness.core.interfaces import (
    ParsedIntent, ToolDefinition, ToolSchema, ToolEffect, ToolContext, ToolResult,
)
from agents.agent_harness import ModelTurn
from agents.agent_harness.core.tool_selector import DynamicToolSelector
from agents.tools.advertising.application.composition.ad_application import AdvertisingComposition
from agents.agent_harness.skills.contract import SkillLoader
from agents.skills.advertising.businesses.policy import BusinessSkillPolicy
from agents.tools.advertising.application.execution.account_policy import AccountWhitelistValidator
from agents.tools.advertising.application.operations.session_context import SessionContext
from agents.agent_harness.core.intent import SimpleIntentRouter
from agents.agent_harness.core.intent import LLMIntentParser


def test_core_does_not_host_advertising_domain_modules():
    """Advertising models belong to the advertising Tool package."""
    root = Path(__file__).resolve().parents[2]
    core = root / "agent_harness" / "core"
    ad_domain = root / "tools" / "advertising" / "shared" / "domain"
    moved = {
        "blueprint.py", "creation_card.py", "cross_channel.py",
        "parameter_catalog.py", "provider_preflight.py", "release_readiness.py",
    }
    assert not any((core / name).exists() for name in moved)
    assert all((ad_domain / name).exists() for name in moved)


def test_advertising_application_modules_have_single_layer_ownership():
    """Application modules live under their architectural responsibility."""
    root = Path(__file__).resolve().parents[2] / "tools" / "advertising" / "application"
    ownership = {
        "composition": {
            "ad_application.py", "ad_application_assembly.py",
            "ad_application_bootstrap.py", "ad_application_components.py",
            "ad_application_contracts.py", "ad_application_facade.py",
            "ad_application_hooks.py", "ad_runtime_facades.py",
        },
        "creation": {
            "ad_creation_blueprint_services.py", "ad_creation_catalog_services.py",
            "ad_creation_contract_services.py", "ad_creation_services.py",
            "ad_creation_template_services.py", "ad_creation_ui_services.py",
        },
        "execution": {
            "account_context.py", "account_policy.py", "ad_tool_interaction.py",
            "ad_tool_policy_factory.py", "input_builder.py",
            "parameter_selection.py", "security.py", "tool_executor.py",
        },
        "integrations": {
            "ad_provider_runtime_services.py", "ad_skill_discovery.py",
            "ad_skill_lifecycle.py", "ad_skill_plugins.py",
            "ad_tool_source_registration.py", "ad_tool_source_services.py",
            "ad_turn_context.py", "integration.py", "provider_bindings.py",
            "tool_source_context.py",
        },
        "operations": {
            "ad_conversation_services.py", "ad_persistence_services.py",
            "ad_session_services.py", "ad_task_operational_services.py",
            "ad_task_services.py", "ad_workflow_provider_reconciliation.py",
            "ad_workflow_services.py", "reconciliation.py",
            "scheduling_service.py", "services.py", "session_context.py",
            "workflow.py",
        },
        "run": {
            "ad_run_memory.py", "ad_run_projection.py", "ad_run_service.py",
            "ad_runtime_catalog.py", "ad_runtime_context.py",
            "ad_runtime_controls.py", "ad_runtime_lifecycle.py",
            "ad_runtime_policy.py", "ad_runtime_presentation.py",
            "ad_runtime_reconciliation.py", "ad_runtime_scope.py",
        },
    }

    expected = set().union(*ownership.values())
    actual = {
        path.name
        for path in root.glob("*.py")
        if path.name != "__init__.py"
    }
    assert actual == set()
    assert expected == {
        path.name
        for package in ownership
        for path in (root / package).glob("*.py")
        if path.name != "__init__.py"
    }
    for package, modules in ownership.items():
        package_path = root / package
        assert (package_path / "__init__.py").is_file()
        assert {path.name for path in package_path.glob("*.py")} - {"__init__.py"} == modules

    allowed_dependencies = {
        "composition": set(ownership),
        "creation": {"creation"},
        "execution": {"execution"},
        "integrations": {"integrations"},
        "operations": {"operations"},
        "run": {"execution", "integrations", "run"},
    }
    for package, dependencies in allowed_dependencies.items():
        for path in (root / package).glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or not node.level:
                    continue
                dependency = (
                    package if node.level == 1 else (node.module or "").split(".")[0]
                )
                assert dependency in dependencies, (
                    f"{path.relative_to(root)} imports across an invalid layer: "
                    f"{node.module or ''}"
                )


def test_core_contracts_do_not_publish_advertising_models_or_scope_fields():
    """Harness contracts stay opaque; advertising models belong to Tools."""
    root = Path(__file__).resolve().parents[2] / "agent_harness"
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
        "agents.agent_harness.core.interfaces", fromlist=["WriteReservation"]
    ).WriteReservation.__dataclass_fields__


def test_core_has_no_provider_or_advertising_security_catalog():
    """Provider/account credential names belong to the application boundary."""
    root = Path(__file__).resolve().parents[2] / "agent_harness" / "core"
    source = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in root.glob("*.py")
    )
    for forbidden in (
        "bc_id", "partner_id", "perter_id", "mcc", "campaign",
        "ad_group", "tiktok", "google", "dv360",
    ):
        assert forbidden not in source


def test_router_only_requires_a_read_only_tool_catalog():
    """Routing must not depend on the executable registry implementation."""
    from agents.agent_harness.core.interfaces import ToolCatalog

    tool = ToolDefinition(
        name="catalog_read",
        skill="custom",
        namespace="custom",
        description="read a resource",
        input_schema=ToolSchema(),
        action="read",
        resource_type="resource",
        intent_types=["read_resource"],
    )

    class Catalog:
        def list_by_namespace(self, namespace):
            return [tool] if namespace == "custom" else []

    catalog = Catalog()
    assert isinstance(catalog, ToolCatalog)
    assert [item.name for item in SimpleIntentRouter().route(
        ParsedIntent("read_resource", "read", ["custom"]), catalog
    )["custom"]] == ["catalog_read"]


def test_execution_plan_rejects_invalid_namespace_and_sequence():
    """A persisted plan must have stable, unambiguous node identity."""
    for node in (
        PlanNode("empty-namespace", 1, "", "tool", "read", "resource"),
        PlanNode("zero-sequence", 0, "custom", "tool", "read", "resource"),
    ):
        with pytest.raises(ValueError):
            ExecutionPlan("1.0", "read_resource", (node,)).validate()


def test_core_security_accepts_application_specific_redaction_policy():
    """Shared trace protection is generic and can be extended at the edge."""
    from agents.agent_harness.core.execution_trace import ExecutionTrace

    events = []
    trace = ExecutionTrace(events.append, sensitive_fields=("workspace_key",))
    trace.stage_status(
        "custom", "Custom", "succeeded",
        safe_output={"workspace_key": "secret", "value": "visible"},
    )

    assert events[-1]["safe_output"] == {"value": "visible"}


def test_generic_runtime_adapters_do_not_import_ad_domain_or_name_account_fields():
    """Generic orchestration stays usable for a non-advertising embedding."""
    root = Path(__file__).resolve().parents[2] / "agent_harness"
    generic_modules = (root / "agent_runtime.py", root / "turn_pipeline.py")
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


def test_runtime_has_no_advertising_feature_turn_handlers():
    runtime = AdvertisingComposition(require_llm=False)

    assert runtime.features == []
    assert not hasattr(runtime, "business_context")
    assert not hasattr(runtime, "load_business_context")
    assert not hasattr(runtime, "_build_tool_input")
    assert not hasattr(runtime, "_apply_selection_tokens")
    assert not hasattr(runtime, "_execute_tool")
    assert not hasattr(runtime, "_start_workflow")
    assert not hasattr(runtime, "_finish_workflow")
    assert not hasattr(runtime, "_validate_tool_input_redline")
    assert not hasattr(runtime, "_render_response")
    assert not hasattr(runtime, "response_renderer")
    assert not hasattr(runtime, "response_synthesizer")
    assert runtime.input_builder.services is runtime.services
    assert runtime.services.workflow_lease_owner() == runtime._workflow_lease_owner
    assert runtime.tool_executor.services is runtime.services
    assert runtime.security.runtime is runtime
    assert isinstance(runtime.workflow.services, type(runtime.services))
    assert AccountWhitelistValidator is not None
    assert SessionContext is not None
    assert not Path(
        "agents/tools/advertising/shared/features/cross_channel.py"
    ).exists()
    assert not hasattr(DynamicToolSelector(SkillLoader()), "business_context")


def test_creation_application_exposes_configuration_not_turn_handlers():
    from agents.tools.advertising.application.creation.ad_creation_services import (
        AdCreationServicesMixin,
    )

    service_names = {
        base.__name__ for base in AdCreationServicesMixin.__mro__
    }

    assert "AdTurnInteractionServicesMixin" not in service_names
    assert "AdCreationResponseServicesMixin" not in service_names
    assert "AdSchedulingPreflightMixin" not in service_names
    assert not hasattr(AdCreationServicesMixin, "prepare_creation_turn")
    assert not hasattr(AdCreationServicesMixin, "adopt_creation_drafts")
    assert not hasattr(AdCreationServicesMixin, "preflight_scheduled_prompt")
    assert hasattr(AdCreationServicesMixin, "build_creation_ui")
    assert hasattr(AdCreationServicesMixin, "list_creation_blueprints")
    assert not hasattr(AdvertisingComposition, "preflight_scheduled_prompt")


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
        namespaces=["tiktok"],
        campaign_type="APP",
        budget=100,
    )

    errors = policy.validate_intent(intent)
    assert errors
    assert "不允许使用 tiktok" in errors[0]

    runtime = AdvertisingComposition(require_llm=False, policies=[policy])
    assert runtime._validate_policies(intent) == errors


def test_execution_plan_is_provider_neutral_and_validates_dependencies():
    campaign = ToolDefinition(
        name="provider_create_campaign",
        skill="provider",
        namespace="provider",
        description="create",
        input_schema=ToolSchema(),
        action="create",
        resource_type="campaign",
        effect_class=ToolEffect.WRITE,
    )
    child = ToolDefinition(
        name="provider_create_child",
        skill="provider",
        namespace="provider",
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
        "intent_type", "raw_input", "namespaces", "attributes", "parameters",
        "scoped_parameters", "metadata",
    } == set(ParsedIntent.__dataclass_fields__)
    assert "campaign_type" not in ParsedIntent.__dataclass_fields__
    assert intent.attributes == {"publisher_value": "v1"}
    assert intent.scoped_parameters["custom-namespace"]["resource_key"] == "r1"


def test_generic_workflow_coordinator_receives_scope_from_application_boundary():
    """Workflow infrastructure must not require an account resolver."""
    from agents.tools.advertising.application.operations.workflow import WorkflowCoordinator

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
        namespace="custom-namespace",
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
        "namespaces": [],
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
        "agents.agent_harness.core.tool_registry",
        fromlist=["SimpleToolRegistry"],
    ).SimpleToolRegistry()
    report_tool = ToolDefinition(
        name="new_network_download_report",
        skill="new-network",
        namespace="new-network",
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


def test_parser_drops_unregistered_routing_metadata_from_scoped_parameters():
    parser = LLMIntentParser()
    parser.register_namespaces(["new-network"])
    parser.register_tool_schemas(
        "new-network",
        [{"properties": {"account_id": {"type": "string"}}}],
    )

    normalized = parser._normalize_intent({
        "intent_type": "list_resources",
        "namespaces": ["new-network"],
        "scoped_parameters": {
            "new-network": {
                "action": "list",
                "resource_type": "resource",
                "account_id": "a1",
            }
        },
    })

    assert normalized["scoped_parameters"]["new-network"] == {
        "account_id": "a1"
    }


def test_parser_drops_llm_operation_and_note_metadata_from_scoped_parameters():
    parser = LLMIntentParser()
    parser.register_namespaces(["new-network"])
    parser.register_tool_schemas(
        "new-network",
        [{"properties": {"account_id": {"type": "string"}}}],
    )

    normalized = parser._normalize_intent({
        "intent_type": "list_resources",
        "namespaces": ["new-network"],
        "scoped_parameters": {
            "new-network": {
                "operation": "list",
                "note": "campaign list",
                "account_id": "a1",
            }
        },
    })

    assert normalized["scoped_parameters"]["new-network"] == {
        "account_id": "a1"
    }


def test_generic_run_uses_harness_model_and_has_no_ad_parser_or_router():
    class Model:
        def complete(self, _messages, _tools, _request):
            return ModelTurn(content="还无法确定具体的查询对象。")

    runtime = AdvertisingComposition(
        require_llm=False,
        llm_client=Model(),
        features=[],
    )

    assert not hasattr(runtime, "intent_parser")
    assert not hasattr(runtime, "intent_router")
    result = runtime.run("查询新渠道报表")

    assert "还无法确定具体的查询对象" in result["reply"]
    assert result["tool_plan"] == {}
    assert "你好！我是 ad-agent" not in result["reply"]


def test_advertising_application_has_no_parser_or_router_wiring():
    root = Path(__file__).resolve().parents[2] / "tools" / "advertising" / "application"
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in root.glob("*.py")
    )
    assert "intent_parser" not in source
    assert "intent_router" not in source
    assert "SimpleIntentRouter" not in source


def test_legacy_parser_is_not_an_advertising_composition_dependency():
    runtime = AdvertisingComposition(
        require_llm=True,
    )

    assert runtime.platform_application.agent.model is None
    assert not hasattr(runtime, "intent_parser")
    assert not hasattr(runtime, "intent_router")
    with pytest.raises(RuntimeError, match="LLM client is required"):
        runtime.assert_llm_ready()
