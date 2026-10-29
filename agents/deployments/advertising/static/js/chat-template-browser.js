/* Template management navigation; the existing blueprint editor owns parameter editing. */
const templateBrowser = {
    view: 'list', q: '', provider: '', account: '', format: '', status: '',
    page: 1, limit: 20, selectedId: '', hasDraft: false,
    loaded: false, loading: false, navigationSequence: 0,
};

let templateLibraryLoadPromise = null;
let templateEditorLoadPromise = null;

function loadTemplateLibrary() {
    if (templateLibraryLoadPromise) return templateLibraryLoadPromise;
    templateBrowser.loading = true;
    renderTemplateLibrary();
    templateLibraryLoadPromise = (async () => {
        try {
            const data = await apiFetch('/creation-templates?source=user&limit=200');
            const presets = blueprintState.templates.filter(item => item.source === 'builtin');
            blueprintState.templates = [...presets, ...savedCreationTemplates(data.templates || [])];
            templateBrowser.loaded = true;
            showBlueprintNotice('');
        } catch (error) {
            showBlueprintNotice(`模板读取失败：${error.message || '服务暂不可用'}。已保留现有列表，请刷新重试。`);
        } finally {
            templateBrowser.loading = false;
            templateLibraryLoadPromise = null;
            renderTemplateLibrary();
        }
    })();
    return templateLibraryLoadPromise;
}

async function ensureTemplateEditorCatalog() {
    if (blueprintState.catalogLoaded) return true;
    if (!templateEditorLoadPromise) {
        showBlueprintNotice('正在读取模板字段定义…');
        templateEditorLoadPromise = loadCreationBlueprints(null, true)
            .then(() => Boolean(blueprintState.catalogLoaded))
            .finally(() => { templateEditorLoadPromise = null; });
    }
    return templateEditorLoadPromise;
}

function refreshTemplateManager() {
    if (blueprintState.mode === 'templates' && templateBrowser.view === 'list') return loadTemplateLibrary();
    return loadCreationBlueprints(null, true);
}

function savedCreationTemplates(items) {
    return items.filter(item => item.source !== 'builtin');
}

function templateCreationPresets(items, blueprint) {
    if (!blueprint) return [];
    return items.filter(item => item.source === 'builtin' && item.status === 'active'
        && item.provider === blueprint.provider && item.blueprint_id === blueprint.id
        && (!item.blueprint_version || item.blueprint_version === blueprint.version));
}

function templateCatalogPage(items, filters = {}) {
    const query = String(filters.q || '').trim().toLocaleLowerCase();
    const matches = savedCreationTemplates(items).filter(item => {
        const account = item.account_id || '__general__';
        const text = [item.name, item.description, item.account_id, ...(item.tags || [])].join(' ').toLocaleLowerCase();
        return (!filters.provider || item.provider === filters.provider)
            && (!filters.account || account === filters.account)
            && (!filters.format || item.ad_format === filters.format)
            && (!filters.status || item.status === filters.status)
            && (!query || text.includes(query));
    });
    const limit = [10, 20, 50].includes(Number(filters.limit)) ? Number(filters.limit) : 20;
    const pages = Math.max(1, Math.ceil(matches.length / limit));
    const page = Math.max(1, Math.min(Number(filters.page) || 1, pages));
    return {items: matches.slice((page - 1) * limit, page * limit), total: matches.length, pages, page};
}

function templateIsEditable(template) {
    return Boolean(template && template.source !== 'builtin' && template.editable !== false);
}

function templateFormatLabel(template) {
    return blueprintState.items.find(item => item.id === template.blueprint_id)?.title || template.ad_format || '—';
}

function setTemplateManagerView(view) {
    templateBrowser.view = view;
    const overlay = document.getElementById('blueprintOverlay');
    overlay?.setAttribute('data-template-mode', String(blueprintState.mode === 'templates'));
    overlay?.setAttribute('data-template-view', view);
    const back = document.getElementById('templateLibraryBack');
    if (back) back.hidden = blueprintState.mode !== 'templates' || view === 'list';
}

function showTemplateLibrary() {
    templateBrowser.navigationSequence++;
    setTemplateManagerView('list');
    renderTemplateLibrary();
}

function resumeTemplateDraft() {
    if (!templateBrowser.hasDraft) return;
    setTemplateManagerView('edit');
    setBlueprintStudioView(blueprintState.templatePanelOpen ? 'save' : 'fields');
}

function templateFilterOptions(id, options, value, placeholder) {
    const control = document.getElementById(id);
    if (!control) return;
    control.replaceChildren(new Option(placeholder, ''));
    for (const [key, label] of options) control.add(new Option(label, key));
    control.value = value;
}

function renderTemplateFilters() {
    const templates = savedCreationTemplates(blueprintState.templates);
    const scoped = templates.filter(item => !templateBrowser.provider || item.provider === templateBrowser.provider);
    templateFilterOptions('templateFilterProvider', new Map(templates.map(item =>
        [item.provider, creationProviderLabel(item.provider)])), templateBrowser.provider, '全部渠道');
    templateFilterOptions('templateFilterAccount', new Map(scoped.map(item =>
        [item.account_id || '__general__', item.account_id || '通用 · 不限账号'])), templateBrowser.account, '全部账号');
    templateFilterOptions('templateFilterFormat', new Map(scoped.map(item =>
        [item.ad_format || '', templateFormatLabel(item)])), templateBrowser.format, '全部广告类型');
}

function applyTemplateFilters(changed) {
    if (changed === 'provider') {
        templateBrowser.provider = document.getElementById('templateFilterProvider').value;
        templateBrowser.account = '';
        templateBrowser.format = '';
    } else {
        templateBrowser.account = document.getElementById('templateFilterAccount').value;
        templateBrowser.format = document.getElementById('templateFilterFormat').value;
    }
    templateBrowser.q = document.getElementById('templateFilterQuery').value.trim();
    templateBrowser.status = document.getElementById('templateFilterStatus').value;
    templateBrowser.limit = Number(document.getElementById('templatePageSize').value);
    templateBrowser.page = 1;
    renderTemplateLibrary();
}

function changeTemplatePage(direction) {
    templateBrowser.page += direction;
    renderTemplateLibrary();
    document.getElementById('templateLibrary')?.scrollTo({top: 0});
}

function templateRowActions(template, detail = false) {
    const id = escapeHtml(template.template_id).replaceAll('"', '&quot;');
    const editable = templateIsEditable(template);
    return `<div class="template-row-actions">
        ${detail ? '' : `<button type="button" data-id="${id}" onclick="openTemplateDetail(this.dataset.id)">详情</button>`}
        ${editable ? `<button type="button" data-id="${id}" onclick="editTemplateFromLibrary(this.dataset.id)">编辑</button>` : ''}
        <button type="button" data-id="${id}" onclick="duplicateSelectedCreationTemplate(this.dataset.id)">复制</button>
        ${editable ? `<button type="button" class="danger" data-id="${id}" onclick="deleteSelectedCreationTemplate(this.dataset.id)">删除</button>` : ''}
    </div>`;
}

function renderTemplateLibrary() {
    const target = document.getElementById('templateLibraryRows');
    if (!target) return;
    renderTemplateFilters();
    const result = templateCatalogPage(blueprintState.templates, templateBrowser);
    templateBrowser.page = result.page;
    target.innerHTML = result.items.length ? result.items.map(item => `
        <tr class="template-table-row">
            <td><button type="button" class="template-name" data-id="${escapeHtml(item.template_id).replaceAll('"', '&quot;')}" onclick="openTemplateDetail(this.dataset.id)">${escapeHtml(item.name || '未命名模板')}</button><p>${escapeHtml(item.description || (item.is_default ? '默认模板' : ''))}</p></td>
            <td data-label="渠道">${escapeHtml(creationProviderLabel(item.provider))}</td>
            <td data-label="账号">${escapeHtml(item.account_id || '通用 · 不限账号')}</td>
            <td data-label="广告类型">${escapeHtml(templateFormatLabel(item))}</td>
            <td data-label="状态"><span>${item.status === 'active' ? '已启用' : '已停用'}</span><small>${[item.is_default ? '默认模板' : '',templateIsEditable(item) ? '' : '只读'].filter(Boolean).join(' · ')}</small></td>
            <td>${templateRowActions(item)}</td>
        </tr>`).join('') : `<tr><td colspan="6" class="monitoring-empty">${templateBrowser.loading ? '正在读取模板…' : savedCreationTemplates(blueprintState.templates).length
            ? '没有匹配的模板，请调整筛选。' : '还没有保存的模板。点击“新建模板”，选择渠道和广告类型，从蓝图预设开始填写，保存后即可在这里编辑和管理。'}</td></tr>`;
    document.getElementById('templatePageInfo').textContent = `共 ${result.total} 条 · 第 ${result.page} / ${result.pages} 页`;
    document.getElementById('templatePrevious').disabled = result.page <= 1;
    document.getElementById('templateNext').disabled = result.page >= result.pages;
    document.getElementById('templateResumeDraft').hidden = !templateBrowser.hasDraft;
}

function templateParameterGroups(template) {
    const blueprint = blueprintState.items.find(item => item.id === template.blueprint_id);
    const fields = new Map((blueprint?.fields || []).map(field => [field.path, field]));
    const groups = new Map();
    const values = template.values || {};
    const paths = [...fields.keys()].filter(path => Object.hasOwn(values, path))
        .concat(Object.keys(values).filter(path => !fields.has(path)));
    for (const path of paths) {
        const field = fields.get(path);
        const group = field ? creationDirectoryHierarchy(field) : '其他参数';
        if (!groups.has(group)) groups.set(group, []);
        groups.get(group).push({path, label: field?.label || path, value: values[path]});
    }
    return [...groups].map(([label, fields]) => `<section class="template-parameter-group"><h3>${escapeHtml(label)}</h3>
        <table><thead><tr><th scope="col">参数</th><th scope="col">已保存的值</th></tr></thead><tbody>${fields.map(field => `<tr>
            <td>${escapeHtml(field.label)}<small>${escapeHtml(field.path)}</small></td>
            <td><pre>${escapeHtml(typeof field.value === 'object' ? JSON.stringify(field.value, null, 2) : String(field.value ?? ''))}</pre></td>
        </tr>`).join('')}</tbody></table></section>`).join('') || '<p class="monitoring-empty">此模板尚未保存参数。</p>';
}

async function openTemplateDetail(id) {
    const sequence = ++templateBrowser.navigationSequence;
    if (!blueprintState.catalogLoaded && !await ensureTemplateEditorCatalog()) return;
    if (sequence !== templateBrowser.navigationSequence) return;
    const template = blueprintState.templates.find(item => item.template_id === id);
    if (!template) return;
    templateBrowser.selectedId = id;
    setTemplateManagerView('detail');
    const metadata = [
        ['渠道', creationProviderLabel(template.provider)], ['账号', template.account_id || '通用 · 不限账号'],
        ['广告类型', templateFormatLabel(template)], ['来源', template.source === 'builtin' ? '内置 · 只读' : '自建'],
        ['状态', template.status === 'active' ? '已启用' : '已停用'],
        ['验证', creationTemplateVerificationLabel(template.verification_status)],
    ];
    document.getElementById('templateDetail').innerHTML = `<header class="template-detail-heading"><div><h2>${escapeHtml(template.name || '未命名模板')}</h2><p>${escapeHtml(template.description || '')}</p></div>${templateRowActions(template, true)}</header>
        <dl class="template-detail-meta">${metadata.map(([label, value]) => `<div><dt>${label}</dt><dd>${escapeHtml(value)}</dd></div>`).join('')}</dl>
        ${template.required_inputs?.length ? `<p class="template-required-note">使用时需补充：${escapeHtml(template.required_inputs.join('、'))}</p>` : ''}
        ${templateParameterGroups(template)}`;
    document.getElementById('templateDetail').scrollTop = 0;
}

async function editTemplateFromLibrary(id) {
    const template = blueprintState.templates.find(item => item.template_id === id);
    if (!template) return;
    if (!templateIsEditable(template)) {
        openTemplateDetail(id);
        showBlueprintNotice('此模板为只读配置，可以复制后编辑。');
        return;
    }
    const sequence = ++templateBrowser.navigationSequence;
    if (!blueprintState.catalogLoaded && !await ensureTemplateEditorCatalog()) return;
    if (sequence !== templateBrowser.navigationSequence) return;
    templateBrowser.hasDraft = true;
    setTemplateManagerView('edit');
    blueprintState.accountId = template.account_id || '';
    selectCreationTemplate(id);
}
