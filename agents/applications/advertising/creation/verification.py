"""Conservative, read-only projection of the existing creation evidence files."""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import hashlib
import json
import logging
from pathlib import Path
import re
from typing import Any, Mapping


logger = logging.getLogger(__name__)
_SAFE_SCOPE = re.compile(r"^[a-zA-Z0-9_.-]{1,160}$")
_STATES = {
    "live_pass": "passed", "passed": "passed",
    "provider_rejected": "failed", "failed": "failed",
    "not_run": "not_run", "not_verified": "not_run", "skipped": "not_run",
    "live_partial": "partial", "partial": "partial",
}
_LABELS = {
    "live_verified": "已验证所列操作",
    "partial_live_verified": "部分操作已验证",
    "provider_limited": "渠道验证受阻",
    "pending_live_verification": "当前版本待实测",
    "dry_run_only": "草稿预设 · 未实测",
}
_NOTICE = "验证仅适用于所列账号、版本与参数，不授予权限，也不代表全部广告变体或投放效果通过。"


def template_values_digest(values: Any) -> str:
    encoded = json.dumps(
        values, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _operations(coverage: Mapping[str, Any]) -> list[dict[str, str]]:
    return [
        {"scope": scope, "state": _STATES.get(str(state), "unknown")}
        for scope, state in coverage.items()
        if isinstance(scope, str) and _SAFE_SCOPE.fullmatch(scope)
    ][:80]


def _legacy_operations(resources: Mapping[str, Any], prefix: str = "") -> list[dict]:
    result = []
    for key, value in resources.items():
        if not isinstance(key, str) or not _SAFE_SCOPE.fullmatch(key):
            continue
        scope = f"{prefix}.{key}" if prefix else key
        if isinstance(value, Mapping):
            result.extend(_legacy_operations(value, scope))
        elif key in {"create", "update", "readback"}:
            result.extend(_operations({scope: value}))
    return result[:80]


class CreationVerificationCatalog:
    """Evidence is advisory. No registry, policy or Provider calls are reachable."""

    def __init__(self, memory_entries=(), *, legacy_runs=(), available=True):
        self.available = available
        self._entries: dict[tuple[str, str, str], list[dict]] = {}
        for row in memory_entries:
            if not isinstance(row, Mapping):
                continue
            key = (row.get("provider", ""), row.get("test_account", ""),
                   row.get("template_key", ""))
            self._entries.setdefault(key, []).append(deepcopy(dict(row)))
        self._legacy_runs = deepcopy(list(legacy_runs))

    def summarize(self, template: Mapping[str, Any]) -> dict[str, Any]:
        result = {
            "status": "pending_live_verification", "match": "none",
            "blueprint_version": str(template.get("blueprint_version") or ""),
            "verified_at": "", "operations": [], "historical_operations": [],
            "blockers": [], "notice": _NOTICE,
            "evidence_available": self.available,
        }
        if template.get("source") == "user":
            return self._finish(result)
        if not template.get("account_id"):
            result["status"] = "dry_run_only"
            return self._finish(result)
        key = (template.get("provider", ""), template.get("account_id", ""),
               template.get("catalog_key", template.get("key", "")))
        candidates = sorted(
            self._entries.get(key, []),
            key=lambda row: str(row.get("last_verified_at") or ""), reverse=True,
        )
        exact = next((row for row in candidates if self._matches(row, template)), None)
        if exact is not None:
            result.update(self._exact_result(exact))
        elif candidates:
            result["match"] = "historical"
            result["historical_operations"] = _operations(candidates[0].get("coverage") or {})
            if candidates[0].get("verification_state") == "blocked_by_provider":
                result["blockers"].append("同账号旧版本存在渠道阻断记录，尚未确认解除。")
        else:
            result["historical_operations"] = self._historical_operations(template)
            if result["historical_operations"]:
                result["match"] = "historical"
        return self._finish(result)

    @staticmethod
    def _matches(row: Mapping, template: Mapping) -> bool:
        return (
            row.get("blueprint_id") == template.get("blueprint_id")
            and row.get("blueprint_version") == template.get("blueprint_version")
            and row.get("template_values_sha256") == template_values_digest(
                template.get("values") or {},
            )
        )

    @staticmethod
    def _exact_result(row: Mapping) -> dict:
        operations = _operations(row.get("coverage") or {})
        states = {item["state"] for item in operations}
        declared = row.get("verification_state")
        blocked = declared == "blocked_by_provider" or "failed" in states
        status = "pending_live_verification"
        if blocked:
            status = "provider_limited"
        elif operations and states == {"passed"} and declared == "live_verified":
            status = "live_verified"
        elif states & {"passed", "partial"}:
            status = "partial_live_verified"
        return {
            "status": status, "match": "exact", "operations": operations,
            "verified_at": str(row.get("last_verified_at") or "")[:40],
            "blockers": ["上次验证存在渠道拒绝，未完成的层级不能视为成功。"] if blocked else [],
        }

    def _historical_operations(self, template: Mapping) -> list[dict]:
        values = template.get("values") or {}
        campaign_type = (
            template.get("campaign_type")
            or values.get("campaign.objective_type")
            or values.get("campaign.advertising_channel_type")
            or template.get("ad_format")
        )
        matches = [
            row for row in self._legacy_runs if isinstance(row, Mapping)
            and row.get("provider") == template.get("provider")
            and row.get("test_account") == template.get("account_id")
            and campaign_type == row.get("campaign_type")
        ]
        return _legacy_operations(matches[-1].get("resources") or {}) if matches else []

    @staticmethod
    def _finish(result: dict) -> dict:
        result["label"] = _LABELS[result["status"]]
        if result["match"] == "historical":
            result["notice"] = "已有历史操作记录，但未绑定当前模板版本与参数；" + _NOTICE
        if not result["evidence_available"]:
            result["blockers"].append("验证记录暂不可用，不能确认实测结果。")
        return result


@lru_cache(maxsize=1)
def load_creation_verification() -> CreationVerificationCatalog:
    root = Path(__file__).resolve().parents[3] / "tools" / "advertising" / "contracts"
    try:
        documents = []
        for filename in ("provider_live_e2e_memory.json", "provider_e2e_evidence.json"):
            path = root / filename
            if path.stat().st_size > 2_000_000:
                raise ValueError("evidence size limit")
            document = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(document, dict):
                raise ValueError("evidence root")
            documents.append(document)
        memory, legacy = documents
        if (not isinstance(memory.get("campaign_types"), list)
                or not isinstance(legacy.get("runs"), list)):
            raise ValueError("evidence rows")
        return CreationVerificationCatalog(memory["campaign_types"], legacy_runs=legacy["runs"])
    except (OSError, ValueError, TypeError):
        logger.warning("创建验证记录加载失败；模板按未验证处理")
        return CreationVerificationCatalog(available=False)
