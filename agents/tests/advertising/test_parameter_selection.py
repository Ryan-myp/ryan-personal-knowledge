from types import SimpleNamespace
import pytest

from agents.agent_harness.core.interfaces import ToolContext, ToolResult
from agents.applications.advertising.execution.parameter_selection import (
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


def _live_lookup():
    signer = _Signer()
    source = _tool("example_list_assets", namespace="example")
    target = _tool(
        "example_create_ad", namespace="example", action="create",
        properties={"asset_id": {"type": "string", "lookup_tool": source.name}},
    )
    services = SimpleNamespace(
        registry=SimpleNamespace(list_all=lambda: [source, target]),
        selection_signer=signer, execution_mode="live",
        normalize_namespace=lambda value: value,
    )
    service = ParameterSelectionService(
        services, scope_value_resolver=lambda context: context.account_id,
    )
    return service, signer, source, target


def test_native_creation_reuses_a_live_lookup_proof_without_exposing_its_token_to_the_model():
    selection, signer, source, target = _live_lookup()
    selection.decorate_lookup_result(
        source, ToolResult.ok({
            "assets": [{"id": "asset-1"}], "data_status": "live",
        }), _context(), "example",
    )
    errors = selection.apply_selection_tokens(
        target, {"asset_id": "asset-1"}, {}, _context(),
    )
    assert errors == []
    assert signer.verified[0][1]["tool_name"] == target.name
    assert signer.verified[0][1]["field"] == "asset_id"


@pytest.mark.parametrize("change", ["session", "user", "tenant", "account", "value", "tool", "namespace"])
def test_native_lookup_proof_cannot_authorize_another_scope(change):
    selection, _signer, source, target = _live_lookup()
    selection.decorate_lookup_result(
        source, ToolResult.ok({
            "assets": [{"id": "asset-1"}], "data_status": "live",
        }), _context(), "example",
    )
    context = _context()
    value = "asset-1"
    if change == "session":
        context.session_id = "another-session"
    elif change == "user":
        context.user_id = "another-user"
    elif change == "tenant":
        context.metadata["tenant_id"] = "another-tenant"
    elif change == "account":
        context.account_id = "another-account"
    elif change == "value":
        value = "another-asset"
    else:
        setattr(target, "name" if change == "tool" else "namespace", "another")
    assert selection.apply_selection_tokens(target, {"asset_id": value}, {}, context)


@pytest.mark.parametrize("data_status", ["offline_no_client", "local", None])
def test_native_creation_never_treats_an_offline_lookup_as_provider_authorization(data_status):
    selection, _signer, source, target = _live_lookup()
    selection.decorate_lookup_result(
        source, ToolResult.ok({
            "assets": [{"id": "asset-1"}], "data_status": data_status,
        }), _context(), "example",
    )
    assert selection.apply_selection_tokens(target, {"asset_id": "asset-1"}, {}, _context())


def test_native_creation_verifies_expiry_even_for_a_remembered_provider_lookup():
    selection, signer, source, target = _live_lookup()
    selection.decorate_lookup_result(
        source, ToolResult.ok({
            "assets": [{"id": "asset-1"}], "data_status": "live",
        }), _context(), "example",
    )
    def expired(*_args, **_kwargs):
        raise ValueError("selection token expired")
    signer.verify = expired
    errors = selection.apply_selection_tokens(
        target, {"asset_id": "asset-1"}, {}, _context(),
    )
    assert any("expired" in error for error in errors)


def test_a_new_empty_live_lookup_invalidates_previously_cached_options():
    selection, _signer, source, target = _live_lookup()
    for assets in ([{"id": "asset-1"}], []):
        selection.decorate_lookup_result(
            source, ToolResult.ok({"assets": assets, "data_status": "live"}),
            _context(), "example",
        )
    assert selection.apply_selection_tokens(target, {"asset_id": "asset-1"}, {}, _context())


def test_native_lookup_proofs_are_bounded_and_not_part_of_persistent_context():
    selection, _signer, source, target = _live_lookup()
    context = _context()
    for index in range(270):
        context.session_id = f"session-{index}"
        selection.decorate_lookup_result(
            source, ToolResult.ok({"assets": [{"id": "asset-1"}], "data_status": "live"}),
            context, "example",
        )
    assert len(selection._lookup_proofs) == 256
    assert context.metadata == {}
    assert context.protected_state == {}
    context.session_id = "session-0"
    assert selection.apply_selection_tokens(target, {"asset_id": "asset-1"}, {}, context)
    context.session_id = "session-269"
    assert selection.apply_selection_tokens(target, {"asset_id": "asset-1"}, {}, context) == []


def test_implicit_business_catalog_proof_still_requires_the_same_selected_account():
    selection, _signer, source, target = _live_lookup()
    target.input_schema.properties["asset_id"]["lookup_account_required"] = False
    selection.decorate_lookup_result(
        source, ToolResult.ok({"assets": [{"id": "asset-1"}], "data_status": "live"}),
        _context(), "example",
    )
    context = _context()
    context.account_id = "another-account"
    assert selection.apply_selection_tokens(target, {"asset_id": "asset-1"}, {}, context)


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


@pytest.mark.parametrize(
    ("query", "expected_count"),
    [
        ("customers/123/assets/24", 1),
        ("asset 24", 1),
        ("  ASSET 24  ", 1),
        ("not-present", 0),
        (None, 20),
    ],
)
def test_lookup_search_filters_before_the_twenty_option_limit(query, expected_count):
    signer = _Signer()
    source = _tool("google_list_assets")
    target = _tool("google_create_ad", action="create", properties={"asset_id": {
        "type": "string",
        "lookup_tool": source.name,
        "selection_value_fields": ["resource_name"],
    }})
    services = SimpleNamespace(
        registry=SimpleNamespace(list_all=lambda: [source, target]),
        selection_signer=signer,
    )
    selection = ParameterSelectionService(
        services, scope_value_resolver=lambda context: context.account_id,
    )
    result = ToolResult.ok({
        "assets": [
            {"resource_name": f"customers/123/assets/{index}", "name": f"Asset {index}"}
            for index in range(30)
        ],
        "data_status": "live",
    })
    decorated = selection.decorate_lookup_result(
        source, result, _context(), "google-ads",
        target_tool_name=target.name, target_field="asset_id", query=query,
    )
    options = decorated.data["parameter_selections"][0]["options"]
    assert len(options) == expected_count
    assert len(signer.issued) == expected_count
    if expected_count == 1:
        assert options[0]["value"] == "customers/123/assets/24"
        assert signer.issued[0]["scope_key"] == "test-account"


def test_google_asset_lookup_excludes_resources_with_the_wrong_asset_type():
    signer = _Signer()
    source = _tool("google_list_assets")
    target = _tool(
        "google_create_ad",
        properties={"images": {
            "type": "array",
            "lookup_tool": "google_list_assets",
            "lookup_asset_types": ["IMAGE"],
            "items": {"type": ["string", "object"]},
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
        "assets": [
            {"id": "text-1", "name": "Not an image", "type": "TEXT"},
            {"id": "image-1", "name": "Approved image", "type": "IMAGE"},
        ],
        "data_status": "live",
    })

    decorated = selection.decorate_lookup_result(
        source, result, _context(), "google-ads",
    )

    assert decorated.data["parameter_selections"][0]["options"] == [{
        "value": "image-1",
        "label": "Approved image",
        "selection_token": "selection-token",
    }]
    assert [item["value"] for item in signer.issued] == ["image-1"]


def test_exact_resource_lookup_signs_a_single_object_result():
    signer = _Signer()
    source = _tool("tiktok_get_video", namespace="tiktok")
    target = _tool(
        "tiktok_smart_plus_create_ad",
        namespace="tiktok",
        properties={"video_id": {
            "type": "string",
            "lookup_tool": "tiktok_get_video",
            "lookup_result_key": "video",
            "selection_value_fields": ["video_id", "id"],
            "selection_label_fields": ["file_name", "name"],
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
        "video": {
            "video_id": "video-42",
            "file_name": "verified-video.mp4",
        },
        "data_status": "live",
    })

    decorated = selection.decorate_lookup_result(
        source,
        result,
        _context(),
        "tiktok",
        target_tool_name="tiktok_smart_plus_create_ad",
        target_field="video_id",
    )

    assert decorated.data["parameter_selections"][0]["options"] == [{
        "value": "video-42",
        "label": "verified-video.mp4",
        "selection_token": "selection-token",
    }]
    assert signer.issued[0]["scope_key"] == "test-account"
    assert signer.issued[0]["tool_name"] == "tiktok_smart_plus_create_ad"


def test_tiktok_image_lookup_uses_stable_image_id_not_signed_preview_url():
    signer = _Signer()
    source = _tool("tiktok_list_images", namespace="tiktok")
    target = _tool(
        "tiktok_smart_plus_create_ad",
        namespace="tiktok",
        properties={"image_web_uris": {
            "type": "array",
            "lookup_tool": "tiktok_list_images",
            "lookup_result_key": "images",
            "selection_value_fields": ["web_uri", "image_id", "image_url"],
            "selection_label_fields": ["file_name", "image_name", "image_id"],
            "items": {"type": "string"},
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
        "images": [{
            "image_id": "ad-site-i18n-sg/stable-image",
            "image_url": "https://cdn.example/image.jpg?signature=temporary",
            "file_name": "cover.jpg",
        }],
        "data_status": "live",
    })

    decorated = selection.decorate_lookup_result(
        source,
        result,
        _context(),
        "tiktok",
        target_tool_name="tiktok_smart_plus_create_ad",
        target_field="image_web_uris",
    )

    assert decorated.data["parameter_selections"][0]["options"] == [{
        "value": "ad-site-i18n-sg/stable-image",
        "label": "cover.jpg",
        "selection_token": "selection-token",
    }]
    assert signer.issued[0]["value"] == "ad-site-i18n-sg/stable-image"


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
