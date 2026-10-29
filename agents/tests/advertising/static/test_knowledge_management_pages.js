const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function environment() {
    const nodes = new Map();
    class Element {
        constructor() { this.value = ''; this.dataset = {}; this.children = []; this.classList = {toggle() {}, add() {}, remove() {}}; }
        set id(value) { this._id = value; nodes.set(value, this); }
        get id() { return this._id; }
        append(...children) { this.children.push(...children); }
        replaceChildren(...children) { this.children = children; }
        add(option) { this.append(option); }
        setAttribute() {}
        focus() {}
        get options() { return this.children; }
    }
    const document = {
        createElement: () => new Element(), querySelector: () => null,
        getElementById(id) { if (!nodes.has(id)) { const node = new Element(); node.id = id; } return nodes.get(id); },
    };
    const context = {console, document, URLSearchParams, window: {}, knowledgeState: {items: [], managedItems: []},
        Option: function(label, value) { return {textContent: label, value}; }};
    vm.createContext(context);
    for (const name of ['chat-resource-catalogs.js', 'chat-catalog-loading.js', 'chat-knowledge.js', 'chat-management-catalogs.js']) {
        vm.runInContext(fs.readFileSync(path.resolve(__dirname, '../../../deployments/advertising/static/js', name), 'utf8'), context);
    }
    context.state = vm.runInContext('resourceCatalogs.knowledge', context);
    const calls = [];
    context.apiFetch = async url => {
        calls.push(url);
        const params = new URL(url, 'http://offline').searchParams;
        const offset = Number(params.get('offset') || 0), limit = Number(params.get('limit') || 100);
        const q = params.get('q');
        const total = q ? 1 : 125;
        return {documents: Array.from({length: Math.min(limit, Math.max(0, total - offset))}, (_, i) => ({
            document_id: q ? 'old-draft' : `doc-${offset+i}`, title: q ? '命中正文的旧草稿' : `文档 ${offset+i}`,
            status: 'draft', catalog_source: 'managed', knowledge_type: 'workflow',
        })), total, limit, offset, has_more: offset + limit < total, categories: ['workflow', 'general']};
    };
    return {context, nodes, calls};
}

test('server paging reaches old drafts after 100 and never slices the returned page again', async () => {
    const {context, nodes, calls} = environment();
    await context.loadManagedKnowledgeDocuments();
    assert.equal(new URL(calls[0], 'http://offline').searchParams.get('source'), 'all');
    assert.equal(new URL(calls[0], 'http://offline').searchParams.get('limit'), '20');
    for (let i=0; i<6; i++) await nodes.get('knowledgeCatalogNext').onclick();
    assert.equal(new URL(calls.at(-1), 'http://offline').searchParams.get('offset'), '120');
    assert.equal(nodes.get('knowledgeCatalogRows').children.length, 5);
    assert.match(nodes.get('knowledgeCatalogPageInfo').textContent, /125.*7 \/ 7/);
    assert.equal(nodes.get('knowledgeCatalogNext').disabled, true);
    assert.equal(nodes.get('knowledgeCatalogPrevious').disabled, false);
});

test('query and all filters run on the server, reset offset, and preserve body-only hits', async () => {
    const {context, nodes, calls} = environment();
    await context.loadManagedKnowledgeDocuments();
    await nodes.get('knowledgeCatalogNext').onclick();
    nodes.get('knowledgeQuery').value = 'Needle';
    nodes.get('knowledgePlatform').value = 'meta';
    context.state.filters = {category: 'workflow', source: 'managed', status: 'draft'};
    await context.searchKnowledge();
    const params = new URL(calls.at(-1), 'http://offline').searchParams;
    for (const [key,value] of Object.entries({offset:'0', q:'Needle', platform:'meta', category:'workflow', source:'managed', status:'draft'})) {
        assert.equal(params.get(key), value);
    }
    assert.equal(nodes.get('knowledgeCatalogRows').children.length, 1);
    assert.match(nodes.get('knowledgeCatalogPageInfo').textContent, /共 1 条/);
    assert.ok(nodes.get('knowledgeCatalogFilter-category').options.some(option => option.value === 'general'));
    const source = nodes.get('knowledgeCatalogFilter-source');
    source.value = 'builtin';
    await source.onchange();
    assert.equal(new URL(calls.at(-1), 'http://offline').searchParams.get('source'), 'builtin');
    const size = nodes.get('knowledgeCatalogSize'); size.value = '10';
    await size.onchange();
    assert.equal(new URL(calls.at(-1), 'http://offline').searchParams.get('limit'), '10');
});

test('failed navigation retains rows and page metadata, and retry requests the failed offset', async () => {
    const {context, nodes, calls} = environment();
    await context.loadManagedKnowledgeDocuments();
    const rows = nodes.get('knowledgeCatalogRows').children;
    const info = nodes.get('knowledgeCatalogPageInfo').textContent;
    const fetch = context.apiFetch;
    context.apiFetch = async () => { throw new Error('offline'); };
    await nodes.get('knowledgeCatalogNext').onclick();
    assert.equal(nodes.get('knowledgeCatalogRows').children, rows);
    assert.equal(nodes.get('knowledgeCatalogPageInfo').textContent, info);
    assert.match(nodes.get('knowledgeCatalogStatusMessage').textContent, /offline/);
    context.apiFetch = fetch;
    nodes.get('knowledgeCatalogRetry').onclick();
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(new URL(calls.at(-1), 'http://offline').searchParams.get('offset'), '20');
});

test('late old request cannot overwrite a new filter result', async () => {
    const {context, nodes} = environment();
    let completeOld;
    context.apiFetch = () => new Promise(resolve => { completeOld = resolve; });
    const old = context.loadManagedKnowledgeDocuments();
    context.apiFetch = async () => ({documents: [], total: 0, offset: 0, limit: 20, has_more: false, categories: []});
    context.state.filters.source = 'builtin';
    await context.loadManagedKnowledgeDocuments();
    completeOld({documents: [{document_id:'late',title:'late'}], total: 125, offset: 0, limit: 20, has_more: true});
    await old;
    assert.match(nodes.get('knowledgeCatalogPageInfo').textContent, /共 0 条/);
});

test('builtin metadata rows fetch full detail for reading and copying', async () => {
    const {context, nodes} = environment();
    const urls = [];
    context.apiFetch = async url => { urls.push(url); return {document_id:'guide',title:'指南',content:'完整正文',platform:'all'}; };
    context.renderKnowledgeReader = item => { context.read = item; };
    await context.openKnowledgeCatalogEntry({document_id:'guide',catalog_source:'builtin',title:'指南'});
    assert.equal(context.read.excerpt, '完整正文');
    await context.cloneKnowledgeDocument({document_id:'guide',title:'指南'});
    assert.equal(nodes.get('knowledgeContent').value, '完整正文');
    assert.deepEqual(urls, ['/knowledge/builtin/guide', '/knowledge/builtin/guide']);
});

test('a deleted last page refetches the new boundary once and uses server totals', async () => {
    const {context, nodes} = environment();
    await context.loadManagedKnowledgeDocuments();
    context.state.page = 7;
    const offsets = [];
    context.apiFetch = async url => {
        const offset = Number(new URL(url, 'http://offline').searchParams.get('offset'));
        offsets.push(offset);
        return {documents:offset === 120 ? [] : [{document_id:'last',catalog_source:'managed'}],
            total:101, offset, limit:20, has_more:false, categories:[]};
    };
    await context.loadManagedKnowledgeDocuments();
    assert.deepEqual(offsets, [120, 100]);
    assert.match(nodes.get('knowledgeCatalogPageInfo').textContent, /101.*6 \/ 6/);
    assert.equal(nodes.get('knowledgeCatalogRows').children.length, 1);
});

test('existing duplicate open callbacks share one request and summary never replaces inventory', async () => {
    const {context, nodes} = environment();
    let resolve, count = 0;
    context.apiFetch = () => { count++; return new Promise(done => { resolve = done; }); };
    const first = context.loadKnowledgeCatalog(), second = context.loadManagedKnowledgeDocuments();
    assert.equal(count, 1);
    resolve({documents:[],total:0,offset:0,limit:20,has_more:false,categories:[]});
    await Promise.all([first, second]);
    nodes.get('knowledgeQuery').value = 'Needle';
    context.document.getElementById('knowledgeSmartSummary').checked = true;
    context.apiFetch = async url => url.startsWith('/knowledge/search')
        ? {results:[{document_id:'irrelevant-published'}],summary:'总结',summary_mode:'llm'}
        : {documents:[{document_id:'draft',title:'草稿',catalog_source:'managed'}],total:1,offset:0,limit:20,has_more:false,categories:[]};
    await context.searchKnowledge();
    assert.equal(context.knowledgeState.catalogItems[0].document_id, 'managed:draft');
    assert.equal(context.knowledgeState.summary, '总结');
});

test('other resource pagination stays local with no remote callback', () => {
    const {context, nodes} = environment();
    const rows = Array.from({length:25}, (_,i)=>({title:`Skill ${i}`,filters:{},cells:[],actions:[],open(){}}));
    context.renderResourceCatalog('skills',rows,{title:'Skills',columns:['名称'],filters:[]});
    nodes.get('skillsCatalogNext').onclick();
    assert.equal(nodes.get('skillsCatalogRows').children.length, 5);
    assert.match(nodes.get('skillsCatalogPageInfo').textContent, /25.*2 \/ 2/);
});
