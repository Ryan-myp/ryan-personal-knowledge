"""Tests for standard-directory Skill management and safe activation."""

import pytest
import time
import threading
from pathlib import Path

from agents.ad_agent import AgentRuntime
from agents.ad_agent.core.interfaces import ParsedIntent
from agents.ad_agent.core.interfaces import ToolDefinition, ToolSchema
from agents.ad_agent.persistence.store import AdAgentStore
from agents.ad_agent.skill_management import (
    BuiltinSkillCatalog,
    ManagedSkillManager,
    SkillPackageError,
    _safe_evaluation_payload,
)


def test_builtin_skill_catalog_lists_standard_packages_as_read_only():
    skills_root = Path(__file__).resolve().parents[1] / "skills"
    catalog = BuiltinSkillCatalog(skills_root)

    items = catalog.list_versions(limit=200)

    assert {item["skill_name"] for item in items} >= {
        "google-ads-api-expert", "meta-marketing-api-expert", "tiktok-ads-expert",
    }
    assert all(item["source"] == "builtin" and item["editable"] is False for item in items)
    detail = catalog.get_version("google-ads-api-expert", "2.0.0")
    assert detail["files"]["SKILL.md"]["encoding"] == "base64"
    assert detail["location"] == "channels/google-ads"


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


def test_channel_and_cross_channel_skills_are_natural_language_guidance():
    skills_root = Path(__file__).resolve().parents[1] / "skills"
    skill_paths = [
        *sorted((skills_root / "channels").glob("*/SKILL.md")),
        skills_root / "cross-channel" / "SKILL.md",
    ]

    for skill_path in skill_paths:
        content = skill_path.read_text(encoding="utf-8")
        # Internal intent labels and provider Tool names are Runtime concerns.
        # Keeping them out of Skill prose prevents the LLM from treating a
        # capability description as an executable Tool registry.
        assert "cross_channel_" not in content, skill_path
        assert "workflow.yaml" not in content, skill_path
        assert "meta_list_pixels" not in content, skill_path
        assert "ToolDefinition" in content or "Capability" in content, skill_path


def test_channel_skill_body_is_available_to_model_context():
    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    try:
        examples = {
            "google-ads": ("查询 Google Ads campaign", "Google Ads API 专家 Skill"),
            "meta": ("查询 Meta campaign performance", "Meta Marketing API 专家 Skill"),
            "tiktok": ("查询 TikTok campaign performance", "TikTok Ads 专家 Skill"),
            "dv360": ("查询 DV360 line item report", "Display & Video 360 专家 Skill"),
        }
        for platform, (request, marker) in examples.items():
            # The test only needs a provider-owned contract to enter the
            # selector's expert-context merge; it must not initialize or call
            # a real Provider client.
            tool = ToolDefinition(
                name=f"{platform}_list_campaigns",
                skill=f"{platform}-capability",
                platform=platform,
                description="list campaigns",
                input_schema=ToolSchema(),
                intent_types=["list_campaigns"],
            )
            selection = runtime.tool_selector.select_tools(
                request,
                ParsedIntent("list_campaigns", request, [platform]),
                [tool],
            )
            assert marker in selection.expert_knowledge, platform
    finally:
        runtime.close(wait=True)


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

    runtime = AgentRuntime(require_llm=False, persistence_store=store, offline_mode=True)
    published = manager.publish(
        "tenant-a", "business-growth", "1.0.0", runtime=runtime
    )
    assert published["status"] == "published"
    assert "business-growth" in runtime.get_managed_skills()
    assert not any(
        tool.skill == "business-growth" for tool in runtime.registry.list_all()
    )
    context = runtime.tool_selector.build_context_for_input(
        "规划一个跨渠道投放", runtime.registry.list_all(), tenant_id="tenant-a"
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


def test_unpublish_removes_release_but_keeps_version_for_explicit_rollback(tmp_path):
    store = AdAgentStore(":memory:")
    manager = ManagedSkillManager(store, root=str(tmp_path / "managed"))
    manager.create_version("tenant-a", "business-growth", "1.0.0", _files(), "u1")

    runtime = AgentRuntime(require_llm=False, persistence_store=store, offline_mode=True)
    manager.publish("tenant-a", "business-growth", "1.0.0", runtime=runtime)
    assert "business-growth" in runtime.get_managed_skills("tenant-a")

    unpublished = manager.unpublish(
        "tenant-a", "business-growth", "1.0.0", runtime=runtime
    )

    assert unpublished["status"] == "archived"
    assert manager.get_version("tenant-a", "business-growth") is None
    assert manager.get_version("tenant-a", "business-growth", "1.0.0")["status"] == "archived"
    assert "business-growth" not in runtime.get_managed_skills("tenant-a")

    # Re-publishing the immutable archived snapshot is the explicit rollback
    # path; it must restore both the release pointer and Runtime context.
    rolled_back = manager.publish(
        "tenant-a", "business-growth", "1.0.0", runtime=runtime
    )
    assert rolled_back["status"] == "published"
    assert manager.get_version("tenant-a", "business-growth")["version"] == "1.0.0"
    assert "business-growth" in runtime.get_managed_skills("tenant-a")


def test_publication_serializes_runtime_activation_and_release_pointer(tmp_path):
    """Separate HTTP manager facades cannot diverge Runtime and SQLite state."""
    store = AdAgentStore(":memory:")
    manager_a = ManagedSkillManager(store, root=str(tmp_path / "managed"))
    manager_b = ManagedSkillManager(store, root=str(tmp_path / "managed"))
    manager_a.create_version("tenant-a", "release-skill", "1.0.0", _files("release-skill"), "u1")
    manager_a.create_version(
        "tenant-a", "release-skill", "2.0.0",
        {**_files("release-skill"), "SKILL.md": _files("release-skill")["SKILL.md"].replace("1.0.0", "2.0.0")},
        "u1",
    )

    class RecordingRuntime:
        def __init__(self):
            self.first_entered = threading.Event()
            self.release_first = threading.Event()
            self.active = 0
            self.max_active = 0
            self._lock = threading.Lock()
            self.loaded_versions = []

        def load_managed_skill(self, path, **_kwargs):
            with self._lock:
                self.active += 1
                self.max_active = max(self.max_active, self.active)
                first = not self.loaded_versions
            if first:
                self.first_entered.set()
                self.release_first.wait(timeout=2)
            self.loaded_versions.append(Path(path).name)
            with self._lock:
                self.active -= 1
            return True

    runtime = RecordingRuntime()
    errors = []

    def publish(manager, version):
        try:
            manager.publish("tenant-a", "release-skill", version, runtime=runtime)
        except Exception as exc:  # pragma: no cover - assertion below reports it
            errors.append(exc)

    first = threading.Thread(target=publish, args=(manager_a, "1.0.0"))
    second = threading.Thread(target=publish, args=(manager_b, "2.0.0"))
    first.start()
    assert runtime.first_entered.wait(timeout=2)
    second.start()
    # The second request has its own manager, so only a shared publication
    # lock can keep it from activating while the first request is in flight.
    time.sleep(0.05)
    assert runtime.max_active == 1
    runtime.release_first.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert errors == []
    assert runtime.max_active == 1
    assert runtime.loaded_versions == ["1_0_0", "2_0_0"]
    assert manager_a.get_version("tenant-a", "release-skill")["version"] == "2.0.0"


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


def test_managed_skills_are_isolated_by_tenant_on_shared_runtime():
    store = AdAgentStore(":memory:")
    runtime = AgentRuntime(require_llm=False, persistence_store=store, offline_mode=True)
    manager = ManagedSkillManager(store)
    first_files = _files("first-skill")
    first_files["SKILL.md"] = first_files["SKILL.md"].replace(
        "platform: multi_platform\n", "platform: multi_platform\naliases: [tenant-a-only]\n"
    ).replace(
        "# Campaign planning", "# Tenant A planning"
    )
    second_files = _files("second-skill")
    second_files["SKILL.md"] = second_files["SKILL.md"].replace(
        "# Campaign planning", "# Tenant B planning"
    )
    manager.create_version("tenant-a", "first-skill", "1.0.0", first_files, "u1")
    manager.publish("tenant-a", "first-skill", "1.0.0", runtime=runtime)
    manager.create_version("tenant-b", "second-skill", "1.0.0", second_files, "u2")
    manager.publish("tenant-b", "second-skill", "1.0.0", runtime=runtime)

    tenant_a_context = runtime.tool_selector.build_context_for_input(
        "规划一个跨渠道投放", runtime.registry.list_all(), tenant_id="tenant-a"
    )
    tenant_b_context = runtime.tool_selector.build_context_for_input(
        "规划一个跨渠道投放", runtime.registry.list_all(), tenant_id="tenant-b"
    )
    assert "first-skill" in tenant_a_context["expert_knowledge"]
    assert "Tenant A planning" in tenant_a_context["expert_knowledge"]
    assert "second-skill" not in tenant_a_context["expert_knowledge"]
    assert "second-skill" in tenant_b_context["expert_knowledge"]
    assert "Tenant B planning" in tenant_b_context["expert_knowledge"]
    assert "first-skill" not in tenant_b_context["expert_knowledge"]
    assert set(runtime.get_managed_skills("tenant-a")) == {"first-skill"}
    assert set(runtime.get_managed_skills("tenant-b")) == {"second-skill"}
    assert runtime.skill_loader.get("first-skill") is None
    assert runtime.skill_loader.get("second-skill") is None
    assert "tenant-a-only" not in getattr(runtime.intent_parser, "_platform_aliases", {})


def test_separate_in_memory_stores_do_not_share_materialized_skill_cache():
    first_store = AdAgentStore(":memory:")
    second_store = AdAgentStore(":memory:")
    first = ManagedSkillManager(first_store)
    second = ManagedSkillManager(second_store)

    assert first.root != second.root
    first_store.close()
    second_store.close()


def test_publish_does_not_commit_when_runtime_activation_fails():
    store = AdAgentStore(":memory:")
    manager = ManagedSkillManager(store)
    manager.create_version("tenant-a", "broken-skill", "1.0.0", _files("broken-skill"), "u1")

    class BrokenRuntime:
        def load_managed_skill(self, *_args, **_kwargs):
            raise ValueError("invalid managed context")

    with pytest.raises(SkillPackageError, match="release was not published"):
        manager.publish("tenant-a", "broken-skill", "1.0.0", runtime=BrokenRuntime())
    record = manager.get_version("tenant-a", "broken-skill", "1.0.0")
    assert record["status"] == "draft"
    assert manager.get_version("tenant-a", "broken-skill") is None


def test_materialized_skill_cache_rejects_tampering(tmp_path):
    store = AdAgentStore(":memory:")
    manager = ManagedSkillManager(store, root=str(tmp_path / "managed"))
    manager.create_version("tenant-a", "tamper-check", "1.0.0", _files("tamper-check"), "u1")
    record = store.get_skill_version("tenant-a", "tamper-check", "1.0.0")

    materialized = manager._materialize(record)
    (materialized / "SKILL.md").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(SkillPackageError, match="snapshot digest mismatch"):
        manager._materialize(record)


def test_evaluation_payload_scrubs_echoed_environment_secrets(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-secret-value")
    monkeypatch.setenv("META_ACCESS_TOKEN", "meta-secret-value")
    payload = _safe_evaluation_payload({
        "stdout": "OPENAI_API_KEY=openai-secret-value META_ACCESS_TOKEN=meta-secret-value",
    })
    assert "openai-secret-value" not in payload["stdout"]
    assert "meta-secret-value" not in payload["stdout"]
    assert payload["stdout"].count("<redacted>") == 2


def test_skill_up_environment_is_minimal_and_engine_scoped(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-secret-value")
    monkeypatch.setenv("META_ACCESS_TOKEN", "meta-secret-value")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-secret-value")
    runtime_env = ManagedSkillManager._evaluation_environment("ad-agent-runtime")
    claude_env = ManagedSkillManager._evaluation_environment("claude_sdk")

    assert "OPENAI_API_KEY" not in runtime_env
    assert "META_ACCESS_TOKEN" not in runtime_env
    assert "ANTHROPIC_API_KEY" not in runtime_env
    assert claude_env["ANTHROPIC_API_KEY"] == "anthropic-secret-value"
    assert "OPENAI_API_KEY" not in claude_env
    assert "META_ACCESS_TOKEN" not in claude_env


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
            "engine:\n  name: ad-agent-runtime\n"
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
    assert config["engine"]["name"] == "ad-agent-runtime"
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
            "engine:\n  name: ad-agent-runtime\n"
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


def test_skill_package_rejects_service_account_file_assignments():
    manager = ManagedSkillManager(AdAgentStore(":memory:"))
    files = {
        **_files("service-account-skill"),
        "references/auth.md": "service_account_file: /tmp/provider.json\n",
    }
    with pytest.raises(SkillPackageError, match="forbidden credential field assignment"):
        manager.create_version("tenant-a", "service-account-skill", "1.0.0", files, "u1")


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


def test_managed_skill_eval_rejects_external_cli_engines():
    store = AdAgentStore(":memory:")
    manager = ManagedSkillManager(store)
    files = {
        **_files("external-engine"),
        "evals/eval.yaml": (
            "skills:\n  - source: local_path\n    path: .\n"
            "engine:\n  name: codex\n"
            "cases:\n  files: [evals/cases/basic.yaml]\n"
        ),
        "evals/cases/basic.yaml": "id: basic\ninput:\n  prompt: test\n",
    }
    manager.create_version("tenant-a", "external-engine", "1.0.0", files, "u1")
    with pytest.raises(SkillPackageError, match="platform-managed engine"):
        manager._validate_eval_config(
            store.get_skill_version("tenant-a", "external-engine", "1.0.0")
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
            "engine:\n  name: ad-agent-runtime\n"
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
    for _ in range(500):
        current = manager.get_evaluation("tenant-a", run["run_id"])
        if current and current["status"] in {"passed", "failed", "error"}:
            break
        time.sleep(0.01)
    assert current["status"] == "passed"
    version = manager.get_version("tenant-a", "runnable-eval", "1.0.0")
    assert version["evaluation_status"] == "passed"
    assert version["evaluation_run_id"] == run["run_id"]
    materialized = manager._materialize(store.get_skill_version(
        "tenant-a", "runnable-eval", "1.0.0"
    ))
    assert not list(materialized.glob(".skill-up-eval-*.yaml"))


def test_skill_up_allows_only_one_active_evaluation_per_version(tmp_path, monkeypatch):
    store = AdAgentStore(":memory:")
    manager = ManagedSkillManager(store, root=str(tmp_path / "managed"))
    files = {
        **_files("single-flight-eval"),
        "evals/eval.yaml": (
            "schema_version: v1alpha1\n"
            "environment:\n  type: none\n"
            "mcp:\n  servers: []\n"
            "skills:\n  - source: local_path\n    path: .\n"
            "engine:\n  name: ad-agent-runtime\n"
            "cases:\n  files: [evals/cases/basic.yaml]\n"
        ),
        "evals/cases/basic.yaml": "id: basic\ninput:\n  prompt: test\n",
    }
    manager.create_version("tenant-a", "single-flight-eval", "1.0.0", files, "u1")
    fake_bin = tmp_path / "skill-up"
    fake_bin.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, sys, time\n"
        "if sys.argv[1] == 'validate': sys.exit(0)\n"
        "time.sleep(0.15)\n"
        "out = pathlib.Path(sys.argv[sys.argv.index('--output-dir') + 1])\n"
        "out.mkdir(parents=True, exist_ok=True)\n"
        "(out / 'result.json').write_text('{}')\n",
        encoding="utf-8",
    )
    fake_bin.chmod(0o755)
    monkeypatch.setenv("SKILL_UP_BIN", str(fake_bin))

    first = manager.start_evaluation("tenant-a", "single-flight-eval", "1.0.0")
    with pytest.raises(SkillPackageError, match="already has an evaluation"):
        manager.start_evaluation("tenant-a", "single-flight-eval", "1.0.0")
    assert manager.get_evaluation("tenant-a", first["run_id"])["status"] in {
        "queued", "running", "passed", "failed", "error"
    }


def test_interrupted_skill_up_evaluation_is_recovered_and_retryable():
    store = AdAgentStore(":memory:")
    manager = ManagedSkillManager(store)
    manager.create_version("tenant-a", "recoverable-eval", "1.0.0", _files("recoverable-eval"), "u1")
    version = store.get_skill_version("tenant-a", "recoverable-eval", "1.0.0")
    run = store.claim_skill_evaluation("old-run", version["version_id"], "tenant-a")
    assert run["status"] == "queued"

    with store._lock:
        store._get_conn().execute(
            "UPDATE skill_evaluation_runs SET updated_at = ? WHERE run_id = ?",
            ("2000-01-01T00:00:00", "old-run"),
        )
        store._get_conn().commit()

    assert manager.recover_interrupted_evaluations(stale_after_seconds=900) == 1
    recovered = manager.get_evaluation("tenant-a", "old-run")
    assert recovered["status"] == "error"
    assert "interrupted" in recovered["error"]
    version = manager.get_version("tenant-a", "recoverable-eval", "1.0.0")
    assert version["evaluation_status"] == "error"

    retry = store.claim_skill_evaluation("new-run", version["version_id"], "tenant-a")
    assert retry["run_id"] == "new-run"


def test_skill_evaluation_updates_are_tenant_and_run_scoped():
    store = AdAgentStore(":memory:")
    manager = ManagedSkillManager(store)
    manager.create_version("tenant-a", "scoped-eval", "1.0.0", _files("scoped-eval"), "u1")
    version = store.get_skill_version("tenant-a", "scoped-eval", "1.0.0")
    store.claim_skill_evaluation("run-a", version["version_id"], "tenant-a")

    assert store.update_skill_evaluation_run(
        "run-a", "tenant-b", "running"
    ) is False
    assert store.set_skill_evaluation(
        version["version_id"], "tenant-b", "running", run_id="run-a"
    ) is False
    assert store.get_skill_evaluation("run-a", "tenant-a")["status"] == "queued"
    assert store.get_skill_version("tenant-a", "scoped-eval", "1.0.0")[
        "evaluation_status"
    ] == "queued"

    assert store.update_skill_evaluation_run(
        "run-a", "tenant-a", "running"
    ) is True
    assert store.set_skill_evaluation(
        version["version_id"], "tenant-a", "running", run_id="run-a"
    ) is True


def test_skill_up_never_imports_user_skill_plugin(tmp_path, monkeypatch):
    """Managed Skill evaluation must remain context-only even with tools.py."""
    from agents.ad_agent.evals import skill_up_engine

    skill_dir = tmp_path / "managed-skill"
    skill_dir.mkdir()
    marker = tmp_path / "plugin-imported"
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: evaluated-context\n"
        "description: Context-only evaluation fixture\n"
        "platform: multi_platform\n"
        "---\n\nUse the registered provider Tools.\n",
        encoding="utf-8",
    )
    (skill_dir / "tools.py").write_text(
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('imported')\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AD_AGENT_SKILLS_ROOT", str(skill_dir))
    monkeypatch.setenv(
        "AD_AGENT_BASE_SKILLS_ROOT",
        str(Path(__file__).resolve().parents[1] / "skills"),
    )

    result = skill_up_engine.run({
        "case_id": "managed-plugin-boundary",
        "prompt": "规划一个跨渠道投放",
        "workspace": str(tmp_path / "workspace"),
    })

    assert result["metadata"]["runtime_execution_mode"] == "dry_run"
    assert not marker.exists()


def test_runtime_turn_uses_request_tenant_managed_context():
    from agents.ad_agent.core.auth import RequestPrincipal

    store = AdAgentStore(":memory:")
    runtime = AgentRuntime(require_llm=False, persistence_store=store, offline_mode=True)
    manager = ManagedSkillManager(store)
    manager.create_version("tenant-a", "tenant-skill", "1.0.0", _files("tenant-skill"), "u1")
    manager.publish("tenant-a", "tenant-skill", "1.0.0", runtime=runtime)

    class Parser:
        def __init__(self):
            self.contexts = []

        def parse(self, _text, context):
            self.contexts.append(context.metadata.get("skill_context", {}))
            from agents.ad_agent.core.interfaces import ParsedIntent
            return ParsedIntent("chat", "查询 Meta campaign", [])

    parser = Parser()
    runtime.intent_parser = parser
    runtime.run(
        "查询 Meta campaign",
        principal=RequestPrincipal(
            user_id="u2",
            tenant_id="tenant-b",
            permissions=frozenset({"ads.read"}),
        )
    )
    assert parser.contexts
    assert "tenant-skill" not in parser.contexts[0].get("expert_knowledge", "")


@pytest.mark.parametrize("permissions", ["ads.read", {"ads.read": True}, ["ads.read", 1]])
def test_request_principal_rejects_malformed_permission_claims(permissions):
    from agents.ad_agent.core.auth import RequestPrincipal

    with pytest.raises(ValueError, match="permissions"):
        RequestPrincipal(user_id="u1", permissions=permissions)
