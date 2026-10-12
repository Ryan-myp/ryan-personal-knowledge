from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
WRAPPER = REPOSITORY_ROOT / "scripts" / "ad-agent-python"
DEPENDENCY_CHECK = REPOSITORY_ROOT / "scripts" / "check_ad_agent_dependencies.py"


def _fake_python(path: Path, version: str, name: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    major_minor = ".".join(version.split(".")[:2])
    path.write_text(
        "#!/bin/sh\n"
        'if [ "${1:-}" = "-c" ]; then printf "%s\\n" "' + major_minor + '"; exit 0; fi\n'
        'printf "%s\\n" "' + name + '" > "$SELECTION_MARKER"\n'
        'printf "Python ' + version + '\\n"\n',
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _run_wrapper(
    tmp_path: Path,
    *,
    path_entries: list[Path],
    explicit_python: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    scripts_dir = tmp_path / "repo" / "scripts"
    scripts_dir.mkdir(parents=True)
    wrapper = scripts_dir / "ad-agent-python"
    shutil.copy2(WRAPPER, wrapper)
    marker = tmp_path / "selected-python"
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join([str(entry) for entry in path_entries] + ["/usr/bin", "/bin"])
    env["SELECTION_MARKER"] = str(marker)
    env.pop("AD_AGENT_PYTHON", None)
    if explicit_python is not None:
        env["AD_AGENT_PYTHON"] = str(explicit_python)
    result = subprocess.run(
        [str(wrapper), "--version"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        check=False,
        text=True,
    )
    result.selection_marker = marker  # type: ignore[attr-defined]
    return result


def test_wrapper_prefers_repository_virtualenv(tmp_path: Path) -> None:
    venv_python = _fake_python(
        tmp_path / "repo" / ".venv" / "bin" / "python",
        "3.13.4",
        "project-venv",
    )
    fallback_dir = tmp_path / "fallback"
    _fake_python(fallback_dir / "python3.13", "3.13.2", "path-python")

    result = _run_wrapper(tmp_path, path_entries=[fallback_dir])

    assert result.returncode == 0
    assert result.selection_marker.read_text(encoding="utf-8").strip() == "project-venv"
    assert venv_python.exists()


def test_explicit_python_override_takes_precedence(tmp_path: Path) -> None:
    _fake_python(
        tmp_path / "repo" / ".venv" / "bin" / "python",
        "3.13.4",
        "project-venv",
    )
    fallback_dir = tmp_path / "fallback"
    _fake_python(fallback_dir / "python3.13", "3.13.2", "path-python")
    explicit = _fake_python(tmp_path / "custom-python", "3.13.7", "explicit-python")

    result = _run_wrapper(
        tmp_path,
        path_entries=[fallback_dir],
        explicit_python=explicit,
    )

    assert result.returncode == 0
    assert result.selection_marker.read_text(encoding="utf-8").strip() == "explicit-python"


def test_wrapper_rejects_wrong_version_in_repository_virtualenv(tmp_path: Path) -> None:
    _fake_python(
        tmp_path / "repo" / ".venv" / "bin" / "python",
        "3.12.8",
        "wrong-project-venv",
    )
    fallback_dir = tmp_path / "fallback"
    _fake_python(fallback_dir / "python3.13", "3.13.2", "path-python")

    result = _run_wrapper(tmp_path, path_entries=[fallback_dir])

    assert result.returncode == 2
    assert "requires Python 3.13, got Python 3.12" in result.stderr


def test_wrapper_does_not_fall_back_to_global_python_without_project_venv(
    tmp_path: Path,
) -> None:
    fallback_dir = tmp_path / "fallback"
    _fake_python(fallback_dir / "python3.13", "3.13.2", "path-python")

    result = _run_wrapper(tmp_path, path_entries=[fallback_dir])

    assert result.returncode == 127
    assert "make ad-agent-install" in result.stderr
    assert not result.selection_marker.exists()


def test_wrapper_checks_dependencies_before_running_project_command(
    tmp_path: Path,
) -> None:
    scripts_dir = tmp_path / "repo" / "scripts"
    scripts_dir.mkdir(parents=True)
    wrapper = scripts_dir / "ad-agent-python"
    shutil.copy2(WRAPPER, wrapper)
    explicit = tmp_path / "custom-python"
    payload_marker = tmp_path / "payload-ran"
    explicit.write_text(
        "#!/bin/sh\n"
        'if [ "${1:-}" = "-c" ]; then printf "3.13\\n"; exit 0; fi\n'
        'case "${1:-}" in */check_ad_agent_dependencies.py) '
        'echo "dependency preflight blocked" >&2; exit 23 ;; esac\n'
        f'touch "{payload_marker}"\n',
        encoding="utf-8",
    )
    explicit.chmod(0o755)
    env = os.environ.copy()
    env["AD_AGENT_PYTHON"] = str(explicit)

    result = subprocess.run(
        [str(wrapper), "-m", "uvicorn"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 23
    assert "dependency preflight blocked" in result.stderr
    assert not payload_marker.exists()


def test_dependency_check_reports_missing_requirement_with_install_hint(
    tmp_path: Path,
) -> None:
    package_name = f"codex-missing-{uuid4().hex}"
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(f"{package_name}>=1.0\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(DEPENDENCY_CHECK), "--requirements", str(requirements)],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 1
    assert package_name in result.stderr
    assert "make ad-agent-install" in result.stderr


def test_dependency_check_explains_explicit_interpreter_override(
    tmp_path: Path,
) -> None:
    package_name = f"codex-missing-{uuid4().hex}"
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(f"{package_name}>=1.0\n", encoding="utf-8")
    env = os.environ.copy()
    env["AD_AGENT_PYTHON"] = "/usr/local/bin/python3.13"

    result = subprocess.run(
        [
            sys.executable,
            str(DEPENDENCY_CHECK),
            "--requirements",
            str(requirements),
        ],
        capture_output=True,
        check=False,
        text=True,
        env=env,
    )

    assert result.returncode == 1
    assert "AD_AGENT_PYTHON is set" in result.stderr
    assert "unset AD_AGENT_PYTHON" in result.stderr
    assert "make ad-agent-install" in result.stderr


def test_dependency_check_accepts_installed_requirement(tmp_path: Path) -> None:
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("pytest>=7.0.0\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(DEPENDENCY_CHECK), "--requirements", str(requirements)],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_make_preserves_explicit_ad_agent_python_override(tmp_path: Path) -> None:
    explicit = _fake_python(tmp_path / "custom-python", "3.13.7", "make-override")
    marker = tmp_path / "selected-python"
    env = os.environ.copy()
    env["AD_AGENT_PYTHON"] = str(explicit)
    env["SELECTION_MARKER"] = str(marker)

    result = subprocess.run(
        ["make", "--no-print-directory", "-s", "ad-agent-python-version"],
        cwd=REPOSITORY_ROOT,
        env=env,
        capture_output=True,
        check=False,
        text=True,
        timeout=5,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "Python 3.13.7"
    assert marker.read_text(encoding="utf-8").strip() == "make-override"


def test_install_rejects_wrong_bootstrap_version_before_creating_venv(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    venv_marker = tmp_path / "venv-created"
    bootstrap = bin_dir / "python312"
    bootstrap.write_text(
        "#!/bin/sh\n"
        'if [ "${1:-}" = "-c" ]; then printf "3.12\\n"; exit 0; fi\n'
        'if [ "${1:-}" = "-m" ] && [ "${2:-}" = "venv" ]; then '
        f'touch "{venv_marker}"; fi\n'
        'printf "Python 3.12.9\\n"\n',
        encoding="utf-8",
    )
    bootstrap.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join([str(bin_dir), env.get("PATH", "")])

    result = subprocess.run(
        [
            "make",
            "--no-print-directory",
            "-s",
            "-f",
            str(REPOSITORY_ROOT / "Makefile"),
            "ad-agent-install",
            "AD_AGENT_BOOTSTRAP_PYTHON=python312",
            "AD_AGENT_VENV_PYTHON=.venv/bin/python",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        check=False,
        text=True,
        timeout=5,
    )

    assert result.returncode == 2
    assert "Python 3.12" in result.stderr
    assert "Python 3.13" in result.stderr
    assert not venv_marker.exists()
    assert not (tmp_path / ".venv").exists()
