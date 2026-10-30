"""The real advertising composition accepts a reviewed engine, not a second app."""
from agents.applications.advertising.composition.ad_application import AdvertisingComposition
from agents.tests.harness.test_execution_engines import ScriptEngine


def test_advertising_uses_selected_engine_with_existing_services():
    snapshots = []
    def script(session):
        snapshots.append(session.snapshot())
        session.emit_text("沿用原服务")
        session.finish("使用平台管理的 Skills 和工具")
    engine = ScriptEngine(script)
    runtime = AdvertisingComposition(
        execution_engine=engine, require_llm=True, features=[],
        start_background_workers=False,
    )
    try:
        result = runtime.run("你好", user_id="operator-1")
        assert result["status"] == "succeeded", result
        assert result["reply"] == "使用平台管理的 Skills 和工具"
        assert len(snapshots) == 1
        assert runtime.platform_application.engine is engine
        assert runtime.plugin_registry.get(engine.manifest.plugin_id).contribution is engine
        assert runtime.platform_application.harness.skills is not None
        assert runtime.platform_application.harness.tools is not None
    finally:
        runtime.close(wait=True)


def test_replacement_engine_executes_registered_advertising_tools_and_projects_results():
    from agents.agent_harness import ToolCall
    from agents.agent_harness.core.interfaces import ToolEffect, ToolResult, ToolSchema
    from agents.tests.advertising.test_generic_runtime_contracts import _tool
    executed = []
    def script(session):
        assert "custom_read_record" in [t["name"] for t in session.snapshot().tools]
        rows = session.call_tools([ToolCall("read-1", "custom_read_record", {})])
        assert not rows[0]["is_error"]
        session.finish("读取完成")
    runtime = AdvertisingComposition(
        execution_engine=ScriptEngine(script), require_llm=True, features=[],
        start_background_workers=False, enforce_account_scope=False,
    )
    runtime.register_tool(_tool(
        name="custom_read_record", namespace="custom", skill="custom",
        description="Read records from custom", action="list", effect_class=ToolEffect.READ,
        input_schema=ToolSchema(), intent_types=["list_records"],
    ), lambda context, args: executed.append(context) or ToolResult.ok({"count": 3}),
        source_id="custom-source")
    try:
        result = runtime.run("Read records from custom", user_id="operator-1")
        assert result["status"] == "succeeded", result
        assert result["tool_plan"] == {"custom": ["custom_read_record"]}
        assert len(executed) == 1
    finally:
        runtime.close(wait=True)
