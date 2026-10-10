from pathlib import Path
import shutil

from setuptools import setup
from setuptools.command.build_py import build_py


ROOT = Path(__file__).resolve().parent
AGENTS_ROOT = ROOT / "agents"
_DATA_ROOTS = (
    AGENTS_ROOT / "ad_agent",
    AGENTS_ROOT / "applications" / "advertising",
    AGENTS_ROOT / "tools" / "advertising",
    AGENTS_ROOT / "skills" / "advertising",
    AGENTS_ROOT / "knowledge" / "advertising",
    AGENTS_ROOT / "deployments" / "advertising",
)


def _runtime_package_data() -> list[str]:
    paths = []
    for root in _DATA_ROOTS:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in {"__pycache__", "build", "tests"} for part in path.parts):
                continue
            if path.suffix in {".py", ".pyc", ".pyo"} or path.name.lower().endswith(
                (".db", "-wal", "-shm", "-journal", ".sqlite", ".sqlite3")
            ):
                continue
            if path.name == ".env" or path.name.startswith(".env.") and path.name != ".env.example":
                continue
            paths.append(path.relative_to(AGENTS_ROOT).as_posix())
    return sorted(paths)


def _runtime_packages() -> list[str]:
    packages = {"agents"}
    for source in AGENTS_ROOT.rglob("*.py"):
        relative = source.relative_to(AGENTS_ROOT)
        if any(part in {"__pycache__", "build", "tests"} for part in relative.parts):
            continue
        package_parts = relative.parts[:-1]
        for end in range(1, len(package_parts) + 1):
            packages.add("agents." + ".".join(package_parts[:end]))
    return sorted(packages)

class CleanBuildPy(build_py):
    """Prevent stale files from a previous build entering the wheel."""

    def run(self):
        build_lib = Path(self.build_lib)
        if build_lib.exists():
            shutil.rmtree(build_lib)
        super().run()


setup(
    name="ad-agent",
    version="1.0.0",
    description="多渠道广告投放 Agent - 单 Agent + 多 Skills 架构",
    long_description=(ROOT / "agents" / "docs" / "advertising" / "README.md").read_text(
        encoding="utf-8"
    ),
    long_description_content_type="text/markdown",
    author="Ryan",
    packages=_runtime_packages(),
    cmdclass={"build_py": CleanBuildPy},
    include_package_data=False,
    package_data={"agents": _runtime_package_data()},
    python_requires=">=3.13,<3.14",
    install_requires=[
        "requests>=2.28.0",
        "pyjwt>=2.6.0",
        "PyYAML>=6.0",
        "fastapi>=0.100.0",
        "uvicorn>=0.22.0",
        "PyMySQL>=1.1.0",
        "fastmcp>=3.4.0,<4.0.0",
        "openai>=1.0.0,<2.0.0",
    ],
    extras_require={
        "claude": [
            "anthropic>=0.40.0",
        ],
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.13",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
