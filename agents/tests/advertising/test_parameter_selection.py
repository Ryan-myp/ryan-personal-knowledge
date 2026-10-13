from types import SimpleNamespace

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
