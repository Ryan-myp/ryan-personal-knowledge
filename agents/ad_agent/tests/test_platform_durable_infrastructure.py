"""The durable execution layer must be importable without advertising code."""

import ast
from pathlib import Path

from agents.agent_platform.infrastructure.durable import (
    RuntimeSupervisor,
    TaskExecutor,
    TaskSubmission,
)


def test_durable_infrastructure_is_application_neutral():
    assert RuntimeSupervisor is not None
    assert TaskExecutor is not None
    assert TaskSubmission is not None

    root = Path("agents/agent_platform/infrastructure/durable")
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "ad_agent" not in node.module, path
            if isinstance(node, ast.Import):
                assert all("ad_agent" not in alias.name for alias in node.names), path
