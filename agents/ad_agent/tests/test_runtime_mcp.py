import asyncio
import json
from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.testclient import TestClient

from agents.ad_agent import AgentRuntime
from agents.ad_agent.runtime_mcp import RuntimeMCPServers, _current_principal
from agents.ad_agent.core.interfaces import (
    RiskLevel, ReplayPolicy, ToolDefinition, ToolEffect, ToolHandler, ToolResult, ToolSchema,
)
from agents.ad_agent.domain.ad.auth import RequestPrincipal


class _NeverCalledHandler(ToolHandler):
    def execute(self, _ctx, _input_data):
        raise AssertionError("dry-run MCP write must not invoke the handler")


class _ReadHandler(ToolHandler):
    def execute(self, _ctx, input_data):
        return ToolResult(success=True, data={"input": input_data})


def test_runtime_mcp_server_wraps_registry_tool_and_keeps_writes_dry_run():
    runtime = AgentRuntime(require_llm=False, features=[])
    definition = ToolDefinition(
        name="test_channel_create",
        skill="test-tool_source",
        namespace="test-channel",
        description="Test channel create",
        input_schema=ToolSchema(type="object", required=["name"], properties={"name": {"type": "string"}}),
        action="create",
        resource_type="campaign",
        risk_level=RiskLevel.HIGH,
        effect_class=ToolEffect.WRITE,
        replay_policy=ReplayPolicy.UNSAFE,
        required_permissions=["ads.plan"],
        resource_id_field="campaign_id",
    )
    runtime.registry.register(definition, _NeverCalledHandler())
    principal = RequestPrincipal(
        user_id="operator", tenant_id="tenant-a", permissions=frozenset({"ads.plan"}),
    )
    gateway = RuntimeMCPServers(lambda: runtime, lambda *_args, **_kwargs: principal)
    try:
        assert gateway.refresh(runtime) == 1
        servers = gateway.list_servers(runtime)
        assert [server["server_id"] for server in servers] == ["channel-test_channel"]
        assert servers[0]["source"] == "runtime_registry"
        assert servers[0]["endpoint"] == "/mcp/channels/test_channel/mcp"
        tested = gateway.test_tool(
            "channel-test_channel", "test_channel_create", runtime, principal,
            {"name": "draft"},
        )
        assert tested["success"] is True
        assert tested["data"]["simulated"] is True

        async def call_tool():
            token = _current_principal.set(principal)
            try:
                tools = await gateway._mcps["test_channel"].list_tools()
                result = await gateway._mcps["test_channel"].call_tool("test_channel_create", {"name": "draft"})
                return tools, result
            finally:
                _current_principal.reset(token)

        tools, result = asyncio.run(call_tool())
        assert [item.name for item in tools] == ["test_channel_create"]
        assert result.is_error is False
        assert result.structured_content["success"] is True
        assert result.structured_content["data"]["simulated"] is True
    finally:
        runtime.close(wait=True)


def test_runtime_mcp_server_uses_principal_scoped_mode_for_write_guard():
    runtime = AgentRuntime(require_llm=False, features=[])
    definition = ToolDefinition(
        name="test_channel_create",
        skill="test-tool_source",
        namespace="test-channel",
        description="Test channel create",
        input_schema=ToolSchema(type="object", required=["name"], properties={"name": {"type": "string"}}),
        action="create",
        resource_type="campaign",
        risk_level=RiskLevel.HIGH,
        effect_class=ToolEffect.WRITE,
        replay_policy=ReplayPolicy.UNSAFE,
        required_permissions=["ads.plan"],
    )
    runtime.registry.register(definition, _NeverCalledHandler())
    principal = RequestPrincipal(
        user_id="operator", tenant_id="tenant-a", permissions=frozenset({"ads.plan"}),
    )
    runtime.set_execution_mode("live", tenant_id="tenant-a", user_id="operator")
    gateway = RuntimeMCPServers(lambda: runtime, lambda *_args, **_kwargs: principal)
    try:
        assert gateway.list_servers(runtime, principal)[0]["execution_mode"] == "live"
        try:
            gateway.test_tool(
                "channel-test_channel", "test_channel_create", runtime, principal,
                {"name": "must-not-run"},
            )
        except PermissionError as exc:
            assert "当前为 live 模式" in str(exc)
        else:
            raise AssertionError("live scoped mode must block direct MCP write tests")
    finally:
        runtime.close(wait=True)


def test_runtime_mcp_server_streamable_http_starts_lifespan_and_calls_tool(monkeypatch):
    """The mounted protocol endpoint must initialize FastMCP's session manager."""
    monkeypatch.setenv("AD_AGENT_MCP_CHANNELS_ENABLED", "1")
    runtime = AgentRuntime(require_llm=False, features=[])
    definition = ToolDefinition(
        name="test_channel_read",
        skill="test-tool_source",
        namespace="test-channel",
        description="Test channel read",
        input_schema=ToolSchema(
            type="object", required=["value"], properties={"value": {"type": "string"}}
        ),
        action="read",
        resource_type="campaign",
        risk_level=RiskLevel.LOW,
        effect_class=ToolEffect.READ,
        replay_policy=ReplayPolicy.SAFE,
        required_permissions=[],
    )
    runtime.registry.register(definition, _ReadHandler())
    principal = RequestPrincipal(
        user_id="operator", tenant_id="tenant-a", permissions=frozenset({"ads.read"}),
    )
    gateway = RuntimeMCPServers(lambda: runtime, lambda *_args, **_kwargs: principal)
    gateway.refresh(runtime)
    child = gateway.asgi_app()

    @asynccontextmanager
    async def lifespan(app):
        async with child.lifespan(app):
            yield

    app = Starlette(lifespan=lifespan)
    app.mount("/", child)

    def rpc_response(response):
        assert response.status_code == 200
        events = [line[6:] for line in response.text.splitlines() if line.startswith("data: ")]
        assert events, response.text
        return json.loads(events[-1])

    try:
        with TestClient(app) as client:
            headers = {
                "X-API-Key": "test-key",
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            }
            initialize = client.post(
                "/test_channel/mcp", headers=headers, json={
                    "jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-06-18", "capabilities": {},
                        "clientInfo": {"name": "test-client", "version": "1.0"},
                    },
                },
            )
            assert rpc_response(initialize)["result"]["serverInfo"]["name"] == "ad-agent-test_channel-tools"

            initialized = client.post(
                "/test_channel/mcp", headers=headers,
                json={"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
            )
            assert initialized.status_code == 202

            called = client.post(
                "/test_channel/mcp", headers=headers, json={
                    "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                    "params": {"name": "test_channel_read", "arguments": {"value": "ok"}},
                },
            )
            result = rpc_response(called)["result"]
            assert result["isError"] is False
            assert result["structuredContent"]["data"] == {"input": {"value": "ok"}}
    finally:
        runtime.close(wait=True)
