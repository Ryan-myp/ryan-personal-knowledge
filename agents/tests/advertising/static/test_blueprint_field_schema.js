const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function environment() {
    const properties = {
        name: { type: 'string', maxLength: 80 },
        settings: {
            type: 'object', required: ['merchant_id'],
            properties: {
                merchant_id: { type: 'integer', minimum: 1, lookup_tool: 'list_merchants' },
                targeting: {
                    type: 'object', properties: {
                        regions: { type: 'array', items: { type: 'string', enum: ['US', 'CA'] } },
                    },
                },
            },
        },
        optional_object: { type: 'object', required: ['child'], properties: { child: { type: 'string' } } },
    };
    const ctx = { blueprintState: { tools: [{ name: 'create', input_schema: { properties, required: ['name'] } }] } };
    vm.runInNewContext(fs.readFileSync(path.resolve(__dirname,
        '../../../deployments/advertising/static/js/chat-blueprint-core.js'), 'utf8'), ctx);
    return ctx;
}

test('nested fields retain types, constraints, lookups and array choices', () => {
    const ctx = environment();
    const result = ctx.blueprintToolFieldSchema('create.settings.merchant_id');
    assert.equal(result.schema.type, 'integer');
    assert.equal(result.schema.minimum, 1);
    assert.equal(result.schema.lookup_tool, 'list_merchants');
    assert.equal(result.required, true);
    assert.equal(ctx.parsePresentedValue({}, '123', result.schema), 123);
    assert.deepEqual(Array.from(ctx.blueprintOptions({
        tool_ref: 'create.settings.targeting.regions',
    })), ['US', 'CA']);
});

test('object child required lists do not make an optional parent required', () => {
    const ctx = environment();
    assert.equal(ctx.blueprintToolFieldSchema('create.name').required, true);
    assert.equal(ctx.blueprintToolFieldSchema('create.optional_object').required, false);
    assert.equal(ctx.blueprintToolFieldSchema('create.settings.targeting').required, false);
});

test('unknown, empty and inherited paths fail closed', () => {
    const ctx = environment();
    for (const ref of ['missing.name', '', 'create', 'create.settings.missing',
        'create.settings..merchant_id', 'create.__proto__', 'create.constructor']) {
        const result = ctx.blueprintToolFieldSchema(ref);
        assert.equal(Object.keys(result.schema).length, 0, ref);
        assert.equal(result.required, false, ref);
    }
});

test('plain string arrays use line input while choices, lookups and explicit JSON retain their controls', () => {
    const ctx = environment();
    const spec = {type: 'array', items: {type: 'string'}};
    assert.equal(ctx.blueprintFieldPresentation({}, spec), 'text_list');
    assert.deepEqual(Array.from(ctx.parsePresentedValue({}, 'First\nSecond', spec)), ['First', 'Second']);
    assert.equal(ctx.blueprintFieldPresentation({presentation: 'advanced_json'}, spec), 'advanced_json');
    assert.equal(ctx.blueprintFieldPresentation({source: 'lookup'}, spec), undefined);
    assert.equal(ctx.blueprintFieldPresentation({}, {...spec, lookup_tool: 'list_items'}), undefined);
    assert.equal(ctx.blueprintFieldPresentation({}, {...spec, items: {type: 'string', enum: ['A']}}), undefined);
    assert.equal(ctx.blueprintFieldPresentation({options: ['A']}, spec), undefined);
    assert.equal(ctx.blueprintFieldPresentation({}, {...spec, items: {type: 'object'}}), undefined);
});
