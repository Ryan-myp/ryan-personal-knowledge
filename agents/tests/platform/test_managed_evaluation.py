"""Trusted evaluator configuration cannot be supplied by uploaded Skills."""

from pathlib import Path
import json
import os
import subprocess
import sys

import pytest

from agents.agent_platform.management.skill_management import (
    ManagedSkillManager,
    SkillPackageError,
)


def test_platform_has_a_real_builtin_evaluation_adapter(tmp_path):
    manager = ManagedSkillManager(object(), root=str(tmp_path))
    adapter = manager.evaluation_engines["claude_sdk"].adapter_path
    assert adapter.is_file()
    assert "advertising" not in str(adapter)


def test_unregistered_domain_evaluator_is_rejected(tmp_path):
    from agents.agent_platform.management.skill_management import encode_skill_files

    record = {
        "files": encode_skill_files(
            {
                "SKILL.md": b"---\nname: example\ndescription: Example\n---\n",
                "evals/eval.yaml": (
                    b"engine: {name: ad-agent-runtime}\n"
                    b"skills: [{source: local_path, path: .}]\n"
                    b"cases: {files: [evals/case.yaml]}\n"
                ),
                "evals/case.yaml": b"id: one\ninput: {prompt: hello}\n",
            }
        )
    }
    manager = ManagedSkillManager(object(), root=str(tmp_path))
    with pytest.raises(SkillPackageError, match="platform-managed engine"):
        manager._validate_eval_config(record)


def test_deployment_evaluation_adapter_exists_and_is_injected(tmp_path):
    from agents.applications.advertising.integrations.skill_evaluation import (
        advertising_evaluation_engines,
    )

    engines = advertising_evaluation_engines()
    manager = ManagedSkillManager(
        object(), root=str(tmp_path), evaluation_engines=engines
    )
    adapter = manager.evaluation_engines["ad-agent-runtime"].adapter_path
    assert adapter.is_file()
    assert (
        adapter
        == Path(__file__).resolve().parents[2] / "evals/advertising/skill_up_engine.py"
    )


def test_builtin_adapter_starts_from_an_unrelated_working_directory(tmp_path):
    manager = ManagedSkillManager(object(), root=str(tmp_path / "managed"))
    input_file = tmp_path / "input.json"
    output_file = tmp_path / "output.json"
    input_file.write_text(json.dumps({}), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(manager.evaluation_engines["claude_sdk"].adapter_path),
            "--input",
            str(input_file),
            "--output",
            str(output_file),
        ],
        cwd=tmp_path,
        env={key: value for key, value in os.environ.items() if key == "PATH"},
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 1
    data = json.loads(output_file.read_text())
    assert data["engine"] == "claude_sdk"
    assert "SessionInput.messages or SessionInput.prompt is required" in data["stderr"]


def test_adapter_bindings_validate_paths_and_kwargs(tmp_path):
    from agents.agent_platform.management.evaluation import ManagedEvaluationEngine

    with pytest.raises(ValueError, match="deployed Python file"):
        ManagedEvaluationEngine(tmp_path / "missing.py")
    with pytest.raises(TypeError, match="trusted engine binding"):
        ManagedSkillManager(
            object(), root=str(tmp_path), evaluation_engines={"unsafe": {}}
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"prompt": "hello"},
        {"messages": [], "prompt": "hello"},
    ],
)
def test_evaluation_protocol_accepts_a_plain_prompt(payload):
    from agents.agent_platform.evals.protocol import session_messages

    assert session_messages(payload) == [{"role": "user", "content": "hello"}]


@pytest.mark.parametrize(
    "messages",
    [
        ["invalid"],
        [{"role": "unknown", "content": "hello"}],
        [{"role": "user", "content": {"script": "invalid"}}],
    ],
)
def test_evaluation_protocol_rejects_malformed_messages(messages):
    from agents.agent_platform.evals.protocol import session_messages

    with pytest.raises(ValueError):
        session_messages({"messages": messages})
