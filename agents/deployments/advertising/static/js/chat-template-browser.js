/* Template management navigation; the existing blueprint editor owns parameter editing. */
const templateBrowser = {
    view: 'list', q: '', provider: '', account: '', format: '', status: '',
    page: 1, limit: 20, selectedId: '', hasDraft: false,
    loaded: false, loading: false, navigationSequence: 0,
};

let templateLibraryLoadPromise = null;
let templateEditorLoadPromise = null;
const templateBlueprintCache = new Map();

async function loadTemplateBlueprint(template) {
    const version = template.blueprint_version;
    const current = blueprintState.items.find(item => item.id === template.blueprint_id && item.version === version);
    if (current) return current;
    const key = `${template.blueprint_id}@${version}`;
    if (templateBlueprintCache.has(key)) return templateBlueprintCache.get(key);
    const data = await apiFetch(`/creation-blueprints/${encodeURIComponent(template.blueprint_id)}?version=${encodeURIComponent(version)}`);
    if (data.blueprint?.id !== template.blueprint_id || data.blueprint?.version !== version) {
        throw new Error('返回的蓝图版本与模板不一致，已停止加载。');
    }
    if (templateBlueprintCache.size >= 64) templateBlueprintCache.delete(templateBlueprintCache.keys().next().value);
    templateBlueprintCache.set(key, data.blueprint);
    return data.blueprint;
}

function templateVerificationMarkup(template) {
    const info = template.verification;
    if (!info) return '<section class="template-verification"><h3>验证记录</h3><p>当前模板没有绑定版本与参数的实测记录。</p></section>';
    const states = {passed:'已通过', failed:'未通过', partial:'部分通过', not_run:'未验证', unknown:'未知'};
    const operations = info.match === 'historical' ? info.historical_operations : info.operations;
    const rows = (operations || []).map(item => `<tr><td>${escapeHtml(item.scope)}</td><td>${escapeHtml(states[item.state] || '未知')}</td></tr>`).join('');
    return `<section class="template-verification"><h3>${escapeHtml(info.label || '验证记录')}</h3>
        ${info.verified_at ? `<p>记录日期：${escapeHtml(info.verified_at)}</p>` : ''}
        ${info.match === 'historical' ? '<h4>历史版本操作记录</h4>' : ''}
        ${rows ? `<table><thead><tr><th scope="col">操作范围</th><th scope="col">结果</th></tr></thead><tbody>${rows}</tbody></table>` : ''}
        ${(info.blockers || []).map(item => `<p class="template-verification-warning">${escapeHtml(item)}</p>`).join('')}
        <p>${escapeHtml(info.notice || '')}</p></section>`;
}

function templateVerificationDisclosure(template) {
    return `<details class="template-verification-disclosure"><summary>模板验证记录 · ${escapeHtml(template.verification?.label || '待验证')}</summary>
        <p>以下记录针对原模板保存的参数；本次修改及账户资源仍需重新校验。</p>
        ${templateVerificationMarkup(template)}</details>`;
}

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
            .then(() => {
                const loaded = Boolean(blueprintState.catalogLoaded);
                if (loaded) showBlueprintNotice('');
                return loaded;
            })
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
    if (typeof blueprintSelectionSequence !== 'undefined') blueprintSelectionSequence++;
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

function templateParameterGroups(template, pinnedBlueprint = null) {
    const blueprint = pinnedBlueprint || blueprintState.items.find(item =>
        item.id === template.blueprint_id && item.version === template.blueprint_version);
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
    let blueprint;
    try { blueprint = await loadTemplateBlueprint(template); }
    catch (error) { showBlueprintNotice(error.message || '固定蓝图读取失败。'); return; }
    if (sequence !== templateBrowser.navigationSequence) return;
    templateBrowser.selectedId = id;
    templateBrowser.upgradePreview = null;
    setTemplateManagerView('detail');
    const metadata = [
        ['渠道', creationProviderLabel(template.provider)], ['账号', template.account_id || '通用 · 不限账号'],
        ['广告类型', templateFormatLabel(template)], ['来源', template.source === 'builtin' ? '内置 · 只读' : '自建'],
        ['状态', template.status === 'active' ? '已启用' : '已停用'],
        ['验证', creationTemplateVerificationLabel(template.verification_status)],
        ['蓝图版本', template.blueprint_version || '未固定'],
    ];
    const latest = blueprintState.items.find(item => item.id === template.blueprint_id);
    const upgrade = latest && latest.version !== template.blueprint_version;
    document.getElementById('templateDetail').innerHTML = `<header class="template-detail-heading"><div><h2>${escapeHtml(template.name || '未命名模板')}</h2><p>${escapeHtml(template.description || '')}</p></div>${templateRowActions(template, true)}</header>
        <dl class="template-detail-meta">${metadata.map(([label, value]) => `<div><dt>${label}</dt><dd>${escapeHtml(value)}</dd></div>`).join('')}</dl>
        ${upgrade ? `<div class="template-version-row"><span>可升级至 ${escapeHtml(latest.version)}</span>
            <button type="button" onclick="previewTemplateUpgrade()">预览升级</button></div>` : ''}
        <div id="templateUpgradePreview" aria-live="polite"></div>
        ${templateVerificationMarkup(template)}
        ${template.required_inputs?.length ? `<p class="template-required-note">使用时需补充：${escapeHtml(template.required_inputs.join('、'))}</p>` : ''}
        ${templateParameterGroups(template, blueprint)}`;
    document.getElementById('templateDetail').scrollTop = 0;
}

async function previewTemplateUpgrade() {
    const id = templateBrowser.selectedId;
    const sequence = templateBrowser.navigationSequence;
    const target = document.getElementById('templateUpgradePreview');
    if (!target || !id) return;
    templateBrowser.upgradePreview = null;
    target.textContent = '正在核对版本差异…';
    try {
        const preview = await apiFetch(`/creation-templates/${encodeURIComponent(id)}/upgrade-preview`, {
            method:'POST', headers:{'Content-Type':'application/json'}, body:'{}',
        });
        if (sequence !== templateBrowser.navigationSequence || id !== templateBrowser.selectedId) return;
        templateBrowser.upgradePreview = preview;
        const groups = [
            ['新增字段',preview.added_fields], ['不再支持的已存参数',preview.removed_fields],
            ['约束或默认值变化',preview.changed_fields], ['需补充参数',preview.missing_fields],
            ['需修正参数',preview.invalid_fields],
        ];
        target.innerHTML = `<section class="template-upgrade"><h3>${escapeHtml(preview.source_version)} → ${escapeHtml(preview.target_version)}</h3>
            ${groups.filter(([,fields])=>fields?.length).map(([title,fields])=>`<details><summary>${escapeHtml(title)} · ${fields.length}</summary>
                <ul>${fields.map(field=>`<li>${escapeHtml(typeof field === 'string' ? field : field.path || field.field || '')}</li>`).join('')}</ul></details>`).join('')}
            <p>原模板保留。升级副本需重新选择账户资源并验证，历史实测状态不继承。</p>
            <button type="button" onclick="beginTemplateUpgrade()">编辑升级副本</button></section>`;
    } catch (error) {
        if (sequence === templateBrowser.navigationSequence) target.textContent = error.message || '升级预览失败。';
    }
}

function beginTemplateUpgrade() {
    const preview = templateBrowser.upgradePreview;
    if (!preview || preview.source_template_id !== templateBrowser.selectedId) return;
    const draft = {...preview.draft, template_id:'', source:'user'};
    templateBrowser.navigationSequence++;
    templateBrowser.hasDraft = true;
    blueprintState.creatingTemplate = true;
    setTemplateManagerView('edit');
    selectBlueprint(preview.blueprint.id, null, draft, false, preview.blueprint);
    blueprintState.templateSaveAsNew = true;
    showBlueprintNotice('升级副本尚未保存，原模板未改变。');
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
    await selectCreationTemplate(id);
}
