"""Check every built-in template against its pinned Blueprint, without storage writes."""

from functools import lru_cache

from agents.applications.advertising.creation.templates import (
    CreationTemplateError,
    CreationTemplateManager,
    load_builtin_template_definitions,
)
from agents.applications.advertising.creation.template_upgrade import (
    invalid_template_fields, registered_field_schema,
)


def audit_creation_templates(runtime, definitions=None):
    rows = load_builtin_template_definitions() if definitions is None else definitions

    @lru_cache(maxsize=128)
    def blueprint_data(identifier, version=None):
        blueprint = runtime.creation_blueprints.get(identifier, version)
        if blueprint is None:
            return None
        return runtime.creation_card_builder.expand_blueprint(blueprint).to_dict()

    manager = CreationTemplateManager(None, blueprint_data)
    issues = []
    for row in rows:
        try:
            _validate_template(manager, blueprint_data, row)
            if row.get("scope_type") == "general" and not row.get("catalog_hidden"):
                _validate_preset(runtime, blueprint_data, row)
        except CreationTemplateError as error:
            issues.append({"key": row["key"], "error": str(error)})
    starters = {
        (row["blueprint_id"], row["blueprint_version"]) for row in rows
        if row.get("scope_type") == "general" and not row.get("catalog_hidden")
    }
    missing = [
        {"blueprint_id": blueprint.blueprint_id, "version": blueprint.version}
        for blueprint in runtime.creation_blueprints.list()
        if blueprint.provider in runtime.ad_format_catalogs
        and (blueprint.blueprint_id, blueprint.version) not in starters
    ]
    return {
        "count": len(rows), "issues": issues, "provider_calls": 0,
        "missing_general_starters": missing,
    }


def _validate_preset(runtime, blueprint_data, row):
    blueprint = blueprint_data(row["blueprint_id"], row["blueprint_version"])
    evaluation = runtime.evaluate_creation_blueprint(
        row["blueprint_id"], row["values"], version=row["blueprint_version"],
    )
    invalid = set(evaluation["invalid_fields"])
    invalid.update(invalid_template_fields(
        blueprint, row["values"], lambda ref: registered_field_schema(runtime.registry, ref),
    ))
    defaults = {
        field["path"]: field["default"] for field in blueprint["fields"] if "default" in field
    }
    hydrated = runtime.evaluate_creation_blueprint(
        row["blueprint_id"], {**defaults, **row["values"]}, version=row["blueprint_version"],
    )
    invalid.update(hydrated["invalid_fields"])
    if invalid:
        raise CreationTemplateError("起步预设的参数不符合合同：" + "、".join(sorted(invalid)))


def _validate_template(manager, blueprint_data, row):
    blueprint = blueprint_data(row["blueprint_id"], row["blueprint_version"])
    if blueprint is None:
        raise CreationTemplateError("模板引用的蓝图版本不存在")
    if row["provider"] != blueprint["provider"] or row.get("ad_format") != blueprint["ad_format"]:
        raise CreationTemplateError("模板渠道或蓝图族标识与固定蓝图版本不一致")
    manager.validate_overrides(row, row["values"])
    fields = {item["path"] for item in blueprint["fields"]}
    for path in row.get("required_input_fields", []):
        if not any(path == field or path.startswith(field + ".") for field in fields):
            raise CreationTemplateError(f"模板必填项没有蓝图字段合同：{path}")
