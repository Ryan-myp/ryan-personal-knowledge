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
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.ad_agent.domain.ad.release_readiness import (  # noqa: E402
    ReadinessPolicy,
    build_readiness_report,
)
from agents.ad_agent.scripts.audit_provider_tools import audit_provider_tools  # noqa: E402
from agents.ad_agent.scripts.provider_contract_harness import run_harness  # noqa: E402
from agents.ad_agent.scripts.validate_contracts import (  # noqa: E402
    build_runtime,
    build_contract_snapshot,
    verify_snapshot,
)
from agents.ad_agent.evals.skill_up_assertions import (  # noqa: E402
    evaluate_structured_expectations,
)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _load_optional_provider_evidence(path: Path | None) -> tuple[dict[str, Any] | None, str | None]:
    if path is None:
        return None, None
    try:
        return _load_json(path), None
    except (OSError, json.JSONDecodeError, ValueError) as error:
        return None, f"{type(error).__name__}: {error}"


def _run_skill_up_cases() -> dict[str, Any]:
    """Run repository cases through the Runtime adapter without CLI/network."""
    try:
        import yaml
        from agents.ad_agent.evals.skill_up_engine import run as run_case

        cases_root = ROOT / "agents" / "ad_agent" / "evals" / "skill-up" / "evals" / "cases"
        rows: list[dict[str, Any]] = []
        with tempfile.TemporaryDirectory(prefix="ad-agent-readiness-") as workspace:
            for case_path in sorted(cases_root.glob("*.yaml")):
                case = yaml.safe_load(case_path.read_text(encoding="utf-8")) or {}
                prompt = ((case.get("input") or {}).get("prompt") or "").strip()
                if not prompt:
                    rows.append({"case": case_path.name, "passed": False, "error": "missing prompt"})
                    continue
                result = run_case({
                    "case_id": str(case.get("id") or case_path.stem),
                    "workspace": workspace,
                    "messages": [{"role": "user", "content": prompt}],
                })
                output = str(result.get("final_message") or "")
                expected = case.get("expect") or {}
                missing = [str(item) for item in (expected.get("must_contain") or []) if str(item) not in output]
                forbidden = [str(item) for item in (expected.get("must_not_contain") or []) if str(item) in output]
                structured_failures = evaluate_structured_expectations(result, expected)
                passed = (
                    result.get("exit_code") == expected.get("exit_code", 0)
                    and not missing and not forbidden and not structured_failures
                )
                rows.append({
                    "case": str(case.get("id") or case_path.stem),
                    "passed": passed,
                    "missing": missing,
                    "forbidden": forbidden,
                    "structured_failures": structured_failures,
                })
        failures = [row for row in rows if not row["passed"]]
        return {
            "executed": True,
            "scenario_count": len(rows),
            "passed": len(rows) - len(failures),
            "failed": len(failures),
            "errors": [f"{row['case']}: case assertion failed" for row in failures],
            "cases": rows,
            "evidence": "skill_up_runtime_adapter_local_only",
        }
    except Exception as exc:
        return {
            "executed": False,
            "scenario_count": 0,
            "passed": 0,
            "failed": 1,
            "errors": [f"Skill-up suite failed to start: {type(exc).__name__}: {exc}"],
            "evidence": "skill_up_runtime_adapter_local_only",
        }


def _contract_gate_errors() -> list[str]:
    """Use the existing executable contract validator as a fixed sub-gate."""
    runtime = build_runtime()
    try:
        snapshot = build_contract_snapshot(runtime)
        snapshot_path = ROOT / "agents" / "ad_agent" / "contracts" / "builtin_tools.json"
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
    runtime_root = ROOT / "agents" / "ad_agent" / "runtime"
    paths = [
        path for path in runtime_root.glob("*.py")
        if (
            path.name.startswith("ad_")
            and (
                path.name.endswith("_services.py")
                or path.name in {
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
                }
            )
        )
    ]
    if not paths:
        return None
    return max(len(path.read_text(encoding="utf-8").splitlines()) for path in paths)


def _run_generic_platform_smoke() -> dict[str, Any]:
    """Exercise the business-neutral six-layer reference application."""
    try:
        from agents.agent_platform.examples import create_ticket_support_application

        application = create_ticket_support_application(
            model=lambda _messages, tools, _request: tools[0]["name"],
        )
        try:
            response = application.prompt("Find ticket status")
            layers = tuple(application.layer_snapshot())
            passed = (
                application.scenario.scenario_id == "ticket-support"
                and [item["name"] for item in application.list_tools()]
                == ["lookup_ticket"]
                and response.reply == "lookup_ticket"
                and len(layers) == 6
            )
            return {
                "passed": passed,
                "evidence": "ticket_support_reference_application_smoke",
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


def _run_reliability_evidence() -> dict[str, Any]:
    """Run local process-level coordination and recovery evidence.

    This is intentionally reported separately from ``production_evidence``.
    Passing local shared-persistence scenarios does not attest that a
    production deployment, database cluster, or provider environment has been
    exercised.
    """
    try:
        from agents.ad_agent.scripts.production_reliability_evidence import (
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
            "error": f"{type(exc).__name__}: {exc}",
        }


def build_report(
    profile: str,
    policy_path: Path,
    provider_evidence_path: Path | None = None,
) -> dict[str, Any]:
    policy = ReadinessPolicy.from_dict(_load_json(policy_path))
    resolved_provider_evidence_path = provider_evidence_path or (
        ROOT / "agents" / "ad_agent" / "contracts" / "provider_e2e_evidence.json"
    )
    provider_evidence, provider_evidence_error = _load_optional_provider_evidence(
        resolved_provider_evidence_path
    )
    tool_source_report = audit_provider_tools(resolved_provider_evidence_path)
    contract_errors = _contract_gate_errors()
    provider_report = run_harness(
        ROOT / "agents" / "ad_agent" / "contracts" / "provider_contract_scenarios.json"
    )
    skill_report = _run_skill_up_cases()
    generic_platform_report = _run_generic_platform_smoke()
    reliability_report = _run_reliability_evidence()
    dry_run_report = {
        "executed": bool(provider_report.get("executed") and skill_report.get("executed")),
        "failed": int(provider_report.get("failed", 0) or 0) + int(skill_report.get("failed", 0) or 0),
        "errors": list(provider_report.get("errors") or []) + list(skill_report.get("errors") or []),
        "provider_harness": provider_report,
        "skill_up": skill_report,
        "generic_platform_evidence": bool(generic_platform_report.get("passed")),
        "generic_platform": generic_platform_report,
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
        "reliability": reliability_report,
        "provider_evidence_source": (
            str(resolved_provider_evidence_path)
        ),
        "provider_evidence_load_error": provider_evidence_error,
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="local")
    parser.add_argument(
        "--policy",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "contracts" / "readiness_policy.json",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--provider-evidence",
        type=Path,
        help="Optional controlled Provider E2E evidence JSON; never inferred from local tests.",
    )
    args = parser.parse_args(argv)
    try:
        report = build_report(
            args.profile,
            args.policy,
            provider_evidence_path=args.provider_evidence,
        )
    except Exception as exc:
        report = {
            "format_version": 1,
            "profile": args.profile,
            "passed": False,
            "blocking_stages": ["code_contract"],
            "stage_results": {},
            "errors": [f"readiness gate failed to run: {type(exc).__name__}: {exc}"],
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
