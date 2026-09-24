"""Auditable quality scorecard for the Agent platform release gate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


QUALITY_THRESHOLD = 95


@dataclass(frozen=True)
class QualityDimension:
    """One independently evidenced quality dimension."""

    name: str
    score: int
    evidence: str
    blockers: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return self.score >= QUALITY_THRESHOLD and not self.blockers

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "score": self.score,
            "threshold": QUALITY_THRESHOLD,
            "passed": self.passed,
            "evidence": self.evidence,
            "blockers": list(self.blockers),
        }


def _binary_dimension(
    name: str,
    passed: bool,
    *,
    evidence: str,
    blocker: str,
) -> QualityDimension:
    return QualityDimension(
        name=name,
        score=100 if passed else 0,
        evidence=evidence,
        blockers=() if passed else (blocker,),
    )


def _ratio(value: Any) -> int:
    try:
        normalized = float(value)
    except (TypeError, ValueError):
        normalized = 0.0
    return max(0, min(100, round(normalized * 100)))


def build_quality_scorecard(
    *,
    code_contract_ok: bool,
    dry_run_ok: bool,
    provider_scope_ratio: float,
    provider_query_e2e_ratio: float,
    generic_platform_ok: bool,
    security_ok: bool,
    provider_e2e_ratio: float,
    live_verified_ratio: float,
    production_evidence_ok: bool,
    max_runtime_module_lines: int | None,
    maintainability_target_lines: int = 400,
) -> dict[str, Any]:
    """Build the hard 95-point release scorecard.

    Ratios are derived from operation-specific evidence, not Tool counts.
    Maintainability is deliberately strict: a large runtime module is a
    measurable blocker until its responsibilities are split.
    """
    if max_runtime_module_lines is None:
        maintainability = QualityDimension(
            name="maintainability",
            score=0,
            evidence="largest advertising runtime module size was not measured",
            blockers=("runtime module size evidence is missing",),
        )
    else:
        measured_lines = int(max_runtime_module_lines)
        maintainability = QualityDimension(
            name="maintainability",
            score=max(
                0,
                min(
                    100,
                    round(
                        maintainability_target_lines
                        / max(1, measured_lines)
                        * 100
                    ),
                ),
            ),
            evidence=(
                f"largest advertising runtime module is "
                f"{measured_lines} lines; target is "
                f"{int(maintainability_target_lines)}"
            ),
            blockers=(
                ()
                if measured_lines <= int(maintainability_target_lines)
                else (
                    "advertising runtime module exceeds the maintainability target",
                )
            ),
        )

    dimensions = [
        _binary_dimension(
            "code_contract",
            code_contract_ok,
            evidence="Tool Source audit and executable contract snapshot",
            blocker="code contract or Tool Source audit failed",
        ),
        _binary_dimension(
            "dry_run",
            dry_run_ok,
            evidence="local Provider contract harness and Skill-up cases",
            blocker="dry-run or Skill-up evidence failed",
        ),
        QualityDimension(
            name="provider_scope",
            score=_ratio(provider_scope_ratio),
            evidence="all declared query APIs and campaign-hierarchy create/update operations",
            blockers=(
                ()
                if _ratio(provider_scope_ratio) >= QUALITY_THRESHOLD
                else ("in-scope Provider API contract coverage is below 95%",)
            ),
        ),
        QualityDimension(
            name="provider_query_e2e",
            score=_ratio(provider_query_e2e_ratio),
            evidence="declared query API operations exercised against controlled Provider accounts",
            blockers=(
                ()
                if _ratio(provider_query_e2e_ratio) >= QUALITY_THRESHOLD
                else ("Provider query E2E coverage is below 95%",)
            ),
        ),
        _binary_dimension(
            "generic_platform",
            generic_platform_ok,
            evidence="standalone Harness package and non-advertising reference application",
            blocker="generic Harness isolation evidence is incomplete",
        ),
        _binary_dimension(
            "security",
            security_ok,
            evidence="schema, permission, scope, redline, idempotency and audit gates",
            blocker="security audit evidence is incomplete",
        ),
        QualityDimension(
            name="provider_e2e",
            score=_ratio(provider_e2e_ratio),
            evidence="operation-specific controlled Provider E2E evidence",
            blockers=(
                ()
                if _ratio(provider_e2e_ratio) >= QUALITY_THRESHOLD
                else ("Provider E2E coverage is below 95%",)
            ),
        ),
        QualityDimension(
            name="live_verified",
            score=_ratio(live_verified_ratio),
            evidence="operation-specific live verification evidence",
            blockers=(
                ()
                if _ratio(live_verified_ratio) >= QUALITY_THRESHOLD
                else ("live-verified operation coverage is below 95%",)
            ),
        ),
        _binary_dimension(
            "production",
            production_evidence_ok,
            evidence="multi-instance, worker, observability and recovery evidence",
            blocker="production deployment evidence is not supplied",
        ),
        maintainability,
    ]
    encoded = [item.to_dict() for item in dimensions]
    blockers = [
        f"{item['name']}: {blocker}"
        for item in encoded
        for blocker in item["blockers"]
    ]
    return {
        "threshold": QUALITY_THRESHOLD,
        "passed": not blockers and all(item["passed"] for item in encoded),
        "dimensions": encoded,
        "blocking_dimensions": [
            item["name"] for item in encoded if not item["passed"]
        ],
        "blockers": blockers,
    }


def provider_evidence_ratios(
    readiness_scope_reports: Mapping[str, Any],
    required_providers: Iterable[str] = (),
) -> tuple[float, float]:
    """Return the weakest provider's E2E and live ratios for managed writes."""
    provider_ratios: list[tuple[float, float]] = []
    included_providers: set[str] = set()
    for provider, report in readiness_scope_reports.items():
        if not isinstance(report, Mapping) or report.get("included") is False:
            continue
        included_providers.add(str(provider))
        operations = report.get("operations") or []
        total = 0
        provider_e2e = 0
        live_verified = 0
        for operation in operations:
            if (
                not isinstance(operation, Mapping)
                or operation.get("readiness_category") != "managed_write"
            ):
                continue
            total += 1
            provider_e2e += int(operation.get("evidence_level") == "provider_e2e")
            live_verified += int(
                operation.get("execution_status") == "live_verified"
            )
        if total:
            provider_ratios.append(
                (provider_e2e / total, live_verified / total)
            )
    missing = set(str(provider) for provider in required_providers) - included_providers
    provider_ratios.extend((0.0, 0.0) for _ in missing)
    if not provider_ratios:
        return 0.0, 0.0
    return (
        min(ratio[0] for ratio in provider_ratios),
        min(ratio[1] for ratio in provider_ratios),
    )


def provider_scope_coverage_ratio(
    readiness_scope_reports: Mapping[str, Any],
    required_providers: Iterable[str] = (),
) -> float:
    """Return the weakest included provider's contract coverage ratio."""
    ratios: list[float] = []
    included_providers: set[str] = set()
    for provider, report in readiness_scope_reports.items():
        if not isinstance(report, Mapping) or report.get("included") is False:
            continue
        included_providers.add(str(provider))
        total = int(report.get("total", 0) or 0)
        covered = int(report.get("covered", 0) or 0)
        ratios.append(covered / total if total else 0.0)
    missing = set(str(provider) for provider in required_providers) - included_providers
    ratios.extend(0.0 for _ in missing)
    return min(ratios) if ratios else 0.0


def provider_query_evidence_ratio(
    readiness_scope_reports: Mapping[str, Any],
    required_providers: Iterable[str] = (),
) -> float:
    """Return the weakest required provider's query E2E coverage."""
    ratios: list[float] = []
    included_providers: set[str] = set()
    for provider, report in readiness_scope_reports.items():
        if not isinstance(report, Mapping) or report.get("included") is False:
            continue
        included_providers.add(str(provider))
        operations = [
            operation
            for operation in (report.get("operations") or [])
            if isinstance(operation, Mapping)
            and operation.get("readiness_category") == "query"
        ]
        if operations:
            verified = sum(
                int(operation.get("evidence_level") == "provider_e2e")
                for operation in operations
            )
            ratios.append(verified / len(operations))
        else:
            ratios.append(0.0)
    missing = set(str(provider) for provider in required_providers) - included_providers
    ratios.extend(0.0 for _ in missing)
    return min(ratios) if ratios else 0.0


__all__ = [
    "QUALITY_THRESHOLD",
    "QualityDimension",
    "build_quality_scorecard",
    "provider_evidence_ratios",
    "provider_query_evidence_ratio",
    "provider_scope_coverage_ratio",
]
