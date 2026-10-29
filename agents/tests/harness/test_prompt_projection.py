"""模型输入投影保留执行约束，去除纯界面负载。"""

import copy

from agents.agent_harness.core.llm_client import LLMClient


def project(schema):
    return LLMClient._provider_tools([{
        "name": "example", "description": "Example", "input_schema": schema,
    }])[0]["function"]["parameters"]


def test_schema_projection_removes_presentation_recursively_without_changing_contract():
    schema = {"type": "object", "properties": {
        "records": {"type": "array", "minItems": 1, "items": {
            "type": "object", "properties": {
                "id": {"type": "string", "minLength": 1, "lookup_tool": "find_records",
                       "selection_label_fields": ["name"], "ui_visible_when": {"kind": "id"}},
                "ui_hidden": {"type": "boolean"},
            }, "required": ["id"], "additionalProperties": False,
        }},
        "settings": {"type": "object", "default": {"presentation": "literal value"},
                     "additionalProperties": {"type": "string", "maxLength": 20}},
    }, "required": ["records"], "additionalProperties": False,
        "oneOf": [{"required": ["records"]}, {"required": ["settings"]}]}
    original = copy.deepcopy(schema)
    result = project(schema)
    identifier = result["properties"]["records"]["items"]["properties"]["id"]
    assert "selection_label_fields" not in identifier
    assert "ui_visible_when" not in identifier
    assert identifier["lookup_tool"] == "find_records"
    assert result["oneOf"] == schema["oneOf"]
    assert result["properties"]["settings"] == schema["properties"]["settings"]
    assert "ui_hidden" in result["properties"]["records"]["items"]["properties"]
    assert schema == original


def test_schema_projection_preserves_constraints_inside_definitions_and_combinators():
    schema = {"type": "object", "properties": {"x": {"$ref": "#/$defs/variant"}},
              "$defs": {"variant": {"anyOf": [
                  {"type": "string", "enum": ["A"], "presentation": {"label": "A"}},
                  {"type": "array", "uniqueItems": True, "items": {"type": "number"}},
              ]}}, "if": {"required": ["x"]}, "then": {"required": ["y"]}}
    result = project(schema)
    variants = result["$defs"]["variant"]["anyOf"]
    assert "presentation" not in variants[0]
    assert variants[0]["enum"] == ["A"]
    assert variants[1]["uniqueItems"] is True
    assert result["then"] == {"required": ["y"]}


def test_schema_projection_removes_hidden_nested_arguments_and_required_entries():
    result = project({"type": "object", "properties": {"payload": {
        "type": "object", "properties": {
            "visible": {"type": "string"}, "server_value": {"type": "string", "ui_hidden": True},
        }, "required": ["visible", "server_value"],
    }}})
    assert result["properties"]["payload"]["required"] == ["visible"]
    assert "server_value" not in result["properties"]["payload"]["properties"]
