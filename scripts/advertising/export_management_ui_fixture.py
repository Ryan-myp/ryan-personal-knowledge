"""Export credential-free registry metadata for offline browser layout checks."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from agents.applications.advertising.composition.ad_application import AdvertisingComposition
from agents.applications.advertising.persistence.store import AdAgentStore
from agents.tools.advertising.providers.google import create_google_tool_source
from agents.tools.advertising.providers.meta import create_meta_tool_source
from agents.tools.advertising.providers.tiktok import create_tiktok_tool_source


def export_fixture() -> dict:
    """Use an in-memory store and metadata only; never execute a provider Tool."""
    app = AdvertisingComposition(
        require_llm=False, offline_mode=True, persistence_store=AdAgentStore(':memory:'))
    for factory in (create_google_tool_source, create_meta_tool_source, create_tiktok_tool_source):
        app.register_tool_source(factory())
    blueprints = app.list_creation_blueprints()
    templates = app.list_creation_templates(account_scope=None)
    tools = []
    for definition in app.registry.list_all():
        schema = definition.input_schema
        tools.append({
            'name': definition.name,
            'description': definition.description,
            'input_schema': {'properties': schema.properties, 'required': schema.required},
        })
    evaluations = {}
    for blueprint in blueprints:
        values = {field['path']: field['default']
                  for field in blueprint['fields'] if 'default' in field}
        starter = next((item for item in templates
                        if item['blueprint_id'] == blueprint['id']
                        and item['scope_type'] == 'general'), None)
        if starter:
            values.update(starter['values'])
        evaluations[blueprint['id']] = app.evaluate_creation_blueprint(blueprint['id'], values)
    return {'blueprints': blueprints, 'templates': templates, 'tools': tools,
            'formats': app.list_ad_formats(), 'evaluations': evaluations}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(export_fixture(), ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    main()
