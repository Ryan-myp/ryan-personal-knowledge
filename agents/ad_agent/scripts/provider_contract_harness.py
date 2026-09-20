#!/usr/bin/env python3.13
"""Run the no-network Provider -> Tool -> Runtime contract harness.

The harness uses the public Capability factories and a recording client.  It
does not monkey-patch the Runtime, does not import user Skill code, and does
not contact a provider.  A passing result means the selected read operation
crossed the real registration, routing, policy and handler boundaries with a
local client double; it is not Provider E2E evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.ad_agent.capabilities.factory import (  # noqa: E402
    create_capability,
    discover_capability_factory,
)
from agents.ad_agent.core.interfaces import ParsedIntent  # noqa: E402
from agents.ad_agent.persistence.store import AdAgentStore  # noqa: E402
from agents.ad_agent.runtime.runtime import AgentRuntime  # noqa: E402


class _RecordingCampaignClient:
    """Minimal provider client doubles with explicit provider signatures."""

    def __init__(self, platform: str):
        self.platform = platform
        self.calls: list[dict[str, Any]] = []

    def _record(self, method: str, *args: Any, **kwargs: Any) -> list[dict[str, str]]:
        self.calls.append({"method": method, "args": list(args), "kwargs": dict(kwargs)})
        return [{"id": f"{self.platform}-campaign-1", "name": "Contract campaign"}]

    def list_campaigns(self, *args: Any, **kwargs: Any) -> list[dict[str, str]]:
        # The handler helper uses signature inspection to pass paging. The
        # explicit call is still recorded through this provider-neutral test
        # double, while the scenario verifies the required account scope.
        return self._record("list_campaigns", *args, **kwargs)


class _DeterministicIntentParser:
    """A test-only parser that fixes intent; Runtime remains authoritative."""

    def __init__(self, intent_type: str, namespace: str, scoped_parameters: dict[str, dict[str, str]]):
        self.intent_type = intent_type
        self.namespace = namespace
        self.scoped_parameters = scoped_parameters

    def refresh_tool_catalog(self, _definitions: Any) -> None:
        return None

    def register_tool_definitions(self, _definitions: Any) -> None:
        return None

    def register_namespace_aliases(self, _namespace: str, _aliases: Any) -> None:
        return None

    def parse(self, raw_input: str, _context: Any) -> ParsedIntent:
        return ParsedIntent(
            intent_type=self.intent_type,
            raw_input=raw_input,
            namespaces=[self.namespace],
            scoped_parameters=self.scoped_parameters,
        )


def _read_scenarios(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not value:
        raise ValueError("provider contract scenarios must be a non-empty array")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"scenario[{index}] must be an object")
        for field in ("platform", "tool_name", "account_field", "account_id"):
            if not str(item.get(field) or "").strip():
                raise ValueError(f"scenario[{index}].{field} is required")
        result.append(dict(item))
    return result


def run_harness(path: str | Path) -> dict[str, Any]:
    scenarios = _read_scenarios(Path(path))
    rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        platform = str(scenario["platform"])
        tool_name = str(scenario["tool_name"])
        account_field = str(scenario["account_field"])
        account_id = str(scenario["account_id"])
        client = _RecordingCampaignClient(platform)
        store = AdAgentStore(":memory:")
        parser = _DeterministicIntentParser(
            "list_campaigns", platform, {platform: {account_field: account_id}}
        )
        runtime = AgentRuntime(
            intent_parser=parser,
            require_llm=False,
            persistence_store=store,
            offline_mode=False,
            enforce_account_scope=False,
            max_tool_calls=4,
            # The harness uses a temporary in-memory store and executes each
            # scenario synchronously. Background durable workers add no
            # contract evidence and can race store teardown.
            start_background_workers=False,
        )
        error = ""
        result: Mapping[str, Any] = {}
        try:
            factory = discover_capability_factory(platform)
            if not callable(factory):
                raise ValueError(f"Capability factory not found: {platform}")
            runtime.register_capability(create_capability(platform, client))
            definition, _handler = runtime.registry.get_authorized(
                tool_name, runtime._registry_execution_token
            )
            if definition is None:
                raise ValueError(f"Tool is not registered: {tool_name}")
            result = runtime.run(
                user_input=f"contract probe {platform}",
                session_id=f"provider-contract:{platform}",
                user_id="provider-contract-harness",
                account_id=account_id,
                platform_params={platform: {account_field: account_id}},
            )
            selected = set((result.get("tool_plan") or {}).get(platform, []))
            tool_plan = result.get("tool_plan") or {}
            selected_names = {
                name for names in tool_plan.values() for name in (names if isinstance(names, list) else [])
            }
            if tool_name not in selected_names:
                raise AssertionError(f"Runtime did not select {tool_name}")
            results = result.get("results") or []
            if len(results) != 1 or not results[0].get("success"):
                raise AssertionError(f"Runtime result was not successful: {results}")
            payload = results[0].get("data") or {}
            if payload.get("data_status") != "live" or payload.get("simulated"):
                raise AssertionError("local client result was not marked as live client evidence")
            if len(client.calls) != 1 or client.calls[0].get("method") != "list_campaigns":
                raise AssertionError(f"unexpected client calls: {client.calls}")
        except Exception as exc:  # pragma: no cover - report path is tested
            error = f"{type(exc).__name__}: {exc}"
        finally:
            runtime.close(wait=True)
            store.close()
        rows.append({
            "platform": platform,
            "tool_name": tool_name,
            "passed": not bool(error),
            "error": error,
            "client_calls": len(client.calls),
            "runtime_result_success": bool(
                (result.get("results") or [{}])[0].get("success")
            ) if result else False,
        })
    failures = [row for row in rows if not row["passed"]]
    return {
        "executed": True,
        "scenario_count": len(rows),
        "passed": len(rows) - len(failures),
        "failed": len(failures),
        "errors": [f"{row['platform']}: {row['error']}" for row in failures],
        "scenarios": rows,
        "evidence": "local_recording_client_only",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenarios",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "contracts" / "provider_contract_scenarios.json",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        report = run_harness(args.scenarios)
    except Exception as exc:
        report = {"executed": False, "passed": 0, "failed": 1, "errors": [str(exc)]}
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0 if report.get("executed") and not report.get("failed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
