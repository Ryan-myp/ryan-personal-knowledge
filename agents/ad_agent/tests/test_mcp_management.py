"""MCP control-plane and Runtime registration contracts."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from agents.ad_agent.core.interfaces import ToolContext
from agents.ad_agent.domain.ad.auth import RequestPrincipal
from agents.ad_agent.mcp_management import MCPServerManager
from agents.ad_agent.persistence.mysql_store import _mysql_schema
from agents.ad_agent.persistence.store import AdAgentStore
from agents.ad_agent.runtime.runtime import AgentRuntime


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
    runtime = AgentRuntime(require_llm=False, persistence_store=store, features=[])
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
            }, runtime,
        )
        assert configured["tools"][0]["intent_types"] == ["campaign_report"]
        assert configured["tools"][0]["skill_refs"] == ["reporting-sop"]
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


def test_mysql_schema_preserves_mcp_payload_capacity():
    sql = _mysql_schema(AdAgentStore.SCHEMA)
    assert "endpoint VARCHAR(2048)" in sql
    assert "validation_report LONGTEXT" in sql
    assert "input_schema LONGTEXT" in sql
    assert "annotations LONGTEXT" in sql
