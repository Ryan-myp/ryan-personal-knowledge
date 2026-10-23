const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function setup(fetchHandler) {
    const calls = [];
    const context = {
        document: { getElementById: () => null },
        Headers,
        fetch: async (url, options = {}) => {
            calls.push({ url, headers: new Headers(options.headers) });
            return fetchHandler(url, options);
        },
        console,
        Promise,
        pendingBlueprintRequest: null,
        pendingBlueprintContinuation: null,
    };
    const source = path.resolve(
        __dirname,
        '../../../deployments/advertising/static/js/chat-requests.js',
    );
    vm.runInNewContext(fs.readFileSync(source, 'utf8'), context, { filename: source });
    return { context, calls };
}

test('service requests do not require or send a browser service key', async () => {
    const { context, calls } = setup(async () => ({ status: 200, ok: true }));

    const response = await context.serviceFetch('/sessions', {
        headers: { 'X-API-Key': 'stale-browser-key', Accept: 'application/json' },
    });

    assert.equal(response.status, 200);
    assert.equal(calls.length, 1);
    assert.equal(calls[0].headers.get('X-API-Key'), null);
    assert.equal(calls[0].headers.get('Accept'), 'application/json');
});

test('an authorization response is returned without prompting for a key or retrying', async () => {
    const { context, calls } = setup(async () => ({ status: 401, ok: false }));

    const response = await context.serviceFetch('/sessions');

    assert.equal(response.status, 401);
    assert.equal(calls.length, 1);
});
