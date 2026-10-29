/* Catalog adapters use existing domain operations and preserve their permissions. */
const resourceDraftFieldIds = {
    knowledge: ['knowledgeTitle','knowledgeContent','knowledgeWritePlatform','knowledgeWriteType',
        'knowledgeVersion','knowledgeTags','knowledgeSource'],
    skills: ['skillNameInput','skillVersionInput'],
    mcp: ['mcpNameInput','mcpEndpointInput','mcpAuthTypeInput','mcpCredentialRefInput',
        'mcpAuthHeaderInput','mcpTimeoutInput','mcpDescriptionInput'],
};

// One in-memory draft per workspace. Browsing details never replaces its data.
function captureResourceDraft(kind) {
    const fields = Object.fromEntries(resourceDraftFieldIds[kind].map(id =>
        [id, document.getElementById(id)?.value || '']));
    if (kind === 'knowledge') return {fields, documentId:knowledgeState.editingDocumentId};
    if (kind === 'mcp') return {fields, serverId:mcpState.selectedId};
    return {fields, files:skillState.files.map(file => ({...file})),
        activeFilePath:skillState.activeFilePath, previewMode:skillState.previewMode};
}

function restoreResourceDraft(kind, draft) {
    if (kind === 'knowledge') setKnowledgeEditorMode(draft.documentId);
    if (kind === 'mcp') {
        if (draft.serverId) selectMCPServer(draft.serverId, true);
        else newMCPServer();
    }
    for (const [id,value] of Object.entries(draft.fields)) {
        const field = document.getElementById(id);
        if (field) field.value = value;
    }
    if (kind === 'mcp') updateMCPAuthHint();
    if (kind !== 'skills') return;
    skillDetailSequence++;
    skillState.selected = null;
    skillState.detail = null;
    skillState.readOnly = false;
    skillState.browsingOnly = false;
    skillState.files = draft.files.map(file => ({...file}));
    skillState.activeFilePath = draft.activeFilePath;
    skillState.previewMode = draft.previewMode;
    document.getElementById('skillEvalSummary').textContent = '已恢复未保存的版本草稿；原版本保持不变。';
    renderSkillFiles();
    updateSkillEditorState();
    clearSkillNotice();
}

function renderKnowledgeCatalogTable() {
    const query=String(document.getElementById('knowledgeQuery')?.value || '').trim().toLowerCase();
    const platform=document.getElementById('knowledgePlatform')?.value || '';
    const managed=(knowledgeState.managedItems || []).filter(item=>(!platform || item.platform===platform)
        && (!query || [item.title,item.content,...(item.tags || [])].join(' ').toLowerCase().includes(query)));
    const items=mergeKnowledgeCatalog(knowledgeState.items || [],managed);
    const rows=items.map(item=>{
        const isManaged=String(item.document_id || '').startsWith('managed:');
        const id=isManaged ? item.document_id.slice(8) : item.document_id;
        const status=item.status || 'published';
        const statusLabel={published:'已发布',draft:'草稿',deprecated:'已归档'}[status] || status;
        const source=isManaged?'managed':'builtin', category=item.category || item.knowledge_type || 'general';
        const categoryLabel=item.category?knowledgeCategoryLabel(category):knowledgeTypeLabel(category);
        const open=()=>openKnowledgeCatalogEntry(item);
        const actions=[{label:'详情',run:open}];
        if(isManaged && status!=='deprecated') actions.push({label:'编辑',run:()=>editKnowledgeDocument(id)});
        if(isManaged) actions.push({label:status==='published'?'归档':'删除',danger:true,run:()=>deleteKnowledgeDocument(id,status)});
        else actions.push({label:'复制',run:()=>cloneKnowledgeDocument(item)});
        return {title:item.title || item.topic || '未命名知识',subtitle:item.description || (item.tags || []).join(' · '),
            filters:{source,status,category},filterLabels:{source:isManaged?'自建':'内置',status:statusLabel,category:categoryLabel},
            cells:[knowledgePlatformLabel(item.platform),categoryLabel,item.version || '—',statusLabel,isManaged?'自建':'内置 · 只读'],open,actions};
    });
    renderResourceCatalog('knowledge',rows,{title:'知识库列表',search:false,
        columns:['知识标题','平台','分类','版本','状态','来源'],filters:[{key:'category',label:'分类'},{key:'source',label:'来源'},{key:'status',label:'状态'}]});
}

async function openKnowledgeCatalogEntry(item) {
    const sequence=++resourceCatalogs.knowledge.sequence;
    setResourceView('knowledge','detail');
    const reader=document.getElementById('knowledgeReader'); reader.textContent='正在读取知识正文…';
    try {
        let detail=item;
        if(String(item.document_id || '').startsWith('managed:')) {
            detail=await apiFetch(`/knowledge/documents/${encodeURIComponent(item.document_id.slice(8))}`);
            detail={...detail,document_id:item.document_id,excerpt:detail.content || ''};
        }
        if(sequence!==resourceCatalogs.knowledge.sequence) return;
        renderKnowledgeReader(detail);
        reader.scrollTop=0;
    } catch(error) {
        if(sequence!==resourceCatalogs.knowledge.sequence) return;
        reader.textContent=error.message || '读取失败，请返回列表重试。';
    }
}

function newKnowledgeCatalogDocument() {
    resetKnowledgeEditor();
    showKnowledgeManagementView();
}

function renderSkillsCatalogTable() {
    const rows=skillState.versions.map(item=>{
        const source=item.source || 'managed', status=item.status || (source==='builtin'?'published':'draft');
        const open=()=>openSkillCatalogEntry(item);
        const platform=item.platform || item.metadata?.platform || 'all';
        const statusLabel=skillStatusLabel(status), sourceLabel=source==='builtin'?'内置':'自建';
        return {title:item.display_name || item.skill_name,subtitle:item.description || item.skill_name,
            search:[item.skill_name,item.description,platform].join(' '),filters:{source,status,platform},
            filterLabels:{source:sourceLabel,status:statusLabel,platform:knowledgePlatformLabel(platform)},
            cells:[knowledgePlatformLabel(platform),item.version,statusLabel,sourceLabel],open,
            actions:[{label:'详情',run:open},{label:source==='builtin'?'复制':'编辑新版本',run:()=>openSkillCatalogEntry(item,true)}]};
    });
    renderResourceCatalog('skills',rows,{title:'Skills 列表',columns:['Skill','平台','版本','状态','来源'],
        filters:[{key:'platform',label:'平台'},{key:'source',label:'来源'},{key:'status',label:'状态'}]});
}

async function openSkillCatalogEntry(item, edit = false) {
    const selected=await selectSkillVersion(item.skill_name,item.version,item.source || 'managed');
    if(selected && edit) cloneSelectedBuiltin();
}

function renderMCPCatalogTable() {
    const rows=mcpState.servers.map(server=>{
        const runtime=server.source==='runtime_registry';
        const source=runtime?'runtime':'external', status=server.status || 'draft';
        const open=()=>selectMCPServer(server.server_id);
        const actions=[{label:'详情',run:open}];
        if(!runtime) actions.push({label:'编辑',run:()=>selectMCPServer(server.server_id,true)},
            {label:'移除',danger:true,run:()=>deleteMCPServer(server.server_id)});
        return {title:server.name || server.server_id,subtitle:server.description || '',
            search:[server.name,server.description,server.endpoint,...(server.tools || []).map(tool=>tool.name)].join(' '),
            filters:{source,status},filterLabels:{source:runtime?'内置':'外部',status:mcpStatusLabel(status)},
            cells:[runtime?'内置':'外部',mcpStatusLabel(status),String((server.tools || []).length),server.endpoint || '由部署配置提供'],open,actions};
    });
    renderResourceCatalog('mcp',rows,{title:'MCP 列表',columns:['MCP 服务','来源','状态','Tools','Endpoint'],
        filters:[{key:'source',label:'来源'},{key:'status',label:'状态'}]});
}
