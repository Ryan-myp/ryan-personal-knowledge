"""Tests for the common Agent Harness plugin contract."""

import json

import pytest

from agents.ad_agent import AgentRuntime, create_meta_capability
from agents.ad_agent.core.plugins import (
    PluginKind,
    PluginLoader,
    PluginManifest,
    PluginRegistry,
    PluginState,
    manifest_for_managed_skill,
)
from agents.ad_agent.core.plugin_package import (
    PluginPackageError,
    build_plugin_manifest,
    validate_plugin_directory,
)


class _Lifecycle:
    def __init__(self, events):
        self.events = events

    def load(self, _registry):
        self.events.append("load")

    def activate(self, _registry):
        self.events.append("activate")

    def deactivate(self, _registry):
        self.events.append("deactivate")

    def unload(self, _registry):
        self.events.append("unload")


class _FailingLifecycle(_Lifecycle):
    def activate(self, _registry):
        self.events.append("activate-failed")
        raise RuntimeError("upgrade rejected")


def _trusted_manifest(plugin_id, *, dependencies=None):
    return PluginManifest(
        plugin_id=plugin_id,
        version="1.2.0",
        kinds=(PluginKind.FEATURE.value,),
        source="trusted",
        trusted=True,
        executable=True,
        dependencies=dependencies or {},
    )


def test_plugin_manifest_is_versioned_and_serializable():
    manifest = PluginManifest(
        plugin_id="business:campaigns",
        version="1.2",
        kinds=("skill", "feature"),
        metadata={"owner": "growth"},
    )

    assert manifest.version == "1.2.0"
    assert manifest.to_dict()["kinds"] == ["skill", "feature"]
    assert manifest.to_dict()["metadata"] == {"owner": "growth"}


def test_untrusted_or_managed_executable_plugin_is_rejected():
    with pytest.raises(ValueError, match="trusted"):
        PluginManifest(
            plugin_id="unsafe-plugin",
            version="1.0.0",
            kinds=("tool_capability",),
            executable=True,
        )

    with pytest.raises(ValueError, match="cannot be executable"):
        PluginManifest(
            plugin_id="managed-plugin",
            version="1.0.0",
            kinds=("skill",),
            source="managed",
            trusted=True,
            executable=True,
        )

    with pytest.raises(ValueError, match="protected field"):
        PluginManifest(
            plugin_id="metadata-leak",
            version="1.0.0",
            kinds=("skill",),
            metadata={"nested": {"client_secret": "never"}},
        )


def test_plugin_activation_is_dependency_ordered_and_lifecycle_managed():
    events = []
    registry = PluginRegistry()
    registry.register(_trusted_manifest("base-plugin"), lifecycle=_Lifecycle(events))
    registry.register(
        _trusted_manifest("feature-plugin", dependencies={"base-plugin": "^1.0"}),
        lifecycle=_Lifecycle(events),
    )

    registry.activate("feature-plugin")
    assert events == ["load", "load", "activate", "activate"]
    assert [record.state for record in registry.list()] == [
        PluginState.ACTIVE,
        PluginState.ACTIVE,
    ]

    with pytest.raises(ValueError, match="active dependents"):
        registry.deactivate("base-plugin")

    registry.unregister("feature-plugin")
    assert events[-2:] == ["deactivate", "unload"]
    registry.unregister("base-plugin")
    assert events[-2:] == ["deactivate", "unload"]


def test_managed_skill_manifest_is_advisory_only():
    manifest = manifest_for_managed_skill("tenant-a", "weekly-report", "2.1")

    assert manifest.source == "managed"
    assert manifest.executable is False
    assert manifest.trusted is False
    assert manifest.metadata["tenant_id"] == "tenant-a"


def test_manifest_loader_does_not_enable_untrusted_executable_code():
    registry = PluginRegistry()
    loader = PluginLoader(registry)
    with pytest.raises(PermissionError, match="trusted deployment"):
        loader.load_manifest({
            "plugin_id": "external-code",
            "version": "1.0.0",
            "kinds": ["tool_capability"],
            "source": "external",
            "trusted": True,
            "executable": True,
            "entrypoint": "tools.py",
        })

    record = loader.load_manifest({
        "plugin_id": "managed-context",
        "version": "1.0.0",
        "kinds": ["skill"],
        "source": "managed",
        "metadata": {"advisory_only": True},
    })
    assert record.state == PluginState.ACTIVE


def test_trusted_plugin_permissions_are_deployment_approved():
    manifest = _trusted_manifest("permissioned-plugin")
    manifest = PluginManifest(
        **{**manifest.to_dict(), "permissions": ["ads.read", "plugins.health"]}
    )
    with pytest.raises(PermissionError, match="deployment approval"):
        PluginLoader(PluginRegistry(), allow_trusted_source=True).install(manifest)

    record = PluginLoader(
        PluginRegistry(),
        allow_trusted_source=True,
        approved_permissions={"ads.read", "plugins.health"},
    ).install(manifest)
    assert record.state == PluginState.ACTIVE


def test_trusted_plugin_upgrade_restores_previous_version_on_failure():
    events = []
    registry = PluginRegistry()
    loader = PluginLoader(registry, allow_trusted_source=True)
    old_manifest = _trusted_manifest("upgradeable-plugin")
    loader.install(old_manifest, contribution="old", lifecycle=_Lifecycle(events))
    new_manifest = PluginManifest(
        plugin_id="upgradeable-plugin",
        version="2.0.0",
        kinds=(PluginKind.FEATURE.value,),
        source="trusted",
        trusted=True,
        executable=True,
    )

    with pytest.raises(RuntimeError, match="upgrade rejected"):
        loader.upgrade(
            new_manifest,
            contribution="new",
            lifecycle=_FailingLifecycle(events),
        )

    restored = registry.get("upgradeable-plugin")
    assert restored.manifest.version == old_manifest.version
    assert restored.contribution == "old"
    assert restored.state == PluginState.ACTIVE


def test_plugin_package_manifest_validates_files_and_signature(tmp_path):
    manifest = PluginManifest(
        plugin_id="managed:reporting",
        version="1.0.0",
        kinds=("skill",),
        source="managed",
    )
    files = {
        "SKILL.md": b"---\nname: reporting\nversion: 1.0.0\n---\nUse reports.\n",
        "references/metrics.md": b"CTR is clicks divided by impressions.\n",
    }
    document = build_plugin_manifest(manifest, files, signing_key="package-key")
    for path, data in files.items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (tmp_path / "plugin.manifest.json").write_text(
        json.dumps(document), encoding="utf-8"
    )

    package = validate_plugin_directory(
        tmp_path,
        signing_key="package-key",
        require_signature=True,
    )
    assert package.manifest.plugin_id == "managed:reporting"
    assert package.signature_verified is True

    (tmp_path / "references/metrics.md").write_bytes(b"tampered")
    with pytest.raises(PluginPackageError, match="digest mismatch"):
        validate_plugin_directory(tmp_path, signing_key="package-key", require_signature=True)


def test_plugin_package_loader_never_imports_package_files(tmp_path):
    marker = tmp_path / "imported"
    files = {
        "tools.py": (
            f"from pathlib import Path\nPath({str(marker)!r}).write_text('bad')\n"
        ).encode(),
    }
    manifest = PluginManifest(
        plugin_id="managed:code-shaped",
        version="1.0.0",
        kinds=("skill",),
        source="managed",
    )
    (tmp_path / "tools.py").write_bytes(files["tools.py"])
    (tmp_path / "plugin.manifest.json").write_text(
        json.dumps(build_plugin_manifest(manifest, files)), encoding="utf-8"
    )

    registry = PluginRegistry()
    record = PluginLoader(registry).load_package(str(tmp_path))
    assert record.state == PluginState.ACTIVE
    assert not marker.exists()


def test_runtime_publishes_capability_and_builtin_extensions_to_one_registry():
    runtime = AgentRuntime(
        require_llm=False,
        offline_mode=True,
        enforce_account_scope=False,
    )
    runtime.register_capability(create_meta_capability())

    plugins = {item["manifest"]["plugin_id"]: item for item in runtime.list_plugins()}
    assert plugins["capability:meta"]["state"] == "active"
    assert "tool_capability" in plugins["capability:meta"]["manifest"]["kinds"]
    assert plugins["renderer:ad-agent"]["state"] == "active"
    assert any(
        item["manifest"]["plugin_id"].startswith("feature:")
        for item in plugins.values()
    )
