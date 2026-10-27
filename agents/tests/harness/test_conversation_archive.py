"""Long-session context is scoped and bounded beyond the in-memory window."""

from agents.agent_harness import AgentApplication, AgentMessage, ModelTurn
from agents.agent_harness.conversation_recall import relevant_user_requests


class ArchiveStore:
    def __init__(self):
        self.messages = {}
        self.history_reads = []
        self.fail_history = False

    def load(self, session_id, *, tenant_id, user_id, limit=200):
        return list(self.messages.get((tenant_id, user_id, session_id), ())[-limit:])

    def append(self, session_id, messages, *, tenant_id, user_id):
        self.messages.setdefault((tenant_id, user_id, session_id), []).extend(messages)

    def clear(self, session_id, *, tenant_id, user_id):
        self.messages.pop((tenant_id, user_id, session_id), None)

    def load_user_history(self, session_id, *, tenant_id, user_id, limit):
        self.history_reads.append((tenant_id, user_id, session_id, limit))
        if self.fail_history:
            raise RuntimeError("private backend diagnostics")
        return [
            item for item in self.messages.get((tenant_id, user_id, session_id), ())
            if item.role == "user"
        ][-limit:]


class CaptureModel:
    def __init__(self):
        self.inputs = []

    def complete(self, messages, _tools, _request):
        self.inputs.append(tuple(messages))
        return ModelTurn(content="done")


def _seed(store, *, tenant="tenant-a", user="operator"):
    key = (tenant, user, "long-session")
    store.messages[key] = [
        AgentMessage.user("Meta campaign 归因方案：优先分析增量收益", turn_id="original"),
        AgentMessage.assistant("已记录", turn_id="original"),
    ]
    for index in range(110):
        store.messages[key].extend((
            AgentMessage.user(f"临时话题 {index}", turn_id=f"temp-{index}"),
            AgentMessage.assistant("收到", turn_id=f"temp-{index}"),
        ))


def test_archive_restores_a_relevant_goal_past_200_messages_once_per_run():
    store = ArchiveStore()
    _seed(store)
    model = CaptureModel()
    app = AgentApplication.create(
        model=model, transcript_store=store, max_transcript_messages=200,
        max_model_input_chars=12_000,
    )
    try:
        result = app.prompt(
            "继续 Meta campaign 归因方案",
            tenant_id="tenant-a", user_id="operator", session_id="long-session",
        )
        assert result.status.value == "succeeded"
        assert any(
            item.metadata.get("context_type") == "conversation_recall"
            and "增量收益" in item.content
            for item in model.inputs[-1]
        )
        assert store.history_reads == [("tenant-a", "operator", "long-session", 128)]
        assert not any(
            "增量收益" in item.content
            for item in app.agent._state_for("long-session", "operator", "tenant-a").messages
        )
    finally:
        app.close()


def test_archive_restores_tool_namespace_without_granting_a_write():
    from agents.agent_harness import StaticToolSource, ToolBinding
    from agents.agent_harness.core.interfaces import (
        ToolDefinition, ToolEffect, ToolSchema,
    )
    from agents.agent_harness.core.tool_selection import ToolSelector

    class ToolCapture(CaptureModel):
        def __init__(self):
            super().__init__()
            self.visible = []

        def complete(self, messages, tools, request):
            self.visible.append({tool.name for tool in tools})
            return super().complete(messages, tools, request)

    store = ArchiveStore()
    _seed(store)
    model = ToolCapture()
    selector = ToolSelector()
    tools = [
        ToolDefinition(
            name=f"{namespace}_list_campaigns", skill=namespace,
            namespace=namespace, description=f"List {namespace} campaigns",
            input_schema=ToolSchema(properties={}),
            action="list", resource_type="campaign", effect_class=ToolEffect.READ,
        )
        for namespace in ("meta", "google-ads")
    ]
    tools.append(ToolDefinition(
        name="meta_update_campaign", skill="meta", namespace="meta",
        description="Update Meta campaign", input_schema=ToolSchema(properties={}),
        action="update", resource_type="campaign", effect_class=ToolEffect.WRITE,
    ))
    app = AgentApplication.create(
        model=model, transcript_store=store,
        tool_selector=lambda request, catalog: selector.select_relevant(
            request.user_input, catalog,
            conversation_context=request.context.get(
                "_agent_tool_selection_context", (),
            ),
        ),
    )
    app.register_tool_source(StaticToolSource(
        "ads",
        [ToolBinding(tool, lambda _context, _args: {"success": True})
         for tool in tools],
    ))
    try:
        app.prompt(
            "继续查询 campaign 归因方案",
            tenant_id="tenant-a", user_id="operator", session_id="long-session",
        )
        assert model.visible[-1] == {"meta_list_campaigns"}
        assert store.history_reads == [("tenant-a", "operator", "long-session", 128)]
    finally:
        app.close()


def test_archive_does_not_cross_scope_or_reuse_stale_goal_on_new_topic():
    store = ArchiveStore()
    _seed(store)
    model = CaptureModel()
    app = AgentApplication.create(model=model, transcript_store=store)
    try:
        app.prompt(
            "继续 Meta campaign 归因方案",
            tenant_id="tenant-b", user_id="operator", session_id="long-session",
        )
        assert not any("增量收益" in str(item.content) for item in model.inputs[-1])
        app.prompt(
            "查询 Google campaign 归因报表",
            tenant_id="tenant-a", user_id="operator", session_id="long-session",
        )
        assert not any("增量收益" in str(item.content) for item in model.inputs[-1])
        assert not any(row[0] == "tenant-a" for row in store.history_reads)
    finally:
        app.close()


def test_archive_lookup_failure_is_advisory_and_does_not_expose_exception():
    store = ArchiveStore()
    _seed(store)
    store.fail_history = True
    events = []
    app = AgentApplication.create(
        model=CaptureModel(), transcript_store=store,
        event_callback=events.append,
    )
    try:
        result = app.prompt(
            "继续 Meta campaign 归因方案",
            tenant_id="tenant-a", user_id="operator", session_id="long-session",
        )
        assert result.status.value == "succeeded"
        assert "private backend diagnostics" not in str(events)
        assert any(event["type"] == "conversation_recall_error" for event in events)
    finally:
        app.close()


def test_archive_is_loaded_once_across_multiple_model_turns():
    from agents.agent_harness import StaticToolSource, ToolBinding, ToolCall
    from agents.agent_harness.core.interfaces import ToolDefinition, ToolSchema

    class TwoTurns(CaptureModel):
        def complete(self, messages, tools, request):
            self.inputs.append(tuple(messages))
            if len(self.inputs) == 1:
                return ModelTurn(tool_calls=(ToolCall("read-1", "local_lookup", {}),))
            return ModelTurn(content="done")

    store = ArchiveStore()
    _seed(store)
    app = AgentApplication.create(model=TwoTurns(), transcript_store=store)
    app.register_tool_source(StaticToolSource(
        "local", [ToolBinding(
            ToolDefinition(
                name="local_lookup", skill="local", namespace="local",
                description="Read local information",
                input_schema=ToolSchema(properties={}),
            ),
            lambda _context, _values: {"success": True},
        )],
    ))
    try:
        result = app.prompt(
            "继续 Meta campaign 归因方案",
            tenant_id="tenant-a", user_id="operator", session_id="long-session",
        )
        assert result.status.value == "succeeded"
        assert store.history_reads == [("tenant-a", "operator", "long-session", 128)]
    finally:
        app.close()


def test_reset_removes_archived_context_from_the_same_session():
    store = ArchiveStore()
    _seed(store)
    model = CaptureModel()
    app = AgentApplication.create(model=model, transcript_store=store)
    try:
        app.prompt(
            "继续 Meta campaign 归因方案",
            tenant_id="tenant-a", user_id="operator", session_id="long-session",
        )
        app.agent.reset("long-session", tenant_id="tenant-a", user_id="operator")
        app.prompt(
            "继续 Meta campaign 归因方案",
            tenant_id="tenant-a", user_id="operator", session_id="long-session",
        )
        assert not any("增量收益" in str(item.content) for item in model.inputs[-1])
    finally:
        app.close()


def test_weak_overlap_does_not_recall_unrelated_advertising_request():
    assert relevant_user_requests(
        "继续分析广告行业研究",
        [AgentMessage.user("创建 Meta 广告，分析受众")],
    ) == ()


def test_explicit_topic_switch_never_recalls_shared_resource_name():
    assert relevant_user_requests(
        "查询 Google campaign 归因报表",
        [AgentMessage.user("查询 Meta campaign 归因报表")],
    ) == ()


def test_topicless_continue_does_not_scan_the_archive():
    store = ArchiveStore()
    _seed(store)
    app = AgentApplication.create(
        model=CaptureModel(), transcript_store=store,
    )
    try:
        app.prompt(
            "继续", tenant_id="tenant-a", user_id="operator",
            session_id="long-session",
        )
        assert store.history_reads == []
    finally:
        app.close()
