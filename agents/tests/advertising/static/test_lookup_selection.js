const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const sourcePath = path.resolve(
    __dirname,
    '../../../deployments/advertising/static/js/chat-blueprint-core.js',
);
const context = {};
vm.runInNewContext(fs.readFileSync(sourcePath, 'utf8'), context, {
    filename: sourcePath,
});

class ElementMock {
    constructor(tagName) {
        this.tagName = tagName.toUpperCase();
        this.children = [];
        this.dataset = {};
        this.attributes = {};
        this.listeners = {};
        this.className = '';
        this.textContent = '';
        this.value = '';
        this.disabled = false;
    }

    append(...nodes) {
        this.children.push(...nodes);
    }

    appendChild(node) {
        this.children.push(node);
        return node;
    }

    replaceChildren(...nodes) {
        this.children = [...nodes];
    }

    addEventListener(name, callback) {
        this.listeners[name] = callback;
    }

    setAttribute(name, value) {
        this.attributes[name] = value;
    }

    matches(selector) {
        return selector.startsWith('.') && this.className.split(/\s+/).includes(selector.slice(1));
    }

    closest() {
        return null;
    }

    querySelector(selector) {
        return this.querySelectorAll(selector)[0] || null;
    }

    querySelectorAll(selector) {
        const className = selector.match(/^\.([a-z-]+)/)?.[1];
        if (!className) return [];
        const matches = [];
        const visit = node => {
            if (node.matches?.(`.${className}`)) matches.push(node);
            node.children.forEach(visit);
        };
        this.children.forEach(visit);
        return matches;
    }
}

function installLookupEnvironment(options) {
    context.document = {
        createElement: tagName => new ElementMock(tagName),
        getElementById: () => null,
    };
    context.URLSearchParams = URLSearchParams;
    context.crypto = { randomUUID: () => 'lookup-session' };
    context.sessionId = '';
    context.lookupRequests = [];
    context.serviceFetch = async () => ({
        ok: true,
        status: 200,
        text: async () => JSON.stringify({ options }),
    });
}

test('exact lookup match refreshes the current token', () => {
    const result = context.reconcileLookupSelection(
        'resource-1',
        [{ value: 'resource-1', selection_token: 'fresh-token' }],
        false,
    );

    assert.deepEqual(JSON.parse(JSON.stringify(result)), {
        tokens: ['fresh-token'],
        matchedCount: 1,
        unresolvedCount: 0,
    });
});

test('a missing lookup match remains unverified', () => {
    const result = context.reconcileLookupSelection(
        'stale-resource',
        [{ value: 'current-resource', selection_token: 'fresh-token' }],
        false,
    );

    assert.deepEqual(JSON.parse(JSON.stringify(result)), {
        tokens: [''],
        matchedCount: 0,
        unresolvedCount: 1,
    });
});

test('multi-select reconciliation preserves token positions for partial matches', () => {
    const result = context.reconcileLookupSelection(
        ['resource-1', 'stale-resource'],
        [{ value: 'resource-1', selection_token: 'fresh-token' }],
        true,
    );

    assert.deepEqual(JSON.parse(JSON.stringify(result)), {
        tokens: ['fresh-token', ''],
        matchedCount: 1,
        unresolvedCount: 1,
    });
});

test('an exact option without a fresh token is not treated as verified', () => {
    const result = context.reconcileLookupSelection(
        'resource-1',
        [{ value: 'resource-1' }],
        false,
    );

    assert.deepEqual(JSON.parse(JSON.stringify(result)), {
        tokens: [''],
        matchedCount: 0,
        unresolvedCount: 1,
    });
});

test('duplicate exact options are ambiguous and do not issue a token', () => {
    const result = context.reconcileLookupSelection(
        'resource-1',
        [
            { value: 'resource-1', selection_token: 'token-a' },
            { value: 'resource-1', selection_token: 'token-b' },
        ],
        false,
    );

    assert.deepEqual(JSON.parse(JSON.stringify(result)), {
        tokens: [''],
        matchedCount: 0,
        unresolvedCount: 1,
    });
});

test('multi-select matching is independent of object key order', () => {
    const result = context.reconcileLookupSelection(
        [{ id: 'resource-1', kind: 'page' }],
        [{ value: { kind: 'page', id: 'resource-1' }, selection_token: 'fresh-token' }],
        true,
    );

    assert.deepEqual(JSON.parse(JSON.stringify(result)), {
        tokens: ['fresh-token'],
        matchedCount: 1,
        unresolvedCount: 0,
    });
});

test('lookup query refreshes a prefilled value through its selection callback', async () => {
    installLookupEnvironment([
        { value: 'resource-1', label: 'Current resource', selection_token: 'fresh-token' },
    ]);
    const selectionTokens = {};
    let selected;
    const picker = context.renderLookupPicker({
        value: 'resource-1',
        path: 'asset_id',
        lookup: { tool: 'list_assets' },
    }, {
        platform: 'meta',
        accountId: 'act_test',
        fieldName: 'asset_id',
        targetToolName: 'create_ad',
        selectionTokens,
        onSelection: value => { selected = value; },
    });

    await picker.querySelector('.lookup-picker-search').listeners.click();

    assert.ok(selected, picker.querySelector('.lookup-picker-status').textContent);
    assert.equal(selected.value, 'resource-1');
    assert.equal(selected.tokens, 'fresh-token');
    assert.equal(selectionTokens.asset_id, 'fresh-token');
});

test('lookup query does not authorize a prefilled value missing from current results', async () => {
    installLookupEnvironment([
        { value: 'current-resource', label: 'Current resource', selection_token: 'fresh-token' },
    ]);
    const selectionTokens = {};
    let selected;
    const picker = context.renderLookupPicker({
        value: 'stale-resource',
        path: 'asset_id',
        lookup: { tool: 'list_assets' },
    }, {
        platform: 'meta',
        accountId: 'act_test',
        fieldName: 'asset_id',
        targetToolName: 'create_ad',
        selectionTokens,
        onSelection: value => { selected = value; },
    });

    await picker.querySelector('.lookup-picker-search').listeners.click();

    assert.ok(selected, picker.querySelector('.lookup-picker-status').textContent);
    assert.equal(selected.value, 'stale-resource');
    assert.equal(selected.tokens, undefined);
    assert.equal(selectionTokens.asset_id, undefined);
    assert.match(picker.querySelector('.lookup-picker-status').textContent, /未匹配/);
});

test('template-prefilled asset selection resolves automatically by its exact ID', async () => {
    installLookupEnvironment([]);
    context.serviceFetch = async url => {
        context.lookupRequests.push(String(url));
        return {
            ok: true,
            status: 200,
            text: async () => JSON.stringify({
                options: [{
                    value: 'customers/9055507554/assets/7',
                    label: 'Current image',
                    selection_token: 'fresh-template-token',
                }],
            }),
        };
    };
    const selectionTokens = {};
    let selected;
    context.renderLookupPicker({
        value: ['customers/9055507554/assets/7'],
        lookup_multiple: true,
        lookup: {
            tool: 'google_list_assets',
            query_field: 'asset_id',
        },
    }, {
        platform: 'google-ads',
        accountId: '9055507554',
        fieldName: 'images',
        targetToolName: 'google_create_ad',
        selectionTokens,
        autoResolvePrefill: true,
        onSelection: value => { selected = value; },
    });
    await new Promise(resolve => setImmediate(resolve));

    assert.equal(context.lookupRequests.length, 1);
    const requested = new URL(context.lookupRequests[0], 'http://localhost');
    assert.equal(requested.searchParams.get('query'), '7');
    assert.deepEqual(JSON.parse(JSON.stringify(selectionTokens.images)), [
        'fresh-template-token',
    ]);
    assert.deepEqual(JSON.parse(JSON.stringify(selected.value)), [
        'customers/9055507554/assets/7',
    ]);
});

test('template-prefilled asset selection stays unresolved when lookup misses', async () => {
    installLookupEnvironment([]);
    const selectionTokens = {};
    let selected;
    const picker = context.renderLookupPicker({
        value: ['customers/9055507554/assets/404'],
        lookup_multiple: true,
        lookup: {
            tool: 'google_list_assets',
            query_field: 'asset_id',
        },
    }, {
        platform: 'google-ads',
        accountId: '9055507554',
        fieldName: 'images',
        targetToolName: 'google_create_ad',
        selectionTokens,
        autoResolvePrefill: true,
        onSelection: value => { selected = value; },
    });
    await new Promise(resolve => setImmediate(resolve));

    assert.equal(selectionTokens.images, undefined);
    assert.equal(selected.tokens, undefined);
    assert.deepEqual(JSON.parse(JSON.stringify(selected.value)), [
        'customers/9055507554/assets/404',
    ]);
    assert.match(picker.querySelector('.lookup-picker-status').textContent, /未匹配/);
});

test('template-prefilled selection refreshes a token when lookup has no query field', async () => {
    installLookupEnvironment([]);
    context.serviceFetch = async url => {
        context.lookupRequests.push(String(url));
        return {
            ok: true,
            status: 200,
            text: async () => JSON.stringify({
                options: [{
                    value: 'video-42',
                    label: 'Current video',
                    selection_token: 'fresh-video-token',
                }],
            }),
        };
    };
    const selectionTokens = {};
    let selected;
    context.renderLookupPicker({
        value: 'video-42',
        lookup: { tool: 'tiktok_list_videos' },
    }, {
        platform: 'tiktok',
        accountId: 'advertiser-test',
        fieldName: 'video_id',
        targetToolName: 'tiktok_smart_plus_create_ad',
        selectionTokens,
        autoResolvePrefill: true,
        onSelection: value => { selected = value; },
    });
    await new Promise(resolve => setImmediate(resolve));

    assert.equal(context.lookupRequests.length, 1);
    const requested = new URL(context.lookupRequests[0], 'http://localhost');
    assert.equal(requested.searchParams.get('field'), 'video_id');
    assert.equal(requested.searchParams.has('query'), false);
    assert.equal(selectionTokens.video_id, 'fresh-video-token');
    assert.equal(selected.tokens, 'fresh-video-token');
    assert.equal(selected.value, 'video-42');
});

test('template-prefilled exact lookup sends the selected ID to the lookup query field', async () => {
    installLookupEnvironment([]);
    context.serviceFetch = async url => {
        context.lookupRequests.push(String(url));
        return {
            ok: true,
            status: 200,
            text: async () => JSON.stringify({
                options: [{
                    value: 'video-42',
                    label: 'Current video',
                    selection_token: 'fresh-video-token',
                }],
            }),
        };
    };
    const selectionTokens = {};
    let selected;
    context.renderLookupPicker({
        value: 'video-42',
        lookup: {
            tool: 'tiktok_get_video',
            query_field: 'video_id',
        },
    }, {
        platform: 'tiktok',
        accountId: 'advertiser-test',
        fieldName: 'video_id',
        targetToolName: 'tiktok_smart_plus_create_ad',
        selectionTokens,
        autoResolvePrefill: true,
        onSelection: value => { selected = value; },
    });
    await new Promise(resolve => setImmediate(resolve));

    assert.equal(context.lookupRequests.length, 1);
    const requested = new URL(context.lookupRequests[0], 'http://localhost');
    assert.equal(
        requested.searchParams.get('tool_name'),
        'tiktok_smart_plus_create_ad',
    );
    assert.equal(requested.searchParams.get('query'), 'video-42');
    assert.equal(selectionTokens.video_id, 'fresh-video-token');
    assert.equal(selected.value, 'video-42');
});

test('template-prefilled asset-picker video resolves by exact ID before submission', async () => {
    installLookupEnvironment([]);
    context.serviceFetch = async url => {
        context.lookupRequests.push(String(url));
        return {
            ok: true,
            status: 200,
            text: async () => JSON.stringify({
                options: [{
                    value: 'video-42',
                    label: 'Current video',
                    selection_token: 'fresh-video-token',
                }],
            }),
        };
    };
    const selectionTokens = {};
    let selected;
    context.renderLookupPicker({
        control: 'asset_picker',
        source: 'lookup',
        value: 'video-42',
        lookup: {
            tool: 'tiktok_get_video',
            query_field: 'video_id',
        },
    }, {
        platform: 'tiktok',
        accountId: 'advertiser-test',
        fieldName: 'video_id',
        targetToolName: 'tiktok_smart_plus_create_ad',
        selectionTokens,
        autoResolvePrefill: true,
        onSelection: value => { selected = value; },
    });
    await new Promise(resolve => setImmediate(resolve));

    assert.equal(context.lookupRequests.length, 1);
    const requested = new URL(context.lookupRequests[0], 'http://localhost');
    assert.equal(requested.searchParams.get('field'), 'video_id');
    assert.equal(requested.searchParams.get('query'), 'video-42');
    assert.equal(selectionTokens.video_id, 'fresh-video-token');
    assert.equal(selected.tokens, 'fresh-video-token');
    assert.equal(selected.value, 'video-42');
});

test('template-prefilled selection without query field stays unverified when lookup misses', async () => {
    installLookupEnvironment([]);
    context.serviceFetch = async url => {
        context.lookupRequests.push(String(url));
        return {
            ok: true,
            status: 200,
            text: async () => JSON.stringify({
                options: [{
                    value: 'different-video',
                    label: 'Different video',
                    selection_token: 'fresh-video-token',
                }],
            }),
        };
    };
    const selectionTokens = {};
    let selected;
    const picker = context.renderLookupPicker({
        value: 'video-42',
        lookup: { tool: 'tiktok_list_videos' },
    }, {
        platform: 'tiktok',
        accountId: 'advertiser-test',
        fieldName: 'video_id',
        targetToolName: 'tiktok_smart_plus_create_ad',
        selectionTokens,
        autoResolvePrefill: true,
        onSelection: value => { selected = value; },
    });
    await new Promise(resolve => setImmediate(resolve));

    assert.equal(context.lookupRequests.length, 1);
    assert.equal(selectionTokens.video_id, undefined);
    assert.equal(selected.tokens, undefined);
    assert.match(picker.querySelector('.lookup-picker-status').textContent, /未匹配/);
});

test('an unchanged empty prefill result does not restart lookup after a rerender', async () => {
    installLookupEnvironment([]);
    const optionsStore = {};
    let queries = 0;
    let change;
    context.serviceFetch = async () => {
        queries += 1;
        return { ok: true, text: async () => JSON.stringify({ options: [] }) };
    };
    const field = { value: 'asset-1', lookup: { tool: 'list_assets' } };
    const settings = {
        platform: 'example', accountId: 'test-account',
        fieldName: 'asset_id', targetToolName: 'create_ad',
        optionsStore, selectionTokens: {}, autoResolvePrefill: true,
        onSelection: selection => { change = selection.changed; },
    };
    context.renderLookupPicker(field, settings);
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(change, false);
    const rerendered = context.renderLookupPicker(field, settings);
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(queries, 1);
    await rerendered.querySelector('.lookup-picker-search').listeners.click();
    assert.equal(queries, 2, 'manual retry remains available');
    context.renderLookupPicker(field, { ...settings, accountId: 'another-account' });
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(queries, 3, 'a different account requires a new lookup');
});

test('a changed declared dependency permits another prefill lookup', async () => {
    installLookupEnvironment([]);
    const optionsStore = {};
    let queries = 0;
    let catalog = 'catalog-1';
    context.serviceFetch = async () => {
        queries += 1;
        return { ok: true, text: async () => JSON.stringify({ options: [] }) };
    };
    const field = {
        value: 'product-set', lookup: {
            tool: 'list_sets', dependencies: [{ input_field: 'catalog_id', value_path: 'catalog_id' }],
        },
    };
    const settings = {
        platform: 'example', accountId: 'test-account',
        fieldName: 'set_id', targetToolName: 'create_ad',
        optionsStore, autoResolvePrefill: true,
        getLookupContext: () => ({ catalog_id: catalog }),
    };
    context.renderLookupPicker(field, settings);
    await new Promise(resolve => setImmediate(resolve));
    catalog = 'catalog-2';
    context.renderLookupPicker(field, settings);
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(queries, 2);
});
