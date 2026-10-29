from agents.agent_harness import ModelTurn, ToolCall
from agents.agent_harness.core.interfaces import ToolDefinition, ToolEffect, ToolSchema
from agents.agent_harness.core.tool_selection import ToolSelector
from agents.applications.advertising.composition.ad_application import AdvertisingComposition
from agents.applications.advertising.composition.ad_application_assembly import AdApplicationAssembly
from agents.agent_harness import TurnRequest
from agents.agent_platform.tools.clarification import clarification_tool_source
from types import SimpleNamespace


def test_advertising_conversation_returns_a_visible_clarification_without_provider_calls():
    question = "请选择要使用的平台。"

    class Model:
        def complete(self, *_args):
            return ModelTurn(tool_calls=(ToolCall(
                "ask", "agent_request_input", {"question": question, "choices": ["one", "two"]},
            ),))

    runtime = AdvertisingComposition(
        llm_client=Model(), offline_mode=True, start_background_workers=False,
        features=[],
    )
    try:
        result = runtime.run("创建一个资源", user_id="operator")
        assert result["needs_input"] is True
        assert question in result["reply"]
        assert result["ui"]["clarification"]["options"] == [
            {"label": "one", "value": "one"}, {"label": "two", "value": "two"},
        ]
        assert all(row["tool"] == "agent_request_input" for row in result["results"])
    finally:
        runtime.close(wait=True)


def test_interaction_tool_visibility_does_not_change_account_namespace_resolution():
    ask = clarification_tool_source(required_permission="ads.read").list_bindings()[0].definition
    report = SimpleNamespace(name="report", namespace="example", traits=[], scope_fields=[], input_schema={})
    tools = [report, ask]
    runtime = SimpleNamespace(registry=SimpleNamespace(list_all=lambda: tools))
    selector = SimpleNamespace(
        detect_namespaces=lambda *_: ["example"],
        is_read_only_request=lambda *_: False,
        has_declared_resource_target=lambda *_: True,
        explicitly_requests_discovery=lambda *_: False,
        select_relevant=lambda *_args, **_kwargs: [report],
        requires_tool_call=lambda *_args, **_kwargs: False,
    )
    request = TurnRequest(user_input="read a report", context={})
    selected = AdApplicationAssembly._tool_selector(runtime, selector)(request, tools)
    assert {tool.name for tool in selected} == {"report", "agent_request_input"}
    assert request.context["_agent_tool_namespaces"] == ["example"]


def test_process_comparison_with_an_image_does_not_offer_creation_or_clarification_tools():
    create = ToolDefinition(
        name="google_create_campaign",
        skill="google-ads",
        namespace="google-ads",
        description="创建 Google Ads campaign",
        input_schema=ToolSchema(properties={"name": {"type": "string"}}),
        action="create",
        resource_type="campaign",
        effect_class=ToolEffect.EXTERNAL_WRITE,
    )
    ask = clarification_tool_source(
        required_permission="ads.read",
    ).list_bindings()[0].definition
    tools = [create, ask]
    runtime = SimpleNamespace(
        registry=SimpleNamespace(list_all=lambda: tools),
    )
    selector = AdApplicationAssembly._tool_selector(runtime, ToolSelector())

    for prompt in (
        "看下比如用户说创建Google campaign，是这个流程不",
        "我说广告创建，agent里面执行的流程，是不是跟这个图里面的一样",
    ):
        request = TurnRequest(user_input=prompt, context={})
        assert selector(request, tools) == []
        assert request.context.get("_agent_tool_choice_required") is not True
