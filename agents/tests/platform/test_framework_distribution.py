"""Build and run framework artifacts without any advertising application code."""

from email.parser import Parser
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import yaml


ROOT = Path(__file__).resolve().parents[3]


def test_framework_wheels_run_without_advertising(tmp_path):
    source_root = tmp_path / "source"
    package_root = source_root / "agents"
    package_root.mkdir(parents=True)
    shutil.copy2(ROOT / "agents/__init__.py", package_root)
    for package in ("agent_harness", "agent_platform"):
        shutil.copytree(
            ROOT / "agents" / package,
            package_root / package,
            ignore=shutil.ignore_patterns("build", "*.egg-info", "__pycache__"),
        )
    build_root = source_root / "packaging/agent-platform"
    build_root.mkdir(parents=True)
    shutil.copy2(ROOT / "packaging/agent-platform/pyproject.toml", build_root)
    wheel_dir = tmp_path / "wheels"
    wheel_dir.mkdir()
    for path in (package_root / "agent_harness", build_root):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; from setuptools.build_meta import build_wheel; build_wheel(sys.argv[1])",
                str(wheel_dir),
            ],
            cwd=path,
            env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path[1:])},
            text=True,
            capture_output=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr
    install_root = tmp_path / "installed"
    for path in wheel_dir.glob("*.whl"):
        with zipfile.ZipFile(path) as wheel:
            if path.name.startswith("agent_harness-"):
                metadata_path = next(
                    name for name in wheel.namelist() if name.endswith("/METADATA")
                )
                metadata = Parser().parsestr(wheel.read(metadata_path).decode("utf-8"))
                assert any(
                    requirement.startswith("PyYAML")
                    for requirement in metadata.get_all("Requires-Dist", [])
                )
            wheel.extractall(install_root)
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            """
import sys
sys.path.insert(0, sys.argv[1])
sys.path.append(sys.argv[2])
import importlib.util
assert importlib.util.find_spec("agents.applications") is None
assert importlib.util.find_spec("agents.tools") is None
from agents.agent_harness import TurnRequest
from agents.agent_platform.examples.ticket_support import create_ticket_support_application
app = create_ticket_support_application(model=lambda *_: "standalone")
assert app.run(TurnRequest(user_input="hello")).reply == "standalone"
app.close()
""",
            str(install_root),
            str(Path(yaml.__file__).resolve().parent.parent),
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
