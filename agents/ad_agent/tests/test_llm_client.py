"""Structured LLM client contract tests; no network calls are made."""

import pytest

from agents.ad_agent.core.llm_client import LLMClient, LLMStructuredOutputError


def test_call_json_returns_only_json_objects(monkeypatch):
    client = LLMClient(model="test-model", api_key="test-key")
    monkeypatch.setattr(client, "call", lambda *_args, **_kwargs: '```json\n{"ok": true}\n```')

    assert client.call_json([]) == {"ok": True}


def test_call_json_fails_closed_on_non_json_text(monkeypatch):
    client = LLMClient(model="test-model", api_key="test-key")
    monkeypatch.setattr(client, "call", lambda *_args, **_kwargs: "not json")

    with pytest.raises(LLMStructuredOutputError):
        client.call_json([])
