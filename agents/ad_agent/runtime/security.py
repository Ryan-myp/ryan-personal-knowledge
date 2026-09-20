"""Security and execution-boundary services for Agent Runtime."""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timedelta
from typing import Any, Optional

from ..core.interfaces import ExecutionMode, ToolError, ToolResult
from ..domain.ad.security import (
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

    def validate_text_redline(self, value: str) -> list[str]:
        """Reject credential-shaped assignments before intent parsing.

        Natural language is not a structured Tool payload, so a request that
        only contains a credential field would otherwise be invisible to the
        schema-driven parser when no Tool Source is loaded. Inspect only the
        field name and return no value; the caller redacts the original text
        before persistence or model use.
        """
        text = str(value or "")
        found: list[str] = []
        def field_expression(field: str) -> str:
            # Structured red-line names are normalized (``accesstoken``),
            # while chat text commonly uses ``access_token`` or ``access
            # token``. Allow separators only inside a declared protected
            # field; this does not create a business vocabulary.
            return r"[_\s-]*".join(re.escape(char) for char in str(field))

        field_pattern = "|".join(
            field_expression(field)
            for field in sorted(self.PROTECTED_INPUT_FIELDS, key=len, reverse=True)
        )
        for match in re.finditer(
            rf"(?<![A-Za-z0-9_])(?P<field>{field_pattern})(?![A-Za-z0-9_])"
            r"\s*(?:=|:|：|是|为)",
            text,
            re.IGNORECASE,
        ):
            field = match.group("field")
            if field not in found:
                found.append(field)
            if len(found) >= 10:
                break
        return found

    @staticmethod
    def redact_for_persistence(value: Any) -> Any:
        """移除可能包含凭证的字段后再写入 SQLite。"""
        sensitive = (
            "token", "secret", "api_key", "private_key", "private_key_id",
            "service_account", "sa_email", "developer_key", "credential", "authorization",
            "bc_id", "bcid", "partner_id", "partnerid", "perter_id", "perterid", "developer_token",
            "mcc", "login_customer_id", "logincustomerid",
            "manager_customer_id", "managercustomerid", "client_id", "clientid",
        )
        if isinstance(value, dict):
            return {
                k: (
                    RuntimeSecurity.redact_for_persistence(v)
                    if str(k).lower() in {"selection_token", "selection_tokens"}
                    else "<redacted>"
                    if any(part in str(k).lower() for part in sensitive)
                    else RuntimeSecurity.redact_for_persistence(v)
                )
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [RuntimeSecurity.redact_for_persistence(v) for v in value]
        if isinstance(value, str):
            # User messages are persisted as strings, so key-based redaction
            # alone is insufficient when a secret is pasted into chat.
            patterns = (
                # Quoted JSON/Python values, e.g. {'access_token': '...'}.
                r"(?is)(?P<prefix>['\"]?(?:access|refresh|developer)[_-]?token['\"]?\s*[:=]\s*)['\"][^'\"]*['\"]",
                r"(?is)(?P<prefix>['\"]?private[_-]?key['\"]?\s*[:=]\s*)['\"]-----BEGIN.*?-----END[^\r\n]*-----['\"]",
                r"(?is)(?P<prefix>['\"]?private[_-]?key['\"]?\s*[:=]\s*)['\"][^'\"]*['\"]",
                r"(?is)(?P<prefix>['\"]?client[_-]?secret['\"]?\s*[:=]\s*)['\"][^'\"]*['\"]",
                r"(?is)(?P<prefix>['\"]?(?:bc[_-]?id|partner[_-]?id|perter[_-]?id|mcc|login[_-]?customer[_-]?id|manager[_-]?customer[_-]?id|client[_-]?id)['\"]?\s*[:=]\s*)['\"][^'\"]*['\"]",
                r"(?is)(?P<prefix>['\"]?authorization['\"]?\s*[:=]\s*)['\"][^'\"]*['\"]",
                # Unquoted key/value forms used by logs and CLI snippets.
                r"(?i)(?P<prefix>\b(?:access|refresh|developer)[_-]?token\s*[:=]\s*)[^\s,;}]+",
                r"(?is)(?P<prefix>\bprivate[_-]?key\s*[:=]\s*)-----BEGIN.*?-----END[^\r\n]*-----",
                r"(?i)(?P<prefix>\bprivate[_-]?key\s*[:=]\s*)[^\s,;}]+",
                r"(?i)(?P<prefix>\bclient[_-]?secret\s*[:=]\s*)[^\s,;}]+",
                r"(?i)(?P<prefix>\b(?:bc[_-]?id|partner[_-]?id|perter[_-]?id|mcc|login[_-]?customer[_-]?id|manager[_-]?customer[_-]?id|client[_-]?id|authorization)\s*[:=]\s*)[^\s,;}]+",
            )
            redacted = value
            for pattern in patterns:
                redacted = re.sub(
                    pattern,
                    lambda match: f"{match.group('prefix')}<redacted>",
                    redacted,
                )
            return redacted
        return value

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

    @staticmethod
    def confirmation_chain_plan(
        session_id: str,
        user_id: str,
        account_id: str,
        platform: str,
        tool_defs: list[Any],
        request_context: dict[str, Any],
        preview: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Create one approval binding for a dependent creation chain.

        A Campaign -> child-resource chain is one operator decision even
        though it contains several write Tools.  The approval binds the
        complete declarative request and ordered Tool contract set; generated
        parent IDs are deliberately not part of the request context because
        they are provider output, not operator input.
        """
        tools = [str(getattr(tool, "name", "")) for tool in tool_defs]
        contract_hash = sha256_json([
            {
                "name": str(getattr(tool, "name", "")),
                "contract_hash": str(getattr(tool, "contract_hash", "") or ""),
            }
            for tool in tool_defs
        ])
        manifest = {
            "platform": str(platform),
            "tools": tools,
            "request": request_context,
        }
        normalized = canonical_json(manifest)
        input_digest = sha256_json(manifest)
        request_digest = request_hash(str(platform), account_id, "__creation_plan__", input_digest)
        idempotency_key = hashlib.sha256(
            f"{user_id}:__creation_plan__:{normalized}".encode("utf-8")
        ).hexdigest()[:16]
        fingerprint = hashlib.sha256(
            "|".join((
                str(session_id), str(account_id or ""), str(platform),
                normalized, idempotency_key,
            )).encode("utf-8")
        ).hexdigest()
        token = hashlib.sha256(
            f"ad-agent-confirm-chain-v1:{fingerprint}".encode("utf-8")
        ).hexdigest()
        return {
            "type": "confirm_write_plan",
            "session_id": str(session_id),
            "user_id": str(user_id),
            "account_id": str(account_id or ""),
            "platform": str(platform),
            "tool": "__creation_plan__",
            "tools": tools,
            "plan_fingerprint": fingerprint,
            "confirmation_token": token,
            "idempotency_key": idempotency_key,
            "input_hash": input_digest,
            "preview_hash": sha256_json(preview if preview is not None else manifest),
            "request_hash": request_digest,
            "contract_hash": contract_hash,
            "preview": preview if preview is not None else manifest,
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
        if not isinstance(payload, dict):
            return False
        expected_type = "confirm_write_plan" if expected.get("type") == "confirm_write_plan" else "confirm_write"
        if payload.get("type") != expected_type:
            return False
        if not all(
            str(payload.get(key, "")) == str(expected.get(key, ""))
            for key in (
                "session_id", "user_id", "account_id", "tool",
                "plan_fingerprint", "confirmation_token", "idempotency_key",
                "input_hash", "preview_hash", "request_hash", "contract_hash",
            )
        ):
            return False
        if expected_type == "confirm_write_plan":
            return payload.get("platform") == expected.get("platform") and payload.get("tools") == expected.get("tools")
        return True

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
