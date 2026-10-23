import plistlib
import io
from pathlib import Path
from types import SimpleNamespace

import pytest

from agents.deployments.advertising import local_service
from agents.deployments.advertising.local_service import (
    LocalServiceConfig, build_manifest, owns_listener, write_manifest,
)


def config(tmp_path):
    root = tmp_path / "project with spaces"
    (root / "scripts").mkdir(parents=True)
    (root / "scripts/ad-agent-python").write_text("#!/bin/sh\n", encoding="utf-8")
    (root / "agents/ad_agent").mkdir(parents=True)
    profile = root / "agents/ad_agent/config.test-live.yaml"
    profile.write_text("execution_mode: dry_run\n", encoding="utf-8")
    return LocalServiceConfig(
        root=root, home=tmp_path / "home", config_path=profile,
        database_path=root / "agents/ad_agent/ad_agent.db",
    )


def test_launch_agent_preserves_data_paths_and_uses_one_worker_without_secrets(tmp_path):
    spec = config(tmp_path)
    manifest = build_manifest(spec)
    assert manifest["WorkingDirectory"] == str(spec.root)
    assert manifest["KeepAlive"] is True
    assert manifest["RunAtLoad"] is True
    args = manifest["ProgramArguments"]
    assert args[0] == str(spec.root / "scripts/ad-agent-python")
    assert args[args.index("--host") + 1] == "0.0.0.0"
    assert args[args.index("--port") + 1] == "8766"
    assert "--workers" not in args
    environment = manifest["EnvironmentVariables"]
    assert environment["AD_AGENT_DB_PATH"] == str(spec.database_path)
    assert environment["AD_AGENT_CONFIG_PATH"] == str(spec.config_path)
    assert not ({"OPENAI_API_KEY", "AD_AGENT_API_KEY", "AD_AGENT_ENABLE_LIVE"} & set(environment))


def test_manifest_is_private_and_foreign_manifest_is_never_overwritten(tmp_path):
    spec = config(tmp_path)
    path = write_manifest(spec)
    assert path.stat().st_mode & 0o777 == 0o600
    assert plistlib.loads(path.read_bytes()) == build_manifest(spec)
    manifest = build_manifest(spec)
    manifest["WorkingDirectory"] = "/another/project"
    path.write_bytes(plistlib.dumps(manifest))
    with pytest.raises(RuntimeError, match="another project"):
        write_manifest(spec)
    assert plistlib.loads(path.read_bytes())["WorkingDirectory"] == "/another/project"


def test_takeover_requires_matching_user_project_and_command(tmp_path):
    spec = config(tmp_path)
    command = "python -m uvicorn agents.deployments.advertising.api_server:app --host 0.0.0.0 --port 8766"
    assert owns_listener(spec, command, spec.root, 100, 100)
    assert not owns_listener(spec, command, Path("/another/project"), 100, 100)
    assert not owns_listener(spec, command, spec.root, 100, 101)
    assert not owns_listener(spec, "python unrelated.py --port 8766", spec.root, 100, 100)
    assert not owns_listener(spec, command.replace("8766", "8765"), spec.root, 100, 100)


@pytest.mark.parametrize("port", [0, 65536, True])
def test_invalid_service_port_is_rejected(tmp_path, port):
    with pytest.raises(ValueError):
        LocalServiceConfig(root=tmp_path, home=tmp_path, port=port)


def test_install_refuses_an_occupied_port_without_explicit_takeover(tmp_path, monkeypatch):
    spec = config(tmp_path)
    monkeypatch.setattr(local_service, "_listener_pids", lambda _port: [123])
    monkeypatch.setattr(
        local_service, "_command", lambda *_args, **_kwargs: SimpleNamespace(returncode=1),
    )
    with pytest.raises(RuntimeError, match="already in use"):
        local_service.install(spec)
    assert not spec.manifest_path.exists()


def test_install_bootstraps_only_the_owned_manifest(tmp_path, monkeypatch):
    spec = config(tmp_path)
    commands = []

    def run(arguments, **_kwargs):
        commands.append(arguments)
        return SimpleNamespace(returncode=1 if "print" in arguments else 0)

    monkeypatch.setattr(local_service, "_command", run)
    monkeypatch.setattr(local_service, "_listener_pids", lambda _port: [])
    monkeypatch.setattr(local_service, "health", lambda _config: True)
    local_service.install(spec)
    assert commands[-1] == [
        "/bin/launchctl", "bootstrap", f"gui/{local_service.os.getuid()}",
        str(spec.manifest_path),
    ]


def test_takeover_does_not_signal_an_unowned_listener(tmp_path, monkeypatch):
    spec = config(tmp_path)
    sent = []
    monkeypatch.setattr(local_service, "_listener_pids", lambda _port: [123])
    monkeypatch.setattr(local_service.os, "kill", lambda *_args: sent.append(True))

    def run(arguments, **_kwargs):
        output = "unrelated process"
        if "uid=" in arguments:
            output = str(local_service.os.getuid())
        if "-Fn" in arguments:
            output = "n/another/project\n"
        return SimpleNamespace(stdout=output, returncode=0)

    monkeypatch.setattr(local_service, "_command", run)
    with pytest.raises(RuntimeError, match="another project"):
        local_service._take_over(spec)
    assert sent == []


def test_failed_manifest_replace_keeps_the_previous_manifest(tmp_path, monkeypatch):
    spec = config(tmp_path)
    path = write_manifest(spec)
    previous = path.read_bytes()

    def fail(*_args):
        raise OSError("simulated disk failure")

    monkeypatch.setattr(local_service.os, "replace", fail)
    with pytest.raises(OSError):
        write_manifest(spec)
    assert path.read_bytes() == previous
    assert list(path.parent.iterdir()) == [path]


@pytest.mark.parametrize("body,expected", [
    (b'{"service":"ad-agent","state":"ready"}', True),
    (b'{"service":"another-service","state":"ready"}', False),
    (b"not JSON", False),
    (b"[]", False),
])
def test_health_checks_only_the_local_service_identity(tmp_path, monkeypatch, body, expected):
    seen = []

    def open_url(url, timeout):
        seen.append((url, timeout))
        return io.BytesIO(body)

    monkeypatch.setattr(local_service, "urlopen", open_url)
    assert local_service.health(config(tmp_path)) is expected
    assert seen == [("http://127.0.0.1:8766/health", 2)]


def test_health_connection_failure_is_explicitly_unhealthy(tmp_path, monkeypatch):
    def fail(*_args, **_kwargs):
        raise OSError("connection closed")
    monkeypatch.setattr(local_service, "urlopen", fail)
    assert local_service.health(config(tmp_path)) is False


def test_successful_takeover_only_stops_the_verified_listener(tmp_path, monkeypatch):
    spec = config(tmp_path)
    listeners = iter([[123], []])
    signals = []
    monkeypatch.setattr(local_service, "_listener_pids", lambda _port: next(listeners))
    monkeypatch.setattr(local_service.os, "kill", lambda *args: signals.append(args))

    def run(arguments, **_kwargs):
        if "uid=" in arguments:
            output = str(local_service.os.getuid())
        elif "-Fn" in arguments:
            output = f"n{spec.root}\n"
        else:
            output = f"python -m uvicorn {local_service.APPLICATION} --port 8766"
        return SimpleNamespace(stdout=output, returncode=0)

    monkeypatch.setattr(local_service, "_command", run)
    local_service._take_over(spec)
    assert signals == [(123, local_service.signal.SIGTERM)]


@pytest.mark.parametrize("action", ["install", "restart", "stop", "uninstall", "status"])
def test_cli_lifecycle_uses_only_owned_user_job(tmp_path, monkeypatch, action):
    spec = config(tmp_path)
    write_manifest(spec)
    commands = []
    monkeypatch.setattr(local_service.sys, "argv", ["local-service", action])
    monkeypatch.setattr(local_service, "_configuration", lambda _args: spec)
    monkeypatch.setattr(local_service, "health", lambda _config: True)
    monkeypatch.setattr(local_service, "install", lambda *_args, **_kwargs: None)

    def run(arguments, **_kwargs):
        commands.append(arguments)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(local_service, "_command", run)
    assert local_service.main() == 0
    for command in commands:
        assert command[0] == "/bin/launchctl"
        assert command[-1] == f"gui/{local_service.os.getuid()}/{local_service.LABEL}"
    assert spec.manifest_path.exists() is (action != "uninstall")
