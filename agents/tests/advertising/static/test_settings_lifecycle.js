const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function deferred() { let resolve; const promise = new Promise(done => {resolve = done;}); return {promise, resolve}; }
function environment(apiFetch) {
    const elements = new Map();
    const context = {apiFetch, console, document: {
        querySelectorAll: () => [],
        getElementById(id) {
            if (!elements.has(id)) elements.set(id, {value: '', textContent: '', hidden: false,
                dataset: {}, addEventListener() {}, setAttribute() {},
                classList: {add() {}, remove() {}, toggle() {}}});
            return elements.get(id);
        },
    }};
    vm.createContext(context);
    vm.runInContext(fs.readFileSync(path.resolve(__dirname,
        '../../../deployments/advertising/static/js/chat-settings.js'), 'utf8'), context);
    const renders = [];
    context.renderAgentModelProfiles = () => renders.push('models');
    context.renderAgentProviderFields = () => renders.push('providers');
    context.renderWebSearchSettings = () => renders.push('web-search');
    return {context, elements, renders};
}

test('concurrent settings opens share one read and preserve newly typed fields', async () => {
    const pending = deferred(); let calls = 0;
    const {context, renders} = environment(() => {calls++; return pending.promise;});
    const first = context.loadAgentSettings();
    const second = context.loadAgentSettings();
    context.markSettingsDirty('providers');
    pending.resolve({models: {profiles: []}});
    await Promise.all([first,second]);
    assert.equal(calls, 1);
    assert.deepEqual(renders, ['models','web-search']);
});

test('switching tabs does not refill forms or erase pending credential input', () => {
    const {context, renders} = environment(async () => ({}));
    context.selectAgentSettingsTab('providers');
    context.selectAgentSettingsTab('web-search');
    context.selectAgentSettingsTab('models');
    assert.deepEqual(renders, []);
});

test('a read started before saving cannot overwrite the saved snapshot', async () => {
    const pending = deferred();
    const {context} = environment((_url, options = {}) => options.method
        ? Promise.resolve({version:'saved'}) : pending.promise);
    const first = context.loadAgentSettings();
    const saved = await context.settingsRequest('/settings/models', {method:'POST'});
    context.saved = saved;
    vm.runInContext('agentSettingsState.snapshot = saved', context);
    pending.resolve({version:'old'});
    await first;
    assert.equal(vm.runInContext('agentSettingsState.snapshot.version',context),'saved');
});

test('a pending settings write cannot be submitted twice', {timeout:1000}, async () => {
    const pending = deferred(); let calls = 0;
    const {context} = environment(() => {calls++; return pending.promise;});
    const first = context.settingsRequest('/settings/models', {method:'POST'});
    await assert.rejects(context.settingsRequest('/settings/models', {method:'POST'}), /正在保存/);
    pending.resolve({}); await first;
    assert.equal(calls, 1);
});
