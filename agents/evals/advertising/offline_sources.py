"""Trusted offline Tool bindings for model-backed conversation evaluation."""

from agents.agent_harness import StaticToolSource, ToolBinding
from agents.agent_harness.core.interfaces import ToolResult
from agents.agent_platform.tools.web_search import web_search_tool_source


def offline_web_search_source() -> StaticToolSource:
    canonical = web_search_tool_source(
        configuration_provider=lambda: {"enabled": True, "provider": "duckduckgo"},
        required_permission="ads.read",
    )

    def execute(_context, arguments):
        return ToolResult(
            success=True, simulated=True,
            data={
                "query": str(arguments.get("query") or ""),
                "results": [],
                "data_status": "simulated",
                "simulated": True,
                "notice": (
                    "Offline evaluation fixture. No web request was sent. "
                    "Do not invent current facts, sources, or search results."
                ),
            },
        )

    return StaticToolSource(canonical.source_id, [
        ToolBinding(binding.definition, execute)
        for binding in canonical.list_bindings()
    ])
