"""MCP control-plane and Runtime registration contracts."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from agents.ad_agent.core.interfaces import ToolContext
from agents.ad_agent.domain.ad.auth import RequestPrincipal
from agents.ad_agent.mcp_management import (
    MCPManagementError,
    MCPServerManager,
    MCPToolHandler,
)
from agents.ad_agent.persistence.mysql_store import _mysql_schema
from agents.ad_agent.persistence.store import AdAgentStore
from agents.ad_agent.runtime.runtime import AdvertisingComposition


class _MCPHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802 - stdlib HTTP handler contract
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        method = payload.get("method")
        if method == "notifications/initialized":
            self.send_response(202)
            self.end_headers()
            return
        if method == "initialize":
            result = {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "test-mcp", "version": "1.0.0"},
            }
        elif method == "tools/list":
            result = {"tools": [{
                "name": "lookup_report",
                "title": "Lookup report",
                "description": "Read a report from the test MCP server.",
                "inputSchema": {
                    "type": "object",
                    "required": ["account"],
                    "properties": {"account": {"type": "string"}},
                },
                "annotations": {"readOnlyHint": True, "destructiveHint": False},
            }]}
        elif method == "tools/call":
            result = {"content": [{"type": "text", "text": "ok"}]}
        else:
            result = {"error": {"code": -32601, "message": "unknown method"}}
        body = json.dumps({"jsonrpc": "2.0", "id": payload.get("id"), "result": result}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        return


def test_mcp_validation_discovers_tools_and_registers_only_enabled_tools():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _MCPHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    store = AdAgentStore(":memory:")
    runtime = AdvertisingComposition(require_llm=False, persistence_store=store, features=[])
    manager = MCPServerManager(store)
    try:
        created = manager.create_server(
            "tenant-a",
            {
                "name": "test-server",
                "endpoint": f"http://127.0.0.1:{server.server_port}/mcp",
                "auth_type": "none",
            },
            "operator",
        )
        validated = manager.validate_server("tenant-a", created["server_id"], ["all"])
        assert validated["validation_status"] == "passed"
        assert validated["timeout_seconds"] == 20.0
        assert len(validated["tools"]) == 1
        assert validated["tools"][0]["enabled"] is False
        assert validated["tools"][0]["trusted_read"] is False

        manager.enable_server("tenant-a", created["server_id"], runtime)
        assert not any(item.name.startswith("mcp__") for item in runtime.registry.list_all())
        enabled = manager.enable_tool(
            "tenant-a", created["server_id"], validated["tools"][0]["tool_id"], runtime
        )
        assert enabled["tools"][0]["enabled"] is True
        configured = manager.update_tool_metadata(
            "tenant-a", created["server_id"], validated["tools"][0]["tool_id"],
            {
                "intent_types": ["campaign_report"],
                "intent_aliases": ["分析 Campaign 表现"],
                "skill_refs": ["reporting-sop"],
                "action": "query",
                "resource_type": "campaign_report",
                "required_permissions": ["ads.read"],
                "trusted_read": True,
            }, runtime,
        )
        assert configured["tools"][0]["intent_types"] == ["campaign_report"]
        assert configured["tools"][0]["skill_refs"] == ["reporting-sop"]
        assert configured["tools"][0]["trusted_read"] is True
        tool = next(item for item in runtime.registry.list_all() if item.name.startswith("mcp__"))
        assert tool.intent_types == ["campaign_report"]
        assert tool.skill_refs == ["reporting-sop"]
        _definition, handler = runtime._get_registered_tool(tool.name)
        result = handler.execute(
            ToolContext(session_id="session", user_id="user", metadata={"tenant_id": "tenant-a"}),
            {"account": "account-1"},
        )
        assert result.success is True
        assert result.data["mcp_tool"] == "lookup_report"
        tested = manager.test_tool(
            "tenant-a", created["server_id"], validated["tools"][0]["tool_id"],
            runtime,
            RequestPrincipal(
                user_id="operator", tenant_id="tenant-a",
                permissions=frozenset({"mcp.read", "mcp.manage", "ads.read"}),
            ),
            {"account": "account-1"},
        )
        assert tested["success"] is True
        assert tested["remote_tool"] == "lookup_report"
    finally:
        runtime.close(wait=True)
        store.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_mcp_handler_never_calls_remote_write_in_dry_run():
    calls = []

    class Client:
        def call_tool(self, name, arguments):
            calls.append((name, arguments))
            return {"structuredContent": {"created": True}}

    result = MCPToolHandler(
        Client(),
        "server-a",
        "tenant-a",
        "create_record",
        write_effect=True,
    ).execute(
        ToolContext(
            session_id="session",
            user_id="user",
            metadata={"tenant_id": "tenant-a", "execution_mode": "dry_run"},
        ),
        {"name": "record"},
    )

    assert calls == []
    assert result.success is True
    assert result.data["executed"] is False
    assert result.data["execution_status"] == "dry_run_only"
    assert result.data["effect_state"] == "not_started"


def test_mcp_handler_fails_closed_for_live_write_without_host_trust_or_idempotency():
    calls = []

    class Client:
        def call_tool(self, name, arguments):
            calls.append((name, arguments))
            return {"structuredContent": {"created": True}}

    context = ToolContext(
        session_id="session",
        user_id="user",
        metadata={"tenant_id": "tenant-a", "execution_mode": "live"},
    )
    untrusted = MCPToolHandler(
        Client(),
        "server-a",
        "tenant-a",
        "create_record",
        write_effect=True,
    ).execute(context, {"request_id": "request-1"})
    missing_key = MCPToolHandler(
        Client(),
        "server-a",
        "tenant-a",
        "create_record",
        write_effect=True,
        live_write_allowed=True,
        idempotency_key_field="request_id",
    ).execute(context, {})

    assert untrusted.success is False
    assert untrusted.data["execution_status"] == "blocked_untrusted_write"
    assert missing_key.success is False
    assert missing_key.data["execution_status"] == "blocked_missing_idempotency_key"
    assert calls == []


def test_mcp_remote_annotation_cannot_be_used_as_host_read_trust():
    store = AdAgentStore(":memory:")
    runtime = AdvertisingComposition(
        require_llm=False,
        persistence_store=store,
        features=[],
    )
    manager = MCPServerManager(store)
    try:
        created = manager.create_server(
            "tenant-a",
            {
                "name": "test-server",
                "endpoint": "http://127.0.0.1:8765/mcp",
                "auth_type": "none",
            },
            "operator",
        )
        tool = store.upsert_mcp_tool({
            "tool_id": "tool-a",
            "server_id": created["server_id"],
            "tenant_id": "tenant-a",
            "remote_name": "lookup_report",
            "input_schema": {"type": "object", "properties": {}},
            "annotations": {"readOnlyHint": True},
            "validation_status": "passed",
        })
        with pytest.raises(MCPManagementError, match="mcp:trusted_read"):
            manager.update_tool_metadata(
                "tenant-a",
                created["server_id"],
                tool["tool_id"],
                {
                    "intent_types": ["lookup_report"],
                    "traits": ["mcp:trusted_read"],
                },
                runtime,
            )
    finally:
        runtime.close(wait=True)
        store.close()


def test_mcp_live_create_requires_schema_idempotency_but_not_input_resource_id():
    store = AdAgentStore(":memory:")
    runtime = AdvertisingComposition(
        require_llm=False,
        persistence_store=store,
        features=[],
    )
    manager = MCPServerManager(store)
    try:
        created = manager.create_server(
            "tenant-a",
            {
                "name": "test-server",
                "endpoint": "http://127.0.0.1:8765/mcp",
                "auth_type": "none",
            },
            "operator",
        )
        tool = store.upsert_mcp_tool({
            "tool_id": "create-record",
            "server_id": created["server_id"],
            "tenant_id": "tenant-a",
            "remote_name": "create_record",
            "input_schema": {
                "type": "object",
                "required": ["name", "request_id"],
                "properties": {
                    "name": {"type": "string"},
                    "request_id": {"type": "string"},
                },
            },
            "validation_status": "passed",
        })

        with pytest.raises(MCPManagementError, match="idempotency_key_field"):
            manager.update_tool_metadata(
                "tenant-a",
                created["server_id"],
                tool["tool_id"],
                {
                    "intent_types": ["create_record"],
                    "action": "create",
                    "live_write_enabled": True,
                },
                runtime,
            )
        with pytest.raises(MCPManagementError, match="可信只读"):
            manager.update_tool_metadata(
                "tenant-a",
                created["server_id"],
                tool["tool_id"],
                {
                    "intent_types": ["create_record"],
                    "action": "create",
                    "trusted_read": True,
                },
                runtime,
            )

        result = manager.update_tool_metadata(
            "tenant-a",
            created["server_id"],
            tool["tool_id"],
            {
                "intent_types": ["create_record"],
                "action": "create",
                "idempotency_key_field": "request_id",
                "live_write_enabled": True,
            },
            runtime,
        )
        saved = next(
            item for item in result["tools"]
            if item["tool_id"] == tool["tool_id"]
        )
        assert saved["live_write_enabled"] is True
        assert saved["idempotency_key_field"] == "request_id"
        assert saved["resource_id_field"] is None
    finally:
        runtime.close(wait=True)
        store.close()


def test_mysql_schema_preserves_mcp_payload_capacity():
    sql = _mysql_schema(AdAgentStore.SCHEMA)
    assert "endpoint VARCHAR(2048)" in sql
    assert "validation_report LONGTEXT" in sql
    assert "input_schema LONGTEXT" in sql
    assert "annotations LONGTEXT" in sql


def test_mcp_conflicts_are_normalized_at_the_persistence_boundary():
    store = AdAgentStore(":memory:")
    manager = MCPServerManager(store)
    payload = {
        "server_id": "duplicate-server",
        "name": "duplicate",
        "endpoint": "http://127.0.0.1:8765/mcp",
        "auth_type": "none",
    }
    try:
        manager.create_server("tenant-a", payload, "operator")
        with pytest.raises(MCPManagementError, match="同名 MCP Server"):
            manager.create_server("tenant-a", payload, "operator")
    finally:
        store.close()
