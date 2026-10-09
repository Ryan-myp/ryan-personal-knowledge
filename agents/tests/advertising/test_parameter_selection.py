from types import SimpleNamespace

from agents.agent_harness.core.interfaces import ToolContext, ToolResult
from agents.tools.advertising.application.execution.parameter_selection import (
    ParameterSelectionService,
)


class _Signer:
    def __init__(self):
        self.issued = []
        self.verified = []

    def issue(self, **claims):
        self.issued.append(claims)
        return "selection-token", 1_800_000_000

    def verify(self, token, **claims):
        self.verified.append((token, claims))
        if token != "selection-token":
            raise ValueError("selection token is invalid")
        return "asset-1"


def _context():
    return ToolContext(
        session_id="picker-session",
        user_id="test-user",
        scope={"account_id": "test-account"},
    )


def _tool(name, *, namespace="google-ads", properties=None, action="list"):
    return SimpleNamespace(
        name=name,
        namespace=namespace,
        action=action,
        is_write_tool=action in {"create", "upload"},
        input_schema=SimpleNamespace(
            properties=properties or {},
            required=[],
        ),
    )


def test_lookup_options_are_signed_for_target_and_account_scope():
    signer = _Signer()
    source = _tool("google_list_assets")
    target = _tool(
        "google_create_ad",
        properties={"asset_id": {
            "type": "string",
            "lookup_tool": "google_list_assets",
        }},
        action="create",
    )
    services = SimpleNamespace(
        registry=SimpleNamespace(list_all=lambda: [source, target]),
        selection_signer=signer,
    )
    selection = ParameterSelectionService(
        services, scope_value_resolver=lambda context: context.account_id,
    )
    result = ToolResult.ok({
        "assets": [{"id": "asset-1", "name": "Logo"}],
        "data_status": "live",
    })

    decorated = selection.decorate_lookup_result(
        source, result, _context(), "google-ads",
    )

    assert decorated.data["parameter_selections"][0]["options"] == [{
        "value": "asset-1",
        "label": "Logo",
        "selection_token": "selection-token",
    }]
    assert signer.issued[0]["session_id"] == "picker-session"
    assert signer.issued[0]["user_id"] == "test-user"
    assert signer.issued[0]["scope_key"] == "test-account"
    assert signer.issued[0]["tool_name"] == "google_create_ad"


def test_valid_selection_token_resolves_declared_tool_input():
    signer = _Signer()
    services = SimpleNamespace(
        selection_signer=signer,
        execution_mode="live",
        normalize_namespace=lambda value: value,
    )
    selection = ParameterSelectionService(
        services, scope_value_resolver=lambda context: context.account_id,
    )
    tool = _tool(
        "google_create_ad",
        properties={"asset_id": {
            "type": "string",
            "lookup_tool": "google_list_assets",
        }},
        action="create",
    )
    tool_input = {}

    errors = selection.apply_selection_tokens(
        tool, tool_input, {"selection_tokens": {"asset_id": "selection-token"}},
        _context(),
    )

    assert errors == []
    assert tool_input["asset_id"] == "asset-1"
    assert signer.verified[0][1]["scope_key"] == "test-account"


def test_live_create_rejects_raw_lookup_id_without_selection_token():
    services = SimpleNamespace(
        selection_signer=_Signer(),
        execution_mode="live",
        normalize_namespace=lambda value: value,
    )
    selection = ParameterSelectionService(
        services, scope_value_resolver=lambda context: context.account_id,
    )
    tool = _tool(
        "google_create_ad",
        properties={"asset_id": {
            "type": "string",
            "lookup_tool": "google_list_assets",
        }},
        action="create",
    )

    errors = selection.apply_selection_tokens(
        tool, {"asset_id": "unverified"}, {}, _context(),
    )

    assert errors == [
        "live 写入字段 asset_id 必须使用 provider lookup 返回的 selection_token"
    ]
