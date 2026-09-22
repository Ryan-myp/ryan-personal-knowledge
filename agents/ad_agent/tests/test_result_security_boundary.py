"""Regression tests for the in-memory Tool result security boundary."""

import json

from agents.ad_agent.core.interfaces import (
    ToolContext,
    ToolDefinition,
    ToolEffect,
    ToolHandler,
    ToolResult,
    ToolSchema,
)
from agents.ad_agent.runtime.runtime import AdvertisingComposition


class _LeakyHandler(ToolHandler):
    def execute(self, _ctx, _input):
        return ToolResult(
            success=True,
            data={
                "safe": "visible",
                "access_token": "access-secret",
                "nested": {"refresh_token": "refresh-secret"},
            },
            error="provider access_token=error-secret",
            card_payload={"client_secret": "card-secret"},
        )


class _ExplodingHandler(ToolHandler):
    def execute(self, _ctx, _input):
        raise RuntimeError("provider access_token=exception-secret")


def _register(runtime, name, handler):
    runtime.registry.register(
        ToolDefinition(
            name=name,
            skill="security-test",
            namespace="security-test",
            description="security boundary test tool",
            input_schema=ToolSchema(),
            action="read",
            resource_type="status",
            intent_types=["read_status"],
            effect_class=ToolEffect.READ,
            required_permissions=["ads.read"],
        ),
        handler,
    )


def test_tool_result_data_error_and_card_are_redacted_before_return():
    runtime = AdvertisingComposition(require_llm=False, enforce_account_scope=False)
    _register(runtime, "security_leak_probe", _LeakyHandler())

    result = runtime.tool_executor.execute(
        ToolContext("security-session", "security-user"),
        "security_leak_probe",
        {},
    )

    encoded = json.dumps(result.to_dict(), ensure_ascii=False)
    assert result.success is True
    assert "access-secret" not in encoded
    assert "refresh-secret" not in encoded
    assert "error-secret" not in encoded
    assert "card-secret" not in encoded
    assert result.data["safe"] == "visible"


def test_handler_exception_becomes_redacted_tool_result():
    runtime = AdvertisingComposition(require_llm=False, enforce_account_scope=False)
    _register(runtime, "security_exception_probe", _ExplodingHandler())

    result = runtime.tool_executor.execute(
        ToolContext("security-session", "security-user"),
        "security_exception_probe",
        {},
    )

    assert result.success is False
    assert "exception-secret" not in str(result.error)
    assert "工具 security_exception_probe 执行失败" in str(result.error)
