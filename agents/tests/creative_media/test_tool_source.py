from __future__ import annotations

from types import SimpleNamespace

from agents.agent_harness.core.interfaces import ToolContext, ToolEffect
from agents.agent_harness.core.tool_selection import ToolSelector
from agents.tools.creative_media.source import (
    _generation_error_message,
    creative_media_tool_source,
)


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def test_video_queue_full_error_is_explained_as_an_upstream_capacity_limit():
    message = _generation_error_message("media_provider_video_queue_full")

    assert "video_queue_full" in message
    assert "上游容量限制" in message
    assert "API Key" not in message


class FakeAssetStore:
    def __init__(self):
        self.assets = {}
        self.last_include_content = None

    def put(self, content, *, filename, media_type, tenant_id, user_id, metadata):
        asset_id = "11111111111141118111111111111111"
        self.assets[asset_id] = {
            "content": content,
            "filename": filename,
            "media_type": media_type,
            "tenant_id": tenant_id,
            "user_id": user_id,
            **metadata,
        }
        return {"asset_id": asset_id, **self.assets[asset_id]}

    def create_pending(
        self, *, filename, media_type, tenant_id, user_id, metadata,
    ):
        asset_id = "22222222222242228222222222222222"
        self.assets[asset_id] = {
            "content": None,
            "filename": filename,
            "media_type": media_type,
            "tenant_id": tenant_id,
            "user_id": user_id,
            **metadata,
        }
        return {"asset_id": asset_id, **self.assets[asset_id]}

    def get(self, asset_id, *, tenant_id, user_id, include_content=True):
        self.last_include_content = include_content
        item = self.assets[asset_id]
        if (item["tenant_id"], item["user_id"]) != (tenant_id, user_id):
            raise FileNotFoundError
        return SimpleNamespace(
            content=item["content"],
            metadata={"asset_id": asset_id, **item},
        )

    def complete(
        self, asset_id, content, *, tenant_id, user_id, metadata,
    ):
        item = self.assets[asset_id]
        if (item["tenant_id"], item["user_id"]) != (tenant_id, user_id):
            raise FileNotFoundError
        item["content"] = content
        item.update(metadata)
        return {"asset_id": asset_id, **item}

    def update(self, asset_id, *, tenant_id, user_id, metadata):
        item = self.assets[asset_id]
        if (item["tenant_id"], item["user_id"]) != (tenant_id, user_id):
            raise FileNotFoundError
        item.update(metadata)
        return {"asset_id": asset_id, **item}

    def list(self, *, tenant_id, user_id, limit=20):
        return [
            {"asset_id": asset_id, **item}
            for asset_id, item in self.assets.items()
            if item["tenant_id"] == tenant_id and item["user_id"] == user_id
        ][:limit]


class FakeMediaClient:
    def __init__(self, _configuration):
        pass

    def generate_image(self, prompt, size, aspect_ratio):
        assert prompt == "A product hero with verifiable packaging"
        assert size == "2K"
        assert aspect_ratio == "1:1"
        return [{"content": PNG_BYTES, "media_type": "image/png"}]

    def submit_video(
        self, prompt, *, aspect_ratio, duration_seconds, resolution,
    ):
        assert aspect_ratio == "16:9"
        assert duration_seconds == 5
        assert resolution == "720P"
        return {
            "video_id": "provider-job-1",
            "status": "processing",
            "model": "video-model",
        }

    def poll_video(self, video_id):
        assert video_id == "provider-job-1"
        return {
            "status": "completed",
            "content": b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 16,
            "media_type": "video/mp4",
        }


def _source():
    store = FakeAssetStore()
    source = creative_media_tool_source(
        configuration_provider=lambda _purpose: {
            "model": "media-model",
            "model_profile_id": "profile-1",
            "base_url": "https://media.example/v1",
            "api_key": "private",
        },
        asset_store=store,
        client_factory=FakeMediaClient,
    )
    return source, store


def _context(user_id="user-a", tenant_id="tenant-a"):
    return ToolContext(
        session_id="session-1",
        user_id=user_id,
        metadata={"principal_tenant_id": tenant_id},
    )


def test_creative_source_registers_governed_tools_and_generates_scoped_image():
    source, store = _source()
    bindings = {item.definition.name: item for item in source.list_bindings()}

    assert {
        "creative_generate_image",
        "creative_submit_video",
        "creative_check_video",
        "creative_list_assets",
    } <= set(bindings)
    assert bindings["creative_generate_image"].definition.effect_class == (
        ToolEffect.INTERNAL_WRITE
    )
    assert bindings["creative_generate_image"].definition.required_permissions == [
        "creative.generate",
    ]
    assert bindings["creative_generate_image"].definition.timeout_seconds == 500
    assert bindings["creative_submit_video"].definition.timeout_seconds == 500
    assert bindings["creative_check_video"].definition.timeout_seconds == 500
    assert bindings["creative_list_assets"].definition.timeout_seconds == 15

    result = bindings["creative_generate_image"].executor.execute(
        _context(),
        {"prompt": "A product hero with verifiable packaging"},
    )

    assert result.success
    assert result.data["image_assets"][0]["url"] == (
        "/creative/assets/11111111111141118111111111111111"
    )
    assert store.assets["11111111111141118111111111111111"]["tenant_id"] == "tenant-a"
    assert store.assets["11111111111141118111111111111111"]["user_id"] == "user-a"
    assert store.assets["11111111111141118111111111111111"]["content"] == PNG_BYTES


def test_plain_image_generation_request_selects_image_tool_not_upload_guidance():
    source, _store = _source()
    definitions = [
        binding.definition for binding in source.list_bindings()
    ]
    selector = ToolSelector()

    selected = selector.select_relevant(
        "帮我生成一个苹果手机图片",
        definitions,
    )

    assert [tool.name for tool in selected] == ["creative_generate_image"]
    assert selector.requires_tool_call(
        "帮我生成一个苹果手机图片",
        selected,
    )


def test_plain_video_generation_request_selects_video_generation_tool():
    source, _store = _source()
    definitions = [
        binding.definition for binding in source.list_bindings()
    ]
    selector = ToolSelector()
    request = "帮我生成一个苹果手机视频"

    selected = selector.select_relevant(request, definitions)

    assert [tool.name for tool in selected] == ["creative_submit_video"]
    assert selector.requires_tool_call(request, selected)


def test_video_tool_persists_job_then_completes_it_on_status_check():
    source, store = _source()
    bindings = {item.definition.name: item for item in source.list_bindings()}

    submitted = bindings["creative_submit_video"].executor.execute(
        _context(),
        {"prompt": "A short product demonstration"},
    )
    checked = bindings["creative_check_video"].executor.execute(
        _context(),
        {"asset_id": submitted.data["asset_id"]},
    )

    assert submitted.success
    assert submitted.data["status"] == "processing"
    assert checked.success
    assert checked.data["status"] == "ready"
    assert checked.data["video_assets"][0]["url"] == (
        f"/creative/assets/{submitted.data['asset_id']}"
    )
    assert store.assets[submitted.data["asset_id"]]["content"].startswith(
        b"\x00\x00\x00\x18ftyp",
    )
    assert store.last_include_content is False


def test_creative_tool_requires_trusted_identity_and_never_accepts_scope_input():
    source, _store = _source()
    generate = next(
        binding.executor
        for binding in source.list_bindings()
        if binding.definition.name == "creative_generate_image"
    )
    untrusted = ToolContext(
        session_id="session-1",
        user_id="user-a",
        metadata={},
    )

    result = generate.execute(
        untrusted,
        {"prompt": "Generate an image", "tenant_id": "attacker-tenant"},
    )

    assert not result.success
    assert "可信" in result.error


def test_creative_source_never_returns_or_persists_provider_api_key():
    source, store = _source()
    bindings = {item.definition.name: item for item in source.list_bindings()}

    result = bindings["creative_generate_image"].executor.execute(
        _context(),
        {"prompt": "A product hero with verifiable packaging"},
    )

    assert "private" not in repr(result.data)
    assert "api_key" not in repr(
        store.assets["11111111111141118111111111111111"],
    )


def test_generation_returns_a_safe_error_for_invalid_prompt():
    source, _store = _source()
    generate = next(
        binding.executor
        for binding in source.list_bindings()
        if binding.definition.name == "creative_generate_image"
    )

    result = generate.execute(_context(), {"prompt": ""})

    assert not result.success
    assert "提示词" in result.error


def test_missing_image_model_configuration_explains_the_next_step():
    source = creative_media_tool_source(
        configuration_provider=lambda _purpose: {},
        asset_store=FakeAssetStore(),
    )
    generate = next(
        binding.executor
        for binding in source.list_bindings()
        if binding.definition.name == "creative_generate_image"
    )

    result = generate.execute(
        _context(),
        {"prompt": "A minimal abstract product hero"},
    )

    assert not result.success
    assert "Agnes Image 2.5 Flash" in result.error
    assert "Agnes API Key" in result.error


def test_creative_skill_is_context_only_and_documents_provider_boundaries():
    from pathlib import Path

    from agents.agent_harness.skills import MarkdownSkillSource

    skill_path = (
        Path(__file__).resolve().parents[2]
        / "skills"
        / "advertising"
        / "practices"
        / "creative-production"
    )
    binding = MarkdownSkillSource.from_directory(skill_path).list_skills()[0]

    assert binding.name == "creative-production"
    assert (
        "不能将本地 MP4 描述为已上传"
        in binding.reference_documents["references/production-workflow.md"]
    )
