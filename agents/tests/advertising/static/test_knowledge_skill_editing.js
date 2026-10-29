const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function editor() {
    const nodes = new Map();
    const context = {console, URLSearchParams, TextDecoder, Uint8Array, atob,
        window: {clearTimeout() {}},
        knowledgeState: {items: [], managedItems: []},
        skillState: {files: [], versions: []},
        document: {getElementById(id) {
            if (!nodes.has(id)) nodes.set(id, {value: '', hidden: false, disabled: false,
                focus() {}, setAttribute() {}, toggleAttribute(name, value) { this[name] = value; },
                classList: {add() {}, remove() {}, toggle() {}}, options: [{value: 'all'}, {value: 'meta'}]});
            return nodes.get(id);
        }},
    };
    vm.createContext(context);
    for (const name of ['chat-resource-catalogs.js', 'chat-knowledge.js', 'chat-skills.js', 'chat-management-catalogs.js']) {
        vm.runInContext(fs.readFileSync(path.resolve(__dirname, '../../../deployments/advertising/static/js', name), 'utf8'), context);
    }
    for (const name of ['setResourceView', 'trackResourceDraft', 'renderSkillList', 'renderSkillFiles',
        'renderSkillEvaluation', 'loadManagedKnowledgeDocuments', 'loadKnowledgeCatalog', 'showResourceList']) context[name] = () => {};
    context.renderResourceCatalog = (kind, rows) => { context[kind + 'Rows'] = rows; };
    return {context, nodes};
}

test('builtin knowledge and Skills both expose an explicit edit action', () => {
    const {context} = editor();
    context.knowledgeState.items = [{document_id: 'guide', title: '指南'}];
    context.skillState.versions = [{skill_name: 'growth', version: '1.0.0', source: 'builtin'}];
    context.renderKnowledgeCatalogTable();
    context.renderSkillsCatalogTable();
    assert.ok(context.knowledgeRows[0].actions.some(action => action.label === '编辑'));
    assert.ok(context.skillsRows[0].actions.some(action => action.label === '编辑'));
});

test('builtin knowledge edit loads the complete document and preserves its origin on save', async () => {
    const {context, nodes} = editor();
    const calls = [];
    context.apiFetch = async (url, options) => {
        calls.push({url, options});
        if (!options) return {document_id: 'guide', title: '指南', content: '# 完整正文\n\n第二节',
            version: '1.0.0', platform: 'meta', layer: 'experience', confidence: 0.95,
            source_ref: 'https://example.com', wikilinks: ['[[参考]]']};
        return {document_id: 'saved', ...JSON.parse(options.body)};
    };
    await context.editBuiltinKnowledgeDocument({document_id: 'guide', excerpt: '检索片段'});
    assert.equal(nodes.get('knowledgeContent').value, '# 完整正文\n\n第二节');
    assert.equal(nodes.get('knowledgeTitle').value, '指南');
    nodes.get('knowledgeContent').value += '\n修改';
    await context.saveKnowledgeDocument(false);
    const body = JSON.parse(calls[1].options.body);
    assert.equal(calls[1].options.method, 'POST');
    assert.equal(body.derived_from, 'builtin:guide');
    assert.equal(body.layer, 'experience');
    assert.equal(body.confidence, 0.95);
    assert.equal(body.source_ref, 'https://example.com');
    assert.deepEqual(body.wikilinks, ['[[参考]]']);
    assert.equal(body.version, '1.0.1');
});

test('published knowledge suggests a new version and retains metadata through draft restoration', async () => {
    const {context, nodes} = editor();
    context.apiFetch = async () => ({document_id: 'managed-id', title: '指南', content: '内容',
        status: 'published', version: '1.2.3', derived_from: 'builtin:guide', layer: 'experience'});
    await context.editKnowledgeDocument('managed-id');
    assert.equal(nodes.get('knowledgeVersion').value, '1.2.4');
    const saved = context.captureResourceDraft('knowledge');
    context.resetKnowledgeEditor();
    context.restoreResourceDraft('knowledge', saved);
    assert.equal(context.knowledgeState.editorMetadata.derived_from, 'builtin:guide');
    assert.equal(context.knowledgeState.editingDocumentId, 'managed-id');
});

test('Skill publish and unpublish keep their result visible after refreshing the version', async () => {
    const {context, nodes} = editor();
    context.window.confirm = () => true;
    context.skillState.selected = {skillName: 'growth', version: '1.0.1'};
    context.skillState.detail = {status: 'published'};
    const calls = [];
    context.apiFetch = async (url) => { calls.push(url); return {}; };
    context.loadManagedSkills = async () => context.clearSkillNotice();
    await context.publishSelectedSkill();
    assert.match(nodes.get('skillNotice').textContent, /已发布 growth@1.0.1/);
    await context.unpublishSelectedSkill();
    assert.match(nodes.get('skillNotice').textContent, /已下线 growth@1.0.1/);
    assert.deepEqual(calls, ['/skills/growth/versions/1.0.1/publish', '/skills/growth/versions/1.0.1/unpublish']);
});

test('Skill edit keeps every file, suggests a free version, and failed save keeps edits', async () => {
    const {context, nodes} = editor();
    context.skillState.versions = [{skill_name: 'growth', version: '1.0.1'}];
    context.apiFetch = async () => ({source: 'builtin', files: {'SKILL.md': '# 指导',
        'references/guide.md': '参考', 'assets/data.bin': {encoding: 'base64', content: 'AA=='}}});
    await context.openSkillCatalogEntry({skill_name: 'growth', version: '1.0.0', source: 'builtin'}, true);
    assert.equal(nodes.get('skillVersionInput').value, '1.0.2');
    assert.equal(nodes.get('skillSaveButton').disabled, false);
    assert.equal(context.skillState.files.length, 3);
    context.skillState.files[0].content = '# 修改后的指导';
    let sent;
    context.apiFetch = async (_url, options) => { sent = JSON.parse(options.body); throw new Error('保存暂时失败'); };
    await context.saveSkillDraft();
    assert.equal(sent.files['SKILL.md'], '# 修改后的指导');
    assert.deepEqual(sent.files['assets/data.bin'], {encoding: 'base64', content: 'AA=='});
    assert.equal(context.skillState.files[0].content, '# 修改后的指导');
    assert.equal(nodes.get('skillSaveButton').disabled, false);
    assert.match(nodes.get('skillNotice').textContent, /保存暂时失败/);
});
