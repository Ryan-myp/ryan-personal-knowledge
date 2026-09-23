"""Auditable quality scorecard for the Agent platform release gate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


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
    inventory_reports: Mapping[str, Any],
) -> tuple[float, float]:
    """Calculate E2E/live ratios from operation inventory evidence."""
    total = 0
    provider_e2e = 0
    live_verified = 0
    for report in inventory_reports.values():
        if not isinstance(report, Mapping):
            continue
        total += int(report.get("total", 0) or 0)
        evidence = report.get("evidence_levels") or {}
        execution = report.get("execution_statuses") or {}
        provider_e2e += int(evidence.get("provider_e2e", 0) or 0)
        live_verified += int(execution.get("live_verified", 0) or 0)
    if total <= 0:
        return 0.0, 0.0
    return provider_e2e / total, live_verified / total


__all__ = [
    "QUALITY_THRESHOLD",
    "QualityDimension",
    "build_quality_scorecard",
    "provider_evidence_ratios",
]
