const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function environment() {
    const evaluated = [];
    const blueprint = {
        id: 'example.complete', version: '1.0.0',
        selector: { field: 'campaign.objective', values: ['TRAFFIC'] },
        fields: [],
    };
    const context = {
        blueprintState: { items: [blueprint], templates: [], accountId: '' },
        blueprintDefaultValues: () => ({}),
        document: { getElementById: () => null, querySelector: () => null },
        blueprintToolFieldSchema: () => ({ schema: { type: 'string' } }),
        parsePresentedValue: (_field, value) => value,
    };
    vm.runInNewContext(
        fs.readFileSync(path.resolve(__dirname, '../../../deployments/advertising/static/js/chat-blueprint-editor.js'), 'utf8'),
        context,
    );
    for (const name of ['renderBlueprintList', 'renderBlueprintEditor', 'showBlueprintNotice']) {
        context[name] = () => {};
    }
    context.evaluateBlueprintDraft = changedPath => evaluated.push(changedPath);
    return { context, evaluated };
}

test('applying a complete template does not trigger a selector-change cascade', () => {
    const { context, evaluated } = environment();
    context.selectBlueprint('example.complete', null, {
        template_id: 'preset', account_id: 'test-account',
        values: {
            'campaign.objective': 'TRAFFIC',
            'ad_set.optimization_goal': 'LANDING_PAGE_VIEWS',
            'ad_set.billing_event': 'IMPRESSIONS',
        },
    });
    assert.deepEqual(evaluated, [null]);
    assert.equal(context.blueprintState.values['ad_set.optimization_goal'], 'LANDING_PAGE_VIEWS');
    assert.equal(context.blueprintState.values['ad_set.billing_event'], 'IMPRESSIONS');
});

test('initializing an untemplated blueprint also evaluates without a synthetic edit', () => {
    const { context, evaluated } = environment();
    let notice='old template notice';
    context.showBlueprintNotice=value=>{notice=value};
    context.selectBlueprint('example.complete');
    assert.deepEqual(evaluated, [null]);
    assert.equal(context.blueprintState.values['campaign.objective'], 'TRAFFIC');
    assert.equal(notice,'');
});

test('an actual selector edit still evaluates the changed path and previous values', async () => {
    const { context, evaluated } = environment();
    context.blueprintState.values = { 'campaign.objective': 'TRAFFIC' };
    await context.updateBlueprintField({ path: 'campaign.objective', tool_ref: 'create.objective' }, 'SALES');
    assert.deepEqual(evaluated, ['campaign.objective']);
    assert.equal(context.blueprintState.previousValues['campaign.objective'], 'TRAFFIC');
    assert.equal(context.blueprintState.values['campaign.objective'], 'SALES');
});


test('wizard submission omits evaluated hidden fields and their selection proofs', () => {
    const { context } = environment();
    const fields = [
        { path: 'campaign.name', tool_ref: 'example_create.name' },
        { path: 'campaign.brand_guidelines_enabled', tool_ref: 'example_create.brand_guidelines_enabled' },
        { path: 'campaign.asset_id', tool_ref: 'example_create.asset_id' },
    ];
    context.blueprintState.values = {
        'campaign.name': 'Paused QA', 'campaign.brand_guidelines_enabled': false,
        'campaign.asset_id': 'hidden-asset',
    };
    context.blueprintState.evaluation = { fields: [
        { path: 'campaign.name', visible: true },
        { path: 'campaign.brand_guidelines_enabled', visible: false },
        { path: 'campaign.asset_id', visible: false },
    ] };
    context.blueprintState.selectionTokens = { asset_id: 'hidden-proof' };
    context.blueprintState.selectionTokenTools = { asset_id: 'example_create' };
    context.blueprintOptions = () => [];
    context.blueprintFieldDefault = () => undefined;
    context.blueprintToolFieldSchema = ref => ({
        toolName: ref.split('.')[0], fieldPath: ref.split('.').slice(1).join('.'),
    });
    context.setCreationNestedValue = (target, field, value) => { target[field] = value; };
    const params = context.blueprintDraftPlatformParams({ provider: 'example', fields }).example;
    assert.equal(params.name, 'Paused QA');
    assert.equal(params.brand_guidelines_enabled, undefined);
    assert.equal(params.asset_id, undefined);
    assert.equal(params.example_create.selection_tokens, undefined);
});
