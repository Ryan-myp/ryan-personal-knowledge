const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function deferred() {
    let resolve, reject;
    const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
    return { promise, resolve, reject };
}

function environment(file, overrides = {}) {
    const elements = new Map();
    const context = {
        console, URLSearchParams, TextDecoder, Uint8Array, atob, workspaceMode: 'dry_run',
        window: { clearTimeout() {}, setTimeout() {}, confirm: () => true },
        document: { getElementById(id) {
            if (!elements.has(id)) elements.set(id, {
                value: '', textContent: '', disabled: false, hidden: false,
                classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
                setAttribute() {}, removeAttribute() {}, toggleAttribute() {}, focus() {},
            });
            return elements.get(id);
        } },
        skillState: { expanded: new Set(), files: [], versions: [] },
        templateBrowser: {view: 'list', hasDraft: false},
        renderTemplateLibrary() {},
        resourceCatalogs: {knowledge:{filters:{},page:1,limit:20},skills:{},mcp:{}},
        setResourceView() {}, showResourceList() {}, trackResourceDraft() {},
        renderSkillsCatalogTable() {}, renderKnowledgeCatalogTable() {}, renderMCPCatalogTable() {},
        knowledgeState: { managedItems: [] },
        apiFetch: async () => ({}), serviceFetch: async () => ({}),
        ...overrides,
    };
    vm.createContext(context);
    vm.runInContext(fs.readFileSync(path.resolve(__dirname,
        '../../../deployments/advertising/static/js/chat-catalog-loading.js'), 'utf8'), context);
    vm.runInContext(fs.readFileSync(path.resolve(
        __dirname, '../../../deployments/advertising/static/js', file,
    ), 'utf8'), context);
    if (file === 'chat-workspace.js') {
        vm.runInContext(fs.readFileSync(path.resolve(__dirname, '../../../deployments/advertising/static/js/chat-schedules.js'), 'utf8'), context);
    }
    return { context, elements };
}

function skillEnvironment(apiFetch) {
    const env = environment('chat-skills.js', { apiFetch });
    for (const key of ['renderSkillList', 'renderSkillFiles', 'renderSkillEvaluation', 'updateSkillEditorState']) {
        env.context[key] = () => {};
    }
    return env;
}

test('refreshing MCP catalog does not overwrite an open configuration draft', async () => {
    const {context} = environment('chat-mcp.js', {
        resourceCatalogs:{mcp:{view:'edit',sequence:0}},
        apiFetch: async () => ({servers:[{server_id:'draft-server',name:'Saved'}]}),
    });
    vm.runInContext("mcpState.selectedId = 'draft-server'",context);
    let selections = 0;
    context.selectMCPServer = () => { selections++; };
    await context.loadMCPServers();
    assert.equal(selections,0);
});

test('late MCP list refresh cannot reopen a detail after returning to the list', async () => {
    const pending = deferred();
    const {context} = environment('chat-mcp.js', {
        resourceCatalogs:{mcp:{view:'detail',sequence:1}}, apiFetch: () => pending.promise,
    });
    let selections = 0;
    context.selectMCPServer = () => { selections++; };
    const request = context.loadMCPServers('old-server');
    context.resourceCatalogs.mcp.sequence++;
    context.resourceCatalogs.mcp.view = 'list';
    pending.resolve({servers:[{server_id:'old-server'}]});
    await request;
    assert.equal(selections,0);
});

test('older MCP catalog response cannot overwrite the newest refresh', async () => {
    const old = deferred();
    let count = 0;
    const {context} = environment('chat-mcp.js', {apiFetch: () => ++count === 1
        ? old.promise : Promise.resolve({servers:[{server_id:'new'}]})});
    const first = context.loadMCPServers();
    await context.loadMCPServers();
    old.resolve({servers:[{server_id:'old'}]});
    await first;
    assert.equal(vm.runInContext('mcpState.servers[0].server_id',context),'new');
});

test('failed knowledge refresh preserves the last usable catalog', async () => {
    const {context} = environment('chat-knowledge.js', {
        apiFetch: async () => {throw new Error('offline');},
        serviceFetch: async () => {throw new Error('offline');},
    });
    context.knowledgeState.catalogItems = [{title:'keep me'}];
    await context.loadKnowledgeCatalog();
    assert.equal(context.knowledgeState.catalogItems[0]?.title,'keep me');
});

test('old managed knowledge refresh cannot replace newly loaded documents', async () => {
    const old = deferred();
    let count = 0;
    const {context} = environment('chat-knowledge.js', {apiFetch: () => ++count === 1
        ? old.promise : Promise.resolve({documents:[{document_id:'new',catalog_source:'managed'}],total:1,offset:0,limit:20,has_more:false})});
    const first = context.loadManagedKnowledgeDocuments();
    context.resourceCatalogs.knowledge.filters.source = 'managed';
    await context.loadManagedKnowledgeDocuments();
    old.resolve({documents:[{document_id:'old',catalog_source:'managed'}],total:1,offset:0,limit:20,has_more:false});
    await first;
    assert.equal(context.knowledgeState.catalogItems[0].document_id,'managed:new');
});

test('Skill binary assets survive loading and saving without decoding corruption', async () => {
    const content = Buffer.from([0, 255, 137, 80, 78, 71, 128]).toString('base64');
    const { context } = skillEnvironment(async () => ({ files: {
        'SKILL.md': '# Instructions', 'assets/image.png': { encoding: 'base64', content },
        'references/readme.md': { encoding: 'base64', content: Buffer.from('中文说明').toString('base64') },
    } }));
    await context.selectSkillVersion('example', '1.0.0');
    const files = context.collectSkillFiles();
    assert.equal(files['assets/image.png'].content, content);
    assert.equal(files['assets/image.png'].encoding, 'base64');
    assert.equal(files['references/readme.md'], '中文说明');
});

test('older Skill response cannot overwrite the newly selected version', async () => {
    const old = deferred();
    const { context } = skillEnvironment(endpoint => endpoint.includes('old')
        ? old.promise : Promise.resolve({ files: { 'SKILL.md': 'NEW' } }));
    const first = context.selectSkillVersion('old', '1.0.0');
    await context.selectSkillVersion('new', '2.0.0');
    old.resolve({ files: { 'SKILL.md': 'OLD' } });
    await first;
    assert.equal(context.skillState.selected.skillName, 'new');
    assert.equal(context.skillState.files[0].content, 'NEW');
});

test('new Skill draft invalidates a pending version read', async () => {
    const pending = deferred();
    const { context } = skillEnvironment(() => pending.promise);
    const first = context.selectSkillVersion('old', '1.0.0');
    context.newSkillDraft();
    pending.resolve({ files: { 'SKILL.md': 'OLD' } });
    await first;
    assert.equal(context.skillState.selected, null);
    assert.match(context.skillState.files[0].content, /new-skill/);
});

test('late knowledge search cannot replace a newer query', async () => {
    const old = deferred();
    const reply = title => ({documents:[{title,document_id:title,catalog_source:'managed'}],total:1,offset:0,limit:20,has_more:false});
    const { context } = environment('chat-knowledge.js', {
        apiFetch: endpoint => endpoint.includes('old') ? old.promise : Promise.resolve(reply('NEW')),
    });
    context.showKnowledgeSearchView = () => {};
    context.document.getElementById('knowledgeQuery').value = 'old';
    const first = context.searchKnowledge();
    context.document.getElementById('knowledgeQuery').value = 'new';
    await context.searchKnowledge();
    old.resolve(reply('OLD'));
    await first;
    assert.equal(context.knowledgeState.catalogItems[0].title, 'NEW');
});

test('knowledge publish failure keeps saved draft identity for retry', async () => {
    const calls = [];
    const { context } = environment('chat-knowledge.js', { apiFetch: async endpoint => {
        calls.push(endpoint);
        if (endpoint.endsWith('/publish')) throw new Error('temporarily unavailable');
        return { document_id: 'saved-draft' };
    } });
    context.document.getElementById('knowledgeTitle').value = 'Title';
    context.document.getElementById('knowledgeContent').value = 'Document';
    await context.saveKnowledgeDocument(true);
    assert.equal(context.knowledgeState.editingDocumentId, 'saved-draft');
    assert.equal(context.document.getElementById('knowledgeContent').value, 'Document');
    await context.saveKnowledgeDocument(true);
    assert.equal(calls.filter(endpoint => endpoint === '/knowledge/documents').length, 1);
});

test('late MCP test result cannot overwrite another tool panel', async () => {
    const pending = deferred();
    const { context } = environment('chat-mcp.js', { apiFetch: () => pending.promise });
    vm.runInContext("mcpState.selectedTool = {serverId:'server',toolId:'old',tool:{}}; mcpState.advancedInputEdited = true;", context);
    context.document.getElementById('mcpExternalInput').value = '{}';
    const request = context.testMCPTool();
    vm.runInContext("mcpState.selectedTool = {serverId:'server',toolId:'new',tool:{}};", context);
    context.document.getElementById('mcpExternalResult').textContent = 'NEW PANEL';
    pending.resolve({ success: true, data: 'OLD RESULT' });
    await request;
    assert.equal(context.document.getElementById('mcpExternalResult').textContent, 'NEW PANEL');
});

test('switching MCP tools resets pending controls for the new tool', () => {
    const { context } = environment('chat-mcp.js');
    context.renderMCPParameterForm = () => {};
    vm.runInContext("mcpState.servers = [{server_id:'s', tools:[{tool_id:'new',enabled:true,effect:'read',read_only:true}]}];", context);
    context.mcpToolIsReadOnly = () => true;
    context.document.getElementById('mcpExternalTestButton').disabled = true;
    context.selectMCPTool('s', 'new');
    assert.equal(context.document.getElementById('mcpExternalTestButton').disabled, false);
});

test('saving a new knowledge draft twice updates the same document', async () => {
    const calls = [];
    const { context } = environment('chat-knowledge.js', { apiFetch: async endpoint => {
        calls.push(endpoint);
        return { document_id: 'draft' };
    } });
    context.loadKnowledgeCatalog = context.loadManagedKnowledgeDocuments = async () => {};
    context.document.getElementById('knowledgeTitle').value = 'Title';
    context.document.getElementById('knowledgeContent').value = 'Document';
    await context.saveKnowledgeDocument();
    await context.saveKnowledgeDocument();
    assert.equal(calls.filter(endpoint => endpoint === '/knowledge/documents').length, 1);
});

test('Skills manager lists managed versions without automatically reading the first one', async () => {
    const { context } = skillEnvironment(async endpoint => endpoint.startsWith('/skills?')
        ? {managed_skills:[{skill_name:'managed',version:'1.0.0'}]} : {files:{'SKILL.md':'CONTENT'}});
    await context.loadManagedSkills();
    assert.equal(context.skillState.selected, undefined);
    assert.equal(context.skillState.versions.length, 1);
    await context.selectSkillVersion('managed','1.0.0');
    assert.equal(context.skillState.selected.skillName, 'managed');
});

test('Skill save cannot submit twice or overwrite a new draft', async () => {
    const pending = deferred(); let calls = 0;
    const { context } = skillEnvironment(() => { calls++; return pending.promise; });
    context.document.getElementById('skillNameInput').value = 'test';
    context.document.getElementById('skillVersionInput').value = '1.0.0';
    const saving = context.saveSkillDraft();
    const second = context.saveSkillDraft();
    context.newSkillDraft();
    pending.resolve({sha256:'digest'});
    await Promise.all([saving, second]);
    assert.equal(calls, 1);
    assert.equal(context.skillState.selected, null);
});

test('knowledge publishing does not reset another draft selected while waiting', async () => {
    const pending = deferred();
    const { context } = environment('chat-knowledge.js', { apiFetch: endpoint => endpoint.endsWith('/publish')
        ? pending.promise : Promise.resolve({document_id:'saved'}) });
    context.document.getElementById('knowledgeTitle').value = 'Title';
    context.document.getElementById('knowledgeContent').value = 'Document';
    const saving = context.saveKnowledgeDocument(true);
    await new Promise(resolve => setImmediate(resolve));
    context.resetKnowledgeEditor();
    context.document.getElementById('knowledgeContent').value = 'NEW';
    pending.resolve({});
    await saving;
    assert.equal(context.document.getElementById('knowledgeContent').value, 'NEW');
    assert.equal(context.knowledgeState.editingDocumentId || '', '');
});

test('schedule home fetches only its filtered task page', async () => {
    const calls=[];
    const { context } = environment('chat-workspace.js', {
        escapeHtml: String, apiFetch: async endpoint => {
            calls.push(endpoint);
            if (endpoint.startsWith('/schedules?')) return { schedules: [{name:'Daily'}] };
            throw new Error('unavailable');
        },
    });
    await context.loadSchedules();
    assert.match(context.document.getElementById('scheduleList').innerHTML, /Daily/);
    assert.equal(calls.length,1);
    assert.match(calls[0],/\/schedules\?.*page=1/);
});

test('editing a paged schedule reads its full prompt instead of saving the preview', async () => {
    const calls = [];
    const prompt = '完整执行指令'.repeat(100);
    const {context} = environment('chat-workspace.js', {
        escapeHtml: String, apiFetch: async endpoint => {
            calls.push(endpoint);
            return {schedule: {schedule_id: 'daily', name: 'Daily', prompt}};
        },
    });
    context.renderSchedules({schedules: [{schedule_id: 'daily', prompt_preview: '摘要'}]});
    await context.editSchedule('daily');
    assert.deepEqual(calls, ['/schedules/daily?include_runs=false']);
    assert.equal(context.document.getElementById('scheduleEditPrompt').value, prompt);
});

test('a slow schedule edit cannot replace another task or reopen a closed editor', async () => {
    const pending = deferred();
    const {context} = environment('chat-workspace.js', {
        escapeHtml: String, apiFetch: () => pending.promise,
    });
    context.renderSchedules({schedules: [
        {schedule_id: 'old', prompt_preview: '摘要'},
        {schedule_id: 'new', prompt: 'NEW'},
    ]});
    const first = context.editSchedule('old');
    await context.editSchedule('new');
    pending.resolve({schedule: {schedule_id: 'old', prompt: 'OLD'}});
    await first;
    assert.equal(context.document.getElementById('scheduleEditPrompt').value, 'NEW');

    const closed = deferred();
    context.apiFetch = () => closed.promise;
    const second = context.editSchedule('old');
    context.closeSchedules();
    closed.resolve({schedule: {schedule_id: 'old', prompt: 'CLOSED'}});
    await second;
    assert.equal(context.document.getElementById('scheduleEditPrompt').value, 'NEW');
});

test('schedule result details load on demand and ignore a closed panel', async () => {
    const pending = deferred();
    const calls = [];
    const { context } = environment('chat-workspace.js', {
        escapeHtml: String, formatContent: String,
        apiFetch: endpoint => { calls.push(endpoint); return pending.promise; },
    });
    context.renderScheduleRuns({ runs: [{schedule_run_id:'r',task_id:'t',status:'running'}] });
    assert.equal(calls.length, 0);
    const request = context.showScheduleRun('r');
    assert.deepEqual(calls, ['/tasks/t']);
    context.closeScheduleRun();
    pending.resolve({status:'succeeded', result:{response:'OLD RESULT'}});
    await request;
    assert.doesNotMatch(context.document.getElementById('scheduleRunContent').innerHTML || '', /OLD RESULT/);
});

test('saved schedule result displays response, error and a conversation link', async () => {
    const { context } = environment('chat-workspace.js', {
        escapeHtml: String, formatContent: value => `<p>${value}</p>`,
    });
    context.renderScheduleRuns({ runs: [{schedule_run_id:'r',status:'failed',error:'permission denied',
        result:{response:'Partial report',session_id:'session'}}] });
    await context.showScheduleRun('r');
    assert.match(context.document.getElementById('scheduleRunContent').innerHTML, /Partial report/);
    assert.match(context.document.getElementById('scheduleRunError').textContent, /permission denied/);
    assert.equal(context.document.getElementById('scheduleRunConversation').hidden, false);
});

test('run history requests only the selected task and resets its page on filtering', async () => {
    const calls=[];
    const {context}=environment('chat-workspace.js', {
        escapeHtml:String, apiFetch:async endpoint=>{
            calls.push(endpoint);
            return endpoint.includes('/runs?')?{runs:[],pagination:{page:1,total:0,pages:1,limit:20}}:{schedule:{schedule_id:'target',name:'Target'}};
        },
    });
    await context.showScheduleHistory('target');
    assert(calls.includes('/schedules/target?include_runs=false'));
    assert(calls.some(url=>url.startsWith('/schedules/target/runs?')));
    assert(!calls.some(url=>url.startsWith('/schedule-runs')));
    context.document.getElementById('scheduleRunsStatus').value='failed';
    await context.applyScheduleFilters('runs');
    assert.match(calls.at(-1),/status=failed/);
    assert.match(calls.at(-1),/page=1/);
});

test('schedule results extract the final assistant answer and keep tool payloads out of the reading view', () => {
    const { context } = environment('chat-workspace.js');
    const messages = [{role:'tool',content:'{"large":"RAW PAYLOAD"}'},
        {role:'assistant',content:'### 实际结果\n已完成查询。'}];
    assert.match(context.scheduleResultText({messages}, 'succeeded'), /实际结果/);
    assert.doesNotMatch(context.scheduleResultText({messages:messages.slice(0,1)}, 'failed'), /RAW PAYLOAD/);
});

test('switching workspaces closes skills and model settings too', () => {
    let closedSkills=0, closedSettings=0;
    const {context} = environment('chat-workspace.js', {
        monitoringRefreshTimer:null,
        closeSkillManager:()=>closedSkills++, closeAgentSettings:()=>closedSettings++,
    });
    context.closeWorkspacePopovers();
    assert.equal(closedSkills,1);
    assert.equal(closedSettings,1);
});

test('template load failure preserves previously loaded templates and reports an error', async () => {
    const prior = [{template_id:'saved',blueprint_id:'bp',status:'active'}];
    const {context} = environment('chat-blueprint-editor.js', {
        blueprintState:{mode:'templates',items:[],tools:[],templates:prior,selected:{id:'bp'},values:{name:'draft'}},
        apiFetch: async url => {
            if(url==='/creation-templates') throw new Error('模板目录暂不可用');
            return url==='/creation-blueprints'?{blueprints:[{id:'bp'}]}:{tools:[],formats:[]};
        },
    });
    let notice='';
    context.renderBlueprintList=()=>{};
    context.renderBlueprintEditor=()=>{};
    context.selectCreationTemplate=()=>{};
    context.showBlueprintNotice=message=>{notice=message};
    await context.loadCreationBlueprints();
    assert.equal(context.blueprintState.templates,prior);
    assert.match(notice,/模板.*不可用/);
});

test('declared single-option derived field wins over a broad Tool default', () => {
    const {context}=environment('chat-blueprint-core.js');
    context.blueprintToolFieldSchema=()=>({schema:{default:'GENERIC',type:'string'}});
    assert.equal(context.blueprintFieldDefault({presentation:'derived_readonly',options:['SPECIAL'],default:'GENERIC'}),'SPECIAL');
    assert.equal(context.blueprintFieldDefault({options:['A','B'],default:'GENERIC'}),undefined);
});

test('new template starts from the selected registered blueprint without an account preset', () => {
    const {context}=environment('chat-blueprint-editor.js', {
        blueprintState:{items:[{id:'format-a'}], templates:[], accountId:'previous-account'},
    });
    vm.runInContext(fs.readFileSync(path.resolve(__dirname,
        '../../../deployments/advertising/static/js/chat-template-browser.js'), 'utf8'),context);
    context.document.getElementById('templateCreateType').value='format-a';
    let args;
    context.selectBlueprint=(...value)=>{args=value};
    context.showBlueprintNotice=()=>{};
    context.beginTemplateDraft();
    assert.equal(context.blueprintState.accountId,'');
    assert.equal(context.blueprintState.creatingTemplate,true);
    assert.deepEqual(args,['format-a',null,null,false]);
});

test('health readiness treats 503 as diagnostic data, not a failed JSON read', async () => {
    const {context} = environment('chat-workspace.js', {
        serviceFetch: async () => ({ok:false,status:503,json:async()=>({status:'not_ready',checks:{llm:false}})}),
    });
    const report = await context.fetchServiceReadiness();
    assert.equal(report.checks.llm,false);
    context.serviceFetch=async()=>({ok:false,status:403,json:async()=>({detail:'Denied'})});
    await assert.rejects(context.fetchServiceReadiness(), /403/);
});

test('opening system operations retains an open mobile navigation', () => {
    let navigationOpen = true;
    const {context} = environment('chat-workspace.js');
    context.document.body = {classList:{contains:()=>navigationOpen,add:()=>{navigationOpen=true}}};
    context.closeWorkspacePopovers=()=>{navigationOpen=false};
    context.toggleSystemOpsMenu();
    assert.equal(navigationOpen,true);
});

test('closing health view before its response prevents rendering and polling', async () => {
    const pending=deferred();
    let active=true, rendered=0, polls=0;
    const {context}=environment('chat-workspace.js', {
        monitoringRequestToken:0, monitoringRefreshTimer:null,
        window:{clearTimeout(){},setTimeout(){polls++}},
    });
    const overlay=context.document.getElementById('monitoringOverlay');
    overlay.classList.contains=()=>active;
    overlay.dataset={monitoringView:'health'};
    context.fetchServiceReadiness=()=>pending.promise;
    context.renderServiceHealth=()=>{rendered++};
    const request=context.loadMonitoring(true);
    active=false;
    pending.resolve({status:'ready',checks:{runtime:true}});
    await request;
    assert.equal(rendered,0);
    assert.equal(polls,0);
});

for (const phase of ['save', 'publish', 'refresh']) {
    test(`knowledge edits during ${phase} remain dirty and keep their document identity`, async () => {
        const pending = deferred(), entered = deferred(), calls = [];
        const {context} = environment('chat-knowledge.js', {apiFetch: async (url, options) => {
            calls.push({url, options});
            if ((phase === 'save' && !url.endsWith('/publish')) || (phase === 'publish' && url.endsWith('/publish'))) {
                entered.resolve(); await pending.promise;
            }
            return {document_id:'saved',version:'1.0.1'};
        }});
        context.loadManagedKnowledgeDocuments = async () => {
            if (phase === 'refresh') {entered.resolve();await pending.promise;}
        };
        let navigated = false;
        context.showResourceList = () => {navigated = true;};
        context.document.getElementById('knowledgeTitle').value = 'Title';
        context.document.getElementById('knowledgeContent').value = 'Submitted';
        context.document.getElementById('knowledgeVersion').value = '1.0.0';
        const saving = context.saveKnowledgeDocument(phase === 'publish');
        await entered.promise;
        context.document.getElementById('knowledgeContent').value = 'New unsaved edits';
        context.document.getElementById('knowledgeVersion').value = '2.0.0';
        pending.resolve(); await saving;
        assert.equal(context.document.getElementById('knowledgeContent').value, 'New unsaved edits');
        assert.equal(context.document.getElementById('knowledgeVersion').value, '2.0.0');
        assert.equal(context.knowledgeState.editingDocumentId, 'saved');
        assert.equal(context.resourceCatalogs.knowledge.hasDraft, true);
        assert.equal(navigated, false);
        assert.match(context.document.getElementById('knowledgeWriteStatus').textContent, /未保存/);
    });
}
