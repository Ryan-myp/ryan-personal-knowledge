"""Structured LLM client contract tests; no network calls are made."""

import pytest
from types import SimpleNamespace

from agents.agent_harness.core.llm_client import (
    LLMClient,
    LLMStructuredOutputError,
    capture_llm_usage,
)
from agents.agent_harness.messages import InputMedia, MediaFrame


def test_call_json_returns_only_json_objects(monkeypatch):
    client = LLMClient(model="test-model", api_key="test-key")
    monkeypatch.setattr(client, "call", lambda *_args, **_kwargs: '```json\n{"ok": true}\n```')

    assert client.call_json([]) == {"ok": True}


def test_call_json_fails_closed_on_non_json_text(monkeypatch):
    client = LLMClient(model="test-model", api_key="test-key")
    monkeypatch.setattr(client, "call", lambda *_args, **_kwargs: "not json")

    with pytest.raises(LLMStructuredOutputError):
        client.call_json([])


def test_call_reports_provider_token_and_prompt_cache_usage(monkeypatch):
    client = LLMClient(model="test-model", api_key="test-key")
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="answer"))],
        usage=SimpleNamespace(
            prompt_tokens=120,
            completion_tokens=18,
            total_tokens=138,
            prompt_tokens_details=SimpleNamespace(cached_tokens=72),
        ),
    )
    monkeypatch.setattr(
        client,
        "_get_client",
        lambda: SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=lambda **_kwargs: response)
            )
        ),
    )

    with capture_llm_usage() as usage:
        assert client.call([]) == "answer"

    assert usage.snapshot() == {
        "input_tokens": 120,
        "output_tokens": 18,
        "total_tokens": 138,
        "cache_read_input_tokens": 72,
        "cache_write_input_tokens": 0,
        "llm_requests": 1,
    }


def test_call_with_usage_preserves_legacy_call_contract(monkeypatch):
    client = LLMClient(model="test-model", api_key="test-key")
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
        usage=None,
    )
    monkeypatch.setattr(
        client,
        "_get_client",
        lambda: SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=lambda **_kwargs: response)
            )
        ),
    )

    assert client.call_with_usage([]) == (
        "ok",
        {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cache_read_input_tokens": 0,
            "cache_write_input_tokens": 0,
            "llm_requests": 1,
        },
    )


def test_failed_provider_attempt_is_counted_without_copying_exception_payload(monkeypatch):
    client = LLMClient(model="test-model", api_key="test-key")

    def fail(**_kwargs):
        raise RuntimeError("request failed access_token=private")

    monkeypatch.setattr(
        client,
        "_get_client",
        lambda: SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=fail)
            )
        ),
    )

    with capture_llm_usage() as usage:
        with pytest.raises(RuntimeError):
            client.call([])

    assert usage.snapshot()["llm_requests"] == 1
    assert "private" not in str(usage.snapshot())


def test_tool_call_failure_logs_only_safe_provider_diagnostics(monkeypatch, caplog):
    client = LLMClient(model="test-model", api_key="test-key")
    error = RuntimeError("access_token=private raw request body")
    error.status_code = 400
    error.body = {
        "error": {
            "type": "invalid_request_error",
            "code": "invalid_tool_call_id",
            "param": "messages[5].tool_call_id",
            "message": (
                "maximum context length exceeded; "
                "access_token=private raw request body"
            ),
        }
    }

    def fail(**_kwargs):
        raise error

    monkeypatch.setattr(
        client,
        "_get_client",
        lambda: SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=fail)
            )
        ),
    )
    caplog.set_level("ERROR", logger="agents.agent_harness.core.llm_client")

    with pytest.raises(RuntimeError):
        client.complete(
            [
                {"role": "system", "content": "fixed protocol"},
                {"role": "user", "content": "create an app promotion campaign"},
                {
                    "role": "tool",
                    "name": "tiktok_list_identities",
                    "tool_call_id": "call_1",
                    "content": {"success": True, "data": {"count": 27}},
                },
            ],
            tools=[{
                "name": "tiktok_list_identities",
                "description": "List identities",
                "input_schema": {
                    "type": "object",
                    "properties": {"account_id": {"type": "string"}},
                    "required": ["account_id"],
                    "additionalProperties": False,
                },
            }],
            request=SimpleNamespace(context={}),
        )

    assert "status_code=400" in caplog.text
    assert "api_error_type=invalid_request_error" in caplog.text
    assert "api_error_code=invalid_tool_call_id" in caplog.text
    assert "api_error_param=messages[5].tool_call_id" in caplog.text
    assert "api_error_category=context_limit" in caplog.text
    assert "message_count=3" in caplog.text
    assert "tool_count=1" in caplog.text
    assert "system_chars=" in caplog.text
    assert "tool_result_chars=" in caplog.text
    assert "tool_schema_chars=" in caplog.text
    assert "private" not in caplog.text
    assert "raw request body" not in caplog.text


def test_complete_passes_uploaded_images_as_openai_compatible_vision_content(monkeypatch):
    client = LLMClient(model="test-model", api_key="test-key")
    captured = {}
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="看到了图片"))],
        usage=None,
    )

    def create(**kwargs):
        captured.update(kwargs)
        return response

    monkeypatch.setattr(
        client,
        "_get_client",
        lambda: SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        ),
    )
    image = InputMedia(
        attachment_id="image-1",
        filename="product.png",
        media_type="image/png",
        content=b"png bytes",
    )

    result = client.complete(
        [{"role": "user", "content": "请评价这张图片"}],
        [],
        SimpleNamespace(context={}, input_media=(image,)),
    )

    assert result.content == "看到了图片"
    content = captured["messages"][0]["content"]
    assert content[0] == {"type": "text", "text": "请评价这张图片"}
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"] == "data:image/png;base64,cG5nIGJ5dGVz"


def test_complete_adds_only_bounded_video_frames_to_vision_request(monkeypatch):
    client = LLMClient(model="test-model", api_key="test-key")
    captured = {}
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="视频已分析"))],
        usage=None,
    )

    def create(**kwargs):
        captured.update(kwargs)
        return response

    monkeypatch.setattr(
        client,
        "_get_client",
        lambda: SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        ),
    )
    video = InputMedia(
        attachment_id="video-1",
        filename="story.mp4",
        media_type="video/mp4",
        content=b"video bytes",
        frames=(
            MediaFrame(
                timestamp_seconds=1.5,
                media_type="image/jpeg",
                content=b"frame-1",
            ),
            MediaFrame(
                timestamp_seconds=4.0,
                media_type="image/jpeg",
                content=b"frame-2",
            ),
        ),
    )

    client.complete(
        [{"role": "user", "content": "总结视频内容"}],
        [],
        SimpleNamespace(context={}, input_media=(video,)),
    )

    content = captured["messages"][0]["content"]
    assert "story.mp4" in content[0]["text"]
    assert "1.5s" in content[0]["text"]
    assert [item["type"] for item in content[1:]] == ["image_url", "image_url"]
    assert all(
        item["image_url"]["url"].startswith("data:image/jpeg;base64,")
        for item in content[1:]
    )


def test_input_media_rejects_empty_content_and_unsupported_mime_types():
    with pytest.raises(ValueError, match="media type"):
        InputMedia(
            attachment_id="bad",
            filename="bad.svg",
            media_type="image/svg+xml",
            content=b"<svg/>",
        )

    with pytest.raises(ValueError, match="non-empty"):
        InputMedia(
            attachment_id="empty",
            filename="empty.png",
            media_type="image/png",
            content=b"",
        )


def test_input_media_rejects_video_frame_counts_over_the_bound():
    with pytest.raises(ValueError, match="frame limit"):
        InputMedia(
            attachment_id="video-many",
            filename="large.mp4",
            media_type="video/mp4",
            content=b"video",
            frames=tuple(
                MediaFrame(
                    timestamp_seconds=float(index),
                    media_type="image/jpeg",
                    content=b"frame",
                )
                for index in range(9)
            ),
        )


@pytest.mark.parametrize(
    "timestamp",
    [float("nan"), float("inf"), float("-inf"), -0.1],
)
def test_media_frame_rejects_non_finite_or_negative_timestamps(timestamp):
    with pytest.raises(ValueError, match="finite and non-negative"):
        MediaFrame(
            timestamp_seconds=timestamp,
            media_type="image/jpeg",
            content=b"frame",
        )
