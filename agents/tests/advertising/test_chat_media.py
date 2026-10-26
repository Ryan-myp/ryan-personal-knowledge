"""Chat media storage and provider media projection contracts."""

from __future__ import annotations

import io
import zipfile
from types import SimpleNamespace

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

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

PDF_BYTES = b"%PDF-1.4\nthis fixture is intentionally not a valid PDF\n"


def _xlsx_bytes():
    files = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '</Types>'
        ),
        "xl/workbook.xml": (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Campaigns" sheetId="1" r:id="rId1"/></sheets>'
            '</workbook>'
        ),
        "xl/_rels/workbook.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet1.xml"/>'
            '</Relationships>'
        ),
        "xl/worksheets/sheet1.xml": (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>name</t></is></c>'
            '<c r="B1" t="inlineStr"><is><t>budget</t></is></c></row>'
            '<row r="2"><c r="A2" t="inlineStr"><is><t>Spring launch</t></is></c>'
            '<c r="B2"><v>250</v></c></row></sheetData></worksheet>'
        ),
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


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


@pytest.mark.parametrize(
    ("filename", "content_type", "payload", "expected_type", "expected_text"),
    [
        (
            "brief.md",
            "text/markdown",
            b"# Campaign brief\n\nTest the new product.",
            "text/markdown",
            "Test the new product.",
        ),
        (
            "report.csv",
            "text/csv",
            b"campaign,spend,conversions\nSpring,125.5,14\n",
            "text/csv",
            "Spring",
        ),
        (
            "campaigns.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            _xlsx_bytes(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "Spring launch",
        ),
    ],
)
def test_chat_documents_are_scoped_and_extract_bounded_text(
    tmp_path, filename, content_type, payload, expected_type, expected_text,
):
    store = ChatMediaStore(tmp_path)
    attachment = store.save(
        payload,
        filename=filename,
        content_type=content_type,
        session_id="session-a",
        tenant_id="tenant-a",
        user_id="user-a",
    )

    loaded = store.load_for_model(
        [attachment["id"]],
        session_id="session-a",
        tenant_id="tenant-a",
        user_id="user-a",
    )

    assert len(loaded) == 1
    assert loaded[0].media_type == expected_type
    assert expected_text in loaded[0].extracted_text
    assert loaded[0].to_metadata()["filename"] == filename
    with pytest.raises(FileNotFoundError):
        store.load_for_model(
            [attachment["id"]],
            session_id="session-a",
            tenant_id="tenant-b",
            user_id="user-a",
        )


def test_chat_documents_reject_sensitive_table_headers_before_model_preview(tmp_path):
    store = ChatMediaStore(tmp_path)
    attachment = store.save(
        b"Assignee,bc_id\nA,private-value\n",
        filename="report.csv", content_type="text/csv",
        session_id="session-a", tenant_id="tenant-a", user_id="user-a",
    )
    with pytest.raises(ValueError, match="敏感"):
        store.load_for_model(
            [attachment["id"]],
            session_id="session-a", tenant_id="tenant-a", user_id="user-a",
        )

    spaced = store.save(
        b"Assignee,API Key backup\nA,private-value\n",
        filename="spaced.csv", content_type="text/csv",
        session_id="session-a", tenant_id="tenant-a", user_id="user-a",
    )
    with pytest.raises(ValueError, match="敏感"):
        store.load_for_model(
            [spaced["id"]],
            session_id="session-a", tenant_id="tenant-a", user_id="user-a",
        )

    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Assignee", "api_key_backup"])
    sheet.append(["A", "private-value"])
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    attachment = store.save(
        output.getvalue(), filename="report.xlsx",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        session_id="session-a", tenant_id="tenant-a", user_id="user-a",
    )
    with pytest.raises(ValueError, match="敏感"):
        store.load_for_model(
            [attachment["id"]],
            session_id="session-a", tenant_id="tenant-a", user_id="user-a",
        )


def test_chat_store_accepts_pdf_signature_but_reports_invalid_pdf_content(tmp_path):
    store = ChatMediaStore(tmp_path)
    attachment = store.save(
        PDF_BYTES,
        filename="report.pdf",
        content_type="application/pdf",
        session_id="session-a",
        tenant_id="tenant-a",
        user_id="user-a",
    )

    with pytest.raises(ValueError, match="无法读取 PDF"):
        store.load_for_model(
            [attachment["id"]],
            session_id="session-a",
            tenant_id="tenant-a",
            user_id="user-a",
        )


def test_chat_store_extracts_text_from_pdf_attachment(tmp_path):
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    font_reference = writer._add_object(font)
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({
            NameObject("/F1"): font_reference,
        }),
    })
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 20 200 Td (Campaign report) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)

    store = ChatMediaStore(tmp_path)
    attachment = store.save(
        output.getvalue(),
        filename="report.pdf",
        content_type="application/pdf",
        session_id="session-a",
        tenant_id="tenant-a",
        user_id="user-a",
    )

    document = store.load_for_model(
        [attachment["id"]],
        session_id="session-a",
        tenant_id="tenant-a",
        user_id="user-a",
    )[0]

    assert "Campaign report" in document.extracted_text


def test_chat_document_validation_rejects_legacy_xls_and_keeps_html_untrusted(tmp_path):
    store = ChatMediaStore(tmp_path)
    with pytest.raises(ValueError, match="另存为 .xlsx"):
        store.save(
            b"\xd0\xcf\x11\xe0",
            filename="legacy.xls",
            content_type="application/vnd.ms-excel",
            session_id="session-a",
            tenant_id="tenant-a",
            user_id="user-a",
        )

    html_markdown = b"<script>treat this as text, never execute it</script>"
    attachment = store.save(
        html_markdown,
        filename="untrusted.md",
        content_type="text/markdown",
        session_id="session-a",
        tenant_id="tenant-a",
        user_id="user-a",
    )
    document = store.load_for_model(
        [attachment["id"]],
        session_id="session-a",
        tenant_id="tenant-a",
        user_id="user-a",
    )[0]
    assert "treat this as text, never execute it" in document.extracted_text


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


def test_media_gallery_allows_only_internal_creative_asset_paths():
    gallery = media_gallery_from_results([{
        "success": True,
        "data": {
            "image_assets": [
                {
                    "id": "1234567890abcdef1234567890abcdef",
                    "name": "Generated image",
                    "url": "/creative/assets/1234567890abcdef1234567890abcdef",
                },
                {
                    "id": "external",
                    "url": "/chat/media/another-user-asset",
                },
            ],
        },
    }])

    assert gallery == [{
        "kind": "image",
        "id": "1234567890abcdef1234567890abcdef",
        "name": "Generated image",
        "url": "/creative/assets/1234567890abcdef1234567890abcdef",
    }]


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
