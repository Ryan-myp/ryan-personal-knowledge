"""Chat spreadsheet statistics must use the scoped file, not a model excerpt."""

from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

from openpyxl import Workbook

from agents.agent_harness import (
    AgentApplication, InputMedia, ModelTurn, ToolCall, TurnRequest,
)
from agents.agent_harness.core.tool_selection import ToolSelector
from agents.agent_platform.tools.knowledge import knowledge_search_tool_source
from agents.applications.advertising.composition.ad_application_assembly import (
    AdApplicationAssembly,
)
from agents.deployments.advertising.api.chat_documents import open_chat_document_table
from agents.deployments.advertising.api.chat_media import ChatMediaStore
from agents.tools.data_analysis.chat_table import chat_table_tool_source


def _workbook(rows, *, header=("Key", "Assignee", "Story Points")):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Snapshot"
    sheet.append(header)
    for row in rows:
        sheet.append(row)
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def _context(*, session="session-a", user="user-a", tenant="tenant-a"):
    return SimpleNamespace(request=SimpleNamespace(
        session_id=session,
        user_id=user,
        principal=SimpleNamespace(tenant_id=tenant, user_id=user),
    ))


def _execute(store, attachment_id, **arguments):
    source = chat_table_tool_source(
        store, open_chat_document_table, required_permission="ads.read",
    )
    binding = source.list_bindings()[0]
    result = binding.executor.execute(
        arguments.pop("context", _context()),
        {"attachment_id": attachment_id, **arguments},
    )
    return result, binding.definition


def _save(store, rows, *, header=("Key", "Assignee", "Story Points")):
    return store.save(
        _workbook(rows, header=header),
        filename="snapshot.xlsx",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        session_id="session-a",
        tenant_id="tenant-a",
        user_id="user-a",
    )["id"]


def test_chat_table_inspect_and_complete_grouped_aggregation(tmp_path):
    store = ChatMediaStore(tmp_path)
    attachment_id = _save(store, [
        ("T-1", "A", 2.5),
        ("T-2", "A", None),
        ("T-2", "B", 3),
        ("T-3", None, 0),
        ("T-4", "B", "not a number"),
        *[(f"F-{i}", "A", 1) for i in range(1050)],
    ])
    inspect, definition = _execute(store, attachment_id, operation="inspect")
    assert inspect.success
    assert inspect.data["columns"] == ["Key", "Assignee", "Story Points"]
    assert inspect.data["row_count"] == 1055
    assert inspect.data["complete"] is True
    assert definition.effect_class.value == "read"
    assert definition.required_permissions == ["ads.read"]
    assert definition.input_schema.additional_properties is False

    result, _ = _execute(
        store, attachment_id, operation="aggregate",
        group_by="Assignee", value_column="Story Points", id_column="Key",
    )
    assert result.success
    assert result.data["complete"] is True
    assert result.data["row_count"] == 1055
    assert result.data["duplicate_id_count"] == 1
    assert result.data["missing_group_count"] == 1
    assert result.data["missing_value_count"] == 1
    assert result.data["invalid_value_count"] == 1
    groups = {item["group"]: item for item in result.data["groups"]}
    assert groups["A"]["row_count"] == 1052
    assert groups["A"]["value_sum"] == "1052.5"
    assert groups["B"]["row_count"] == 2
    assert groups["B"]["value_sum"] == "3"
    assert result.data["value_column"] == "Story Points"
    assert "工时" not in str(result.data)


def test_chat_table_rejects_missing_columns_and_cross_scope(tmp_path):
    store = ChatMediaStore(tmp_path)
    attachment_id = _save(store, [("T-1", "A", 1)])
    for arguments in (
        {"operation": "aggregate", "group_by": "Assignee", "value_column": "hours"},
        {"operation": "aggregate", "group_by": "No column", "value_column": "Story Points"},
        {"operation": "aggregate", "group_by": "Assignee", "value_column": "Story Points",
         "id_column": "Missing"},
        {"operation": "unknown"},
    ):
        result, _ = _execute(store, attachment_id, **arguments)
        assert result.success is False
    for context in (
        _context(session="other"),
        _context(user="other"),
        _context(tenant="other"),
        SimpleNamespace(request=SimpleNamespace(
            session_id="session-a", user_id="user-a", principal=None,
        )),
    ):
        result, _ = _execute(store, attachment_id, operation="inspect", context=context)
        assert result.success is False
        assert "Story Points" not in str(result)


def test_chat_table_fails_closed_for_oversize_and_paginates_groups(tmp_path):
    store = ChatMediaStore(tmp_path)
    attachment_id = _save(store, [(f"T-{i}", f"person-{i}", 1) for i in range(10001)])
    result, _ = _execute(store, attachment_id, operation="inspect")
    assert result.success is False
    assert "上限" in (result.error or "")

    attachment_id = _save(store, [(f"T-{i}", f"person-{i}", 1) for i in range(101)])
    result, _ = _execute(
        store, attachment_id, operation="aggregate",
        group_by="Assignee", value_column="Story Points",
        group_limit=20,
    )
    assert result.success is True
    assert result.data["group_count"] == 101
    assert result.data["total_value_sum"] == "101"
    assert len(result.data["groups"]) == 20
    assert result.data["has_more_groups"] is True
    next_page, _ = _execute(
        store, attachment_id, operation="aggregate",
        group_by="Assignee", value_column="Story Points",
        group_offset=100, group_limit=20,
    )
    assert next_page.success is True
    assert len(next_page.data["groups"]) == 1
    assert next_page.data["has_more_groups"] is False


def test_chat_table_csv_and_sensitive_columns(tmp_path):
    store = ChatMediaStore(tmp_path)
    attachment_id = store.save(
        b"Key,Assignee,Hours\nT-1,A,1.5\nT-2,A,\n",
        filename="hours.csv", content_type="text/csv",
        session_id="session-a", tenant_id="tenant-a", user_id="user-a",
    )["id"]
    result, _ = _execute(
        store, attachment_id, operation="aggregate",
        group_by="Assignee", value_column="Hours",
    )
    assert result.success
    assert result.data["groups"][0]["value_sum"] == "1.5"
    assert result.data["missing_value_count"] == 1

    secret_id = _save(store, [("T-1", "A", 1)], header=("Key", "access_token", "Story Points"))
    result, _ = _execute(store, secret_id, operation="inspect")
    assert result.success is False
    assert "access_token" not in (result.error or "")


def test_chat_table_counts_ragged_csv_rows_without_a_numeric_column(tmp_path):
    store = ChatMediaStore(tmp_path)
    attachment_id = store.save(
        b"Key,Assignee,Hours\nT-1,A,2\nT-2,A\nT-3,B,1\nT-4\n",
        filename="hours.csv", content_type="text/csv",
        session_id="session-a", tenant_id="tenant-a", user_id="user-a",
    )["id"]
    counts, _ = _execute(
        store, attachment_id, operation="aggregate", group_by="Assignee",
    )
    assert counts.success
    assert counts.data["row_count"] == 4
    assert counts.data["group_count"] == 3
    assert counts.data["missing_group_count"] == 1
    assert counts.data["groups"][0]["group"] == "A"
    assert counts.data["groups"][0]["row_count"] == 2
    assert "total_value_sum" not in counts.data
    assert "value_sum" not in counts.data["groups"][0]

    values, _ = _execute(
        store, attachment_id, operation="aggregate",
        group_by="Assignee", value_column="Hours",
    )
    assert values.success
    assert values.data["missing_value_count"] == 2
    assert values.data["total_value_sum"] == "3"


def test_chat_table_sums_decimal_values_exactly(tmp_path):
    store = ChatMediaStore(tmp_path)
    attachment_id = store.save(
        b"Assignee,Value\nA,1000000000000000000\n"
        + b"A,0.000000000001\n" * 10000,
        filename="values.csv", content_type="text/csv",
        session_id="session-a", tenant_id="tenant-a", user_id="user-a",
    )["id"]
    result, _ = _execute(
        store, attachment_id, operation="aggregate",
        group_by="Assignee", value_column="Value",
    )
    assert result.success is False
    assert "上限" in (result.error or "")

    attachment_id = store.save(
        b"Assignee,Value\nA,1000000000000000000\n"
        + b"A,0.000000000001\n" * 9999,
        filename="values.csv", content_type="text/csv",
        session_id="session-a", tenant_id="tenant-a", user_id="user-a",
    )["id"]
    result, _ = _execute(
        store, attachment_id, operation="aggregate",
        group_by="Assignee", value_column="Value",
    )
    assert result.success
    assert result.data["total_value_sum"] == "1000000000000000000.000000009999"
    assert result.data["groups"][0]["value_sum"] == result.data["total_value_sum"]


def test_chat_table_rejects_sensitive_columns_including_provider_credentials(tmp_path):
    store = ChatMediaStore(tmp_path)
    for header in (
        "bc_id", "partner_id", "mcc", "api_key_backup",
        "API Key backup", "private key",
    ):
        attachment_id = store.save(
            f"Assignee,{header}\nA,should-not-appear\n".encode(),
            filename="report.csv", content_type="text/csv",
            session_id="session-a", tenant_id="tenant-a", user_id="user-a",
        )["id"]
        result, _ = _execute(store, attachment_id, operation="inspect")
        assert result.success is False
        assert "should-not-appear" not in str(result)
        assert header not in str(result)


def test_chat_table_bounds_numeric_and_group_values(tmp_path):
    store = ChatMediaStore(tmp_path)
    attachment_id = _save(store, [
        ("T-1", "A", "1e1000000"),
        ("T-2", "A", 2),
    ])
    result, _ = _execute(
        store, attachment_id, operation="aggregate",
        group_by="Assignee", value_column="Story Points",
    )
    assert result.success is True
    assert result.data["invalid_value_count"] == 1
    assert result.data["value_complete"] is False
    assert result.data["total_value_sum"] == "2"

    attachment_id = _save(store, [("T-1", "A" * 501, 2)])
    result, _ = _execute(
        store, attachment_id, operation="aggregate",
        group_by="Assignee", value_column="Story Points",
    )
    assert result.success is False


def test_chat_turn_can_call_scoped_table_tool_without_provider_api(tmp_path):
    store = ChatMediaStore(tmp_path)
    attachment_id = _save(store, [("T-1", "A", 1), ("T-2", "A", 2)])
    observed = []

    class Model:
        def complete(self, messages, tools, request):
            observed.append((messages, {tool.name for tool in tools}))
            if not any(message.role == "tool" for message in messages):
                return ModelTurn(tool_calls=(ToolCall(
                    id="analyze-1",
                    name="agent_chat_table_analyze",
                    arguments={
                        "attachment_id": attachment_id,
                        "operation": "aggregate",
                        "group_by": "Assignee",
                        "value_column": "Story Points",
                    },
                ),))
            return ModelTurn(content="A: 2 条任务，3 Story Points；不是工时。")

    app = AgentApplication.create(
        model=Model(),
        tool_execution="sequential",
        before_tool_call=lambda _context: None,
    )
    app.register_tool_source(chat_table_tool_source(
        store, open_chat_document_table, required_permission="ads.read",
    ))
    try:
        result = app.runtime.run(TurnRequest(
            user_input="按人汇总我上传的表格",
            session_id="session-a",
            user_id="user-a",
            tenant_id="tenant-a",
            principal=SimpleNamespace(
                user_id="user-a", tenant_id="tenant-a",
                permissions=frozenset({"ads.read"}),
            ),
        ))
    finally:
        app.close()
    assert result.status.value == "succeeded"
    assert "agent_chat_table_analyze" in observed[0][1]
    assert "3 Story Points" in result.reply


def test_table_tool_is_selected_for_visualization_and_attached_data(tmp_path):
    store = ChatMediaStore(tmp_path)
    attachment_id = _save(store, [("T-1", "A", 1)])
    tool = chat_table_tool_source(
        store, open_chat_document_table, required_permission="ads.read",
    ).list_bindings()[0].definition
    knowledge = knowledge_search_tool_source(
        object(), required_permission="ads.read",
    ).list_bindings()[0].definition
    selector = ToolSelector()
    assert tool in selector.select_relevant(
        "按人跟工时进行可视化", [knowledge, tool], limit=10,
    )
    request = TurnRequest(
        user_input="这是数据", session_id="session-a",
        input_media=store.load_for_model(
            [attachment_id],
            session_id="session-a", tenant_id="tenant-a", user_id="user-a",
        ),
    )
    runtime = SimpleNamespace(
        registry=SimpleNamespace(list_all=lambda: [knowledge, tool]),
        _canonical_platform=lambda value: value,
    )
    selected = AdApplicationAssembly._tool_selector(runtime, selector)(
        request, [knowledge, tool],
    )
    assert selected == [tool]
    assert request.context["_agent_tool_choice_required"] is True
