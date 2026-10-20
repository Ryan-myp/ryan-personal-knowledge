from __future__ import annotations

import pytest

from agents.agent_platform.infrastructure.durable.filesystem_asset_store import (
    FilesystemCreativeAssetStore,
)


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def test_asset_store_persists_content_and_metadata_by_principal(tmp_path):
    store = FilesystemCreativeAssetStore(tmp_path)

    saved = store.put(
        PNG_BYTES,
        filename="campaign.png",
        media_type="image/png",
        tenant_id="tenant-a",
        user_id="user-a",
        metadata={"kind": "image", "status": "ready", "prompt": "Product hero"},
    )

    loaded = store.get(
        saved["asset_id"], tenant_id="tenant-a", user_id="user-a",
    )

    assert loaded.metadata["filename"] == "campaign.png"
    assert loaded.metadata["sha256"]
    assert loaded.content == PNG_BYTES
    assert loaded.path.is_file()
    assert store.list(tenant_id="tenant-a", user_id="user-a")[0]["asset_id"] == (
        saved["asset_id"]
    )


def test_asset_store_hides_assets_from_other_users_and_tenants(tmp_path):
    store = FilesystemCreativeAssetStore(tmp_path)
    saved = store.put(
        PNG_BYTES,
        filename="campaign.png",
        media_type="image/png",
        tenant_id="tenant-a",
        user_id="user-a",
        metadata={"kind": "image"},
    )

    with pytest.raises(FileNotFoundError):
        store.get(saved["asset_id"], tenant_id="tenant-b", user_id="user-a")
    with pytest.raises(FileNotFoundError):
        store.get(saved["asset_id"], tenant_id="tenant-a", user_id="user-b")


def test_asset_store_rejects_invalid_signature_and_oversized_content(tmp_path):
    store = FilesystemCreativeAssetStore(tmp_path, max_image_bytes=16)

    with pytest.raises(ValueError, match="match"):
        store.put(
            b"not an image",
            filename="campaign.png",
            media_type="image/png",
            tenant_id="tenant-a",
            user_id="user-a",
            metadata={"kind": "image"},
        )

    with pytest.raises(ValueError, match="size"):
        store.put(
            PNG_BYTES,
            filename="campaign.png",
            media_type="image/png",
            tenant_id="tenant-a",
            user_id="user-a",
            metadata={"kind": "image"},
        )


def test_asset_store_metadata_updates_are_scoped_and_do_not_replace_content(tmp_path):
    store = FilesystemCreativeAssetStore(tmp_path)
    saved = store.put(
        PNG_BYTES,
        filename="campaign.png",
        media_type="image/png",
        tenant_id="tenant-a",
        user_id="user-a",
        metadata={"kind": "image", "status": "processing"},
    )

    updated = store.update(
        saved["asset_id"],
        tenant_id="tenant-a",
        user_id="user-a",
        metadata={"status": "ready", "platform_assets": {"meta": "hash-1"}},
    )
    loaded = store.get(
        saved["asset_id"], tenant_id="tenant-a", user_id="user-a",
    )

    assert updated["status"] == "ready"
    assert loaded.content == PNG_BYTES
    assert loaded.metadata["platform_assets"] == {"meta": "hash-1"}


def test_asset_store_persists_video_jobs_before_provider_completion(tmp_path):
    store = FilesystemCreativeAssetStore(tmp_path)

    pending = store.create_pending(
        filename="video.mp4",
        media_type="video/mp4",
        tenant_id="tenant-a",
        user_id="user-a",
        metadata={
            "kind": "video",
            "status": "processing",
            "model": "agnes-video-model",
            "provider_job_id": "job-1",
        },
    )

    loaded = store.get(
        pending["asset_id"], tenant_id="tenant-a", user_id="user-a",
    )
    assert loaded.content is None
    assert loaded.metadata["status"] == "processing"


def test_asset_store_completes_video_job_and_rejects_unsafe_metadata(tmp_path):
    store = FilesystemCreativeAssetStore(tmp_path)
    pending = store.create_pending(
        filename="video.mp4",
        media_type="video/mp4",
        tenant_id="tenant-a",
        user_id="user-a",
        metadata={"kind": "video", "status": "processing"},
    )
    video_bytes = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 16

    completed = store.complete(
        pending["asset_id"],
        video_bytes,
        tenant_id="tenant-a",
        user_id="user-a",
        metadata={"status": "ready"},
    )

    assert completed["status"] == "ready"
    assert store.get(
        pending["asset_id"], tenant_id="tenant-a", user_id="user-a",
    ).content == video_bytes
    with pytest.raises(ValueError, match="metadata"):
        store.update(
            pending["asset_id"],
            tenant_id="tenant-a",
            user_id="user-a",
            metadata={"api_key": "must-not-be-stored"},
        )
