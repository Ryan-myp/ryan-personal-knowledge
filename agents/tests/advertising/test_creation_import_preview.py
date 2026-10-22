from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.applications.advertising.creation.import_preview import (
    preview_creation_rows,
)
from agents.deployments.advertising.api.chat_documents import (
    read_chat_document_table,
)


def test_csv_table_reader_returns_headers_and_typed_cells():
    table = read_chat_document_table(
        b"campaign,budget,active\nSpring,125.5,true\n",
        filename="campaigns.csv",
        media_type="text/csv",
    )

    assert table == {
        "headers": ["campaign", "budget", "active"],
        "rows": [["Spring", "125.5", "true"]],
        "sheet_name": "",
        "truncated": False,
    }


def test_csv_table_reader_rejects_duplicate_or_empty_headers():
    with pytest.raises(ValueError, match="header"):
        read_chat_document_table(
            b"campaign,campaign\nA,B\n",
            filename="campaigns.csv",
            media_type="text/csv",
        )
    with pytest.raises(ValueError, match="header"):
        read_chat_document_table(
            b"campaign,,budget\nA,B,C\n",
            filename="campaigns.csv",
            media_type="text/csv",
        )


def test_import_preview_maps_blueprint_fields_and_reports_each_row():
    blueprint = SimpleNamespace(
        blueprint_id="example.search",
        version="1.0.0",
        fields=(
            {
                "path": "campaign.name",
                "tool_ref": "create_campaign.name",
                "label": "Campaign 名称",
            },
            {
                "path": "campaign.daily_budget",
                "tool_ref": "create_campaign.daily_budget",
                "label": "日预算",
            },
        ),
    )
    tool_definition = SimpleNamespace(input_schema=SimpleNamespace(
        properties={
            "name": {"type": "string"},
            "daily_budget": {"type": "number"},
        },
    ))
    evaluations = []
    runtime = SimpleNamespace(
        creation_blueprints=SimpleNamespace(
            get=lambda blueprint_id, version=None: (
                blueprint
                if blueprint_id == "example.search" and version in {None, "1.0.0"}
                else None
            ),
        ),
        creation_card_builder=SimpleNamespace(
            expand_blueprint=lambda item: item,
        ),
        _get_registered_tool=lambda name: (tool_definition, object()),
        evaluate_creation_blueprint=lambda blueprint_id, values, **_kwargs: (
            evaluations.append(dict(values))
            or {
                "ready": bool(values.get("campaign", {}).get("name")),
                "missing_fields": (
                    [] if values.get("campaign", {}).get("name")
                    else ["campaign.name"]
                ),
                "invalid_fields": [],
            }
        ),
    )

    result = preview_creation_rows(
        runtime,
        blueprint_id="example.search",
        version="1.0.0",
        headers=["Campaign", "Daily Budget"],
        rows=[["Spring", "125.5"], ["Summer", "not-a-number"]],
        column_mapping={
            "campaign.name": "Campaign",
            "campaign.daily_budget": "Daily Budget",
        },
    )

    assert result["preview_only"] is True
    assert result["ready_count"] == 1
    assert result["invalid_count"] == 1
    assert evaluations == [
        {"campaign": {"name": "Spring", "daily_budget": 125.5}},
        {"campaign": {"name": "Summer"}},
    ]
    assert result["rows"][1]["invalid_fields"] == ["campaign.daily_budget"]


def test_import_preview_rejects_unknown_columns_paths_and_excess_rows():
    blueprint = SimpleNamespace(
        blueprint_id="example.search",
        version="1.0.0",
        fields=({"path": "campaign.name", "tool_ref": "create_campaign.name"},),
    )
    runtime = SimpleNamespace(
        creation_blueprints=SimpleNamespace(get=lambda *_args: blueprint),
        creation_card_builder=SimpleNamespace(expand_blueprint=lambda item: item),
        _get_registered_tool=lambda _name: (
            SimpleNamespace(input_schema=SimpleNamespace(
                properties={"name": {"type": "string"}},
            )),
            object(),
        ),
        evaluate_creation_blueprint=lambda *_args, **_kwargs: {
            "ready": True,
            "missing_fields": [],
            "invalid_fields": [],
        },
    )

    with pytest.raises(ValueError, match="column"):
        preview_creation_rows(
            runtime,
            blueprint_id="example.search",
            version=None,
            headers=["Campaign"],
            rows=[["Spring"]],
            column_mapping={"campaign.name": "Missing"},
        )
    with pytest.raises(ValueError, match="blueprint field"):
        preview_creation_rows(
            runtime,
            blueprint_id="example.search",
            version=None,
            headers=["Campaign"],
            rows=[["Spring"]],
            column_mapping={"campaign.secret": "Campaign"},
        )
    with pytest.raises(ValueError, match="100"):
        preview_creation_rows(
            runtime,
            blueprint_id="example.search",
            version=None,
            headers=["Campaign"],
            rows=[["Spring"]] * 101,
            column_mapping={"campaign.name": "Campaign"},
        )


def test_import_preview_validates_object_fields_using_the_object_schema():
    blueprint = SimpleNamespace(
        blueprint_id="example.search",
        version="1.0.0",
        fields=({
            "path": "campaign.targeting",
            "tool_ref": "create_campaign.targeting",
        },),
    )
    tool_definition = SimpleNamespace(input_schema=SimpleNamespace(
        properties={
            "targeting": {
                "type": "object",
                "properties": {
                    "locations": {"type": "array"},
                },
            },
        },
    ))
    runtime = SimpleNamespace(
        creation_blueprints=SimpleNamespace(get=lambda *_args: blueprint),
        _get_registered_tool=lambda _name: (tool_definition, object()),
        evaluate_creation_blueprint=lambda _blueprint_id, values, **_kwargs: {
            "ready": isinstance(values.get("campaign", {}).get("targeting"), dict),
            "missing_fields": [],
            "invalid_fields": [],
        },
    )

    result = preview_creation_rows(
        runtime,
        blueprint_id="example.search",
        version=None,
        headers=["Targeting"],
        rows=[['{"locations":["US"]}']],
        column_mapping={"campaign.targeting": "Targeting"},
    )

    assert result["rows"][0]["values"] == {
        "campaign": {"targeting": {"locations": ["US"]}},
    }
    assert result["rows"][0]["ready"] is True
    assert result["rows"][0]["field_errors"] == {}


def test_import_preview_reports_short_and_long_rows_without_dropping_row_errors():
    blueprint = SimpleNamespace(
        blueprint_id="example.search",
        version="1.0.0",
        fields=(
            {"path": "campaign.name", "tool_ref": "create_campaign.name"},
            {
                "path": "campaign.daily_budget",
                "tool_ref": "create_campaign.daily_budget",
            },
        ),
    )
    runtime = SimpleNamespace(
        creation_blueprints=SimpleNamespace(get=lambda *_args: blueprint),
        _get_registered_tool=lambda _name: (
            SimpleNamespace(input_schema=SimpleNamespace(properties={
                "name": {"type": "string"},
                "daily_budget": {"type": "number"},
            })),
            object(),
        ),
        evaluate_creation_blueprint=lambda _blueprint_id, _values, **_kwargs: {
            "ready": True,
            "missing_fields": [],
            "invalid_fields": [],
        },
    )

    result = preview_creation_rows(
        runtime,
        blueprint_id="example.search",
        version=None,
        headers=["Campaign", "Budget"],
        rows=[["Spring"], ["Summer", "20", "extra"]],
        column_mapping={
            "campaign.name": "Campaign",
            "campaign.daily_budget": "Budget",
        },
    )

    assert result["rows"][0]["field_errors"] == {
        "campaign.daily_budget": "该行缺少已映射的单元格",
    }
    assert result["rows"][1]["field_errors"]["$row"] == (
        "该行的单元格数量超过表头列数"
    )


def test_xlsx_table_reader_limits_preview_and_reports_truncation():
    from io import BytesIO

    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Campaigns"
    sheet.append(["Campaign", "Daily Budget"])
    for index in range(101):
        sheet.append([f"Campaign {index}", index + 1])
    stream = BytesIO()
    workbook.save(stream)

    table = read_chat_document_table(
        stream.getvalue(),
        filename="campaigns.xlsx",
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    )

    assert table["sheet_name"] == "Campaigns"
    assert len(table["rows"]) == 100
    assert table["truncated"] is True
