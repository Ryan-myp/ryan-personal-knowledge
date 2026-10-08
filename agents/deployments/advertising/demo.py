"""Inspect the advertising application composition without provider I/O."""

from __future__ import annotations

from agents.ad_agent.application import create_advertising_application


def main() -> int:
    application = create_advertising_application(
        require_llm=False,
        offline_mode=True,
        start_background_workers=False,
    )
    try:
        tools = application.registry.list_all()
        print(f"Execution mode: {application.execution_mode}")
        print(f"Registered advertising Tools: {len(tools)}")
        for definition in tools:
            print(f"- {definition.name} ({definition.action} {definition.resource_type})")
    finally:
        application.close(wait=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
