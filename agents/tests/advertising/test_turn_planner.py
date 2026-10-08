"""Focused tests for the generic planning helpers used by the ad adapter."""

from types import SimpleNamespace

from agents.tools.advertising.application.integration_turn_planner import AdvertisingTurnPlanner


class _Owner:
    def _resolve_platform_identifier(self, value):
        return str(value).lower().replace("_", "-")

    def _canonical_platform(self, value):
        return self._resolve_platform_identifier(value)


def test_merge_platform_params_preserves_existing_scoped_values():
    planner = AdvertisingTurnPlanner(_Owner())
    intent = SimpleNamespace(
        namespaces=["meta"],
        scoped_parameters={"meta": {"objective": "TRAFFIC"}},
    )

    planner.merge_platform_params(
        intent,
        {"meta": {"account_id": "act-1", "objective": "SALES"}, "tiktok": {}},
    )

    assert intent.scoped_parameters == {
        "meta": {"objective": "SALES", "account_id": "act-1"},
        "tiktok": {},
    }
    assert intent.namespaces == ["meta", "tiktok"]


def test_route_repairs_platform_mismatch_before_returning_tool_directory():
    class Owner(_Owner):
        def __init__(self):
            self.loaded = []
            self.intent_parser = SimpleNamespace(
                repair_for_routing=lambda _text, _context, _intent: SimpleNamespace(
                    intent_type="list_campaigns",
                    namespaces=["tiktok"],
                )
            )
            self.intent_router = SimpleNamespace(
                route=lambda intent, _registry: (
                    {"google": ["google"]}
                    if intent.namespaces == ["meta"]
                    else {intent.namespaces[0]: [intent.namespaces[0]]}
                )
            )
            self.registry = object()

        def _load_required_skills(self, namespaces):
            self.loaded.append(tuple(namespaces))

        @staticmethod
        def _validate_policies(_intent):
            return []

    owner = Owner()
    result = AdvertisingTurnPlanner(owner).route(
        SimpleNamespace(intent_type="list_campaigns", namespaces=["meta"]),
        "list tiktok campaigns",
        SimpleNamespace(),
    )

    assert result.intent.namespaces == ["tiktok"]
    assert result.routed == {"tiktok": ["tiktok"]}
    assert owner.loaded == [("meta",), ("tiktok",)]


def test_route_revalidates_policy_after_intent_repair():
    class Owner(_Owner):
        def __init__(self):
            self.intent_parser = SimpleNamespace(
                repair_for_routing=lambda *_args: SimpleNamespace(
                    intent_type="blocked_intent",
                    namespaces=["tiktok"],
                )
            )
            self.intent_router = SimpleNamespace(
                route=lambda intent, _registry: (
                    {"google": ["google"]}
                    if intent.namespaces == ["meta"]
                    else {intent.namespaces[0]: [intent.namespaces[0]]}
                )
            )
            self.registry = object()

        @staticmethod
        def _load_required_skills(_namespaces):
            return None

        @staticmethod
        def _validate_policies(intent):
            return ["blocked"] if intent.intent_type == "blocked_intent" else []

    result = AdvertisingTurnPlanner(Owner()).route(
        SimpleNamespace(intent_type="list_campaigns", namespaces=["meta"]),
        "list tiktok campaigns",
        SimpleNamespace(),
    )

    assert result.policy_errors == ("blocked",)
    assert result.intent.intent_type == "blocked_intent"


def test_build_tool_calls_removes_internal_input_builder_markers():
    definition = SimpleNamespace(
        name="meta_list_accounts",
        namespace="meta",
        input_schema=SimpleNamespace(properties={"account_id": {}}),
        scope_fields=("account_id",),
    )
    owner = _Owner()
    owner.input_builder = SimpleNamespace(
        build=lambda *_args: {
            "account_id": "act-1",
            "_missing_params": ["ignored"],
            "_unknown_params": ["ignored"],
            "_selection_errors": ["ignored"],
        }
    )
    planner = AdvertisingTurnPlanner(owner)
    intent = SimpleNamespace(scoped_parameters={"meta": {"account_id": "act-2"}})

    calls = planner.build_tool_calls(
        {"meta": [definition]},
        intent,
        SimpleNamespace(),
    )

    assert len(calls) == 1
    assert calls[0].name == "meta_list_accounts"
    assert calls[0].arguments == {"account_id": "act-2"}


def test_build_tool_calls_resolves_scope_per_namespace():
    definitions = [
        SimpleNamespace(
            name="meta_list_campaigns",
            namespace="meta",
            input_schema=SimpleNamespace(properties={"account_id": {}}),
            scope_fields=("account_id",),
            is_write_tool=False,
        ),
        SimpleNamespace(
            name="google_list_campaigns",
            namespace="google-ads",
            input_schema=SimpleNamespace(properties={"customer_id": {}}),
            scope_fields=("customer_id",),
            is_write_tool=False,
        ),
    ]
    owner = _Owner()
    owner.input_builder = SimpleNamespace(build=lambda *_args: {})
    owner.account_resolver = SimpleNamespace(
        resolve=lambda _intent, platform, _tools, _fallback, **_kwargs: {
            "meta": "meta-test-account",
            "google-ads": "google-test-account",
        }[platform]
    )
    planner = AdvertisingTurnPlanner(owner)
    intent = SimpleNamespace(
        namespaces=["meta", "google-ads"],
        scoped_parameters={"meta": {}, "google-ads": {}},
    )

    calls = planner.build_tool_calls(
        {"meta": [definitions[0]], "google-ads": [definitions[1]]},
        intent,
        SimpleNamespace(account_id="global-meta-account"),
    )

    assert [call.arguments for call in calls] == [
        {"account_id": "meta-test-account"},
        {"customer_id": "google-test-account"},
    ]


def test_build_plan_returns_one_execution_contract_for_the_turn():
    definition = SimpleNamespace(
        name="meta_list_accounts",
        namespace="meta",
        action="list",
        resource_type="account",
        parent_resource_type=None,
        input_schema=SimpleNamespace(properties={}),
        scope_fields=(),
    )
    owner = _Owner()
    owner.input_builder = SimpleNamespace(build=lambda *_args: {})
    planner = AdvertisingTurnPlanner(owner)

    plan = planner.build_plan(
        {"meta": [definition]},
        SimpleNamespace(intent_type="list_accounts", scoped_parameters={}),
        SimpleNamespace(),
    )

    assert plan.tool_plan == {"meta": ("meta_list_accounts",)}
    assert [call.name for call in plan.calls] == ["meta_list_accounts"]
    assert plan.execution_plan.to_dict()["nodes"][0]["resource_type"] == "account"


def test_build_plan_declares_parent_result_binding_for_resource_chain():
    campaign = SimpleNamespace(
        name="meta_create_campaign",
        namespace="meta",
        action="create",
        resource_type="campaign",
        resource_id_field="campaign_id",
        parent_resource_type=None,
        parent_resource_id_field=None,
        input_schema=SimpleNamespace(properties={"name": {}}),
        scope_fields=(),
        is_write_tool=True,
    )
    ad_group = SimpleNamespace(
        name="meta_create_ad_group",
        namespace="meta",
        action="create",
        resource_type="ad_group",
        resource_id_field="ad_group_id",
        parent_resource_type="campaign",
        parent_resource_id_field="campaign_id",
        input_schema=SimpleNamespace(properties={"campaign_id": {}}),
        scope_fields=(),
        is_write_tool=True,
    )
    owner = _Owner()
    owner.input_builder = SimpleNamespace(build=lambda definition, *_args: {
        "name": "campaign" if definition is campaign else "ad group",
    })
    planner = AdvertisingTurnPlanner(owner)

    plan = planner.build_plan(
        {"meta": [campaign, ad_group]},
        SimpleNamespace(
            intent_type="create_campaign",
            scoped_parameters={},
        ),
        SimpleNamespace(),
    )

    parent_call, child_call = plan.calls
    assert child_call.depends_on == (parent_call.id,)
    assert child_call.argument_bindings[0].target_field == "campaign_id"
    assert child_call.argument_bindings[0].source_call_id == parent_call.id
    assert child_call.argument_bindings[0].source_path == "data.campaign_id"
