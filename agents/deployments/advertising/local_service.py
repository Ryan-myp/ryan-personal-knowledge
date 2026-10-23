"""User-owned macOS service management; never changes application data or keys."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import ipaddress
import json
import os
from pathlib import Path
import plistlib
import shlex
import signal
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import urlopen

from .local_config import load_default_local_env


LABEL = "com.ryan.ad-agent"
APPLICATION = "agents.deployments.advertising.api_server:app"
ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class LocalServiceConfig:
    root: Path
    home: Path
    host: str = "0.0.0.0"
    port: int = 8766
    config_path: Path | None = None
    database_path: Path | None = None

    def __post_init__(self):
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValueError("port must be between 1 and 65535")
        ipaddress.ip_address(self.host)
        root = self.root.resolve()
        object.__setattr__(self, "root", root)
        object.__setattr__(self, "home", self.home.expanduser().resolve())
        for name, default in (
            ("config_path", "agents/ad_agent/config.yaml"),
            ("database_path", "agents/ad_agent/ad_agent.db"),
        ):
            path = Path(getattr(self, name) or default).expanduser()
            object.__setattr__(self, name, (root / path).resolve())

    @property
    def manifest_path(self) -> Path:
        return self.home / "Library/LaunchAgents" / (LABEL + ".plist")

    @property
    def log_directory(self) -> Path:
        return self.home / "Library/Logs/ryan-ad-agent"


def build_manifest(config: LocalServiceConfig) -> dict:
    """Use explicit paths and the existing ignored local credential loader."""
    return {
        "Label": LABEL,
        "ProgramArguments": [
            str(config.root / "scripts/ad-agent-python"), "-m", "uvicorn",
            APPLICATION, "--host", config.host, "--port", str(config.port),
        ],
        "WorkingDirectory": str(config.root),
        "EnvironmentVariables": {
            "AD_AGENT_CONFIG_PATH": str(config.config_path),
            "AD_AGENT_DB_PATH": str(config.database_path),
            "PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        },
        "RunAtLoad": True, "KeepAlive": True, "ThrottleInterval": 5,
        "ProcessType": "Background",
        "StandardOutPath": str(config.log_directory / "stdout.log"),
        "StandardErrorPath": str(config.log_directory / "stderr.log"),
    }


def _assert_manifest_owner(config: LocalServiceConfig) -> None:
    path = config.manifest_path
    if not path.exists():
        return
    if path.is_symlink():
        raise RuntimeError("refusing a symlinked service manifest")
    manifest = plistlib.loads(path.read_bytes())
    expected = build_manifest(config)
    if (
        manifest.get("Label") != LABEL
        or manifest.get("WorkingDirectory") != expected["WorkingDirectory"]
        or manifest.get("ProgramArguments", [])[:4] != expected["ProgramArguments"][:4]
    ):
        raise RuntimeError("service manifest belongs to another project")


def write_manifest(config: LocalServiceConfig) -> Path:
    """Atomically publish only this project's private user service manifest."""
    _assert_manifest_owner(config)
    if not (config.root / "scripts/ad-agent-python").is_file():
        raise RuntimeError("project Python wrapper is missing")
    if not config.config_path.is_file():
        raise RuntimeError("selected configuration file is missing")
    path = config.manifest_path
    path.parent.mkdir(parents=True, exist_ok=True)
    config.log_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name in ("stdout.log", "stderr.log"):
        log_path = config.log_directory / name
        if log_path.is_symlink():
            raise RuntimeError("refusing a symlinked service log")
        log_path.touch(mode=0o600, exist_ok=True)
        log_path.chmod(0o600)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        temporary_path = Path(temporary.name)
        try:
            temporary.write(plistlib.dumps(build_manifest(config)))
            temporary.flush()
            os.fsync(temporary.fileno())
            os.replace(temporary_path, path)
        finally:
            temporary_path.unlink(missing_ok=True)
    return path


def _command(arguments: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(arguments, capture_output=True, text=True, timeout=20)
    if check and result.returncode:
        raise RuntimeError(f"{Path(arguments[0]).name} failed (exit {result.returncode})")
    return result


def owns_listener(
    config: LocalServiceConfig, command: str, cwd: Path, uid: int, expected_uid: int,
) -> bool:
    arguments = shlex.split(command)
    try:
        port = arguments[arguments.index("--port") + 1]
    except (ValueError, IndexError):
        return False
    return (
        uid == expected_uid and cwd.resolve() == config.root
        and APPLICATION in arguments and "uvicorn" in arguments
        and port == str(config.port)
    )


def _listener_pids(port: int) -> list[int]:
    result = _command([
        "/usr/sbin/lsof", "-nP", "-t", f"-iTCP:{port}", "-sTCP:LISTEN",
    ], check=False)
    if result.returncode not in {0, 1}:
        raise RuntimeError("unable to inspect service port ownership")
    return sorted({int(value) for value in result.stdout.split()})


def _take_over(config: LocalServiceConfig) -> None:
    pids = _listener_pids(config.port)
    for pid in pids:
        command = _command(["/bin/ps", "-p", str(pid), "-o", "command="]).stdout.strip()
        uid = int(_command(["/bin/ps", "-p", str(pid), "-o", "uid="]).stdout.strip())
        output = _command([
            "/usr/sbin/lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn",
        ]).stdout
        cwd = next((Path(line[1:]) for line in output.splitlines() if line.startswith("n")), None)
        if cwd is None or not owns_listener(config, command, cwd, uid, os.getuid()):
            raise RuntimeError("port is owned by another project; nothing was stopped")
    for pid in pids:
        os.kill(pid, signal.SIGTERM)
    _wait_for_port(config.port)


def _wait_for_port(port: int) -> None:
    deadline = time.monotonic() + 20
    while _listener_pids(port):
        if time.monotonic() >= deadline:
            raise RuntimeError("existing service did not stop; takeover aborted")
        time.sleep(0.2)


def health(config: LocalServiceConfig) -> bool:
    host = "127.0.0.1" if config.host == "0.0.0.0" else config.host
    host = f"[{host}]" if ":" in host else host
    try:
        with urlopen(f"http://{host}:{config.port}/health", timeout=2) as response:
            result = json.load(response)
    except (OSError, URLError, ValueError):
        return False
    return (
        isinstance(result, dict)
        and result.get("service") == "ad-agent" and result.get("state") == "ready"
    )


def install(config: LocalServiceConfig, *, take_over: bool = False) -> None:
    target = f"gui/{os.getuid()}/{LABEL}"
    _assert_manifest_owner(config)
    loaded = _command(["/bin/launchctl", "print", target], check=False).returncode == 0
    if _listener_pids(config.port) and not (take_over or loaded):
        raise RuntimeError("port is already in use; verify ownership and use --take-over")
    path = write_manifest(config)
    if loaded:
        _command(["/bin/launchctl", "bootout", target])
        _wait_for_port(config.port)
    if take_over:
        _take_over(config)
    _command(["/bin/launchctl", "enable", target])
    _command(["/bin/launchctl", "bootstrap", f"gui/{os.getuid()}", str(path)])
    deadline = time.monotonic() + 40
    while not health(config):
        if time.monotonic() >= deadline:
            raise RuntimeError("service did not become healthy; inspect private service logs")
        time.sleep(0.5)


def _configuration(args: argparse.Namespace) -> LocalServiceConfig:
    load_default_local_env()
    config_path = os.environ.get("AD_AGENT_CONFIG_PATH")
    database_path = os.environ.get("AD_AGENT_DB_PATH")
    return LocalServiceConfig(
        root=ROOT, home=Path.home(), host=args.host, port=args.port,
        config_path=Path(config_path) if config_path else None,
        database_path=Path(database_path) if database_path else None,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "status", "stop", "restart", "uninstall"))
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--take-over", action="store_true")
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("this local service manager requires macOS")
    target = f"gui/{os.getuid()}/{LABEL}"
    try:
        config = _configuration(args)
        _assert_manifest_owner(config)
        if args.action in {"install", "restart"}:
            install(config, take_over=args.take_over)
        elif args.action in {"stop", "uninstall"}:
            _command(["/bin/launchctl", "disable", target])
            loaded = _command(["/bin/launchctl", "print", target], check=False).returncode == 0
            if loaded:
                _command(["/bin/launchctl", "bootout", target])
            if args.action == "uninstall":
                config.manifest_path.unlink(missing_ok=True)
        loaded = _command(["/bin/launchctl", "print", target], check=False).returncode == 0
        ready = health(config)
        print(json.dumps({"managed": loaded, "healthy": ready, "port": config.port}))
        return 0 if args.action != "status" or (loaded and ready) else 1
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"Local service operation failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
