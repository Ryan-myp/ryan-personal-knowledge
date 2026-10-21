#!/usr/bin/env python3.13
"""Produce the ad-agent release-readiness report.

This is the single local quality gate for the harness. It deliberately keeps
provider evidence separate from repository evidence and exits non-zero only
when the selected profile's required stages are not satisfied. The default
``local`` profile is safe to run without credentials; ``release`` is expected
to remain blocked until controlled Provider E2E/live evidence is supplied.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
SKILL_UP_ROOT = ROOT / "agents" / "evals" / "advertising" / "skill-up"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _safe_exception_text(error: Exception) -> str:
    """Redact known secret values before an exception reaches a readiness report."""
    from agents.agent_harness.redaction import redact_for_persistence

    text = str(redact_for_persistence(str(error)))
    secret_markers = (
        "API_KEY", "TOKEN", "SECRET", "PRIVATE_KEY", "PASSWORD",
        "CREDENTIAL", "DEVELOPER_TOKEN", "MCC", "PARTNER_ID",
    )
    for name, value in os.environ.items():
        if value and len(value) >= 8 and any(
            marker in name.upper() for marker in secret_markers
        ):
            text = text.replace(value, "<redacted>")
    return f"{type(error).__name__}: {text[:600]}"


from agents.tools.advertising.shared.domain.release_readiness import (  # noqa: E402
    ReadinessPolicy,
    build_readiness_report,
)
from agents.tools.advertising.shared.domain.provider_evidence import (  # noqa: E402
    merge_provider_evidence_files,
)
from scripts.advertising.audit_provider_tools import audit_provider_tools  # noqa: E402
from scripts.advertising.provider_contract_harness import run_harness  # noqa: E402
from scripts.advertising.validate_contracts import (  # noqa: E402
    build_runtime,
    build_contract_snapshot,
    verify_snapshot,
)
from agents.evals.advertising.skill_up_assertions import (  # noqa: E402
    evaluate_structured_expectations,
)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _load_skill_up_cases(yaml_module: Any) -> list[dict[str, Any]]:
    """Load exactly the repository-declared Skill-up suite, with no orphans."""
    manifest_path = SKILL_UP_ROOT / "evals" / "eval.yaml"
    manifest = yaml_module.safe_load(manifest_path.read_text(encoding="utf-8"))
    declared_files = (manifest.get("cases") or {}).get("files")
    if not isinstance(declared_files, list) or not declared_files:
        raise ValueError("Skill-up eval.yaml must declare a non-empty cases.files list")

    cases_root = (SKILL_UP_ROOT / "evals" / "cases").resolve()
    declared_paths = []
    for relative_path in declared_files:
        if not isinstance(relative_path, str) or not relative_path.strip():
            raise ValueError("Skill-up case paths must be non-empty strings")
        resolved = (SKILL_UP_ROOT / relative_path).resolve()
        if resolved.parent != cases_root or resolved.suffix != ".yaml":
            raise ValueError("Skill-up case paths must target evals/cases/*.yaml")
        declared_paths.append(resolved)
    if len(set(declared_paths)) != len(declared_paths):
        raise ValueError("Skill-up eval.yaml contains duplicate case paths")

    actual_paths = set(cases_root.glob("*.yaml"))
    if set(declared_paths) != actual_paths:
        missing = sorted(path.name for path in actual_paths - set(declared_paths))
        absent = sorted(path.name for path in set(declared_paths) - actual_paths)
        raise ValueError(
            f"Skill-up suite manifest mismatch (unlisted={missing}, missing={absent})"
        )

    cases = []
    seen_ids = set()
    for path in declared_paths:
        case = yaml_module.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(case, dict):
            raise ValueError(f"Skill-up case must be an object: {path.name}")
        case_id = str(case.get("id") or "").strip()
        prompt = ((case.get("input") or {}).get("prompt") or "").strip()
        if not case_id or not prompt:
            raise ValueError(f"Skill-up case requires id and prompt: {path.name}")
        if case_id in seen_ids:
            raise ValueError(f"Skill-up case IDs must be unique: {case_id}")
        seen_ids.add(case_id)
        cases.append({"path": path, "case": case, "id": case_id, "prompt": prompt})
    return cases


def _default_provider_evidence_paths() -> list[Path]:
    contracts = ROOT / "agents" / "tools" / "advertising" / "contracts"
    return [
        contracts / "provider_e2e_evidence.json",
        contracts / "provider_query_e2e_evidence.json",
    ]


def _load_provider_evidence(
    paths: Iterable[Path],
) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    bundle = merge_provider_evidence_files(paths)
    return (
        bundle.get("evidence") if bundle.get("valid") is True else None,
        list(bundle.get("errors") or []),
        list(bundle.get("sources") or []),
    )


def _model_eval_skipped(required_scenario_count: int, reason: str) -> dict[str, Any]:
    return {
        "executed": False,
        "skipped": True,
        "scenario_count": 0,
        "required_scenario_count": required_scenario_count,
        "suite_complete": False,
        "passed": False,
        "passed_scenarios": 0,
        "failed": 0,
        "errors": [],
        "evidence": "configured_model_skill_up",
        "reason": reason,
    }


def _evaluate_skill_up_case(
    item: dict[str, Any],
    run_case: Any,
    model_adapter: Any,
    workspace: str,
) -> dict[str, Any]:
    result = run_case({
        "case_id": item["id"],
        "workspace": workspace,
        "messages": [{"role": "user", "content": item["prompt"]}],
    }, model_adapter=model_adapter)
    output = str(result.get("final_message") or "")
    expected = item["case"].get("expect") or {}
    missing = [
        str(value)
        for value in (expected.get("must_contain") or [])
        if str(value) not in output
    ]
    forbidden = [
        str(value)
        for value in (expected.get("must_not_contain") or [])
        if str(value) in output
    ]
    structured_failures = evaluate_structured_expectations(result, expected)
    passed = (
        result.get("exit_code") == expected.get("exit_code", 0)
        and not missing
        and not forbidden
        and not structured_failures
    )
    return {
        "case": item["id"],
        "passed": passed,
        "missing": missing,
        "forbidden": forbidden,
        "structured_failures": structured_failures,
    }


def _execute_skill_up_suite(
    suite: list[dict[str, Any]],
    run_case: Any,
    model_adapter: Any,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="ad-agent-readiness-") as workspace:
        rows = [
            _evaluate_skill_up_case(item, run_case, model_adapter, workspace)
            for item in suite
        ]
    failures = [row for row in rows if not row["passed"]]
    suite_ids = {item["id"] for item in suite}
    suite_complete = len(rows) == len(suite) and {
        row["case"] for row in rows
    } == suite_ids
    errors = [f"{row['case']}: case assertion failed" for row in failures]
    if not suite_complete:
        errors.append("Skill-up suite run did not cover every declared case")
    return {
        "executed": True,
        "scenario_count": len(rows),
        "required_scenario_count": len(suite),
        "suite_complete": suite_complete,
        "passed": not failures and suite_complete and bool(rows),
        "passed_scenarios": len(rows) - len(failures),
        "failed": len(failures),
        "errors": errors,
        "cases": rows,
        "evidence": "configured_model_skill_up",
    }


def _run_skill_up_cases(*, enabled: bool = False) -> dict[str, Any]:
    """Run intent and response cases only when a reviewer opts into model calls."""
    required_scenario_count = 0
    try:
        import yaml

        suite = _load_skill_up_cases(yaml)
        required_scenario_count = len(suite)
        if not enabled:
            return _model_eval_skipped(
                required_scenario_count,
                "model evaluation requires --with-model-eval",
            )

        from agents.evals.advertising.skill_up_engine import run as run_case
        from agents.evals.advertising.skill_up_engine import (
            configured_model_adapter,
        )

        model_adapter = configured_model_adapter()
        if model_adapter is None:
            return _model_eval_skipped(
                len(suite),
                "set AD_AGENT_EVAL_API_KEY and AD_AGENT_EVAL_MODEL "
                "to run model-quality cases",
            )
        return _execute_skill_up_suite(suite, run_case, model_adapter)
    except Exception as exc:
        return {
            "executed": True,
            "scenario_count": 0,
            "required_scenario_count": required_scenario_count,
            "suite_complete": False,
            "passed": False,
            "passed_scenarios": 0,
            "failed": 1,
            "errors": [
                f"Skill-up model evaluation failed to start: {type(exc).__name__}"
            ],
            "evidence": "configured_model_skill_up",
        }


def _contract_gate_errors() -> list[str]:
    """Use the existing executable contract validator as a fixed sub-gate."""
    runtime = build_runtime()
    try:
        snapshot = build_contract_snapshot(runtime)
        snapshot_path = ROOT / "agents" / "tools" / "advertising" / "contracts" / "builtin_tools.json"
        return verify_snapshot(snapshot_path, snapshot)
    finally:
        store = getattr(runtime, "_contract_gate_store", None)
        if store is not None:
            store.close()


def _application_service_module_lines() -> int | None:
    """Measure only advertising application service modules.

    Platform bootstrap, generic input construction, and task executor code are
    infrastructure concerns with their own contracts. The maintainability
    dimension measures the business-facing service modules that are expected
    to remain independently understandable.
    """
    runtime_root = ROOT / "agents" / "applications" / "advertising"
    if not runtime_root.is_dir():
        return None
    service_names = {
        "ad_scheduling_preflight.py",
        "ad_creation_state_services.py",
        "ad_creation_template_services.py",
        "ad_creation_blueprint_services.py",
        "ad_creation_ui_services.py",
        "ad_creation_contract_services.py",
        "ad_creation_response_services.py",
        "ad_tool_source_registration.py",
        "ad_skill_lifecycle.py",
        "ad_skill_plugins.py",
        "ad_skill_discovery.py",
        "ad_provider_runtime_services.py",
        "ad_workflow_provider_reconciliation.py",
        "ad_task_operational_services.py",
        "ad_run_service.py",
        "scheduling_service.py",
        "template_tool_service.py",
    }
    paths = [
        path for path in runtime_root.rglob("*.py")
        if (
            (
                path.name.startswith("ad_")
                and (
                    path.name.endswith("_services.py")
                    or path.name in service_names
                )
            )
            or path.name in service_names
        )
    ]
    if not paths:
        return None
    return max(len(path.read_text(encoding="utf-8").splitlines()) for path in paths)


def _run_advertising_runtime_contract_smoke() -> dict[str, Any]:
    """Exercise one real advertising Run with a scripted model and offline Tool."""
    try:
        from agents.agent_harness.messages import ModelTurn, ToolCall
        from agents.evals.advertising.skill_up_engine import run as run_case

        class RuntimeContractModel:
            def __init__(self) -> None:
                self.turn = 0

            def complete(self, _messages, tools, _request):
                self.turn += 1
                if self.turn == 1:
                    available = {
                        str(getattr(tool, "name", "")) for tool in (tools or ())
                    }
                    if "tiktok_list_apps" not in available:
                        return ModelTurn(content="expected read Tool is unavailable")
                    return ModelTurn(tool_calls=(ToolCall(
                        "readiness-tiktok-apps",
                        "tiktok_list_apps",
                        {"account_id": "7397068114548195329"},
                    ),))
                return ModelTurn(content="Offline TikTok app lookup completed.")

        model = RuntimeContractModel()
        with tempfile.TemporaryDirectory(
            prefix="ad-agent-runtime-smoke-"
        ) as workspace:
            result = run_case({
                "case_id": "readiness-advertising-runtime",
                "workspace": workspace,
                "messages": [{
                    "role": "user",
                    "content": "查询 TikTok 可用应用列表",
                }],
            }, model_adapter=model)
        evidence = (result.get("metadata") or {}).get("runtime_result") or {}
        results = evidence.get("results") or []
        passed = (
            result.get("exit_code") == 0
            and evidence.get("tool_plan") == {"tiktok": ["tiktok_list_apps"]}
            and len(results) == 1
            and results[0].get("success") is True
            and (results[0].get("data") or {}).get("data_status") == "offline_mock"
            and model.turn == 2
        )
        return {
            "executed": True,
            "passed": passed,
            "scenario_count": 1,
            "evidence": "scripted_advertising_runtime_contract",
            "scope": (
                "real advertising Runtime and registered offline Tool; "
                "model intent quality and Provider connectivity are not tested"
            ),
            "provider_calls": 0,
            "model_turns": model.turn,
            "errors": [] if passed else ["offline advertising Runtime smoke failed"],
        }
    except Exception as exc:
        return {
            "executed": False,
            "passed": False,
            "scenario_count": 0,
            "evidence": "scripted_advertising_runtime_contract",
            "scope": "offline Runtime contract only",
            "provider_calls": 0,
            "errors": [f"Runtime smoke failed: {type(exc).__name__}"],
        }


def _run_generic_platform_smoke() -> dict[str, Any]:
    """Exercise deterministic Tool routing, not real-LLM decision quality."""
    try:
        from agents.agent_harness import ModelTurn, ToolCall
        from agents.agent_platform.examples import create_ticket_support_application

        class SmokeModel:
            def __init__(self) -> None:
                self.turn = 0

            def complete(self, messages, tools, _request):
                self.turn += 1
                if self.turn == 1:
                    names = [item.get("name") for item in tools]
                    if names != ["lookup_ticket"]:
                        return ModelTurn(content="unexpected tool catalog")
                    return ModelTurn(tool_calls=(
                        ToolCall(
                            "ticket-lookup-1",
                            "lookup_ticket",
                            {"ticket_id": "T-42"},
                        ),
                    ))
                saw_ticket_result = any(
                    "T-42" in json.dumps(message, ensure_ascii=False, default=str)
                    for message in messages
                )
                return ModelTurn(
                    content="Ticket T-42 status is open"
                    if saw_ticket_result
                    else "ticket lookup result missing"
                )

        model = SmokeModel()
        application = create_ticket_support_application(
            model=model,
        )
        try:
            response = application.prompt("Find ticket status for T-42")
            layers = tuple(application.layer_snapshot())
            tool_results = list(response.data.get("tool_results") or [])
            tool_executed = any(
                item.get("name") == "lookup_ticket" for item in tool_results
            )
            passed = (
                application.scenario.scenario_id == "ticket-support"
                and [item["name"] for item in application.list_tools()]
                == ["lookup_ticket"]
                and response.reply == "Ticket T-42 status is open"
                and tool_executed
                and model.turn == 2
                and len(layers) == 6
            )
            return {
                "passed": passed,
                "evidence": "ticket_support_reference_application_smoke",
                "scope": (
                    "synthetic deterministic Tool selection and execution; "
                    "not an LLM quality benchmark"
                ),
                "tool_executed": tool_executed,
                "model_turns": model.turn,
                "layers": list(layers),
            }
        finally:
            application.close()
    except Exception as exc:
        return {
            "passed": False,
            "evidence": "ticket_support_reference_application_smoke",
            "error": f"{type(exc).__name__}: {exc}",
        }


def _run_security_contracts() -> dict[str, Any]:
    """Exercise local MCP trust and dry-run boundaries without network calls."""
    from agents.agent_harness import MCPToolExecutor, MCPToolSource, TurnRequest

    class FakeClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, Any]]] = []

        def list_tools(self):
            return [
                {
                    "name": "lookup",
                    "inputSchema": {"type": "object", "properties": {}},
                    "annotations": {"readOnlyHint": False},
                },
                {
                    "name": "publish",
                    "inputSchema": {
                        "type": "object",
                        "required": ["request_id"],
                        "properties": {"request_id": {"type": "string"}},
                    },
                    "annotations": {"readOnlyHint": True},
                },
            ]

        def call_tool(self, name, arguments):
            self.calls.append((name, dict(arguments)))
            return {"structuredContent": {"ok": True}}

    checks: list[bool] = []
    client = FakeClient()
    untrusted_source = MCPToolSource("mcp:untrusted", client)
    untrusted = {
        item.definition["name"]: item
        for item in untrusted_source.list_bindings()
    }
    checks.append(
        untrusted["publish"].definition["effect_class"] == "external_write"
    )
    dry_result = untrusted["publish"].executor.execute(
        type(
            "Context",
            (),
            {
                "request": TurnRequest(
                    user_input="publish",
                    tenant_id="default",
                    execution_mode="dry_run",
                ),
            },
        )(),
        {},
    )
    checks.append(
        dry_result.get("execution_status") == "dry_run_only"
        and not client.calls
    )

    trusted_source = MCPToolSource(
        "mcp:trusted",
        client,
        trusted_read_tools={"lookup"},
        live_write_tools={"publish"},
        idempotency_key_fields={"publish": "request_id"},
    )
    trusted = {
        item.definition["name"]: item
        for item in trusted_source.list_bindings()
    }
    checks.append(trusted["lookup"].definition["effect_class"] == "read")
    cross_tenant = trusted["lookup"].executor.execute(
        type(
            "Context",
            (),
            {
                "request": TurnRequest(
                    user_input="lookup",
                    tenant_id="other",
                    execution_mode="dry_run",
                ),
            },
        )(),
        {},
    )
    checks.append(
        cross_tenant.get("success") is False
        and not client.calls
    )

    live_write = trusted["publish"].executor.execute(
        type(
            "Context",
            (),
            {
                "request": TurnRequest(
                    user_input="publish",
                    tenant_id="default",
                    execution_mode="live",
                ),
            },
        )(),
        {"record_id": "r-1", "request_id": "publish-smoke-1"},
    )
    checks.append(
        live_write.get("success") is True
        and client.calls == [(
            "publish",
            {"record_id": "r-1", "request_id": "publish-smoke-1"},
        )]
    )
    return {
        "executed": True,
        "passed": all(checks),
        "scenario_count": len(checks),
        "scope": "local MCP executor trust, tenant and dry-run contracts only",
        "errors": [
            f"security contract {index + 1} failed"
            for index, passed in enumerate(checks)
            if not passed
        ],
    }


def _run_reliability_evidence() -> dict[str, Any]:
    """Run local process-level coordination and recovery evidence.

    This is intentionally reported separately from ``production_evidence``.
    Passing local shared-persistence scenarios does not attest that a
    production deployment, database cluster, or provider environment has been
    exercised.
    """
    try:
        from scripts.advertising.production_reliability_evidence import (
            run_reliability_evidence,
        )

        report = run_reliability_evidence(timeout_seconds=30)
        return {
            "executed": True,
            "passed": bool(report.get("passed")),
            "production_deployment_attested": bool(
                report.get("production_deployment_attested")
            ),
            "report": report,
        }
    except Exception as exc:
        return {
            "executed": False,
            "passed": False,
            "production_deployment_attested": False,
            "error": _safe_exception_text(exc),
        }


def build_report(
    profile: str,
    policy_path: Path,
    provider_evidence_paths: list[Path] | None = None,
    *,
    run_model_eval: bool = False,
) -> dict[str, Any]:
    policy = ReadinessPolicy.from_dict(_load_json(policy_path))
    resolved_provider_evidence_paths = (
        provider_evidence_paths or _default_provider_evidence_paths()
    )
    provider_evidence, provider_evidence_errors, provider_evidence_sources = (
        _load_provider_evidence(resolved_provider_evidence_paths)
    )
    tool_source_report = audit_provider_tools(resolved_provider_evidence_paths)
    contract_errors = _contract_gate_errors()
    provider_report = run_harness(
        ROOT / "agents" / "tools" / "advertising" / "contracts" / "provider_contract_scenarios.json"
    )
    skill_report = _run_skill_up_cases(enabled=run_model_eval)
    runtime_smoke = _run_advertising_runtime_contract_smoke()
    generic_platform_report = _run_generic_platform_smoke()
    security_report = _run_security_contracts()
    reliability_report = _run_reliability_evidence()
    dry_run_report = {
        "executed": bool(
            provider_report.get("executed") and runtime_smoke.get("executed")
        ),
        "failed": (
            int(provider_report.get("failed", 0) or 0)
            + int(not runtime_smoke.get("passed"))
        ),
        "errors": (
            list(provider_report.get("errors") or [])
            + list(runtime_smoke.get("errors") or [])
        ),
        "provider_harness": provider_report,
        "advertising_runtime_smoke": runtime_smoke,
        "skill_up": skill_report,
        "generic_platform_evidence": bool(generic_platform_report.get("passed")),
        "generic_platform": generic_platform_report,
        "security": security_report,
        "reliability_evidence": bool(reliability_report.get("passed")),
        "reliability": reliability_report,
        "max_runtime_module_lines": _application_service_module_lines(),
        # Local subprocess evidence is not a production deployment attestation.
        "production_evidence": bool(
            reliability_report.get("production_deployment_attested")
        ),
    }
    report = build_readiness_report(
        tool_source_report=tool_source_report,
        contract_gate_errors=contract_errors,
        dry_run_report=dry_run_report,
        model_quality_report=skill_report,
        security_report=security_report,
        provider_evidence=provider_evidence,
        policy=policy,
        profile=profile,
    )
    # Keep the full audit evidence nested, while the top-level decision stays
    # small enough for CI and the UI to consume.
    report["evidence"] = {
        "tool_source_audit": tool_source_report,
        "contract_snapshot_errors": contract_errors,
        "dry_run": dry_run_report,
        "model_quality": skill_report,
        "security": security_report,
        "reliability": reliability_report,
        "provider_evidence_sources": provider_evidence_sources,
        "provider_evidence_load_errors": provider_evidence_errors,
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="local")
    parser.add_argument(
        "--policy",
        type=Path,
        default=ROOT / "agents" / "tools" / "advertising" / "contracts" / "readiness_policy.json",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--with-model-eval",
        action="store_true",
        help=(
            "Opt into model-backed Skill-up requests using "
            "AD_AGENT_EVAL_API_KEY/AD_AGENT_EVAL_MODEL."
        ),
    )
    parser.add_argument(
        "--provider-evidence",
        action="append",
        type=Path,
        help=(
            "Controlled Provider evidence JSON (repeatable). When omitted, "
            "loads both checked-in write and query evidence sources."
        ),
    )
    args = parser.parse_args(argv)
    try:
        report = build_report(
            args.profile,
            args.policy,
            provider_evidence_paths=args.provider_evidence,
            run_model_eval=args.with_model_eval,
        )
    except Exception as exc:
        report = {
            "format_version": 1,
            "profile": args.profile,
            "passed": False,
            "blocking_stages": ["code_contract"],
            "stage_results": {},
            "errors": [f"readiness gate failed to run: {_safe_exception_text(exc)}"],
        }
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
