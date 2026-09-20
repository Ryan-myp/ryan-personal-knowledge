"""Controlled external MCP Server and Tool management.

MCP is an integration boundary, not a shortcut around the Agent Runtime.
This module owns the HTTP control plane and the adapter that turns a validated
remote ``tools/list`` result into ordinary Runtime ``ToolDefinition`` objects.
It deliberately supports remote HTTP MCP servers only: the management API
never accepts or executes shell commands, local processes, or uploaded code.

The lifecycle is:

    draft -> validate -> server enabled -> individual Tool enabled
        -> Runtime registry -> normal permission/confirmation/audit gates

Secrets are referenced by name and resolved from deployment environment at
connection time. They are never persisted or returned by this module.
"""

from __future__ import annotations

import ipaddress
import hashlib
import json
import logging
import os
import re
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping, Optional
from urllib.parse import urlparse

import requests

from .core.interfaces import (
    ReplayPolicy, RiskLevel, ToolDefinition, ToolEffect, ToolHandler,
    ToolContext, ToolResult, ToolSchema,
)
from .core.security import is_sensitive_field, redact_sensitive_text
from .core.tool_registry import validate_tool_input
from .core.tool_sources import StaticToolSource, ToolBinding
from .persistence.errors import PersistenceConflictError


logger = logging.getLogger(__name__)

_TRANSPORT = "streamable_http"
_AUTH_TYPES = {"none", "bearer", "api_key"}
_CHECKS = ("configuration", "connectivity", "tool_schema", "policy")
_SERVER_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._:-]{1,127}$")
_CREDENTIAL_REF_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:-]{0,127}$")
_REMOTE_TOOL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_MAX_TOOLS = 200
_MAX_SCHEMA_BYTES = 64 * 1024
_MAX_RESPONSE_BYTES = 1_000_000
_FIELD_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,127}$")
_ACTION_RE = re.compile(r"^[a-z][a-z0-9_.:-]{0,63}$")
_PERMISSION_RE = re.compile(r"^[a-z][a-z0-9_.:-]{0,127}$")


class MCPManagementError(ValueError):
    """A safe, user-facing MCP configuration or lifecycle error."""


class MCPProtocolError(RuntimeError):
    """A remote MCP endpoint did not return a valid JSON-RPC response."""


def _safe_error(error: BaseException) -> str:
    return redact_sensitive_text(f"{type(error).__name__}: {error}")[:500]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_mcp_endpoint(endpoint: str) -> str:
    """Validate an endpoint before any network request is attempted.

    HTTPS is required for non-loopback endpoints. Query strings, fragments,
    and URL credentials are rejected so a secret cannot be hidden in a URL.
    Literal private addresses are also blocked unless the deployment
    explicitly opts into private-network MCP endpoints.
    """
    raw = str(endpoint or "").strip()
    parsed = urlparse(raw)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        raise MCPManagementError("MCP endpoint 必须是带主机名的 http(s) URL")
    if parsed.username or parsed.password:
        raise MCPManagementError("MCP endpoint 不能包含 URL 用户名或密码")
    if parsed.query or parsed.fragment:
        raise MCPManagementError("MCP endpoint 不能包含 query 或 fragment；请使用凭证引用")
    host = str(parsed.hostname).strip().lower()
    loopback = host in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme == "http" and not loopback and os.environ.get("AD_AGENT_MCP_ALLOW_HTTP") != "1":
        raise MCPManagementError("非本机 MCP endpoint 必须使用 HTTPS")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and (address.is_private or address.is_link_local or address.is_reserved) and not loopback:
        if os.environ.get("AD_AGENT_MCP_ALLOW_PRIVATE_NETWORK") != "1":
            raise MCPManagementError("私有网络 MCP endpoint 需要部署配置 AD_AGENT_MCP_ALLOW_PRIVATE_NETWORK=1")
    if len(raw) > 2048:
        raise MCPManagementError("MCP endpoint 过长")
    return raw.rstrip("/")


def _credential_env_name(reference: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]", "_", str(reference or "")).upper()
    return f"AD_AGENT_MCP_CREDENTIAL_{normalized}"


def _validate_auth(auth_type: str, credential_ref: Optional[str], auth_header: str) -> tuple[str, Optional[str], str]:
    kind = str(auth_type or "none").strip().lower()
    if kind not in _AUTH_TYPES:
        raise MCPManagementError(f"不支持的 MCP 认证方式：{kind}")
    ref = str(credential_ref or "").strip() or None
    if kind != "none" and (not ref or not _CREDENTIAL_REF_RE.fullmatch(ref)):
        raise MCPManagementError("MCP 认证需要合法 credential_ref；只保存引用，不保存密钥")
    if kind == "none" and ref:
        raise MCPManagementError("auth_type=none 时不能配置 credential_ref")
    header = str(auth_header or ("Authorization" if kind == "bearer" else "X-API-Key")).strip()
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9-]{0,63}", header):
        raise MCPManagementError("MCP 认证 Header 名称不合法")
    if kind == "bearer" and header.lower() != "authorization":
        raise MCPManagementError("bearer 认证必须使用 Authorization Header")
    return kind, ref, header


def _validate_schema(raw_schema: Any) -> tuple[ToolSchema, dict[str, Any]]:
    if raw_schema in (None, {}):
        raw_schema = {"type": "object", "properties": {}, "required": []}
    if not isinstance(raw_schema, Mapping):
        raise MCPManagementError("MCP Tool inputSchema 必须是 object")
    schema = dict(raw_schema)
    if str(schema.get("type", "object")) != "object":
        raise MCPManagementError("MCP Tool inputSchema.type 必须是 object")
    required = schema.get("required", []) or []
    properties = schema.get("properties", {}) or {}
    if not isinstance(required, list) or not all(isinstance(item, str) and item.strip() for item in required):
        raise MCPManagementError("MCP Tool inputSchema.required 必须是字符串列表")
    if not isinstance(properties, Mapping):
        raise MCPManagementError("MCP Tool inputSchema.properties 必须是 object")
    if len(properties) > 100:
        raise MCPManagementError("MCP Tool inputSchema 字段数超过 100")
    for field_name, field_schema in properties.items():
        if not isinstance(field_name, str) or not field_name.strip() or is_sensitive_field(field_name):
            raise MCPManagementError(f"MCP Tool schema 含受保护或非法字段：{field_name!r}")
        if not isinstance(field_schema, Mapping):
            raise MCPManagementError(f"MCP Tool 字段 {field_name!r} 的 schema 必须是 object")
        _validate_nested_schema(field_schema, str(field_name), 1)
    if set(required) - set(properties):
        raise MCPManagementError("MCP Tool required 字段必须存在于 properties")
    if "additionalProperties" in schema and not isinstance(schema["additionalProperties"], bool):
        raise MCPManagementError("MCP Tool additionalProperties 必须是 boolean")
    encoded = json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > _MAX_SCHEMA_BYTES:
        raise MCPManagementError("MCP Tool inputSchema 超过 64KB")
    public = {
        "type": "object",
        "required": list(dict.fromkeys(required)),
        "properties": dict(properties),
        "additionalProperties": bool(schema.get("additionalProperties", False)),
    }
    return ToolSchema(
        type="object", required=public["required"], properties=public["properties"],
        additional_properties=public["additionalProperties"],
    ), public


def _validate_nested_schema(schema: Mapping[str, Any], path: str, depth: int) -> None:
    """Apply the same credential/depth limits to nested MCP schemas."""
    if depth > 8:
        raise MCPManagementError(f"MCP Tool schema 嵌套超过 8 层：{path}")
    properties = schema.get("properties") or {}
    if properties and not isinstance(properties, Mapping):
        raise MCPManagementError(f"MCP Tool schema {path}.properties 必须是 object")
    for field_name, field_schema in (properties.items() if isinstance(properties, Mapping) else ()):
        if not isinstance(field_name, str) or not field_name.strip() or is_sensitive_field(field_name):
            raise MCPManagementError(f"MCP Tool schema 含受保护或非法字段：{field_name!r}")
        if not isinstance(field_schema, Mapping):
            raise MCPManagementError(f"MCP Tool schema 字段 {path}.{field_name} 必须是 object")
        _validate_nested_schema(field_schema, f"{path}.{field_name}", depth + 1)
    items = schema.get("items")
    if isinstance(items, Mapping):
        _validate_nested_schema(items, f"{path}[]", depth + 1)


def _normalise_remote_tool(raw: Mapping[str, Any]) -> dict[str, Any]:
    remote_name = str(raw.get("name") or "").strip()
    if not _REMOTE_TOOL_RE.fullmatch(remote_name):
        raise MCPManagementError(f"MCP Tool 名称不合法：{remote_name!r}")
    description = str(raw.get("description") or raw.get("title") or remote_name).strip()[:4000]
    schema, public_schema = _validate_schema(raw.get("inputSchema", raw.get("input_schema")))
    annotations = raw.get("annotations") or {}
    if not isinstance(annotations, Mapping):
        annotations = {}
    annotations = {
        key: value for key, value in annotations.items()
        if key in {"readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint"}
        and isinstance(value, bool)
    }
    read_only = annotations.get("readOnlyHint") is True and annotations.get("destructiveHint") is not True
    return {
        "remote_name": remote_name,
        "title": str(raw.get("title") or "").strip()[:200],
        "description": description,
        "input_schema": public_schema,
        "annotations": annotations,
        "read_only": read_only,
        "schema": schema,
    }


def _runtime_tool_name(server_id: str, remote_name: str) -> str:
    """Build a deterministic, collision-resistant Runtime registry name."""
    readable = re.sub(r"[^A-Za-z0-9_]", "_", str(remote_name)).strip("_") or "tool"
    digest = hashlib.sha256(str(remote_name).encode("utf-8")).hexdigest()[:10]
    prefix = f"mcp__{server_id}__"
    return f"{prefix}{readable[:max(1, 240 - len(prefix) - len(digest) - 2)]}__{digest}"


class MCPHTTPClient:
    """Small dependency-light MCP Streamable HTTP client."""

    def __init__(self, server: Mapping[str, Any]):
        self.endpoint = validate_mcp_endpoint(str(server.get("endpoint") or ""))
        self.transport = str(server.get("transport") or _TRANSPORT)
        if self.transport != _TRANSPORT:
            raise MCPManagementError(f"暂不支持 MCP transport：{self.transport}")
        self.auth_type, self.credential_ref, self.auth_header = _validate_auth(
            str(server.get("auth_type") or "none"),
            server.get("credential_ref"),
            str(server.get("auth_header") or ""),
        )
        self.timeout_seconds = max(1.0, min(float(server.get("timeout_seconds") or 20.0), 120.0))
        self._session = requests.Session()
        self._lock = threading.RLock()
        self._next_id = 0
        self._mcp_session_id: Optional[str] = None
        self._initialized = False

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if self._mcp_session_id:
            headers["Mcp-Session-Id"] = self._mcp_session_id
        if self.auth_type != "none":
            if not self.credential_ref:
                raise MCPManagementError("MCP credential_ref 未配置")
            secret = os.environ.get(_credential_env_name(self.credential_ref), "")
            if not secret:
                raise MCPManagementError(
                    f"部署环境未提供 MCP credential_ref：{self.credential_ref}"
                )
            headers[self.auth_header] = f"Bearer {secret}" if self.auth_type == "bearer" else secret
        return headers

    @staticmethod
    def _decode_response(response: Any) -> dict[str, Any]:
        content_type = str(response.headers.get("content-type") or "").lower()
        if "text/event-stream" not in content_type:
            try:
                value = response.json()
            except (TypeError, ValueError) as exc:
                raise MCPProtocolError("MCP response 不是合法 JSON") from exc
            if not isinstance(value, Mapping):
                raise MCPProtocolError("MCP response 必须是 JSON object")
            return dict(value)
        candidates = []
        for line in str(response.text or "").splitlines():
            if line.startswith("data:"):
                try:
                    value = json.loads(line[5:].strip())
                except (TypeError, ValueError):
                    continue
                if isinstance(value, Mapping):
                    candidates.append(dict(value))
        if not candidates:
            raise MCPProtocolError("MCP SSE response 未包含 JSON-RPC 消息")
        return candidates[-1]

    def _request(self, payload: Mapping[str, Any], *, allow_empty: bool = False) -> dict[str, Any]:
        try:
            response = self._session.post(
                self.endpoint, headers=self._headers(), json=dict(payload),
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise MCPProtocolError("MCP endpoint 网络请求失败") from exc
        if response.headers.get("Mcp-Session-Id"):
            self._mcp_session_id = str(response.headers["Mcp-Session-Id"])
        if response.status_code >= 400:
            raise MCPProtocolError(f"MCP endpoint 返回 HTTP {response.status_code}")
        if allow_empty and response.status_code in {202, 204}:
            return {}
        content_length = response.headers.get("Content-Length")
        try:
            if content_length is not None and int(content_length) > _MAX_RESPONSE_BYTES:
                raise MCPProtocolError("MCP response 超过 1MB 输出上限")
        except ValueError as exc:
            raise MCPProtocolError("MCP response 的 Content-Length 不合法") from exc
        if len(response.content) > _MAX_RESPONSE_BYTES:
            raise MCPProtocolError("MCP response 超过 1MB 输出上限")
        return self._decode_response(response)

    def _rpc(self, method: str, params: Optional[Mapping[str, Any]] = None) -> dict[str, Any]:
        with self._lock:
            self._next_id += 1
            response = self._request({
                "jsonrpc": "2.0", "id": self._next_id,
                "method": method, "params": dict(params or {}),
            })
        if response.get("error"):
            error = response.get("error")
            message = error.get("message") if isinstance(error, Mapping) else "MCP JSON-RPC error"
            raise MCPProtocolError(f"MCP {method} 失败：{str(message)[:300]}")
        result = response.get("result")
        if not isinstance(result, Mapping):
            raise MCPProtocolError(f"MCP {method} 缺少 result")
        return dict(result)

    def discover_tools(self) -> tuple[str, list[dict[str, Any]]]:
        with self._lock:
            if not self._initialized:
                result = self._rpc("initialize", {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "ad-agent", "version": "1.0.0"},
                })
                protocol_version = str(result.get("protocolVersion") or "unknown")
                self._request({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}, allow_empty=True)
                self._initialized = True
            else:
                protocol_version = "reused"
            tools: list[dict[str, Any]] = []
            names_seen: set[str] = set()
            cursor: Optional[str] = None
            for _ in range(10):
                params = {"cursor": cursor} if cursor else {}
                result = self._rpc("tools/list", params)
                entries = result.get("tools") or []
                if not isinstance(entries, list):
                    raise MCPProtocolError("MCP tools/list.tools 必须是数组")
                for entry in entries:
                    if not isinstance(entry, Mapping):
                        raise MCPManagementError("MCP tools/list 返回了非法 Tool")
                    normalised = _normalise_remote_tool(entry)
                    if normalised["remote_name"] in names_seen:
                        raise MCPManagementError(
                            f"MCP tools/list 返回重复 Tool：{normalised['remote_name']}"
                        )
                    names_seen.add(normalised["remote_name"])
                    tools.append(normalised)
                    if len(tools) >= _MAX_TOOLS:
                        break
                if len(tools) >= _MAX_TOOLS:
                    break
                next_cursor = result.get("nextCursor")
                if not next_cursor or str(next_cursor) == cursor:
                    break
                cursor = str(next_cursor)
            return protocol_version, tools

    def call_tool(self, remote_name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock:
            if not self._initialized:
                self.discover_tools()
            return self._rpc("tools/call", {
                "name": str(remote_name), "arguments": dict(arguments or {}),
            })


class MCPToolHandler:
    """Runtime handler for one already-validated remote MCP Tool."""

    def __init__(
        self, client: MCPHTTPClient, server_id: str, tenant_id: str,
        remote_name: str, *, write_effect: bool = False,
    ):
        self.client = client
        self.server_id = server_id
        self.tenant_id = tenant_id
        self.remote_name = remote_name
        self.write_effect = bool(write_effect)

    def execute(self, ctx: Any, input_data: dict[str, Any]) -> ToolResult:
        context_tenant = str((getattr(ctx, "metadata", {}) or {}).get("tenant_id") or "default")
        if context_tenant != self.tenant_id:
            return ToolResult.error("MCP Tool 不属于当前租户")
        try:
            result = self.client.call_tool(self.remote_name, input_data)
        except Exception as exc:
            if self.write_effect:
                # A timeout, connection reset, or protocol error does not
                # prove that a remote mutation was not accepted. Preserve
                # uncertainty so TaskExecutor/recovery UI cannot retry it as
                # an ordinary failure.
                return ToolResult(
                    success=False,
                    data={
                        "execution_status": "unknown",
                        "effect_state": "unknown",
                        "requires_reconciliation": True,
                    },
                    error="MCP 写 Tool 调用结果未知，必须先核对远端状态",
                )
            return ToolResult.error("MCP Tool 调用失败", detail=None)
        if bool(result.get("isError")):
            if self.write_effect:
                return ToolResult(
                    success=False,
                    data={
                        "execution_status": "unknown",
                        "effect_state": "unknown",
                        "requires_reconciliation": True,
                    },
                    error="MCP Server 返回写操作错误，远端结果需要核对",
                )
            return ToolResult.error("MCP Server 报告 Tool 执行失败")
        return ToolResult.ok({
            "mcp_server_id": self.server_id,
            "mcp_tool": self.remote_name,
            "content": result.get("content", []),
            "structured_content": result.get("structuredContent"),
        })


class MCPServerManager:
    """Tenant-scoped MCP control plane and Runtime registry adapter."""

    def __init__(self, store: Any):
        self.store = store
        self._lock = threading.RLock()
        self._clients: dict[str, MCPHTTPClient] = {}
        self._registered: dict[str, list[str]] = {}
        self._registered_sources: dict[str, str] = {}
        self._registered_tenants: dict[str, str] = {}
        self._server_fingerprints: dict[str, str] = {}
        self._tenant_fingerprints: dict[str, str] = {}

    @staticmethod
    def _public_tool(record: Mapping[str, Any]) -> dict[str, Any]:
        value = dict(record)
        value["enabled"] = bool(value.get("enabled"))
        for key in (
            "input_schema", "annotations", "intent_types", "intent_aliases",
            "skill_refs", "required_permissions", "traits",
        ):
            if isinstance(value.get(key), str):
                try:
                    value[key] = json.loads(value[key] or "{}")
                except (TypeError, ValueError):
                    value[key] = {} if key in {"input_schema", "annotations"} else []
            if key in {"input_schema", "annotations"}:
                if not isinstance(value.get(key), dict):
                    value[key] = {}
            elif not isinstance(value.get(key), list):
                value[key] = []
        if not value.get("intent_types"):
            value["intent_types"] = [str(value.get("remote_name") or "")]
        if not value.get("intent_aliases") and value.get("title"):
            value["intent_aliases"] = [str(value.get("title"))]
        if not value.get("traits"):
            value["traits"] = ["external", "mcp"]
        read_only = (
            (value.get("annotations") or {}).get("readOnlyHint") is True
            and (value.get("annotations") or {}).get("destructiveHint") is not True
        )
        if not value.get("required_permissions"):
            value["required_permissions"] = ["mcp.read" if read_only else "mcp.write"]
        return {key: value.get(key) for key in (
            "tool_id", "server_id", "tenant_id", "remote_name", "title", "description",
            "input_schema", "annotations", "intent_types", "intent_aliases", "skill_refs",
            "action", "resource_type", "resource_id_field", "readback_tool",
            "idempotency_key_field", "required_permissions", "traits",
            "status", "enabled", "validation_status",
            "last_error", "created_at", "updated_at",
        )}

    @classmethod
    def _public_server(cls, record: Mapping[str, Any], tools: list[Mapping[str, Any]]) -> dict[str, Any]:
        value = dict(record)
        for key in ("validation_report",):
            if isinstance(value.get(key), str):
                try:
                    value[key] = json.loads(value[key] or "{}")
                except (TypeError, ValueError):
                    value[key] = {}
        result = {key: value.get(key) for key in (
            "server_id", "tenant_id", "name", "description", "endpoint", "transport",
            "auth_type", "credential_ref", "auth_header", "status", "enabled",
            "timeout_seconds", "validation_status", "validation_report", "protocol_version", "created_by",
            "created_at", "updated_at", "last_checked_at", "last_error",
        )}
        result["enabled"] = bool(value.get("enabled"))
        result["credential_configured"] = bool(value.get("credential_ref"))
        result["tools"] = [cls._public_tool(tool) for tool in tools]
        return result

    def create_server(self, tenant_id: str, data: Mapping[str, Any], created_by: str) -> dict[str, Any]:
        server_id = str(data.get("server_id") or uuid.uuid4().hex[:24]).strip().lower()
        if not _SERVER_ID_RE.fullmatch(server_id):
            raise MCPManagementError("server_id 只能包含小写字母、数字、点、下划线、冒号或短横线")
        endpoint = validate_mcp_endpoint(str(data.get("endpoint") or ""))
        auth_type, credential_ref, auth_header = _validate_auth(
            str(data.get("auth_type") or "none"), data.get("credential_ref"), str(data.get("auth_header") or "")
        )
        try:
            record = self.store.create_mcp_server({
                "server_id": server_id, "tenant_id": str(tenant_id or "default"),
                "name": str(data.get("name") or server_id).strip()[:120],
                "description": str(data.get("description") or "").strip()[:500],
                "endpoint": endpoint, "transport": _TRANSPORT, "auth_type": auth_type,
                "credential_ref": credential_ref, "auth_header": auth_header,
                "timeout_seconds": max(1.0, min(float(data.get("timeout_seconds") or 20.0), 120.0)),
                "created_by": str(created_by),
            })
        except (sqlite3.IntegrityError, PersistenceConflictError) as exc:
            raise MCPManagementError("当前租户已存在同名 MCP Server 或 server_id") from exc
        return self._public_server(record, [])

    def list_servers(self, tenant_id: str, limit: int = 50) -> list[dict[str, Any]]:
        records = self.store.list_mcp_servers(str(tenant_id or "default"), limit)
        return [self._public_server(record, self.store.list_mcp_tools(record["server_id"], record["tenant_id"])) for record in records]

    def get_server(self, tenant_id: str, server_id: str) -> Optional[dict[str, Any]]:
        record = self.store.get_mcp_server(str(tenant_id or "default"), str(server_id))
        if not record:
            return None
        return self._public_server(record, self.store.list_mcp_tools(record["server_id"], record["tenant_id"]))

    def validate_server(
        self, tenant_id: str, server_id: str, checks: list[str], runtime: Any = None,
    ) -> dict[str, Any]:
        record = self.store.get_mcp_server(str(tenant_id or "default"), str(server_id))
        if not record:
            raise KeyError(server_id)
        requested = list(_CHECKS) if "all" in checks else list(dict.fromkeys(checks or list(_CHECKS)))
        unknown = sorted(set(requested) - set(_CHECKS))
        if unknown:
            raise MCPManagementError(f"不支持的 MCP 校验项：{', '.join(unknown)}")
        report: dict[str, Any] = {"requested": requested, "checks": {}, "checked_at": _now()}
        discovered: list[dict[str, Any]] = []
        protocol_version = record.get("protocol_version")
        for check in requested:
            try:
                if check == "configuration":
                    validate_mcp_endpoint(record.get("endpoint"))
                    _validate_auth(record.get("auth_type"), record.get("credential_ref"), record.get("auth_header"))
                    report["checks"][check] = {"status": "passed", "transport": _TRANSPORT}
                elif check == "connectivity":
                    client = MCPHTTPClient(record)
                    protocol_version, discovered = client.discover_tools()
                    self._clients[str(server_id)] = client
                    report["checks"][check] = {"status": "passed", "protocol_version": protocol_version, "tool_count": len(discovered)}
                    for item in discovered:
                        self.store.upsert_mcp_tool({
                            "tool_id": uuid.uuid5(uuid.NAMESPACE_URL, f"{server_id}:{item['remote_name']}").hex,
                            "server_id": str(server_id), "tenant_id": str(tenant_id or "default"),
                            "remote_name": item["remote_name"], "title": item["title"],
                            "description": item["description"], "input_schema": item["input_schema"],
                            "annotations": item["annotations"], "validation_status": "pending",
                        })
                    remote_names = {str(item["remote_name"]) for item in discovered}
                    for existing in self.store.list_mcp_tools(server_id, tenant_id):
                        if str(existing.get("remote_name")) not in remote_names:
                            self.store.update_mcp_tool(
                                existing["tool_id"], tenant_id,
                                {
                                    "enabled": False,
                                    "status": "stale",
                                    "validation_status": "failed",
                                    "last_error": "MCP Server 已不再发布该 Tool",
                                },
                            )
                    # Continue subsequent checks with the durable records so
                    # Tool IDs and prior enablement state are available.
                    discovered = self.store.list_mcp_tools(server_id, tenant_id)
                elif check == "tool_schema":
                    tools = discovered or self.store.list_mcp_tools(server_id, tenant_id)
                    errors = []
                    valid_count = 0
                    for tool in tools:
                        tool_error = None
                        try:
                            _validate_schema(tool.get("input_schema") or {})
                            valid_count += 1
                            tool_status = "passed"
                        except MCPManagementError as exc:
                            tool_error = f"{tool.get('remote_name')}: {exc}"
                            errors.append(tool_error)
                            tool_status = "failed"
                        self.store.update_mcp_tool(
                            tool["tool_id"], tenant_id,
                            {
                                "validation_status": tool_status,
                                "last_error": tool_error,
                            },
                        )
                    report["checks"][check] = {"status": "passed" if not errors else "failed", "valid_tools": valid_count, "errors": errors[:20]}
                elif check == "policy":
                    tools = discovered or self.store.list_mcp_tools(server_id, tenant_id)
                    write_count = sum(1 for tool in tools if not bool((tool.get("annotations") or {}).get("readOnlyHint")))
                    report["checks"][check] = {
                        "status": "passed", "write_tools_require_confirmation": write_count,
                        "read_tools": max(0, len(tools) - write_count),
                        "note": "非只读 Tool 默认按 external_write/high/unsafe 处理",
                    }
            except Exception as exc:
                report["checks"][check] = {"status": "failed", "error": _safe_error(exc)}
        statuses = [item.get("status") for item in report["checks"].values()]
        passed = bool(statuses) and all(status == "passed" for status in statuses)
        report["status"] = "passed" if passed else "failed"
        report["tool_count"] = len(discovered) if discovered else len(self.store.list_mcp_tools(server_id, tenant_id))
        self.store.update_mcp_server(str(server_id), str(tenant_id or "default"), {
            "validation_status": "passed" if passed and set(requested) == set(_CHECKS) else "partial" if passed else "failed",
            "validation_report": report, "protocol_version": protocol_version,
            "status": "validated" if passed else "error", "last_checked_at": _now(),
            "last_error": None if passed else "MCP validation failed",
        })
        if runtime is not None:
            current = self.store.get_mcp_server(str(tenant_id or "default"), str(server_id))
            if current and current.get("status") == "active" and current.get("enabled"):
                self.sync_server(tenant_id, server_id, runtime)
        return self.get_server(tenant_id, server_id) or {}

    def enable_server(self, tenant_id: str, server_id: str, runtime: Any) -> dict[str, Any]:
        record = self.store.get_mcp_server(tenant_id, server_id)
        if not record:
            raise KeyError(server_id)
        if record.get("validation_status") != "passed":
            raise MCPManagementError("MCP Server 必须先完成全部校验并通过，才能启用")
        self.store.update_mcp_server(server_id, tenant_id, {"status": "active", "enabled": True, "last_error": None})
        self.sync_server(tenant_id, server_id, runtime)
        return self.get_server(tenant_id, server_id) or {}

    def disable_server(self, tenant_id: str, server_id: str, runtime: Any) -> dict[str, Any]:
        if not self.store.get_mcp_server(tenant_id, server_id):
            raise KeyError(server_id)
        self.store.update_mcp_server(server_id, tenant_id, {"status": "disabled", "enabled": False})
        self._unregister(server_id, runtime)
        return self.get_server(tenant_id, server_id) or {}

    def update_server(self, tenant_id: str, server_id: str, data: Mapping[str, Any], runtime: Any) -> dict[str, Any]:
        record = self.store.get_mcp_server(tenant_id, server_id)
        if not record:
            raise KeyError(server_id)
        updates = {key: value for key, value in data.items() if value is not None}
        if updates.get("auth_type") == "none" and "credential_ref" not in updates:
            updates["credential_ref"] = None
        endpoint = validate_mcp_endpoint(str(updates.get("endpoint", record.get("endpoint") or "")))
        auth_type, credential_ref, auth_header = _validate_auth(
            str(updates.get("auth_type", record.get("auth_type") or "none")),
            updates.get("credential_ref", record.get("credential_ref")),
            str(updates.get("auth_header", record.get("auth_header") or "")),
        )
        changed_connection = any(key in updates for key in ("endpoint", "auth_type", "credential_ref", "auth_header", "transport"))
        normalized = {
            "name": str(updates.get("name", record.get("name") or "")).strip()[:120],
            "description": str(updates.get("description", record.get("description") or "")).strip()[:500],
            "endpoint": endpoint, "transport": _TRANSPORT, "auth_type": auth_type,
            "credential_ref": credential_ref, "auth_header": auth_header,
            "timeout_seconds": max(1.0, min(float(updates.get("timeout_seconds", record.get("timeout_seconds") or 20.0)), 120.0)),
        }
        if changed_connection:
            normalized.update({
                "status": "draft", "enabled": False, "validation_status": "not_run",
                "validation_report": {}, "protocol_version": None, "last_checked_at": None,
                "last_error": None,
            })
            self._unregister(server_id, runtime)
        try:
            self.store.update_mcp_server(server_id, tenant_id, normalized)
        except (sqlite3.IntegrityError, PersistenceConflictError) as exc:
            raise MCPManagementError("当前租户已存在同名 MCP Server") from exc
        return self.get_server(tenant_id, server_id) or {}

    def delete_server(self, tenant_id: str, server_id: str, runtime: Any) -> dict[str, Any]:
        if not self.store.get_mcp_server(tenant_id, server_id):
            raise KeyError(server_id)
        self.store.update_mcp_server(server_id, tenant_id, {"status": "deleted", "enabled": False})
        self._unregister(server_id, runtime)
        return self.get_server(tenant_id, server_id) or {}

    def enable_tool(self, tenant_id: str, server_id: str, tool_id: str, runtime: Any) -> dict[str, Any]:
        record = self.store.get_mcp_server(tenant_id, server_id)
        tool = self.store.get_mcp_tool(tool_id, tenant_id)
        if not record or not tool or str(tool.get("server_id")) != str(server_id):
            raise KeyError(tool_id)
        if record.get("status") != "active":
            raise MCPManagementError("请先启用 MCP Server")
        if tool.get("validation_status") != "passed":
            raise MCPManagementError("MCP Tool schema 校验未通过，不能启用")
        self.store.update_mcp_tool(tool_id, tenant_id, {"enabled": True, "status": "enabled", "last_error": None})
        self.sync_server(tenant_id, server_id, runtime)
        return self.get_server(tenant_id, server_id) or {}

    def disable_tool(self, tenant_id: str, server_id: str, tool_id: str, runtime: Any) -> dict[str, Any]:
        tool = self.store.get_mcp_tool(tool_id, tenant_id)
        if not tool or str(tool.get("server_id")) != str(server_id):
            raise KeyError(tool_id)
        self.store.update_mcp_tool(tool_id, tenant_id, {"enabled": False, "status": "disabled"})
        self.sync_server(tenant_id, server_id, runtime)
        return self.get_server(tenant_id, server_id) or {}

    def update_tool_metadata(
        self, tenant_id: str, server_id: str, tool_id: str,
        data: Mapping[str, Any], runtime: Any,
    ) -> dict[str, Any]:
        """Update publisher metadata without changing the discovered wire schema.

        MCP discovery remains the source of truth for the remote input schema
        and safety annotations. This method only edits the declarative routing
        and advisory contract that lets a generic Tool participate in the
        Agent's normal selection flow.
        """
        server = self.store.get_mcp_server(str(tenant_id or "default"), str(server_id))
        tool = self.store.get_mcp_tool(str(tool_id), str(tenant_id or "default"))
        if not server or not tool or str(tool.get("server_id")) != str(server_id):
            raise KeyError(tool_id)
        updates = dict(data or {})
        allowed = {
            "intent_types", "intent_aliases", "skill_refs", "action",
            "resource_type", "resource_id_field", "readback_tool",
            "idempotency_key_field", "required_permissions", "traits",
        }
        unknown = sorted(set(updates) - allowed)
        if unknown:
            raise MCPManagementError("不支持的 MCP Tool 元数据字段：" + ", ".join(unknown))

        def string_list(key: str, *, required: bool = False, max_items: int = 32) -> list[str]:
            value = updates.get(key, tool.get(key))
            if value is None:
                value = []
            if isinstance(value, str):
                value = [value]
            if not isinstance(value, list) or len(value) > max_items:
                raise MCPManagementError(f"{key} 必须是最多 {max_items} 项的字符串列表")
            result = []
            for item in value:
                text = str(item or "").strip()
                if not text or len(text) > 200:
                    raise MCPManagementError(f"{key} 含有空值或过长项")
                result.append(text)
            result = list(dict.fromkeys(result))
            if required and not result:
                raise MCPManagementError(f"{key} 不能为空")
            return result

        intent_types = string_list("intent_types", required=True)
        intent_aliases = string_list("intent_aliases")
        skill_refs = string_list("skill_refs")
        permissions = string_list("required_permissions")
        if any(not _PERMISSION_RE.fullmatch(item) for item in permissions):
            raise MCPManagementError("required_permissions 含有非法权限名")
        traits = string_list("traits")
        if "mcp" not in traits:
            traits.append("mcp")
        if "external" not in traits:
            traits.append("external")

        action = str(updates.get("action", tool.get("action") or "invoke")).strip().lower()
        resource_type = str(
            updates.get("resource_type", tool.get("resource_type") or "mcp_invocation")
        ).strip().lower()
        if not _ACTION_RE.fullmatch(action):
            raise MCPManagementError("action 必须是小写扩展动作标识")
        if not _FIELD_NAME_RE.fullmatch(resource_type):
            raise MCPManagementError("resource_type 必须是合法标识")

        def optional_field(key: str) -> Optional[str]:
            value = updates.get(key, tool.get(key))
            if value in (None, ""):
                return None
            value = str(value).strip()
            valid = _REMOTE_TOOL_RE if key == "readback_tool" else _FIELD_NAME_RE
            if not valid.fullmatch(value):
                raise MCPManagementError(f"{key} 必须是合法字段名")
            return value

        resource_id_field = optional_field("resource_id_field")
        readback_tool = optional_field("readback_tool")
        idempotency_key_field = optional_field("idempotency_key_field")
        if action in {"create", "update", "delete", "pause", "resume", "enable", "disable"} and not resource_id_field:
            raise MCPManagementError("可变更动作必须声明 resource_id_field；不能使用内部请求 ID 冒充远端资源 ID")

        metadata = {
            "intent_types": intent_types,
            "intent_aliases": intent_aliases,
            "skill_refs": skill_refs,
            "action": action,
            "resource_type": resource_type,
            "resource_id_field": resource_id_field,
            "readback_tool": readback_tool,
            "idempotency_key_field": idempotency_key_field,
            "required_permissions": permissions,
            "traits": traits,
        }
        updated = self.store.update_mcp_tool(str(tool_id), str(tenant_id or "default"), metadata)
        if not updated:
            raise KeyError(tool_id)
        if server.get("status") == "active" and server.get("enabled"):
            self.sync_server(str(tenant_id or "default"), str(server_id), runtime)
        return self.get_server(str(tenant_id or "default"), str(server_id)) or {}

    def test_tool(
        self,
        tenant_id: str,
        server_id: str,
        tool_id: str,
        runtime: Any,
        principal: Any,
        input_data: Mapping[str, Any],
        *,
        account_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Execute an enabled read-only MCP Tool through the Runtime.

        A remote MCP server cannot be assumed to understand this service's
        dry-run contract.  Consequently a management-console test never
        invokes a remote write Tool; write Tools must use the normal Agent
        confirmation, idempotency and live execution path.
        """
        server = self.store.get_mcp_server(str(tenant_id or "default"), str(server_id))
        tool = self.store.get_mcp_tool(str(tool_id), str(tenant_id or "default"))
        if not server or not tool or str(tool.get("server_id")) != str(server_id):
            raise KeyError(tool_id)
        if server.get("status") != "active" or not server.get("enabled"):
            raise MCPManagementError("请先启用 MCP Server")
        if not tool.get("enabled") or tool.get("validation_status") != "passed":
            raise MCPManagementError("请先启用并完成校验该 MCP Tool")
        annotations = tool.get("annotations") or {}
        read_only = annotations.get("readOnlyHint") is True and annotations.get("destructiveHint") is not True
        if not read_only:
            raise MCPManagementError(
                "外部 MCP 写 Tool 不支持管理台直测；请通过 Agent 的确认、幂等和 live 执行链路调用"
            )
        public_name = _runtime_tool_name(str(server_id), str(tool.get("remote_name")))
        definition, _handler = runtime._get_registered_tool(public_name)
        missing = sorted(
            set(definition.required_permissions or ()) - set(principal.permissions or ())
        )
        if missing and "admin" not in set(principal.permissions or ()):
            raise PermissionError("Tool 所需权限未授予：" + ", ".join(missing))
        data = dict(input_data or {})
        schema_errors = validate_tool_input(definition.input_schema, data)
        if schema_errors:
            raise MCPManagementError("Input validation failed: " + "; ".join(schema_errors))
        session_id = f"mcp-test-{uuid.uuid4().hex}"
        turn_id = f"mcp-test-turn-{uuid.uuid4().hex}"
        context = ToolContext(
            session_id=session_id,
            user_id=str(principal.user_id),
            scope={"account_id": account_id or ""},
            metadata={
                "tenant_id": str(tenant_id or "default"),
                "mcp_source": "ui_test",
                "mcp_tool_test": True,
            },
        )
        started_at = _now()
        result = runtime.tool_executor.execute(context, public_name, data)
        ended_at = _now()
        persistence = getattr(runtime, "persistence_services", None)
        ensure_session = getattr(runtime, "_ensure_session", None)
        if callable(persistence) and callable(ensure_session):
            try:
                session = ensure_session(
                    session_id, context.user_id, account_id or "", {},
                    tenant_id=str(tenant_id or "default"),
                )
                persistence.persist_tool_result(
                    session, turn_id, definition, f"mcp:{server_id}", data, result,
                    started_at=started_at, ended_at=ended_at,
                )
            except Exception:
                logger.warning("MCP Tool test audit persistence failed", exc_info=True)
        return {
            "success": bool(result.success),
            "tool": public_name,
            "remote_tool": str(tool.get("remote_name")),
            "mode": "read_test",
            "data": result.data,
            "error": result.error,
        }

    def sync_tenant(self, tenant_id: str, runtime: Any) -> int:
        records = self.store.list_mcp_servers(tenant_id, 200)
        active = {str(record["server_id"]) for record in records if record.get("status") == "active" and record.get("enabled")}
        for server_id in list(self._registered):
            if self._registered_tenants.get(server_id) == str(tenant_id) and server_id not in active:
                self._unregister(server_id, runtime)
        count = 0
        for server_id in sorted(active):
            record = next(item for item in records if str(item["server_id"]) == server_id)
            tools = self.store.list_mcp_tools(server_id, tenant_id)
            fingerprint = self._fingerprint(record, tools)
            if (
                self._registered_tenants.get(server_id) == str(tenant_id)
                and self._server_fingerprints.get(server_id) == fingerprint
            ):
                count += len(self._registered.get(server_id, []))
                continue
            count += self.sync_server(tenant_id, server_id, runtime)
            if server_id in self._registered:
                self._server_fingerprints[server_id] = fingerprint
                self._registered_tenants[server_id] = str(tenant_id)
        return count

    def sync_tenant_if_changed(self, tenant_id: str, runtime: Any) -> int:
        """Refresh this process only when durable MCP metadata changed.

        The fingerprint is intentionally derived from durable control-plane
        rows, including ``updated_at``. Every instance can therefore observe a
        change made by another instance without a broadcast channel, while a
        normal chat request does not unregister/re-register unchanged Tools.
        """
        tenant = str(tenant_id or "default")
        records = self.store.list_mcp_servers(tenant, 200)
        parts = []
        for record in records:
            tools = self.store.list_mcp_tools(str(record["server_id"]), tenant)
            parts.append(self._fingerprint(record, tools))
        fingerprint = hashlib.sha256(
            json.dumps(sorted(parts), ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()
        with self._lock:
            if self._tenant_fingerprints.get(tenant) == fingerprint:
                return 0
            count = self.sync_tenant(tenant, runtime)
            self._tenant_fingerprints[tenant] = fingerprint
            return count

    @staticmethod
    def _fingerprint(record: Mapping[str, Any], tools: list[Mapping[str, Any]]) -> str:
        payload = {
            "server": {
                key: record.get(key) for key in (
                    "server_id", "tenant_id", "status", "enabled", "validation_status",
                    "endpoint", "transport", "auth_type", "credential_ref", "auth_header",
                    "timeout_seconds", "updated_at",
                )
            },
            "tools": [
                {
                    key: tool.get(key) for key in (
                        "tool_id", "remote_name", "status", "enabled", "validation_status",
                        "updated_at", "intent_types", "intent_aliases", "skill_refs",
                        "action", "resource_type", "resource_id_field", "readback_tool",
                        "idempotency_key_field", "required_permissions", "traits",
                    )
                }
                for tool in tools
            ],
        }
        return hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode()
        ).hexdigest()

    def sync_server(self, tenant_id: str, server_id: str, runtime: Any) -> int:
        record = self.store.get_mcp_server(tenant_id, server_id)
        self._unregister(server_id, runtime)
        if not record or record.get("status") != "active" or not record.get("enabled"):
            return 0
        client = self._clients.get(server_id)
        if client is None:
            try:
                client = MCPHTTPClient(record)
            except Exception as exc:
                safe_error = _safe_error(exc)
                self.store.update_mcp_server(
                    server_id, tenant_id, {"last_error": safe_error},
                )
                logger.warning("MCP Server %s registration failed: %s", server_id, safe_error)
                return 0
            self._clients[server_id] = client
        bindings: list[ToolBinding] = []
        for tool in self.store.list_mcp_tools(server_id, tenant_id):
            if not tool.get("enabled") or tool.get("validation_status") != "passed":
                continue
            try:
                schema, _ = _validate_schema(tool.get("input_schema") or {})
                read_only = bool((tool.get("annotations") or {}).get("readOnlyHint") is True and (tool.get("annotations") or {}).get("destructiveHint") is not True)
                public_name = _runtime_tool_name(server_id, str(tool["remote_name"]))
                required_permissions = list(dict.fromkeys(
                    ["mcp.read" if read_only else "mcp.write"]
                    + list(tool.get("required_permissions") or [])
                ))
                definition = ToolDefinition(
                    name=public_name, skill=f"mcp:{server_id}", namespace=f"mcp:{server_id}",
                    description=f"{record.get('name')}: {tool.get('description') or tool.get('remote_name')}",
                    input_schema=schema,
                    action=str(tool.get("action") or "invoke"),
                    resource_type=str(tool.get("resource_type") or "mcp_invocation"),
                    intent_types=list(tool.get("intent_types") or [str(tool.get("remote_name"))]),
                    intent_aliases=list(tool.get("intent_aliases") or [str(tool.get("title") or "")]),
                    skill_refs=list(tool.get("skill_refs") or []),
                    risk_level=RiskLevel.LOW if read_only else RiskLevel.HIGH,
                    effect_class=ToolEffect.READ if read_only else ToolEffect.EXTERNAL_WRITE,
                    replay_policy=ReplayPolicy.SAFE if read_only else ReplayPolicy.UNSAFE,
                    traits=["external", "mcp"], live_support=read_only,
                    timeout_seconds=min(float(record.get("timeout_seconds") or 20.0), 120.0),
                    max_output_bytes=1_000_000,
                    required_permissions=required_permissions,
                    resource_id_field=tool.get("resource_id_field"),
                    readback_tool=tool.get("readback_tool"),
                    idempotency_key_field=tool.get("idempotency_key_field"),
                )
                definition.traits = list(dict.fromkeys(
                    list(tool.get("traits") or []) + ["external", "mcp"]
                ))
                bindings.append(
                    ToolBinding(
                        definition,
                        MCPToolHandler(
                            client, server_id, tenant_id, str(tool["remote_name"]),
                            write_effect=not read_only,
                        ),
                    )
                )
            except Exception as exc:
                logger.warning("MCP Tool %s registration failed: %s", tool.get("remote_name"), _safe_error(exc))
        names: list[str] = []
        source_id = f"mcp:{tenant_id}:{server_id}"
        source_registered = False
        if bindings:
            source = StaticToolSource(source_id, bindings)
            register_source = getattr(runtime, "register_tool_source", None)
            if callable(register_source):
                names = register_source(source)
                source_registered = True
            else:
                for binding in bindings:
                    runtime.registry.register(binding.definition, binding.executor)
                    names.append(binding.definition.name)
        self._registered[server_id] = names
        if names and source_registered:
            self._registered_sources[server_id] = source_id
        self._registered_tenants[server_id] = str(tenant_id)
        self._server_fingerprints[server_id] = self._fingerprint(record, self.store.list_mcp_tools(server_id, tenant_id))
        refresh = getattr(runtime, "_refresh_parser_catalog", None)
        if callable(refresh):
            refresh()
        return len(names)

    def _unregister(self, server_id: str, runtime: Any) -> None:
        source_id = self._registered_sources.pop(str(server_id), None)
        unregister_source = getattr(runtime, "unregister_tool_source", None)
        if source_id and callable(unregister_source):
            try:
                unregister_source(source_id)
            except Exception:
                logger.warning("failed to unregister MCP Tool source %s", source_id, exc_info=True)
        for name in self._registered.pop(str(server_id), []):
            try:
                # Older embedding facades may not expose source lifecycle yet.
                # The generic path above already removed these names.
                if not source_id:
                    runtime.registry.unregister(name)
            except Exception:
                logger.warning("failed to unregister MCP Tool %s", name, exc_info=True)
        self._clients.pop(str(server_id), None)
        self._registered_tenants.pop(str(server_id), None)
        self._server_fingerprints.pop(str(server_id), None)
        refresh = getattr(runtime, "_refresh_parser_catalog", None)
        if callable(refresh):
            refresh()


__all__ = ["MCPManagementError", "MCPServerManager", "MCPHTTPClient", "validate_mcp_endpoint"]
