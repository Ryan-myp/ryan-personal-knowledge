const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function deferred() {
    let resolve, reject;
    const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
    return {promise, resolve, reject};
}

function environment() {
    const nodes = new Map();
    const node = id => {
        if (!nodes.has(id)) nodes.set(id, {
            value: '', textContent: '', disabled: false, hidden: false, dataset: {},
            classList: {add() {}, remove() {}, toggle() {}},
            listeners: {}, addEventListener(event, callback) { this.listeners[event] = callback; },
            setAttribute() {}, toggleAttribute(name, value) { this[name] = value; }, focus() {},
        });
        return nodes.get(id);
    };
    const context = {
        console, TextDecoder, Uint8Array, atob,
        document: {getElementById: node, querySelector: node, querySelectorAll: () => []},
        window: {clearTimeout() {}}, skillState: {files: [], versions: []},
        apiFetch: async () => { throw new Error('Unexpected request'); },
    };
    vm.createContext(context);
    for (const file of ['chat-resource-catalogs.js', 'chat-catalog-loading.js', 'chat-skills.js',
        'chat-mcp.js', 'chat-management-catalogs.js']) {
        vm.runInContext(fs.readFileSync(path.resolve(__dirname,
            '../../../deployments/advertising/static/js', file), 'utf8'), context);
    }
    // Keep real navigation, draft capture, save and reload logic; omit only DOM rendering.
    for (const name of ['renderResourceCatalog', 'renderSkillList', 'renderSkillFiles',
        'renderMCPServerList', 'renderMCPTools', 'renderMCPValidation']) {
        context[name] = () => {};
    }
    const catalogs = vm.runInContext('resourceCatalogs', context);
    const mcp = vm.runInContext('mcpState', context);
    return {context, node, catalogs, mcp};
}

function mcpDraft(env, name) {
    env.context.newMCPServer();
    env.node('mcpNameInput').value = name;
    env.node('mcpEndpointInput').value = 'https://example.invalid/mcp';
}

function mcpRequests(env, pending = null) {
    const writes = [];
    let saved;
    env.context.apiFetch = async (url, options) => {
        if (!options) return {servers: saved ? [saved] : []};
        writes.push({url, method: options.method, body: JSON.parse(options.body)});
        saved = {server_id: 'saved-server', status: 'draft', tools: [], ...writes.at(-1).body};
        if (writes.length === 1 && pending) await pending.promise;
        return saved;
    };
    return writes;
}

function skillRequests(env, pending = null) {
    const writes = [];
    let saved;
    env.context.apiFetch = async (url, options) => {
        if (!options) return url.startsWith('/skills?')
            ? {managed_skills: saved ? [saved] : []}
            : {...saved, files: writes.at(-1).body.files};
        const body = JSON.parse(options.body);
        writes.push({url, body});
        saved = {skill_name: 'new-skill', version: body.version, sha256: 'fixture',
            status: 'draft', source: 'managed', files: Object.keys(body.files)};
        if (writes.length === 1 && pending) await pending.promise;
        return saved;
    };
    return writes;
}

test('MCP save completion cannot replace a newer draft or clear its dirty state', async () => {
    const env = environment(), pending = deferred();
    mcpRequests(env, pending);
    mcpDraft(env, 'A');
    const saving = env.context.saveMCPServer();
    mcpDraft(env, 'B');
    pending.resolve();
    await saving;
    assert.equal(env.node('mcpNameInput').value, 'B');
    assert.equal(env.mcp.selectedId, '');
    assert.equal(env.catalogs.mcp.view, 'edit');
    assert.equal(env.catalogs.mcp.hasDraft, true);
});

test('an obsolete MCP save failure does not report an error on the newer draft', async () => {
    const env = environment(), pending = deferred();
    mcpRequests(env, pending);
    mcpDraft(env, 'A');
    const saving = env.context.saveMCPServer();
    mcpDraft(env, 'B');
    env.node('mcpNotice').textContent = 'B is being edited';
    pending.reject(new Error('A save failed'));
    await saving;
    assert.equal(env.node('mcpNotice').textContent, 'B is being edited');
    assert.equal(env.node('mcpNameInput').value, 'B');
});

test('MCP keeps in-flight edits and updates the saved server on the next save', async () => {
    const env = environment(), pending = deferred();
    const writes = mcpRequests(env, pending);
    mcpDraft(env, 'Original');
    const saving = env.context.saveMCPServer();
    env.node('mcpDescriptionInput').value = 'New unsaved description';
    env.node('#mcpServerForm').listeners.input();
    pending.resolve();
    await saving;
    assert.equal(writes[0].body.description, '');
    assert.equal(env.node('mcpDescriptionInput').value, 'New unsaved description');
    assert.equal(env.catalogs.mcp.hasDraft, true);
    assert.equal(env.catalogs.mcp.view, 'edit');
    assert.equal(env.mcp.selectedId, 'saved-server');
    assert.match(env.node('mcpNotice').textContent, /已保存.*快照.*未保存/);
    await env.context.saveMCPServer();
    assert.equal(writes[1].method, 'PATCH');
    assert.equal(writes[1].url, '/mcp/servers/saved-server');
    assert.equal(writes[1].body.description, 'New unsaved description');
    assert.equal(env.catalogs.mcp.hasDraft, false);
});

test('MCP repeated save clicks send only one write and show the saved detail', async () => {
    const env = environment(), pending = deferred();
    const writes = mcpRequests(env, pending);
    mcpDraft(env, 'Original');
    const saving = env.context.saveMCPServer();
    await env.context.saveMCPServer();
    pending.resolve();
    await saving;
    assert.equal(writes.length, 1);
    assert.equal(env.catalogs.mcp.view, 'detail');
    assert.equal(env.catalogs.mcp.hasDraft, false);
    assert.equal(env.node('mcpSaveButton').disabled, false);
    assert.match(env.node('mcpNotice').textContent, /已保存/);
});

test('MCP failed save retains editable fields and allows retry', async () => {
    const env = environment(), pending = deferred();
    const writes = mcpRequests(env, pending);
    mcpDraft(env, 'Retry');
    const saving = env.context.saveMCPServer();
    pending.reject(new Error('offline'));
    await saving;
    assert.equal(env.node('mcpNameInput').value, 'Retry');
    assert.equal(env.mcp.selectedId, '');
    assert.equal(env.catalogs.mcp.hasDraft, true);
    assert.equal(env.node('mcpSaveButton').disabled, false);
    assert.match(env.node('mcpNotice').textContent, /offline/);
    await env.context.saveMCPServer();
    assert.equal(writes[1].method, 'POST');
    assert.equal(env.catalogs.mcp.hasDraft, false);
});

test('Skill keeps in-flight edits, stays dirty and retries with an unused version', async () => {
    const env = environment(), pending = deferred();
    const writes = skillRequests(env, pending);
    env.context.newSkillDraft();
    env.context.skillState.versions = [{skill_name: 'new-skill', version: '1.0.1'}];
    const saving = env.context.saveSkillDraft();
    env.context.skillState.files[0].content += '\nNew unsaved rule.\n';
    env.node('.skill-editor').listeners.input();
    pending.resolve();
    await saving;
    assert.doesNotMatch(writes[0].body.files['SKILL.md'], /New unsaved rule/);
    assert.match(env.context.skillState.files[0].content, /New unsaved rule/);
    assert.equal(env.catalogs.skills.hasDraft, true);
    assert.equal(env.catalogs.skills.view, 'edit');
    assert.equal(env.node('skillSaveButton').disabled, false);
    assert.equal(env.node('skillVersionInput').value, '1.0.2');
    assert.match(env.node('skillNotice').textContent, /已保存.*快照.*未保存/);
    await env.context.saveSkillDraft();
    assert.equal(writes[1].body.version, '1.0.2');
    assert.match(writes[1].body.files['SKILL.md'], /New unsaved rule/);
    assert.equal(env.catalogs.skills.hasDraft, false);
});

test('Skill preserves newly added invalid file paths instead of losing edits after a successful write', async () => {
    const env = environment(), pending = deferred();
    skillRequests(env, pending);
    env.context.newSkillDraft();
    const saving = env.context.saveSkillDraft();
    env.context.skillState.files.push({path: '', encoding: 'utf-8', content: 'Unfinished file'});
    pending.resolve();
    await saving;
    assert.equal(env.context.skillState.files.at(-1).content, 'Unfinished file');
    assert.equal(env.catalogs.skills.hasDraft, true);
    assert.equal(env.node('skillVersionInput').value, '1.0.1');
    assert.match(env.node('skillNotice').textContent, /已保存.*快照.*未保存/);
});

test('Skill preserves a version manually chosen while saving', async () => {
    const env = environment(), pending = deferred();
    skillRequests(env, pending);
    env.context.newSkillDraft();
    const saving = env.context.saveSkillDraft();
    env.node('skillVersionInput').value = '2.0.0';
    pending.resolve();
    await saving;
    assert.equal(env.node('skillVersionInput').value, '2.0.0');
    assert.equal(env.catalogs.skills.hasDraft, true);
});

test('Skill unchanged save shows the saved version and retains binary assets', async () => {
    const env = environment();
    skillRequests(env);
    env.context.newSkillDraft();
    env.context.skillState.files.push({path: 'assets/data.bin', encoding: 'base64', content: 'AP+A'});
    await env.context.saveSkillDraft();
    assert.equal(env.catalogs.skills.view, 'detail');
    assert.equal(env.catalogs.skills.hasDraft, false);
    assert.equal(env.context.skillState.selected.version, '1.0.0');
    assert.equal(env.context.collectSkillFiles()['assets/data.bin'].content, 'AP+A');
    assert.equal(env.node('skillPublishButton').disabled, false);
    assert.match(env.node('skillNotice').textContent, /已保存/);
});

test('Skill failed save keeps newer edits and the original version for retry', async () => {
    const env = environment(), pending = deferred();
    const writes = skillRequests(env, pending);
    env.context.newSkillDraft();
    const saving = env.context.saveSkillDraft();
    env.context.skillState.files[0].content += '\nKeep after failure.\n';
    pending.reject(new Error('offline'));
    await saving;
    assert.match(env.context.skillState.files[0].content, /Keep after failure/);
    assert.equal(env.node('skillVersionInput').value, '1.0.0');
    assert.equal(env.catalogs.skills.hasDraft, true);
    assert.equal(env.node('skillSaveButton').disabled, false);
    assert.match(env.node('skillNotice').textContent, /offline/);
    await env.context.saveSkillDraft();
    assert.equal(writes[1].body.version, '1.0.0');
});

test('Skill save completion leaves a replacement draft and its notice alone', async () => {
    const env = environment(), pending = deferred();
    skillRequests(env, pending);
    env.context.newSkillDraft();
    const saving = env.context.saveSkillDraft();
    env.context.newSkillDraft();
    env.context.skillState.files[0].content += '\nReplacement draft.\n';
    env.node('skillNotice').textContent = 'Replacement notice';
    pending.resolve();
    await saving;
    assert.match(env.context.skillState.files[0].content, /Replacement draft/);
    assert.equal(env.node('skillNotice').textContent, 'Replacement notice');
    assert.equal(env.catalogs.skills.hasDraft, true);
    assert.equal(env.node('skillVersionInput').value, '1.0.0');
});
