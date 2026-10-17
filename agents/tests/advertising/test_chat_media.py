"""Chat media storage and provider media projection contracts."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.applications.advertising.run.ad_run_media import (
    media_gallery_from_results,
)
from agents.applications.advertising.run.ad_run_service import AdvertisingRunService
from agents.deployments.advertising.api.chat_media import (
    ChatMediaStore,
    StoredChatMedia,
)
from agents.tools.advertising.shared.domain.conversation import (
    project_conversation_messages,
)


PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
)


def test_chat_media_store_round_trips_within_tenant_user_and_session(tmp_path):
    store = ChatMediaStore(tmp_path)
    attachment = store.save(
        PNG_BYTES,
        filename="product.png",
        content_type="image/png",
        session_id="session-a",
        tenant_id="tenant-a",
        user_id="user-a",
    )

    loaded = store.load(
        attachment["id"],
        session_id="session-a",
        tenant_id="tenant-a",
        user_id="user-a",
    )

    assert loaded.content == PNG_BYTES
    assert loaded.metadata == attachment
    with pytest.raises(FileNotFoundError):
        store.load(
            attachment["id"],
            session_id="session-b",
            tenant_id="tenant-a",
            user_id="user-a",
        )
    with pytest.raises(FileNotFoundError):
        store.load(
            attachment["id"],
            session_id="session-a",
            tenant_id="tenant-a",
            user_id="user-b",
        )


@pytest.mark.parametrize(
    ("content_type", "payload"),
    [
        ("image/png", b"not an image"),
        ("image/jpeg", PNG_BYTES),
        ("text/html", b"<html>unsafe</html>"),
    ],
)
def test_chat_media_store_rejects_mime_spoofing(tmp_path, content_type, payload):
    store = ChatMediaStore(tmp_path)

    with pytest.raises(ValueError):
        store.save(
            payload,
            filename="upload.bin",
            content_type=content_type,
            session_id="session-a",
            tenant_id="tenant-a",
            user_id="user-a",
        )


def test_chat_media_store_enforces_media_size_limits(tmp_path):
    store = ChatMediaStore(tmp_path, max_image_bytes=len(PNG_BYTES) - 1)

    with pytest.raises(ValueError, match="size limit"):
        store.save(
            PNG_BYTES,
            filename="too-large.png",
            content_type="image/png",
            session_id="session-a",
            tenant_id="tenant-a",
            user_id="user-a",
        )


def test_chat_media_store_enforces_session_quota_and_supports_scoped_delete(tmp_path):
    store = ChatMediaStore(
        tmp_path,
        max_session_bytes=(len(PNG_BYTES) * 2) - 1,
    )
    attachment = store.save(
        PNG_BYTES,
        filename="first.png",
        content_type="image/png",
        session_id="session-a",
        tenant_id="tenant-a",
        user_id="user-a",
    )

    with pytest.raises(ValueError, match="storage limit"):
        store.save(
            PNG_BYTES,
            filename="second.png",
            content_type="image/png",
            session_id="session-a",
            tenant_id="tenant-a",
            user_id="user-a",
        )

    assert store.delete(
        attachment["id"],
        session_id="session-a",
        tenant_id="tenant-a",
        user_id="user-a",
    )
    with pytest.raises(FileNotFoundError):
        store.load(
            attachment["id"],
            session_id="session-a",
            tenant_id="tenant-a",
            user_id="user-a",
        )


def test_combined_upload_limit_is_checked_before_loading_media_bytes(
    tmp_path, monkeypatch,
):
    store = ChatMediaStore(tmp_path)
    attachment = store.save(
        PNG_BYTES,
        filename="image.png",
        content_type="image/png",
        session_id="session-a",
        tenant_id="tenant-a",
        user_id="user-a",
    )
    monkeypatch.setattr(
        "agents.deployments.advertising.api.chat_media._MAX_TURN_BYTES",
        len(PNG_BYTES) - 1,
    )
    monkeypatch.setattr(
        StoredChatMedia,
        "to_input_media",
        lambda _self: pytest.fail("oversized input should fail before loading bytes"),
    )

    with pytest.raises(ValueError, match="combined chat attachments"):
        store.load_for_model(
            [attachment["id"]],
            session_id="session-a",
            tenant_id="tenant-a",
            user_id="user-a",
        )


def test_provider_media_gallery_keeps_safe_image_and_video_previews():
    gallery = media_gallery_from_results([
        {
            "success": True,
            "resource_type": "image_asset",
            "data": {
                "image_assets": [{
                    "id": "image-1",
                    "name": "Summer",
                    "original_width": 800,
                    "original_height": 800,
                    "url": "https://scontent.example.test/image.jpg",
                }, {
                    "id": "image-unsafe",
                    "url": "javascript:alert(1)",
                }],
            },
        },
        {
            "success": True,
            "resource_type": "video_asset",
            "data": {
                "video_assets": [{
                    "video_id": "video-1",
                    "file_name": "Story",
                    "preview_url": "https://cdn.example.test/preview.mp4?sig=one",
                    "video_cover_url": "https://cdn.example.test/cover.jpg",
                    "preview_url_expire_time": "2026-10-17T12:00:00Z",
                }],
            },
        },
    ])

    assert gallery == [
        {
            "kind": "image",
            "id": "image-1",
            "name": "Summer",
            "url": "https://scontent.example.test/image.jpg",
            "width": 800,
            "height": 800,
        },
        {
            "kind": "video",
            "id": "video-1",
            "name": "Story",
            "url": "https://cdn.example.test/preview.mp4?sig=one",
            "poster": "https://cdn.example.test/cover.jpg",
            "expires_at": "2026-10-17T12:00:00Z",
        },
    ]


def test_provider_video_gallery_uses_media_source_not_permalink():
    gallery = media_gallery_from_results([{
        "success": True,
        "resource_type": "video_asset",
        "data": {
            "video_assets": [{
                "id": "video-1",
                "title": "Demo video",
                "source": "https://video.example/demo.mp4?signature=short-lived",
                "picture": "https://video.example/demo.jpg",
                    "permalink_url": "https://www.facebook.com/watch/?v=1",
            }, {
                "id": "video-2",
                "title": "No source permission",
                "picture": "https://video.example/locked.jpg",
                    "permalink_url": "https://www.facebook.com/watch/?v=2",
            }],
        },
    }])

    assert gallery == [
        {
            "kind": "video",
            "id": "video-1",
            "name": "Demo video",
            "url": "https://video.example/demo.mp4?signature=short-lived",
            "poster": "https://video.example/demo.jpg",
            "permalink_url": "https://www.facebook.com/watch/?v=1",
        },
        {
            "kind": "video",
            "id": "video-2",
            "name": "No source permission",
            "poster": "https://video.example/locked.jpg",
            "permalink_url": "https://www.facebook.com/watch/?v=2",
        },
    ]


def test_provider_video_gallery_normalizes_relative_facebook_permalink():
    gallery = media_gallery_from_results([{
        "success": True,
        "resource_type": "video_asset",
        "data": {
            "video_assets": [{
                "id": "3521725561330657",
                "title": "id_10492203795_2_1920x1080_25s.mp4",
                "permalink_url": (
                    "/23845088583740250/videos/3521725561330657/"
                    "?idorvanity=23845088583740250"
                ),
            }],
        },
    }])

    assert gallery == [{
        "kind": "video",
        "id": "3521725561330657",
        "name": "id_10492203795_2_1920x1080_25s.mp4",
        "permalink_url": (
            "https://www.facebook.com/23845088583740250/videos/"
            "3521725561330657/"
        ),
    }]


def test_provider_video_gallery_rejects_untrusted_or_non_video_facebook_urls():
    gallery = media_gallery_from_results([{
        "success": True,
        "resource_type": "video_asset",
        "data": {
            "video_assets": [
                {
                    "id": "bad-host",
                    "permalink_url": (
                        "https://www.facebook.com.attacker.test/1/videos/2/"
                    ),
                },
                {
                    "id": "settings",
                    "permalink_url": "https://www.facebook.com/advertiser/settings/",
                },
                {
                    "id": "bad-protocol",
                    "permalink_url": "http://www.facebook.com/1/videos/2/",
                },
            ],
        },
    }])

    assert gallery == []


def test_provider_media_gallery_is_bounded_and_rejects_private_or_credential_urls():
    rows = [
        {"id": str(index), "url": f"https://cdn.example.test/{index}.jpg"}
        for index in range(20)
    ]
    rows.extend([
        {"id": "private", "url": "https://127.0.0.1/image.jpg"},
        {"id": "credential", "url": "https://user:pass@cdn.example.test/image.jpg"},
    ])

    gallery = media_gallery_from_results([{
        "success": True,
        "resource_type": "image_asset",
        "data": {"image_assets": rows},
    }])

    assert len(gallery) == 12
    assert all(item["id"] != "private" for item in gallery)
    assert all(item["id"] != "credential" for item in gallery)


def test_queried_image_url_reaches_chat_gallery_and_durable_history():
    image = {
        "hash": "image-hash",
        "name": "Summer creative",
        "original_width": 800,
        "original_height": 800,
        "url": "https://scontent.example.test/summer.jpg?sig=preview",
        "url_128": "https://scontent.example.test/summer-128.jpg?sig=preview",
    }

    class Registry:
        @staticmethod
        def get(_name):
            return SimpleNamespace(
                namespace="meta",
                action="list",
                resource_type="image_asset",
                intent_types=("list_image_assets",),
            ), None

    class PlatformApplication:
        @staticmethod
        def run(_request):
            return {
                "run_id": "run-1",
                "turn_id": "turn-1",
                "status": "succeeded",
                "reply": "找到 1 张图片。",
                "tool_results": [{
                    "name": "meta_list_image_assets",
                    "content": {
                        "success": True,
                        "data": {"image_assets": [image]},
                    },
                    "data": {"image_assets": [image]},
                    "is_error": False,
                }],
            }

    persisted = {}
    runtime = SimpleNamespace(
        platform_application=PlatformApplication(),
        registry=Registry(),
        execution_mode="dry_run",
        _sessions={},
        _memory_manager=None,
        sessions={"session-1": object()},
        session_manager=None,
        redact_for_persistence=lambda value: value,
        persistence_services=SimpleNamespace(
            persist_conversation_turn=lambda *_args, **kwargs: persisted.update(
                ui=kwargs["ui"],
            ),
        ),
    )

    result = AdvertisingRunService(runtime).run(
        "查询图片素材",
        session_id="session-1",
        user_id="user-1",
        tenant_id="tenant-1",
    )

    expected_gallery = [{
        "kind": "image",
        "id": "image-hash",
        "name": "Summer creative",
        "url": image["url"],
        "width": 800,
        "height": 800,
    }]
    assert result["ui"]["media_gallery"] == expected_gallery
    assert persisted["ui"]["media_gallery"] == expected_gallery

    history = project_conversation_messages([
        {
            "role": "user",
            "content": "查询图片素材",
            "turn_id": "turn-1",
            "metadata": {},
        },
        {
            "role": "assistant",
            "content": result["reply"],
            "turn_id": "turn-1",
            "metadata": {"ui": persisted["ui"]},
        },
    ])
    assert history[-1]["ui"]["media_gallery"] == expected_gallery


def test_advertising_agent_prompt_does_not_claim_supported_video_links_cannot_embed():
    from agents.scenarios.advertising import advertising_agent_profile

    guidance = advertising_agent_profile().response_guidance

    assert "Facebook 视频链接" in guidance
    assert "不得声称界面不支持播放器" in guidance
