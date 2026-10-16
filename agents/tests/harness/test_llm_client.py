"""Structured LLM client contract tests; no network calls are made."""

import pytest
from types import SimpleNamespace

from agents.agent_harness.core.llm_client import (
    LLMClient,
    LLMStructuredOutputError,
    capture_llm_usage,
)


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
