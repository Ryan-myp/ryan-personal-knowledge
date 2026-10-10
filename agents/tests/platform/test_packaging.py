"""Packaging tests validate the wheel, not only setup metadata."""

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_wheel_excludes_local_state_and_stale_build_outputs(tmp_path):
    build_base = tmp_path / "build"
    stale_files = (
        build_base / "lib" / "agents" / "tests" / "stale_test.py",
        build_base
        / "lib"
        / "agents"
        / "agent_harness"
        / "build"
        / "lib"
        / "stale_module.py",
    )
    for path in stale_files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("stale = True\n", encoding="utf-8")

    egg_info_base = tmp_path / "egg-info"
    egg_info_base.mkdir()
    bdist_dir = tmp_path / "bdist"
    dist_dir = tmp_path / "dist"
    build = subprocess.run(
        [
            sys.executable,
            "setup.py",
            "egg_info",
            "--egg-base",
            str(egg_info_base),
            "build",
            "--build-base",
            str(build_base),
            "bdist_wheel",
            "--bdist-dir",
            str(bdist_dir),
            "--dist-dir",
            str(dist_dir),
        ],
        cwd=REPOSITORY_ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, f"{build.stdout}\n{build.stderr}"

    wheels = list(dist_dir.glob("*.whl"))
    assert len(wheels) == 1
    with zipfile.ZipFile(wheels[0]) as wheel:
        files = set(wheel.namelist())

    assert not any("/tests/" in f"/{path}" for path in files)
    assert not any("/build/" in f"/{path}" for path in files)
    assert not any(
        path.endswith((".db", ".db-shm", ".db-wal", ".sqlite", ".sqlite3"))
        for path in files
    )
    assert not any(Path(path).name == ".env" for path in files)
    assert "agents/ad_agent/.env.example" in files
    assert any(path.startswith("agents/tools/advertising/") for path in files)
    assert any(path.startswith("agents/skills/advertising/") for path in files)
    assert any(path.startswith("agents/knowledge/advertising/") for path in files)
    assert any(path.startswith("agents/deployments/advertising/static/") for path in files)


def test_platform_wheel_excludes_advertising_application(tmp_path):
    platform_root = REPOSITORY_ROOT / "agents" / "agent_platform"
    packaging_root = REPOSITORY_ROOT / "packaging" / "agent-platform"
    assert (packaging_root / "pyproject.toml").is_file()
    source_root = tmp_path / "source"
    package_root = source_root / "agents"
    package_root.mkdir(parents=True)
    shutil.copy2(REPOSITORY_ROOT / "agents" / "__init__.py", package_root)
    shutil.copytree(
        platform_root,
        package_root / "agent_platform",
        ignore=shutil.ignore_patterns("build", "*.egg-info", "__pycache__"),
    )
    build_root = source_root / "packaging" / "agent-platform"
    build_root.mkdir(parents=True)
    shutil.copy2(packaging_root / "pyproject.toml", build_root)
    result = subprocess.run(
        [
            sys.executable, "-c",
            "import sys; from setuptools.build_meta import build_wheel; build_wheel(sys.argv[1])",
            str(tmp_path),
        ],
        cwd=build_root,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path[1:])},
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    wheels = list(tmp_path.glob("agent_platform-*.whl"))
    assert len(wheels) == 1
    with zipfile.ZipFile(wheels[0]) as wheel:
        files = set(wheel.namelist())
    assert "agents/agent_platform/platform.py" in files
    assert not any(path.startswith("agents/applications/") for path in files)
    assert not any(path.startswith("agents/tools/advertising/") for path in files)
    assert not any(path.startswith("agents/deployments/") for path in files)
