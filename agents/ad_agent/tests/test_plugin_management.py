"""Plugin package control-plane tests; no provider or package code is executed."""

import json

import pytest
from fastapi.testclient import TestClient

from agents.ad_agent import AgentRuntime
from agents.ad_agent.persistence.store import AdAgentStore
from agents.ad_agent.plugin_management import PluginPackageManager
from agents.ad_agent.core.plugin_package import PluginPackageError
from agents.ad_agent import api_server


def _manifest(plugin_id="external:reporting", version="1.0.0"):
    return {
        "plugin_id": plugin_id,
        "version": version,
        "kinds": ["feature"],
        "source": "external",
        "description": "advisory deployment candidate",
    }


def _files(marker="not-imported"):
    return {
        "tools.py": f"from pathlib import Path\nPath({marker!r}).write_text('bad')\n",
        "README.md": "This is package data, not an execution hook.\n",
    }


def test_plugin_package_versions_are_immutable_and_tenant_scoped(tmp_path):
    store = AdAgentStore(str(tmp_path / "plugins.db"))
    manager = PluginPackageManager(store)

    first = manager.create_package(
        "tenant-a", _manifest(), _files(), "editor-a"
    )
    assert first["status"] == "validated"
    assert first["files"] == ["README.md", "tools.py"]
    assert manager.get_package("tenant-b", "external:reporting", "1.0.0") is None

    with pytest.raises(PluginPackageError, match="already exists"):
        manager.create_package("tenant-a", _manifest(), _files("different"), "editor-a")

    second = manager.create_package(
        "tenant-a", _manifest(version="2.0.0"), _files("second"), "editor-a"
    )
    assert manager.activate("tenant-a", "external:reporting", "2.0.0")["status"] == "active"
    assert manager.get_package("tenant-a", "external:reporting")["version"] == "2.0.0"

    # Selecting the older immutable snapshot is the rollback operation.
    rollback = manager.activate("tenant-a", "external:reporting", "1.0.0")
    assert rollback["version"] == first["version"]
    assert manager.get_package("tenant-a", "external:reporting")["version"] == "1.0.0"
    assert manager.deactivate("tenant-a", "external:reporting", "1.0.0")["status"] == "inactive"
    assert manager.get_package("tenant-a", "external:reporting") is None

    removed = manager.uninstall("tenant-a", "external:reporting", "2.0.0")
    assert removed["status"] == "uninstalled"
    assert second["package_id"] == removed["package_id"]
    store.close()


def test_plugin_package_activation_never_imports_package_files(tmp_path):
    marker = tmp_path / "imported"
    store = AdAgentStore(":memory:")
    manager = PluginPackageManager(store)
    manager.create_package(
        "tenant-a", _manifest(), _files(str(marker)), "editor-a"
    )
    result = manager.activate("tenant-a", "external:reporting", "1.0.0")
    assert result["runtime_loaded"] is False
    assert not marker.exists()
    store.close()


def test_plugin_package_release_requires_active_compatible_dependencies():
    store = AdAgentStore(":memory:")
    manager = PluginPackageManager(store)
    manager.create_package(
        "tenant-a", _manifest("external:feature-base", "1.0.0"), _files(), "editor"
    )
    dependent_manifest = _manifest("external:feature-child", "1.0.0")
    dependent_manifest["dependencies"] = {"external:feature-base": "^1.0"}
    manager.create_package("tenant-a", dependent_manifest, _files(), "editor")

    with pytest.raises(PluginPackageError, match="not active"):
        manager.activate("tenant-a", "external:feature-child", "1.0.0")
    manager.activate("tenant-a", "external:feature-base", "1.0.0")
    assert manager.activate("tenant-a", "external:feature-child", "1.0.0")["status"] == "active"
    store.close()


def test_plugin_package_api_is_tenant_scoped_and_control_plane_only(monkeypatch, tmp_path):
    store = AdAgentStore(str(tmp_path / "api.db"))
    runtime = AgentRuntime(
        require_llm=False, persistence_store=store, offline_mode=True
    )
    monkeypatch.setattr(api_server, "runtime", runtime)
    monkeypatch.setattr(api_server, "API_KEY", "")
    monkeypatch.setattr(api_server, "ALLOW_UNAUTHENTICATED", False)
    monkeypatch.setenv(
        "AD_AGENT_API_KEY_PRINCIPALS",
        json.dumps({
            "tenant-a-key": {
                "user_id": "editor-a",
                "tenant_id": "tenant-a",
                "permissions": ["plugins.read", "plugins.write"],
            },
            "tenant-b-key": {
                "user_id": "editor-b",
                "tenant_id": "tenant-b",
                "permissions": ["plugins.read", "plugins.write"],
            },
        }),
    )
    payload = {"manifest": _manifest(), "files": _files()}

    with TestClient(api_server.app) as client:
        response = client.post(
            "/plugins/packages", headers={"X-API-Key": "tenant-a-key"}, json=payload
        )
        assert response.status_code == 201
        response = client.get(
            "/plugins/packages", headers={"X-API-Key": "tenant-b-key"}
        )
        assert response.status_code == 200
        assert response.json()["packages"] == []
        response = client.post(
            "/plugins/packages/external:reporting/versions/1.0.0/activate",
            headers={"X-API-Key": "tenant-a-key"},
        )
        assert response.status_code == 200
        assert response.json()["runtime_loaded"] is False
        response = client.get(
            "/plugins/packages/external:reporting/versions/1.0.0",
            headers={"X-API-Key": "tenant-b-key"},
        )
        assert response.status_code == 404
        response = client.delete(
            "/plugins/packages/external:reporting/versions/1.0.0",
            headers={"X-API-Key": "tenant-a-key"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "uninstalled"

    assert runtime.plugin_registry.list()  # built-in lifecycle is unaffected
    store.close()
