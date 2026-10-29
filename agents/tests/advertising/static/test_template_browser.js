const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function environment() {
    const context = {blueprintState: {templates: [], items: []}, console};
    vm.createContext(context);
    vm.runInContext(fs.readFileSync(path.resolve(__dirname,
        '../../../deployments/advertising/static/js/chat-template-browser.js'), 'utf8'), context);
    return context;
}

const templates = [
    {template_id:'a', name:'新品推广', provider:'meta', account_id:'123', ad_format:'traffic', source:'builtin'},
    {template_id:'b', name:'新品推广 副本', provider:'meta', account_id:'456', ad_format:'traffic', source:'user'},
    {template_id:'c', name:'搜索模板', provider:'google-ads', account_id:'', ad_format:'search', source:'user'},
];

test('saved template filters intersect channel, account, format, status and search', () => {
    const {templateCatalogPage} = environment();
    const result = templateCatalogPage(templates, {q:'新品', provider:'meta', account:'456', format:'traffic', page:1, limit:20});
    assert.equal(result.total, 1);
    assert.equal(result.items[0].template_id, 'b');
    assert.equal(templateCatalogPage(templates, {provider:'meta', account:'123', format:'search'}).total, 0);
    assert.equal(templateCatalogPage([{source:'user',status:'inactive'}],{status:'active'}).total,0);
});

test('the saved list excludes builtin presets but keeps user-created general templates', () => {
    const {templateCatalogPage} = environment();
    const items = [
        ...templates,
        {template_id:'starter',source:'builtin',scope_type:'general'},
        {template_id:'named-starter',name:'我的起步模板',source:'user',scope_type:'general'},
    ];
    assert.deepEqual(Array.from(templateCatalogPage(items).items,item=>item.template_id),['b','c','named-starter']);
    assert.equal(templateCatalogPage(items.filter(item=>item.source==='builtin')).total,0);
    assert.equal(items.length,5,'classification must not remove the original presets');
});

test('creation presets include only active builtin parameters for the chosen blueprint and version', () => {
    const {templateCreationPresets} = environment();
    const blueprint={id:'meta.traffic',provider:'meta',version:'1.0.0'};
    const base={source:'builtin',status:'active',blueprint_id:blueprint.id,provider:blueprint.provider};
    const presets=[
        {...base,template_id:'general',scope_type:'general'},
        {...base,template_id:'account',account_id:'123',scope_type:'account'},
        {...base,template_id:'user',source:'user'},
        {...base,template_id:'inactive',status:'inactive'},
        {...base,template_id:'other',blueprint_id:'meta.app'},
        {...base,template_id:'old',blueprint_version:'0.1.0'},
    ];
    assert.deepEqual(Array.from(templateCreationPresets(presets,blueprint),item=>item.template_id),['general','account']);
    assert.equal(templateCreationPresets(presets,null).length,0);
});

test('unscoped templates and missing metadata remain browsable', () => {
    const {templateCatalogPage} = environment();
    assert.equal(templateCatalogPage(templates, {account:'__general__'}).items[0].template_id, 'c');
    assert.equal(templateCatalogPage([{}, {name:'Hello'}], {q:'hello'}).total, 1);
    assert.equal(templateCatalogPage([], {page:8}).page, 1);
});

test('pagination clamps after deletion or filtering without rendering all entries', () => {
    const {templateCatalogPage} = environment();
    const items = Array.from({length:23}, (_,i)=>({template_id:String(i)}));
    const result = templateCatalogPage(items, {page:99, limit:10});
    assert.equal(result.page, 3);
    assert.equal(result.items.length, 3);
    assert.equal(result.items[0].template_id, '20');
});

test('builtin and explicitly read-only templates cannot enter edit mode', () => {
    const context = environment();
    let opened, edited = false;
    context.blueprintState.templates = [{template_id:'builtin',source:'builtin'}, {template_id:'locked',source:'user',editable:false}];
    context.openTemplateDetail = id => { opened = id; };
    context.showBlueprintNotice = () => {};
    context.selectCreationTemplate = () => { edited = true; };
    context.editTemplateFromLibrary('builtin');
    assert.equal(opened, 'builtin');
    context.editTemplateFromLibrary('locked');
    assert.equal(opened, 'locked');
    assert.equal(edited, false);
});

function editorEnvironment() {
    const context = environment();
    context.document = {getElementById: () => ({value:'', checked:false})};
    context.window = {confirm: () => true};
    context.showTemplateLibrary = () => {};
    vm.runInContext(fs.readFileSync(path.resolve(__dirname,
        '../../../deployments/advertising/static/js/chat-blueprint-editor.js'), 'utf8'), context);
    context.showBlueprintNotice = message => { context.notice = message; };
    context.blueprintState.mode = 'templates';
    return context;
}

test('delete failure preserves the template and read-only deletion never sends a request', async () => {
    const context = editorEnvironment();
    context.blueprintState.templates = [{template_id:'read-only',source:'builtin'}, {template_id:'mine',source:'user'}];
    let requests = 0;
    context.apiFetch = async () => { requests++; throw new Error('保存服务暂不可用'); };
    await context.deleteSelectedCreationTemplate('read-only');
    assert.equal(requests, 0);
    await context.deleteSelectedCreationTemplate('mine');
    assert.equal(requests, 1);
    assert.equal(context.blueprintState.templates.length, 2);
    assert.match(context.notice, /服务暂不可用/);
});

test('editing an inactive template preserves its status; save-as-new starts active', () => {
    const context = editorEnvironment();
    context.blueprintState.selected = {id:'search',provider:'google-ads'};
    context.blueprintState.templates = [{template_id:'mine',status:'inactive'}];
    context.blueprintState.selectedTemplateId = 'mine';
    assert.equal(context.creationTemplatePayload().status, 'inactive');
    context.blueprintState.templateSaveAsNew = true;
    assert.equal(context.creationTemplatePayload().status, 'active');
});

test('template row identifiers cannot escape their data attribute', () => {
    const context = environment();
    context.escapeHtml = value => String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
    const html = context.templateRowActions({template_id:'id" autofocus="true',source:'user'});
    assert(html.includes('data-id="id&quot; autofocus=&quot;true"'));
    assert(!html.includes('data-id="id" autofocus="true"'));
});

test('starting from an account preset makes an independent draft without a builtin save target', () => {
    const context=editorEnvironment();
    const blueprint={id:'meta.traffic',provider:'meta',version:'1.0.0'};
    const preset={template_id:'reference',source:'builtin',status:'active',provider:'meta',
        blueprint_id:blueprint.id,account_id:'123',values:{targeting:{countries:['US']}}};
    context.blueprintState.items=[blueprint];
    context.blueprintState.templates=[preset];
    context.document.getElementById=id=>({value:{templateCreateType:blueprint.id,templateCreatePreset:'reference'}[id] || ''});
    let draft;
    context.selectBlueprint=(id,selector,template,useDefault)=>{
        assert.equal(id,blueprint.id);
        assert.equal(useDefault,false);
        draft=template;
    };
    context.beginTemplateDraft();
    assert.equal(draft.template_id,'');
    assert.equal(draft.account_id,'123');
    draft.values.targeting.countries.push('CA');
    assert.deepEqual(preset.values.targeting.countries,['US']);
    assert.equal(context.blueprintState.creatingTemplate,true);
});

test('a stale preset from another ad type cannot seed the new draft', () => {
    const context=editorEnvironment();
    context.blueprintState.items=[{id:'meta.app',provider:'meta',version:'1.0.0'}];
    context.blueprintState.templates=[{template_id:'old',source:'builtin',status:'active',blueprint_id:'meta.traffic',provider:'meta'}];
    context.document.getElementById=id=>({value:id==='templateCreateType'?'meta.app':'old'});
    let selected=false;
    context.selectBlueprint=()=>{selected=true};
    context.beginTemplateDraft();
    assert.equal(selected,false);
    assert.match(context.notice,/重新选择/);
});

test('template list fetches only saved records, shares in-flight reads and keeps data on error', async () => {
    const context=environment();
    let release, calls=0;
    context.renderTemplateLibrary=()=>{};
    context.showBlueprintNotice=()=>{};
    context.apiFetch=url=>{
        assert.equal(url,'/creation-templates?source=user&limit=200');
        calls++;
        return new Promise(resolve=>{release=resolve});
    };
    const first=context.loadTemplateLibrary();
    const second=context.loadTemplateLibrary();
    release({templates:[{template_id:'saved',source:'user'}]});
    await Promise.all([first,second]);
    assert.equal(calls,1);
    assert.equal(context.blueprintState.templates[0].template_id,'saved');
    context.apiFetch=async()=>{throw new Error('offline')};
    await context.loadTemplateLibrary();
    assert.equal(context.blueprintState.templates[0].template_id,'saved');
});
