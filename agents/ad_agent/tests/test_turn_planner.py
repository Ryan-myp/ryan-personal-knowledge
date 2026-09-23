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
