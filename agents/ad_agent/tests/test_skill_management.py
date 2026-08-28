"""Tests for standard-directory Skill management and safe activation."""

import pytest
import time

from agents.ad_agent import AgentRuntime
from agents.ad_agent.persistence.store import AdAgentStore
from agents.ad_agent.skill_management import ManagedSkillManager, SkillPackageError


def _files(name="business-growth"):
    return {
        "SKILL.md": (
            "---\n"
            f"name: {name}\n"
            "description: Business campaign planning guidance\n"
            "platform: multi_platform\n"
            "version: 1.0.0\n"
            "---\n\n"
            "# Campaign planning\n\n"
            "Use the registered provider Tools and keep all writes in dry-run.\n"
        ),
        "scripts/README.md": "Scripts are package assets, not provider Tools.\n",
        "scripts/check.py": "print('must never be imported by Runtime')\n",
        "references/launch.md": "Ask for objective, budget and account before planning.\n",
        "assets/example.svg": "<svg xmlns='http://www.w3.org/2000/svg'/>\n",
    }


def test_standard_skill_directory_is_versioned_and_published(tmp_path):
    store = AdAgentStore(":memory:")
    manager = ManagedSkillManager(store, root=str(tmp_path / "managed"))

    draft = manager.create_version(
        "tenant-a", "business-growth", "1.0.0", _files(), "user-a"
    )
    assert draft["status"] == "draft"
    assert set(draft["files"]) == set(_files())

    detailed = manager.get_version(
        "tenant-a", "business-growth", "1.0.0", include_files=True
    )
    assert detailed["files"]["scripts/check.py"]["encoding"] == "base64"

    runtime = AgentRuntime(persistence_store=store, offline_mode=True)
    published = manager.publish(
        "tenant-a", "business-growth", "1.0.0", runtime=runtime
    )
    assert published["status"] == "published"
    assert "business-growth" in runtime.get_managed_skills()
    assert not any(
        tool.skill == "business-growth" for tool in runtime.registry.list_all()
    )
    context = runtime.tool_selector.build_context_for_input(
        "规划一个跨渠道投放", runtime.registry.list_all()
    )
    assert "Ask for objective" in context["expert_knowledge"]
    assert "must never be imported" not in context["expert_knowledge"]
    assert (tmp_path / "managed").exists()


def test_new_version_archives_previous_release_and_active_lookup_is_scoped(tmp_path):
    store = AdAgentStore(":memory:")
    manager = ManagedSkillManager(store, root=str(tmp_path / "managed"))
    manager.create_version("tenant-a", "business-growth", "1.0.0", _files(), "u1")
    manager.publish("tenant-a", "business-growth", "1.0.0")
    manager.create_version(
        "tenant-a", "business-growth", "1.1.0", {
            **_files(),
            "SKILL.md": _files()["SKILL.md"].replace("1.0.0", "1.1.0"),
        }, "u1"
    )
    manager.publish("tenant-a", "business-growth", "1.1.0")

    active = manager.get_version("tenant-a", "business-growth")
    assert active["version"] == "1.1.0"
    assert [item["version"] for item in manager.list_versions("tenant-a", "business-growth")] == [
        "1.1.0", "1.0.0"
    ]
    assert manager.get_version("tenant-b", "business-growth") is None


@pytest.mark.parametrize(
    "files, message",
    [
        ({"references/only.md": "missing entry"}, "SKILL.md"),
        ({"../SKILL.md": "bad"}, "unsafe Skill file path"),
        ({"SKILL.md": "---\nname: wrong\ndescription: x\n---\n"}, "does not match"),
    ],
)
def test_invalid_standard_skill_package_is_rejected(files, message):
    store = AdAgentStore(":memory:")
    manager = ManagedSkillManager(store)
    with pytest.raises(SkillPackageError, match=message):
        manager.create_version("tenant-a", "business-growth", "1.0.0", files, "u1")


def test_managed_skill_cannot_switch_runtime_tenant():
    store = AdAgentStore(":memory:")
    runtime = AgentRuntime(persistence_store=store, offline_mode=True)
    manager = ManagedSkillManager(store)
    manager.create_version("tenant-a", "first-skill", "1.0.0", _files("first-skill"), "u1")
    manager.publish("tenant-a", "first-skill", "1.0.0", runtime=runtime)
    manager.create_version("tenant-b", "second-skill", "1.0.0", _files("second-skill"), "u2")
    with pytest.raises(PermissionError):
        manager.publish("tenant-b", "second-skill", "1.0.0", runtime=runtime)


def test_skill_up_config_is_data_only_and_uses_standard_package_files():
    store = AdAgentStore(":memory:")
    manager = ManagedSkillManager(store)
    files = {
        **_files("evaluated-skill"),
        "evals/eval.yaml": (
            "schema_version: v1alpha1\n"
            "environment:\n  type: none\n"
            "mcp:\n  servers: []\n"
            "skills:\n  - source: local_path\n    path: .\n"
            "engine:\n  name: codex\n"
            "cases:\n  files:\n    - evals/cases/basic.yaml\n"
        ),
        "evals/cases/basic.yaml": (
            "id: basic\ninput:\n  prompt: 'Explain the campaign plan'\n"
            "expect:\n  exit_code: 0\n"
            "judge:\n  type: rule_based\n"
            "  success:\n    - output_contains:\n        all: ['campaign']\n"
        ),
    }
    record = manager.create_version(
        "tenant-a", "evaluated-skill", "1.0.0", files, "u1"
    )
    eval_path, config = manager._validate_eval_config(
        store.get_skill_version("tenant-a", "evaluated-skill", "1.0.0")
    )
    assert str(eval_path) == "evals/eval.yaml"
    assert config["engine"]["name"] == "codex"
    assert record["evaluation_status"] == "not_run"


def test_skill_with_evaluation_suite_cannot_publish_before_passing(tmp_path):
    store = AdAgentStore(":memory:")
    manager = ManagedSkillManager(store, root=str(tmp_path / "managed"))
    files = {
        **_files("gated-skill"),
        "evals/eval.yaml": (
            "schema_version: v1alpha1\n"
            "environment:\n  type: none\n"
            "mcp:\n  servers: []\n"
            "skills:\n  - source: local_path\n    path: .\n"
            "engine:\n  name: codex\n"
            "cases:\n  files: [evals/cases/basic.yaml]\n"
        ),
        "evals/cases/basic.yaml": "id: basic\ninput:\n  prompt: test\n",
    }
    manager.create_version("tenant-a", "gated-skill", "1.0.0", files, "u1")
    with pytest.raises(SkillPackageError, match="must pass skill-up"):
        manager.publish("tenant-a", "gated-skill", "1.0.0")


def test_skill_package_rejects_credential_assignments_in_context_files():
    manager = ManagedSkillManager(AdAgentStore(":memory:"))
    files = {
        **_files("credential-skill"),
        "references/auth.md": "Runtime-owned config only\naccess_token: YOUR_TOKEN\n",
    }
    with pytest.raises(SkillPackageError, match="forbidden credential field assignment"):
        manager.create_version("tenant-a", "credential-skill", "1.0.0", files, "u1")


def test_skill_up_config_allows_platform_managed_claude_sdk_with_safe_kwargs():
    store = AdAgentStore(":memory:")
    manager = ManagedSkillManager(store)
    files = {
        **_files("claude-skill"),
        "evals/eval.yaml": (
            "schema_version: v1alpha1\n"
            "environment:\n  type: none\n"
            "mcp:\n  servers: []\n"
            "skills:\n  - source: local_path\n    path: .\n"
            "engine:\n"
            "  name: claude_sdk\n"
            "  model:\n    provider: anthropic\n    name: claude-test\n"
            "  kwargs:\n"
            "    max_tokens: 512\n"
            "    file_paths: inputs/brief.txt\n"
            "cases:\n  files: [evals/cases/basic.yaml]\n"
        ),
        "evals/cases/basic.yaml": "id: basic\ninput:\n  prompt: test\n",
    }
    record = manager.create_version("tenant-a", "claude-skill", "1.0.0", files, "u1")
    _, config = manager._validate_eval_config(
        store.get_skill_version("tenant-a", "claude-skill", "1.0.0")
    )
    assert config["engine"]["name"] == "claude_sdk"
    assert config["engine"]["kwargs"]["max_tokens"] == 512
    assert record["evaluation_status"] == "not_run"


def test_skill_up_config_rejects_custom_engines_and_judge_scripts():
    store = AdAgentStore(":memory:")
    manager = ManagedSkillManager(store)
    files = {
        **_files("unsafe-eval"),
        "evals/eval.yaml": (
            "skills:\n  - source: local_path\n    path: .\n"
            "engine:\n  name: unsafe\n  custom:\n    transport: local\n"
            "cases:\n  files: [evals/cases/basic.yaml]\n"
        ),
        "evals/cases/basic.yaml": "id: basic\ninput:\n  prompt: test\n",
    }
    record = manager.create_version(
        "tenant-a", "unsafe-eval", "1.0.0", files, "u1"
    )
    with pytest.raises(SkillPackageError, match="Custom Engine"):
        manager._validate_eval_config(
            store.get_skill_version("tenant-a", "unsafe-eval", "1.0.0")
        )


def test_skill_up_evaluation_is_persisted_for_an_immutable_version(tmp_path, monkeypatch):
    store = AdAgentStore(":memory:")
    manager = ManagedSkillManager(store, root=str(tmp_path / "managed"))
    files = {
        **_files("runnable-eval"),
        "evals/eval.yaml": (
            "schema_version: v1alpha1\n"
            "environment:\n  type: none\n"
            "mcp:\n  servers: []\n"
            "skills:\n  - source: local_path\n    path: .\n"
            "engine:\n  name: codex\n"
            "cases:\n  files:\n    - evals/cases/basic.yaml\n"
        ),
        "evals/cases/basic.yaml": "id: basic\ninput:\n  prompt: test\n",
    }
    manager.create_version("tenant-a", "runnable-eval", "1.0.0", files, "u1")
    fake_bin = tmp_path / "skill-up"
    fake_bin.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, sys\n"
        "if sys.argv[1] == 'validate': sys.exit(0)\n"
        "out = pathlib.Path(sys.argv[sys.argv.index('--output-dir') + 1])\n"
        "out.mkdir(parents=True, exist_ok=True)\n"
        "(out / 'result.json').write_text('{}')\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    fake_bin.chmod(0o755)
    monkeypatch.setenv("SKILL_UP_BIN", str(fake_bin))

    run = manager.start_evaluation("tenant-a", "runnable-eval", "1.0.0")
    for _ in range(100):
        current = manager.get_evaluation("tenant-a", run["run_id"])
        if current and current["status"] in {"passed", "failed", "error"}:
            break
        time.sleep(0.01)
    assert current["status"] == "passed"
    version = manager.get_version("tenant-a", "runnable-eval", "1.0.0")
    assert version["evaluation_status"] == "passed"
    assert version["evaluation_run_id"] == run["run_id"]
