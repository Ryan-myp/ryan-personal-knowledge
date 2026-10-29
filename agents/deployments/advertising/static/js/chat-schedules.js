/* Task list -> one task's paged occurrences -> existing result reader. */
const schedulePages = {
    selectedId: '', selected: null,
    tasks: {page: 1, limit: 20, q: '', status: ''},
    runs: {page: 1, limit: 20, q: '', status: '', since: ''},
};

function schedulePageParams(kind) {
    const state = schedulePages[kind];
    const params = new URLSearchParams({page: state.page, limit: state.limit});
    for (const key of ['q', 'status', 'since']) {
        if (state[key]) params.set(key, state[key]);
    }
    return params.toString();
}

function renderSchedulePagination(kind, pagination, count) {
    const page = pagination || {page: 1, pages: 1, total: count, limit: 20};
    schedulePages[kind].page = page.page;
    const prefix = kind === 'tasks' ? 'scheduleTasks' : 'scheduleRuns';
    document.getElementById(`${prefix}PageInfo`).textContent =
        `共 ${page.total} 条 · 第 ${page.page} / ${page.pages} 页`;
    document.getElementById(`${prefix}Previous`).disabled = page.page <= 1;
    document.getElementById(`${prefix}Next`).disabled = page.page >= page.pages;
}

function scheduleTaskActions(item) {
    const id = escapeHtml(item.schedule_id);
    const busy = Boolean(item.has_pending_run) || scheduleActionsPending.has(item.schedule_id);
    return `<div class="schedule-row-actions">
        <button type="button" data-id="${id}" onclick="showScheduleHistory(this.dataset.id)">查看运行历史</button>
        <button type="button" data-id="${id}" onclick="editSchedule(this.dataset.id)">编辑</button>
        <button type="button" data-id="${id}" data-action="${item.status === 'paused' ? 'resume' : 'pause'}" onclick="scheduleAction(this.dataset.id,this.dataset.action,this)">${item.status === 'paused' ? '恢复' : '暂停'}</button>
        <button type="button" data-id="${id}" ${busy ? 'disabled aria-busy="true"' : ''} onclick="scheduleAction(this.dataset.id,'run-now',this)">${busy ? scheduleStatusLabel(item.latest_run_status || 'queued') : '立即执行'}</button>
        <button class="danger" type="button" data-id="${id}" onclick="scheduleAction(this.dataset.id,'delete',this)">删除</button>
    </div>`;
}

function renderSchedules(data) {
    const items = Array.isArray(data.schedules) ? data.schedules : [];
    schedulesById = new Map(items.map(item => [String(item.schedule_id), item]));
    document.getElementById('scheduleList').innerHTML = items.length ? `<table class="schedule-task-table" aria-label="定时任务">
        <colgroup><col><col class="schedule-plan-column"><col class="schedule-stats-column"><col class="schedule-actions-column"></colgroup>
        <thead><tr><th scope="col">任务</th><th scope="col">执行计划</th><th scope="col">运行统计</th><th scope="col">操作</th></tr></thead>
        <tbody>${items.map(item => `
        <tr class="schedule-row">
            <td class="schedule-row-main">
                <div class="schedule-row-title"><button class="schedule-title-link" type="button" data-id="${escapeHtml(item.schedule_id)}" onclick="showScheduleHistory(this.dataset.id)">${escapeHtml(item.name || '未命名任务')}</button><span class="schedule-status ${escapeHtml(item.status || '')}">${scheduleStatusLabel(item.status)}</span></div>
                <p>${escapeHtml(item.prompt_preview || item.prompt || '')}</p>
            </td>
            <td class="schedule-row-plan">
                <div class="schedule-plan-expression"><span>${escapeHtml(item.cron_expression || '—')}</span><small>${escapeHtml(item.timezone || '')}</small></div>
                <small class="schedule-next-run">下次 ${escapeHtml(scheduleDisplayTime(item.next_run_at))}</small>
            </td>
            <td class="schedule-row-counts"><div class="schedule-row-stats"><span>成功 <strong>${monitoringNumber(item.success_count || 0)}</strong></span><span>失败 <strong>${monitoringNumber(item.failure_count || 0)}</strong></span><span>总计 <strong>${monitoringNumber(item.run_count || 0)}</strong></span></div></td>
            <td class="schedule-row-controls">${scheduleTaskActions(item)}</td>
        </tr>`).join('')}</tbody></table>` : '<div class="monitoring-empty">没有匹配的任务。可以调整筛选，或在对话中创建定时任务。</div>';
    renderSchedulePagination('tasks', data.pagination, items.length);
}

function scheduleRunDuration(run) {
    if (!run.started_at || !run.finished_at) return '—';
    const elapsed = new Date(run.finished_at) - new Date(run.started_at);
    return Number.isFinite(elapsed) && elapsed >= 0 ? monitoringAge(elapsed / 1000) : '—';
}

function renderScheduleRuns(data) {
    const runs = Array.isArray(data.runs) ? data.runs : [];
    scheduleRunsById = new Map(runs.map(run => [String(run.schedule_run_id), run]));
    document.getElementById('scheduleRunRows').innerHTML = runs.length ? runs.map(run => `
        <tr><td>${escapeHtml(scheduleDisplayTime(run.scheduled_for))}<small class="schedule-instance-id">${escapeHtml(run.schedule_run_id || '')}</small></td>
        <td><span class="schedule-status ${escapeHtml(run.status || '')}">${scheduleStatusLabel(run.status)}</span></td>
        <td>${escapeHtml(scheduleRunDuration(run))}</td>
        <td class="schedule-run-summary">${escapeHtml(run.error || (['queued','running'].includes(run.status) ? '执行中，可查看当前结果' : '查看本次执行内容与结果'))}</td>
        <td><button class="btn btn-secondary" type="button" data-id="${escapeHtml(run.schedule_run_id)}" onclick="showScheduleRun(this.dataset.id)">查看结果</button></td></tr>`).join('')
        : '<tr><td colspan="5" class="monitoring-empty">没有匹配的运行历史，请调整筛选或稍后刷新。</td></tr>';
    renderSchedulePagination('runs', data.pagination, runs.length);
}

function renderScheduleHeader(schedule) {
    schedulePages.selected = schedule;
    schedulesById.set(String(schedule.schedule_id), schedule);
    document.getElementById('scheduleHistoryTitle').textContent = schedule.name ? `${schedule.name} · 运行历史` : '运行历史';
    document.getElementById('scheduleHistoryMeta').textContent =
        `${scheduleStatusLabel(schedule.status)} · ${schedule.cron_expression || ''} · ${schedule.timezone || ''}`;
    document.getElementById('scheduleHistoryPrompt').textContent = schedule.prompt || '';
}

async function loadSchedules() {
    stopScheduleRefresh();
    const sequence = ++scheduleRefreshSequence;
    const id = schedulePages.selectedId;
    document.getElementById('scheduleUpdated').textContent = '正在加载…';
    for (const kind of ['Tasks', 'Runs']) {
        document.getElementById(`schedule${kind}Previous`).disabled = true;
        document.getElementById(`schedule${kind}Next`).disabled = true;
    }
    try {
        let pending = false;
        if (id) {
            const [detail, data] = await Promise.all([
                apiFetch(`/schedules/${encodeURIComponent(id)}?include_runs=false`),
                apiFetch(`/schedules/${encodeURIComponent(id)}/runs?${schedulePageParams('runs')}`),
            ]);
            if (sequence !== scheduleRefreshSequence) return;
            renderScheduleHeader(detail.schedule);
            renderScheduleRuns(data);
            pending = (data.runs || []).some(run => ['queued','running'].includes(run.status));
        } else {
            const data = await apiFetch(`/schedules?${schedulePageParams('tasks')}`);
            if (sequence !== scheduleRefreshSequence) return;
            renderSchedules(data);
            pending = (data.schedules || []).some(item => item.has_pending_run);
        }
        document.getElementById('scheduleUpdated').textContent = `更新于 ${new Date().toLocaleTimeString('zh-CN')}`;
        if (pending && document.getElementById('scheduleOverlay')?.classList.contains('active')) {
            scheduleRefreshTimer = window.setTimeout(loadSchedules, 5000);
        }
    } catch (error) {
        if (sequence !== scheduleRefreshSequence) return;
        const message = escapeHtml(error.message || '读取失败，请点击刷新重试');
        document.getElementById('scheduleUpdated').textContent = '读取失败，请刷新重试';
        const target = document.getElementById(id ? 'scheduleRunRows' : 'scheduleList');
        target.innerHTML = id ? `<tr><td colspan="5">${message}</td></tr>` : `<div class="monitoring-empty">${message}</div>`;
        if (id) scheduleRunsById.clear();
    }
}

async function showScheduleHistory(id) {
    closeScheduleRun();
    closeScheduleEditor();
    if (schedulePages.selectedId !== id) {
        schedulePages.runs = {page: 1, limit: 20, q: '', status: '', since: ''};
        for (const field of ['Query', 'Status', 'Range']) document.getElementById(`scheduleRuns${field}`).value = '';
        document.getElementById('scheduleRunsSize').value = '20';
    }
    schedulePages.selectedId = id;
    document.getElementById('scheduleListView').hidden = true;
    document.getElementById('scheduleHistoryView').hidden = false;
    document.getElementById('scheduleHistoryTitle').textContent = '正在读取任务…';
    document.getElementById('scheduleHistoryMeta').textContent = '';
    document.getElementById('scheduleHistoryPrompt').textContent = '';
    document.getElementById('scheduleRunRows').innerHTML = '<tr><td colspan="5">正在读取运行历史…</td></tr>';
    await loadSchedules();
}

async function showScheduleList() {
    closeScheduleRun();
    closeScheduleEditor();
    schedulePages.selectedId = '';
    schedulePages.selected = null;
    document.getElementById('scheduleListView').hidden = false;
    document.getElementById('scheduleHistoryView').hidden = true;
    await loadSchedules();
}

async function applyScheduleFilters(kind) {
    const state = schedulePages[kind];
    const prefix = kind === 'tasks' ? 'scheduleTasks' : 'scheduleRuns';
    state.page = 1;
    state.limit = Number(document.getElementById(`${prefix}Size`).value) || 20;
    state.q = (document.getElementById(`${prefix}Query`).value || '').trim();
    state.status = document.getElementById(`${prefix}Status`).value || '';
    if (kind === 'runs') {
        const days = Number(document.getElementById('scheduleRunsRange').value);
        state.since = days ? new Date(Date.now() - days * 86400000).toISOString() : '';
    }
    closeScheduleRun();
    await loadSchedules();
}

async function changeSchedulePage(kind, direction) {
    schedulePages[kind].page = Math.max(1, schedulePages[kind].page + direction);
    closeScheduleRun();
    await loadSchedules();
}
