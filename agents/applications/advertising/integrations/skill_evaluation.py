"""Trusted advertising evaluator configuration for deployment assembly."""

from pathlib import Path

from agents.agent_platform.management.evaluation import ManagedEvaluationEngine


def advertising_evaluation_engines() -> dict[str, ManagedEvaluationEngine]:
    agents_root = Path(__file__).resolve().parents[3]
    catalog = agents_root / "tools/advertising/contracts/builtin_tools.json"
    return {
        "ad-agent-runtime": ManagedEvaluationEngine(
            adapter_path=agents_root / "evals/advertising/skill_up_engine.py",
        ),
        "claude_sdk": ManagedEvaluationEngine(
            adapter_path=agents_root / "agent_platform/evals/claude_sdk_engine.py",
            allowed_kwargs=(
                "max_tokens",
                "file_paths",
                "max_skill_context_chars",
                "max_tool_context_chars",
                "max_file_context_chars",
            ),
            environment={"AGENT_EVAL_TOOL_CATALOG": str(catalog)},
        ),
    }
