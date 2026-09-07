"""Security and execution-boundary services for Agent Runtime."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timedelta
from typing import Any, Optional

from ..core.interfaces import ExecutionMode, ToolError, ToolResult
from ..core.security import (
    PROTECTED_INPUT_FIELDS,
    canonical_json,
    normalize_field_name,
    protected_field_paths,
    protected_update_paths,
    request_hash,
    sha256_json,
)


class RuntimeSecurity:
    """Common red-line, approval and result-boundary checks."""

    PROTECTED_INPUT_FIELDS = PROTECTED_INPUT_FIELDS

    def __init__(self, runtime: Any):
        self.runtime = runtime

    def validate_input_redline(self, value: Any) -> list[str]:
        paths = protected_field_paths(
            value, self.PROTECTED_INPUT_FIELDS, limit=100
        )

        def visit(node: Any, path: str = "") -> None:
            if isinstance(node, dict):
                for key, child in node.items():
                    key_text = str(key)
                    current = f"{path}.{key_text}" if path else key_text
                    if normalize_field_name(key_text) in {"updates", "update"}:
                        paths.extend(protected_update_paths(child, current))
                    else:
                        visit(child, current)
            elif isinstance(node, (list, tuple)):
                for index, child in enumerate(node):
                    visit(child, f"{path}[{index}]")

        visit(value)
        return list(dict.fromkeys(paths))[:10]

    def sanitize_result(self, result: ToolResult) -> ToolResult:
        """Redact a Tool result before it leaves the Runtime boundary.

        Persistence and prompt-context redaction are not sufficient: callers
        can also receive the in-memory ``ToolResult`` directly through the
        API, a Feature, or an injected Runtime.  Provider responses and
        exception messages are untrusted data, so data, error text, and
        confirmation cards must all use the same central redactor.
        """
        if not isinstance(result, ToolResult):
            return result
        redact = self.runtime._redact_for_persistence
        result.data = redact(result.data)
        result.error = redact(result.error)
        if result.error_detail:
            detail = result.error_detail
            result.error_detail = ToolError(
                category=detail.category,
                code=detail.code,
                message=str(redact(detail.message)),
                suggestion=str(redact(detail.suggestion)),
            )
        result.card_payload = redact(result.card_payload)
        return result

    @staticmethod
    def confirmation_plan(
        session_id: str,
        user_id: str,
        account_id: str,
        tool_def: Any,
        input_data: dict,
        preview: Optional[dict] = None,
    ) -> dict[str, Any]:
        normalized = canonical_json(input_data)
        input_digest = sha256_json(input_data)
        preview_payload = preview if preview is not None else input_data
        preview_digest = sha256_json(preview_payload)
        request_digest = request_hash(
            getattr(tool_def, "platform", ""), account_id,
            getattr(tool_def, "name", ""), input_digest,
        )
        idempotency_key = hashlib.sha256(
            f"{user_id}:{tool_def.name}:{normalized}".encode("utf-8")
        ).hexdigest()[:16]
        material = "|".join((
            str(session_id), str(account_id or ""), tool_def.name,
            normalized, idempotency_key,
        ))
        fingerprint = hashlib.sha256(material.encode("utf-8")).hexdigest()
        token = hashlib.sha256(
            f"ad-agent-confirm-v1:{fingerprint}".encode("utf-8")
        ).hexdigest()
        return {
            "session_id": str(session_id),
            "user_id": str(user_id),
            "account_id": str(account_id or ""),
            "tool": tool_def.name,
            "plan_fingerprint": fingerprint,
            "confirmation_token": token,
            "idempotency_key": idempotency_key,
            "input_hash": input_digest,
            "preview_hash": preview_digest,
            "request_hash": request_digest,
            "contract_hash": str(getattr(tool_def, "contract_hash", "") or ""),
            "preview": preview_payload,
        }

    def prepare_confirmation(
        self, expected: dict[str, Any], create: bool = False,
        ttl_seconds: int = 600,
    ) -> dict[str, Any]:
        manager = self.runtime._session_manager
        if not manager:
            if create:
                return {**expected, "approval_persistence": "in_memory"}
            return expected
        existing = manager.get_approval(expected["plan_fingerprint"])
        if existing:
            return {**expected, "expires_at": str(existing.get("expires_at", ""))}
        if create:
            expires_at = (
                datetime.now() + timedelta(seconds=ttl_seconds)
            ).isoformat()
            manager.create_approval(
                expected["plan_fingerprint"],
                expected["confirmation_token"],
                expected["session_id"],
                expected.get("user_id", ""),
                expected["account_id"],
                expected["tool"],
                expires_at,
                expected.get("input_hash"), expected.get("preview_hash"),
                expected.get("request_hash"), expected.get("contract_hash"),
            )
            return {**expected, "expires_at": expires_at}
        return expected

    def validate_confirmation_record(
        self, expected: dict[str, Any], payload: dict
    ) -> tuple[bool, str]:
        manager = self.runtime._session_manager
        if not manager:
            return True, ""
        return manager.validate_approval(
            expected["plan_fingerprint"],
            expected["confirmation_token"],
            expected["session_id"],
            expected.get("user_id", ""),
            expected["account_id"],
            expected["tool"],
            expected.get("input_hash"), expected.get("preview_hash"),
            expected.get("request_hash"), expected.get("contract_hash"),
        )

    @staticmethod
    def confirmation_matches(
        payload: Optional[dict], expected: dict[str, Any]
    ) -> bool:
        if not isinstance(payload, dict) or payload.get("type") != "confirm_write":
            return False
        return all(
            str(payload.get(key, "")) == str(expected.get(key, ""))
            for key in (
                "session_id", "user_id", "account_id", "tool",
                "plan_fingerprint", "confirmation_token", "idempotency_key",
                "input_hash", "preview_hash", "request_hash", "contract_hash",
            )
        )

    def apply_read_data_boundary(
        self, tool_name: str, result: ToolResult
    ) -> ToolResult:
        if self.runtime.offline_mode or not result or not result.success:
            return result
        try:
            definition, _ = self.runtime._get_registered_tool(tool_name)
        except KeyError:
            return result
        if not definition.is_read_tool:
            return result
        data = result.data if isinstance(result.data, dict) else {}
        data_status = str(data.get("data_status") or "")
        if (
            result.simulated
            or data.get("simulated") is True
            or data_status.startswith("offline")
        ):
            return ToolResult.error(
                f"{tool_name} 没有配置 Provider Client；当前未启用 offline_mode，"
                "不会返回模拟查询数据"
            )
        return result

    @staticmethod
    def normalize_read_result_evidence(
        tool_def: Any, result: ToolResult
    ) -> ToolResult:
        if not result or not result.success or not tool_def.is_read_tool:
            return result
        data = result.data if isinstance(result.data, dict) else {}
        if result.simulated or data.get("simulated") is True:
            if data.get("data_status") == "offline_mock":
                return result
            result.data = {
                **data, "data_status": "offline_mock", "simulated": True,
            }
            return result
        if data.get("data_status"):
            return result
        result.data = {**data, "data_status": "unknown"}
        return result

    @staticmethod
    def enforce_result_limit(result: ToolResult, tool_def: Any) -> ToolResult:
        limit = int(getattr(tool_def, "max_output_bytes", 1_000_000) or 1_000_000)
        try:
            size = len(json.dumps(
                result.data, ensure_ascii=False, default=str
            ).encode("utf-8"))
        except (TypeError, ValueError):
            return ToolResult.error(f"{tool_def.name} 返回了不可序列化的结果")
        if size <= limit:
            return result
        return ToolResult.error(
            f"{tool_def.name} 返回结果超过大小限制（最多 {limit} 字节）"
        )

    @staticmethod
    def is_uncertain_provider_failure(
        tool_def: Any, result: ToolResult
    ) -> bool:
        if not tool_def.is_write_tool or not result or result.success:
            return False
        data = result.data if isinstance(result.data, dict) else {}
        if str(data.get("execution_status") or "").lower() in {
            "unknown", "timed_out", "timeout", "transport_unknown",
        }:
            return True
        message = str(result.error or "").lower()
        return any(marker in message for marker in (
            "timeout", "timed out", "deadline", "connection error",
            "rate limit", "rate limited", "server error", "http 5",
            "temporarily unavailable", "temporary error",
        ))
