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
    context.authenticatedFetch = async () => ({
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
