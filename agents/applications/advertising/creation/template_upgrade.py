"""Pure comparison of immutable Blueprint versions for an explicit new draft."""

from copy import deepcopy
from typing import Any, Callable, Mapping

from agents.agent_harness.core.interfaces import ToolSchema
from agents.agent_harness.core.tool_registry import validate_tool_input
from agents.tools.advertising.shared.domain.blueprint import (
    AdCreationBlueprint, BlueprintCascadeEngine, _schema_at_path,
)


def preview_template_upgrade(
    template: Mapping[str, Any], source: Mapping[str, Any], target: Mapping[str, Any],
    *, field_schema_getter: Callable[[str], Mapping] | None = None,
) -> dict[str, Any]:
    old_fields = {field["path"]: field for field in source.get("fields", [])}
    new_fields = {field["path"]: field for field in target.get("fields", [])}
    original_values = template.get("values") or {}
    values = deepcopy({
        path: value for path, value in original_values.items() if path in new_fields
    })
    evaluation = BlueprintCascadeEngine().evaluate(AdCreationBlueprint.from_dict(target), values)
    invalid = list(evaluation["invalid_fields"])
    if field_schema_getter is not None:
        invalid.extend(invalid_template_fields(target, values, field_schema_getter))
    draft = {
        key: deepcopy(template.get(key))
        for key in ("name", "description", "provider", "blueprint_id", "scope_type",
                    "account_id", "region", "tags")
        if template.get(key) is not None
    }
    draft.update({
        "name": str(template["name"])[:100] + " · 升级副本",
        "blueprint_version": target["version"], "ad_format": target["ad_format"],
        "values": values, "status": "active", "is_default": False,
    })
    return {
        "preview_only": True, "source_template_id": template["template_id"],
        "source_version": source["version"], "target_version": target["version"],
        "blueprint": deepcopy(dict(target)), "draft": draft, "values": values,
        "added_fields": sorted(set(new_fields) - set(old_fields)),
        "removed_fields": sorted(set(original_values) - set(new_fields)),
        "changed_fields": sorted(
            path for path in set(old_fields) & set(new_fields)
            if old_fields[path] != new_fields[path]
        ),
        "missing_fields": list(evaluation["missing_fields"]),
        "invalid_fields": list(dict.fromkeys(invalid)),
        "verification_status": "pending_live_verification",
        "selection_revalidation_required": True,
    }


def invalid_template_fields(
    blueprint: Mapping, values: Mapping, field_schema_getter: Callable[[str], Mapping],
) -> list[str]:
    """Validate only provided values; partial presets need not be executable yet."""
    invalid = []
    for field in blueprint.get("fields", []):
        path = field["path"]
        if path not in values:
            continue
        spec = field_schema_getter(field["tool_ref"])
        if not spec or validate_tool_input(
            ToolSchema(properties={"value": dict(spec)}), {"value": values[path]},
        ):
            invalid.append(path)
    return invalid


def registered_field_schema(registry: Any, tool_ref: str) -> Mapping:
    tool_name, path = tool_ref.split(".", 1)
    try:
        definition, _handler = registry.get(tool_name)
    except KeyError:
        return {}
    return _schema_at_path(definition.input_schema.properties, path) or {}
