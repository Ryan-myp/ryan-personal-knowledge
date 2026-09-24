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

import re
from dataclasses import dataclass
from typing import Any, Mapping

from ...core.namespace import normalize_namespace as normalize_platform
from .provider_evidence import build_provider_evidence_report
from .quality_scorecard import (
    build_quality_scorecard,
    provider_evidence_ratios,
    provider_query_evidence_ratio,
    provider_scope_coverage_ratio,
)


EVIDENCE_STAGES = (
    "code_contract",
    "dry_run",
    "provider_scope",
    "provider_query_e2e",
    "provider_e2e",
    "live_verified",
    "quality_95",
)


@dataclass(frozen=True)
class ReadinessPolicy:
    """Validated, declarative policy loaded from a repository JSON file."""

    format_version: int
    profiles: Mapping[str, tuple[str, ...]]
    required_providers: tuple[str, ...]
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
        scope_policy = raw.get("readiness_scope")
        if not isinstance(scope_policy, Mapping):
            raise ValueError("readiness_scope policy must be an object")
        raw_providers = scope_policy.get("required_providers")
        if not isinstance(raw_providers, list) or not raw_providers:
            raise ValueError(
                "readiness_scope.required_providers must be a non-empty array"
            )
        required_providers: list[str] = []
        for provider in raw_providers:
            if (
                not isinstance(provider, str)
                or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", provider)
                or normalize_platform(provider) != provider
            ):
                raise ValueError(
                    "readiness_scope.required_providers must use normalized provider IDs"
                )
            if provider in required_providers:
                raise ValueError(
                    "readiness_scope.required_providers cannot contain duplicates"
                )
            required_providers.append(provider)
        return cls(
            format_version,
            profiles,
            tuple(required_providers),
            default_profile,
        )

    def stages_for(self, profile: str | None) -> tuple[str, ...]:
        selected = str(profile or self.default_profile).strip()
        if selected not in self.profiles:
            raise ValueError(f"unknown readiness profile: {selected}")
        return self.profiles[selected]


def _provider_readiness_status(report: Mapping[str, Any]) -> dict[str, Any]:
    """Summarize only the provider operations included in the release scope."""
    operations = [
        item for item in (report.get("operations") or [])
        if isinstance(item, Mapping)
    ]
    managed_writes = [
        item for item in operations
        if item.get("readiness_category") == "managed_write"
    ]
    queries = [
        item for item in operations
        if item.get("readiness_category") == "query"
    ]
    write_total = len(managed_writes)
    provider_e2e = sum(
        int(item.get("evidence_level") == "provider_e2e")
        for item in managed_writes
    )
    live_verified = sum(
        int(item.get("execution_status") == "live_verified")
        for item in managed_writes
    )
    return {
        "included": bool(report.get("included", False)),
        "scope": report.get("scope", ""),
        "total": int(report.get("total", 0) or 0),
        "covered": int(report.get("covered", 0) or 0),
        "gaps": int(report.get("gaps", 0) or 0),
        "coverage_ratio": float(report.get("coverage_ratio", 0.0) or 0.0),
        "query_total": int(report.get("query_total", 0) or 0),
        "query_covered": int(report.get("query_covered", 0) or 0),
        "query_e2e_items": sum(
            int(item.get("evidence_level") == "provider_e2e")
            for item in queries
        ),
        "query_e2e_ratio": (
            sum(
                int(item.get("evidence_level") == "provider_e2e")
                for item in queries
            )
            / len(queries)
            if queries
            else 0.0
        ),
        "managed_write_total": write_total,
        "managed_write_covered": int(
            report.get("managed_write_covered", 0) or 0
        ),
        "provider_e2e_items": provider_e2e,
        "provider_e2e_ratio": provider_e2e / write_total if write_total else 0.0,
        "live_verified_items": live_verified,
        "live_verified_ratio": live_verified / write_total if write_total else 0.0,
        "exclusion_reason": str(report.get("exclusion_reason") or ""),
    }

def build_readiness_report(
    *,
    tool_source_report: Mapping[str, Any],
    contract_gate_errors: list[str] | tuple[str, ...] = (),
    dry_run_report: Mapping[str, Any] | None = None,
    provider_evidence: Mapping[str, Any] | None = None,
    policy: ReadinessPolicy,
    profile: str | None = None,
) -> dict[str, Any]:
    """Build a release report and a conservative pass/fail decision.

    ``provider_e2e`` and ``live_verified`` are never inferred from local
    tests.  Callers that have controlled evidence may provide it separately;
    the local tool_source audit remains the source of provider inventory facts.
    """
    selected_profile = str(profile or policy.default_profile).strip()
    required = policy.stages_for(selected_profile)
    tool_source_issues = [str(item) for item in (tool_source_report.get("issues") or [])]
    contract_errors = [str(item) for item in contract_gate_errors]
    dry_run = dict(dry_run_report or {})
    dry_run_failures = int(dry_run.get("failed", 0) or 0)
    controlled_evidence = build_provider_evidence_report(provider_evidence) if provider_evidence else {
        "format_version": 1,
        "valid": False,
        "errors": ["未提供受控 Provider E2E 证据"],
        "run_count": 0,
        "providers": {},
    }

    code_contract_ok = not tool_source_issues and not contract_errors
    dry_run_ok = bool(dry_run.get("executed", False)) and dry_run_failures == 0

    readiness_scope_reports = tool_source_report.get("readiness_scope") or {}
    provider_summaries = {
        normalize_platform(str(platform)): _provider_readiness_status(report)
        for platform, report in readiness_scope_reports.items()
        if isinstance(report, Mapping) and report.get("included") is True
    }
    missing_providers = sorted(
        set(policy.required_providers) - set(provider_summaries)
    )
    unexpected_providers = sorted(
        set(provider_summaries) - set(policy.required_providers)
    )
    provider_targets_match = not missing_providers and not unexpected_providers
    provider_evidence_valid = controlled_evidence.get("valid") is True
    provider_scope_ok = provider_targets_match and bool(provider_summaries) and all(
        item["total"] > 0 and item["coverage_ratio"] >= 0.95
        for item in provider_summaries.values()
    )
    provider_query_e2e_ok = (
        provider_evidence_valid
        and provider_targets_match
        and bool(provider_summaries)
        and all(
            item["query_total"] > 0
            and item["query_e2e_ratio"] >= 0.95
            for item in provider_summaries.values()
        )
    )
    provider_e2e_ok = (
        provider_evidence_valid
        and provider_targets_match
        and bool(provider_summaries)
        and all(
            item["managed_write_total"] > 0
            and item["provider_e2e_ratio"] >= 0.95
            for item in provider_summaries.values()
        )
    )
    live_verified_ok = (
        provider_evidence_valid
        and provider_targets_match
        and bool(provider_summaries)
        and all(
            item["managed_write_total"] > 0
            and item["live_verified_ratio"] >= 0.95
            for item in provider_summaries.values()
        )
    )
    provider_e2e_ratio, live_verified_ratio = provider_evidence_ratios(
        readiness_scope_reports,
        policy.required_providers,
    )
    provider_query_e2e_ratio = provider_query_evidence_ratio(
        readiness_scope_reports,
        policy.required_providers,
    )
    provider_scope_ratio = provider_scope_coverage_ratio(
        readiness_scope_reports,
        policy.required_providers,
    )
    if not provider_targets_match:
        provider_scope_ratio = 0.0
        provider_query_e2e_ratio = 0.0
        provider_e2e_ratio = 0.0
        live_verified_ratio = 0.0
    if not provider_evidence_valid:
        provider_query_e2e_ratio = 0.0
        provider_e2e_ratio = 0.0
        live_verified_ratio = 0.0
    scorecard = build_quality_scorecard(
        code_contract_ok=code_contract_ok,
        dry_run_ok=dry_run_ok,
        provider_scope_ratio=provider_scope_ratio,
        provider_query_e2e_ratio=provider_query_e2e_ratio,
        generic_platform_ok=bool(dry_run.get("generic_platform_evidence", False)),
        security_ok=code_contract_ok,
        provider_e2e_ratio=provider_e2e_ratio,
        live_verified_ratio=live_verified_ratio,
        production_evidence_ok=bool(
            dry_run.get("production_evidence", False)
        ),
        max_runtime_module_lines=(
            int(dry_run["max_runtime_module_lines"])
            if dry_run.get("max_runtime_module_lines") is not None
            else None
        ),
    )
    provider_e2e_errors: list[str] = []
    provider_query_e2e_errors: list[str] = []
    live_verified_errors: list[str] = []
    if not provider_evidence_valid:
        provider_e2e_errors.extend(
            controlled_evidence.get("errors")
            or ["受控 Provider E2E 证据无效或未提供"]
        )
        provider_query_e2e_errors.extend(
            controlled_evidence.get("errors")
            or ["受控 Provider query 证据无效或未提供"]
        )
        live_verified_errors.append("受控 Provider E2E 证据无效或未提供")
    if missing_providers or unexpected_providers:
        target_errors = []
        if missing_providers:
            target_errors.append(f"缺少必需渠道: {', '.join(missing_providers)}")
        if unexpected_providers:
            target_errors.append(
                f"存在未声明的启用渠道: {', '.join(unexpected_providers)}"
            )
        target_message = "；".join(target_errors)
        provider_query_e2e_errors.append(target_message)
        provider_e2e_errors.append(target_message)
        live_verified_errors.append(target_message)
    if not provider_query_e2e_ok:
        provider_query_e2e_errors.append(
            "缺少与所有纳入范围查询 Tool/action 逐项关联的 Provider 实测证据"
        )
    if not provider_e2e_ok:
        provider_e2e_errors.append(
            "缺少与纳入范围写操作逐项关联的完整 Provider E2E 证据"
        )
    if not live_verified_ok:
        live_verified_errors.append(
            "纳入范围的 Campaign 层级写操作尚未逐项完成 live 验证"
        )

    stage_results = {
        "code_contract": {
            "status": "passed" if code_contract_ok else "failed",
            "evidence": "tool_source audit and executable Tool contract gate",
            "errors": tool_source_issues + contract_errors,
        },
        "dry_run": {
            "status": "passed" if dry_run_ok else "failed",
            "evidence": "local provider harness and Skill-up Runtime cases",
            "executed": bool(dry_run.get("executed", False)),
            "failed": dry_run_failures,
            "errors": list(dry_run.get("errors") or []),
        },
        "provider_scope": {
            "status": "passed" if provider_scope_ok else "failed",
            "evidence": "declared query APIs and campaign-hierarchy create/update contracts",
            "providers": provider_summaries,
            "missing_providers": missing_providers,
            "unexpected_providers": unexpected_providers,
            "errors": (
                []
                if provider_scope_ok
                else [
                    "Provider 必需集合不匹配，或存在未覆盖查询及 Campaign 层级写入接口"
                ]
            ),
        },
        "provider_query_e2e": {
            "status": "passed" if provider_query_e2e_ok else "not_verified",
            "evidence": "exact Tool/action outcomes from controlled Provider query calls",
            "providers": {
                name: {
                    "query_total": item["query_total"],
                    "query_e2e_items": item["query_e2e_items"],
                    "query_e2e_ratio": item["query_e2e_ratio"],
                }
                for name, item in provider_summaries.items()
            },
            "missing_providers": missing_providers,
            "unexpected_providers": unexpected_providers,
            "controlled_evidence": controlled_evidence,
            "errors": provider_query_e2e_errors,
        },
        "provider_e2e": {
            "status": "passed" if provider_e2e_ok else "not_verified",
            "evidence": "operation-specific evidence for in-scope campaign-hierarchy writes",
            "controlled_evidence": controlled_evidence,
            "errors": provider_e2e_errors,
        },
        "live_verified": {
            "status": "passed" if live_verified_ok else "not_verified",
            "evidence": "live verification for in-scope campaign-hierarchy writes",
            "errors": live_verified_errors,
        },
        "quality_95": {
            "status": "passed" if scorecard["passed"] else "failed",
            "evidence": "all platform quality dimensions must score at least 95",
            "scorecard": scorecard,
            "errors": list(scorecard["blockers"]),
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
        "tool_source_issue_count": len(tool_source_issues),
        "contract_error_count": len(contract_errors),
        "controlled_evidence": controlled_evidence,
    }
