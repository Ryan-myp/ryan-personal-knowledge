"""Exercise the real SDK adapter CLI with a non-network model double."""

import json
import sys
from types import SimpleNamespace

import pytest

from agents.agent_platform.evals import claude_sdk_engine as engine
from agents.agent_platform.management.evaluation import (
    builtin_evaluation_engines,
    skill_up_config,
)


def test_sdk_cli_writes_a_session_result_without_executable_tools(
    tmp_path, monkeypatch
):
    calls = []
    client = SimpleNamespace(
        messages=SimpleNamespace(
            create=lambda **kwargs: (
                calls.append(kwargs)
                or {
                    "content": [{"type": "text", "text": "done"}],
                    "usage": {},
                }
            ),
        )
    )
    monkeypatch.setattr(engine, "_build_client", lambda: client)
    monkeypatch.delenv("AGENT_EVAL_SKILLS_ROOT", raising=False)
    monkeypatch.delenv("AGENT_EVAL_TOOL_CATALOG", raising=False)
    input_path, output_path = tmp_path / "input.json", tmp_path / "output.json"
    input_path.write_text(json.dumps({"prompt": "hello", "workspace": str(tmp_path)}))
    assert engine.main(["--input", str(input_path), "--output", str(output_path)]) == 0
    assert json.loads(output_path.read_text())["final_message"] == "done"
    assert "tools" not in calls[0]
    assert "advertising agent" not in calls[0]["system"]


def test_sdk_cli_redacts_errors_and_rejects_non_object_input(tmp_path, monkeypatch):
    input_path, output_path = tmp_path / "input.json", tmp_path / "output.json"
    input_path.write_text("[]", encoding="utf-8")
    assert engine.main(["--input", str(input_path), "--output", str(output_path)]) == 1
    assert (
        "SessionInput must be a JSON object"
        in json.loads(output_path.read_text())["stderr"]
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-model-key-not-a-real-key")
    assert (
        engine._safe_error(RuntimeError("test-model-key-not-a-real-key"))
        == "[REDACTED]"
    )


def test_sdk_client_uses_only_the_selected_model_credential(monkeypatch):
    monkeypatch.setitem(
        sys.modules, "anthropic", SimpleNamespace(Anthropic=lambda **kwargs: kwargs)
    )
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="requires ANTHROPIC_API_KEY"):
        engine._build_client()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-model-key-not-a-real-key")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://model.example.invalid")
    assert engine._build_client() == {
        "api_key": "test-model-key-not-a-real-key",
        "base_url": "https://model.example.invalid",
    }


def test_generated_evaluation_command_is_deployed_and_config_is_immutable():
    config = {
        "engine": {
            "name": "claude_sdk",
            "model": "test-model",
            "kwargs": {"max_tokens": 1024},
        }
    }
    binding = builtin_evaluation_engines()["claude_sdk"]
    generated = skill_up_config(config, binding, 60)
    assert generated["engine"]["model"] == "test-model"
    assert generated["engine"]["custom"]["kwargs"] == {"max_tokens": "1024"}
    assert generated["engine"]["custom"]["local"]["args"][0] == str(
        binding.adapter_path
    )
    assert "custom" not in config["engine"]


def test_generated_file_path_kwargs_preserve_structured_lists(tmp_path):
    (tmp_path / "notes.txt").write_text("trusted file context", encoding="utf-8")
    config = {"engine": {"name": "claude_sdk", "kwargs": {"file_paths": ["notes.txt"]}}}
    generated = skill_up_config(config, builtin_evaluation_engines()["claude_sdk"], 60)
    kwargs = generated["engine"]["custom"]["kwargs"]
    assert "trusted file context" in engine._load_file_context(tmp_path, kwargs, 2000)
