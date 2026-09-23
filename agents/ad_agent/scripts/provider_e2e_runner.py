"""Controlled Provider E2E runner and redacted evidence builder.

This module is deliberately adapter-based.  It does not discover credentials,
construct provider clients, or bypass the normal Tool gates.  A deployment
supplies a trusted adapter and an explicit allowlist for test accounts.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence

from agents.ad_agent.core.namespace import normalize_namespace


class ProviderE2EAdapter(Protocol):
    """Provider adapter used only after all live-write gates pass."""

    def execute(self, operation: str, payload: Mapping[str, Any]) -> Any:
        ...


@dataclass(frozen=True)
class ProviderE2ERequest:
    provider: str
    account_ref: str
    campaign_type: str
    operations: Sequence[str] = field(default_factory=tuple)
    execution_mode: str = "dry_run"
    confirmed: bool = False
    require_paused: bool = True
    idempotency_key: str = ""
    paused_statuses: Sequence[str] = ("PAUSED", "DISABLE", "DISABLED")


def _preview(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "missing"
    return f"…{text[-4:]}" if len(text) > 4 else "configured"


def _hash(value: Any) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()[:16]


def _resource_name(operation: str) -> str:
    value = str(operation or "").strip().lower()
    if value.startswith("read_"):
        value = value[5:]
    if value.startswith("create_"):
        value = value[7:]
    if value.startswith("update_"):
        value = value[7:]
    return value or "resource"


def _is_write(operation: str) -> bool:
    return str(operation or "").strip().lower().startswith((
        "create_", "update_", "delete_", "enable_", "activate_",
    ))


class ProviderE2ERunner:
    """Run only explicitly declared, test-account-scoped scenarios."""

    def __init__(
        self,
        *,
        adapter: ProviderE2EAdapter,
        allowed_test_accounts: Mapping[str, Sequence[str] | set[str]],
    ) -> None:
        self.adapter = adapter
        self.allowed_test_accounts = {
            normalize_namespace(provider): {
                str(account).strip()
                for account in accounts
                if str(account).strip()
            }
            for provider, accounts in allowed_test_accounts.items()
        }

    def _blocked(self, reason: str, request: ProviderE2ERequest) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "provider": normalize_namespace(request.provider),
            "campaign_type": str(request.campaign_type or "").strip(),
            "status": "blocked",
            "blocked_reason": reason,
            "account_preview": _preview(request.account_ref),
            "idempotency_key_hash": _hash(request.idempotency_key),
        }

    @staticmethod
    def _safe_response(value: Any) -> Mapping[str, Any]:
        return value if isinstance(value, Mapping) else {}

    def run(self, request: ProviderE2ERequest) -> dict[str, Any]:
        provider = normalize_namespace(request.provider)
        account_ref = str(request.account_ref or "").strip()
        campaign_type = str(request.campaign_type or "").strip()
        operations = tuple(
            str(operation).strip()
            for operation in (request.operations or ())
            if str(operation).strip()
        )
        if not provider or not account_ref or not campaign_type or not operations:
            return self._blocked("invalid_request", request)
        if any(_is_write(operation) for operation in operations):
            if str(request.execution_mode or "").strip().lower() != "live":
                return self._blocked("live_execution_required", request)
            if not request.confirmed:
                return self._blocked("explicit_confirmation_required", request)
            if not request.idempotency_key.strip():
                return self._blocked("idempotency_key_required", request)
            if account_ref not in self.allowed_test_accounts.get(provider, set()):
                return self._blocked("test_account_not_allowlisted", request)
        rows: dict[str, dict[str, Any]] = {}
        failures: list[str] = []
        for operation in operations:
            resource = _resource_name(operation)
            payload = {
                "account_ref": account_ref,
                "campaign_type": campaign_type,
                "idempotency_key": request.idempotency_key,
            }
            try:
                response = self._safe_response(
                    self.adapter.execute(operation, payload)
                )
            except Exception as error:
                rows[resource] = {
                    "operation": operation,
                    "state": "failed",
                    "error_type": type(error).__name__,
                }
                failures.append(resource)
                continue
            resource_id = str(response.get("id") or "").strip()
            status = str(response.get("status") or "").strip().upper()
            row = {
                "operation": operation,
                "state": "passed" if resource_id else "unknown",
                "id": _preview(resource_id),
                "status": status or "unknown",
            }
            if _is_write(operation):
                if request.require_paused and status not in {
                    str(item).strip().upper()
                    for item in request.paused_statuses
                    if str(item).strip()
                }:
                    row["state"] = "failed"
                    row["error_type"] = "resource_not_paused"
                    failures.append(resource)
                    rows[resource] = row
                    continue
                if not resource_id:
                    failures.append(resource)
                    rows[resource] = row
                    continue
                read_operation = f"read_{resource}"
                try:
                    readback = self._safe_response(
                        self.adapter.execute(
                            read_operation,
                            {
                                "account_ref": account_ref,
                                "id": resource_id,
                            },
                        )
                    )
                except Exception as error:
                    row["readback"] = "failed"
                    row["readback_error_type"] = type(error).__name__
                    failures.append(resource)
                    rows[resource] = row
                    continue
                readback_id = str(readback.get("id") or "").strip()
                readback_status = str(
                    readback.get("status") or ""
                ).strip().upper()
                row["readback"] = (
                    "passed"
                    if readback_id == resource_id
                    and (
                        not request.require_paused
                        or readback_status in {
                            str(item).strip().upper()
                            for item in request.paused_statuses
                            if str(item).strip()
                        }
                    )
                    else "failed"
                )
                if row["readback"] != "passed":
                    failures.append(resource)
            rows[resource] = row
        return {
            "schema_version": "1.0",
            "provider": provider,
            "campaign_type": campaign_type,
            "status": (
                "failed"
                if failures
                else "live_verified"
                if any(_is_write(operation) for operation in operations)
                else "read_verified"
            ),
            "account_preview": _preview(account_ref),
            "idempotency_key_hash": _hash(request.idempotency_key),
            "resources": rows,
            "failures": sorted(set(failures)),
        }


__all__ = ["ProviderE2EAdapter", "ProviderE2ERequest", "ProviderE2ERunner"]
