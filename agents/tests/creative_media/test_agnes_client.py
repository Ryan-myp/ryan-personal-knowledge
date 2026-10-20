from __future__ import annotations

import base64
import json

import pytest
import requests

from agents.tools.creative_media import agnes_client
from agents.tools.creative_media.agnes_client import (
    AgnesMediaClient,
    MediaProviderError,
)


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code
        self.content = json.dumps(payload).encode()
        self.headers = {"content-length": str(len(self.content))}
        self.closed = False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(
                "provider request failed",
                response=self,
            )

    def json(self):
        return self.payload

    def iter_content(self, chunk_size):
        for offset in range(0, len(self.content), chunk_size):
            yield self.content[offset:offset + chunk_size]

    def close(self):
        self.closed = True


def test_image_generation_uses_agnes_image_25_contract():
    image = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    calls = []

    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return FakeResponse({
            "data": [{
                "b64_json": base64.b64encode(image).decode("ascii"),
                "mime_type": "image/png",
            }],
        })

    client = AgnesMediaClient(
        {
            "model": "agnes-image-2.5-flash",
            "base_url": "https://apihub.agnes-ai.com/v1",
            "api_key": "test-key",
        },
        request=request,
    )

    result = client.generate_image(
        "Premium product hero",
        size="2K",
        aspect_ratio="1:1",
    )

    assert result == [{"content": image, "media_type": "image/png"}]
    method, url, kwargs = calls[0]
    assert method == "POST"
    assert url == "https://apihub.agnes-ai.com/v1/images/generations"
    assert kwargs["json"] == {
        "model": "agnes-image-2.5-flash",
        "prompt": "Premium product hero",
        "size": "2K",
        "ratio": "1:1",
        "response_format": "b64_json",
        "n": 1,
    }
    assert kwargs["headers"]["Authorization"] == "Bearer test-key"
    assert kwargs["stream"] is True
    assert kwargs["timeout"] == 500.0


def test_video_generation_uses_agnes_video_25_contract_and_polls_by_video_id():
    calls = []

    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if method == "POST":
            return FakeResponse({"video_id": "video-123", "status": "processing"})
        return FakeResponse({
            "status": "completed",
            "video_url": "https://apihub.agnes-ai.com/output/video.mp4",
        })

    downloads = []

    def download(url, *, max_bytes):
        downloads.append((url, max_bytes))
        return b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 16

    client = AgnesMediaClient(
        {
            "model": "agnes-video-2.5-flash",
            "base_url": "https://apihub.agnes-ai.com/v1",
            "api_key": "test-key",
        },
        request=request,
        download=download,
    )

    submitted = client.submit_video(
        "Short product video",
        aspect_ratio="16:9",
        duration_seconds=5,
        resolution="720P",
    )
    completed = client.poll_video(submitted["video_id"])

    assert submitted["status"] == "processing"
    assert completed["status"] == "completed"
    assert completed["content"].startswith(b"\x00\x00\x00\x18ftyp")
    assert calls[1][1] == "https://apihub.agnes-ai.com/agnesapi"
    assert calls[1][2]["params"] == {
        "video_id": "video-123",
        "model_name": "agnes-video-2.5-flash",
    }
    assert calls[0][2]["json"] == {
        "model": "agnes-video-2.5-flash",
        "prompt": "Short product video",
        "mode": "text",
        "seconds": "5",
        "size": "720P",
        "aspect_ratio": "16:9",
        "n": 1,
    }
    assert downloads[0][0] == "https://apihub.agnes-ai.com/output/video.mp4"


def test_video_result_rejects_non_global_or_non_https_urls():
    client = AgnesMediaClient(
        {
            "model": "agnes-video-2.5-flash",
            "base_url": "https://apihub.agnes-ai.com/v1",
            "api_key": "test-key",
        },
        request=lambda *_args, **_kwargs: FakeResponse({
            "status": "completed",
            "video_url": "http://127.0.0.1/private.mp4",
        }),
        download=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("unsafe URLs must not be fetched")
        ),
    )

    result = client.poll_video("video-123")

    assert result["status"] == "failed"
    assert result["error"] == "video_result_url_unsafe"


def test_video_result_accepts_the_configured_agnes_output_cdn():
    downloads = []
    video_bytes = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 16
    client = AgnesMediaClient(
        {
            "model": "agnes-video-2.5-flash",
            "base_url": "https://apihub.agnes-ai.com/v1",
            "api_key": "test-key",
        },
        request=lambda *_args, **_kwargs: FakeResponse({
            "status": "completed",
            "video_url": (
                "https://platform-outputs.agnes-ai.space/videos/output.mp4"
            ),
        }),
        download=lambda url, **_kwargs: (
            downloads.append(url) or video_bytes
        ),
    )

    result = client.poll_video("video-123")

    assert result["status"] == "completed"
    assert result["content"] == video_bytes
    assert downloads == [
        "https://platform-outputs.agnes-ai.space/videos/output.mp4",
    ]


def test_video_result_rejects_unlisted_public_hosts():
    client = AgnesMediaClient(
        {
            "model": "agnes-video-2.5-flash",
            "base_url": "https://apihub.agnes-ai.com/v1",
            "api_key": "test-key",
        },
        request=lambda *_args, **_kwargs: FakeResponse({
            "status": "completed",
            "video_url": "https://media.example.com/output.mp4",
        }),
        download=lambda *_args, **_kwargs: pytest.fail(
            "unlisted hosts must not be fetched"
        ),
    )

    result = client.poll_video("video-123")

    assert result == {
        "status": "failed",
        "error": "video_result_url_unsafe",
    }


def test_image_generation_rejects_malformed_base64_and_non_image_mime():
    import pytest

    client = AgnesMediaClient(
        {
            "model": "image-model",
            "base_url": "https://apihub.agnes-ai.com/v1",
            "api_key": "test-key",
        },
        request=lambda *_args, **_kwargs: FakeResponse({
            "data": [{"b64_json": "not-base64", "mime_type": "image/png"}],
        }),
    )

    with pytest.raises(ValueError):
        client.generate_image("Product hero", size="1K", aspect_ratio="1:1")

    client = AgnesMediaClient(
        {
            "model": "image-model",
            "base_url": "https://apihub.agnes-ai.com/v1",
            "api_key": "test-key",
        },
        request=lambda *_args, **_kwargs: FakeResponse({
            "data": [{
                "b64_json": base64.b64encode(b"<html>").decode("ascii"),
                "mime_type": "text/html",
            }],
        }),
    )

    with pytest.raises(ValueError):
        client.generate_image("Product hero", size="1K", aspect_ratio="1:1")


def test_video_generation_rejects_oversized_downloads():
    client = AgnesMediaClient(
        {
            "model": "agnes-video-2.5-flash",
            "base_url": "https://apihub.agnes-ai.com/v1",
            "api_key": "test-key",
        },
        request=lambda *_args, **_kwargs: FakeResponse({
            "status": "completed",
            "video_url": "https://apihub.agnes-ai.com/output/video.mp4",
        }),
        download=lambda *_args, **_kwargs: b"x" * 17,
        max_video_bytes=16,
    )

    result = client.poll_video("video-123")

    assert result == {
        "status": "failed",
        "error": "video_result_too_large",
    }


def test_generation_rejects_unsupported_models_and_invalid_video_parameters():
    client = AgnesMediaClient(
        {
            "model": "unrecognized-image-model",
            "base_url": "https://apihub.agnes-ai.com/v1",
            "api_key": "test-key",
        },
        request=lambda *_args, **_kwargs: pytest.fail(
            "unsupported model must fail before network access"
        ),
    )
    with pytest.raises(ValueError, match="free Agnes"):
        client.generate_image("Product hero", size="1K", aspect_ratio="1:1")

    client = AgnesMediaClient(
        {
            "model": "agnes-video-2.5-flash",
            "base_url": "https://apihub.agnes-ai.com/v1",
            "api_key": "test-key",
        },
        request=lambda *_args, **_kwargs: pytest.fail(
            "invalid video parameters must fail before network access"
        ),
    )
    with pytest.raises(ValueError, match="720P"):
        client.submit_video(
            "A short video",
            aspect_ratio="16:9",
            duration_seconds=5,
            resolution="1080P",
        )


@pytest.mark.parametrize(
    ("model", "operation"),
    [
        ("agnes-image-2.5", "image"),
        ("agnes-video-2.5", "video"),
        ("unlisted-image-model", "image"),
        ("unlisted-video-model", "video"),
    ],
)
def test_generation_rejects_paid_or_unapproved_models_before_network(
    model,
    operation,
):
    client = AgnesMediaClient(
        {
            "model": model,
            "base_url": "https://apihub.agnes-ai.com/v1",
            "api_key": "test-key",
        },
        request=lambda *_args, **_kwargs: pytest.fail(
            "unapproved model must fail before network access"
        ),
    )

    with pytest.raises(ValueError, match="free Agnes"):
        if operation == "image":
            client.generate_image("Product image")
        else:
            client.submit_video("Product video")


@pytest.mark.parametrize(
    ("status_code", "expected_code"),
    [
        (401, "media_provider_auth_failed"),
        (403, "media_provider_auth_failed"),
        (402, "media_provider_quota_exceeded"),
        (404, "media_provider_endpoint_not_found"),
        (422, "media_provider_request_rejected"),
        (429, "media_provider_rate_limited"),
        (503, "media_provider_unavailable"),
    ],
)
def test_provider_http_errors_are_safely_classified(
    status_code,
    expected_code,
    monkeypatch,
):
    monkeypatch.setattr(agnes_client.time, "sleep", lambda _seconds: None)
    client = AgnesMediaClient(
        {
            "model": "agnes-video-2.5-flash",
            "base_url": "https://apihub.agnes-ai.com/v1",
            "api_key": "must-not-leak",
        },
        request=lambda *_args, **_kwargs: FakeResponse(
            {"error": {"message": "private provider detail"}},
            status_code=status_code,
        ),
    )

    with pytest.raises(MediaProviderError) as raised:
        client.submit_video("A short product video")

    assert raised.value.code == expected_code
    assert "private provider detail" not in str(raised.value)
    assert "must-not-leak" not in str(raised.value)


def test_provider_timeouts_have_a_distinct_safe_error_code():
    def timeout(*_args, **_kwargs):
        raise requests.Timeout("request timed out")

    client = AgnesMediaClient(
        {
            "model": "agnes-video-2.5-flash",
            "base_url": "https://apihub.agnes-ai.com/v1",
            "api_key": "must-not-leak",
        },
        request=timeout,
    )

    with pytest.raises(MediaProviderError) as raised:
        client.submit_video("A short product video")

    assert raised.value.code == "media_provider_timeout"
    assert "must-not-leak" not in str(raised.value)


def test_video_queue_full_response_retries_and_recovers(monkeypatch):
    calls = []
    waits = []
    full = FakeResponse(
        {"error": {"code": "video_queue_full"}},
        status_code=503,
    )
    full.headers["Retry-After"] = "17"

    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if len(calls) == 1:
            return full
        return FakeResponse({"video_id": "video-123", "status": "processing"})

    monkeypatch.setattr(agnes_client.time, "sleep", waits.append)
    client = AgnesMediaClient(
        {
            "model": "agnes-video-2.5-flash",
            "base_url": "https://apihub.agnes-ai.com/v1",
            "api_key": "must-not-leak",
        },
        request=request,
    )

    submitted = client.submit_video("A short product video")

    assert submitted == {
        "video_id": "video-123",
        "status": "processing",
        "model": "agnes-video-2.5-flash",
    }
    assert len(calls) == 2
    assert waits == [17.0]
    assert calls[1][0:2] == calls[0][0:2]


def test_video_queue_full_http_200_envelope_is_retried(monkeypatch):
    calls = []
    waits = []

    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if len(calls) == 1:
            return FakeResponse({"code": "video_queue_full"})
        return FakeResponse({"video_id": "video-456", "status": "processing"})

    monkeypatch.setattr(agnes_client.time, "sleep", waits.append)
    client = AgnesMediaClient(
        {
            "model": "agnes-video-2.5-flash",
            "base_url": "https://apihub.agnes-ai.com/v1",
            "api_key": "test-key",
        },
        request=request,
    )

    submitted = client.submit_video("A short product video")

    assert submitted["video_id"] == "video-456"
    assert len(calls) == 2
    assert waits == [10.0]


def test_video_rate_limit_retries_after_retry_after(monkeypatch):
    calls = []
    waits = []
    limited = FakeResponse({"error": {"code": "rate_limit"}}, status_code=429)
    limited.headers["Retry-After"] = "65"

    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if len(calls) == 1:
            return limited
        return FakeResponse({"video_id": "video-789", "status": "processing"})

    monkeypatch.setattr(agnes_client.time, "sleep", waits.append)
    client = AgnesMediaClient(
        {
            "model": "agnes-video-2.5-flash",
            "base_url": "https://apihub.agnes-ai.com/v1",
            "api_key": "test-key",
        },
        request=request,
    )

    submitted = client.submit_video("A short product video")

    assert submitted["video_id"] == "video-789"
    assert len(calls) == 2
    assert waits == [65.0]


def test_video_rate_limit_without_retry_after_waits_once_then_stops(monkeypatch):
    calls = []
    waits = []

    def request(*_args, **_kwargs):
        calls.append(None)
        return FakeResponse(
            {"error": {"code": "rate_limit"}},
            status_code=429,
        )

    monkeypatch.setattr(agnes_client.time, "sleep", waits.append)
    client = AgnesMediaClient(
        {
            "model": "agnes-video-2.5-flash",
            "base_url": "https://apihub.agnes-ai.com/v1",
            "api_key": "test-key",
        },
        request=request,
    )

    with pytest.raises(MediaProviderError) as raised:
        client.submit_video("A short product video")

    assert raised.value.code == "media_provider_rate_limited"
    assert len(calls) == 2
    assert waits == [60.0]


def test_video_queue_full_retries_are_bounded_and_return_safe_error(monkeypatch):
    calls = []
    waits = []

    def request(*_args, **_kwargs):
        calls.append(None)
        return FakeResponse(
            {"error": {"code": "video_queue_full"}},
            status_code=503,
        )

    monkeypatch.setattr(agnes_client.time, "sleep", waits.append)
    client = AgnesMediaClient(
        {
            "model": "agnes-video-2.5-flash",
            "base_url": "https://apihub.agnes-ai.com/v1",
            "api_key": "must-not-leak",
        },
        request=request,
    )

    with pytest.raises(MediaProviderError) as raised:
        client.submit_video("A short product video")

    assert raised.value.code == "media_provider_video_queue_full"
    assert len(calls) == 4
    assert waits == [10.0, 20.0, 40.0]
    assert "must-not-leak" not in str(raised.value)


def test_oversized_provider_json_is_rejected_before_parsing():
    class OversizedResponse(FakeResponse):
        def __init__(self):
            super().__init__({})
            self.headers = {"content-length": "128"}

        def iter_content(self, chunk_size):
            yield b"x" * 128

        def json(self):
            pytest.fail("oversized response must not be parsed")

    client = AgnesMediaClient(
        {
            "model": "agnes-image-2.5-flash",
            "base_url": "https://apihub.agnes-ai.com/v1",
            "api_key": "test-key",
        },
        request=lambda *_args, **_kwargs: OversizedResponse(),
        max_response_bytes=64,
    )

    with pytest.raises(MediaProviderError, match="too_large"):
        client.generate_image("Product hero", size="1K", aspect_ratio="1:1")
