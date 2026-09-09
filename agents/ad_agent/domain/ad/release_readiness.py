"""Release-readiness aggregation for the advertising Agent harness.

This module deliberately does not decide that a provider is production-ready
because a Tool is registered or a dry-run fixture passed.  It combines the
independent evidence layers into a small, machine-readable report:

``code_contract`` -> ``dry_run`` -> ``provider_e2e`` -> ``live_verified``

The first two layers are safe to run in CI without provider credentials.  The
last two are evidence supplied by a separately controlled provider test
environment and are therefore absent from the local report by default.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ...core.namespace import normalize_namespace as normalize_platform


EVIDENCE_STAGES = (
    "code_contract",
    "dry_run",
    "provider_e2e",
    "live_verified",
)


@dataclass(frozen=True)
class ReadinessPolicy:
    """Validated, declarative policy loaded from a repository JSON file."""

    format_version: int
    profiles: Mapping[str, tuple[str, ...]]
    default_profile: str = "local"

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ReadinessPolicy":
        if not isinstance(raw, Mapping):
            raise ValueError("readiness policy must be an object")
        try:
            format_version = int(raw.get("format_version", 0))
        except (TypeError, ValueError) as exc:
            raise ValueError("readiness policy format_version must be an integer") from exc
        if format_version != 1:
            raise ValueError(f"unsupported readiness policy format_version: {format_version}")
        raw_profiles = raw.get("profiles")
        if not isinstance(raw_profiles, Mapping) or not raw_profiles:
            raise ValueError("readiness policy profiles must be a non-empty object")
        profiles: dict[str, tuple[str, ...]] = {}
        for name, stages in raw_profiles.items():
            profile = str(name or "").strip()
            if not profile:
                raise ValueError("readiness profile name cannot be empty")
            if not isinstance(stages, list) or not stages:
                raise ValueError(f"readiness profile {profile!r} must declare stages")
            normalized = tuple(dict.fromkeys(str(stage).strip() for stage in stages))
            invalid = sorted(set(normalized) - set(EVIDENCE_STAGES))
            if invalid:
                raise ValueError(
                    f"readiness profile {profile!r} has unsupported stages: {', '.join(invalid)}"
                )
            profiles[profile] = normalized
        default_profile = str(raw.get("default_profile") or "local").strip()
        if default_profile not in profiles:
            raise ValueError(f"default readiness profile is not declared: {default_profile}")
        return cls(format_version, profiles, default_profile)

    def stages_for(self, profile: str | None) -> tuple[str, ...]:
        selected = str(profile or self.default_profile).strip()
        if selected not in self.profiles:
            raise ValueError(f"unknown readiness profile: {selected}")
        return self.profiles[selected]


def _provider_inventory_status(report: Mapping[str, Any]) -> dict[str, Any]:
    """Summarize evidence without treating scoped inventory as exhaustive."""
    total = int(report.get("total", 0) or 0)
    evidence = report.get("evidence_levels") or {}
    execution = report.get("execution_statuses") or {}
    provider_e2e = int(evidence.get("provider_e2e", 0) or 0)
    live_verified = int(execution.get("live_verified", 0) or 0)
    return {
        "inventory_scope": report.get("scope", ""),
        "completeness": report.get("completeness", "scoped_not_exhaustive"),
        "inventory_total": total,
        "provider_e2e_items": provider_e2e,
        "live_verified_items": live_verified,
        "provider_e2e_complete_for_inventory": bool(total and provider_e2e >= total),
        "live_verified_complete_for_implemented_surface": bool(
            total and live_verified >= total
        ),
    }

def build_readiness_report(
    *,
    capability_report: Mapping[str, Any],
    contract_gate_errors: list[str] | tuple[str, ...] = (),
    dry_run_report: Mapping[str, Any] | None = None,
    policy: ReadinessPolicy,
    profile: str | None = None,
) -> dict[str, Any]:
    """Build a release report and a conservative pass/fail decision.

    ``provider_e2e`` and ``live_verified`` are never inferred from local
    tests.  Callers that have controlled evidence may provide it separately;
    the local capability audit remains the source of provider inventory facts.
    """
    selected_profile = str(profile or policy.default_profile).strip()
    required = policy.stages_for(selected_profile)
    capability_issues = [str(item) for item in (capability_report.get("issues") or [])]
    contract_errors = [str(item) for item in contract_gate_errors]
    dry_run = dict(dry_run_report or {})
    dry_run_failures = int(dry_run.get("failed", 0) or 0)

    code_contract_ok = not capability_issues and not contract_errors
    dry_run_ok = bool(dry_run.get("executed", False)) and dry_run_failures == 0

    inventory_reports = capability_report.get("official_inventory") or {}
    provider_summaries = {
        normalize_platform(str(platform)): _provider_inventory_status(report)
        for platform, report in inventory_reports.items()
        if isinstance(report, Mapping)
    }
    provider_e2e_ok = bool(provider_summaries) and all(
        item["provider_e2e_complete_for_inventory"] for item in provider_summaries.values()
    )
    live_verified_ok = bool(provider_summaries) and all(
        item["live_verified_complete_for_implemented_surface"]
        for item in provider_summaries.values()
    )
    stage_results = {
        "code_contract": {
            "status": "passed" if code_contract_ok else "failed",
            "evidence": "capability audit and executable Tool contract gate",
            "errors": capability_issues + contract_errors,
        },
        "dry_run": {
            "status": "passed" if dry_run_ok else "failed",
            "evidence": "local provider harness and Skill-up Runtime cases",
            "executed": bool(dry_run.get("executed", False)),
            "failed": dry_run_failures,
            "errors": list(dry_run.get("errors") or []),
        },
        "provider_e2e": {
            "status": "passed" if provider_e2e_ok else "not_verified",
            "evidence": "operation-specific controlled provider evidence",
            "errors": [] if provider_e2e_ok else [
                "本地验证不等同于 Provider E2E；当前没有完整的渠道账户证据"
            ],
        },
        "live_verified": {
            "status": "passed" if live_verified_ok else "not_verified",
            "evidence": "operation-specific live verification evidence",
            "errors": [] if live_verified_ok else [
                "当前 Capability 默认 dry_run_only，未提供 live_verified 证据"
            ],
        },
    }
    blocking = [stage for stage in required if stage_results[stage]["status"] != "passed"]
    return {
        "format_version": 1,
        "profile": selected_profile,
        "required_stages": list(required),
        "passed": not blocking,
        "blocking_stages": blocking,
        "stage_results": stage_results,
        "provider_summaries": provider_summaries,
        "capability_issue_count": len(capability_issues),
        "contract_error_count": len(contract_errors),
    }
