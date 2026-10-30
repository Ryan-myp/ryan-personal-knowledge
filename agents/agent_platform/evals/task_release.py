"""Offline verification of current-source, repeated task evaluation artifacts."""

from datetime import datetime, timedelta, timezone
import hashlib
import json


def dataset_digest(cases):
    data = [case.model_dump(mode="json") for case in cases]
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def source_digest(root):
    """Hash deployed code/context, excluding credentials, databases and generated evidence."""
    digest = hashlib.sha256()
    total, count = 0, 0
    roots = [root / "agents" / name for name in (
        "agent_harness", "agent_platform", "applications", "tools", "skills",
        "knowledge", "scenarios", "deployments", "evals",
    )] + [root / "scripts" / "advertising"]
    for directory in roots:
        for path in sorted(directory.rglob("*")):
            if "evidence" in path.relative_to(root).parts:
                continue
            if path.suffix not in {".py", ".js", ".json", ".yaml", ".yml", ".md", ".html", ".css"}:
                continue
            if path.is_symlink() or not path.is_file():
                continue
            size = path.stat().st_size
            count, total = count + 1, total + size
            if count > 6000 or total > 100_000_000:
                raise ValueError("evaluation source fingerprint exceeds bounded scan")
            digest.update(str(path.relative_to(root)).encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    if count == 0:
        raise ValueError("evaluation source fingerprint is empty")
    return digest.hexdigest()


def verify_task_report(report, cases, *, source_sha256, now=None):
    if report is None:
        return {"status": "not_verified", "errors": ["task_evidence_missing"]}
    if not isinstance(report, dict):
        return {"status": "failed", "errors": ["task_evidence_invalid"]}
    errors = []
    if (report.get("mode") != "model_backed_offline_providers"
            or report.get("complete") is not True or report.get("release_ready") is not True):
        errors.append("complete_passing_model_suite_required")
    identity = report.get("identity")
    identity = identity if isinstance(identity, dict) else {}
    if (identity.get("source_sha256") != source_sha256
            or identity.get("source_unchanged") is not True):
        errors.append("source_changed_or_unverified")
    if identity.get("dataset_sha256") != dataset_digest(cases):
        errors.append("dataset_changed_or_incomplete")
    if not _fresh(identity.get("recorded_at"), now or datetime.now(timezone.utc)):
        errors.append("stale_or_invalid_timestamp")
    if not _complete_attempts(report, cases):
        errors.append("three_complete_passing_repeats_required")
    return {"status": "failed" if errors else "passed", "errors": errors,
            "evidence": "current_source_repeated_tasks", "provider_e2e": False}


def _fresh(value, now):
    try:
        stamp = datetime.fromisoformat(value)
        return stamp.tzinfo is not None and timedelta(0) <= now - stamp <= timedelta(days=7)
    except (TypeError, ValueError):
        return False


def _complete_attempts(report, cases):
    repeats = report.get("repeats")
    rows = report.get("cases")
    if type(repeats) is not int or not 3 <= repeats <= 5 or not isinstance(rows, list):
        return False
    expected = {(case.id, n) for case in cases for n in range(1, repeats + 1)}
    actual = []
    for row in rows:
        if (not isinstance(row, dict) or row.get("status") != "passed"
                or type(row.get("checks")) is not int or row["checks"] < 1
                or not isinstance(row.get("id"), str) or type(row.get("attempt")) is not int):
            return False
        actual.append((row["id"], row["attempt"]))
    return bool(expected) and len(actual) == len(expected) and set(actual) == expected
