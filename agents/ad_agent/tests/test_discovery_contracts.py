"""Regression tests for metadata-driven Tool discovery."""

from agents.ad_agent.core.interfaces import (
    IntentParser,
    ParsedIntent,
    Skill,
    SkillWorkflow,
    SkillWorkflowStep,
    ToolContext,
    ToolDefinition,
    ToolEffect,
    ToolResult,
    ToolSchema,
)
from agents.ad_agent.core.intent import SimpleIntentRouter
from agents.ad_agent.core.tool_registry import SimpleToolRegistry
from agents.ad_agent.capabilities.meta import create_meta_capability
from agents.ad_agent.capabilities.google import create_google_capability
from agents.ad_agent.capabilities.tiktok import create_tiktok_capability
from agents.ad_agent.capabilities.dv360 import create_dv360_capability
from agents.ad_agent.runtime.runtime import AgentRuntime, AccountWhitelistValidator
from agents.ad_agent.capabilities.factory import create_capability, discover_capability_factory
from agents.ad_agent.api_clients.factory import create_platform_client


def test_existing_channel_tools_publish_routing_metadata():
    definitions = []
    for capability in (
        create_meta_capability(), create_google_capability(),
        create_tiktok_capability(), create_dv360_capability(),
    ):
        definitions.extend(definition for definition, _ in capability.register_tools())

    assert all(definition.action for definition in definitions)
    assert all(definition.resource_type for definition in definitions)
    assert all(definition.intent_types for definition in definitions if definition.is_read_tool or definition.is_write_tool)

    by_name = {definition.name: definition for definition in definitions}
    assert by_name["meta_create_adset"].parent_resource_type == "campaign"
    assert by_name["google_create_ad"].parent_resource_type == "ad_group"
    assert by_name["dv360_create_line_item"].parent_resource_type == "io"


def test_existing_channel_tools_publish_wire_id_fields_for_hierarchy():
    definitions = []
    for capability in (
        create_meta_capability(), create_google_capability(),
        create_tiktok_capability(), create_dv360_capability(),
    ):
        definitions.extend(definition for definition, _ in capability.register_tools())

    by_name = {definition.name: definition for definition in definitions}
    assert by_name["meta_create_ad"].parent_resource_id_field == "adset_id"
    assert by_name["google_create_ad"].parent_resource_id_field == "ad_group_id"
    assert by_name["tiktok_create_adgroup"].resource_id_field == "adgroup_id"
    assert by_name["tiktok_create_ad"].parent_resource_id_field == "adgroup_id"
    assert by_name["dv360_create_line_item"].parent_resource_id_field == "io_id"


def test_resource_results_follow_declared_parent_fields_across_channels():
    cases = [
        ("meta", "meta_create_campaign", "meta_create_adset", "campaign_id", "c-meta", "adset_id", "s-meta"),
        ("google-ads", "google_create_campaign", "google_create_ad_group", "campaign_id", "c-google", "ad_group_id", "g-google"),
        ("tiktok", "tiktok_create_campaign", "tiktok_create_adgroup", "campaign_id", "c-tiktok", "adgroup_id", "g-tiktok"),
        ("dv360", "dv360_create_campaign", "dv360_create_io", "campaign_id", "c-dv360", "io_id", "io-dv360"),
    ]
    definitions = {}
    for capability in (
        create_meta_capability(), create_google_capability(),
        create_tiktok_capability(), create_dv360_capability(),
    ):
        definitions.update({definition.name: definition for definition, _ in capability.register_tools()})

    normalized = []
    for platform, parent_name, child_name, parent_id_field, parent_id, child_id_field, child_id in cases:
        parent = definitions[parent_name]
        child = definitions[child_name]
        normalized.extend([
            {
                "tool": parent.name,
                "platform": platform,
                "account_id": f"{platform}-account",
                "resource_type": parent.resource_type,
                "resource_id_field": parent.resource_id_field or parent_id_field,
                "success": True,
                "data": {
                    "simulated": True,
                    parent.resource_id_field or parent_id_field: parent_id,
                    "input": {},
                },
            },
            {
                "tool": child.name,
                "platform": platform,
                "account_id": f"{platform}-account",
                "resource_type": child.resource_type,
                "resource_id_field": child.resource_id_field or child_id_field,
                "parent_resource_type": child.parent_resource_type,
                "parent_resource_id_field": child.parent_resource_id_field,
                "parent_resource_id": parent_id,
                "success": True,
                "data": {
                    "simulated": True,
                    child.resource_id_field or child_id_field: child_id,
                    "input": {child.parent_resource_id_field: parent_id},
                },
            },
        ])

    results = AgentRuntime._build_resource_results(normalized)
    assert len(results) == 8
    for index in (1, 3, 5, 7):
        assert results[index]["parent_sequence"] == results[index - 1]["sequence"]
        assert results[index]["parent_resource_id"] == results[index - 1]["logical_resource_id"]
        assert results[index]["resource_ref"]["platform"] == results[index]["platform"]
        assert results[index]["parent_ref"]["resource_id"] == results[index]["parent_resource_id"]


def test_new_standard_tool_is_discovered_without_router_configuration():
    registry = SimpleToolRegistry()

    class Handler:
        def execute(self, _ctx, _input):
            return ToolResult.ok({"discovered": True})

    registry.register(
        ToolDefinition(
            name="new_network_create_campaign",
            skill="new-network-skill",
            platform="new-network",
            description="Create a campaign on a new network",
            input_schema=ToolSchema(),
            action="create",
            resource_type="campaign",
            effect_class=ToolEffect.WRITE,
        ),
        Handler(),
    )

    routed = SimpleIntentRouter().route(
        ParsedIntent("create_campaign", "create", ["new-network"]), registry
    )
    assert [definition.name for definition in routed["new-network"]] == [
        "new_network_create_campaign"
    ]


def test_new_custom_intent_is_declared_on_tool_not_router():
    registry = SimpleToolRegistry()

    class Handler:
        def execute(self, _ctx, _input):
            return ToolResult.ok({})

    registry.register(
        ToolDefinition(
            name="new_network_estimate_reach",
            skill="new-network-skill",
            platform="new-network",
            description="Estimate reach",
            input_schema=ToolSchema(),
            action="estimate",
            resource_type="audience",
            intent_types=["estimate_reach"],
        ),
        Handler(),
    )

    routed = SimpleIntentRouter().route(
        ParsedIntent("estimate_reach", "estimate", ["new-network"]), registry
    )
    assert [definition.name for definition in routed["new-network"]] == [
        "new_network_estimate_reach"
    ]


def test_new_channel_capability_is_discovered_by_package_convention(monkeypatch):
    """Adding a channel factory must not require editing a central map."""
    import sys
    import types

    package_name = "agents.ad_agent.capabilities.new_network"
    module_name = f"{package_name}.capability"
    package = types.ModuleType(package_name)
    package.__path__ = []
    module = types.ModuleType(module_name)

    sentinel = object()
    module.create_new_network_capability = lambda client=None: sentinel
    monkeypatch.setitem(sys.modules, package_name, package)
    monkeypatch.setitem(sys.modules, module_name, module)

    factory = discover_capability_factory("new-network")
    assert callable(factory)
    assert create_capability("new-network") is sentinel


def test_new_channel_client_is_discovered_by_package_convention(monkeypatch):
    import sys
    import types

    module_name = "agents.ad_agent.api_clients.new_network_client"
    module = types.ModuleType(module_name)
    sentinel = object()
    module.create_new_network_client = lambda credentials=None: sentinel
    monkeypatch.setitem(sys.modules, module_name, module)

    assert create_platform_client("new-network", {"access_token": "secret"}) is sentinel


def test_skill_can_own_optional_workflow_without_becoming_tool_registry(tmp_path):
    from agents.ad_agent.runtime.skill import BaseSkill, SkillContract

    skill_dir = tmp_path / "channels" / "workflow-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: workflow-skill\nplatform: new-network\n---\n"
        "# Provider SOP\nUse the provider's campaign creation sequence.\n",
        encoding="utf-8",
    )
    (skill_dir / "workflow.yaml").write_text(
        "workflows:\n"
        "  create_with_validation:\n"
        "    steps:\n"
        "      - id: validate\n"
        "        tool: new_validate_campaign\n"
        "      - id: create\n"
        "        tool: new_create_campaign\n"
        "        depends_on: [validate]\n",
        encoding="utf-8",
    )

    skill = BaseSkill(SkillContract(str(skill_dir)).load())
    assert skill.get_tools() == []
    assert skill.get_workflow_mappings() == {
        "create_with_validation": {
            "new-network": ["new_validate_campaign", "new_create_campaign"]
        }
    }


def test_skill_workflow_executes_dependency_order_and_input_mapping():
    calls = []

    class FixedIntentParser(IntentParser):
        def parse(self, _user_input, _context):
            return ParsedIntent(
                intent_type="create_campaign",
                raw_input="create",
                platforms=["new-network"],
                objective="sales",
            )

    class ValidateHandler:
        def execute(self, _ctx, _input):
            calls.append("validate")
            return ToolResult.ok({"validation_id": "validation-1"})

    class CreateHandler:
        def execute(self, _ctx, input_data):
            calls.append(("create", input_data["validation_id"]))
            return ToolResult.ok({"campaign_id": "provider-campaign-1"})

    class WorkflowSkill(Skill):
        name = "new-network-skill"
        platform = "new-network"
        description = "New network campaign workflow"

        def __init__(self):
            self.handlers = {
                "new_validate_campaign": ValidateHandler(),
                "new_create_campaign": CreateHandler(),
            }

        def get_tools(self):
            return [
                ToolDefinition(
                    name="new_validate_campaign",
                    skill=self.name,
                    platform=self.platform,
                    description="Validate campaign",
                    input_schema=ToolSchema(
                        properties={"account_id": {"type": "string"}},
                    ),
                    action="validate",
                    resource_type="campaign",
                    intent_types=["create_campaign"],
                ),
                ToolDefinition(
                    name="new_create_campaign",
                    skill=self.name,
                    platform=self.platform,
                    description="Create campaign",
                    input_schema=ToolSchema(
                        required=["account_id", "name", "validation_id"],
                        properties={
                            "account_id": {"type": "string"},
                            "name": {"type": "string"},
                            "validation_id": {"type": "string"},
                        },
                    ),
                    action="create",
                    resource_type="campaign",
                    intent_types=["create_campaign"],
                    effect_class=ToolEffect.WRITE,
                ),
            ]

        def get_tool_handler(self, tool_name):
            return self.handlers[tool_name]

        def get_workflows(self):
            return {
                "create_campaign": SkillWorkflow(
                    name="create_campaign",
                    steps=(
                        SkillWorkflowStep(
                            id="create",
                            tool="new_create_campaign",
                            depends_on=("validate",),
                            input_mapping={"validation_id": "validate.validation_id"},
                        ),
                        SkillWorkflowStep(
                            id="validate",
                            tool="new_validate_campaign",
                            output_mapping={"validation_id": "validate.validation_id"},
                        ),
                    ),
                )
            }

    validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
    validator.allowed_accounts = {"new-network": ["n1"]}
    runtime = AgentRuntime(
        intent_parser=FixedIntentParser(),
        whitelist_validator=validator,
    )
    assert runtime.register_skill(WorkflowSkill(), "new-network") is True

    result = runtime.run(
        "create",
        account_id="n1",
        platform_params={"new-network": {"name": "workflow-campaign"}},
    )

    # Dry-run writes are intentionally intercepted before the Handler. The
    # planned payload is still the evidence that the workflow mapping ran.
    assert calls == ["validate"]
    assert [item["tool"] for item in result["results"]] == [
        "new_validate_campaign", "new_create_campaign",
    ]
    assert result["results"][1]["success"] is True
    assert result["results"][1]["data"]["input"]["validation_id"] == "validation-1"


def test_skill_workflow_when_false_skips_step_and_blocks_dependents():
    class FixedIntentParser(IntentParser):
        def parse(self, _user_input, _context):
            return ParsedIntent(
                intent_type="create_campaign",
                raw_input="create",
                platforms=["new-network"],
                objective="traffic",
            )

    class WorkflowSkill(Skill):
        name = "conditional-network-skill"
        platform = "new-network"
        description = "Conditional network workflow"

        def get_tools(self):
            return [
                ToolDefinition(
                    name="new_validate_campaign",
                    skill=self.name,
                    platform=self.platform,
                    description="Validate campaign",
                    input_schema=ToolSchema(),
                    action="validate",
                    resource_type="campaign",
                    intent_types=["create_campaign"],
                ),
                ToolDefinition(
                    name="new_create_campaign",
                    skill=self.name,
                    platform=self.platform,
                    description="Create campaign",
                    input_schema=ToolSchema(),
                    action="create",
                    resource_type="campaign",
                    intent_types=["create_campaign"],
                    effect_class=ToolEffect.WRITE,
                ),
            ]

        def get_tool_handler(self, _tool_name):
            return type("Handler", (), {"execute": lambda _self, _ctx, _input: ToolResult.ok({})})()

        def get_workflows(self):
            return {
                "create_campaign": SkillWorkflow(
                    name="create_campaign",
                    steps=(
                        SkillWorkflowStep(
                            id="validate",
                            tool="new_validate_campaign",
                            when={"objective": "sales"},
                        ),
                        SkillWorkflowStep(
                            id="create",
                            tool="new_create_campaign",
                            depends_on=("validate",),
                        ),
                    ),
                )
            }

    validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
    validator.allowed_accounts = {"new-network": ["n1"]}
    runtime = AgentRuntime(
        intent_parser=FixedIntentParser(),
        whitelist_validator=validator,
    )
    runtime.register_skill(WorkflowSkill(), "new-network")

    result = runtime.run("create", account_id="n1")

    assert len(result["results"]) == 1
    assert result["results"][0]["tool"] == "new_create_campaign"
    assert result["results"][0]["skipped"] is True
    assert "validate" in result["results"][0]["error"]


def test_skill_workflow_on_error_continue_allows_explicit_dependent_step():
    class FixedIntentParser(IntentParser):
        def parse(self, _user_input, _context):
            return ParsedIntent(
                intent_type="create_campaign",
                raw_input="create",
                platforms=["new-network"],
            )

    class WorkflowSkill(Skill):
        name = "continue-network-skill"
        platform = "new-network"
        description = "Continue-on-error workflow"

        def get_tools(self):
            return [
                ToolDefinition(
                    name="new_validate_campaign",
                    skill=self.name,
                    platform=self.platform,
                    description="Validate campaign",
                    input_schema=ToolSchema(),
                    action="validate",
                    resource_type="campaign",
                    intent_types=["create_campaign"],
                ),
                ToolDefinition(
                    name="new_create_campaign",
                    skill=self.name,
                    platform=self.platform,
                    description="Create campaign",
                    input_schema=ToolSchema(),
                    action="create",
                    resource_type="campaign",
                    intent_types=["create_campaign"],
                    effect_class=ToolEffect.WRITE,
                ),
            ]

        def get_tool_handler(self, tool_name):
            if tool_name == "new_validate_campaign":
                return type(
                    "FailingHandler",
                    (),
                    {"execute": lambda _self, _ctx, _input: ToolResult.error("validation failed")},
                )()
            return type(
                "Handler",
                (),
                {"execute": lambda _self, _ctx, _input: ToolResult.ok({})},
            )()

        def get_workflows(self):
            return {
                "create_campaign": SkillWorkflow(
                    name="create_campaign",
                    steps=(
                        SkillWorkflowStep(
                            id="validate",
                            tool="new_validate_campaign",
                            on_error="continue",
                        ),
                        SkillWorkflowStep(
                            id="create",
                            tool="new_create_campaign",
                            depends_on=("validate",),
                        ),
                    ),
                )
            }

    validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
    validator.allowed_accounts = {"new-network": ["n1"]}
    runtime = AgentRuntime(
        intent_parser=FixedIntentParser(),
        whitelist_validator=validator,
    )
    runtime.register_skill(WorkflowSkill(), "new-network")

    result = runtime.run("create", account_id="n1")

    assert [item["tool"] for item in result["results"]] == [
        "new_validate_campaign", "new_create_campaign",
    ]
    assert result["results"][0]["success"] is False
    assert result["results"][1]["success"] is True


def test_runtime_resource_outputs_use_tool_metadata_not_tool_name():
    definition = ToolDefinition(
        name="provider_operation",
        skill="provider-skill",
        platform="new-network",
        description="Create a campaign",
        input_schema=ToolSchema(properties={"name": {"type": "string"}}),
        action="create",
        resource_type="campaign",
        effect_class=ToolEffect.WRITE,
    )
    runtime = AgentRuntime.__new__(AgentRuntime)
    runtime.registry = SimpleToolRegistry()
    simulated = runtime._simulate_write(definition, {"name": "demo"}, "new-network")
    assert simulated.data["campaign_id"].startswith("dry_new-network_")

    assert AgentRuntime._build_resource_results([{
        "tool": "provider_operation",
        "platform": "new-network",
        "success": True,
        "data": {"campaign_id": "c1"},
    }]) == []


def test_live_mode_alone_cannot_enable_provider_writes():
    validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
    validator.allowed_accounts = {"meta": ["m1"]}
    runtime = AgentRuntime(
        execution_mode="live",
        live_approved_tools={"meta_update_campaign"},
        granted_permissions={"ads.read", "ads.plan", "ads.write"},
        whitelist_validator=validator,
    )
    runtime.register_capability(create_meta_capability())

    result = runtime.run(
        "更新 Meta campaign campaign_id=123 status=PAUSED",
        user_id="u1", account_id="m1",
    )
    assert result["results"][0]["success"] is False
    assert "allow_live_writes" in result["results"][0]["error"]
