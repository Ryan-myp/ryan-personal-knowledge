"""Focused tests for the generic planning helpers used by the ad adapter."""

from types import SimpleNamespace

from agents.ad_agent.integration_turn_planner import AdvertisingTurnPlanner


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
