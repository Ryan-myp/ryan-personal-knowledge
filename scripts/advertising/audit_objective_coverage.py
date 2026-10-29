"""Check every provider-declared campaign selector, including missing formats."""

from collections import defaultdict
from typing import Any


def _objective_row(objective: str, blueprints: list, catalog: list) -> dict[str, Any]:
    declared_ids = {
        blueprint_id
        for entry in catalog if objective in entry.get("objective_values", [])
        for blueprint_id in entry.get("blueprint_ids", [])
    }
    matching = [
        blueprint for blueprint in blueprints
        if blueprint.blueprint_id in declared_ids
        or (blueprint.selector and objective in blueprint.selector["values"])
    ]
    entries = [
        entry for entry in catalog
        if objective in entry.get("objective_values", []) or any(
            blueprint.blueprint_id in entry.get("blueprint_ids", [])
            for blueprint in matching
        )
    ]
    limitations = [
        entry["creation_limitation"] for entry in entries
        if entry.get("creation_limitation")
    ]
    status = "guided_contract" if matching else "missing"
    if limitations:
        status = "restricted"
    return {
        "objective": objective,
        "blueprint_ids": sorted({blueprint.blueprint_id for blueprint in matching}),
        "status": status,
        "limitations": limitations[:1],
        "verification": "offline_contract_only",
    }


def audit_objective_coverage(runtime: Any) -> dict[str, Any]:
    selectors = defaultdict(set)
    for tool in runtime.registry.list_all():
        if tool.action != "create" or tool.resource_type != "campaign":
            continue
        for spec in tool.input_schema.properties.values():
            if spec.get("creation_selector"):
                selectors[tool.namespace].update(spec.get("enum", []))
    report = {}
    for provider, objectives in sorted(selectors.items()):
        blueprints = runtime.creation_blueprints.list(provider=provider)
        catalog = runtime.list_ad_formats(provider)
        rows = [
            _objective_row(objective, blueprints, catalog)
            for objective in sorted(objectives)
        ]
        report[provider] = {
            "objectives": rows,
            "missing": [row["objective"] for row in rows if row["status"] == "missing"],
        }
    return report
