"""Architecture tests for the framework, platform and scenario boundaries."""

import ast
from pathlib import Path


AGENTS_ROOT = Path(__file__).resolve().parents[2]


def _python_imports(root: Path) -> set[str]:
    imports: set[str] = set()
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts or "build" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
    return imports


def test_repository_uses_the_documented_package_roots():
    expected = (
        "agent_harness",
        "agent_platform",
        "tools/advertising",
        "skills/advertising",
        "knowledge/advertising/wiki",
        "scenarios",
        "deployments/advertising",
        "docs/advertising",
        "tests/harness",
        "tests/platform",
        "tests/advertising",
    )
    assert all((AGENTS_ROOT / path).is_dir() for path in expected)
    assert (AGENTS_ROOT / "scenarios" / "advertising.py").is_file()


def test_advertising_deployment_does_not_own_a_second_core_or_runtime():
    package = AGENTS_ROOT / "ad_agent"
    assert not (package / "core").exists()
    assert not (package / "runtime").exists()
    assert not (package / "api").exists()
    assert not (package / "persistence").exists()
    assert (package / "application.py").is_file()
    assert not (package / "setup.py").exists()
    assert not (package / "requirements.txt").exists()
    for misplaced in (
        "api_server.py",
        "chat.py",
        "scripts",
        "static",
        "templates",
        "tests",
        "evals",
        "knowledge_base",
        "tools",
        "skills",
    ):
        assert not (package / misplaced).exists(), misplaced


def test_deployment_and_operations_are_outside_framework_packages():
    deployment = AGENTS_ROOT / "deployments" / "advertising"
    assert (deployment / "api_server.py").is_file()
    assert (deployment / "chat.py").is_file()
    assert (deployment / "static").is_dir()
    assert (AGENTS_ROOT.parent / "scripts" / "advertising" / "audit_provider_tools.py").is_file()


def test_framework_and_platform_do_not_import_advertising_implementation():
    forbidden_fragments = ("agents.ad_agent", "agents.tools.advertising")
    for package in (AGENTS_ROOT / "agent_harness", AGENTS_ROOT / "agent_platform"):
        imports = _python_imports(package)
        assert not any(
            fragment in imported
            for fragment in forbidden_fragments
            for imported in imports
        ), package


def test_advertising_tools_are_independent_of_the_deployment_package():
    imports = _python_imports(AGENTS_ROOT / "tools" / "advertising")
    assert not any("agents.ad_agent" in imported for imported in imports)


def test_harness_and_platform_are_independent_of_advertising_packages():
    for package in (AGENTS_ROOT / "agent_harness", AGENTS_ROOT / "agent_platform"):
        imports = _python_imports(package)
        assert not any("agents.tools.advertising" in imported for imported in imports)
        assert not any("agents.skills.advertising" in imported for imported in imports)
        assert not any("agents.knowledge.advertising" in imported for imported in imports)


def test_scenario_is_declarative_and_does_not_own_a_turn_pipeline():
    scenario = AGENTS_ROOT / "scenarios" / "advertising.py"
    tree = ast.parse(scenario.read_text(encoding="utf-8"), filename=str(scenario))
    definitions = [node for node in tree.body if isinstance(node, ast.ClassDef)]
    assert not definitions
    imported_names = _python_imports(scenario.parent)
    assert not any(
        term in imported.lower()
        for term in ("turn_handler", "turn_planner", "runtime", "provider", "client")
        for imported in imported_names
    )
