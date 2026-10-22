let creationImportState = null;
let creationImportRequestToken = 0;

function creationImportBlueprintKey(blueprint) {
    return `${String(blueprint?.id || '')}@${String(blueprint?.version || '')}`;
}

function creationImportStatus(message, isError = false) {
    const status = document.getElementById('blueprintImportStatus');
    if (!status) return;
    status.textContent = message || '';
    status.classList.toggle('error', Boolean(isError));
}

function openCreationImportPicker() {
    if (!blueprintState.selected || blueprintState.mode === 'templates') {
        showBlueprintNotice('请先选择广告类型，再导入配置表格。');
        return;
    }
    document.getElementById('blueprintImportFileInput')?.click();
}

async function handleCreationImportFile(event) {
    const input = event?.target;
    const file = input?.files?.[0];
    if (!file || !blueprintState.selected) return;
    input.value = '';
    const extension = String(file.name || '').toLowerCase().split('.').pop();
    if (!['csv', 'xlsx'].includes(extension)) {
        creationImportStatus('仅支持 CSV 和 XLSX 文件。', true);
        return;
    }
    if (!file.size || file.size > 20 * 1024 * 1024) {
        creationImportStatus('文件必须小于或等于 20 MiB。', true);
        return;
    }

    await clearCreationImport();
    const requestToken = ++creationImportRequestToken;
    const blueprintKey = creationImportBlueprintKey(blueprintState.selected);
    const panel = document.getElementById('blueprintImportPanel');
    panel.hidden = false;
    creationImportStatus(`正在安全读取 ${file.name}…`);
    document.getElementById('blueprintImportMapping')?.replaceChildren();
    document.getElementById('blueprintImportRows')?.replaceChildren();
    document.getElementById('blueprintImportPreviewButton').disabled = true;
    try {
        const activeSessionId = ensureChatMediaSession();
        const mediaType = extension === 'csv'
            ? 'text/csv'
            : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
        const query = new URLSearchParams({
            session_id: activeSessionId,
            filename: file.name,
        });
        const upload = await serviceFetch(`/chat/media?${query}`, {
            method: 'POST',
            headers: { 'Content-Type': mediaType },
            body: file,
        });
        const uploaded = await upload.json();
        if (!upload.ok) throw new Error(uploaded.detail || `上传失败（${upload.status}）`);
        if (
            requestToken !== creationImportRequestToken
            || blueprintKey !== creationImportBlueprintKey(blueprintState.selected)
        ) {
            await deleteCreationImportAttachment(activeSessionId, uploaded.id);
            return;
        }
        const nextState = {
            sessionId: activeSessionId,
            attachmentId: uploaded.id,
            filename: file.name,
            headers: [],
            fields: [],
            truncated: false,
            preview: null,
        };
        creationImportState = nextState;

        const inspect = await apiFetch('/creation-import/inspect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: activeSessionId,
                attachment_id: uploaded.id,
                blueprint_id: blueprintState.selected.id,
                version: blueprintState.selected.version,
            }),
        });
        if (
            requestToken !== creationImportRequestToken
            || creationImportState !== nextState
            || blueprintKey !== creationImportBlueprintKey(blueprintState.selected)
        ) return;
        nextState.headers = inspect.headers || [];
        nextState.fields = inspect.fields || [];
        nextState.truncated = Boolean(inspect.truncated);
        renderCreationImportMapping();
        creationImportStatus(
            `${Number(inspect.row_count) || 0} 行可预览${inspect.truncated ? '，文件超过 100 行，仅展示前 100 行' : ''}。未执行广告操作。`,
        );
    } catch (error) {
        if (requestToken !== creationImportRequestToken) return;
        creationImportStatus(error?.message || '表格读取失败。', true);
    }
}

function renderCreationImportMapping() {
    const container = document.getElementById('blueprintImportMapping');
    if (!container || !creationImportState) return;
    container.replaceChildren();
    const label = document.createElement('div');
    label.className = 'blueprint-import-map-label';
    label.textContent = `字段映射 · ${creationImportState.filename}`;
    container.appendChild(label);
    const fields = creationImportState.fields.slice(0, 80);
    fields.forEach(field => {
        const row = document.createElement('label');
        row.className = 'blueprint-import-map-row';
        const fieldLabel = document.createElement('span');
        fieldLabel.textContent = field.label || field.path;
        const select = document.createElement('select');
        select.dataset.fieldPath = field.path;
        const skip = document.createElement('option');
        skip.value = '';
        skip.textContent = '不导入';
        select.appendChild(skip);
        creationImportState.headers.forEach(header => {
            const option = document.createElement('option');
            option.value = header;
            option.textContent = header;
            select.appendChild(option);
        });
        const fieldKey = String(field.path || '').split('.').pop().toLowerCase();
        const labelKey = String(field.label || '').trim().toLowerCase();
        const match = creationImportState.headers.find(header => {
            const normalized = String(header).trim().toLowerCase();
            return normalized === fieldKey || (labelKey && normalized === labelKey);
        });
        if (match) select.value = match;
        row.append(fieldLabel, select);
        container.appendChild(row);
    });
    const previewButton = document.getElementById('blueprintImportPreviewButton');
    if (previewButton) previewButton.disabled = !fields.length;
}

async function previewCreationImport() {
    if (!creationImportState || !blueprintState.selected) return;
    const state = creationImportState;
    const blueprintKey = creationImportBlueprintKey(blueprintState.selected);
    const mapping = {};
    document.querySelectorAll('#blueprintImportMapping select[data-field-path]').forEach(select => {
        if (select.value) mapping[select.dataset.fieldPath] = select.value;
    });
    if (!Object.keys(mapping).length) {
        creationImportStatus('至少映射一个 Blueprint 字段。', true);
        return;
    }
    const button = document.getElementById('blueprintImportPreviewButton');
    button.disabled = true;
    creationImportStatus('正在逐行校验…');
    try {
        const result = await apiFetch('/creation-import/preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: creationImportState.sessionId,
                attachment_id: creationImportState.attachmentId,
                blueprint_id: blueprintState.selected.id,
                version: blueprintState.selected.version,
                column_mapping: mapping,
            }),
        });
        if (
            creationImportState !== state
            || blueprintKey !== creationImportBlueprintKey(blueprintState.selected)
        ) return;
        state.mapping = mapping;
        state.preview = result;
        renderCreationImportRows(result);
        const suffix = result.truncated ? ' · 仅预览前 100 行' : '';
        document.getElementById('blueprintImportSummary').textContent =
            `${result.ready_count || 0} 行满足必填条件，${result.invalid_count || 0} 行需要检查${suffix}`;
        creationImportStatus('选择一行可将已映射值填入当前创建草稿；仍需人工检查并带入对话。');
    } catch (error) {
        if (creationImportState !== state) return;
        creationImportStatus(error?.message || '表格逐行校验失败。', true);
    } finally {
        if (creationImportState === state && button) button.disabled = false;
    }
}

function renderCreationImportRows(result) {
    const container = document.getElementById('blueprintImportRows');
    if (!container) return;
    container.replaceChildren();
    const rows = Array.isArray(result.rows) ? result.rows : [];
    if (!rows.length) {
        const empty = document.createElement('div');
        empty.className = 'blueprint-import-empty';
        empty.textContent = '表格没有可预览的数据行。';
        container.appendChild(empty);
        return;
    }
    rows.forEach((row, index) => {
        const item = document.createElement('button');
        item.type = 'button';
        item.className = `blueprint-import-row${row.ready ? ' ready' : ' needs-review'}`;
        item.addEventListener('click', () => applyCreationImportRow(index));
        const heading = document.createElement('strong');
        heading.textContent = `第 ${row.row_number} 行 · ${row.ready ? '可用' : '需检查'}`;
        const details = document.createElement('span');
        const problems = [
            ...(row.missing_fields || []).map(path => `缺少 ${path}`),
            ...(row.invalid_fields || []).map(path => `无效 ${path}`),
        ];
        const fieldSummary = Object.entries(row.values || {})
            .map(([key, value]) => `${key}: ${typeof value === 'object' ? JSON.stringify(value) : value}`)
            .join(' · ');
        details.textContent = [
            problems.join('；'),
            fieldSummary,
        ].filter(Boolean).join(' | ') || '空白行';
        item.append(heading, details);
        container.appendChild(item);
    });
}

function creationImportNestedValue(source, path) {
    let value = source;
    for (const part of String(path || '').split('.').filter(Boolean)) {
        if (!value || typeof value !== 'object') return undefined;
        value = value[part];
    }
    return value;
}

async function applyCreationImportRow(index) {
    const row = creationImportState?.preview?.rows?.[index];
    const blueprint = blueprintState.selected;
    if (!row || !blueprint) return;
    const prior = { ...blueprintState.values };
    for (const fieldPath of Object.keys(creationImportState.mapping || {})) {
        const value = creationImportNestedValue(row.values, fieldPath);
        if (value === undefined) delete blueprintState.values[fieldPath];
        else blueprintState.values[fieldPath] = value;
    }
    blueprintState.previousValues = prior;
    await evaluateBlueprintDraft(null, false);
    showBlueprintNotice(
        `已将第 ${row.row_number} 行填入草稿。${row.ready ? '' : '该行仍有缺失或无效字段，请检查后再继续。'}`,
    );
}

async function clearCreationImport() {
    creationImportRequestToken += 1;
    const previous = creationImportState;
    creationImportState = null;
    const panel = document.getElementById('blueprintImportPanel');
    if (panel) panel.hidden = true;
    document.getElementById('blueprintImportMapping')?.replaceChildren();
    document.getElementById('blueprintImportRows')?.replaceChildren();
    const summary = document.getElementById('blueprintImportSummary');
    if (summary) summary.textContent = '';
    creationImportStatus('');
    if (!previous?.attachmentId) return;
    await deleteCreationImportAttachment(previous.sessionId, previous.attachmentId);
}

async function deleteCreationImportAttachment(sessionId, attachmentId) {
    if (!attachmentId) return;
    const query = new URLSearchParams({ session_id: sessionId });
    try {
        await serviceFetch(
            `/chat/media/${encodeURIComponent(attachmentId)}?${query}`,
            { method: 'DELETE' },
        );
    } catch (error) {
        console.warn(
            'creation import attachment cleanup failed',
            String(error?.message || 'unknown error'),
        );
        showBlueprintNotice('导入附件未能立即清理，仍受当前用户和会话权限隔离。');
    }
}

document.getElementById('blueprintImportFileInput')?.addEventListener(
    'change',
    handleCreationImportFile,
);
