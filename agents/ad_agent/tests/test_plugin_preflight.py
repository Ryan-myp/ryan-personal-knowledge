import json

from agents.ad_agent.core.plugin_package import build_plugin_manifest
from agents.ad_agent.core.plugin_preflight import build_plugin_preflight
from agents.ad_agent.core.plugins import PluginManifest


def _package(tmp_path, *, executable=False, signing_key=None):
    manifest = PluginManifest(
        plugin_id="preflight-plugin",
        version="1.0.0",
        kinds=("skill",),
        source="trusted" if executable else "managed",
        trusted=executable,
        executable=executable,
    )
    files = {"SKILL.md": b"---\nname: preflight\n---\nUse context.\n"}
    document = build_plugin_manifest(manifest, files, signing_key=signing_key)
    (tmp_path / "SKILL.md").write_bytes(files["SKILL.md"])
    (tmp_path / "plugin.manifest.json").write_text(json.dumps(document), encoding="utf-8")
    return tmp_path


def test_managed_unsigned_package_can_be_preflighted_without_execution(tmp_path):
    report = build_plugin_preflight(_package(tmp_path))
    assert report["status"] == "ready_for_reviewed_deployment"
    assert report["signature_verified"] is False
    assert report["network_called"] is False


def test_executable_package_requires_signature_when_deployment_enforces_it(tmp_path):
    report = build_plugin_preflight(
        _package(tmp_path, executable=True),
        require_signature=True,
    )
    assert report["status"] == "blocked"
    assert report["signature_verified"] is False
    assert any("signature" in issue for issue in report["issues"])
