/* Shared list-first navigation for knowledge, Skills and MCP management. */
const resourceCatalogs = Object.fromEntries(['knowledge', 'skills', 'mcp'].map(kind =>
    [kind, {view:'list', q:'', filters:{}, page:1, limit:20, hasDraft:false, sequence:0}]));
const resourceOverlayIds = {knowledge:'knowledgeOverlay', skills:'skillOverlay', mcp:'mcpOverlay'};

function resourceCatalogPage(items, state = {}) {
    const q = String(state.q || '').trim().toLocaleLowerCase();
    const matches = items.filter(item => (!q || `${item.title || ''} ${item.search || ''}`.toLocaleLowerCase().includes(q))
        && Object.entries(state.filters || {}).every(([key,value]) => !value || item.filters?.[key] === value));
    const limit = [10,20,50].includes(Number(state.limit)) ? Number(state.limit) : 20;
    const pages = Math.max(1, Math.ceil(matches.length / limit));
    const page = Math.max(1, Math.min(Number(state.page) || 1, pages));
    return {items:matches.slice((page-1)*limit,page*limit), total:matches.length, pages, page};
}

function mergeKnowledgeCatalog(published, managed) {
    const items = new Map(published.map(item => [item.document_id || item.source_ref || item.title, item]));
    for (const item of managed) {
        const id = `managed:${item.document_id}`;
        items.set(id, {...items.get(id), ...item, document_id:id, excerpt:item.content || items.get(id)?.excerpt || ''});
    }
    return [...items.values()];
}

function nextSkillRevision(name, version, versions) {
    return nextResourceRevision(version, versions.filter(item => item.skill_name === name).map(item => item.version));
}

function nextResourceRevision(version, versions = []) {
    const match = /^(\d+)\.(\d+)\.(\d+)/.exec(String(version));
    const major = match ? Number(match[1]) : 1, minor = match ? Number(match[2]) : 0;
    let patch = match ? Number(match[3])+1 : 0;
    const existing = new Set(versions);
    while (existing.has(`${major}.${minor}.${patch}`)) patch++;
    return `${major}.${minor}.${patch}`;
}

function setResourceView(kind, view) {
    const state = resourceCatalogs[kind];
    if (state.view === 'edit' && view !== 'edit' && state.hasDraft) {
        state.draft = captureResourceDraft(kind);
    }
    state.view = view;
    document.getElementById(resourceOverlayIds[kind])?.setAttribute('data-catalog-view', view);
    const back = document.getElementById(`${kind}CatalogBack`);
    if (back) back.hidden = view === 'list';
}

function showResourceList(kind) {
    resourceCatalogs[kind].sequence++;
    if (kind === 'skills') {
        skillDetailSequence++;
        if (skillState.evaluationTimer) window.clearTimeout(skillState.evaluationTimer);
        skillState.evaluationTimer = null;
    }
    if (kind === 'knowledge') knowledgeEditSequence++;
    if (kind === 'mcp') hideMCPToolTestPanel();
    setResourceView(kind, 'list');
    const render = {knowledge:renderKnowledgeCatalogTable, skills:renderSkillsCatalogTable, mcp:renderMCPCatalogTable}[kind];
    render();
}

function trackResourceDraft(kind, selector) {
    const editor = document.querySelector(selector);
    if (!editor || editor.dataset.draftTracked) return;
    editor.dataset.draftTracked = 'true';
    const markDirty = () => {
        if (resourceCatalogs[kind].view === 'edit') resourceCatalogs[kind].hasDraft = true;
    };
    editor.addEventListener('input', markDirty);
    editor.addEventListener('change', markDirty);
}

function resumeResourceDraft(kind) {
    if (!resourceCatalogs[kind].hasDraft) return;
    const draft = resourceCatalogs[kind].draft;
    setResourceView(kind, 'edit');
    if (draft) restoreResourceDraft(kind, draft);
    if (kind === 'knowledge') showKnowledgeManagementView(false);
}

function catalogElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
}

function catalogButton(label, action, className = '') {
    const button = catalogElement('button',className,label);
    button.type = 'button'; button.onclick = action;
    return button;
}

function mountResourceCatalog(kind, config) {
    const target = document.getElementById(`${kind}Catalog`);
    if (!target || target.dataset.mounted) return target;
    target.dataset.mounted = 'true';
    const state = resourceCatalogs[kind];
    const filterbar = catalogElement('form','resource-catalog-filters');
    const apply = () => { state.page=1; renderResourceCatalog(kind,state.rows,state.config); };
    filterbar.onsubmit = event => { event.preventDefault(); apply(); };
    if (config.search !== false) {
        const label = catalogElement('label','resource-catalog-search','搜索');
        const input = catalogElement('input'); input.type='search'; input.id=`${kind}CatalogQuery`;
        input.placeholder=config.placeholder || '搜索名称或说明'; input.maxLength=200; input.value=state.q;
        input.oninput=()=>{state.q=input.value; apply();};
        label.append(input); filterbar.append(label);
    }
    for (const filter of config.filters) {
        const label=catalogElement('label','',filter.label), select=catalogElement('select');
        select.id=`${kind}CatalogFilter-${filter.key}`;
        select.onchange=()=>{state.filters[filter.key]=select.value; apply();};
        label.append(select); filterbar.append(label);
    }
    const resume=catalogButton('继续未保存的编辑',()=>resumeResourceDraft(kind),'resource-catalog-resume');
    resume.id=`${kind}CatalogResume`; resume.hidden=true;
    const status = catalogElement('div','resource-catalog-status');
    status.id = `${kind}CatalogStatus`; status.hidden = true;
    const message = catalogElement('span'); message.id = `${kind}CatalogStatusMessage`;
    message.setAttribute('role','status'); message.setAttribute('aria-live','polite');
    const retry = catalogButton('重试',()=>{}); retry.id = `${kind}CatalogRetry`; retry.hidden = true;
    status.append(message,retry);
    const table=catalogElement('table','resource-catalog-table'); table.setAttribute('aria-label',config.title);
    const head=catalogElement('thead'), header=catalogElement('tr');
    for (const title of [...config.columns,'操作']) {const th=catalogElement('th','',title); th.scope='col'; header.append(th);}
    head.append(header);
    const body=catalogElement('tbody'); body.id=`${kind}CatalogRows`;
    table.append(head,body);
    const pagination=catalogElement('nav','schedule-pagination'); pagination.setAttribute('aria-label',`${config.title}分页`);
    const info=catalogElement('span'); info.id=`${kind}CatalogPageInfo`; info.setAttribute('role','status');
    const sizeLabel=catalogElement('label','','每页'), size=catalogElement('select'); size.id=`${kind}CatalogSize`;
    for(const value of [10,20,50]) size.add(new Option(`${value} 条`,String(value)));
    size.value=String(state.limit); size.onchange=()=>{state.limit=Number(size.value);apply();}; sizeLabel.append(size);
    const turn=direction=>{state.page+=direction;renderResourceCatalog(kind,state.rows,state.config);target.scrollTop=0;};
    const previous=catalogButton('上一页',()=>turn(-1)), next=catalogButton('下一页',()=>turn(1));
    previous.id=`${kind}CatalogPrevious`; next.id=`${kind}CatalogNext`;
    pagination.append(info,sizeLabel,previous,next);
    target.replaceChildren(filterbar,status,resume,table,pagination);
    return target;
}

function renderResourceCatalog(kind, rows, config) {
    if (!mountResourceCatalog(kind,config)) return;
    const state=resourceCatalogs[kind]; state.rows=rows; state.config=config;
    for(const filter of config.filters) {
        const select=document.getElementById(`${kind}CatalogFilter-${filter.key}`);
        const options=new Map(rows.map(row=>[row.filters[filter.key],row.filterLabels?.[filter.key] || row.filters[filter.key]]));
        select.replaceChildren(new Option(`全部${filter.label}`,''));
        for(const [value,label] of options) if(value) select.add(new Option(label,value));
        if(state.filters[filter.key] && !options.has(state.filters[filter.key])) select.add(new Option(state.filters[filter.key],state.filters[filter.key]));
        select.value=state.filters[filter.key] || '';
    }
    const page=resourceCatalogPage(rows,state); state.page=page.page;
    const body=document.getElementById(`${kind}CatalogRows`); body.replaceChildren();
    for(const row of page.items) {
        const tr=catalogElement('tr',`resource-catalog-row ${kind}-catalog-row`);
        const main=catalogElement('td'); main.append(catalogButton(row.title,row.open,'resource-catalog-name'));
        if(row.subtitle) main.append(catalogElement('p','',row.subtitle)); tr.append(main);
        row.cells.forEach((value,index)=>{const td=catalogElement('td','',value);td.dataset.label=config.columns[index+1];tr.append(td);});
        const actions=catalogElement('td'), group=catalogElement('div','resource-catalog-actions');
        for(const action of row.actions) group.append(catalogButton(action.label,action.run,action.danger?'danger':''));
        actions.append(group); tr.append(actions); body.append(tr);
    }
    if(!page.items.length) {const tr=catalogElement('tr'), td=catalogElement('td','monitoring-empty');td.id=`${kind}CatalogEmpty`;td.colSpan=config.columns.length+1;tr.append(td);body.append(tr);}
    document.getElementById(`${kind}CatalogPageInfo`).textContent=`共 ${page.total} 条 · 第 ${page.page} / ${page.pages} 页`;
    document.getElementById(`${kind}CatalogPrevious`).disabled=page.page<=1;
    document.getElementById(`${kind}CatalogNext`).disabled=page.page>=page.pages;
    document.getElementById(`${kind}CatalogResume`).hidden=!state.hasDraft;
    renderCatalogLoadStatus(kind);
}
