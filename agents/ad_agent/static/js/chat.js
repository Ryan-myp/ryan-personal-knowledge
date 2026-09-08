        let pendingRequest = null;
        let isSending = false;
        let sessionId = null;
        let apiCallCount = 0;
        let conversationCount = 0;
        let serviceApiKey = '';
        let conversationHistory = [];
        let selectedConversationId = null;
        let conversationHistoryRequest = 0;
        let historySelectionMode = false;
        const selectedConversationIds = new Set();
        let historySearchQuery = '';
        let pendingConversationDeleteIds = [];
        let pendingConversationRenameId = null;
        const loadedConversationTurnIds = new Set();
        let workspaceTheme = 'dark';
        const creationCardState = new Map();
        const creationCardEvaluationTimers = new Map();
        const creationCardEvaluationRevisions = new Map();
        const creationDirectoryCollapseState = new Map();
        let pendingBlueprintRequest = null;
        let pendingCreationReview = null;
        const skillState = {
            versions: [],
            selected: null,
            detail: null,
            files: [],
            readOnly: false,
            evaluationTimer: null,
            expanded: new Set(),
            activeFilePath: 'SKILL.md',
            previewMode: false,
        };
        const blueprintState = {
            items: [],
            selected: null,
            tools: [],
            values: {},
            previousValues: {},
            evaluation: null,
            loading: false,
            accountId: '',
            localFiles: {},
            selectionTokens: {},
            selectionTokenTools: {},
            lookupOptions: {},
            listQuery: '',
            listProvider: 'all',
            templates: [],
            selectedTemplateId: '',
            templatePanelOpen: false,
            templateSaveAsNew: false,
        };
        const knowledgeState = { items: [], selectedKey: '', summary: '', summaryMode: 'lexical', managedItems: [], editingDocumentId: '' };

        const TRACE_STATUS_LABELS = {
            planned: '计划中', running: '运行中', succeeded: '已成功',
            failed: '失败', skipped: '已跳过', awaiting_confirmation: '待确认',
            unknown: '待命', recovery_required: '需恢复'
        };
        let traceState = { nodes: [], events: [], selectedId: null, collapsed: false, expanded: false, activeTurn: 0, traceId: null, status: 'unknown', orderCounter: 0 };
        let durableRunPollTimer = null;
        let durableRunPollToken = 0;
        let activeDurableRunId = null;
        let durableRunSeq = 0;
        let monitoringRefreshTimer = null;
        let monitoringRequestToken = 0;

        function traceStatusLabel(status) {
            return TRACE_STATUS_LABELS[status] || '未知';
        }

        function traceMark(kind) {
            const marks = { Agent: 'A', Skill: 'S', Guard: 'G', Tool: 'T', Meta: 'M', Google: 'G', TikTok: 'T', DV360: 'D', stage: '✦', intent: '◎', analysis: '◌', reply: '↗' };
            return marks[kind] || '·';
        }

        function traceEventLabel(event) {
            const labels = {
                start: 'Agent 回合开始', plan: '执行计划已生成', node_started: 'Tool 开始执行',
                node_status: 'Tool 状态更新', confirmation: '等待用户确认', reply: '回复已准备',
                stage_started: '阶段开始', stage_status: '阶段状态更新',
                done: '回合结束', error: '执行异常'
            };
            const node = event.node_id ? ` · ${event.title || event.tool || event.node_id}` : '';
            return `${labels[event.type] || '执行事件'}${node}`;
        }

        function pushTraceEvent(event) {
            traceState.events.push({ ...event, receivedAt: Date.now() });
            if (traceState.events.length > 80) traceState.events.shift();
        }

        let traceFilter = { platform: 'all', status: 'all', kind: 'all' };
        let workspaceMode = {
            mode: '', loading: false, saving: false, liveAvailable: false, liveReason: ''
        };

        function closeWorkspacePopovers() {
            for (const [popoverId, buttonId] of [['modePopover', 'modeToggleButton'], ['filterPopover', 'filterToggleButton']]) {
                document.getElementById(popoverId)?.classList.remove('active');
                const button = document.getElementById(buttonId);
                button?.classList.remove('active');
                button?.setAttribute('aria-expanded', 'false');
            }
            document.getElementById('knowledgeOverlay')?.classList.remove('active');
            document.getElementById('knowledgeOverlay')?.setAttribute('aria-hidden', 'true');
            document.getElementById('knowledgeNavButton')?.classList.remove('active');
            document.getElementById('knowledgeNavButton')?.setAttribute('aria-expanded', 'false');
            document.getElementById('blueprintOverlay')?.classList.remove('active');
            document.getElementById('blueprintOverlay')?.setAttribute('aria-hidden', 'true');
            document.getElementById('systemOpsMenu')?.classList.remove('active');
            document.getElementById('systemOpsButton')?.classList.remove('active');
            document.getElementById('systemOpsButton')?.setAttribute('aria-expanded', 'false');
            document.getElementById('monitoringOverlay')?.classList.remove('active');
            document.getElementById('monitoringOverlay')?.setAttribute('aria-hidden', 'true');
            document.getElementById('scheduleOverlay')?.classList.remove('active');
            document.getElementById('scheduleOverlay')?.setAttribute('aria-hidden', 'true');
            document.getElementById('memoryOverlay')?.classList.remove('active');
            document.getElementById('memoryOverlay')?.setAttribute('aria-hidden', 'true');
            if (monitoringRefreshTimer) window.clearTimeout(monitoringRefreshTimer);
            monitoringRefreshTimer = null;
        }

        function toggleSystemOpsMenu() {
            const menu = document.getElementById('systemOpsMenu');
            const button = document.getElementById('systemOpsButton');
            if (!menu || !button) return;
            const open = menu.classList.contains('active');
            closeWorkspacePopovers();
            if (!open) {
                menu.classList.add('active');
                button.classList.add('active');
                button.setAttribute('aria-expanded', 'true');
            }
        }

        function monitoringNumber(value) {
            return Number.isFinite(Number(value)) ? Number(value).toLocaleString('zh-CN') : '—';
        }

        function monitoringAge(value) {
            if (value === null || value === undefined) return '—';
            const seconds = Number(value);
            if (!Number.isFinite(seconds)) return '—';
            if (seconds < 60) return `${Math.round(seconds)} 秒`;
            if (seconds < 3600) return `${Math.round(seconds / 60)} 分钟`;
            return `${(seconds / 3600).toFixed(1)} 小时`;
        }

        function monitoringStatusLabel(status) {
            return ({ queued: '排队中', running: '运行中', cancelling: '取消中', paused: '已暂停', succeeded: '已成功', failed: '失败', cancelled: '已取消', recovery_required: '需恢复' })[status] || status;
        }

        function monitoringSetStatus(status, text) {
            const banner = document.getElementById('monitoringStatusBanner');
            const label = document.getElementById('monitoringStatusText');
            if (!banner || !label) return;
            banner.className = `monitoring-status-banner ${status === 'healthy' ? '' : status}`.trim();
            label.textContent = text;
        }

        function renderMonitoringToolTrend(timeline) {
            const svg = document.getElementById('monitoringToolTrend');
            const empty = document.getElementById('monitoringToolTrendEmpty');
            if (!svg || !empty) return;
            const points = Array.isArray(timeline) ? timeline : [];
            const width = 720;
            const height = 230;
            const padding = { top: 14, right: 14, bottom: 28, left: 30 };
            const plotWidth = width - padding.left - padding.right;
            const plotHeight = height - padding.top - padding.bottom;
            const maxValue = Math.max(1, ...points.flatMap(item => [Number(item.calls || 0), Number(item.failed || 0)]));
            const xFor = index => padding.left + (points.length <= 1 ? plotWidth / 2 : index / (points.length - 1) * plotWidth);
            const yFor = value => padding.top + plotHeight - Math.max(0, Number(value || 0)) / maxValue * plotHeight;
            const callPoints = points.map((item, index) => `${xFor(index).toFixed(1)},${yFor(item.calls).toFixed(1)}`).join(' ');
            const failedPoints = points.map((item, index) => `${xFor(index).toFixed(1)},${yFor(item.failed).toFixed(1)}`).join(' ');
            const areaPath = points.length
                ? `M ${padding.left},${padding.top + plotHeight} L ${callPoints.replace(/ /g, ' L ')} L ${padding.left + plotWidth},${padding.top + plotHeight} Z`
                : '';
            const yTicks = [0, maxValue / 2, maxValue];
            const grid = yTicks.map(value => {
                const y = yFor(value).toFixed(1);
                const label = Number.isInteger(value) ? String(value) : value.toFixed(1);
                return `<line class="monitoring-chart-grid" x1="${padding.left}" y1="${y}" x2="${padding.left + plotWidth}" y2="${y}"></line><text class="monitoring-chart-axis" x="${padding.left - 7}" y="${Number(y) + 3}" text-anchor="end">${label}</text>`;
            }).join('');
            const labels = points.map((item, index) => {
                if (index !== 0 && index !== points.length - 1 && index % 2 !== 0) return '';
                const label = String(item.label || '');
                return label ? `<text class="monitoring-chart-axis" x="${xFor(index).toFixed(1)}" y="${height - 7}" text-anchor="middle">${escapeHtml(label)}</text>` : '';
            }).join('');
            const dots = (key, className) => points.map((item, index) => `<circle class="monitoring-chart-point ${className}" cx="${xFor(index).toFixed(1)}" cy="${yFor(item[key]).toFixed(1)}" r="3"></circle>`).join('');
            svg.innerHTML = `<defs><linearGradient id="monitoringTrendFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#58e6d0" stop-opacity=".24"></stop><stop offset="100%" stop-color="#58e6d0" stop-opacity="0"></stop></linearGradient></defs>${grid}<path class="monitoring-chart-area" d="${areaPath}"></path><polyline class="monitoring-chart-line calls" points="${callPoints}"></polyline><polyline class="monitoring-chart-line failed" points="${failedPoints}"></polyline>${dots('calls', 'calls')}${dots('failed', 'failed')}${labels}`;
            const totalCalls = points.reduce((sum, item) => sum + Number(item.calls || 0), 0);
            const totalFailed = points.reduce((sum, item) => sum + Number(item.failed || 0), 0);
            const peak = points.reduce((highest, item) => Math.max(highest, Number(item.calls || 0)), 0);
            empty.hidden = totalCalls > 0;
            document.getElementById('monitoringTrendCalls').textContent = monitoringNumber(totalCalls);
            document.getElementById('monitoringTrendFailed').textContent = monitoringNumber(totalFailed);
            document.getElementById('monitoringTrendPeak').textContent = monitoringNumber(peak);
        }

        function renderMonitoringToolDonut(tools) {
            const donut = document.getElementById('monitoringToolDonut');
            const totalLabel = document.getElementById('monitoringToolDonutTotal');
            const legend = document.getElementById('monitoringToolDonutLegend');
            if (!donut || !totalLabel || !legend) return;
            const total = Math.max(0, Number(tools.total || 0));
            const failed = Math.min(total, Math.max(0, Number(tools.failed || 0)));
            const succeeded = total - failed;
            totalLabel.textContent = monitoringNumber(total);
            if (!total) {
                donut.style.background = '#162e40';
                legend.innerHTML = '<div class="monitoring-empty">最近窗口暂无 Tool 调用</div>';
                return;
            }
            const successPercent = succeeded / total * 100;
            donut.style.background = `conic-gradient(#58e6d0 0 ${successPercent}%, #ff817b ${successPercent}% 100%)`;
            legend.innerHTML = [
                ['成功', succeeded, '#58e6d0'],
                ['失败', failed, '#ff817b'],
            ].map(([label, value, color]) => `<div class="monitoring-donut-legend-item" style="--legend-color:${color}"><i></i><span>${label}</span><strong>${monitoringNumber(value)}</strong><small>${Math.round(Number(value) / total * 100)}% · 最近 1 小时</small></div>`).join('');
        }

        function monitoringToolTimeline(tools) {
            if (Array.isArray(tools.timeline) && tools.timeline.length) return tools.timeline;
            const total = Math.max(0, Number(tools.total || 0));
            if (!total) return [];
            const failed = Math.min(total, Math.max(0, Number(tools.failed || 0)));
            return Array.from({length: 12}, (_, index) => ({
                label: index === 11 ? '现在' : '',
                calls: index === 11 ? total : 0,
                failed: index === 11 ? failed : 0,
            }));
        }

        function renderMonitoring(snapshot) {
            const tasks = snapshot.tasks || {};
            const runs = snapshot.runs || {};
            const workflows = snapshot.workflows || {};
            const sessions = snapshot.sessions || {};
            const outbox = snapshot.outbox || {};
            const tools = snapshot.tools || {};
            const alerts = snapshot.alerts || {};
            const instance = snapshot.instance || {};
            const taskStatuses = tasks.by_status || {};
            const recovery = Number(alerts.recovery_required || 0);
            const expired = Number(alerts.expired_leases || 0);
            const expiring = Number(alerts.expiring_leases || 0);
            const successRate = tools.success_rate === null || tools.success_rate === undefined ? null : `${Math.round(Number(tools.success_rate) * 100)}%`;

            document.getElementById('monitoringQueueDepth').textContent = monitoringNumber(tasks.queued_depth || 0);
            document.getElementById('monitoringQueueHint').textContent = tasks.queued_oldest_age_seconds === null || tasks.queued_oldest_age_seconds === undefined
                ? '当前没有排队任务' : `最老任务已等 ${monitoringAge(tasks.queued_oldest_age_seconds)}`;
            document.getElementById('monitoringLeaseRisk').textContent = monitoringNumber(expired + expiring);
            document.getElementById('monitoringLeaseHint').textContent = `${monitoringNumber(expired)} 已过期 · ${monitoringNumber(expiring)} 即将过期`;
            document.getElementById('monitoringRecoveryCount').textContent = monitoringNumber(recovery);
            document.getElementById('monitoringRecoveryHint').textContent = `Task ${monitoringNumber(taskStatuses.recovery_required || 0)} · Run ${monitoringNumber(runs.by_status?.recovery_required || 0)} · Workflow ${monitoringNumber(workflows.by_status?.recovery_required || 0)}`;
            document.getElementById('monitoringToolSuccess').textContent = successRate || '—';
            document.getElementById('monitoringToolHint').textContent = `${monitoringNumber(tools.total || 0)} 次调用 · 平均 ${tools.avg_latency_ms == null ? '—' : `${Math.round(tools.avg_latency_ms)} ms`}`;
            renderMonitoringToolTrend(monitoringToolTimeline(tools));
            renderMonitoringToolDonut(tools);

            const counts = Object.entries(taskStatuses).sort((a, b) => Number(b[1]) - Number(a[1]));
            const maxCount = Math.max(1, ...counts.map(([, value]) => Number(value)));
            const bars = document.getElementById('monitoringTaskBars');
            bars.innerHTML = counts.length ? counts.map(([status, count]) => `
                <div class="monitoring-bar-row ${escapeHtml(status)}"><span>${escapeHtml(monitoringStatusLabel(status))}</span><div class="monitoring-bar-track"><div class="monitoring-bar-fill" style="width:${Math.max(3, Number(count) / maxCount * 100)}%"></div></div><strong class="monitoring-bar-count">${monitoringNumber(count)}</strong></div>
            `).join('') : '<div class="monitoring-empty">暂无持久化任务</div>';
            const executor = instance.task_executor || {};
            document.getElementById('monitoringTaskSubstats').innerHTML = [
                ['运行中', monitoringNumber(taskStatuses.running || 0)],
                ['本机占用', executor.in_process_tasks === undefined ? '—' : `${monitoringNumber(executor.in_process_tasks)} / ${monitoringNumber(executor.max_workers || 0)}`],
                ['最老排队', monitoringAge(tasks.queued_oldest_age_seconds)],
            ].map(([label, value]) => `<div class="monitoring-substat"><span>${label}</span><strong>${escapeHtml(value)}</strong></div>`).join('');

            const leaseItems = [
                ['Task lease', tasks.leases?.expired || 0, tasks.leases?.expiring_soon || 0],
                ['Workflow lease', workflows.leases?.expired || 0, workflows.leases?.expiring_soon || 0],
                ['Session lease', sessions.expired_leases || 0, 0],
                ['恢复待处理', recovery, 0],
            ];
            document.getElementById('monitoringLeaseList').innerHTML = leaseItems.map(([label, bad, soon]) => {
                const value = Number(bad) + Number(soon);
                const tone = Number(bad) ? 'danger' : Number(soon) ? 'warning' : '';
                return `<div class="monitoring-lease-row ${tone}"><span>${label}</span><strong>${monitoringNumber(value)}${soon ? ` <small>· ${monitoringNumber(soon)} 将到期</small>` : ''}</strong></div>`;
            }).join('');

            const outboxStatuses = outbox.by_status || {};
            document.getElementById('monitoringOutboxSummary').innerHTML = [
                ['待投递', outboxStatuses.pending || 0], ['消费中', outboxStatuses.claimed || 0], ['失败', outboxStatuses.failed || 0], ['重试中', outbox.retrying || 0],
            ].map(([label, value]) => `<span class="monitoring-event-chip"><strong>${monitoringNumber(value)}</strong>${label}</span>`).join('');
            document.getElementById('monitoringRunSummary').textContent = `Run：${monitoringNumber(runs.by_status?.running || 0)} 个运行中，${monitoringNumber(runs.by_status?.recovery_required || 0)} 个需要恢复；Workflow：${monitoringNumber(workflows.by_status?.running || 0)} 个运行中。`;

            const consumer = instance.outbox_consumer || {};
            document.getElementById('monitoringInstanceList').innerHTML = [
                ['Task worker', executor.state || '—', `${monitoringNumber(executor.in_process_tasks || 0)} 个执行中 · PID ${instance.process_id || '—'}`],
                ['Outbox consumer', consumer.state || '—', consumer.state === 'running' ? `每 ${consumer.poll_interval_seconds || '—'} 秒轮询` : '未运行'],
                ['Backend', snapshot.backend || '—', `${monitoringNumber(instance.platform_count || 0)} 个平台 · ${monitoringNumber(instance.tool_count || 0)} 个 Tool`],
            ].map(([label, value, hint]) => `<div class="monitoring-instance-row"><span>${label}<small>${hint}</small></span><strong>${escapeHtml(String(value))}</strong></div>`).join('');

            const toolRows = Array.isArray(tools.top_tools) ? tools.top_tools : [];
            document.getElementById('monitoringToolRows').innerHTML = toolRows.length ? toolRows.map(item => `<tr><td>${escapeHtml(item.tool_name || 'unknown')}</td><td>${escapeHtml(item.platform || '—')}</td><td>${monitoringNumber(item.calls || 0)}</td><td class="${item.failed ? 'monitoring-tool-failed' : ''}">${monitoringNumber(item.failed || 0)}</td></tr>`).join('') : '<tr><td colspan="4" class="monitoring-empty">最近窗口暂无 Tool 调用</td></tr>';

            const generated = snapshot.generated_at ? new Date(snapshot.generated_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—';
            document.getElementById('monitoringUpdated').textContent = `更新于 ${generated} · ${snapshot.backend || 'store'}`;
            const statusText = snapshot.status === 'critical' ? '需要处理：存在恢复项、已过期租约或失败事件' : snapshot.status === 'attention' ? '需要关注：存在排队、即将过期租约或轻微积压' : '运行平稳：当前权限范围内没有需要处理的运行风险';
            monitoringSetStatus(snapshot.status || 'healthy', statusText);
            const badge = document.getElementById('monitoringNavBadge');
            const badgeCount = recovery + expired + Number(outboxStatuses.failed || 0);
            if (badge) { badge.hidden = !badgeCount; badge.textContent = badgeCount > 99 ? '99+' : String(badgeCount); }
        }

        async function loadMonitoring(schedule = false) {
            const token = ++monitoringRequestToken;
            if (!document.getElementById('monitoringOverlay')?.classList.contains('active')) return;
            try {
                const snapshot = await apiFetch('/monitoring/overview');
                if (token !== monitoringRequestToken) return;
                renderMonitoring(snapshot);
            } catch (error) {
                if (token !== monitoringRequestToken) return;
                const message = error?.status === 404
                    ? '当前服务进程尚未加载监控接口（404）。请重启 ad-agent 服务后再刷新。'
                    : error?.status === 401 || error?.status === 403
                        ? '没有读取系统运维数据的权限，请检查服务 API Key 或 ads.read 权限。'
                        : error?.message || '监控数据读取失败';
                monitoringSetStatus('critical', message);
                document.getElementById('monitoringUpdated').textContent = '读取失败';
            } finally {
                if (schedule && document.getElementById('monitoringOverlay')?.classList.contains('active')) {
                    monitoringRefreshTimer = window.setTimeout(() => loadMonitoring(true), 15000);
                }
            }
        }

        function openMonitoring() {
            closeWorkspacePopovers();
            const overlay = document.getElementById('monitoringOverlay');
            if (!overlay) return;
            overlay.classList.add('active');
            overlay.setAttribute('aria-hidden', 'false');
            loadMonitoring(true);
        }

        function closeMonitoring() {
            document.getElementById('monitoringOverlay')?.classList.remove('active');
            document.getElementById('monitoringOverlay')?.setAttribute('aria-hidden', 'true');
            if (monitoringRefreshTimer) window.clearTimeout(monitoringRefreshTimer);
            monitoringRefreshTimer = null;
        }

        function scheduleStatusLabel(status) {
            return ({ active: '运行中', paused: '已暂停', disabled: '已停用', queued: '排队中', running: '执行中', succeeded: '成功', failed: '失败' })[status] || status || '—';
        }

        function renderSchedules(data) {
            const schedules = Array.isArray(data.schedules) ? data.schedules : [];
            const metrics = data.metrics || {};
            const taskStatuses = metrics.tasks_by_status || {};
            const runStatuses = metrics.runs_by_status || {};
            document.getElementById('scheduleTotal').textContent = monitoringNumber(schedules.length);
            document.getElementById('scheduleQueued').textContent = monitoringNumber(runStatuses.queued || 0);
            document.getElementById('scheduleRunning').textContent = monitoringNumber(runStatuses.running || 0);
            document.getElementById('scheduleFailed').textContent = monitoringNumber(runStatuses.failed || 0);
            const list = document.getElementById('scheduleList');
            list.innerHTML = schedules.length ? schedules.map(item => `
                <article class="schedule-row ${item.status === 'paused' ? 'paused' : ''}">
                    <div class="schedule-row-main"><div class="schedule-row-title"><strong>${escapeHtml(item.name || '未命名任务')}</strong><span class="schedule-status ${escapeHtml(item.status || '')}">${scheduleStatusLabel(item.status)}</span></div><p>${escapeHtml(item.prompt || '')}</p><small>${escapeHtml(item.cron_expression || '')} · ${escapeHtml(item.timezone || '')} · 下次 ${escapeHtml(item.next_run_at || '—')}</small></div>
                    <div class="schedule-row-stats"><span>成功 <strong>${monitoringNumber(item.success_count || 0)}</strong></span><span>失败 <strong>${monitoringNumber(item.failure_count || 0)}</strong></span><span>总计 <strong>${monitoringNumber(item.run_count || 0)}</strong></span></div>
                    <div class="schedule-row-actions"><button type="button" onclick="scheduleAction('${escapeHtml(item.schedule_id)}','${item.status === 'paused' ? 'resume' : 'pause'}')">${item.status === 'paused' ? '恢复' : '暂停'}</button><button type="button" onclick="scheduleAction('${escapeHtml(item.schedule_id)}','run-now')">立即执行</button><button class="danger" type="button" onclick="scheduleAction('${escapeHtml(item.schedule_id)}','delete')">删除</button></div>
                </article>`).join('') : '<div class="monitoring-empty">还没有定时任务。可以直接在 Chat 中说“每天 09:00 分析 account 下的 campaign performance”。</div>';
            const runs = Array.isArray(data.runs) ? data.runs : [];
            document.getElementById('scheduleRunRows').innerHTML = runs.length ? runs.map(run => `<tr><td>${escapeHtml(run.scheduled_for || '—')}</td><td>${escapeHtml(run.schedule_id || '—')}</td><td><span class="schedule-status ${escapeHtml(run.status || '')}">${scheduleStatusLabel(run.status)}</span></td><td>${escapeHtml(run.task_id || '—')}</td><td>${escapeHtml(run.error || '—')}</td></tr>`).join('') : '<tr><td colspan="5" class="monitoring-empty">暂无触发记录</td></tr>';
            document.getElementById('scheduleUpdated').textContent = `更新于 ${new Date().toLocaleTimeString('zh-CN')}`;
        }

        async function loadSchedules() {
            try {
                const [items, monitoring] = await Promise.all([apiFetch('/schedules?limit=100'), apiFetch('/monitoring/overview')]);
                const runs = [];
                for (const item of (items.schedules || []).slice(0, 100)) {
                    try { const detail = await apiFetch(`/schedules/${encodeURIComponent(item.schedule_id)}`); runs.push(...(detail.runs || []).slice(0, 5)); } catch (_) { /* list remains useful */ }
                }
                runs.sort((a, b) => String(b.scheduled_for || '').localeCompare(String(a.scheduled_for || '')));
                renderSchedules({ schedules: items.schedules || [], metrics: monitoring.schedules || {}, runs: runs.slice(0, 50) });
            } catch (error) {
                document.getElementById('scheduleList').innerHTML = `<div class="monitoring-empty">${escapeHtml(error.message || '定时任务读取失败')}</div>`;
            }
        }

        async function scheduleAction(scheduleId, action) {
            const labels = { pause: '暂停', resume: '恢复', delete: '删除', 'run-now': '立即执行' };
            if (action === 'delete' && !window.confirm('确认删除这个定时任务？历史执行记录也会被一并删除。')) return;
            try {
                const endpoint = action === 'delete'
                    ? `/schedules/${encodeURIComponent(scheduleId)}`
                    : `/schedules/${encodeURIComponent(scheduleId)}/${action}`;
                await apiFetch(endpoint, { method: action === 'delete' ? 'DELETE' : 'POST' });
                await loadSchedules();
            } catch (error) { window.alert(`${labels[action] || '操作'}失败：${error.message || '请稍后重试'}`); }
        }

        function openSchedules() {
            closeWorkspacePopovers();
            const overlay = document.getElementById('scheduleOverlay');
            if (!overlay) return;
            overlay.classList.add('active'); overlay.setAttribute('aria-hidden', 'false');
            loadSchedules();
        }

        function closeSchedules() {
            document.getElementById('scheduleOverlay')?.classList.remove('active');
            document.getElementById('scheduleOverlay')?.setAttribute('aria-hidden', 'true');
        }

        function applyTheme(theme) {
            workspaceTheme = theme === 'light' ? 'light' : 'dark';
            document.body.classList.toggle('light-theme', workspaceTheme === 'light');
            const label = document.getElementById('themeToggleLabel');
            const icon = document.getElementById('themeToggleIcon');
            if (label) label.textContent = workspaceTheme === 'light' ? '深色' : '浅色';
            if (icon) icon.textContent = workspaceTheme === 'light' ? '☾' : '☼';
            try { localStorage.setItem('ad-agent-theme', workspaceTheme); } catch (_) { /* storage may be disabled */ }
        }

        function initializeTheme() {
            let saved = 'dark';
            try { saved = localStorage.getItem('ad-agent-theme') || 'dark'; } catch (_) { /* use default */ }
            applyTheme(saved);
        }

        function toggleTheme() {
            applyTheme(workspaceTheme === 'light' ? 'dark' : 'light');
        }

        function toggleWorkspacePopover(popoverId, buttonId) {
            const popover = document.getElementById(popoverId);
            if (!popover) return;
            const open = popover.classList.contains('active');
            closeWorkspacePopovers();
            if (!open) {
                popover.classList.add('active');
                const button = document.getElementById(buttonId);
                button?.classList.add('active');
                button?.setAttribute('aria-expanded', 'true');
            }
        }

        function renderWorkspaceMode() {
            const title = document.getElementById('workspaceModeTitle');
            const description = document.getElementById('workspaceModeDescription');
            if (!title || !description) return;
            const toggleLabel = document.getElementById('modeToggleLabel');
            const toggleIcon = document.getElementById('modeToggleIcon');
            const select = document.getElementById('executionModeSelect');
            const apply = document.getElementById('workspaceModeApply');
            if (workspaceMode.loading) {
                title.textContent = '正在读取服务模式…';
                description.textContent = '正在读取当前 Runtime 的执行策略。';
                if (select) select.disabled = true;
                if (apply) apply.disabled = true;
                return;
            }
            if (workspaceMode.mode === 'live') {
                title.textContent = 'live 模式 · 受控执行';
                description.textContent = '受控写入；仍需权限、测试账户白名单和二次确认。';
                if (toggleLabel) toggleLabel.textContent = 'live';
                if (toggleIcon) toggleIcon.textContent = '●';
            } else {
                title.textContent = 'dry-run 模式 · 安全预览';
                description.textContent = '只生成计划与预览，不修改线上广告账户。';
                if (toggleLabel) toggleLabel.textContent = 'dry-run';
                if (toggleIcon) toggleIcon.textContent = '◈';
            }
            if (select) {
                select.disabled = workspaceMode.saving;
                if (select.value !== workspaceMode.mode) select.value = workspaceMode.mode || 'dry_run';
                const liveOption = select.querySelector('option[value="live"]');
                if (liveOption) {
                    liveOption.disabled = false;
                    liveOption.textContent = workspaceMode.liveAvailable
                        ? 'live · 受控执行'
                        : 'live · 受控执行（需开启）';
                    liveOption.title = workspaceMode.liveAvailable ? '' : (workspaceMode.liveReason || 'live 当前不可用');
                }
            }
            if (apply) apply.disabled = workspaceMode.saving || !workspaceMode.mode;
            const traceMode = document.getElementById('traceMode');
            if (traceMode) traceMode.textContent = workspaceMode.mode === 'live'
                ? 'live · 受控执行，写操作需确认'
                : 'dry-run · 不调用线上写 API';
        }

        async function refreshWorkspaceMode() {
            workspaceMode.loading = true;
            renderWorkspaceMode();
            try {
                const response = await authenticatedFetch('/health');
                const data = await response.json();
                workspaceMode.mode = data.execution_mode || 'dry_run';
                workspaceMode.liveAvailable = Boolean(data.live_mode_available);
                workspaceMode.liveReason = data.live_mode_reason || '';
            } catch (_) {
                workspaceMode.mode = 'dry_run';
                workspaceMode.liveAvailable = false;
                workspaceMode.liveReason = '暂时无法读取服务模式';
            } finally {
                workspaceMode.loading = false;
                renderWorkspaceMode();
            }
        }

        function clearWorkspaceModeStatus() {
            const status = document.getElementById('workspaceModeStatus');
            if (status) {
                status.textContent = '';
                status.className = 'workspace-mode-status';
            }
            const select = document.getElementById('executionModeSelect');
            if (select?.value === 'live' && !workspaceMode.liveAvailable && status) {
                status.textContent = workspaceMode.liveReason || 'live 当前不可用，请先完成服务端安全配置';
                status.className = 'workspace-mode-status warning';
            }
        }

        async function applyWorkspaceMode() {
            const select = document.getElementById('executionModeSelect');
            const status = document.getElementById('workspaceModeStatus');
            const mode = select?.value || 'dry_run';
            if (mode === 'live' && !workspaceMode.liveAvailable) {
                if (status) {
                    status.textContent = workspaceMode.liveReason || 'live 当前不可用，请先完成服务端安全配置';
                    status.className = 'workspace-mode-status error';
                }
                return;
            }
            workspaceMode.saving = true;
            clearWorkspaceModeStatus();
            renderWorkspaceMode();
            try {
                const response = await authenticatedFetch('/settings/execution-mode', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mode })
                });
                const text = await response.text();
                let data = {};
                try { data = text ? JSON.parse(text) : {}; } catch (_) { data = {}; }
                if (!response.ok) throw new Error(data.detail || data.error || `切换失败（${response.status}）`);
                workspaceMode.mode = data.mode || mode;
                workspaceMode.liveAvailable = Boolean(data.live_mode_available);
                workspaceMode.liveReason = data.live_mode_reason || '';
                if (status) {
                    status.textContent = data.message || '已切换当前会话模式，无需重启服务';
                    status.className = 'workspace-mode-status success';
                }
            } catch (error) {
                if (status) {
                    status.textContent = error.message || '模式切换失败';
                    status.className = 'workspace-mode-status error';
                }
            } finally {
                workspaceMode.saving = false;
                renderWorkspaceMode();
            }
        }

        function toggleModePopover() {
            toggleWorkspacePopover('modePopover', 'modeToggleButton');
            renderWorkspaceMode();
            if (!workspaceMode.mode && !workspaceMode.loading) refreshWorkspaceMode();
        }

        function toggleFilterPopover() {
            toggleWorkspacePopover('filterPopover', 'filterToggleButton');
        }

        function toggleKnowledgePopover() {
            const overlay = document.getElementById('knowledgeOverlay');
            if (!overlay) return;
            const open = overlay.classList.contains('active');
            closeWorkspacePopovers();
            if (!open) {
                overlay.classList.add('active');
                overlay.setAttribute('aria-hidden', 'false');
                document.getElementById('knowledgeNavButton')?.classList.add('active');
                document.getElementById('knowledgeNavButton')?.setAttribute('aria-expanded', 'true');
                loadKnowledgeCatalog();
                loadManagedKnowledgeDocuments();
            }
            const keyInput = document.getElementById('knowledgeApiKey');
            if (keyInput && !keyInput.value) keyInput.value = serviceApiKey;
        }

        function renderMemories(items) {
            const list = document.getElementById('memoryList');
            const count = document.getElementById('memoryCount');
            if (count) count.textContent = `${items.length} 条有效记忆`;
            if (!list) return;
            if (!items.length) {
                list.innerHTML = '<div class="memory-empty">还没有匹配的有效记忆。你也可以在对话中说“请记住……”来保存。</div>';
                return;
            }
            list.innerHTML = items.map(item => {
                const tags = (item.tags || []).map(tag => `<span>${escapeHtml(tag)}</span>`).join('');
                const score = Number(item.score || 0).toFixed(2);
                return `<article class="memory-item"><div class="memory-item-head"><span class="memory-kind">${escapeHtml(item.kind || 'semantic')}</span><time>${escapeHtml(conversationTime(item.updated_at) || item.updated_at || '—')}</time><button class="memory-delete" type="button" onclick="deleteMemory('${escapeHtml(item.memory_id || '')}')">删除</button></div><p>${escapeHtml(item.content || '')}</p><div class="memory-item-meta"><span>来源 ${escapeHtml(item.source || 'unknown')}</span><span>置信度 ${Number(item.confidence || 0).toFixed(2)}</span><span>相关度 ${score}</span>${item.memory_key ? `<code>${escapeHtml(item.memory_key)}</code>` : ''}</div><div class="memory-tags">${tags}</div></article>`;
            }).join('');
        }

        async function loadMemories() {
            const list = document.getElementById('memoryList');
            if (list) list.innerHTML = '<div class="memory-empty">正在读取记忆…</div>';
            try {
                const query = document.getElementById('memoryQuery')?.value.trim() || '';
                const data = await apiFetch(`/memory?query=${encodeURIComponent(query)}&limit=20`);
                renderMemories(data.memories || []);
                const updated = document.getElementById('memoryUpdated');
                if (updated) updated.textContent = `更新于 ${new Date().toLocaleTimeString('zh-CN')}`;
            } catch (error) {
                if (list) list.innerHTML = `<div class="memory-empty error">${escapeHtml(error.message || '记忆读取失败')}</div>`;
            }
        }

        async function saveMemory() {
            const status = document.getElementById('memoryWriteStatus');
            const content = document.getElementById('memoryContent')?.value.trim() || '';
            if (!content) { if (status) status.textContent = '请先填写记忆内容'; return; }
            if (status) status.textContent = '正在保存…';
            try {
                await apiFetch('/memory', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
                    content, kind: document.getElementById('memoryKind')?.value || 'semantic',
                    memory_key: document.getElementById('memoryKey')?.value.trim() || null,
                    importance: Number(document.getElementById('memoryImportance')?.value || 0.7),
                    confidence: 1, tags: (document.getElementById('memoryTags')?.value || '').split(',').map(item => item.trim()).filter(Boolean),
                }) });
                document.getElementById('memoryContent').value = '';
                if (status) status.textContent = '已保存；相同 Key 的旧版本会保留为 superseded。';
                await loadMemories();
            } catch (error) { if (status) status.textContent = error.message || '保存失败'; }
        }

        async function deleteMemory(memoryId) {
            if (!memoryId || !window.confirm('确认删除这条记忆？删除后不会再被召回。')) return;
            try { await apiFetch(`/memory/${encodeURIComponent(memoryId)}`, { method: 'DELETE' }); await loadMemories(); }
            catch (error) { window.alert(`删除失败：${error.message || '请稍后重试'}`); }
        }

        function openMemoryManager() {
            closeWorkspacePopovers();
            const overlay = document.getElementById('memoryOverlay');
            if (!overlay) return;
            overlay.classList.add('active'); overlay.setAttribute('aria-hidden', 'false');
            loadMemories();
        }

        function closeMemoryManager() {
            document.getElementById('memoryOverlay')?.classList.remove('active');
            document.getElementById('memoryOverlay')?.setAttribute('aria-hidden', 'true');
        }

        function traceNodeMatchesFilter(node) {
            if (traceFilter.status !== 'all' && node.state !== traceFilter.status) return false;
            if (traceFilter.kind !== 'all') {
                const isStage = node.kind === 'stage';
                if (traceFilter.kind === 'stage' && !isStage) return false;
                if (traceFilter.kind === 'tool' && isStage) return false;
            }
            if (traceFilter.platform === 'all') return true;
            if (traceFilter.platform === 'Runtime') return node.kind === 'stage' && !node.platform;
            return node.platform === traceFilter.platform;
        }

        function applyTraceFilters() {
            traceFilter = {
                platform: document.getElementById('tracePlatformFilter')?.value || 'all',
                status: document.getElementById('traceStatusFilter')?.value || 'all',
                kind: document.getElementById('traceKindFilter')?.value || 'all',
            };
            const total = traceState.nodes.length;
            const visible = traceState.nodes.filter(traceNodeMatchesFilter).length;
            const summary = document.getElementById('traceFilterSummary');
            if (summary) summary.textContent = traceFilter.platform === 'all' && traceFilter.status === 'all' && traceFilter.kind === 'all'
                ? '当前显示全部节点'
                : `当前显示 ${visible} / ${total} 个节点`;
            const button = document.getElementById('filterToggleButton');
            if (button) button.querySelector('.global-action-label').textContent = visible === total ? '筛选' : `筛选 · ${visible}`;
            renderExecutionTrace();
        }

        function clearTraceFilters() {
            for (const id of ['tracePlatformFilter', 'traceStatusFilter', 'traceKindFilter']) {
                const control = document.getElementById(id);
                if (control) control.value = 'all';
            }
            applyTraceFilters();
        }

        function setKnowledgeStatus(message, isError = false) {
            const status = document.getElementById('knowledgeStatus');
            if (!status) return;
            status.textContent = message || '';
            status.classList.toggle('error', isError);
        }

        function setKnowledgeWriteStatus(message, isError = false) {
            const status = document.getElementById('knowledgeWriteStatus');
            if (!status) return;
            status.textContent = message || '';
            status.classList.toggle('error', isError);
        }

        function toggleKnowledgeComposer() {
            const composer = document.getElementById('knowledgeComposer');
            const results = document.getElementById('knowledgeResults');
            if (!composer || !results) return;
            const active = !composer.classList.contains('active');
            if (active) {
                showKnowledgeManagementView();
                return;
            }
            composer.classList.toggle('active', active);
            results.classList.toggle('view-hidden', active);
            const toggle = document.getElementById('knowledgeComposeToggle');
            if (toggle) toggle.textContent = active ? '返回目录' : '管理文档';
            const catalogToggle = document.getElementById('knowledgeCatalogToggle');
            catalogToggle?.classList.toggle('active', !active);
            catalogToggle?.setAttribute('aria-pressed', String(!active));
            toggle?.classList.toggle('active', active);
            toggle?.setAttribute('aria-pressed', String(active));
        }

        function showKnowledgeManagementView(focusTitle = true) {
            const composer = document.getElementById('knowledgeComposer');
            const results = document.getElementById('knowledgeResults');
            const toggle = document.getElementById('knowledgeComposeToggle');
            if (!composer || !results) return;
            composer.classList.add('active');
            results.classList.add('view-hidden');
            if (toggle) { toggle.textContent = '返回目录'; toggle.classList.add('active'); toggle.setAttribute('aria-pressed', 'true'); }
            document.getElementById('knowledgeCatalogToggle')?.classList.remove('active');
            document.getElementById('knowledgeCatalogToggle')?.setAttribute('aria-pressed', 'false');
            loadManagedKnowledgeDocuments();
            if (focusTitle) document.getElementById('knowledgeTitle')?.focus();
        }

        function showKnowledgeSearchView() {
            const composer = document.getElementById('knowledgeComposer');
            const results = document.getElementById('knowledgeResults');
            const toggle = document.getElementById('knowledgeComposeToggle');
            composer?.classList.remove('active');
            results?.classList.remove('view-hidden');
            if (toggle) toggle.textContent = '管理文档';
            document.getElementById('knowledgeCatalogToggle')?.classList.add('active');
            document.getElementById('knowledgeCatalogToggle')?.setAttribute('aria-pressed', 'true');
            toggle?.classList.remove('active');
            toggle?.setAttribute('aria-pressed', 'false');
        }

        function setKnowledgeEditorMode(documentId = '') {
            knowledgeState.editingDocumentId = documentId || '';
            const editing = Boolean(knowledgeState.editingDocumentId);
            const cancel = document.getElementById('knowledgeCancelEditButton');
            const draftButton = document.getElementById('knowledgeSaveDraftButton');
            const publishButton = document.getElementById('knowledgeSavePublishButton');
            if (cancel) cancel.hidden = !editing;
            if (draftButton) draftButton.textContent = editing ? '保存修改' : '保存草稿';
            if (publishButton) publishButton.textContent = editing ? '保存并发布新版本' : '保存并发布';
        }

        function resetKnowledgeEditor() {
            setKnowledgeEditorMode('');
            for (const id of ['knowledgeTitle', 'knowledgeTags', 'knowledgeSource', 'knowledgeContent']) {
                const field = document.getElementById(id);
                if (field) field.value = id === 'knowledgeSource' ? 'user' : '';
            }
            const version = document.getElementById('knowledgeVersion');
            if (version) version.value = '1.0.0';
            const platform = document.getElementById('knowledgeWritePlatform');
            if (platform) platform.value = 'all';
            const type = document.getElementById('knowledgeWriteType');
            if (type) type.value = 'general';
            setKnowledgeWriteStatus('已清空编辑器；可以新增一篇知识。');
        }

        function renderManagedKnowledgeDocuments(items) {
            const list = document.getElementById('knowledgeManagedList');
            if (!list) return;
            knowledgeState.managedItems = Array.isArray(items) ? items : [];
            const toggle = document.getElementById('knowledgeComposeToggle');
            if (toggle && !document.getElementById('knowledgeComposer')?.classList.contains('active')) {
                toggle.textContent = knowledgeState.managedItems.length ? `管理文档 · ${knowledgeState.managedItems.length}` : '管理文档';
            }
            list.replaceChildren();
            if (!knowledgeState.managedItems.length) {
                const empty = document.createElement('div');
                empty.className = 'knowledge-managed-empty';
                empty.textContent = '当前没有自建文档。内置知识为只读；回到知识目录点击“复制为我的草稿”即可编辑并发布。';
                list.appendChild(empty);
                return;
            }
            knowledgeState.managedItems.forEach(item => {
                const row = document.createElement('article');
                row.className = 'knowledge-managed-item';
                const main = document.createElement('div');
                const title = document.createElement('strong');
                title.textContent = item.title || '未命名知识';
                const meta = document.createElement('span');
                meta.textContent = [item.status === 'published' ? '已发布' : item.status === 'deprecated' ? '已归档' : '草稿', item.platform || 'all', `v${item.version || '1.0.0'}`].join(' · ');
                main.append(title, meta);
                const actions = document.createElement('div');
                actions.className = 'knowledge-managed-actions';
                if (item.status !== 'deprecated') {
                    const edit = document.createElement('button');
                    edit.type = 'button'; edit.textContent = '编辑';
                    edit.onclick = () => editKnowledgeDocument(item.document_id);
                    actions.appendChild(edit);
                }
                if (item.status === 'draft') {
                    const publish = document.createElement('button');
                    publish.type = 'button'; publish.textContent = '发布';
                    publish.onclick = () => changeKnowledgePublication(item.document_id, true);
                    actions.appendChild(publish);
                } else if (item.status === 'published') {
                    const unpublish = document.createElement('button');
                    unpublish.type = 'button'; unpublish.textContent = '下线';
                    unpublish.onclick = () => changeKnowledgePublication(item.document_id, false);
                    actions.appendChild(unpublish);
                }
                const remove = document.createElement('button');
                remove.type = 'button'; remove.className = 'danger'; remove.textContent = item.status === 'published' ? '归档' : '删除';
                remove.onclick = () => deleteKnowledgeDocument(item.document_id, item.status);
                actions.appendChild(remove);
                row.append(main, actions);
                list.appendChild(row);
            });
        }

        async function loadManagedKnowledgeDocuments() {
            const list = document.getElementById('knowledgeManagedList');
            if (list && !knowledgeState.managedItems.length) list.innerHTML = '<div class="knowledge-managed-empty">正在加载知识文档…</div>';
            try {
                const data = await apiFetch('/knowledge/documents?limit=100');
                renderManagedKnowledgeDocuments(data.documents || []);
            } catch (error) {
                if (list) list.innerHTML = `<div class="knowledge-managed-empty error">${escapeHtml(error.message || '知识文档读取失败')}</div>`;
            }
        }

        async function editKnowledgeDocument(documentId) {
            try {
                const item = await apiFetch(`/knowledge/documents/${encodeURIComponent(documentId)}`);
                document.getElementById('knowledgeTitle').value = item.title || '';
                document.getElementById('knowledgeContent').value = item.content || '';
                document.getElementById('knowledgeWritePlatform').value = item.platform || 'all';
                document.getElementById('knowledgeWriteType').value = item.knowledge_type || 'general';
                document.getElementById('knowledgeVersion').value = item.version || '1.0.0';
                document.getElementById('knowledgeTags').value = (item.tags || []).join(', ');
                document.getElementById('knowledgeSource').value = item.source || 'user';
                setKnowledgeEditorMode(documentId);
                setKnowledgeWriteStatus(item.status === 'published' ? '正在编辑已发布版本；保存会生成新的草稿版本。' : '正在编辑草稿。');
                showKnowledgeManagementView(false);
                document.getElementById('knowledgeContent')?.focus();
            } catch (error) {
                setKnowledgeWriteStatus(error.message || '知识文档读取失败。', true);
            }
        }

        async function changeKnowledgePublication(documentId, publish) {
            try {
                await apiFetch(`/knowledge/documents/${encodeURIComponent(documentId)}/${publish ? 'publish' : 'unpublish'}`, { method: 'POST' });
                setKnowledgeWriteStatus(publish ? '知识已发布，Agent 后续可以检索。' : '知识已下线，Agent 不会再检索。');
                await Promise.all([loadManagedKnowledgeDocuments(), loadKnowledgeCatalog()]);
            } catch (error) { window.alert(`${publish ? '发布' : '下线'}失败：${error.message || '请稍后重试'}`); }
        }

        async function deleteKnowledgeDocument(documentId, status) {
            const prompt = status === 'published' ? '确认归档这篇已发布知识？归档后仍保留历史记录，但不再参与检索。' : '确认删除这篇草稿？删除后不可恢复。';
            if (!documentId || !window.confirm(prompt)) return;
            try {
                await apiFetch(`/knowledge/documents/${encodeURIComponent(documentId)}`, { method: 'DELETE' });
                if (knowledgeState.editingDocumentId === documentId) resetKnowledgeEditor();
                setKnowledgeWriteStatus(status === 'published' ? '知识已归档。' : '草稿已删除。');
                await Promise.all([loadManagedKnowledgeDocuments(), loadKnowledgeCatalog()]);
            } catch (error) { window.alert(`操作失败：${error.message || '请稍后重试'}`); }
        }

        async function handleKnowledgeFileUpload(event) {
            const input = event.target;
            const file = input?.files?.[0];
            if (!file) return;
            const extension = file.name.includes('.') ? file.name.split('.').pop().toLowerCase() : '';
            const supported = new Set(['md', 'markdown', 'txt', 'yaml', 'yml', 'json', 'csv']);
            try {
                if (!supported.has(extension)) throw new Error('目前只支持 Markdown、TXT、YAML、JSON、CSV 文件。');
                if (file.size > 60000 * 4) throw new Error('文件过大，请上传不超过 240 KB 的文本文件。');
                const content = await file.text();
                if (!content.trim()) throw new Error('文件内容为空，请选择有正文的文件。');
                if (content.length > 60000) throw new Error('文件正文超过 60,000 字，请精简后再上传。');
                const titleInput = document.getElementById('knowledgeTitle');
                if (titleInput && !titleInput.value.trim()) {
                    titleInput.value = file.name.replace(/\.[^.]+$/, '');
                }
                const contentInput = document.getElementById('knowledgeContent');
                if (contentInput) {
                    contentInput.value = content;
                    contentInput.dispatchEvent(new Event('input'));
                }
                setKnowledgeWriteStatus(`已导入 ${file.name}，请检查内容后保存。`);
            } catch (error) {
                setKnowledgeWriteStatus(error.message || '文件读取失败，请检查文件格式。', true);
            } finally {
                input.value = '';
            }
        }

        function formatKnowledgeMarkdown(markdown) {
            if (!String(markdown || '').trim()) return '<span class="knowledge-empty">暂无正文</span>';
            let source = String(markdown).replace(/\r\n?/g, '\n');
            if (/^---\s*\n/.test(source)) {
                source = source.replace(/^---\s*\n[\s\S]*?\n---\s*(?:\n|$)/, '');
            }
            const lines = source.split('\n');
            const output = [];
            const inline = value => {
                let html = escapeHtml(String(value || ''));
                const codeTokens = [];
                html = html.replace(/`([^`]+)`/g, (_, code) => {
                    const token = `@@KNOWLEDGE_INLINE_CODE_${codeTokens.length}@@`;
                    codeTokens.push(`<code>${code}</code>`);
                    return token;
                });
                html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
                html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
                html = html.replace(/~~(.+?)~~/g, '<del>$1</del>');
                html = html.replace(/\*([^*\n]+)\*/g, '<em>$1</em>');
                html = html.replace(/_([^_\n]+)_/g, '<em>$1</em>');
                return html.replace(/@@KNOWLEDGE_INLINE_CODE_(\d+)@@/g, (_, index) => codeTokens[Number(index)] || '');
            };
            const splitTableRow = line => {
                let value = String(line || '').trim().replace(/^\s{0,3}/, '');
                if (value.startsWith('|')) value = value.slice(1);
                if (value.endsWith('|')) value = value.slice(0, -1);
                const cells = [];
                let cell = '';
                let escaped = false;
                let inCode = false;
                for (let index = 0; index < value.length; index += 1) {
                    const character = value[index];
                    if (escaped) {
                        cell += character;
                        escaped = false;
                    } else if (character === '\\') {
                        escaped = true;
                    } else if (character === '`') {
                        inCode = !inCode;
                        cell += character;
                    } else if (character === '|' && !inCode) {
                        cells.push(cell.trim());
                        cell = '';
                    } else {
                        cell += character;
                    }
                }
                if (escaped) cell += '\\';
                cells.push(cell.trim());
                return cells;
            };
            const isTableDivider = line => {
                const cells = splitTableRow(line);
                return cells.length > 0 && cells.every(cell => /^:?-{1,}:?$/.test(cell));
            };
            const tableAlignment = cell => {
                const value = String(cell || '').trim();
                if (value.startsWith(':') && value.endsWith(':')) return 'center';
                if (value.endsWith(':')) return 'right';
                return 'left';
            };
            const renderTable = (headerLine, dividerLine, rows) => {
                const headers = splitTableRow(headerLine);
                const dividers = splitTableRow(dividerLine);
                const body = rows.map(splitTableRow);
                const alignments = headers.map((_, index) => tableAlignment(dividers[index] || ''));
                const cellAttrs = index => ` style="text-align:${alignments[index] || 'left'}"`;
                const headerHtml = headers.map((cell, index) => `<th${cellAttrs(index)}>${inline(cell)}</th>`).join('');
                const bodyHtml = body.map(row => {
                    const cells = headers.map((_, index) => `<td${cellAttrs(index)}>${inline(row[index] || '')}</td>`).join('');
                    return `<tr>${cells}</tr>`;
                }).join('');
                return `<div class="knowledge-table-wrap"><table class="knowledge-table"><thead><tr>${headerHtml}</tr></thead><tbody>${bodyHtml}</tbody></table></div>`;
            };
            const fenceMatch = line => String(line || '').trim().match(/^(`{3,}|~{3,})\s*([^ ]*)?\s*$/);
            let index = 0;
            while (index < lines.length) {
                const rawLine = lines[index];
                const trimmed = rawLine.trim();
                if (!trimmed) { index += 1; continue; }
                const fence = fenceMatch(trimmed);
                if (fence) {
                    const marker = fence[1][0];
                    const markerLength = fence[1].length;
                    const language = String(fence[2] || '').replace(/[^a-zA-Z0-9_-]/g, '');
                    const codeLines = [];
                    index += 1;
                    while (index < lines.length && !new RegExp(`^${marker}{${markerLength},}\\s*$`).test(lines[index].trim())) codeLines.push(lines[index++]);
                    if (index < lines.length) index += 1;
                    const languageClass = language ? ` class="language-${language}"` : '';
                    output.push(`<pre><code${languageClass}>${escapeHtml(codeLines.join('\n'))}</code></pre>`);
                    continue;
                }
                if (index + 1 < lines.length && trimmed.includes('|') && isTableDivider(lines[index + 1])) {
                    const tableRows = [];
                    index += 2;
                    while (index < lines.length && lines[index].trim() && lines[index].includes('|')) tableRows.push(lines[index++]);
                    output.push(renderTable(rawLine, lines[index - tableRows.length - 1], tableRows));
                    continue;
                }
                const heading = trimmed.match(/^(#{1,6})\s+(.+)$/);
                if (heading) {
                    const level = Math.min(4, heading[1].length);
                    output.push(`<h${level}>${inline(heading[2])}</h${level}>`);
                    index += 1;
                    continue;
                }
                if (/^([-*_])(?:\s*\1){2,}\s*$/.test(trimmed)) {
                    output.push('<hr>');
                    index += 1;
                    continue;
                }
                if (/^>\s?/.test(trimmed)) {
                    const quoteLines = [];
                    while (index < lines.length && /^>\s?/.test(lines[index].trim())) {
                        quoteLines.push(inline(lines[index].trim().replace(/^>\s?/, '')));
                        index += 1;
                    }
                    output.push(`<blockquote>${quoteLines.join('<br>')}</blockquote>`);
                    continue;
                }
                if (/^(?:[-*+]\s+|\d+[.)]\s+)/.test(trimmed)) {
                    const ordered = /^\d+[.)]\s+/.test(trimmed);
                    const items = [];
                    while (index < lines.length) {
                        const itemLine = lines[index].trim();
                        const match = ordered ? itemLine.match(/^\d+[.)]\s+(.+)$/) : itemLine.match(/^[-*+]\s+(.+)$/);
                        if (!match) break;
                        const task = match[1].match(/^\[([ xX])\]\s+(.+)$/);
                        const content = task ? `<span class="knowledge-task${task[1].toLowerCase() === 'x' ? ' complete' : ''}">${task[1].toLowerCase() === 'x' ? '✓' : '○'}</span>${inline(task[2])}` : inline(match[1]);
                        items.push(`<li>${content}</li>`);
                        index += 1;
                    }
                    output.push(`<${ordered ? 'ol' : 'ul'}>${items.join('')}</${ordered ? 'ol' : 'ul'}>`);
                    continue;
                }
                const paragraph = [trimmed];
                index += 1;
                while (index < lines.length && lines[index].trim()
                    && !/^(`{3,}|~{3,})|^#{1,6}\s+|^>\s?|^(?:[-*+]\s+|\d+[.)]\s+)/.test(lines[index].trim())
                    && !(lines[index].trim().includes('|') && index + 1 < lines.length && isTableDivider(lines[index + 1])) ) {
                    paragraph.push(lines[index].trim());
                    index += 1;
                }
                output.push(`<p>${paragraph.map(inline).join('<br>')}</p>`);
            }
            return output.join('');
        }

        function knowledgeItemKey(item, index) {
            return String(item.document_id || item.source_ref || item.title || index);
        }

        const knowledgeCategoryLabels = {
            system: '系统规范',
            platform_foundation: '平台基础',
            campaign_operations: '投放配置',
            optimization: '优化方法',
            measurement: '测量与报表',
            industry_playbooks: '行业打法',
            budget_bidding: '预算与出价',
            audience_targeting: '受众与定向',
            creative: '创意与素材',
            cross_platform_foundation: '跨平台基础',
            diagnostics: '诊断与排障',
            experimentation: '实验与学习',
            general: '通用知识',
        };

        function knowledgeCategoryLabel(value) {
            const key = String(value || 'general');
            return knowledgeCategoryLabels[key] || key.replace(/[-_]/g, ' ');
        }

        function selectKnowledgeResult(key) {
            const item = knowledgeState.items.find((entry, index) => knowledgeItemKey(entry, index) === key);
            const reader = document.getElementById('knowledgeReader');
            if (!item || !reader) return;
            knowledgeState.selectedKey = key;
            document.querySelectorAll('#knowledgeList .knowledge-list-item').forEach(node => {
                node.classList.toggle('active', node.dataset.key === key);
            });
            reader.replaceChildren();
            if (knowledgeState.summary) {
                const summaryCard = document.createElement('section');
                summaryCard.className = 'knowledge-summary';
                const summaryLabel = document.createElement('div');
                summaryLabel.className = 'knowledge-summary-label';
                summaryLabel.textContent = knowledgeState.summaryMode === 'llm' ? '检索总结 · 智能总结' : '检索总结 · 快速结论';
                const summaryBody = document.createElement('div');
                summaryBody.className = 'knowledge-summary-body';
                summaryBody.innerHTML = formatKnowledgeMarkdown(knowledgeState.summary);
                summaryCard.append(summaryLabel, summaryBody);
                reader.appendChild(summaryCard);
            }
            const header = document.createElement('header');
            header.className = 'knowledge-reader-header';
            const kicker = document.createElement('div');
            kicker.className = 'knowledge-reader-kicker';
            kicker.textContent = [item.platform || '通用', knowledgeCategoryLabel(item.category), item.knowledge_type || item.layer || 'general'].filter(Boolean).join(' / ');
            const title = document.createElement('h1');
            title.textContent = item.title || item.topic || item.document_id || '未命名知识';
            const badge = document.createElement('span');
            badge.className = 'knowledge-reader-badge';
            badge.textContent = item.confidence != null ? `可信度 ${Math.round(Number(item.confidence) * 100)}%` : '已发布';
            const meta = document.createElement('div');
            meta.className = 'knowledge-reader-meta';
            meta.textContent = [item.source_ref || item.source, item.version ? `v${item.version}` : '', item.updated_at ? `更新于 ${String(item.updated_at).slice(0, 10)}` : ''].filter(Boolean).join('  ·  ');
            header.append(kicker, title, badge, meta);
            const context = document.createElement('div');
            context.className = 'knowledge-reader-context';
            const headingPath = Array.isArray(item.heading_path) ? item.heading_path.filter(Boolean).join(' / ') : '';
            const chunkLabel = Number(item.chunk_count) > 1 ? `章节片段 ${Number(item.chunk_index || 0) + 1} / ${Number(item.chunk_count)}` : '完整章节';
            const matchedTerms = Array.isArray(item.matched_terms) ? item.matched_terms.filter(Boolean) : [];
            const coverage = Number(item.match_coverage || 0);
            const matchLabel = matchedTerms.length
                ? `命中 ${matchedTerms.length} 个词 · ${Math.round(coverage * 100)}%`
                : '';
            context.textContent = [headingPath || '文档正文', chunkLabel, matchLabel].filter(Boolean).join('  ·  ');
            const body = document.createElement('article');
            body.className = 'knowledge-reader-body';
            body.innerHTML = formatKnowledgeMarkdown(item.excerpt || '暂无正文');
            const actions = document.createElement('div');
            actions.className = 'knowledge-reader-actions';
            const isManaged = String(item.document_id || '').startsWith('managed:');
            if (isManaged) {
                const managedId = String(item.document_id).slice('managed:'.length);
                const edit = document.createElement('button');
                edit.type = 'button'; edit.textContent = '编辑文档';
                edit.onclick = () => editKnowledgeDocument(managedId);
                const unpublish = document.createElement('button');
                unpublish.type = 'button'; unpublish.textContent = '下线';
                unpublish.onclick = () => changeKnowledgePublication(managedId, false);
                const archive = document.createElement('button');
                archive.type = 'button'; archive.className = 'danger'; archive.textContent = '归档';
                archive.onclick = () => deleteKnowledgeDocument(managedId, 'published');
                actions.append(edit, unpublish, archive);
            } else {
                const readOnly = document.createElement('span');
                readOnly.className = 'knowledge-reader-readonly';
                readOnly.textContent = '内置 · 只读';
                const clone = document.createElement('button');
                clone.type = 'button'; clone.textContent = '复制为我的草稿';
                clone.onclick = () => cloneKnowledgeDocument(item);
                actions.append(readOnly, clone);
            }
            const footer = document.createElement('footer');
            footer.className = 'knowledge-reader-footer';
            footer.textContent = '仅作为 Agent 业务上下文使用，不会直接调用广告渠道接口。';
            header.append(actions);
            reader.append(header, context, body, footer);
        }

        function cloneKnowledgeDocument(item) {
            const platform = document.getElementById('knowledgeWritePlatform');
            const platformValue = String(item.platform || 'all');
            const platformOption = platform && Array.from(platform.options).some(option => option.value === platformValue) ? platformValue : 'all';
            document.getElementById('knowledgeTitle').value = `${item.title || item.topic || '未命名知识'}（我的版本）`;
            document.getElementById('knowledgeContent').value = item.excerpt || '';
            document.getElementById('knowledgeWritePlatform').value = platformOption;
            document.getElementById('knowledgeWriteType').value = item.knowledge_type || 'general';
            document.getElementById('knowledgeVersion').value = '1.0.0';
            document.getElementById('knowledgeTags').value = (item.tags || []).join(', ');
            document.getElementById('knowledgeSource').value = item.source || 'user';
            setKnowledgeEditorMode('');
            setKnowledgeWriteStatus('已复制内置知识，请检查内容后保存为我的草稿。');
            showKnowledgeManagementView(false);
            document.getElementById('knowledgeContent')?.focus();
        }

        function renderKnowledgeResults(results, summary = '', summaryMode = 'lexical') {
            const container = document.getElementById('knowledgeResults');
            const list = document.getElementById('knowledgeList');
            const reader = document.getElementById('knowledgeReader');
            const count = document.getElementById('knowledgeCatalogCount');
            if (!container || !list || !reader) return;
            knowledgeState.items = Array.isArray(results) ? results : [];
            knowledgeState.summary = summary || '';
            knowledgeState.summaryMode = summaryMode || 'lexical';
            knowledgeState.selectedKey = '';
            list.replaceChildren();
            if (count) count.textContent = `${knowledgeState.items.length} 条已发布知识`;
            if (!knowledgeState.items.length) {
                const emptyList = document.createElement('div');
                emptyList.className = 'knowledge-list-empty';
                emptyList.textContent = '没有匹配的已发布知识';
                list.appendChild(emptyList);
                reader.innerHTML = '<div class="knowledge-reader-empty"><span class="knowledge-reader-empty-mark">⌕</span><strong>没有找到相关知识</strong><span>换个关键词或平台试试</span></div>';
                return;
            }
            const groups = new Map();
            knowledgeState.items.forEach((item, index) => {
                const groupKey = `${item.platform || 'all'}::${item.category || item.layer || 'general'}`;
                if (!groups.has(groupKey)) groups.set(groupKey, []);
                groups.get(groupKey).push({ item, index });
            });
            groups.forEach((groupItems, groupKey) => {
                const [platform, category] = groupKey.split('::');
                const groupHeader = document.createElement('div');
                groupHeader.className = 'knowledge-list-group';
                const groupTitle = document.createElement('strong');
                groupTitle.textContent = `${platform === 'all' ? '通用' : platform} · ${knowledgeCategoryLabel(category)}`;
                const groupCount = document.createElement('span');
                groupCount.textContent = `${groupItems.length}`;
                groupHeader.append(groupTitle, groupCount);
                list.appendChild(groupHeader);
                groupItems.forEach(({ item, index }) => {
                const key = knowledgeItemKey(item, index);
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'knowledge-list-item';
                button.dataset.key = key;
                button.onclick = () => selectKnowledgeResult(key);
                const title = document.createElement('strong');
                title.textContent = item.title || item.topic || item.document_id || '未命名知识';
                const meta = document.createElement('span');
                meta.textContent = [item.subcategory || item.knowledge_type || item.layer || 'general', item.version ? `v${item.version}` : ''].filter(Boolean).join(' · ');
                const section = document.createElement('small');
                section.textContent = Array.isArray(item.heading_path) && item.heading_path.length ? item.heading_path.join(' / ') : '文档正文';
                button.append(title, meta, section);
                list.appendChild(button);
                });
            });
            selectKnowledgeResult(knowledgeItemKey(knowledgeState.items[0], 0));
        }

        async function searchKnowledge() {
            showKnowledgeSearchView();
            const query = document.getElementById('knowledgeQuery')?.value.trim() || '';
            const platform = document.getElementById('knowledgePlatform')?.value || '';
            if (!query) {
                await loadKnowledgeCatalog();
                return;
            }
            const keyInput = document.getElementById('knowledgeApiKey');
            if (keyInput?.value.trim()) serviceApiKey = keyInput.value.trim();
            setKnowledgeStatus('正在检索已发布知识…');
            try {
                const summarize = document.getElementById('knowledgeSmartSummary')?.checked || false;
                const params = new URLSearchParams({ query, limit: '10', summarize: String(summarize) });
                if (platform) params.set('platform', platform);
                const response = await authenticatedFetch(`/knowledge/search?${params.toString()}`);
                const text = await response.text();
                let data = {};
                try { data = text ? JSON.parse(text) : {}; } catch (_) { data = {}; }
                if (!response.ok) throw new Error(data.detail || data.error || `知识库请求失败（${response.status}）`);
                const results = Array.isArray(data.results) ? data.results : [];
                renderKnowledgeResults(results, data.summary || '', data.summary_mode || 'lexical');
                setKnowledgeStatus(summarize
                    ? `找到 ${results.length} 条已发布知识 · 已完成 BM25 检索与智能总结。`
                    : `找到 ${results.length} 条已发布知识 · 本地 BM25 快速检索完成。`);
            } catch (error) {
                renderKnowledgeResults([]);
                setKnowledgeStatus(error.message || '知识库暂时不可用。', true);
            }
        }

        async function loadKnowledgeCatalog() {
            const platform = document.getElementById('knowledgePlatform')?.value || '';
            setKnowledgeStatus('正在加载已发布知识目录…');
            try {
                const params = new URLSearchParams({ limit: '100' });
                if (platform) params.set('platform', platform);
                const response = await authenticatedFetch(`/knowledge/catalog?${params.toString()}`);
                const text = await response.text();
                let data = {};
                try { data = text ? JSON.parse(text) : {}; } catch (_) { data = {}; }
                if (!response.ok) throw new Error(data.detail || data.error || `知识目录请求失败（${response.status}）`);
                const results = Array.isArray(data.documents) ? data.documents : [];
                renderKnowledgeResults(results);
                setKnowledgeStatus(`知识目录 · ${Number(data.count ?? results.length)} 条已发布知识`);
            } catch (error) {
                renderKnowledgeResults([]);
                setKnowledgeStatus(error.message || '知识目录暂时不可用。', true);
            }
        }

        async function saveKnowledgeDocument(publishNow = false) {
            const title = document.getElementById('knowledgeTitle')?.value.trim() || '';
            const content = document.getElementById('knowledgeContent')?.value.trim() || '';
            const keyInput = document.getElementById('knowledgeApiKey');
            if (keyInput?.value.trim()) serviceApiKey = keyInput.value.trim();
            if (!title || !content) {
                setKnowledgeWriteStatus('请填写标题和 Markdown 正文。', true);
                return;
            }
            setKnowledgeWriteStatus('正在保存知识文档…');
            const payload = {
                title,
                content,
                platform: document.getElementById('knowledgeWritePlatform')?.value || 'all',
                knowledge_type: document.getElementById('knowledgeWriteType')?.value || 'general',
                tags: (document.getElementById('knowledgeTags')?.value || '').split(',').map(item => item.trim()).filter(Boolean),
                source: document.getElementById('knowledgeSource')?.value.trim() || 'user',
                version: document.getElementById('knowledgeVersion')?.value.trim() || '1.0.0',
                confidence: 0.8,
            };
            try {
                const editingId = knowledgeState.editingDocumentId;
                const created = await apiFetch(editingId ? `/knowledge/documents/${encodeURIComponent(editingId)}` : '/knowledge/documents', {
                    method: editingId ? 'PUT' : 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });
                if (publishNow) {
                    await apiFetch(`/knowledge/documents/${encodeURIComponent(created.document_id)}/publish`, { method: 'POST' });
                    setKnowledgeWriteStatus('已保存并发布；后续检索和 Agent 对话可以使用这份知识。');
                } else {
                    setKnowledgeWriteStatus(created.version_mode === 'new_draft' ? '已生成新版本草稿；发布后才会进入检索和 Agent 上下文。' : '已保存为草稿；发布后才会进入检索和 Agent 上下文。');
                }
                setKnowledgeEditorMode(publishNow || !created.version_mode ? '' : created.document_id);
                if (document.getElementById('knowledgeQuery')?.value.trim()) await searchKnowledge();
                else await loadKnowledgeCatalog();
                await loadManagedKnowledgeDocuments();
                if (publishNow || !editingId) resetKnowledgeEditor();
            } catch (error) {
                setKnowledgeWriteStatus(error.message || '知识文档保存失败，请检查权限和内容。', true);
            }
        }

        function formatTracePayload(payload, emptyText = '该步骤没有独立数据') {
            if (payload === undefined || payload === null) return emptyText;
            try {
                const formatted = JSON.stringify(payload, null, 2);
                return formatted || emptyText;
            } catch (_) {
                return String(payload);
            }
        }

        function renderTraceDetail(node) {
            const detail = document.getElementById('traceDetail');
            if (!node) {
                detail.innerHTML = '<div class="trace-detail-empty">选择一个步骤查看格式化的输入 / 输出摘要</div>';
                return;
            }
            detail.innerHTML = `
                <div class="trace-detail-head">
                    <div><div class="trace-detail-title">${escapeHtml(node.title)}</div><div class="trace-detail-subtitle">${escapeHtml(node.meta || '执行事件')}</div></div>
                    <button class="trace-detail-close" type="button" onclick="clearTraceSelection()" aria-label="关闭节点详情">×</button>
                </div>
                <dl class="trace-detail-grid">
                    <dt>${node.kind === 'stage' ? '阶段' : 'Tool'}</dt><dd>${escapeHtml(node.kind === 'stage' ? (node.title || '运行阶段') : (node.tool || '未绑定'))}</dd>
                    <dt>资源 / 动作</dt><dd>${escapeHtml([node.resource_type, node.action].filter(Boolean).join(' · ') || '通用执行节点')}</dd>
                    <dt>平台</dt><dd>${escapeHtml(node.platform || (node.kind === 'stage' ? 'Runtime' : node.kind) || 'Agent')}</dd>
                    <dt>状态</dt><dd>${escapeHtml(traceStatusLabel(node.state))}</dd>
                    <dt>耗时</dt><dd>${node.duration_ms != null ? escapeHtml(`${node.duration_ms} ms`) : '进行中 / 未记录'}</dd>
                    <dt>门禁结果</dt><dd>${escapeHtml(node.reason || '—')}</dd>
                    <dt>摘要</dt><dd>${escapeHtml(node.subtitle || '已脱敏 · 仅展示安全摘要')}</dd>
                </dl>
                <div class="trace-io">
                    <section class="trace-io-block">
                        <div class="trace-io-label">输入 · 已脱敏</div>
                        <pre>${escapeHtml(formatTracePayload(node.input))}</pre>
                    </section>
                    <section class="trace-io-block">
                        <div class="trace-io-label">输出 · 已脱敏</div>
                        <pre>${escapeHtml(formatTracePayload(node.output, '步骤完成后显示结果'))}</pre>
                    </section>
                </div>
                <div class="trace-safe-note">输入和输出均为脱敏、限长后的业务摘要；不展示模型内部思维链或认证凭证。</div>
            `;
        }

        function renderExecutionTrace() {
            const flow = document.getElementById('traceFlow');
            if (!flow) return;
            flow.replaceChildren();
            flow.classList.remove('has-nodes');
            flow.style.removeProperty('--trace-line-end');
            const visibleNodes = traceState.nodes.filter(traceNodeMatchesFilter);
            const filterSummary = document.getElementById('traceFilterSummary');
            if (filterSummary) filterSummary.textContent = traceFilter.platform === 'all' && traceFilter.status === 'all' && traceFilter.kind === 'all'
                ? '当前显示全部节点'
                : `当前显示 ${visibleNodes.length} / ${traceState.nodes.length} 个节点`;
            const filterButton = document.getElementById('filterToggleButton');
            if (filterButton) {
                const filterLabel = filterButton.querySelector('.global-action-label');
                if (filterLabel) filterLabel.textContent = visibleNodes.length === traceState.nodes.length ? '筛选' : `筛选 · ${visibleNodes.length}`;
            }
            if (!traceState.nodes.length) {
                const empty = document.createElement('div');
                empty.className = 'trace-empty';
                empty.innerHTML = traceState.status === 'running'
                    ? '<div><strong>等待 Agent 事件</strong>Runtime 正在生成本回合真实执行计划…</div>'
                    : '<div><strong>本回合未产生 Tool 执行</strong>发送请求后，这里只显示真实计划与 Tool 状态。</div>';
                flow.appendChild(empty);
            } else if (!visibleNodes.length) {
                const empty = document.createElement('div');
                empty.className = 'trace-empty';
                empty.innerHTML = '<div><strong>没有匹配的步骤</strong>请调整筛选条件。</div>';
                flow.appendChild(empty);
            }
            for (const node of [...visibleNodes].sort((a, b) => (a.order || 0) - (b.order || 0))) {
                const item = document.createElement('button');
                item.type = 'button';
                item.className = `trace-node ${node.state || 'unknown'}${traceState.selectedId === node.id ? ' selected' : ''}`;
                item.setAttribute('aria-label', `${node.title}，${traceStatusLabel(node.state)}`);
                item.innerHTML = `
                    <span class="trace-node-mark">${escapeHtml(traceMark(node.kind || node.platform))}</span>
                    <span class="trace-node-copy"><span class="trace-node-title">${escapeHtml(node.title)}</span><span class="trace-node-meta">${escapeHtml(node.meta || node.tool || '')}</span></span>
                    <span class="trace-node-state">${escapeHtml(traceStatusLabel(node.state))}</span>
                `;
                item.addEventListener('click', () => {
                    traceState.selectedId = node.id;
                    renderExecutionTrace();
                    renderTraceDetail(node);
                });
                flow.appendChild(item);
            }
            const lastNode = flow.querySelector('.trace-node:last-of-type');
            if (lastNode) {
                flow.classList.add('has-nodes');
                flow.style.setProperty('--trace-line-end', `${lastNode.offsetTop + (lastNode.offsetHeight / 2)}px`);
            }
            for (const ticker of [document.getElementById('traceTicker'), document.getElementById('globalTraceTicker')]) {
                if (!ticker) continue;
                ticker.replaceChildren();
                for (const event of traceState.events.slice(-5)) {
                    const row = document.createElement('div');
                    row.className = 'trace-ticker-row';
                    const state = event.status || 'unknown';
                    const time = event.receivedAt ? new Date(event.receivedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—';
                    row.innerHTML = `<span class="trace-ticker-dot ${escapeHtml(state)}"></span><span>${escapeHtml(traceEventLabel(event))}</span><span class="trace-ticker-time">${escapeHtml(time)}</span>`;
                    ticker.appendChild(row);
                }
            }
            renderTraceDetail(traceState.nodes.find(node => node.id === traceState.selectedId));
        }

        function updateTraceHeader(status, subtitle) {
            const label = document.getElementById('traceStatus');
            const dot = document.querySelector('.trace-live-dot');
            const sub = document.getElementById('traceSubtitle');
            if (label) label.textContent = traceStatusLabel(status);
            if (sub) sub.textContent = subtitle || '等待下一次 Agent 回合';
            if (dot) dot.classList.toggle('idle', status === 'planned' || status === 'unknown' || status === 'succeeded' || status === 'failed');
            traceState.status = status;
        }

        function resetExecutionTrace() {
            traceState = { nodes: [], events: [], selectedId: null, collapsed: false, expanded: traceState.expanded, activeTurn: traceState.activeTurn, traceId: null, status: 'unknown', orderCounter: 0 };
            document.body.classList.remove('trace-collapsed');
            document.body.classList.toggle('trace-expanded', traceState.expanded);
            document.querySelector('.right-panel')?.classList.remove('trace-collapsed');
            updateTraceHeader('unknown', '等待下一次 Agent 回合');
            renderExecutionTrace();
        }

        function restoreExecutionTrace(traceHistory) {
            const snapshots = Object.values(traceHistory || {})
                .filter(item => item && Array.isArray(item.events) && item.events.length);
            resetExecutionTrace();
            if (!snapshots.length) {
                updateTraceHeader('unknown', '该历史对话暂无可恢复的执行轨迹');
                return;
            }
            // A conversation can contain several turns; the right panel is
            // the detail view for the most recent turn, matching the live UI.
            const snapshot = snapshots[snapshots.length - 1];
            for (const event of snapshot.events) applyExecutionEvent(event);
            const done = [...snapshot.events].reverse().find(event => event.type === 'done');
            updateTraceHeader(
                done?.status || snapshot.status || 'succeeded',
                '已恢复本次对话最近一轮的执行轨迹',
            );
            renderExecutionTrace();
        }

        function stopDurableRunPolling() {
            durableRunPollToken += 1;
            if (durableRunPollTimer) {
                clearTimeout(durableRunPollTimer);
                durableRunPollTimer = null;
            }
            activeDurableRunId = null;
            durableRunSeq = 0;
        }

        function applyDurableRun(run, { reset = true } = {}) {
            if (!run || !Array.isArray(run.events)) return;
            if (reset) resetExecutionTrace();
            for (const event of run.events) applyExecutionEvent(event);
            durableRunSeq = Math.max(
                Number(run.latest_seq || 0),
                ...run.events.map(event => Number(event.seq || 0)),
            );
            if (run.status === 'recovery_required') {
                updateTraceHeader('recovery_required', run.recovery_message || '服务中断，需先回查 Provider 后恢复');
            } else if (run.status) {
                updateTraceHeader(run.status, run.status === 'running' ? '服务重启后正在恢复本次执行现场' : '已恢复最近一次 Agent 执行轨迹');
            }
            renderExecutionTrace();
        }

        function scheduleDurableRunPoll(delay = 1000) {
            if (!activeDurableRunId) return;
            const token = durableRunPollToken;
            if (durableRunPollTimer) clearTimeout(durableRunPollTimer);
            durableRunPollTimer = setTimeout(() => pollDurableRun(token), delay);
        }

        async function pollDurableRun(token) {
            if (token !== durableRunPollToken || !activeDurableRunId) return;
            try {
                const run = await apiFetch(
                    `/runs/${encodeURIComponent(activeDurableRunId)}/events?after_seq=${durableRunSeq}&limit=256`,
                );
                if (token !== durableRunPollToken) return;
                applyDurableRun(run, { reset: false });
                if (run.status === 'running') scheduleDurableRunPoll(1000);
                else stopDurableRunPolling();
            } catch (_) {
                if (token === durableRunPollToken) scheduleDurableRunPoll(2000);
            }
        }

        async function loadLatestDurableRun(targetSessionId) {
            stopDurableRunPolling();
            if (!targetSessionId) return;
            const token = durableRunPollToken;
            try {
                const response = await authenticatedFetch(
                    `/sessions/${encodeURIComponent(targetSessionId)}/runs/latest`,
                );
                if (!response.ok) return;
                const run = await response.json();
                if (token !== durableRunPollToken || sessionId !== targetSessionId) return;
                activeDurableRunId = run.run_id || null;
                if (
                    ['running', 'recovery_required'].includes(run.status)
                    && run.metadata?.user_input
                    && !loadedConversationTurnIds.has(run.turn_id)
                ) {
                    addMessage(run.metadata.user_input, 'user');
                    loadedConversationTurnIds.add(run.turn_id);
                }
                applyDurableRun(run);
                if (run.status === 'running') scheduleDurableRunPoll(500);
                else stopDurableRunPolling();
            } catch (_) {
                // Older deployments may not expose durable run replay yet.
            }
        }

        function toggleTracePanel() {
            traceState.collapsed = !traceState.collapsed;
            if (traceState.collapsed) {
                traceState.expanded = false;
                document.body.classList.remove('trace-expanded');
            }
            document.body.classList.toggle('trace-collapsed', traceState.collapsed);
            document.querySelector('.right-panel')?.classList.toggle('trace-collapsed', traceState.collapsed);
            const button = document.querySelector('.trace-header-actions .trace-icon-btn:not(.trace-expand-btn)');
            if (button) {
                button.textContent = traceState.collapsed ? '+' : '−';
                button.setAttribute('aria-label', traceState.collapsed ? '展开执行轨迹' : '收起执行轨迹');
                button.setAttribute('title', traceState.collapsed ? '展开执行轨迹' : '收起执行轨迹');
            }
        }

        function toggleTraceExpanded() {
            if (traceState.collapsed) {
                traceState.collapsed = false;
                document.body.classList.remove('trace-collapsed');
                document.querySelector('.right-panel')?.classList.remove('trace-collapsed');
                const collapseButton = document.querySelector('.trace-header-actions .trace-icon-btn:not(.trace-expand-btn)');
                if (collapseButton) {
                    collapseButton.textContent = '−';
                    collapseButton.setAttribute('aria-label', '收起执行轨迹');
                    collapseButton.setAttribute('title', '收起执行轨迹');
                }
            }
            traceState.expanded = !traceState.expanded;
            document.body.classList.toggle('trace-expanded', traceState.expanded);
            const button = document.querySelector('.trace-expand-btn');
            if (button) {
                button.setAttribute('aria-label', traceState.expanded ? '收窄轨迹视图' : '展开轨迹视图');
                button.setAttribute('title', traceState.expanded ? '收窄轨迹视图' : '展开轨迹视图');
            }
        }

        function clearTraceSelection() {
            traceState.selectedId = null;
            renderExecutionTrace();
        }

        function startExecutionTrace(userInput) {
            stopDurableRunPolling();
            traceState.activeTurn += 1;
            traceState.nodes = [];
            traceState.events = [];
            traceState.traceId = null;
            traceState.selectedId = null;
            traceState.orderCounter = 0;
            updateTraceHeader('running', '等待 Agent 返回真实执行事件');
            renderExecutionTrace();
        }

        function updateExecutionTrace(data) {
            const planNodes = data?.execution_plan?.nodes || [];
            const results = data?.results || [];
            if (planNodes.length) {
                const stageNodes = traceState.nodes.filter(node => node.kind === 'stage');
                traceState.nodes = [...stageNodes, ...planNodes.map((raw, index) => {
                    const existing = traceState.nodes.find(node => node.id === (raw.node_id || `plan-${index}`));
                    return {
                    ...(existing || {}),
                    id: raw.node_id || `plan-${index}`, title: raw.tool || raw.action || 'Tool 节点',
                    meta: [raw.platform, raw.resource_type, raw.action].filter(Boolean).join(' · '),
                    kind: raw.platform || 'Tool', tool: raw.tool, platform: raw.platform,
                    resource_type: raw.resource_type, action: raw.action,
                    order: existing?.order || (++traceState.orderCounter),
                    state: existing?.state || 'planned'
                    };
                })];
            }
            // Compatibility path for non-stream callers: only update nodes
            // that already came from an ExecutionPlan; never invent nodes
            // from result rows.
            for (const result of results) {
                const node = traceState.nodes.find(item => item.tool === result.tool && (!item.state || item.state === 'planned'));
                if (node) node.state = result.needs_confirmation ? 'awaiting_confirmation' : result.success ? 'succeeded' : 'failed';
            }
            renderExecutionTrace();
        }

        function markTraceAwaitingConfirmation() {
            updateTraceHeader('awaiting_confirmation', '需要确认后继续执行');
            renderExecutionTrace();
        }

        function markTraceFailed(message) {
            pushTraceEvent({ type: 'error', status: 'failed', safe_metadata: { reason: 'request_error' } });
            updateTraceHeader('failed', '本回合未完成，请查看错误信息');
            renderExecutionTrace();
        }

        function applyExecutionEvent(event) {
            if (!event || !event.type) return null;
            const duplicateStart = event.type === 'start' && traceState.events.some(item => item.type === 'start');
            if (event.type === 'start') {
                traceState.traceId = event.trace_id || traceState.traceId;
                if (event.turn_id) traceState.activeTurn = event.turn_id;
                updateTraceHeader('running', 'Agent 正在处理本回合');
            }
            if (event.type === 'plan' && event.execution_plan) updateExecutionTrace({ execution_plan: event.execution_plan });
            if (event.type === 'stage_started' || event.type === 'stage_status') {
                const id = event.node_id || `stage:${event.stage_id}`;
                const existing = traceState.nodes.find(item => item.id === id);
                const node = {
                    ...(existing || {}),
                    id,
                    title: event.title || event.stage_id || '运行阶段',
                    subtitle: event.subtitle || existing?.subtitle || '',
                    meta: event.subtitle || event.platform || 'Runtime 阶段',
                    kind: 'stage',
                    platform: event.platform || existing?.platform || '',
                    state: event.status || 'unknown',
                    order: existing?.order || (++traceState.orderCounter),
                    reason: event.safe_metadata?.reason || existing?.reason,
                    duration_ms: event.safe_metadata?.duration_ms || existing?.duration_ms,
                    input: event.safe_input !== undefined ? event.safe_input : existing?.input,
                    output: event.safe_output !== undefined ? event.safe_output : existing?.output,
                };
                traceState.nodes = traceState.nodes.filter(item => item.id !== id);
                traceState.nodes.push(node);
                updateTraceHeader(event.status || 'unknown', `${node.title} · ${traceStatusLabel(event.status)}`);
            }
            if (event.type === 'node_discovered') {
                const id = event.node_id;
                const existing = traceState.nodes.find(item => item.id === id);
                const node = {
                    ...(existing || {}),
                    id,
                    title: event.tool || event.action || 'Tool 节点',
                    meta: [event.platform, event.resource_type, event.action].filter(Boolean).join(' · '),
                    kind: event.platform || 'Tool',
                    tool: event.tool,
                    platform: event.platform,
                    resource_type: event.resource_type,
                    action: event.action,
                    state: event.status || 'planned',
                    order: existing?.order || (++traceState.orderCounter),
                    input: event.safe_input !== undefined ? event.safe_input : existing?.input,
                    output: event.safe_output !== undefined ? event.safe_output : existing?.output,
                };
                traceState.nodes = traceState.nodes.filter(item => item.id !== id);
                traceState.nodes.push(node);
                updateTraceHeader(node.state, `${node.title} · ${traceStatusLabel(node.state)}`);
            }
            if (event.type === 'node_started' || event.type === 'node_status' || event.type === 'confirmation') {
                const node = traceState.nodes.find(item => item.id === event.node_id);
                if (node) {
                    node.state = event.status || 'unknown';
                    node.reason = event.safe_metadata?.reason || node.reason;
                    node.duration_ms = event.safe_metadata?.duration_ms || node.duration_ms;
                    if (event.safe_input !== undefined) node.input = event.safe_input;
                    if (event.safe_output !== undefined) node.output = event.safe_output;
                    traceState.selectedId = node.state === 'failed' || node.state === 'recovery_required' ? node.id : traceState.selectedId;
                }
                updateTraceHeader(event.status || 'unknown', node ? `${node.tool} · ${traceStatusLabel(event.status)}` : 'Tool 事件已到达');
            }
            if (event.type === 'done') updateTraceHeader(event.status || 'succeeded', event.status === 'awaiting_confirmation' ? '等待用户确认后继续' : '本回合已完成');
            if (event.type === 'error') updateTraceHeader('failed', '本回合未完成，请查看安全事件');
            if (!duplicateStart) pushTraceEvent(event);
            renderExecutionTrace();
            return event;
        }

        async function streamChatRequest(requestParams) {
            const response = await authenticatedFetch('/chat/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
                body: JSON.stringify(requestParams)
            });
            if (!response.ok) {
                const text = await response.text();
                let data = {};
                try { data = text ? JSON.parse(text) : {}; } catch (_) { data = {}; }
                throw new Error(data.detail || data.error || `请求失败（${response.status}）`);
            }
            if (!response.body) throw new Error('服务端未返回事件流');

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let finalResult = null;
            let streamError = '';
            const consume = (block) => {
                const line = block.split(/\r?\n/).find(item => item.startsWith('data:'));
                if (!line) return;
                try {
                    const payload = JSON.parse(line.slice(5).trim());
                    if (payload.run_id) activeDurableRunId = payload.run_id;
                    const applied = applyExecutionEvent(payload);
                    if (applied?.type === 'reply') finalResult = applied;
                    if (applied?.type === 'error') {
                        streamError = applied.error || applied.message || applied.safe_metadata?.reason || 'Agent 执行失败';
                    }
                } catch (_) {
                    applyExecutionEvent({ type: 'error', status: 'failed', safe_metadata: { reason: 'invalid_event' } });
                }
            };
            while (true) {
                const { value, done } = await reader.read();
                buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
                const blocks = buffer.split(/\r?\n\r?\n/);
                buffer = blocks.pop() || '';
                blocks.forEach(consume);
                if (done) break;
            }
            if (buffer.trim()) consume(buffer);
            if (!finalResult) throw new Error(streamError || '事件流未返回最终回复');
            if (finalResult.run_id) activeDurableRunId = finalResult.run_id;
            return finalResult;
        }

        function renderStreamResult(data, requestParams) {
            sessionId = data.session_id || sessionId;
            selectedConversationId = sessionId;
            const results = data.results || [];
            const creationNeedsCorrection = data.response_source === 'creation_card' || data.response_source === 'creation_validation';
            const hasCreationCards = Boolean(data.ui?.cards?.length) && (!requestParams?.creation_blueprint_id || creationNeedsCorrection);
            if (data.needs_confirmation && data.confirmation_payload && !hasCreationCards) {
                showConfirm(data.confirmation_payload, {
                    user_input: requestParams.user_input,
                    account_id: requestParams.account_id || null,
                    platforms: results.map(item => item.platform).filter(Boolean),
                    platform_params: requestParams.platform_params || {},
                    creation_blueprint_id: requestParams.creation_blueprint_id || null,
                    creation_blueprint_version: requestParams.creation_blueprint_version || null,
                });
                return;
            }
            const tools = results.map(item => ({ tool: item.tool, success: item.success }));
            addMessage(data.content || '我已经整理好这次广告创建需要的参数，请在卡片中确认或继续用文字补充。', 'agent', tools, false, '', null, data.ui || null);
        }

        function requestHeaders(extra = {}) {
            const headers = new Headers(extra);
            const key = serviceApiKey || document.getElementById('skillApiKey')?.value.trim() || '';
            if (key) headers.set('X-API-Key', key);
            return headers;
        }

        function authenticatedFetch(url, options = {}) {
            return fetch(url, { ...options, headers: requestHeaders(options.headers || {}) });
        }

        function conversationTime(value) {
            if (!value) return '';
            const date = new Date(value);
            if (Number.isNaN(date.getTime())) return '';
            const now = new Date();
            if (date.toDateString() === now.toDateString()) {
                return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
            }
            return date.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' });
        }

        function visibleConversations() {
            const query = historySearchQuery;
            if (!query) return conversationHistory;
            return conversationHistory.filter(item =>
                `${item.title || ''} ${item.preview || ''}`.toLowerCase().includes(query)
            );
        }

        function filterConversationHistory() {
            historySearchQuery = document.getElementById('historySearchInput')?.value.trim().toLowerCase() || '';
            renderConversationHistory();
        }

        function conversationGroupLabel(value) {
            if (!value) return '更早';
            const date = new Date(value);
            if (Number.isNaN(date.getTime())) return '更早';
            const now = new Date();
            const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
            const day = new Date(date.getFullYear(), date.getMonth(), date.getDate());
            const daysAgo = Math.floor((today.getTime() - day.getTime()) / 86400000);
            if (daysAgo <= 0) return '今天';
            if (daysAgo < 7) return '最近 7 天';
            return '更早';
        }

        function updateHistoryControls() {
            const manageButton = document.getElementById('historyManageButton');
            const selectAllButton = document.getElementById('historySelectAllButton');
            const deleteButton = document.getElementById('historyDeleteButton');
            const visible = visibleConversations();
            const total = visible.length;
            const selected = [...selectedConversationIds].filter(id =>
                visible.some(item => String(item.session_id || '') === id)
            ).length;
            if (manageButton) {
                manageButton.textContent = historySelectionMode ? '取消' : '管理';
                manageButton.classList.toggle('active', historySelectionMode);
                manageButton.setAttribute('aria-pressed', String(historySelectionMode));
            }
            if (selectAllButton) {
                selectAllButton.hidden = !historySelectionMode;
                selectAllButton.textContent = total > 0 && selected === total ? '取消全选' : '全选';
                selectAllButton.disabled = total === 0;
            }
            if (deleteButton) {
                deleteButton.hidden = !historySelectionMode;
                deleteButton.disabled = selected === 0;
                deleteButton.textContent = selected ? `删除 ${selected}` : '删除';
            }
        }

        function toggleHistorySelectionMode() {
            historySelectionMode = !historySelectionMode;
            selectedConversationIds.clear();
            updateHistoryControls();
            renderConversationHistory();
        }

        function toggleConversationSelection(session) {
            if (!historySelectionMode || !session) return;
            if (selectedConversationIds.has(session)) selectedConversationIds.delete(session);
            else selectedConversationIds.add(session);
            updateHistoryControls();
            renderConversationHistory();
        }

        function toggleSelectAllConversations() {
            if (!historySelectionMode) return;
            const ids = visibleConversations().map(item => String(item.session_id || '')).filter(Boolean);
            const allSelected = ids.length > 0 && ids.every(id => selectedConversationIds.has(id));
            ids.forEach(id => {
                if (allSelected) selectedConversationIds.delete(id);
                else selectedConversationIds.add(id);
            });
            updateHistoryControls();
            renderConversationHistory();
        }

        function showHistoryNotice(message, type = 'error') {
            const container = document.getElementById('chatHistory');
            if (!container) return;
            const notice = document.createElement('div');
            notice.className = `chat-history-status ${type}`;
            notice.textContent = message;
            container.prepend(notice);
            window.setTimeout(() => notice.remove(), 4200);
        }

        function requestConversationDeletion(sessionIdToDelete) {
            if (historySelectionMode || !sessionIdToDelete) return;
            openHistoryDeleteDialog([sessionIdToDelete]);
        }

        function requestConversationRename(sessionIdToRename, currentTitle) {
            if (historySelectionMode || !sessionIdToRename) return;
            pendingConversationRenameId = String(sessionIdToRename);
            const input = document.getElementById('historyRenameInput');
            const status = document.getElementById('historyRenameStatus');
            if (input) {
                input.value = currentTitle || '';
                input.select();
            }
            if (status) status.textContent = '';
            const overlay = document.getElementById('historyRenameOverlay');
            if (overlay) {
                overlay.classList.add('active');
                overlay.setAttribute('aria-hidden', 'false');
            }
            input?.focus();
        }

        function closeHistoryRenameDialog() {
            pendingConversationRenameId = null;
            const overlay = document.getElementById('historyRenameOverlay');
            if (overlay) {
                overlay.classList.remove('active');
                overlay.setAttribute('aria-hidden', 'true');
            }
            const button = document.getElementById('historyRenameConfirmButton');
            if (button) {
                button.disabled = false;
                button.textContent = '保存名称';
            }
        }

        async function confirmHistoryRename() {
            const session = pendingConversationRenameId;
            const input = document.getElementById('historyRenameInput');
            const status = document.getElementById('historyRenameStatus');
            const title = input?.value.trim() || '';
            if (!session) return;
            if (!title) {
                if (status) status.textContent = '请输入对话名称。';
                input?.focus();
                return;
            }
            const button = document.getElementById('historyRenameConfirmButton');
            if (button) {
                button.disabled = true;
                button.textContent = '保存中…';
            }
            try {
                const data = await apiFetch(`/sessions/${encodeURIComponent(session)}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title }),
                });
                const item = conversationHistory.find(
                    conversation => String(conversation.session_id || '') === session
                );
                if (item) item.title = data.title || title;
                closeHistoryRenameDialog();
                renderConversationHistory();
                showHistoryNotice('对话名称已更新。', 'success');
            } catch (error) {
                if (button) {
                    button.disabled = false;
                    button.textContent = '保存名称';
                }
                if (status) status.textContent = error?.message || '名称保存失败，请稍后重试。';
            }
        }

        function openHistoryDeleteDialog(sessionIds) {
            const availableIds = new Set(conversationHistory.map(item => String(item.session_id || '')));
            pendingConversationDeleteIds = [...new Set((sessionIds || []).map(String))]
                .filter(id => id && availableIds.has(id));
            if (!pendingConversationDeleteIds.length) return;
            const count = pendingConversationDeleteIds.length;
            const subtitle = document.getElementById('historyDeleteSubtitle');
            if (subtitle) {
                subtitle.textContent = count === 1
                    ? '确定要删除这条对话吗？删除后将从历史记录中移除。'
                    : `确定要删除这 ${count} 条对话吗？删除后将从历史记录中移除。`;
            }
            const overlay = document.getElementById('historyDeleteOverlay');
            if (!overlay) return;
            overlay.classList.add('active');
            overlay.setAttribute('aria-hidden', 'false');
            document.getElementById('historyDeleteConfirmButton')?.focus();
        }

        function closeHistoryDeleteDialog() {
            pendingConversationDeleteIds = [];
            const overlay = document.getElementById('historyDeleteOverlay');
            if (overlay) {
                overlay.classList.remove('active');
                overlay.setAttribute('aria-hidden', 'true');
            }
            const button = document.getElementById('historyDeleteConfirmButton');
            if (button) {
                button.disabled = false;
                button.textContent = '确认删除';
            }
        }

        async function confirmHistoryDeletion() {
            const ids = [...pendingConversationDeleteIds];
            if (!ids.length) return;
            const button = document.getElementById('historyDeleteConfirmButton');
            if (button) {
                button.disabled = true;
                button.textContent = '删除中…';
            }
            try {
                await performConversationDeletion(ids);
                closeHistoryDeleteDialog();
            } catch (error) {
                if (button) {
                    button.disabled = false;
                    button.textContent = '确认删除';
                }
                showHistoryNotice(error?.message || '删除对话失败，请稍后重试。');
            }
        }

        async function performConversationDeletion(requestedIds) {
            const ids = [...new Set((requestedIds || []).map(String))].filter(Boolean);
            if (!ids.length) return;
            const data = await apiFetch('/sessions', {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_ids: ids }),
            });
            const deletedIds = new Set((data.deleted_session_ids || []).map(String));
            if (!deletedIds.size) throw new Error('没有找到可删除的历史对话。');
            conversationHistory = conversationHistory.filter(item =>
                !deletedIds.has(String(item.session_id || ''))
            );
            deletedIds.forEach(id => selectedConversationIds.delete(id));
            const deletedCurrent = sessionId && deletedIds.has(String(sessionId));
            historySelectionMode = false;
            selectedConversationIds.clear();
            updateHistoryControls();
            if (deletedCurrent) newChat();
            else renderConversationHistory();
            await refreshConversationHistory({ silent: true });
            showHistoryNotice(`已删除 ${deletedIds.size} 条历史对话。`, 'success');
        }

        async function deleteSelectedConversations() {
            if (!historySelectionMode || selectedConversationIds.size === 0) return;
            const requestedIds = [...selectedConversationIds].filter(id =>
                conversationHistory.some(item => String(item.session_id || '') === id)
            );
            if (!requestedIds.length) return;
            openHistoryDeleteDialog(requestedIds);
        }

        function renderConversationHistory(conversations = visibleConversations()) {
            const container = document.getElementById('chatHistory');
            if (!container) return;
            updateHistoryControls();
            container.replaceChildren();
            if (!conversations.length) {
                const empty = document.createElement('div');
                empty.className = 'chat-history-empty';
                empty.textContent = historySearchQuery
                    ? '没有匹配的历史对话。'
                    : '暂无历史对话。发送一条消息后会自动保存。';
                container.appendChild(empty);
                return;
            }
            const grouped = new Map([['今天', []], ['最近 7 天', []], ['更早', []]]);
            for (const conversation of conversations) {
                grouped.get(conversationGroupLabel(conversation.updated_at)).push(conversation);
            }
            for (const [groupLabel, groupConversations] of grouped) {
                if (!groupConversations.length) continue;
                const group = document.createElement('div');
                group.className = 'chat-history-group-label';
                group.textContent = groupLabel;
                container.appendChild(group);
                for (const conversation of groupConversations) {
                    const session = String(conversation.session_id || '');
                    if (!session) continue;
                    const item = document.createElement('div');
                    const selectedForDelete = selectedConversationIds.has(session);
                    item.className = `chat-history-item${session === selectedConversationId ? ' active' : ''}${selectedForDelete ? ' selected-for-delete' : ''}`;
                    const openButton = document.createElement('button');
                    openButton.type = 'button';
                    openButton.className = 'chat-history-open';
                    openButton.setAttribute('aria-label', historySelectionMode
                        ? `${selectedForDelete ? '取消选择' : '选择'}对话：${conversation.title || '新对话'}`
                        : `打开对话：${conversation.title || '新对话'}`);
                    openButton.setAttribute('aria-pressed', String(historySelectionMode && selectedForDelete));
                    openButton.addEventListener('click', () => historySelectionMode
                        ? toggleConversationSelection(session)
                        : loadConversation(session));

                    if (historySelectionMode) {
                        const selectBox = document.createElement('span');
                        selectBox.className = 'history-select-box';
                        selectBox.setAttribute('aria-hidden', 'true');
                        selectBox.textContent = selectedForDelete ? '✓' : '';
                        openButton.appendChild(selectBox);
                    }

                    const copy = document.createElement('span');
                    copy.className = 'chat-history-copy';
                    const title = document.createElement('span');
                    title.className = 'chat-history-title';
                    title.textContent = conversation.title || '新对话';
                    const preview = document.createElement('span');
                    preview.className = 'chat-history-preview';
                    preview.textContent = conversation.preview || '暂无消息预览';
                    copy.append(title, preview);
                    const time = document.createElement('span');
                    time.className = 'chat-history-time';
                    time.textContent = conversationTime(conversation.updated_at);
                    openButton.append(copy, time);
                    item.appendChild(openButton);
                    if (!historySelectionMode) {
                        const renameButton = document.createElement('button');
                        renameButton.type = 'button';
                        renameButton.className = 'chat-history-rename';
                        renameButton.setAttribute('aria-label', `重命名对话：${conversation.title || '新对话'}`);
                        renameButton.title = '重命名这条对话';
                        renameButton.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20h9"></path><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z"></path></svg>';
                        renameButton.addEventListener('click', (event) => {
                            event.stopPropagation();
                            requestConversationRename(session, conversation.title || '');
                        });
                        item.appendChild(renameButton);
                        const deleteButton = document.createElement('button');
                        deleteButton.type = 'button';
                        deleteButton.className = 'chat-history-delete';
                        deleteButton.setAttribute('aria-label', `删除对话：${conversation.title || '新对话'}`);
                        deleteButton.title = '删除这条对话';
                        deleteButton.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"></path></svg>';
                        deleteButton.addEventListener('click', (event) => {
                            event.stopPropagation();
                            requestConversationDeletion(session);
                        });
                        item.appendChild(deleteButton);
                    }
                    container.appendChild(item);
                }
            }
        }

        async function refreshConversationHistory({ silent = false } = {}) {
            const requestId = ++conversationHistoryRequest;
            if (!silent) {
                const status = document.getElementById('chatHistoryStatus');
                if (status) status.textContent = '正在加载历史对话…';
            }
            try {
                const response = await authenticatedFetch('/sessions?limit=50');
                const text = await response.text();
                let data = {};
                try { data = text ? JSON.parse(text) : {}; } catch (_) { data = {}; }
                if (!response.ok) throw new Error(data.detail || data.error || `历史对话加载失败（${response.status}）`);
                if (requestId !== conversationHistoryRequest) return;
                conversationHistory = Array.isArray(data.sessions) ? data.sessions : [];
                renderConversationHistory();
            } catch (error) {
                if (requestId !== conversationHistoryRequest) return;
                conversationHistory = [];
                const message = error?.message || '';
                const status = /401|403|授权|API key/i.test(message)
                    ? '历史对话暂不可用，请检查服务 API Key。'
                    : '历史对话暂时不可用，请稍后重试。';
                const container = document.getElementById('chatHistory');
                if (container) {
                    container.replaceChildren();
                    const errorNode = document.createElement('div');
                    errorNode.className = 'chat-history-status error';
                    errorNode.textContent = status;
                    container.appendChild(errorNode);
                }
            }
        }

        async function loadConversation(targetSessionId) {
            if (!targetSessionId) return;
            try {
                const response = await authenticatedFetch(`/sessions/${encodeURIComponent(targetSessionId)}?limit=500`);
                const text = await response.text();
                let data = {};
                try { data = text ? JSON.parse(text) : {}; } catch (_) { data = {}; }
                if (!response.ok) throw new Error(data.detail || data.error || `对话加载失败（${response.status}）`);
                sessionId = data.session_id || targetSessionId;
                selectedConversationId = sessionId;
                loadedConversationTurnIds.clear();
                for (const message of (Array.isArray(data.messages) ? data.messages : [])) {
                    if (message.turn_id) loadedConversationTurnIds.add(message.turn_id);
                }
                pendingRequest = null;
                document.getElementById('confirmCard')?.remove();
                const container = document.getElementById('chatContainer');
                container.replaceChildren();
                for (const message of (Array.isArray(data.messages) ? data.messages : [])) {
                    addMessage(
                        message.content || '',
                        message.role === 'user' ? 'user' : 'agent',
                        null,
                        false,
                        '',
                        message.created_at,
                        message.ui || null,
                    );
                }
                if (!data.messages?.length) {
                    const empty = document.createElement('div');
                    empty.className = 'chat-history-empty';
                    empty.textContent = '这个对话还没有可展示的消息。';
                    container.appendChild(empty);
                }
                restoreExecutionTrace(data.execution_traces);
                await loadLatestDurableRun(sessionId);
                renderConversationHistory();
            } catch (error) {
                addMessage(error?.message || '对话加载失败，请稍后重试。', 'agent', null, true);
            }
        }

        async function apiFetch(url, options = {}) {
            const response = await authenticatedFetch(url, options);
            const text = await response.text();
            let data = {};
            try { data = text ? JSON.parse(text) : {}; } catch (_) { data = { detail: text }; }
            if (!response.ok) {
                if (response.status === 401 || response.status === 403) {
                    showSkillNotice('请求未授权。请填写当前 ad-agent 服务 API Key；它不是任何渠道的 Provider Token。', true);
                }
                const error = new Error(data.detail || data.error || `请求失败（${response.status}）`);
                error.status = response.status;
                throw error;
            }
            return data;
        }

        function openBlueprintManager(provider = null, selectorValue = null, blueprintId = null) {
            closeWorkspacePopovers();
            const overlay = document.getElementById('blueprintOverlay');
            if (!overlay) return;
            overlay.classList.add('active');
            overlay.setAttribute('aria-hidden', 'false');
            loadCreationBlueprints(blueprintId || null).then(() => {
                if (!provider) return;
                const item = blueprintState.items.find(candidate =>
                    candidate.provider === provider && (
                        (blueprintId && candidate.id === blueprintId)
                        || (!blueprintId && (!selectorValue || (candidate.selector?.values || []).map(String).includes(String(selectorValue))))
                    )
                );
                if (item) selectBlueprint(item.id, selectorValue);
            });
        }

        function closeBlueprintManager() {
            document.getElementById('blueprintOverlay')?.classList.remove('active');
            document.getElementById('blueprintOverlay')?.setAttribute('aria-hidden', 'true');
        }

        function focusBlueprintIssue() {
            const account = document.getElementById('blueprintAccountInput');
            if (!String(account?.value || '').trim()) {
                account?.focus();
                account?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                return;
            }
            const issue = document.querySelector('#blueprintFields .blueprint-field.invalid:not(.hidden), #blueprintFields .blueprint-field.missing:not(.hidden)');
            if (!issue) return;
            scrollCreationTarget(issue);
            issue.querySelector('input:not([disabled]), select:not([disabled]), textarea:not([disabled])')?.focus({ preventScroll: true });
        }

        function blueprintToolFieldSchema(toolRef) {
            const parts = String(toolRef || '').split('.');
            const toolName = parts.shift();
            const fieldPath = parts.join('.');
            const tool = blueprintState.tools.find(item => item.name === toolName);
            let schema = tool?.input_schema?.properties || {};
            for (const part of fieldPath.split('.')) {
                if (!part) continue;
                schema = schema?.[part] || {};
            }
            return { toolName, fieldPath, schema: schema || {} };
        }

        function blueprintFieldDefault(field) {
            if (field && Object.prototype.hasOwnProperty.call(field, 'default')) return field.default;
            const schema = blueprintToolFieldSchema(field?.tool_ref).schema || {};
            if (Object.prototype.hasOwnProperty.call(schema, 'default')) return schema.default;
            return schema.type === 'boolean' ? false : undefined;
        }

        function blueprintDefaultValues(blueprint) {
            const values = {};
            (blueprint?.fields || []).forEach(field => {
                const value = blueprintFieldDefault(field);
                if (value !== undefined) values[field.path] = value;
            });
            return values;
        }

        function blueprintOptions(field, evaluatedState = null) {
            // An evaluated empty list is meaningful: the parent selector is
            // still missing. Do not fall back to the provider's full enum or
            // the cascade would look dynamic while showing invalid values.
            if (evaluatedState && Object.prototype.hasOwnProperty.call(evaluatedState, 'options')) {
                return Array.isArray(evaluatedState.options) ? evaluatedState.options : [];
            }
            const schema = blueprintToolFieldSchema(field.tool_ref).schema || {};
            const arraySchema = schema.type === 'array' || (Array.isArray(schema.type) && schema.type.includes('array'));
            if (Array.isArray(field.options) && !arraySchema) return field.options;
            if (Array.isArray(schema.enum)) return schema.enum;
            if (Array.isArray(schema.items?.enum)) return schema.items.enum;
            return [];
        }

        function blueprintOptionLabel(field, option) {
            const labels = field?.option_labels;
            if (labels && typeof labels === 'object') {
                return labels[String(option)] || String(option);
            }
            return String(option);
        }

        function schemaConstraintHint(schema) {
            if (!schema || typeof schema !== 'object') return '';
            const hints = [];
            if (schema.minItems !== undefined) hints.push(`至少 ${schema.minItems} 项`);
            if (schema.maxItems !== undefined) hints.push(`最多 ${schema.maxItems} 项`);
            if (schema.minLength !== undefined) hints.push(`最少 ${schema.minLength} 个字符`);
            if (schema.maxLength !== undefined) hints.push(`最多 ${schema.maxLength} 个字符`);
            if (schema.minimum !== undefined) hints.push(`最小值 ${schema.minimum}`);
            if (schema.maximum !== undefined) hints.push(`最大值 ${schema.maximum}`);
            if (schema.items?.minLength !== undefined) hints.push(`每项最少 ${schema.items.minLength} 个字符`);
            if (schema.items?.maxLength !== undefined) hints.push(`每项最多 ${schema.items.maxLength} 个字符`);
            if (schema.known_values && schema.allow_custom) hints.push('可选标准值，也可填写自定义值');
            return hints.join('；');
        }

        function presentedLines(value) {
            if (!Array.isArray(value)) return value ? String(value) : '';
            return value.map(item => {
                if (item && typeof item === 'object') return item.text || item.name || item.asset || item.resource_name || '';
                return String(item ?? '');
            }).filter(Boolean).join('\n');
        }

        function parsePresentedValue(field, rawValue, schema) {
            if (field.presentation === 'text_list') {
                const lines = String(rawValue || '').split(/\r?\n/).map(item => item.trim()).filter(Boolean);
                return field.value_shape === 'object_text' ? lines.map(text => ({ text })) : lines;
            }
            if (schema.type === 'object' || schema.type === 'array' || Array.isArray(schema.type)) {
                try { return JSON.parse(rawValue); } catch (_) { return rawValue; }
            }
            if (schema.type === 'number' || schema.type === 'integer') return Number(rawValue);
            return rawValue;
        }

        function structuredObjectValueText(value) {
            if (!value || typeof value !== 'object' || Array.isArray(value)) return '';
            return Object.entries(value)
                .filter(([, item]) => item !== undefined && item !== null && item !== '')
                .map(([key, item]) => `${key}: ${Array.isArray(item) ? item.join(', ') : typeof item === 'object' ? JSON.stringify(item) : item}`)
                .join(' · ');
        }

        function parseStructuredObjectChild(spec, rawValue) {
            const type = spec?.type;
            if (type === 'number' || type === 'integer') return rawValue === '' ? undefined : Number(rawValue);
            if (type === 'boolean') return Boolean(rawValue);
            if (type === 'array') {
                if (spec.items?.type === 'string') return String(rawValue || '').split(/\r?\n/).map(item => item.trim()).filter(Boolean);
                try { return JSON.parse(rawValue); } catch (_) { return rawValue; }
            }
            if (type === 'object') {
                try { return JSON.parse(rawValue); } catch (_) { return rawValue; }
            }
            return rawValue === '' ? undefined : rawValue;
        }

        function ensureLookupSessionId() {
            if (sessionId) return sessionId;
            try {
                sessionId = crypto.randomUUID();
            } catch (_) {
                sessionId = `web-${Date.now()}-${Math.random().toString(16).slice(2)}`;
            }
            return sessionId;
        }

        function lookupValueKey(value) {
            if (value === undefined || value === null) return '';
            return JSON.stringify(value, (_, item) => item, 0);
        }

        function lookupFieldValue(field, context = {}) {
            if (typeof context.getValue === 'function') return context.getValue();
            return field.value;
        }

        function lookupFieldName(field, context = {}) {
            return String(context.fieldName || field.provider_field || field.path || '').trim();
        }

        function lookupToolName(field, context = {}) {
            return String(
                context.targetToolName || field.tool || field.lookup_tool || field.lookup?.tool || ''
            ).trim();
        }

        function lookupIsMultiple(field, context = {}) {
            if (context.multiple !== undefined) return Boolean(context.multiple);
            return Boolean(field.lookup_multiple || field.control === 'multiselect');
        }

        function lookupAccountRequired(field, context = {}) {
            if (context.accountRequired !== undefined) return Boolean(context.accountRequired);
            if (field?.lookup?.account_required !== undefined) return Boolean(field.lookup.account_required);
            if (field?.lookup_account_required !== undefined) return Boolean(field.lookup_account_required);
            return true;
        }

        function lookupSourceAccountRequired(toolName) {
            const tool = (blueprintState.tools || []).find(item => item.name === toolName);
            const required = tool?.input_schema?.required || [];
            return required.some(name => ['account_id', 'advertiser_id', 'customer_id'].includes(name));
        }

        function lookupContextValues(context = {}) {
            if (typeof context.getLookupContext === 'function') {
                const value = context.getLookupContext();
                return value && typeof value === 'object' ? value : {};
            }
            return context.lookupContext && typeof context.lookupContext === 'object'
                ? context.lookupContext : {};
        }

        function lookupSelectedValues(field, context = {}) {
            const value = lookupFieldValue(field, context);
            if (lookupIsMultiple(field, context)) return Array.isArray(value) ? value : [];
            return value === undefined || value === null || value === '' ? [] : [value];
        }

        function lookupOptionLabel(option) {
            return String(option?.label ?? option?.name ?? option?.value ?? '');
        }

        function lookupOptionValue(option) {
            return option?.value;
        }

        function lookupOptionValueText(value) {
            if (value && typeof value === 'object') {
                return String(value.id ?? value.audience_id ?? value.value ?? JSON.stringify(value));
            }
            return String(value ?? '');
        }

        function lookupOptionMatches(option, query) {
            if (!query) return true;
            return `${lookupOptionLabel(option)} ${lookupOptionValueText(lookupOptionValue(option))}`
                .toLowerCase().includes(query.toLowerCase());
        }

        function lookupSelectionTokensFor(context, field) {
            const store = context.selectionTokens || {};
            const key = lookupFieldName(field, context);
            const value = store[key];
            if (lookupIsMultiple(field, context)) return Array.isArray(value) ? value : [];
            return value ? [value] : [];
        }

        function renderLookupPicker(field, context = {}) {
            const picker = document.createElement('div');
            picker.className = 'lookup-picker';
            const fieldName = lookupFieldName(field, context);
            const toolName = lookupToolName(field, context);
            const multiple = lookupIsMultiple(field, context);
            const accountId = () => String(
                typeof context.getAccountId === 'function' ? context.getAccountId() : context.accountId || ''
            ).trim();
            const accountRequired = lookupAccountRequired(field, context);
            const optionsStore = context.optionsStore || {};
            const optionsKey = `${toolName}:${fieldName}`;
            let options = Array.isArray(optionsStore[optionsKey]) ? optionsStore[optionsKey] : [];

            const toolbar = document.createElement('div');
            toolbar.className = 'lookup-picker-toolbar';
            const searchInput = document.createElement('input');
            searchInput.type = 'search';
            searchInput.autocomplete = 'off';
            searchInput.placeholder = '输入名称或 ID 筛选，再查询可用项';
            const searchButton = document.createElement('button');
            searchButton.type = 'button';
            searchButton.className = 'lookup-picker-search';
            searchButton.textContent = '查询';
            toolbar.append(searchInput, searchButton);
            picker.appendChild(toolbar);

            const status = document.createElement('div');
            status.className = 'lookup-picker-status';
            picker.appendChild(status);
            const results = document.createElement('div');
            results.className = 'lookup-picker-results';
            picker.appendChild(results);
            const selected = document.createElement('div');
            selected.className = 'lookup-picker-selected';
            picker.appendChild(selected);

            const getSelected = () => lookupSelectedValues(field, context);
            const tokenStore = context.selectionTokens || {};

            function optionForValue(value) {
                return options.find(option => lookupValueKey(lookupOptionValue(option)) === lookupValueKey(value))
                    || { value, label: String(value ?? '') };
            }

            function renderSelected() {
                selected.replaceChildren();
                const values = getSelected();
                const tokens = lookupSelectionTokensFor(context, field);
                values.forEach((value, index) => {
                    const option = optionForValue(value);
                    const chip = document.createElement('span');
                    chip.className = 'lookup-selection-chip';
                    const label = document.createElement('span');
                    label.textContent = `${lookupOptionLabel(option)} · ${lookupOptionValueText(value)}`;
                    const remove = document.createElement('button');
                    remove.type = 'button';
                    remove.setAttribute('aria-label', `移除 ${lookupOptionLabel(option)}`);
                    remove.textContent = '×';
                    remove.onclick = () => {
                        const next = multiple ? values.filter((_, valueIndex) => valueIndex !== index) : [];
                        const nextTokens = multiple ? tokens.filter((_, tokenIndex) => tokenIndex !== index) : [];
                        commitSelection(next, nextTokens, null);
                    };
                    chip.append(label, remove);
                    selected.appendChild(chip);
                });
                if (!values.length) {
                    const empty = document.createElement('span');
                    empty.className = 'lookup-picker-status';
                    empty.textContent = '尚未选择；请选择查询结果中的项目。';
                    selected.appendChild(empty);
                }
            }

            function renderResults() {
                results.replaceChildren();
                const selectedKeys = new Set(getSelected().map(lookupValueKey));
                const query = searchInput.value.trim();
                const visible = options.filter(option => lookupOptionMatches(option, query));
                if (!visible.length) {
                    status.textContent = options.length ? '没有匹配的项目，请换一个名称或 ID。' : '点击“查询”加载该账户下的可用项。';
                    return;
                }
                status.textContent = `已加载 ${options.length} 项${query ? `，当前显示 ${visible.length} 项` : ''}`;
                visible.slice(0, 100).forEach(option => {
                    const value = lookupOptionValue(option);
                    const button = document.createElement('button');
                    button.type = 'button';
                    button.className = `lookup-option${selectedKeys.has(lookupValueKey(value)) ? ' selected' : ''}`;
                    button.disabled = !multiple && selectedKeys.has(lookupValueKey(value));
                    const label = document.createElement('span');
                    label.className = 'lookup-option-label';
                    label.textContent = lookupOptionLabel(option);
                    const id = document.createElement('span');
                    id.className = 'lookup-option-value';
                    id.textContent = lookupOptionValueText(value);
                    button.append(label, id);
                    button.onclick = () => {
                        const current = getSelected();
                        const currentTokens = lookupSelectionTokensFor(context, field);
                        if (multiple) {
                            if (current.some(item => lookupValueKey(item) === lookupValueKey(value))) return;
                            commitSelection([...current, value], [...currentTokens, option.selection_token || ''], option);
                        } else {
                            commitSelection([value], [option.selection_token || ''], option);
                        }
                    };
                    results.appendChild(button);
                });
            }

            function commitSelection(values, tokens, option) {
                const nextValue = multiple ? values : (values[0] ?? undefined);
                const nextTokens = multiple ? tokens : (tokens[0] || undefined);
                const key = lookupFieldName(field, context);
                if (nextTokens) tokenStore[key] = nextTokens;
                else delete tokenStore[key];
                if (typeof context.onSelection === 'function') {
                    context.onSelection({ value: nextValue, tokens: nextTokens, option });
                }
                renderSelected();
                renderResults();
            }

            async function queryOptions() {
                const account = accountId();
                if (!account && accountRequired) {
                    status.textContent = '请先填写广告账户 ID，再查询该账户下的可用项。';
                    searchButton.disabled = true;
                    return;
                }
                if (!toolName || !fieldName || !context.platform) {
                    status.textContent = '当前字段缺少受控查询配置，暂时无法加载选项。';
                    return;
                }
                searchButton.disabled = true;
                status.textContent = '正在查询该账户的可用项…';
                try {
                    ensureLookupSessionId();
                    const params = new URLSearchParams({
                        platform: String(context.platform), field: fieldName,
                        tool_name: toolName, session_id: sessionId,
                    });
                    if (account) params.set('account_id', account);
                    const lookupContext = lookupContextValues(context);
                    if (Object.keys(lookupContext).length) params.set('lookup_context', JSON.stringify(lookupContext));
                    if (field?.lookup?.query_field && searchInput.value.trim()) params.set('query', searchInput.value.trim());
                    const response = await authenticatedFetch(`/parameter-options/resolve?${params.toString()}`);
                    const body = await response.text();
                    let data = {};
                    try { data = body ? JSON.parse(body) : {}; } catch (_) { data = {}; }
                    if (!response.ok) throw new Error(data.detail || data.error || `查询失败（${response.status}）`);
                    options = Array.isArray(data.options) ? data.options : [];
                    optionsStore[optionsKey] = options;
                    renderResults();
                    renderSelected();
                } catch (error) {
                    status.textContent = error.message || '暂时无法查询可用项，请稍后重试。';
                } finally {
                    searchButton.disabled = false;
                    refreshLookupAccountState(picker);
                }
            }

            searchInput.addEventListener('input', renderResults);
            searchButton.addEventListener('click', queryOptions);
            picker.dataset.accountRequired = accountRequired ? 'true' : 'false';
            picker.dataset.accountValue = accountId();
            refreshLookupAccountState(picker);
            renderSelected();
            renderResults();
            return picker;
        }

        function refreshLookupAccountState(root = document) {
            const accountInput = root?.closest?.('.creation-card')?.querySelector('.creation-card-account input')
                || root?.querySelector?.('.creation-card-account input')
                || document.getElementById('blueprintAccountInput');
            const account = String(accountInput?.value || '').trim();
            (root?.matches?.('.lookup-picker') ? [root] : root?.querySelectorAll?.('.lookup-picker') || []).forEach(picker => {
                picker.dataset.accountValue = account;
                const button = picker.querySelector('.lookup-picker-search');
                const accountRequired = picker.dataset.accountRequired !== 'false';
                if (button && !button.disabled) button.disabled = accountRequired && !account;
                if (!account && accountRequired) {
                    const status = picker.querySelector('.lookup-picker-status');
                    if (status && !picker.querySelector('.lookup-picker-results:not(:empty)')) {
                        status.textContent = '请先填写广告账户 ID，再查询该账户下的可用项。';
                    }
                }
            });
        }

        function clearAccountScopedLookupValues(value, properties) {
            if (Array.isArray(value)) {
                return value.map(item => clearAccountScopedLookupValues(item, properties));
            }
            if (!value || typeof value !== 'object' || !properties || typeof properties !== 'object') {
                return value;
            }
            const result = { ...value };
            Object.entries(properties).forEach(([name, spec]) => {
                if (!spec || typeof spec !== 'object') return;
                if (spec.lookup_tool || spec.source === 'lookup' || spec.lookup) {
                    delete result[name];
                    return;
                }
                if (spec.properties && result[name] && typeof result[name] === 'object') {
                    result[name] = clearAccountScopedLookupValues(result[name], spec.properties);
                } else if (spec.items?.properties && Array.isArray(result[name])) {
                    result[name] = clearAccountScopedLookupValues(result[name], spec.items.properties);
                }
            });
            return result;
        }

        function resetAccountScopedSelections(card) {
            let changed = false;
            card.lookup_options = {};
            card.selection_tokens = {};
            card.selection_token_tools = {};
            (card.fields || []).forEach(field => {
                if (!field || field.visible === false) return;
                if (field.control === 'lookup' && field.lookup?.account_required !== false && !creationCardValueEmpty(field.value)) {
                    field.value = undefined;
                    field.state = 'missing';
                    changed = true;
                }
                if (field.object_properties && !creationCardValueEmpty(field.value)) {
                    const cleared = clearAccountScopedLookupValues(field.value, field.object_properties);
                    if (JSON.stringify(cleared) !== JSON.stringify(field.value)) {
                        field.value = cleared;
                        changed = true;
                    }
                }
            });
            return changed;
        }

        function renderStructuredObjectEditor(schema, value, onChange, metadata = null, lookupContext = null) {
            // Arrays of provider objects are first-class form values (for
            // example carousel cards and asset lists).  Keep the collection
            // wrapper here so every provider gets the same add/remove UX;
            // no channel-specific renderer is needed.
            if (schema?.type === 'array' && schema.items?.properties) {
                const collection = document.createElement('div');
                collection.className = 'structured-object-collection';
                const itemProperties = metadata || schema.items.properties || {};
                const items = Array.isArray(value) ? value.map(item => ({ ...(item || {}) })) : [];
                const list = document.createElement('div');
                list.className = 'structured-object-collection-list';

                const renderItems = () => {
                    list.replaceChildren();
                    items.forEach((itemValue, index) => {
                        const itemBox = document.createElement('div');
                        itemBox.className = 'structured-object-item';
                        const itemHead = document.createElement('div');
                        itemHead.className = 'structured-object-item-head';
                        const itemTitle = document.createElement('strong');
                        itemTitle.textContent = `第 ${index + 1} 项`;
                        const remove = document.createElement('button');
                        remove.type = 'button';
                        remove.className = 'structured-object-remove';
                        remove.textContent = '移除';
                        remove.addEventListener('click', () => {
                            items.splice(index, 1);
                            onChange(items.length ? items.map(item => ({ ...item })) : undefined);
                            renderItems();
                        });
                        itemHead.append(itemTitle, remove);
                        itemBox.appendChild(itemHead);
                        itemBox.appendChild(renderStructuredObjectEditor(
                            schema.items,
                            itemValue,
                            nextValue => {
                                items[index] = nextValue || {};
                                onChange(items.map(item => ({ ...item })));
                            },
                            itemProperties,
                            lookupContext,
                        ));
                        list.appendChild(itemBox);
                    });
                };

                const add = document.createElement('button');
                add.type = 'button';
                add.className = 'structured-object-add';
                add.textContent = '＋ 新增一项';
                add.disabled = schema.maxItems !== undefined && items.length >= Number(schema.maxItems);
                add.addEventListener('click', () => {
                    if (schema.maxItems !== undefined && items.length >= Number(schema.maxItems)) return;
                    items.push({});
                    onChange(items.map(item => ({ ...item })));
                    renderItems();
                    add.disabled = schema.maxItems !== undefined && items.length >= Number(schema.maxItems);
                });
                collection.append(list, add);
                renderItems();
                return collection;
            }
            const editor = document.createElement('div');
            editor.className = 'structured-object-editor';
            const properties = metadata || schema?.properties || {};
            const current = value && typeof value === 'object' && !Array.isArray(value) ? { ...value } : {};
            Object.entries(properties).slice(0, 40).forEach(([name, rawSpec]) => {
                const spec = rawSpec || {};
                const row = document.createElement('div');
                row.className = 'structured-object-row';
                const label = document.createElement('label');
                const specHint = schemaConstraintHint(spec);
                const specDescription = [spec.description, specHint ? `参数限制：${specHint}` : '']
                    .filter(Boolean).join('；');
                const friendlyName = spec.title || {
                    age_groups: '年龄段', operating_systems: '操作系统', placement_type: '版位方式',
                    placements: '投放版位', targeting_optimization_mode: '定向优化方式',
                    billing_event: '计费事件', optimization_event: '优化事件',
                }[name] || name.replace(/[_-]+/g, ' ').replace(/\b\w/g, character => character.toUpperCase());
                label.textContent = friendlyName;
                const key = document.createElement('span');
                key.className = 'structured-object-key';
                key.textContent = name;
                label.appendChild(key);
                if (spec.required) {
                    const required = document.createElement('span');
                    required.className = 'required';
                    required.textContent = ' *';
                    label.appendChild(required);
                }
                row.appendChild(label);
                if (specDescription) {
                    const help = document.createElement('div');
                    help.className = 'structured-object-help';
                    help.textContent = specDescription;
                    row.appendChild(help);
                }
                let control;
                const options = Array.isArray(spec.enum)
                    ? spec.enum
                    : Array.isArray(spec.items?.enum) ? spec.items.enum : [];
                if (spec.lookup_tool || spec.lookup?.tool) {
                    const childPath = [lookupContext?.fieldPath, name].filter(Boolean).join('.');
                    control = renderLookupPicker({
                        ...spec, path: childPath, provider_field: childPath,
                        tool: lookupContext?.targetToolName,
                        lookup: {
                            tool: spec.lookup_tool || spec.lookup?.tool,
                            query_field: spec.lookup_query_field || spec.lookup?.query_field,
                        },
                        lookup_multiple: spec.type === 'array',
                        value: current[name],
                    }, {
                        ...lookupContext,
                        fieldName: childPath,
                        targetToolName: lookupContext?.targetToolName,
                        multiple: spec.type === 'array',
                        getValue: () => current[name],
                        onSelection: ({ value: selectedValue, tokens }) => {
                            if (selectedValue === undefined) delete current[name];
                            else current[name] = selectedValue;
                            onChange({ ...current });
                            lookupContext?.onSelection?.({ fieldName: childPath, tokens });
                        },
                    });
                } else if (
                    spec.type === 'object' && spec.properties && typeof spec.properties === 'object'
                ) {
                    const childPath = [lookupContext?.fieldPath, name].filter(Boolean).join('.');
                    control = renderStructuredObjectEditor(
                        spec,
                        current[name],
                        selectedValue => {
                            if (selectedValue === undefined) delete current[name];
                            else current[name] = selectedValue;
                            onChange({ ...current });
                        },
                        null,
                        {
                            ...(lookupContext || {}),
                            fieldPath: childPath,
                        },
                    );
                } else if (
                    spec.type === 'array' && spec.items?.properties
                    && typeof spec.items.properties === 'object'
                ) {
                    const childPath = [lookupContext?.fieldPath, name].filter(Boolean).join('.');
                    control = renderStructuredObjectEditor(
                        spec,
                        current[name],
                        selectedValue => {
                            if (selectedValue === undefined) delete current[name];
                            else current[name] = selectedValue;
                            onChange({ ...current });
                        },
                        null,
                        { ...(lookupContext || {}), fieldPath: childPath },
                    );
                } else if (spec.options_state === 'awaiting_dependency' || spec.options_state === 'no_matching_rule') {
                    control = document.createElement('select');
                    control.disabled = true;
                    const waiting = document.createElement('option');
                    waiting.value = '';
                    waiting.textContent = spec.options_state === 'awaiting_dependency'
                        ? '请先完成上游选择…' : '当前组合暂无可用选项';
                    control.appendChild(waiting);
                } else if (options.length) {
                    const useChoiceTiles = spec.type === 'array' || options.length <= 6;
                    if (useChoiceTiles) {
                        const multiple = spec.type === 'array';
                        control = renderChoiceTiles(options, current[name], multiple, option => spec.option_labels?.[String(option)] || '', selected => {
                            if (selected === '' || (Array.isArray(selected) && !selected.length)) delete current[name];
                            else current[name] = selected;
                            onChange({ ...current });
                        });
                        control.dataset.customChoice = 'true';
                    } else {
                        control = document.createElement('select');
                        const empty = document.createElement('option');
                        empty.value = ''; empty.textContent = spec.required ? '请选择…' : '不设置';
                        control.appendChild(empty);
                        options.forEach(option => {
                            const item = document.createElement('option');
                            item.value = String(option);
                            item.textContent = spec.option_labels?.[String(option)] || String(option);
                            control.appendChild(item);
                        });
                        control.value = current[name] === undefined ? '' : String(current[name]);
                    }
                } else if (spec.type === 'boolean') {
                    control = document.createElement('input');
                    control.type = 'checkbox'; control.checked = Boolean(current[name]);
                } else if (spec.type === 'array') {
                    control = document.createElement('textarea');
                    control.className = 'structured-object-list';
                    control.placeholder = spec.items?.type === 'string' ? '每行一项' : '[...]';
                    control.value = spec.items?.type === 'string'
                        ? (Array.isArray(current[name]) ? current[name].join('\n') : '')
                        : (current[name] === undefined ? '' : JSON.stringify(current[name]));
                } else {
                    control = document.createElement('input');
                    control.type = spec.type === 'number' || spec.type === 'integer' ? 'number' : 'text';
                    control.value = current[name] === undefined ? '' : String(current[name]);
                }
                let controlNode = control;
                let checkboxState = null;
                if (spec.type === 'boolean') {
                    const checkboxLabel = document.createElement('label');
                    checkboxLabel.className = 'checkbox-control';
                    const visual = document.createElement('span');
                    visual.className = 'checkbox-visual';
                    const copy = document.createElement('span');
                    copy.className = 'checkbox-copy';
                    const title = document.createElement('strong');
                    title.textContent = '启用该设置';
                    checkboxState = document.createElement('small');
                    checkboxState.textContent = control.checked ? '已开启' : '未开启';
                    copy.append(title, checkboxState);
                    checkboxLabel.append(control, visual, copy);
                    controlNode = checkboxLabel;
                }
                if (spec.manual_entry && typeof spec.manual_entry === 'object') {
                    const help = document.createElement('div');
                    help.className = 'manual-entry-help';
                    const title = spec.manual_entry.title || '需要手动提供的外部标识';
                    const instructions = spec.manual_entry.instructions || '该字段当前没有可用的受控列表查询。';
                    help.innerHTML = `<strong>${escapeHtml(title)}</strong><br>${escapeHtml(instructions)}${spec.manual_entry.example ? `<br>示例：${escapeHtml(spec.manual_entry.example)}` : ''}`;
                    row.appendChild(help);
                }
                const commit = () => {
                    if (spec.lookup_tool || spec.lookup?.tool) return;
                    const value = control.type === 'checkbox'
                        ? control.checked
                        : control.tagName === 'SELECT' && control.multiple
                            ? Array.from(control.selectedOptions).map(option => option.value)
                            : parseStructuredObjectChild(spec, control.value.trim());
                    if (value === undefined) delete current[name]; else current[name] = value;
                    if (checkboxState) checkboxState.textContent = control.checked ? '已开启' : '未开启';
                    onChange({ ...current });
                };
                if (!control.dataset.customChoice && !(
                    (spec.type === 'object' && spec.properties && typeof spec.properties === 'object')
                    || (spec.type === 'array' && spec.items?.properties)
                )) {
                    control.addEventListener(control.type === 'checkbox' || control.tagName === 'SELECT' ? 'change' : 'input', commit);
                }
                row.appendChild(controlNode);
                editor.appendChild(row);
            });
            if (!Object.keys(properties).length) {
                const empty = document.createElement('div');
                empty.className = 'asset-picker-note';
                empty.textContent = '当前 Tool 未声明可编辑的子字段。';
                editor.appendChild(empty);
            }
            return editor;
        }

        function blueprintDraftPlatformParams(blueprint) {
            const values = {};
            const scopedSelectionTokens = {};
            const evaluated = new Map((blueprintState.evaluation?.fields || []).map(item => [item.path, item]));
            for (const field of (blueprint?.fields || [])) {
                if (field.visible === false) continue;
                let value = blueprintState.values[field.path];
                if (value === undefined) value = evaluated.get(field.path)?.value;
                if (value === undefined) value = blueprintFieldDefault(field);
                const options = blueprintOptions(field, evaluated.get(field.path));
                if (value === undefined && field.presentation === 'derived_readonly' && options.length === 1) value = options[0];
                if (value === undefined || value === null || value === '') continue;
                const { toolName, fieldPath } = blueprintToolFieldSchema(field.tool_ref);
                setCreationNestedValue(values, fieldPath || field.path, value);
                if (toolName) {
                    values[toolName] = values[toolName] || {};
                    setCreationNestedValue(values[toolName], fieldPath || field.path, value);
                }
            }
            Object.entries(blueprintState.selectionTokens || {}).forEach(([fieldName, token]) => {
                const toolName = blueprintState.selectionTokenTools?.[fieldName];
                if (!toolName || !token) return;
                scopedSelectionTokens[toolName] = scopedSelectionTokens[toolName] || {};
                scopedSelectionTokens[toolName][fieldName] = token;
            });
            Object.entries(scopedSelectionTokens).forEach(([toolName, tokens]) => {
                values[toolName] = values[toolName] || {};
                values[toolName].selection_tokens = tokens;
            });
            return { [blueprint.provider]: values };
        }

        function blueprintSelectorOptions(blueprint) {
            const selector = blueprint?.selector;
            if (!selector?.dimension) return [];
            const options = new Map();
            for (const item of blueprintState.items) {
                if (item.provider !== blueprint.provider || item.selector?.dimension !== selector.dimension) continue;
                const labels = new Map((item.selector.options || []).map(option => [String(option.value), option.label || option.value]));
                for (const value of (item.selector.values || [])) {
                    const key = String(value);
                    if (!options.has(key)) options.set(key, labels.get(key) || key);
                }
            }
            return [...options].map(([value, label]) => ({ value, label }));
        }

        const CREATION_FIELD_GROUPS = [
            { id: 'campaign', title: '系列基础', description: '先确定账户、目标、预算与投放节奏。', tokens: ['campaign', 'objective', 'budget', 'bid', 'schedule', 'start', 'end', 'name', 'status', 'optimization'] },
            { id: 'audience', title: '受众与版位', description: '控制广告展示给谁，以及出现在哪里。', tokens: ['audience', 'target', 'location', 'region', 'country', 'city', 'age', 'gender', 'interest', 'behavior', 'placement', 'device', 'language', 'geo'] },
            { id: 'creative', title: '素材与落地页', description: '配置素材、文案、行动按钮和最终到达地址。', tokens: ['creative', 'asset', 'image', 'video', 'headline', 'title', 'body', 'text', 'copy', 'url', 'landing', 'page', 'call_to_action', 'cta', 'thumbnail', 'identity'] },
            { id: 'measurement', title: '转化与追踪', description: '补充 Pixel、事件、归因与数据回传设置。', tokens: ['conversion', 'pixel', 'event', 'tracking', 'track', 'attribution', 'measurement', 'promoted', 'catalog', 'app', 'optimization_goal'] },
            { id: 'advanced', title: '高级设置', description: '仅在需要覆盖默认行为时展开，保持主流程清爽。', tokens: ['advanced', 'json', 'payload', 'custom', 'extra', 'spec', 'raw'] },
            { id: 'other', title: '其他设置', description: '平台特有或暂未归类的参数。', tokens: [] },
        ];

        function fieldSearchText(field) {
            return [field?.path, field?.label, field?.description, field?.control, field?.presentation]
                .filter(Boolean).join(' ').toLowerCase();
        }

        function creationFieldGroup(field) {
            const text = fieldSearchText(field);
            return CREATION_FIELD_GROUPS.find(group => group.tokens.some(token => text.includes(token)))?.id || 'other';
        }

        function creationFieldGroups(fields) {
            const grouped = new Map(CREATION_FIELD_GROUPS.map(group => [group.id, { ...group, fields: [] }]));
            (fields || []).forEach(field => {
                if (field.visible === false) return;
                grouped.get(creationFieldGroup(field)).fields.push(field);
            });
            return CREATION_FIELD_GROUPS.map(group => grouped.get(group.id)).filter(group => group.fields.length);
        }

        function creationDirectoryHierarchy(field) {
            return creationHierarchyLabel(field) || '通用设置';
        }

        function creationDirectoryHierarchyGroups(fields) {
            const grouped = new Map();
            (fields || []).forEach(field => {
                const hierarchy = creationDirectoryHierarchy(field);
                if (!grouped.has(hierarchy)) grouped.set(hierarchy, []);
                grouped.get(hierarchy).push(field);
            });
            return [...grouped.entries()];
        }

        function creationFieldValue(field, value = field?.value) {
            return value === undefined && field?.control === 'checkbox' ? false : value;
        }

        function creationFieldDisplayValue(field, value = field?.value) {
            const normalized = creationFieldValue(field, value);
            if (field?.control === 'checkbox') return normalized ? '已开启' : '未开启';
            return blueprintDisplayValue(normalized);
        }

        function creationFieldNeedsUserInput(field) {
            if (field?.user_required !== undefined) return Boolean(field.user_required);
            return Boolean(field?.required);
        }

        function creationFieldIsAuto(field) {
            return ['auto_default', 'auto_derived'].includes(String(field?.input_mode || '').toLowerCase());
        }

        function creationFieldModeLabel(field) {
            if (field?.auto_filled) return '系统已填 · 可修改';
            if (field?.input_mode === 'context_required') return '需要从账户或业务上下文确认';
            if (field?.input_mode === 'asset_required') return '需要选择素材或素材资源';
            if (creationFieldIsAuto(field)) return '系统将按当前目标自动处理';
            return '';
        }

        function fieldGroupProgress(fields) {
            const visible = (fields || []).filter(field => field.visible !== false);
            const required = visible.filter(creationFieldNeedsUserInput);
            const missing = required.filter(field => creationCardValueEmpty(creationFieldValue(field)) || field.local_error || field.state === 'invalid');
            return { total: visible.length, missing: missing.length, complete: required.length - missing.length };
        }

        function blueprintFieldEvaluation(field, evaluation) {
            const evaluated = evaluation?.fields?.find(item => item.path === field.path) || {};
            const rawValue = evaluated.value !== undefined
                ? evaluated.value
                : blueprintState.values[field.path] !== undefined
                    ? blueprintState.values[field.path] : blueprintFieldDefault(field);
            const value = creationFieldValue(field, rawValue);
            const required = evaluated.required !== undefined ? evaluated.required : Boolean(field.required);
            const visible = evaluated.visible !== false && field.visible !== false;
            const invalid = evaluated.state === 'invalid' || evaluated.local_error;
            const empty = creationCardValueEmpty(value);
            const status = invalid ? 'invalid' : required && empty ? 'missing' : empty ? 'empty' : 'complete';
            return { ...evaluated, value, required, visible, status };
        }

        function blueprintDisplayValue(value) {
            if (creationCardValueEmpty(value)) return '未填写';
            if (Array.isArray(value)) {
                const values = value.map(item => {
                    if (item && typeof item === 'object') return item.name || item.label || item.text || item.asset_id || item.local_file || '已选择';
                    return String(item);
                });
                return values.length > 2 ? `${values.slice(0, 2).join('、')} +${values.length - 2}` : values.join('、');
            }
            if (typeof value === 'object') {
                const entries = Object.entries(value).slice(0, 2).map(([key, item]) => `${key}: ${blueprintDisplayValue(item)}`);
                return entries.join(' · ') || '已填写';
            }
            const text = String(value);
            return text.length > 42 ? `${text.slice(0, 42)}…` : text;
        }

        function creationHierarchyLabel(field) {
            const path = String(field?.path || '').toLowerCase();
            if (/^(campaign|campaigns)\./.test(path)) return 'Campaign 层级';
            if (/^(ad_set|adset)\./.test(path)) return 'Ad Set 层级';
            if (/^(ad_group|adgroup)\./.test(path)) return 'Ad Group 层级';
            if (/^ad\./.test(path)) return 'Ad 层级';
            if (/^insertion_order\./.test(path)) return 'Insertion Order 层级';
            if (/^line_item\./.test(path)) return 'Line Item 层级';
            if (/^creative\./.test(path)) return 'Creative 层级';
            return '';
        }

        function setCreationSectionExpanded(section, expanded) {
            if (!section) return;
            section.classList.toggle('is-collapsed', !expanded);
            const toggle = section.querySelector('.creation-section-toggle');
            if (toggle) {
                toggle.textContent = expanded ? '收起' : '展开';
                toggle.setAttribute('aria-expanded', String(expanded));
            }
        }

        function scrollCreationTarget(target) {
            if (!target) return;
            const container = target.closest('.blueprint-fields, .creation-card-fields');
            if (!container) {
                target.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                return;
            }
            const targetRect = target.getBoundingClientRect();
            const containerRect = container.getBoundingClientRect();
            const offset = targetRect.top - containerRect.top;
            const delta = targetRect.height <= containerRect.height
                ? offset - (containerRect.height - targetRect.height) / 2
                : offset - 12;
            container.scrollBy({ top: delta, behavior: 'smooth' });
        }

        function blueprintScrollTo(target, activeNode = null) {
            if (!target) return;
            const section = target.closest('.blueprint-field-group, .creation-card-section');
            if (section) setCreationSectionExpanded(section, true);
            scrollCreationTarget(target);
            const focusable = target.querySelector('input:not([disabled]), select:not([disabled]), textarea:not([disabled]), button:not([disabled])');
            focusable?.focus({ preventScroll: true });
            document.querySelectorAll('.blueprint-nav-item.active, .blueprint-nav-group.active').forEach(node => node.classList.remove('active'));
            activeNode?.classList.add('active');
        }

        function renderBlueprintFieldNav(blueprint, evaluation) {
            const container = document.getElementById('blueprintFieldNav');
            if (!container || !blueprint) return;
            container.replaceChildren();

            const header = document.createElement('div');
            header.className = 'blueprint-field-nav-header';
            header.innerHTML = '<span>填写目录</span><small>点击字段快速定位</small>';
            container.appendChild(header);

            const groups = creationFieldGroups(blueprint.fields || []);
            groups.forEach((group, groupIndex) => {
                const states = group.fields.map(field => blueprintFieldEvaluation(field, evaluation));
                const visibleFields = group.fields.filter((field, index) => states[index].visible);
                if (!visibleFields.length) return;
                const progress = fieldGroupProgress(group.fields.map((field, index) => ({
                    ...field,
                    ...states[index],
                    value: states[index].value,
                })));

                const groupButton = document.createElement('button');
                groupButton.type = 'button';
                groupButton.className = 'blueprint-nav-group';
                groupButton.dataset.step = group.id;
                const groupCopy = document.createElement('span');
                groupCopy.className = 'blueprint-nav-group-copy';
                const groupTitle = document.createElement('strong');
                groupTitle.textContent = group.title;
                const groupMeta = document.createElement('small');
                groupMeta.textContent = progress.missing ? `待填 ${progress.missing} · 共 ${progress.total} 项` : `已就绪 · 共 ${progress.total} 项`;
                groupCopy.append(groupTitle, groupMeta);
                const groupStatus = document.createElement('span');
                groupStatus.className = `blueprint-nav-status${progress.missing ? ' missing' : ' complete'}`;
                groupStatus.textContent = progress.missing ? '!' : '✓';
                groupButton.append(groupStatus, groupCopy);
                groupButton.addEventListener('click', () => {
                    blueprintScrollTo(document.querySelector(`#blueprintFields [data-step="${CSS.escape(group.id)}"]`), groupButton);
                });
                container.appendChild(groupButton);

                const fieldList = document.createElement('div');
                fieldList.className = 'blueprint-nav-fields';
                creationDirectoryHierarchyGroups(visibleFields).forEach(([hierarchy, hierarchyFields]) => {
                    const branch = document.createElement('div');
                    branch.className = 'blueprint-nav-hierarchy';
                    const branchKey = `blueprint:${blueprint.id || blueprint.provider}:${group.id}:${hierarchy}`;
                    const collapsed = creationDirectoryCollapseState.get(branchKey) === true;
                    if (collapsed) branch.classList.add('is-collapsed');
                    const branchButton = document.createElement('button');
                    branchButton.type = 'button';
                    branchButton.className = 'blueprint-nav-hierarchy-toggle';
                    branchButton.setAttribute('aria-expanded', String(!collapsed));
                    const branchMarker = document.createElement('span');
                    branchMarker.className = 'blueprint-nav-hierarchy-marker';
                    branchMarker.textContent = collapsed ? '›' : '⌄';
                    const branchCopy = document.createElement('span');
                    branchCopy.className = 'blueprint-nav-hierarchy-copy';
                    const branchTitle = document.createElement('strong');
                    branchTitle.textContent = hierarchy;
                    const branchCount = document.createElement('small');
                    branchCount.textContent = `${hierarchyFields.length} 项`;
                    branchCopy.append(branchTitle, branchCount);
                    branchButton.append(branchMarker, branchCopy);
                    const hierarchyList = document.createElement('div');
                    hierarchyList.className = 'blueprint-nav-hierarchy-fields';
                    branchButton.addEventListener('click', () => {
                        const nextCollapsed = !branch.classList.contains('is-collapsed');
                        branch.classList.toggle('is-collapsed', nextCollapsed);
                        creationDirectoryCollapseState.set(branchKey, nextCollapsed);
                        branchButton.setAttribute('aria-expanded', String(!nextCollapsed));
                        branchMarker.textContent = nextCollapsed ? '›' : '⌄';
                    });
                    hierarchyFields.forEach(field => {
                        const state = blueprintFieldEvaluation(field, evaluation);
                        const button = document.createElement('button');
                        button.type = 'button';
                        button.className = `blueprint-nav-item${state.status === 'missing' ? ' missing' : ''}${state.status === 'invalid' ? ' invalid' : ''}${state.status === 'complete' ? ' complete' : ''}`;
                        button.dataset.fieldPath = field.path;
                        const status = document.createElement('span');
                        status.className = 'blueprint-nav-field-status';
                        status.textContent = state.status === 'invalid' ? '!' : state.status === 'missing' ? '•' : state.status === 'complete' ? '✓' : '·';
                        const copy = document.createElement('span');
                        copy.className = 'blueprint-nav-item-copy';
                        const label = document.createElement('span');
                        label.textContent = field.label || field.path;
                        const value = document.createElement('small');
                        value.textContent = creationFieldDisplayValue(field, state.value);
                        copy.append(label, value);
                        button.append(status, copy);
                        button.addEventListener('click', () => {
                            blueprintScrollTo(document.querySelector(`#blueprintFields [data-field-path="${CSS.escape(field.path)}"]`), button);
                        });
                        hierarchyList.appendChild(button);
                    });
                    branch.append(branchButton, hierarchyList);
                    fieldList.appendChild(branch);
                });
                container.appendChild(fieldList);
            });
        }

        function renderBlueprintSummary(blueprint, evaluation) {
            const container = document.getElementById('blueprintSummary');
            if (!container || !blueprint) return;
            container.replaceChildren();
            const fields = (blueprint.fields || []).filter(field => blueprintFieldEvaluation(field, evaluation).visible);
            const completed = fields.filter(field => !creationCardValueEmpty(blueprintFieldEvaluation(field, evaluation).value));
            const totalRequired = fields.filter(field => blueprintFieldEvaluation(field, evaluation).required).length;
            const missing = evaluation?.missing_fields?.length || fields.filter(field => blueprintFieldEvaluation(field, evaluation).status === 'missing').length;

            const heading = document.createElement('div');
            heading.className = 'blueprint-summary-heading';
            heading.innerHTML = '<span>实时摘要</span><small>滚动填写时始终可见</small>';
            const progress = document.createElement('span');
            progress.className = `blueprint-summary-progress${missing ? ' pending' : ' ready'}`;
            progress.textContent = missing ? `待补 ${missing} 项` : `${Math.min(completed.length, totalRequired || completed.length)}/${totalRequired || completed.length} 项就绪`;
            heading.appendChild(progress);
            container.appendChild(heading);

            const items = document.createElement('div');
            items.className = 'blueprint-summary-items';
            const accountItem = document.createElement('button');
            accountItem.type = 'button';
            accountItem.className = `blueprint-summary-item${blueprintState.accountId ? ' filled' : ' pending'}`;
            accountItem.innerHTML = `<span class="blueprint-summary-item-label">${escapeHtml(creationAccountLabel(blueprint.provider))}</span><strong>${escapeHtml(blueprintState.accountId || '未填写')}</strong>`;
            accountItem.addEventListener('click', () => document.getElementById('blueprintAccountInput')?.focus());
            items.appendChild(accountItem);

            const selectedFields = fields.filter(field => !creationCardValueEmpty(blueprintFieldEvaluation(field, evaluation).value)).slice(0, 6);
            selectedFields.forEach(field => {
                const state = blueprintFieldEvaluation(field, evaluation);
                const item = document.createElement('button');
                item.type = 'button';
                item.className = `blueprint-summary-item${state.status === 'invalid' ? ' invalid' : ' filled'}`;
                item.innerHTML = `<span class="blueprint-summary-item-label">${escapeHtml(field.label || field.path)}</span><strong>${escapeHtml(creationFieldDisplayValue(field, state.value))}</strong>`;
                item.addEventListener('click', () => {
                    blueprintScrollTo(document.querySelector(`#blueprintFields [data-field-path="${CSS.escape(field.path)}"]`));
                });
                items.appendChild(item);
            });
            const remaining = completed.length - selectedFields.length;
            if (remaining > 0) {
                const more = document.createElement('span');
                more.className = 'blueprint-summary-more';
                more.textContent = `还有 ${remaining} 项已填写`;
                items.appendChild(more);
            }
            container.appendChild(items);
        }

        function choiceDisplayLabel(value, label = '') {
            if (label && String(label) !== String(value)) return String(label);
            const text = String(value ?? '');
            const known = {
                ANDROID: 'Android', IOS: 'iOS',
                PLACEMENT_TIKTOK: 'TikTok 信息流', PLACEMENT_PANGLE: 'Pangle',
                PLACEMENT_GLOBAL_APP_BUNDLE: 'Global App Bundle',
                AGE_13_17: '13–17 岁', AGE_18_24: '18–24 岁', AGE_25_34: '25–34 岁',
                AGE_35_44: '35–44 岁', AGE_45_54: '45–54 岁', AGE_55_64: '55–64 岁', 'AGE_65+': '65 岁以上',
            };
            if (known[text]) return known[text];
            return text.toLowerCase().split(/[_-]+/).map(part => part ? part[0].toUpperCase() + part.slice(1) : '').join(' ');
        }

        function renderChoiceTiles(options, selectedValues, multiple, labelFor, onChange) {
            const control = document.createElement('div');
            control.className = `choice-tiles${multiple ? ' multiple' : ''}`;
            const groupName = `choice-${Math.random().toString(36).slice(2)}`;
            const selected = new Set((Array.isArray(selectedValues) ? selectedValues : [selectedValues])
                .filter(value => value !== undefined && value !== null && value !== '').map(String));
            options.forEach(option => {
                const value = typeof option === 'object' ? String(option.value ?? '') : String(option);
                if (!value) return;
                const suppliedLabel = typeof option === 'object' ? (option.label || labelFor?.(option.value) || '') : (labelFor?.(option) || '');
                const label = choiceDisplayLabel(value, suppliedLabel);
                const item = document.createElement('label');
                item.className = `choice-tile${selected.has(value) ? ' selected' : ''}`;
                const input = document.createElement('input');
                input.type = multiple ? 'checkbox' : 'radio';
                input.name = groupName;
                input.value = value;
                input.checked = selected.has(value);
                input.addEventListener('change', () => {
                    if (multiple) {
                        item.classList.toggle('selected', input.checked);
                        const values = Array.from(control.querySelectorAll('input:checked')).map(node => node.value);
                        onChange(values);
                    } else if (input.checked) {
                        control.querySelectorAll('.choice-tile').forEach(node => node.classList.remove('selected'));
                        item.classList.add('selected');
                        onChange(value);
                    }
                });
                const copy = document.createElement('span');
                copy.className = 'choice-copy';
                const title = document.createElement('strong');
                title.textContent = label;
                copy.appendChild(title);
                if (label !== value) {
                    const raw = document.createElement('small');
                    raw.textContent = value;
                    copy.appendChild(raw);
                }
                item.append(input, copy);
                control.appendChild(item);
            });
            return control;
        }

        function renderBlueprintFlowbar(blueprint, evaluation) {
            const container = document.getElementById('blueprintFlowbar');
            if (!container || !blueprint) return;
            const groups = creationFieldGroups(blueprint.fields || []);
            container.replaceChildren();
            groups.forEach((group, index) => {
                const progress = fieldGroupProgress(group.fields.map(field => {
                    const state = evaluation?.fields?.find(item => item.path === field.path);
                    return {
                        ...field,
                        required: state?.required ?? field.required,
                        state: state?.state,
                        value: state?.value ?? blueprintState.values[field.path],
                    };
                }));
                const button = document.createElement('button');
                button.type = 'button';
                button.className = `blueprint-flow-step${index === 0 ? ' active' : ''}${progress.missing ? ' has-missing' : ''}`;
                button.dataset.step = group.id;
                button.innerHTML = `<span class="blueprint-flow-index">${index + 1}</span><span class="blueprint-flow-copy"><strong>${escapeHtml(group.title)}</strong><small>${progress.missing ? `待填 ${progress.missing}` : '已就绪'}</small></span>`;
                button.addEventListener('click', () => {
                    blueprintScrollTo(document.querySelector(`#blueprintFields [data-step="${CSS.escape(group.id)}"]`));
                    container.querySelectorAll('.blueprint-flow-step').forEach(node => node.classList.toggle('active', node === button));
                });
                container.appendChild(button);
            });
            if (evaluation) {
                const summary = document.createElement('span');
                summary.className = 'blueprint-flow-summary';
                summary.textContent = evaluation.missing_fields?.length ? `${evaluation.missing_fields.length} 项待补充` : '必填参数已齐';
                container.appendChild(summary);
            }
        }

        function renderBlueprintSelector() {
            const container = document.getElementById('blueprintSelector');
            const blueprint = blueprintState.selected;
            if (!container || !blueprint?.selector) {
                if (container) container.replaceChildren();
                return;
            }
            const selector = blueprint.selector;
            const options = blueprintSelectorOptions(blueprint);
            container.replaceChildren();
            const label = document.createElement('label');
            label.className = 'blueprint-selector-label';
            label.textContent = `${blueprint.provider} · ${selector.label || (selector.dimension === 'objective' ? '推广目标' : '广告系列类型')}`;
            const control = document.createElement('select');
            const placeholder = document.createElement('option');
            placeholder.value = '';
            placeholder.textContent = '请选择入口…';
            control.appendChild(placeholder);
            for (const option of options) {
                const optionNode = document.createElement('option');
                optionNode.value = option.value;
                optionNode.textContent = option.label;
                control.appendChild(optionNode);
            }
            const current = blueprintState.values[selector.field];
            control.value = current === undefined ? '' : String(current);
            control.onchange = () => chooseBlueprintEntry(blueprint.provider, selector.dimension, control.value);
            const hint = document.createElement('div');
            hint.className = 'blueprint-selector-hint';
            hint.textContent = selector.dimension === 'objective'
                ? '先选推广目标，后续只展示该目标适用的参数。'
                : '先选广告系列类型，后续只展示该类型适用的参数。';
            container.append(label, control, hint);
        }

        function chooseBlueprintEntry(provider, dimension, value) {
            if (!value) return;
            const item = blueprintState.items.find(candidate =>
                candidate.provider === provider && candidate.selector?.dimension === dimension &&
                (candidate.selector.values || []).map(String).includes(String(value))
            );
            if (item) selectBlueprint(item.id, value);
        }

        async function loadCreationBlueprints(selectId = null) {
            const list = document.getElementById('blueprintList');
            if (list) list.innerHTML = '<div class="blueprint-empty">正在加载广告创建蓝图…</div>';
            try {
                const [blueprints, tools, templates] = await Promise.all([
                    apiFetch('/creation-blueprints'),
                    apiFetch('/tools'),
                    apiFetch('/creation-templates').catch(() => ({ templates: [] })),
                ]);
                blueprintState.items = Array.isArray(blueprints.blueprints) ? blueprints.blueprints : [];
                blueprintState.tools = Array.isArray(tools.tools) ? tools.tools : [];
                blueprintState.templates = Array.isArray(templates.templates) ? templates.templates : [];
                renderBlueprintList();
                const target = selectId || blueprintState.selected?.id || blueprintState.items[0]?.id;
                if (target) selectBlueprint(target);
            } catch (error) {
                if (list) {
                    list.replaceChildren();
                    const empty = document.createElement('div');
                    empty.className = 'blueprint-empty';
                    empty.textContent = error.message || '蓝图加载失败，请稍后重试。';
                    list.appendChild(empty);
                }
            }
        }

        function renderBlueprintList() {
            const list = document.getElementById('blueprintList');
            if (!list) return;
            list.replaceChildren();
            const toolbar = document.createElement('div');
            toolbar.className = 'blueprint-list-toolbar';
            const toolbarTitle = document.createElement('div');
            toolbarTitle.className = 'blueprint-list-toolbar-title';
            toolbarTitle.innerHTML = '<strong>创建工作台</strong><span>先选我的模板，也可以从系统蓝图开始</span>';
            const search = document.createElement('input');
            search.type = 'search';
            search.className = 'blueprint-list-search';
            search.placeholder = '搜索广告类型…';
            search.value = blueprintState.listQuery || '';
            search.setAttribute('aria-label', '搜索广告创建模板');
            search.addEventListener('input', () => {
                blueprintState.listQuery = search.value;
                renderBlueprintList();
                const next = document.querySelector('.blueprint-list-search');
                next?.focus({ preventScroll: true });
                if (next) next.setSelectionRange(blueprintState.listQuery.length, blueprintState.listQuery.length);
            });
            const providers = [...new Set(blueprintState.items.map(item => item.provider))];
            const filter = document.createElement('select');
            filter.className = 'blueprint-list-filter';
            filter.setAttribute('aria-label', '按广告平台筛选');
            [['all', '全部渠道'], ...providers.map(provider => [provider, creationProviderLabel(provider)])].forEach(([value, label]) => {
                const option = document.createElement('option');
                option.value = value;
                option.textContent = label;
                option.selected = value === (blueprintState.listProvider || 'all');
                filter.appendChild(option);
            });
            filter.addEventListener('change', () => {
                blueprintState.listProvider = filter.value;
                renderBlueprintList();
            });
            toolbar.append(toolbarTitle, search, filter);
            list.appendChild(toolbar);
            const items = document.createElement('div');
            items.className = 'blueprint-list-items';
            list.appendChild(items);
            const query = String(blueprintState.listQuery || '').trim().toLowerCase();
            const matches = item => {
                if (blueprintState.listProvider !== 'all' && item.provider !== blueprintState.listProvider) return false;
                if (!query) return true;
                return [item.title, item.name, item.id, item.provider, item.ad_format, item.scope_label, item.selector?.label]
                    .filter(Boolean).join(' ').toLowerCase().includes(query);
            };
            const visibleTemplates = blueprintState.templates.filter(matches);
            const visibleItems = blueprintState.items.filter(matches);
            const renderSection = (title, subtitle, values, renderItem) => {
                if (!values.length) return;
                const section = document.createElement('section');
                section.className = 'blueprint-list-section';
                const heading = document.createElement('div');
                heading.className = 'blueprint-list-section-heading';
                heading.innerHTML = `<strong>${escapeHtml(title)}</strong><span>${escapeHtml(subtitle)}</span>`;
                section.appendChild(heading);
                values.forEach(item => section.appendChild(renderItem(item)));
                items.appendChild(section);
            };
            renderSection('我的模板', '可按账户与地区复用', visibleTemplates, template => {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = `blueprint-list-item blueprint-template-item${blueprintState.selectedTemplateId === template.template_id ? ' active' : ''}`;
                button.onclick = () => selectCreationTemplate(template.template_id);
                const title = document.createElement('span');
                title.className = 'blueprint-list-title';
                title.textContent = template.name || '未命名模板';
                const meta = document.createElement('span');
                meta.className = 'blueprint-list-meta';
                meta.textContent = `${creationProviderLabel(template.provider)} · ${template.scope_label || '个人通用'}${template.is_default ? ' · 默认' : ''} · ${template.covered_fields || 0} 项`;
                button.append(title, meta);
                return button;
            });
            renderSection('系统蓝图', '平台维护的字段与联动规则', visibleItems, item => {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = `blueprint-list-item${!blueprintState.selectedTemplateId && blueprintState.selected?.id === item.id ? ' active' : ''}`;
                button.onclick = () => selectBlueprint(item.id);
                const title = document.createElement('span');
                title.className = 'blueprint-list-title';
                title.textContent = item.title || item.id;
                const meta = document.createElement('span');
                meta.className = 'blueprint-list-meta';
                meta.textContent = `${creationProviderLabel(item.provider)} · ${item.ad_format} · v${item.version}`;
                button.append(title, meta);
                return button;
            });
            if (!visibleTemplates.length && !visibleItems.length) {
                const empty = document.createElement('div');
                empty.className = 'blueprint-empty';
                empty.textContent = '没有匹配的模板或广告类型，换个关键词试试。';
                items.appendChild(empty);
            }
        }

        function selectBlueprint(blueprintId, selectorValue = null, template = null) {
            const item = blueprintState.items.find(value => value.id === blueprintId);
            if (!item) return;
            if (!template) {
                template = blueprintState.templates.find(candidate => candidate.status === 'active'
                    && candidate.is_default
                    && candidate.blueprint_id === item.id
                    && (!candidate.blueprint_version || candidate.blueprint_version === item.version)
                    && (candidate.scope_type === 'general'
                        || (candidate.scope_type === 'account' && candidate.account_id === blueprintState.accountId))
                ) || null;
            }
            blueprintState.selected = item;
            blueprintState.values = blueprintDefaultValues(item);
            blueprintState.previousValues = {};
            blueprintState.evaluation = null;
            blueprintState.localFiles = {};
            blueprintState.selectionTokens = {};
            blueprintState.selectionTokenTools = {};
            blueprintState.lookupOptions = {};
            blueprintState.selectedTemplateId = template?.template_id || '';
            const selector = item.selector;
            const initialValue = selectorValue || selector?.values?.[0];
            if (selector?.field && initialValue !== undefined) blueprintState.values[selector.field] = initialValue;
            if (template?.values && typeof template.values === 'object') {
                Object.assign(blueprintState.values, template.values);
                if (template.account_id) blueprintState.accountId = template.account_id;
            }
            const templatePanel = document.getElementById('blueprintTemplatePanel');
            if (templatePanel) templatePanel.hidden = true;
            blueprintState.templatePanelOpen = false;
            blueprintState.templateSaveAsNew = false;
            renderBlueprintList();
            renderBlueprintEditor();
            if (template) showBlueprintNotice(`已应用“${template.name || '我的模板'}”，你仍可修改本次投放参数。`);
            if (selector?.field) evaluateBlueprintDraft(selector.field);
        }

        function selectCreationTemplate(templateId) {
            const template = blueprintState.templates.find(item => item.template_id === templateId);
            if (!template) return;
            const blueprint = blueprintState.items.find(item => item.id === template.blueprint_id && (
                !template.blueprint_version || item.version === template.blueprint_version
            )) || blueprintState.items.find(item => item.id === template.blueprint_id);
            if (!blueprint) {
                showBlueprintNotice('模板依赖的系统蓝图已升级或下线，请复制模板后重新配置。');
                return;
            }
            selectBlueprint(blueprint.id, null, template);
            if (template.status === 'active') {
                apiFetch(`/creation-templates/${encodeURIComponent(templateId)}/apply`, { method: 'POST' }).catch(() => {});
            } else {
                showBlueprintNotice('这是已停用模板，仅用于查看和编辑；重新启用后才能带入对话。');
            }
        }

        function toggleCreationTemplatePanel(force, saveAsNew = false) {
            const panel = document.getElementById('blueprintTemplatePanel');
            if (!panel) return;
            const open = force === undefined ? panel.hidden : Boolean(force);
            panel.hidden = !open;
            blueprintState.templatePanelOpen = open;
            blueprintState.templateSaveAsNew = open && saveAsNew;
            if (!open) return;
            const template = !blueprintState.templateSaveAsNew
                ? blueprintState.templates.find(item => item.template_id === blueprintState.selectedTemplateId)
                : null;
            const fields = {
                creationTemplateName: template?.name || '',
                creationTemplateScope: template?.scope_type || 'general',
                creationTemplateAccount: template?.account_id || blueprintState.accountId || '',
                creationTemplateRegion: template?.region || '',
                creationTemplateTags: Array.isArray(template?.tags) ? template.tags.join(', ') : '',
                creationTemplateDescription: template?.description || '',
            };
            Object.entries(fields).forEach(([id, value]) => {
                const control = document.getElementById(id);
                if (control) control.value = value;
            });
            const title = document.getElementById('blueprintTemplatePanelTitle');
            if (title) title.textContent = template ? '更新当前模板' : '保存当前参数为模板';
            const submit = document.getElementById('creationTemplateSubmitButton');
            if (submit) submit.textContent = template ? '保存修改' : '保存模板';
            const defaultInput = document.getElementById('creationTemplateDefault');
            if (defaultInput) defaultInput.checked = Boolean(template?.is_default);
        }

        function creationTemplatePayload() {
            const blueprint = blueprintState.selected;
            if (!blueprint) return null;
            return {
                name: document.getElementById('creationTemplateName')?.value.trim() || '',
                description: document.getElementById('creationTemplateDescription')?.value.trim() || '',
                provider: blueprint.provider,
                blueprint_id: blueprint.id,
                blueprint_version: blueprint.version,
                ad_format: blueprint.ad_format,
                scope_type: document.getElementById('creationTemplateScope')?.value || 'general',
                account_id: document.getElementById('creationTemplateAccount')?.value.trim() || '',
                region: document.getElementById('creationTemplateRegion')?.value.trim() || '',
                tags: (document.getElementById('creationTemplateTags')?.value || '').split(',').map(item => item.trim()).filter(Boolean),
                values: { ...(blueprintState.values || {}) },
                status: 'active',
                is_default: Boolean(document.getElementById('creationTemplateDefault')?.checked),
            };
        }

        async function saveCreationTemplate(forceCreate = false) {
            const payload = creationTemplatePayload();
            if (!payload) return;
            if (!payload.name) {
                showBlueprintNotice('请先填写模板名称。');
                document.getElementById('creationTemplateName')?.focus();
                return;
            }
            const templateId = forceCreate || blueprintState.templateSaveAsNew ? '' : blueprintState.selectedTemplateId;
            try {
                const result = await apiFetch(templateId
                    ? `/creation-templates/${encodeURIComponent(templateId)}`
                    : '/creation-templates', {
                        method: templateId ? 'PATCH' : 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload),
                    });
                const index = blueprintState.templates.findIndex(item => item.template_id === result.template_id);
                if (index >= 0) blueprintState.templates[index] = result;
                else blueprintState.templates.unshift(result);
                blueprintState.selectedTemplateId = result.template_id;
                toggleCreationTemplatePanel(false);
                renderBlueprintList();
                renderBlueprintEditor();
                showBlueprintNotice(`模板“${result.name}”已保存，可在左侧“我的模板”中复用。`);
            } catch (error) {
                showBlueprintNotice(error.message || '模板保存失败。');
            }
        }

        function updateSelectedCreationTemplate() {
            if (!blueprintState.selectedTemplateId) return;
            toggleCreationTemplatePanel(true);
        }

        async function duplicateSelectedCreationTemplate() {
            const templateId = blueprintState.selectedTemplateId;
            if (!templateId) return;
            const source = blueprintState.templates.find(item => item.template_id === templateId);
            const name = window.prompt('请输入副本名称', `${source?.name || '创建模板'} · 副本`);
            if (!name) return;
            try {
                const result = await apiFetch(`/creation-templates/${encodeURIComponent(templateId)}/duplicate`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }),
                });
                blueprintState.templates.unshift(result);
                blueprintState.selectedTemplateId = result.template_id;
                renderBlueprintList();
                renderBlueprintEditor();
                showBlueprintNotice(`模板副本“${result.name}”已创建。`);
            } catch (error) { showBlueprintNotice(error.message || '模板复制失败。'); }
        }

        async function toggleSelectedCreationTemplateStatus() {
            const template = blueprintState.templates.find(item => item.template_id === blueprintState.selectedTemplateId);
            if (!template) return;
            const nextStatus = template.status === 'active' ? 'inactive' : 'active';
            try {
                const result = await apiFetch(`/creation-templates/${encodeURIComponent(template.template_id)}`, {
                    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status: nextStatus }),
                });
                const index = blueprintState.templates.findIndex(item => item.template_id === result.template_id);
                if (index >= 0) blueprintState.templates[index] = result;
                renderBlueprintList();
                renderBlueprintEditor();
                showBlueprintNotice(nextStatus === 'active' ? '模板已重新启用。' : '模板已停用，不会再出现在可应用模板中。');
            } catch (error) { showBlueprintNotice(error.message || '模板状态更新失败。'); }
        }

        async function deleteSelectedCreationTemplate() {
            const template = blueprintState.templates.find(item => item.template_id === blueprintState.selectedTemplateId);
            if (!template || !window.confirm(`确定删除模板“${template.name}”吗？`)) return;
            try {
                await apiFetch(`/creation-templates/${encodeURIComponent(template.template_id)}`, { method: 'DELETE' });
                blueprintState.templates = blueprintState.templates.filter(item => item.template_id !== template.template_id);
                blueprintState.selectedTemplateId = '';
                selectBlueprint(blueprintState.selected?.id || blueprintState.items[0]?.id);
                showBlueprintNotice('模板已删除。');
            } catch (error) { showBlueprintNotice(error.message || '模板删除失败。'); }
        }

        function renderBlueprintEditor() {
            const blueprint = blueprintState.selected;
            const title = document.getElementById('blueprintEditorTitle');
            const meta = document.getElementById('blueprintEditorMeta');
            if (!blueprint) return;
            const template = blueprintState.templates.find(item => item.template_id === blueprintState.selectedTemplateId);
            if (title) title.textContent = blueprint.title || blueprint.id;
            if (meta) meta.textContent = `${creationProviderLabel(blueprint.provider)} · ${blueprint.ad_format} · 蓝图 v${blueprint.version}${template ? ` · 已应用模板：${template.name}` : ''}`;
            const saveButton = document.getElementById('blueprintTemplateSaveButton');
            const updateButton = document.getElementById('blueprintTemplateUpdateButton');
            const duplicateButton = document.getElementById('blueprintTemplateDuplicateButton');
            const statusButton = document.getElementById('blueprintTemplateStatusButton');
            const deleteButton = document.getElementById('blueprintTemplateDeleteButton');
            if (saveButton) saveButton.textContent = template ? '另存为模板' : '保存为模板';
            if (updateButton) updateButton.hidden = !template;
            if (duplicateButton) duplicateButton.hidden = !template;
            if (statusButton) {
                statusButton.hidden = !template;
                statusButton.textContent = template?.status === 'active' ? '停用' : '启用';
            }
            if (deleteButton) deleteButton.hidden = !template;
            const accountInput = document.getElementById('blueprintAccountInput');
            const accountLabel = document.querySelector('label[for="blueprintAccountInput"]');
            if (accountLabel) accountLabel.innerHTML = `${escapeHtml(creationAccountLabel(blueprint.provider))} <span class="blueprint-required">*</span>`;
            if (accountInput) {
                accountInput.placeholder = `请输入本次要操作的${creationAccountLabel(blueprint.provider)}`;
                accountInput.value = blueprintState.accountId || '';
                accountInput.oninput = () => {
                    blueprintState.accountId = accountInput.value.trim();
                    refreshLookupAccountState(document.getElementById('blueprintFields'));
                    renderBlueprintSummary(blueprint, blueprintState.evaluation);
                };
            }
            renderBlueprintSelector();
            renderBlueprintFlowbar(blueprint, blueprintState.evaluation);
            renderBlueprintFields(blueprintState.evaluation);
            renderBlueprintFieldNav(blueprint, blueprintState.evaluation);
            renderBlueprintSummary(blueprint, blueprintState.evaluation);
        }

        function renderBlueprintFields(evaluation) {
            const container = document.getElementById('blueprintFields');
            const blueprint = blueprintState.selected;
            if (!container || !blueprint) return;
            container.replaceChildren();
            const stateMap = new Map((evaluation?.fields || []).map(item => [item.path, item]));
            const groups = creationFieldGroups(blueprint.fields || []);
            groups.forEach((group, groupIndex) => {
                const section = document.createElement('section');
                section.className = `blueprint-field-group${groupIndex === 0 ? ' active' : ''}`;
                if (['advanced', 'other'].includes(group.id)) section.classList.add('is-collapsed');
                section.dataset.step = group.id;
                const sectionHeader = document.createElement('div');
                sectionHeader.className = 'blueprint-field-group-header';
                sectionHeader.innerHTML = `<div><span class="blueprint-field-group-index">${String(groupIndex + 1).padStart(2, '0')}</span><div><h3>${escapeHtml(group.title)}</h3><p>${escapeHtml(group.description)}</p></div></div><span class="blueprint-field-group-count">${group.fields.length} 项</span>`;
                const sectionToggle = document.createElement('button');
                sectionToggle.type = 'button';
                sectionToggle.className = 'creation-section-toggle';
                sectionToggle.setAttribute('aria-expanded', String(!section.classList.contains('is-collapsed')));
                sectionToggle.textContent = section.classList.contains('is-collapsed') ? '展开' : '收起';
                sectionToggle.addEventListener('click', event => {
                    event.stopPropagation();
                    setCreationSectionExpanded(section, section.classList.contains('is-collapsed'));
                });
                sectionHeader.appendChild(sectionToggle);
                section.appendChild(sectionHeader);
                const sectionFields = document.createElement('div');
                sectionFields.className = 'blueprint-field-group-fields';
                section.appendChild(sectionFields);
                container.appendChild(section);
                for (const field of group.fields) {
                const fieldRef = blueprintToolFieldSchema(field.tool_ref);
                const schema = fieldRef.schema || {};
                const sourceTool = (blueprintState.tools || []).find(item => item.name === fieldRef.toolName);
                const schemaRequired = Boolean(
                    schema.required ||
                    sourceTool?.input_schema?.required?.includes?.(fieldRef.fieldPath)
                );
                const fieldSource = schema.lookup_tool || schema.lookup?.tool
                    ? 'lookup'
                    : field.source || (schema.enum || schema.items?.enum ? 'enum' : 'tool_schema');
                const fieldView = {
                    ...field,
                    source: fieldSource,
                    presentation: field.presentation || schema.presentation,
                    accept: field.accept || schema.accept,
                    lookup_tool: field.lookup_tool || schema.lookup_tool,
                    lookup_result_key: field.lookup_result_key || schema.lookup_result_key,
                    lookup_query_field: field.lookup_query_field || schema.lookup_query_field,
                    lookup_defaults: field.lookup_defaults || schema.lookup_defaults,
                    manual_entry: field.manual_entry || schema.manual_entry,
                };
                const state = stateMap.get(field.path) || {
                    visible: true,
                    required: Boolean(field.required || schemaRequired),
                    state: 'optional',
                };
                const wrapper = document.createElement('div');
                const wideField = fieldView.source === 'lookup'
                    || ['asset_picker', 'file_reference', 'text_list', 'object_editor'].includes(fieldView.presentation)
                    || schema.type === 'object' || schema.type === 'array' || Array.isArray(schema.type);
                wrapper.className = `blueprint-field${wideField ? ' wide' : ''}${state.visible === false ? ' hidden' : ''}${state.state === 'missing' ? ' missing' : ''}${state.state === 'invalid' ? ' invalid' : ''}`;
                wrapper.dataset.fieldPath = field.path;
                const label = document.createElement('label');
                label.className = 'blueprint-field-label';
                label.textContent = field.label || field.path;
                if (state.required) {
                    const required = document.createElement('span');
                    required.className = 'blueprint-required';
                    required.textContent = '*';
                    label.appendChild(required);
                }
                const hierarchy = creationHierarchyLabel(field);
                if (hierarchy) {
                    const badge = document.createElement('span');
                    badge.className = 'creation-hierarchy-badge';
                    badge.textContent = hierarchy;
                    label.appendChild(badge);
                }
                wrapper.appendChild(label);
                const fieldHint = schemaConstraintHint(schema);
                const fieldDescription = [field.description || schema.description, fieldHint ? `参数限制：${fieldHint}` : '']
                    .filter(Boolean).join('；');
                if (fieldDescription) {
                    const help = document.createElement('div');
                    help.className = 'blueprint-field-help';
                    help.textContent = fieldDescription;
                    wrapper.appendChild(help);
                }
                const options = blueprintOptions(fieldView, state);
                const defaultValue = blueprintFieldDefault(field);
                const displayValue = state.value !== undefined && state.value !== null
                    ? state.value : blueprintState.values[field.path] !== undefined
                        ? blueprintState.values[field.path] : defaultValue;
                let control;
                if (fieldView.presentation === 'file_reference') {
                    control = document.createElement('div');
                    control.className = 'asset-picker';
                    const idInput = document.createElement('input');
                    idInput.type = 'text';
                    idInput.placeholder = '填写已上传的素材 ID，或先选择本地文件作为草稿';
                    idInput.value = displayValue === undefined ? '' : String(displayValue);
                    idInput.addEventListener('change', () => updateBlueprintField(field, idInput.value.trim()));
                    const fileInput = document.createElement('input');
                    fileInput.type = 'file';
                    fileInput.accept = fieldView.accept || '*/*';
                    fileInput.addEventListener('change', () => {
                        const file = fileInput.files?.[0];
                        if (!file) return;
                        blueprintState.localFiles[field.path] = {
                            local_file: file.name,
                            mime_type: file.type || 'application/octet-stream',
                            size_bytes: file.size,
                            source: 'local_staging',
                        };
                        const note = control.querySelector('.asset-picker-note');
                        if (note) note.textContent = `已加入本地草稿：${file.name}（未上传，提交前仍需素材 ID）`;
                    });
                    control.append(idInput, fileInput);
                    const note = document.createElement('div');
                    note.className = 'asset-picker-note';
                    note.textContent = '本地文件仅用于准备素材，不会自动上传；执行前仍需对应平台素材 ID。';
                    control.appendChild(note);
                } else if (fieldView.presentation === 'asset_picker') {
                    control = document.createElement('div');
                    control.className = 'asset-picker';
                    const fileInput = document.createElement('input');
                    fileInput.type = 'file';
                    fileInput.multiple = true;
                    fileInput.accept = fieldView.accept || '*/*';
                    fileInput.addEventListener('change', () => {
                        const existing = Array.isArray(blueprintState.values[field.path]) ? blueprintState.values[field.path] : [];
                        const selected = Array.from(fileInput.files || []).map(file => ({
                            local_file: file.name, mime_type: file.type || 'application/octet-stream', size_bytes: file.size,
                            source: 'local_staging',
                        }));
                        blueprintState.values[field.path] = [...existing, ...selected];
                        evaluateBlueprintDraft(field.path);
                    });
                    control.appendChild(fileInput);
                    const staged = Array.isArray(displayValue) ? displayValue : [];
                    if (staged.length) {
                        const list = document.createElement('div');
                        list.className = 'asset-picker-list';
                        staged.slice(0, 20).forEach(item => {
                            const chip = document.createElement('span');
                            chip.className = 'asset-chip';
                            chip.textContent = item && typeof item === 'object'
                                ? `${item.local_file || item.asset_id || item.name || '素材'}${item.source === 'local_staging' ? ' · 未上传' : ''}`
                                : String(item);
                            list.appendChild(chip);
                        });
                        control.appendChild(list);
                    }
                    const note = document.createElement('div');
                    note.className = 'asset-picker-note';
                    note.textContent = '可选择本地文件加入草稿；当前只保存文件信息，不上传到广告平台。';
                    control.appendChild(note);
                } else if (fieldView.presentation === 'derived_readonly') {
                    control = document.createElement('input');
                    control.className = 'derived-readonly';
                    control.readOnly = true;
                    control.disabled = true;
                    control.value = displayValue === undefined ? (options[0] || '') : String(displayValue);
                } else if (fieldView.source === 'lookup') {
                    const lookupRef = blueprintToolFieldSchema(field.tool_ref);
                    const lookupKey = lookupRef.fieldPath || field.path;
                    control = renderLookupPicker({ ...fieldView, value: displayValue, tool: lookupRef.toolName }, {
                        platform: blueprint.provider,
                        accountId: blueprintState.accountId,
                        getAccountId: () => blueprintState.accountId,
                        accountRequired: lookupSourceAccountRequired(fieldView.lookup_tool || lookupRef.schema?.lookup_tool || lookupRef.schema?.lookup?.tool),
                        getLookupContext: blueprintLookupContext,
                        targetToolName: lookupRef.toolName,
                        fieldName: lookupKey,
                        selectionTokens: blueprintState.selectionTokens,
                        optionsStore: blueprintState.lookupOptions,
                        onSelection: ({ value, tokens }) => {
                            if (tokens) {
                                blueprintState.selectionTokens[lookupKey] = tokens;
                                blueprintState.selectionTokenTools[lookupKey] = lookupRef.toolName;
                            } else {
                                delete blueprintState.selectionTokens[lookupKey];
                                delete blueprintState.selectionTokenTools[lookupKey];
                            }
                            updateBlueprintField(field, value);
                        },
                    });
                } else if (schema.type === 'object') {
                    control = renderStructuredObjectEditor(
                        schema,
                        displayValue,
                        value => updateBlueprintField(field, value),
                        null,
                        {
                            platform: blueprint.provider,
                            accountId: blueprintState.accountId,
                            getAccountId: () => blueprintState.accountId,
                            targetToolName: blueprintToolFieldSchema(field.tool_ref).toolName,
                            fieldPath: blueprintToolFieldSchema(field.tool_ref).fieldPath,
                            getLookupContext: blueprintLookupContext,
                            selectionTokens: blueprintState.selectionTokens,
                            optionsStore: blueprintState.lookupOptions,
                            onSelection: ({ fieldName, tokens }) => {
                                if (tokens) {
                                    blueprintState.selectionTokens[fieldName] = tokens;
                                    blueprintState.selectionTokenTools[fieldName] = blueprintToolFieldSchema(field.tool_ref).toolName;
                                } else {
                                    delete blueprintState.selectionTokens[fieldName];
                                    delete blueprintState.selectionTokenTools[fieldName];
                                }
                            },
                        },
                    );
                } else if (field.presentation === 'text_list') {
                    control = document.createElement('textarea');
                    control.className = 'asset-text-list';
                    control.placeholder = '每行填写一条';
                } else if (options.length) {
                    const arraySchema = schema.type === 'array' || (Array.isArray(schema.type) && schema.type.includes('array'));
                    const useChoiceTiles = arraySchema || options.length <= 6;
                    if (useChoiceTiles) {
                        control = renderChoiceTiles(options, displayValue, arraySchema, option => blueprintOptionLabel(field, option), value => updateBlueprintField(field, value));
                        control.dataset.customChoice = 'true';
                    } else {
                        control = document.createElement('select');
                    const placeholder = document.createElement('option');
                    placeholder.value = '';
                    placeholder.textContent = state.required ? '请选择…' : '不设置';
                    control.appendChild(placeholder);
                    for (const option of options) {
                        const optionNode = document.createElement('option');
                        optionNode.value = String(option);
                        optionNode.textContent = blueprintOptionLabel(field, option);
                        control.appendChild(optionNode);
                    }
                    }
                } else if (schema.type === 'object' || schema.type === 'array' || Array.isArray(schema.type)) {
                    control = document.createElement('textarea');
                    control.placeholder = schema.type === 'array' ? '[...]' : '{...}';
                } else {
                    control = document.createElement('input');
                    control.type = schema.type === 'number' || schema.type === 'integer' ? 'number' : 'text';
                }
                if (!control.dataset.customChoice && field.presentation !== 'asset_picker' && field.presentation !== 'file_reference' && field.presentation !== 'derived_readonly' && schema.type !== 'object') {
                    control.value = field.presentation === 'text_list'
                        ? presentedLines(displayValue)
                        : displayValue === undefined
                            ? ''
                            : (typeof displayValue === 'object' ? JSON.stringify(displayValue) : String(displayValue));
                    control.onchange = () => updateBlueprintField(field, control.value);
                }
                wrapper.appendChild(control);
                const source = document.createElement('div');
                source.className = 'blueprint-field-source';
                const dependencyLabels = (state.missing_option_dependencies || []).map(path =>
                    blueprint.fields?.find(item => item.path === path)?.label || path
                );
                source.textContent = state.options_state === 'awaiting_dependency'
                    ? `请先完成：${dependencyLabels.join('、') || '上游选择'}`
                    : field.presentation === 'derived_readonly'
                    ? '已根据当前入口自动匹配'
                    : field.source === 'lookup' || field.control === 'lookup'
                        ? '需要从指定账户中选择'
                        : (field.presentation === 'asset_picker' || field.presentation === 'file_reference')
                            ? '本地素材草稿，不会自动上传'
                            : schema.type === 'object' ? '按字段填写，系统会按 Tool Schema 组装'
                            : field.presentation === 'text_list' ? '每行填写一条' : '可直接填写';
                wrapper.appendChild(source);
                sectionFields.appendChild(wrapper);
                }
            });
            const readiness = document.getElementById('blueprintReadiness');
            if (readiness) {
                const missing = evaluation?.missing_fields || [];
                const invalid = evaluation?.invalid_fields || [];
                readiness.textContent = evaluation
                    ? (invalid.length ? `有 ${invalid.length} 项不适用于当前选择`
                        : missing.length ? `还需要填写 ${missing.length} 项` : '参数草稿已满足蓝图必填条件')
                    : '等待填写参数';
            }
        }

        async function updateBlueprintField(field, rawValue) {
            const prior = { ...blueprintState.values };
            const schema = blueprintToolFieldSchema(field.tool_ref).schema || {};
            if (rawValue === '') {
                delete blueprintState.values[field.path];
            } else {
                blueprintState.values[field.path] = typeof rawValue === 'string'
                    ? parsePresentedValue(field, rawValue, schema)
                    : rawValue;
            }
            blueprintState.previousValues = prior;
            await evaluateBlueprintDraft(field.path);
        }

        async function evaluateBlueprintDraft(changedPath, allowReset = true) {
            const blueprint = blueprintState.selected;
            if (!blueprint) return;
            try {
                const evaluation = await apiFetch(`/creation-blueprints/${encodeURIComponent(blueprint.id)}/evaluate`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        values: blueprintState.values,
                        previous_values: blueprintState.previousValues,
                        changed_fields: changedPath ? [changedPath] : [],
                        version: blueprint.version,
                    }),
                });
                blueprintState.evaluation = evaluation;
                if (allowReset && evaluation.reset_fields?.length) {
                    for (const path of evaluation.reset_fields) {
                        delete blueprintState.values[path];
                        const resetField = blueprint.fields?.find(item => item.path === path);
                        const resetKey = resetField ? blueprintToolFieldSchema(resetField.tool_ref).fieldPath : path;
                        delete blueprintState.selectionTokens[resetKey];
                        delete blueprintState.selectionTokenTools[resetKey];
                    }
                    showBlueprintNotice(`已根据字段变化清理 ${evaluation.reset_fields.length} 个不再适用的下游参数。`);
                    await evaluateBlueprintDraft(changedPath, false);
                    return;
                }
                renderBlueprintFlowbar(blueprint, evaluation);
                renderBlueprintFields(evaluation);
                renderBlueprintFieldNav(blueprint, evaluation);
                renderBlueprintSummary(blueprint, evaluation);
            } catch (error) {
                showBlueprintNotice(error.message || '参数校验失败。');
            }
        }

        function showBlueprintNotice(message) {
            const notice = document.getElementById('blueprintNotice');
            if (!notice) return;
            notice.textContent = message || '';
            notice.classList.toggle('active', Boolean(message));
        }

        function resetBlueprintDraft() {
            blueprintState.values = blueprintDefaultValues(blueprintState.selected);
            blueprintState.previousValues = {};
            blueprintState.evaluation = null;
            blueprintState.localFiles = {};
            blueprintState.selectionTokens = {};
            blueprintState.selectionTokenTools = {};
            blueprintState.lookupOptions = {};
            showBlueprintNotice('');
            renderBlueprintEditor();
        }

        function useBlueprintInChat() {
            const blueprint = blueprintState.selected;
            if (!blueprint) return;
            if (!blueprintState.accountId.trim()) {
                showBlueprintNotice('请先填写本次要操作的广告账户 ID，平台不会自动选择账户。');
                document.getElementById('blueprintAccountInput')?.focus();
                return;
            }
            pendingBlueprintRequest = {
                account_id: blueprintState.accountId.trim(),
                platform_params: blueprintDraftPlatformParams(blueprint),
                creation_blueprint_id: blueprint.id,
                creation_blueprint_version: blueprint.version,
            };
            setInput(`请按“${blueprint.title || blueprint.id}”继续创建广告。参数草稿已带入，请先检查并确认后提交。`);
            closeBlueprintManager();
        }

        function openSkillManager() {
            closeWorkspacePopovers();
            document.getElementById('skillOverlay').classList.add('active');
            document.getElementById('skillOverlay').setAttribute('aria-hidden', 'false');
            document.getElementById('skillApiKey').value = serviceApiKey;
            loadManagedSkills();
        }

        function closeSkillManager() {
            if (skillState.evaluationTimer) window.clearTimeout(skillState.evaluationTimer);
            skillState.evaluationTimer = null;
            document.getElementById('skillOverlay').classList.remove('active');
            document.getElementById('skillOverlay').setAttribute('aria-hidden', 'true');
        }

        function showSkillNotice(message, isError = false) {
            const notice = document.getElementById('skillNotice');
            notice.textContent = message || '';
            notice.className = `skill-notice active ${isError ? 'error' : 'success'}`;
        }

        function clearSkillNotice() {
            const notice = document.getElementById('skillNotice');
            notice.textContent = '';
            notice.className = 'skill-notice';
        }

        function skillStatusLabel(status) {
            return {
                published: '已发布', draft: '草稿', archived: '已归档',
                not_run: '未评测', queued: '排队中', running: '评测中',
                passed: '评测通过', failed: '评测失败', error: '评测异常',
            }[status] || status || '未知';
        }

        async function loadManagedSkills(select = null) {
            clearSkillNotice();
            serviceApiKey = document.getElementById('skillApiKey').value.trim();
            try {
                const data = await apiFetch('/skills?limit=200');
                const managedSkills = Array.isArray(data.managed_skills) ? data.managed_skills : (data.skills || []);
                const builtinSkills = Array.isArray(data.builtin_skills) ? data.builtin_skills : [];
                skillState.versions = [...managedSkills, ...builtinSkills];
                renderSkillList();
                if (select) {
                    await selectSkillVersion(select.skillName, select.version, select.source);
                } else if (skillState.selected) {
                    const stillExists = skillState.versions.some(item =>
                        item.skill_name === skillState.selected.skillName && item.version === skillState.selected.version && (item.source || 'managed') === (skillState.selected.source || 'managed')
                    );
                    if (stillExists) await selectSkillVersion(skillState.selected.skillName, skillState.selected.version, skillState.selected.source);
                } else if (data.builtin_skills?.length) {
                    const firstBuiltin = data.builtin_skills[0];
                    await selectSkillVersion(firstBuiltin.skill_name, firstBuiltin.version, 'builtin');
                }
                if (!skillState.versions.length) newSkillDraft();
            } catch (error) {
                renderSkillList();
                showSkillNotice(error.message, true);
            }
        }

        function renderSkillList() {
            const list = document.getElementById('skillList');
            list.replaceChildren();
            if (!skillState.versions.length) {
                const empty = document.createElement('div');
                empty.className = 'skill-list-empty';
                empty.textContent = '当前租户还没有 Skill 版本。点击“新建 Skill 版本”开始。';
                list.appendChild(empty);
                return;
            }
            const groups = new Map();
            for (const item of skillState.versions) {
                if (!groups.has(item.skill_name)) groups.set(item.skill_name, []);
                groups.get(item.skill_name).push(item);
            }
            if (!skillState.expanded.size) skillState.expanded.add(groups.keys().next().value);
            if (skillState.selected?.skillName) skillState.expanded.add(skillState.selected.skillName);
            const tree = document.createElement('div');
            tree.className = 'skill-tree';
            for (const [name, versions] of groups) {
                const group = document.createElement('div');
                group.className = 'skill-tree-group';
                const isExpanded = skillState.expanded.has(name);
                const title = document.createElement('button');
                title.type = 'button';
                title.className = 'skill-tree-node';
                title.setAttribute('aria-expanded', String(isExpanded));
                const chevron = document.createElement('span');
                chevron.className = 'skill-tree-chevron';
                chevron.textContent = '›';
                const folder = document.createElement('span');
                folder.className = 'skill-tree-folder';
                folder.textContent = '◇';
                const nameLabel = document.createElement('span');
                nameLabel.className = 'skill-tree-name';
                nameLabel.textContent = name;
                const count = document.createElement('span');
                count.className = 'skill-tree-count';
                count.textContent = `${versions.length}`;
                title.append(chevron, folder, nameLabel, count);
                title.addEventListener('click', () => {
                    if (skillState.expanded.has(name)) skillState.expanded.delete(name);
                    else skillState.expanded.add(name);
                    renderSkillList();
                });
                group.appendChild(title);
                const branch = document.createElement('div');
                branch.className = `skill-tree-branch${isExpanded ? ' expanded' : ''}`;
                for (const item of versions) {
                    const button = document.createElement('button');
                    button.type = 'button';
                    button.className = 'skill-tree-version';
                    if (skillState.selected && skillState.selected.skillName === item.skill_name && skillState.selected.version === item.version) {
                        button.classList.add('active');
                    }
                    const connector = document.createElement('span');
                    connector.className = 'skill-tree-connector';
                    const meta = document.createElement('span');
                    meta.className = 'skill-tree-version-meta';
                    const version = document.createElement('span');
                    version.className = 'skill-tree-version-number';
                    version.textContent = `v${item.version}`;
                    const digest = document.createElement('span');
                    digest.className = 'skill-tree-version-digest';
                    digest.textContent = item.sha256 ? `${item.sha256.slice(0, 12)}…` : '无 digest';
                    meta.append(version, digest);
                    const status = document.createElement('span');
                    status.className = `skill-tree-status ${item.status || ''}`;
                    status.textContent = item.source === 'builtin' ? '内置 · 只读' : skillStatusLabel(item.status);
                    button.append(connector, meta, status);
                    button.addEventListener('click', () => {
                        skillState.expanded.add(name);
                        selectSkillVersion(item.skill_name, item.version, item.source);
                    });
                    branch.appendChild(button);
                }
                group.appendChild(branch);
                tree.appendChild(group);
            }
            list.appendChild(tree);
        }

        function newSkillDraft() {
            if (skillState.evaluationTimer) window.clearTimeout(skillState.evaluationTimer);
            skillState.evaluationTimer = null;
            skillState.selected = null;
            skillState.detail = null;
            skillState.readOnly = false;
            skillState.files = [{
                path: 'SKILL.md', encoding: 'utf-8',
                content: '---\nname: new-skill\ndescription: Describe what this Skill does\nplatform: multi_platform\n---\n\n# Instructions\n\nDescribe the business workflow in natural language.\n',
            }];
            skillState.activeFilePath = 'SKILL.md';
            skillState.previewMode = false;
            document.getElementById('skillNameInput').value = 'new-skill';
            document.getElementById('skillVersionInput').value = '1.0.0';
            document.getElementById('skillEvalSummary').textContent = '草稿不会影响已发布 Skill；保存时请使用新的语义化版本号。';
            renderSkillList();
            renderSkillFiles();
            updateSkillEditorState();
            clearSkillNotice();
        }

        function likelyTextPath(path) {
            return path === 'SKILL.md' || /\.(md|markdown|txt|yaml|yml|json|csv|py|js|ts|sh)$/i.test(path);
        }

        function decodeBase64(value) {
            try {
                const binary = atob(value || '');
                const bytes = Uint8Array.from(binary, char => char.charCodeAt(0));
                return new TextDecoder().decode(bytes);
            } catch (_) { return value || ''; }
        }

        async function selectSkillVersion(skillName, version, source = 'managed') {
            try {
                const endpoint = source === 'builtin'
                    ? `/skills/builtin/${encodeURIComponent(skillName)}/versions/${encodeURIComponent(version)}`
                    : `/skills/${encodeURIComponent(skillName)}/versions/${encodeURIComponent(version)}`;
                const data = await apiFetch(endpoint);
                skillState.selected = { skillName, version, source: source || data.source || 'managed' };
                skillState.detail = data;
                skillState.readOnly = skillState.selected.source === 'builtin';
                skillState.files = Object.entries(data.files || {}).map(([path, value]) => ({
                    path,
                    encoding: value && value.encoding === 'base64' && !likelyTextPath(path) ? 'base64' : 'utf-8',
                    content: value && value.encoding === 'base64' ? decodeBase64(value.content) : String(value || ''),
                }));
                skillState.activeFilePath = skillState.files[0]?.path || 'SKILL.md';
                skillState.previewMode = skillState.readOnly && /\.(md|markdown)$/i.test(skillState.activeFilePath);
                document.getElementById('skillNameInput').value = skillName;
                document.getElementById('skillVersionInput').value = version;
                renderSkillList();
                renderSkillFiles();
                renderSkillEvaluation(data);
                updateSkillEditorState();
            } catch (error) { showSkillNotice(error.message, true); }
        }

        function updateSkillEditorState() {
            const readOnly = skillState.readOnly;
            const nameInput = document.getElementById('skillNameInput');
            const versionInput = document.getElementById('skillVersionInput');
            if (nameInput) nameInput.readOnly = readOnly;
            if (versionInput) versionInput.readOnly = readOnly;
            document.getElementById('skillSaveButton')?.toggleAttribute('disabled', readOnly);
            document.getElementById('skillEvaluateButton')?.toggleAttribute('disabled', readOnly || !skillState.selected);
            document.getElementById('skillPublishButton')?.toggleAttribute('disabled', readOnly || !skillState.selected);
            document.getElementById('skillUnpublishButton')?.toggleAttribute('disabled', readOnly || !skillState.selected);
            document.getElementById('skillCloneButton')?.toggleAttribute('disabled', !readOnly);
        }

        function cloneSelectedBuiltin() {
            if (!skillState.selected || skillState.selected.source !== 'builtin') return;
            const parts = String(skillState.selected.version).split('.').map(value => Number.parseInt(value, 10));
            const nextVersion = parts.length === 3 && parts.every(Number.isInteger)
                ? `${parts[0]}.${parts[1]}.${parts[2] + 1}` : '1.0.0';
            skillState.selected = null;
            skillState.detail = null;
            skillState.readOnly = false;
            skillState.activeFilePath = skillState.files[0]?.path || 'SKILL.md';
            skillState.previewMode = false;
            document.getElementById('skillVersionInput').value = nextVersion;
            document.getElementById('skillEvalSummary').textContent = '已复制内置 Skill；请编辑内容并保存为新的托管版本。';
            renderSkillList();
            renderSkillFiles();
            updateSkillEditorState();
            showSkillNotice('已复制内置 Skill。修改后点击“保存为新版本”，不会改动部署内置版本。');
        }

        function renderSkillFiles() {
            const container = document.getElementById('skillFiles');
            container.replaceChildren();
            if (!skillState.files.length) {
                const empty = document.createElement('div');
                empty.className = 'skill-file-empty';
                empty.textContent = '这个 Skill 还没有文件。点击下方“添加文件”开始构建目录。';
                container.appendChild(empty);
                return;
            }
            const activeFile = skillState.files.find(file => file.path === skillState.activeFilePath) || skillState.files[0];
            skillState.activeFilePath = activeFile.path;
            const layout = document.createElement('div');
            layout.className = 'skill-files-layout';
            const treePanel = document.createElement('aside');
            treePanel.className = 'skill-file-tree-panel';
            const treeTitle = document.createElement('div');
            treeTitle.className = 'skill-file-tree-title';
            treeTitle.innerHTML = '<span>文件结构</span><small>Skill package</small>';
            const tree = document.createElement('div');
            tree.className = 'skill-file-tree';
            const root = { directories: new Map(), files: [] };
            for (const file of skillState.files) {
                const parts = String(file.path || '').split('/').filter(Boolean);
                let node = root;
                parts.forEach((part, index) => {
                    if (index === parts.length - 1) node.files.push({ name: part, file });
                    else {
                        if (!node.directories.has(part)) node.directories.set(part, { directories: new Map(), files: [] });
                        node = node.directories.get(part);
                    }
                });
            }
            const renderDirectory = (node, parent, depth = 0) => {
                for (const [name, directory] of node.directories) {
                    const folder = document.createElement('div');
                    folder.className = 'skill-file-tree-folder-group';
                    const folderButton = document.createElement('button');
                    folderButton.type = 'button';
                    folderButton.className = 'skill-file-tree-folder';
                    folderButton.setAttribute('aria-expanded', 'true');
                    folderButton.innerHTML = `<span class="skill-file-tree-folder-chevron">›</span><span class="skill-file-tree-folder-icon">▱</span><span>${escapeHtml(name)}</span>`;
                    const children = document.createElement('div');
                    children.className = 'skill-file-tree-children';
                    folderButton.addEventListener('click', () => {
                        const collapsed = children.classList.toggle('collapsed');
                        folderButton.setAttribute('aria-expanded', String(!collapsed));
                    });
                    folder.append(folderButton, children);
                    parent.appendChild(folder);
                    renderDirectory(directory, children, depth + 1);
                }
                renderFiles(node, parent);
            };
            const renderFiles = (node, parent) => {
                for (const item of node.files) {
                    const fileButton = document.createElement('button');
                    fileButton.type = 'button';
                    fileButton.className = `skill-file-tree-file${item.file.path === activeFile.path ? ' active' : ''}`;
                    fileButton.innerHTML = `<span class="skill-file-tree-file-mark">—</span><span class="skill-file-tree-file-name">${escapeHtml(item.name)}</span><span class="skill-file-tree-file-type">${escapeHtml(item.file.encoding === 'base64' ? 'bin' : 'md')}</span>`;
                    fileButton.title = item.file.path;
                    fileButton.addEventListener('click', () => { skillState.activeFilePath = item.file.path; skillState.previewMode = skillState.readOnly && /\.(md|markdown)$/i.test(item.file.path); renderSkillFiles(); });
                    parent.appendChild(fileButton);
                }
            };
            renderDirectory(root, tree);
            const addFile = document.createElement('button');
            addFile.type = 'button';
            addFile.className = 'skill-file-tree-add';
            addFile.textContent = '+ 添加文件';
            addFile.disabled = skillState.readOnly;
            addFile.addEventListener('click', addSkillFile);
            treePanel.append(treeTitle, tree, addFile);
            const editorPanel = document.createElement('section');
            editorPanel.className = 'skill-file-editor-pane';
            const row = document.createElement('div');
            row.className = 'skill-file-row';
            const header = document.createElement('div');
            header.className = 'skill-file-row-header';
            const path = document.createElement('input');
            path.id = 'skillFilePathInput';
            path.type = 'text'; path.placeholder = 'references/guide.md'; path.value = activeFile.path;
            path.readOnly = skillState.readOnly;
            path.addEventListener('input', () => { activeFile.path = path.value; });
            const encoding = document.createElement('select');
            encoding.innerHTML = '<option value="utf-8">UTF-8 文本</option><option value="base64">Base64 二进制</option>';
            encoding.value = activeFile.encoding;
            encoding.disabled = skillState.readOnly;
            encoding.addEventListener('change', () => { activeFile.encoding = encoding.value; });
            const remove = document.createElement('button');
            remove.type = 'button'; remove.textContent = '删除';
            remove.disabled = skillState.readOnly;
            remove.addEventListener('click', () => { skillState.files = skillState.files.filter(file => file !== activeFile); skillState.activeFilePath = skillState.files[0]?.path || ''; renderSkillFiles(); });
            const isMarkdown = /\.(md|markdown)$/i.test(activeFile.path);
            const tabbar = document.createElement('div');
            tabbar.className = 'skill-file-tabs';
            tabbar.setAttribute('role', 'tablist');
            tabbar.setAttribute('aria-label', '文件视图');
            const editView = document.createElement('button');
            editView.type = 'button';
            editView.textContent = '编辑';
            editView.className = `skill-file-tab${skillState.previewMode ? '' : ' active'}`;
            editView.setAttribute('role', 'tab');
            editView.setAttribute('aria-selected', String(!skillState.previewMode));
            editView.setAttribute('aria-controls', 'skillFileEditorPanel');
            const previewView = document.createElement('button');
            previewView.type = 'button';
            previewView.textContent = '预览';
            previewView.className = `skill-file-tab${skillState.previewMode ? ' active' : ''}`;
            previewView.setAttribute('role', 'tab');
            previewView.setAttribute('aria-selected', String(skillState.previewMode));
            previewView.setAttribute('aria-controls', 'skillFilePreviewPanel');
            editView.addEventListener('click', () => { skillState.previewMode = false; renderSkillFiles(); });
            previewView.addEventListener('click', () => { if (isMarkdown) { skillState.previewMode = true; renderSkillFiles(); } });
            if (!isMarkdown) previewView.disabled = true;
            tabbar.append(editView, previewView);
            header.append(path, encoding, remove);
            const editorTabPanel = document.createElement('section');
            editorTabPanel.id = 'skillFileEditorPanel';
            editorTabPanel.className = `skill-file-panel skill-file-editor-panel${skillState.previewMode ? ' is-hidden' : ''}`;
            editorTabPanel.setAttribute('role', 'tabpanel');
            editorTabPanel.setAttribute('aria-labelledby', 'skillFileEditTab');
            const content = document.createElement('textarea');
            content.spellcheck = false; content.value = activeFile.content; content.readOnly = skillState.readOnly;
            content.addEventListener('input', () => { activeFile.content = content.value; });
            content.className = 'skill-file-editor';
            editorTabPanel.appendChild(content);
            const preview = document.createElement('article');
            preview.id = 'skillFilePreviewPanel';
            preview.className = `skill-file-panel skill-file-preview skill-file-preview-panel${skillState.previewMode ? '' : ' is-hidden'}`;
            preview.setAttribute('role', 'tabpanel');
            preview.setAttribute('aria-labelledby', 'skillFilePreviewTab');
            preview.innerHTML = isMarkdown ? formatSkillMarkdown(activeFile.content) : '<p>当前文件类型不支持 Markdown 预览。</p>';
            const hint = document.createElement('div');
            hint.className = 'skill-file-hint';
            hint.textContent = activeFile.encoding === 'base64' ? '二进制文件请输入严格 Base64；脚本和资源只作为包内容保存，不会被 Runtime 自动执行。' : '自然语言流程写入 SKILL.md，详细资料可放在 references/；evals/eval.yaml 可启用 Skill-up 发布门禁。';
            editView.id = 'skillFileEditTab';
            previewView.id = 'skillFilePreviewTab';
            row.append(header, tabbar, editorTabPanel, preview, hint);
            editorPanel.appendChild(row);
            layout.append(treePanel, editorPanel);
            container.appendChild(layout);
        }

        function formatSkillMarkdown(content) {
            const source = String(content || '').replace(/\r\n?/g, '\n');
            const frontmatterMatch = source.match(/^---\n([\s\S]*?)\n---\n?/);
            const metadata = frontmatterMatch ? frontmatterMatch[1] : '';
            const body = frontmatterMatch ? source.slice(frontmatterMatch[0].length) : source;
            const metadataItems = metadata.split('\n').map(line => {
                const match = line.match(/^([\w-]+):\s*(.*)$/);
                return match ? `<div><dt>${escapeHtml(match[1])}</dt><dd>${escapeHtml(match[2])}</dd></div>` : '';
            }).filter(Boolean).join('');
            const rendered = [];
            let inCode = false;
            let codeLanguage = '';
            let codeLines = [];
            let listItems = [];
            const flushList = () => {
                if (!listItems.length) return;
                rendered.push(`<ul>${listItems.join('')}</ul>`);
                listItems = [];
            };
            const inline = value => value
                .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
                .replace(/`([^`]+)`/g, '<code>$1</code>');
            for (const rawLine of body.split('\n')) {
                const line = escapeHtml(rawLine);
                if (line.trim().startsWith('```')) {
                    flushList();
                    if (inCode) {
                        rendered.push(`<pre><code class="language-${escapeHtml(codeLanguage)}">${codeLines.join('\n')}</code></pre>`);
                        inCode = false; codeLines = []; codeLanguage = '';
                    } else {
                        inCode = true; codeLanguage = line.trim().slice(3).trim();
                    }
                    continue;
                }
                if (inCode) { codeLines.push(line); continue; }
                if (/^[-*]\s+/.test(line)) { listItems.push(`<li>${inline(line.replace(/^[-*]\s+/, ''))}</li>`); continue; }
                flushList();
                if (!line.trim()) continue;
                if (/^###\s+/.test(line)) rendered.push(`<h3>${inline(line.slice(4))}</h3>`);
                else if (/^##\s+/.test(line)) rendered.push(`<h2>${inline(line.slice(3))}</h2>`);
                else if (/^#\s+/.test(line)) rendered.push(`<h1>${inline(line.slice(2))}</h1>`);
                else if (/^&gt;\s?/.test(line)) rendered.push(`<blockquote>${inline(line.replace(/^&gt;\s?/, ''))}</blockquote>`);
                else rendered.push(`<p>${inline(line)}</p>`);
            }
            flushList();
            if (inCode) rendered.push(`<pre><code>${codeLines.join('\n')}</code></pre>`);
            return `${metadataItems ? `<section class="skill-markdown-frontmatter"><strong>Skill metadata</strong><dl>${metadataItems}</dl></section>` : ''}${rendered.join('')}`;
        }

        function addSkillFile() {
            if (skillState.readOnly) return;
            skillState.files.push({ path: 'references/new.md', encoding: 'utf-8', content: '' });
            skillState.activeFilePath = 'references/new.md';
            renderSkillFiles();
            document.getElementById('skillFilePathInput')?.focus();
        }

        function collectSkillFiles() {
            const files = {};
            for (const file of skillState.files) {
                const path = file.path.trim();
                if (!path) throw new Error('Skill 文件路径不能为空');
                if (Object.prototype.hasOwnProperty.call(files, path)) throw new Error(`重复的 Skill 文件：${path}`);
                files[path] = file.encoding === 'base64' ? { encoding: 'base64', content: file.content.trim() } : file.content;
            }
            return files;
        }

        async function saveSkillDraft() {
            if (skillState.readOnly) {
                showSkillNotice('内置 Skill 只能复制为新的托管版本后再编辑。', true);
                return;
            }
            try {
                const skillName = document.getElementById('skillNameInput').value.trim().toLowerCase();
                const version = document.getElementById('skillVersionInput').value.trim();
                if (!skillName || !version) throw new Error('请填写 Skill 名称和语义化版本号');
                const data = await apiFetch(`/skills/${encodeURIComponent(skillName)}/versions`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ version, files: collectSkillFiles() }),
                });
                showSkillNotice(`已保存 ${skillName}@${version}，digest: ${data.sha256 || '已生成'}`);
                await loadManagedSkills({ skillName, version });
            } catch (error) { showSkillNotice(error.message, true); }
        }

        async function uploadSkillZip() {
            const input = document.getElementById('skillZipInput');
            const archive = input.files[0];
            if (!archive) return;
            try {
                const skillName = document.getElementById('skillNameInput').value.trim().toLowerCase();
                const version = document.getElementById('skillVersionInput').value.trim();
                if (!skillName || !version) throw new Error('ZIP 导入前请填写 Skill 名称和版本');
                const data = await apiFetch(`/skills/${encodeURIComponent(skillName)}/versions/archive?version=${encodeURIComponent(version)}`, {
                    method: 'POST', headers: { 'Content-Type': 'application/zip' }, body: archive,
                });
                showSkillNotice(`已导入 ${skillName}@${version}，digest: ${data.sha256 || '已生成'}`);
                input.value = '';
                await loadManagedSkills({ skillName, version });
            } catch (error) { input.value = ''; showSkillNotice(error.message, true); }
        }

        function renderSkillEvaluation(detail) {
            const summary = document.getElementById('skillEvalSummary');
            if (detail.source === 'builtin') {
                summary.textContent = `部署内置版本 · ${detail.location || '标准 Skill 目录'} · 只读；复制后可作为租户新版本编辑。`;
                return;
            }
            const evalStatus = detail.evaluation_status || 'not_run';
            const runId = detail.evaluation_run_id ? ` · run ${detail.evaluation_run_id.slice(0, 10)}…` : '';
            const release = detail.status === 'published' ? '已发布' : detail.status === 'archived' ? '已归档' : '草稿';
            summary.textContent = `版本状态：${release} · Skill-up：${skillStatusLabel(evalStatus)}${runId}`;
        }

        async function evaluateSelectedSkill() {
            if (!skillState.selected) { showSkillNotice('请先保存并选择一个版本，再发起评测。', true); return; }
            try {
                const { skillName, version } = skillState.selected;
                const run = await apiFetch(`/skills/${encodeURIComponent(skillName)}/versions/${encodeURIComponent(version)}/evaluate`, { method: 'POST' });
                renderSkillEvaluation({ ...(skillState.detail || {}), evaluation_status: run.status || 'queued', evaluation_run_id: run.run_id });
                showSkillNotice(`Skill-up 已启动（${run.run_id}），正在轮询结果……`);
                pollSkillEvaluation(run.run_id);
            } catch (error) { showSkillNotice(error.message, true); }
        }

        async function pollSkillEvaluation(runId) {
            if (skillState.evaluationTimer) window.clearTimeout(skillState.evaluationTimer);
            try {
                const run = await apiFetch(`/skills/evaluations/${encodeURIComponent(runId)}`);
                const status = run.status || 'error';
                renderSkillEvaluation({ ...(skillState.detail || {}), evaluation_status: status, evaluation_run_id: runId });
                if (status === 'queued' || status === 'running') {
                    skillState.evaluationTimer = window.setTimeout(() => pollSkillEvaluation(runId), 2000);
                } else {
                    await loadManagedSkills(skillState.selected);
                    showSkillNotice(status === 'passed' ? 'Skill-up 评测通过，可以发布。' : `Skill-up 结束：${skillStatusLabel(status)}`, status !== 'passed');
                }
            } catch (error) {
                showSkillNotice(error.message, true);
                skillState.evaluationTimer = window.setTimeout(() => pollSkillEvaluation(runId), 4000);
            }
        }

        async function publishSelectedSkill() {
            if (!skillState.selected) { showSkillNotice('请先选择要发布或回滚的不可变版本。', true); return; }
            if (!window.confirm(`确认将 ${skillState.selected.skillName}@${skillState.selected.version} 设为当前发布版本？`)) return;
            try {
                const { skillName, version } = skillState.selected;
                await apiFetch(`/skills/${encodeURIComponent(skillName)}/versions/${encodeURIComponent(version)}/publish`, { method: 'POST' });
                showSkillNotice(`已发布 ${skillName}@${version}；若它是旧版本，这也是一次显式回滚。`);
                await loadManagedSkills({ skillName, version });
            } catch (error) { showSkillNotice(error.message, true); }
        }

        async function unpublishSelectedSkill() {
            if (!skillState.selected || skillState.detail?.status !== 'published') { showSkillNotice('只有当前已发布版本可以下线。', true); return; }
            if (!window.confirm(`确认下线 ${skillState.selected.skillName}@${skillState.selected.version}？`)) return;
            try {
                const { skillName, version } = skillState.selected;
                await apiFetch(`/skills/${encodeURIComponent(skillName)}/versions/${encodeURIComponent(version)}/unpublish`, { method: 'POST' });
                showSkillNotice(`已下线 ${skillName}@${version}，版本仍保留，可随后显式回滚。`);
                await loadManagedSkills({ skillName, version });
            } catch (error) { showSkillNotice(error.message, true); }
        }

        // Auto-resize textarea
        function autoResize(textarea) {
            textarea.style.height = 'auto';
            textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
        }

        // Set input from quick actions
        function setInput(text) {
            document.getElementById('userInput').value = text;
            document.getElementById('userInput').focus();
            autoResize(document.getElementById('userInput'));
        }

        // Handle Enter key
        function handleKeyDown(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        }

        function creationCardValueText(value) {
            if (value === undefined || value === null) return '';
            return typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value);
        }

        function creationCardDisplayValue(field) {
            if (field.control === 'text_list') return presentedLines(field.value);
            return creationCardValueText(field.value);
        }

        function parseCreationCardValue(field, rawValue) {
            if (field.control === 'text_list') {
                const lines = String(rawValue || '').split(/\r?\n/).map(item => item.trim()).filter(Boolean);
                return field.value_shape === 'object_text' ? lines.map(text => ({ text })) : lines;
            }
            if (field.control === 'json' || field.control === 'advanced_json') {
                if (!String(rawValue || '').trim()) {
                    delete field.local_error;
                    return undefined;
                }
                try {
                    const value = JSON.parse(rawValue);
                    const expectedShape = String(field.json_shape || '').toLowerCase();
                    const isObject = value !== null && typeof value === 'object' && !Array.isArray(value);
                    const isArray = Array.isArray(value);
                    if (expectedShape === 'object' && !isObject) {
                        field.local_error = '这里需要填写 JSON 对象，例如 {"key":"value"}。';
                        return rawValue;
                    }
                    if (expectedShape === 'array' && !isArray) {
                        field.local_error = '这里需要填写 JSON 数组，例如 [{"key":"value"}]。';
                        return rawValue;
                    }
                    if (expectedShape === 'object_or_array' && !isObject && !isArray) {
                        field.local_error = '这里需要填写 JSON 对象或数组。';
                        return rawValue;
                    }
                    delete field.local_error;
                    return value;
                } catch (_) {
                    field.local_error = '格式不正确，请填写有效的 JSON 对象或数组。';
                    return rawValue;
                }
            }
            if (field.control === 'number') return rawValue === '' ? undefined : Number(rawValue);
            return rawValue === '' ? undefined : rawValue;
        }

        function setCreationNestedValue(target, path, value) {
            const parts = String(path || '').split('.').filter(Boolean);
            if (!parts.length) return;
            let current = target;
            parts.forEach((part, index) => {
                if (index === parts.length - 1) current[part] = value;
                else current = current[part] && typeof current[part] === 'object' ? current[part] : (current[part] = {});
            });
        }

        // Lookup dependencies are declared by the provider schema.  The
        // picker receives the current form values through this generic
        // projection; it does not know Meta/Google/TikTok field names.
        function lookupContextFromFields(fields) {
            const context = {};
            (fields || []).forEach(field => {
                if (!field || field.value === undefined || field.value === null || field.value === '') return;
                const path = field.provider_field || field.path;
                if (path) setCreationNestedValue(context, path, field.value);
                if (field.path) context[field.path] = field.value;
                const leaf = String(path || '').split('.').pop();
                if (leaf && context[leaf] === undefined) context[leaf] = field.value;
                if (field.value && typeof field.value === 'object' && !Array.isArray(field.value)) {
                    Object.entries(field.value).forEach(([key, value]) => {
                        if (value !== undefined && value !== null && value !== '') context[key] = value;
                    });
                }
            });
            return context;
        }

        function blueprintLookupContext() {
            const context = { ...(blueprintState.values || {}) };
            Object.entries(context).forEach(([path, value]) => {
                const leaf = String(path).split('.').pop();
                if (leaf && context[leaf] === undefined) context[leaf] = value;
                if (value && typeof value === 'object' && !Array.isArray(value)) {
                    Object.entries(value).forEach(([key, child]) => {
                        if (child !== undefined && child !== null && child !== '') context[key] = child;
                    });
                }
            });
            return context;
        }

        function creationCardParams(card) {
            const values = {};
            const scopedSelectionTokens = {};
            (card.fields || []).forEach(field => {
                const value = creationFieldValue(field);
                if (field.visible === false || value === undefined || value === null || value === '') return;
                setCreationNestedValue(values, field.provider_field || field.path, value);
                // Keep a tool-scoped copy for repeated fields such as name or
                // app_id. The top-level copy remains available to the
                // provider-neutral activation predicates; the authoritative
                // Tool builder uses the scoped value for its own schema.
                if (field.tool) {
                    values[field.tool] = values[field.tool] || {};
                    setCreationNestedValue(values[field.tool], field.provider_field || field.path, value);
                }
            });
            Object.entries(card.selection_tokens || {}).forEach(([fieldName, token]) => {
                const toolName = card.selection_token_tools?.[fieldName];
                if (!toolName || !token) return;
                scopedSelectionTokens[toolName] = scopedSelectionTokens[toolName] || {};
                scopedSelectionTokens[toolName][fieldName] = token;
            });
            Object.entries(scopedSelectionTokens).forEach(([toolName, tokens]) => {
                values[toolName] = values[toolName] || {};
                values[toolName].selection_tokens = tokens;
            });
            return { [card.provider]: values };
        }

        function creationCardDraftValues(card) {
            const values = {};
            (card.fields || []).forEach(field => {
                const value = creationFieldValue(field);
                if (value !== undefined && value !== null && value !== '') values[field.path] = value;
            });
            return values;
        }

        async function evaluateCreationCard(card, changedPath) {
            if (!card.blueprint_id) return;
            const localInvalidPaths = new Set(
                (card.fields || []).filter(field => field.local_error).map(field => field.path)
            );
            const revision = (creationCardEvaluationRevisions.get(card.id) || 0) + 1;
            creationCardEvaluationRevisions.set(card.id, revision);
            card.validation_pending = true;
            delete card.validation_error;
            const pendingWrapper = document.querySelector(`.creation-card[data-card-id="${CSS.escape(card.id)}"]`);
            if (pendingWrapper) updateCreationCardIndicators(pendingWrapper, card);
            try {
                const response = await authenticatedFetch(`/creation-blueprints/${encodeURIComponent(card.blueprint_id)}/evaluate`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ values: creationCardDraftValues(card), version: card.blueprint_version, changed_fields: changedPath ? [changedPath] : [] })
                });
                if (!response.ok) throw new Error(`参数检查失败（${response.status}）`);
                const evaluation = await response.json();
                // Typing can queue more than one request when the local
                // service is busy. Never let an older response roll a draft
                // back over a newer value.
                if (creationCardEvaluationRevisions.get(card.id) !== revision) return;
                const reset = new Set(evaluation.reset_fields || []);
                const previousFields = new Map((card.fields || []).map(field => [field.path, field]));
                const structuralChange = reset.size > 0 || (evaluation.fields || []).some(next => {
                    const previous = previousFields.get(next.path);
                    return !previous
                        || previous.visible !== next.visible
                        || previous.required !== next.required
                        || JSON.stringify(previous.options || []) !== JSON.stringify(next.options || []);
                });
                (card.fields || []).forEach(field => {
                    if (reset.has(field.path)) {
                        field.value = undefined;
                        const resetKey = field.provider_field || field.path;
                        delete card.selection_tokens?.[resetKey];
                        delete card.selection_token_tools?.[resetKey];
                    }
                    const state = (evaluation.fields || []).find(item => item.path === field.path);
                    if (state) {
                        field.visible = state.visible;
                        field.required = state.required;
                        field.state = state.state;
                    }
                    if (field.local_error) field.state = 'invalid';
                });
                card.missing_fields = evaluation.missing_fields || [];
                card.invalid_fields = [...new Set([
                    ...(evaluation.invalid_fields || []), ...localInvalidPaths,
                ])];
                card.ready = Boolean(evaluation.ready) && localInvalidPaths.size === 0;
                card.validation_pending = false;
                delete card.validation_error;
                const current = document.querySelector(`.creation-card[data-card-id="${CSS.escape(card.id)}"]`);
                if (current) {
                    if (!structuralChange) {
                        updateCreationCardIndicators(current, card);
                        return;
                    }
                    // Cascade evaluation updates field visibility and
                    // requirements, but replacing the whole card must not
                    // make a person lose focus while typing. Restore the
                    // active control and its caret after the structural
                    // update completes.
                    const active = document.activeElement;
                    const isInsideCard = Boolean(active && current.contains(active));
                    const focusPath = isInsideCard
                        ? (active.dataset?.path || (active.closest('.creation-card-account') ? '__account__' : ''))
                        : '';
                    const selectionStart = isInsideCard && typeof active.selectionStart === 'number' ? active.selectionStart : null;
                    const selectionEnd = isInsideCard && typeof active.selectionEnd === 'number' ? active.selectionEnd : null;
                    const replacement = renderCreationCard(card);
                    current.replaceWith(replacement);
                    const target = focusPath === '__account__'
                        ? replacement.querySelector('.creation-card-account input')
                        : focusPath ? replacement.querySelector(`[data-path="${CSS.escape(focusPath)}"]`) : null;
                    if (target && !target.disabled) {
                        target.focus({ preventScroll: true });
                        if (selectionStart !== null && typeof target.setSelectionRange === 'function') {
                            target.setSelectionRange(selectionStart, selectionEnd ?? selectionStart);
                        }
                    }
                }
            } catch (error) {
                // A transient UI evaluation error does not alter the draft;
                // the next chat submission still passes through the server
                // Tool schema and authoritative cascade validation.
                console.debug('creation card evaluation failed', error);
                if (creationCardEvaluationRevisions.get(card.id) === revision) {
                    card.validation_pending = false;
                    card.ready = false;
                    card.validation_error = '参数检查暂时失败，请点击“检查参数”重试。';
                    const current = document.querySelector(`.creation-card[data-card-id="${CSS.escape(card.id)}"]`);
                    if (current) updateCreationCardIndicators(current, card);
                }
            }
        }

        function scheduleCreationCardEvaluation(card, path) {
            const prior = creationCardEvaluationTimers.get(card.id);
            if (prior) window.clearTimeout(prior);
            card.validation_pending = true;
            delete card.validation_error;
            const current = document.querySelector(`.creation-card[data-card-id="${CSS.escape(card.id)}"]`);
            if (current) updateCreationCardIndicators(current, card);
            const timer = window.setTimeout(() => {
                creationCardEvaluationTimers.delete(card.id);
                evaluateCreationCard(card, path);
            }, 220);
            creationCardEvaluationTimers.set(card.id, timer);
        }

        function creationCardValueEmpty(value) {
            return value === undefined || value === null || value === ''
                || (Array.isArray(value) && value.length === 0)
                || (value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length === 0);
        }

        function creationCardPendingLabels(card) {
            const invalidPaths = new Set(card.invalid_fields || []);
            const pending = [];
            if (!String(card.account_id || '').trim()) pending.push('广告账户 ID');
            (card.fields || []).forEach(field => {
                if (field.visible === false || !creationFieldNeedsUserInput(field)) return;
                const label = field.label || field.path || '参数';
                if (invalidPaths.has(field.path) || field.state === 'invalid') return;
                if (creationCardValueEmpty(creationFieldValue(field)) && !pending.includes(label)) pending.push(label);
            });
            return pending;
        }

        function creationCardInvalidLabels(card) {
            const invalidPaths = new Set(card.invalid_fields || []);
            return (card.fields || []).filter(field => field.visible !== false && (invalidPaths.has(field.path) || field.state === 'invalid' || field.local_error)).map(field => field.label || field.path || '参数').filter((label, index, labels) => labels.indexOf(label) === index);
        }

        function creationProviderLabel(provider) {
            return ({ 'google-ads': 'Google Ads', google: 'Google Ads', meta: 'Meta', tiktok: 'TikTok', dv360: 'DV360' })[String(provider || '').toLowerCase()] || String(provider || '广告平台');
        }

        function creationAccountLabel(provider) {
            return ({ 'google-ads': 'Google Ads 客户 ID', google: 'Google Ads 客户 ID', tiktok: 'TikTok 广告主 ID', meta: 'Meta 广告账户 ID', dv360: 'DV360 广告客户 ID' })[String(provider || '').toLowerCase()] || '广告账户 ID';
        }

        function creationCardStatus(card) {
            const invalid = creationCardInvalidLabels(card);
            const pending = creationCardPendingLabels(card);
            if (card.validation_pending) return '正在检查刚刚修改的参数，请稍候…';
            if (card.validation_error) return card.validation_error;
            if (invalid.length) return `有 ${invalid.length} 项需要调整：${invalid.slice(0, 3).join('、')}${invalid.length > 3 ? '等' : ''}`;
            if (pending.length) return `还需要补充 ${pending.length} 项：${pending.slice(0, 3).join('、')}${pending.length > 3 ? '等' : ''}`;
            return card.ready ? '必填参数已齐全，可以先查看预览' : '参数草稿已保存，可以继续补充';
        }

        function creationCardStatusKind(card) {
            if (!String(card.account_id || '').trim()) return 'account';
            if (card.validation_pending) return 'checking';
            if (card.validation_error) return 'error';
            if (creationCardInvalidLabels(card).length) return 'invalid';
            if ((card.missing_fields || []).length) return 'waiting';
            return card.ready ? 'ready' : 'draft';
        }

        function creationCardStatusLabel(card) {
            const kind = creationCardStatusKind(card);
            const pending = creationCardPendingLabels(card).length;
            return kind === 'ready' ? '可提交' : kind === 'checking' ? '检查中…' : kind === 'error' ? '检查失败' : kind === 'invalid' ? `需调整 ${Math.max(1, creationCardInvalidLabels(card).length)} 项` : pending ? `待补充 ${pending} 项` : '待检查';
        }

        function creationCardProgress(card) {
            const requiredFields = (card.fields || []).filter(field => field.visible !== false && creationFieldNeedsUserInput(field));
            const completedFields = requiredFields.filter(field => !creationCardValueEmpty(creationFieldValue(field)) && !field.local_error && field.state !== 'invalid' && !(card.invalid_fields || []).includes(field.path)).length;
            const accountCompleted = String(card.account_id || '').trim() ? 1 : 0;
            const total = requiredFields.length + 1;
            const completed = completedFields + accountCompleted;
            return { completed, total, percent: total ? Math.round(completed / total * 100) : 0 };
        }

        function creationCardCanSubmit(card) {
            return Boolean(String(card.account_id || '').trim() && !card.validation_pending && !card.validation_error && card.ready && !(card.missing_fields || []).length && !(card.invalid_fields || []).length && !(card.fields || []).some(field => field.local_error));
        }

        function updateCreationCardIndicators(wrapper, card) {
            // Keep field-level feedback synchronous with the local draft. In
            // particular, malformed advanced JSON must be visible before the
            // debounced cascade request returns.
            updateCreationCardFieldStates(wrapper, card);
            const status = wrapper.querySelector('.creation-card-status');
            if (status) status.textContent = creationCardStatus(card);
            const nextValue = wrapper.querySelector('.creation-card-next-value');
            if (nextValue) nextValue.textContent = card.type === 'ad_creation_selector' ? '先选择创建类型，系统会展开对应参数。' : creationCardStatus(card);
            const badge = wrapper.querySelector('.creation-card-state');
            if (badge) {
                badge.className = `creation-card-state ${creationCardStatusKind(card)}`;
                badge.textContent = creationCardStatusLabel(card);
            }
            const progress = creationCardProgress(card);
            const progressValue = wrapper.querySelector('.creation-card-progress-value');
            if (progressValue) progressValue.textContent = `${progress.completed} / ${progress.total} · ${progress.percent}%`;
            const progressBar = wrapper.querySelector('.creation-card-progress-bar');
            if (progressBar) {
                progressBar.style.width = `${progress.percent}%`;
                progressBar.setAttribute('aria-valuenow', String(progress.percent));
            }
            wrapper.querySelectorAll('.creation-card-section').forEach(section => {
                const group = creationFieldGroups(card.fields || []).find(item => item.id === section.dataset.step);
                if (!group) return;
                const groupProgress = fieldGroupProgress(group.fields);
                const count = section.querySelector('.creation-card-section-count');
                if (count) {
                    count.classList.toggle('has-missing', Boolean(groupProgress.missing));
                    count.textContent = groupProgress.missing ? `待填 ${groupProgress.missing}` : `${groupProgress.total} 项`;
                }
            });
            wrapper.querySelectorAll('.creation-card-step').forEach(step => {
                const group = creationFieldGroups(card.fields || []).find(item => item.id === step.dataset.step);
                const groupProgress = group ? fieldGroupProgress(group.fields) : { missing: 0 };
                step.classList.toggle('has-missing', Boolean(groupProgress.missing));
                const copy = step.querySelector('small');
                if (copy) copy.textContent = groupProgress.missing ? `待填 ${groupProgress.missing}` : '已就绪';
            });
            const submitButton = wrapper.querySelector('[data-creation-action="submit_create"]');
            if (submitButton) submitButton.disabled = !creationCardCanSubmit(card);
            const focusButton = wrapper.querySelector('.creation-card-focus-action');
            if (focusButton) {
                const hasIssue = !String(card.account_id || '').trim() || creationCardPendingLabels(card).length || creationCardInvalidLabels(card).length;
                focusButton.hidden = !hasIssue;
                focusButton.textContent = creationCardInvalidLabels(card).length ? '查看问题' : '定位待填项';
            }
            renderCreationCardFieldNav(card, wrapper);
            renderCreationCardSummary(card, wrapper);
            renderCreationCardAutomation(card, wrapper);
        }

        function focusCreationCardIssue(card, wrapper = null) {
            const root = wrapper || document.querySelector(`.creation-card[data-card-id="${CSS.escape(card.id)}"]`);
            if (!root) return;
            if (!String(card.account_id || '').trim()) {
                const account = root.querySelector('.creation-card-account input');
                account?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                account?.focus({ preventScroll: true });
                return;
            }
            const issue = root.querySelector('.creation-card-field.invalid:not(.hidden), .creation-card-field.missing:not(.hidden)');
            if (!issue) return;
            scrollCreationTarget(issue);
            issue.querySelector('input:not([disabled]), select:not([disabled]), textarea:not([disabled]), button')?.focus({ preventScroll: true });
        }

        function creationCardFieldState(field) {
            const invalid = field.local_error || field.state === 'invalid';
            const value = creationFieldValue(field);
            const empty = creationCardValueEmpty(value);
            return {
                visible: field.visible !== false,
                required: creationFieldNeedsUserInput(field),
                value,
                status: invalid ? 'invalid' : creationFieldNeedsUserInput(field) && empty ? 'missing' : empty ? 'empty' : 'complete',
            };
        }

        function creationCardScrollTo(wrapper, target, activeNode = null) {
            if (!target) return;
            const section = target.closest('.blueprint-field-group, .creation-card-section');
            if (section) setCreationSectionExpanded(section, true);
            scrollCreationTarget(target);
            target.querySelector('input:not([disabled]), select:not([disabled]), textarea:not([disabled]), button:not([disabled])')?.focus({ preventScroll: true });
            wrapper.querySelectorAll('.creation-card-nav-item.active, .creation-card-nav-group.active').forEach(node => node.classList.remove('active'));
            activeNode?.classList.add('active');
        }

        function renderCreationCardFieldNav(card, wrapper) {
            const container = wrapper?.querySelector('.creation-card-field-nav');
            if (!container) return;
            container.replaceChildren();
            const header = document.createElement('div');
            header.className = 'creation-card-field-nav-header';
            header.innerHTML = '<span>填写目录</span><small>点击字段快速定位</small>';
            container.appendChild(header);
            creationFieldGroups(card.fields || []).forEach((group, groupIndex) => {
                const states = group.fields.map(creationCardFieldState);
                const fields = group.fields.filter((field, index) => states[index].visible && (!card.focus_mode || !field.advanced));
                if (!fields.length) return;
                const progress = fieldGroupProgress(group.fields);
                const groupButton = document.createElement('button');
                groupButton.type = 'button';
                groupButton.className = `creation-card-nav-group${progress.missing ? ' missing' : ' complete'}`;
                const marker = document.createElement('span');
                marker.className = 'creation-card-nav-status';
                marker.textContent = progress.missing ? '!' : '✓';
                const copy = document.createElement('span');
                copy.className = 'creation-card-nav-group-copy';
                copy.innerHTML = `<strong>${escapeHtml(group.title)}</strong><small>${progress.missing ? `待填 ${progress.missing} · 共 ${progress.total} 项` : `已就绪 · 共 ${progress.total} 项`}</small>`;
                groupButton.append(marker, copy);
                groupButton.addEventListener('click', () => creationCardScrollTo(wrapper, wrapper.querySelector(`.creation-card-section[data-step="${CSS.escape(group.id)}"]`), groupButton));
                container.appendChild(groupButton);
                const fieldList = document.createElement('div');
                fieldList.className = 'creation-card-nav-fields';
                creationDirectoryHierarchyGroups(fields).forEach(([hierarchy, hierarchyFields]) => {
                    const branch = document.createElement('div');
                    branch.className = 'creation-card-nav-hierarchy';
                    const branchKey = `card:${card.id}:${group.id}:${hierarchy}`;
                    const collapsed = creationDirectoryCollapseState.get(branchKey) === true;
                    if (collapsed) branch.classList.add('is-collapsed');
                    const branchButton = document.createElement('button');
                    branchButton.type = 'button';
                    branchButton.className = 'creation-card-nav-hierarchy-toggle';
                    branchButton.setAttribute('aria-expanded', String(!collapsed));
                    const branchMarker = document.createElement('span');
                    branchMarker.className = 'creation-card-nav-hierarchy-marker';
                    branchMarker.textContent = collapsed ? '›' : '⌄';
                    const branchCopy = document.createElement('span');
                    branchCopy.className = 'creation-card-nav-hierarchy-copy';
                    const branchTitle = document.createElement('strong');
                    branchTitle.textContent = hierarchy;
                    const branchCount = document.createElement('small');
                    branchCount.textContent = `${hierarchyFields.length} 项`;
                    branchCopy.append(branchTitle, branchCount);
                    branchButton.append(branchMarker, branchCopy);
                    const hierarchyList = document.createElement('div');
                    hierarchyList.className = 'creation-card-nav-hierarchy-fields';
                    branchButton.addEventListener('click', () => {
                        const nextCollapsed = !branch.classList.contains('is-collapsed');
                        branch.classList.toggle('is-collapsed', nextCollapsed);
                        creationDirectoryCollapseState.set(branchKey, nextCollapsed);
                        branchButton.setAttribute('aria-expanded', String(!nextCollapsed));
                        branchMarker.textContent = nextCollapsed ? '›' : '⌄';
                    });
                    hierarchyFields.forEach(field => {
                        const state = creationCardFieldState(field);
                        const button = document.createElement('button');
                        button.type = 'button';
                        button.className = `creation-card-nav-item${state.status === 'missing' ? ' missing' : ''}${state.status === 'invalid' ? ' invalid' : ''}${state.status === 'complete' ? ' complete' : ''}`;
                        const status = document.createElement('span');
                        status.className = 'creation-card-nav-field-status';
                        status.textContent = state.status === 'invalid' ? '!' : state.status === 'missing' ? '•' : state.status === 'complete' ? '✓' : '·';
                        const itemCopy = document.createElement('span');
                        itemCopy.className = 'creation-card-nav-item-copy';
                        itemCopy.innerHTML = `<span>${escapeHtml(field.label || field.path)}</span><small>${escapeHtml(creationFieldDisplayValue(field))}</small>`;
                        button.append(status, itemCopy);
                        button.addEventListener('click', () => creationCardScrollTo(wrapper, wrapper.querySelector(`.creation-card-field[data-field-path="${CSS.escape(field.path)}"]`), button));
                        hierarchyList.appendChild(button);
                    });
                    branch.append(branchButton, hierarchyList);
                    fieldList.appendChild(branch);
                });
                container.appendChild(fieldList);
            });
            if (!container.querySelector('.creation-card-nav-group')) {
                const empty = document.createElement('div');
                empty.className = 'creation-card-nav-empty';
                empty.textContent = '选择创建类型后显示字段目录。';
                container.appendChild(empty);
            }
        }

        function renderCreationCardSummary(card, wrapper) {
            const container = wrapper?.querySelector('.creation-card-summary');
            if (!container) return;
            container.replaceChildren();
            const progress = creationCardProgress(card);
            const heading = document.createElement('div');
            heading.className = 'creation-card-summary-heading';
            heading.innerHTML = '<span>实时摘要</span><small>填写时始终可见</small>';
            const progressValue = document.createElement('span');
            progressValue.className = `creation-card-summary-progress${progress.percent >= 100 ? ' ready' : ''}`;
            progressValue.textContent = `${progress.completed}/${progress.total} 项已填`;
            heading.appendChild(progressValue);
            container.appendChild(heading);
            const items = document.createElement('div');
            items.className = 'creation-card-summary-items';
            const account = document.createElement('button');
            account.type = 'button';
            account.className = `creation-card-summary-item${card.account_id ? ' filled' : ' pending'}`;
            account.innerHTML = `<span>广告账户</span><strong>${escapeHtml(card.account_id || '未填写')}</strong>`;
            account.addEventListener('click', () => wrapper.querySelector('.creation-card-account input')?.focus());
            items.appendChild(account);
            const filled = (card.fields || []).filter(field => field.visible !== false && !creationCardValueEmpty(creationFieldValue(field)) && creationFieldNeedsUserInput(field));
            filled.slice(0, 5).forEach(field => {
                const item = document.createElement('button');
                item.type = 'button';
                item.className = 'creation-card-summary-item filled';
                item.innerHTML = `<span>${escapeHtml(field.label || field.path)}</span><strong>${escapeHtml(creationFieldDisplayValue(field))}</strong>`;
                item.addEventListener('click', () => creationCardScrollTo(wrapper, wrapper.querySelector(`.creation-card-field[data-field-path="${CSS.escape(field.path)}"]`)));
                items.appendChild(item);
            });
            const remaining = filled.length - Math.min(filled.length, 5);
            if (remaining > 0) {
                const more = document.createElement('span');
                more.className = 'creation-card-summary-more';
                more.textContent = `还有 ${remaining} 项已填写`;
                items.appendChild(more);
            }
            container.appendChild(items);
        }

        function renderCreationCardAutomation(card, wrapper) {
            const container = wrapper?.querySelector('.creation-card-automation');
            if (!container) return;
            const count = Number(card.auto_filled_count || 0);
            const autoText = count ? `系统已按平台规则填好 ${count} 项` : '系统会按平台规则生成安全默认值';
            const missing = creationCardPendingLabels(card).filter(label => label !== '广告账户 ID').length;
            container.querySelector('.creation-card-automation-copy strong').textContent = autoText;
            container.querySelector('.creation-card-automation-copy small').textContent = missing ? `还需要你确认 ${missing} 项；账户、素材和链接仍需使用真实资源` : '你可以直接修改任何默认值，最终会按当前内容提交';
            const toggle = container.querySelector('.creation-card-automation-toggle');
            if (toggle) {
                toggle.textContent = card.focus_mode ? '显示全部参数' : '只看需要确认';
                toggle.setAttribute('aria-pressed', String(Boolean(card.focus_mode)));
            }
        }

        function creationReviewRows(card) {
            const fields = (card.fields || []).filter(field => {
                const value = creationFieldValue(field);
                return field.visible !== false && value !== undefined && value !== null && value !== '';
            }).slice(0, 80);
            return creationDirectoryHierarchyGroups(fields).map(([hierarchy, hierarchyFields]) => {
                const rows = hierarchyFields.map(field => {
                    const fieldValue = creationFieldValue(field);
                    const rawValue = field.control === 'checkbox' ? creationFieldDisplayValue(field, fieldValue)
                        : field.control === 'text_list' ? presentedLines(fieldValue)
                        : field.control === 'asset_picker' ? (Array.isArray(fieldValue) ? fieldValue.map(item => item?.local_file || item?.name || item?.asset || '已选素材').join('、') : '')
                        : field.control === 'object_editor' ? structuredObjectValueText(fieldValue)
                        : creationCardValueText(fieldValue);
                    const value = String(rawValue || '已填写');
                    return `<div class="creation-review-row"><span>${escapeHtml(field.label || field.path)}</span><strong title="${escapeHtml(value)}">${escapeHtml(value.length > 180 ? `${value.slice(0, 180)}…` : value)}</strong></div>`;
                }).join('');
                return `<section class="creation-review-group"><div class="creation-review-group-head"><strong>${escapeHtml(hierarchy)}</strong><small>${hierarchyFields.length} 项</small></div>${rows}</section>`;
            }).join('');
        }

        function showCreationPreview(card) {
            const existing = document.querySelector(`.creation-card-review[data-card-review="${CSS.escape(card.id)}"]`);
            if (existing) { existing.remove(); return; }
            const review = document.createElement('div');
            review.className = 'creation-card-review';
            review.dataset.cardReview = card.id;
            const modeLabel = workspaceMode.mode === 'live' ? 'LIVE · 确认后提交' : 'DRY-RUN · 不修改线上';
            review.innerHTML = `<div class="creation-review-head"><div><strong>参数预览</strong><small>按广告层级汇总已填写内容</small></div><span>${modeLabel}</span></div><div class="creation-review-account"><span>广告账户</span><strong>${escapeHtml(card.account_id || '未填写')}</strong></div><div class="creation-review-groups">${creationReviewRows(card) || '<div class="creation-review-empty">暂无已填写参数</div>'}</div><div class="creation-review-note">这里只是预览，不会产生线上变化；确认后才会继续创建。</div>`;
            const target = document.querySelector(`.creation-card[data-card-id="${CSS.escape(card.id)}"] .creation-card-footer`);
            if (target) target.parentElement.insertBefore(review, target);
        }

        function showCreationReview(card) {
            if (!String(card.account_id || '').trim()) {
                const input = document.querySelector(`.creation-card[data-card-id="${CSS.escape(card.id)}"] .creation-card-account input`);
                input?.focus();
                addMessage('请先填写本次要操作的广告账户 ID，再提交创建。', 'agent', null, true);
                return;
            }
            if (!card.ready || card.validation_pending || card.validation_error || card.missing_fields?.length || card.invalid_fields?.length || (card.fields || []).some(field => field.local_error)) {
                addMessage('还有必填参数或联动参数需要补充，请先完成卡片中的标记项。', 'agent', null, true);
                return;
            }
            pendingCreationReview = card;
            const oldCard = document.getElementById('confirmCard');
            if (oldCard) oldCard.remove();
            const review = document.createElement('div');
            review.id = 'confirmCard';
            review.className = 'confirm-card';
            review.innerHTML = `<div class="confirm-card-header"><span class="confirm-icon">✓</span><span class="confirm-title">请确认创建计划</span></div><div class="confirm-card-body"><p>即将为账户 <strong>${escapeHtml(card.account_id)}</strong> 提交“${escapeHtml(card.title || '广告')}”的创建计划。</p><p>请确认账户、预算、定向和素材均无误。${workspaceMode.mode === 'live' ? '确认后将提交到广告平台。' : '当前为预览状态，不会修改线上账户。'}</p></div><div class="confirm-card-footer"><button class="confirm-btn cancel" onclick="cancelCreationReview()">返回修改</button><button class="confirm-btn confirm" onclick="confirmCreationSubmission()">确认创建</button></div>`;
            document.getElementById('confirmCardContainer').appendChild(review);
            review.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }

        function cancelCreationReview() {
            pendingCreationReview = null;
            document.getElementById('confirmCard')?.remove();
        }

        function confirmCreationSubmission() {
            const card = pendingCreationReview;
            pendingCreationReview = null;
            document.getElementById('confirmCard')?.remove();
            if (!card) return;
            if (!creationCardCanSubmit(card)) {
                addMessage('参数已发生变化，请回到卡片完成检查后再确认创建。', 'agent', null, true);
                return;
            }
            submitCreationCard(card);
        }

        async function submitCreationCard(card) {
            if (!creationCardCanSubmit(card)) {
                addMessage('当前参数还未通过检查，请先完成卡片中的必填项和格式校验。', 'agent', null, true);
                return;
            }
            const userInput = `提交“${card.title || card.provider + '广告'}”创建计划`;
            const requestParams = {
                user_input: userInput,
                user_id: 'web_user',
                session_id: sessionId,
                account_id: String(card.account_id || '').trim(),
                platform_params: creationCardParams(card),
                creation_blueprint_id: card.blueprint_id || null,
                creation_blueprint_version: card.blueprint_version || null,
            };
            addMessage('确认创建', 'user');
            addLoading();
            startExecutionTrace(userInput);
            try {
                const data = await streamChatRequest(requestParams);
                removeLoading();
                renderStreamResult(data, requestParams);
                await refreshConversationHistory({ silent: true });
            } catch (error) {
                removeLoading();
                markTraceFailed(error.message);
                addMessage('提交失败：' + error.message, 'agent', null, true);
            }
        }

        function updateCreationCardFieldStates(wrapper, card) {
            (card.fields || []).forEach(field => {
                const item = wrapper.querySelector(`[data-field-path="${CSS.escape(field.path)}"]`);
                if (!item) return;
                const state = creationCardFieldState(field);
                const invalid = state.status === 'invalid' || (card.invalid_fields || []).includes(field.path);
                item.classList.toggle('missing', state.status === 'missing');
                item.classList.toggle('invalid', invalid);
                item.classList.toggle('hidden', !state.visible);
                let error = item.querySelector('.creation-card-field-error');
                if (field.local_error) {
                    if (!error) {
                        error = document.createElement('div');
                        error.className = 'creation-card-field-error';
                        item.appendChild(error);
                    }
                    error.textContent = field.local_error;
                } else if (error) {
                    error.remove();
                }
            });
        }

        function renderCreationCard(card) {
            creationCardState.set(card.id, card);
            const wrapper = document.createElement('section');
            wrapper.className = `creation-card ${creationCardStatusKind(card)}${card.focus_mode ? ' focus-mode' : ''}`;
            wrapper.dataset.cardId = card.id;

            const header = document.createElement('div');
            header.className = 'creation-card-header';
            const headerTop = document.createElement('div');
            headerTop.className = 'creation-card-header-top';
            const kicker = document.createElement('div');
            kicker.className = 'creation-card-kicker';
            kicker.textContent = card.type === 'ad_creation_selector' ? '广告类型选择' : '广告参数草稿';
            const stateBadge = document.createElement('span');
            stateBadge.className = `creation-card-state ${creationCardStatusKind(card)}`;
            stateBadge.textContent = creationCardStatusLabel(card);
            headerTop.append(kicker, stateBadge);
            const title = document.createElement('div');
            title.className = 'creation-card-title';
            title.textContent = card.title || '广告创建参数';
            const meta = document.createElement('div');
            meta.className = 'creation-card-meta';
            const providerLabel = creationProviderLabel(card.provider);
            meta.textContent = card.blueprint_id ? `${providerLabel} · 参数会按平台规则联动，提交前会再次确认` : `${providerLabel} · 先选择创建类型`;
            header.append(headerTop, title, meta);

            const context = document.createElement('div');
            context.className = 'creation-card-context';
            const contextItems = [
                ['投放平台', providerLabel],
                ['创建类型', card.selector?.value ? creationCardValueText(card.selector.value) : (card.blueprint_id ? '已识别' : '待选择')],
            ];
            contextItems.forEach(([label, value]) => {
                const item = document.createElement('span');
                item.className = 'creation-card-context-item';
                const name = document.createElement('span');
                name.textContent = `${label}：`;
                const content = document.createElement('strong');
                content.textContent = value || '待补充';
                item.append(name, content);
                context.appendChild(item);
            });
            header.appendChild(context);
            const next = document.createElement('div');
            next.className = 'creation-card-next';
            const nextTitle = document.createElement('strong');
            nextTitle.textContent = '下一步  ';
            next.appendChild(nextTitle);
            const nextValue = document.createElement('span');
            nextValue.className = 'creation-card-next-value';
            nextValue.textContent = card.type === 'ad_creation_selector' ? '先选择创建类型，系统会展开对应参数。' : creationCardStatus(card);
            next.appendChild(nextValue);
            header.appendChild(next);
            wrapper.appendChild(header);

            const workbench = document.createElement('div');
            workbench.className = 'creation-card-workbench';
            const fieldNav = document.createElement('aside');
            fieldNav.className = 'creation-card-field-nav';
            fieldNav.setAttribute('aria-label', '参数填写目录');
            const main = document.createElement('div');
            main.className = 'creation-card-main';
            workbench.append(fieldNav, main);
            wrapper.appendChild(workbench);
            const contextGrid = document.createElement('div');
            contextGrid.className = 'creation-card-context-grid';
            main.appendChild(contextGrid);

            const account = document.createElement('div');
            account.className = 'creation-card-account';
            const accountLabel = document.createElement('label');
            accountLabel.textContent = `${creationAccountLabel(card.provider)} *`;
            const accountInput = document.createElement('input');
            accountInput.type = 'text';
            accountInput.autocomplete = 'off';
            accountInput.placeholder = `请输入本次要操作的${creationAccountLabel(card.provider)}`;
            accountInput.value = card.account_id || '';
            accountInput.addEventListener('input', () => {
                const previousAccount = String(card.account_id || '').trim();
                card.account_id = accountInput.value.trim();
                if (previousAccount !== card.account_id) {
                    delete card.validation_error;
                    card.ready = false;
                    const selectionsReset = resetAccountScopedSelections(card);
                    if (selectionsReset) {
                        const cursor = typeof accountInput.selectionStart === 'number' ? accountInput.selectionStart : null;
                        const replacement = renderCreationCard(card);
                        wrapper.replaceWith(replacement);
                        const nextInput = replacement.querySelector('.creation-card-account input');
                        if (nextInput) {
                            nextInput.focus({ preventScroll: true });
                            if (cursor !== null && typeof nextInput.setSelectionRange === 'function') nextInput.setSelectionRange(cursor, cursor);
                        }
                        if (card.blueprint_id) scheduleCreationCardEvaluation(card, null);
                        return;
                    }
                    if (card.blueprint_id) scheduleCreationCardEvaluation(card, null);
                }
                updateCreationCardIndicators(wrapper, card);
                refreshLookupAccountState(wrapper);
            });
            const accountHint = document.createElement('small');
            accountHint.textContent = '请填写你确认过的账户；系统不会替你猜测或自动选择。';
            account.append(accountLabel, accountInput, accountHint);
            contextGrid.appendChild(account);

            const progress = creationCardProgress(card);
            const progressBox = document.createElement('div');
            progressBox.className = 'creation-card-progress';
            progressBox.innerHTML = `<div class="creation-card-progress-head"><strong>必填项完成度</strong><span class="creation-card-progress-value">${progress.completed} / ${progress.total} · ${progress.percent}%</span></div><div class="creation-card-progress-track" role="progressbar" aria-label="必填项完成度" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${progress.percent}"><div class="creation-card-progress-bar" style="width:${progress.percent}%"></div></div>`;
            contextGrid.appendChild(progressBox);
            const summary = document.createElement('div');
            summary.className = 'creation-card-summary';
            main.appendChild(summary);

            const automation = document.createElement('div');
            automation.className = 'creation-card-automation';
            const automationCopy = document.createElement('div');
            automationCopy.className = 'creation-card-automation-copy';
            const automationTitle = document.createElement('strong');
            const automationHint = document.createElement('small');
            automationCopy.append(automationTitle, automationHint);
            const automationToggle = document.createElement('button');
            automationToggle.type = 'button';
            automationToggle.className = 'creation-card-automation-toggle';
            automationToggle.setAttribute('aria-pressed', String(Boolean(card.focus_mode)));
            automationToggle.addEventListener('click', () => {
                card.focus_mode = !card.focus_mode;
                wrapper.classList.toggle('focus-mode', card.focus_mode);
                renderCreationCardAutomation(card, wrapper);
                renderCreationCardFieldNav(card, wrapper);
            });
            automation.append(automationCopy, automationToggle);
            main.appendChild(automation);

            const groups = creationFieldGroups(card.fields || []);
            const stepbar = document.createElement('div');
            stepbar.className = 'creation-card-stepbar';
            groups.forEach((group, index) => {
                const groupProgress = fieldGroupProgress(group.fields);
                const step = document.createElement('button');
                step.type = 'button';
                step.className = `creation-card-step${index === 0 ? ' active' : ''}${groupProgress.missing ? ' has-missing' : ''}`;
                step.dataset.step = group.id;
                step.innerHTML = `<span class="creation-card-step-dot">${index + 1}</span><span><strong>${escapeHtml(group.title)}</strong><small>${groupProgress.missing ? `待填 ${groupProgress.missing}` : '已就绪'}</small></span>`;
                step.addEventListener('click', () => {
                    const target = wrapper.querySelector(`.creation-card-section[data-step="${CSS.escape(group.id)}"]`);
                    creationCardScrollTo(wrapper, target);
                    stepbar.querySelectorAll('.creation-card-step').forEach(node => node.classList.toggle('active', node === step));
                });
                stepbar.appendChild(step);
            });
            main.appendChild(stepbar);

            const fields = document.createElement('div');
            fields.className = 'creation-card-fields';
            groups.forEach(group => {
                const section = document.createElement('section');
                section.className = `creation-card-section${group.id === 'advanced' ? ' collapsible' : ''}`;
                if (['advanced', 'other'].includes(group.id)) section.classList.add('is-collapsed');
                section.dataset.step = group.id;
                const sectionHeader = document.createElement('div');
                sectionHeader.className = 'creation-card-section-header';
                const sectionTitle = document.createElement('div');
                sectionTitle.innerHTML = `<span class="creation-card-section-icon">${group.id === 'campaign' ? '◎' : group.id === 'audience' ? '◌' : group.id === 'creative' ? '▧' : group.id === 'measurement' ? '⌁' : '⋯'}</span><span><strong>${escapeHtml(group.title)}</strong><small>${escapeHtml(group.description)}</small></span>`;
                const sectionProgress = fieldGroupProgress(group.fields);
                const sectionCount = document.createElement('span');
                sectionCount.className = `creation-card-section-count${sectionProgress.missing ? ' has-missing' : ''}`;
                sectionCount.textContent = sectionProgress.missing ? `待填 ${sectionProgress.missing}` : `${sectionProgress.total} 项`;
                const sectionToggle = document.createElement('button');
                sectionToggle.type = 'button';
                sectionToggle.className = 'creation-section-toggle';
                sectionToggle.setAttribute('aria-expanded', String(!section.classList.contains('is-collapsed')));
                sectionToggle.textContent = section.classList.contains('is-collapsed') ? '展开' : '收起';
                sectionToggle.addEventListener('click', event => {
                    event.stopPropagation();
                    setCreationSectionExpanded(section, section.classList.contains('is-collapsed'));
                });
                sectionHeader.append(sectionTitle, sectionCount, sectionToggle);
                section.appendChild(sectionHeader);
                const sectionFields = document.createElement('div');
                sectionFields.className = 'creation-card-section-fields';
                section.appendChild(sectionFields);
                fields.appendChild(section);
                group.fields.forEach(field => {
                const fieldState = creationCardFieldState(field);
                const item = document.createElement('div');
                item.dataset.fieldPath = field.path;
                const wideField = field.control === 'lookup' || ['asset_picker', 'file_reference', 'text_list', 'object_editor', 'json', 'advanced_json'].includes(field.control);
                item.className = `creation-card-field${wideField ? ' wide' : ''}${field.advanced ? ' auto-field' : ''}${field.auto_filled ? ' auto-filled' : ''}${fieldState.visible ? '' : ' hidden'}${fieldState.status === 'missing' ? ' missing' : ''}${fieldState.status === 'invalid' ? ' invalid' : ''}`;
                const label = document.createElement('label');
                label.textContent = field.label || field.path;
                if (creationFieldNeedsUserInput(field)) {
                    const required = document.createElement('span');
                    required.className = 'required';
                    required.textContent = '*';
                    label.appendChild(required);
                }
                const modeLabel = creationFieldModeLabel(field);
                if (modeLabel) {
                    const mode = document.createElement('span');
                    mode.className = `creation-field-mode${field.auto_filled ? ' auto' : ''}`;
                    mode.textContent = modeLabel;
                    label.appendChild(mode);
                }
                const hierarchy = creationHierarchyLabel(field);
                if (hierarchy) {
                    const badge = document.createElement('span');
                    badge.className = 'creation-hierarchy-badge';
                    badge.textContent = hierarchy;
                    label.appendChild(badge);
                }
                item.appendChild(label);
                if (field.description) {
                    const help = document.createElement('div');
                    help.className = 'help';
                    help.textContent = field.description;
                    item.appendChild(help);
                }
                let control;
                const options = Array.isArray(field.options) ? field.options : [];
                if (field.control === 'file_reference') {
                    control = document.createElement('div');
                    control.className = 'asset-picker';
                    const idInput = document.createElement('input');
                    idInput.type = 'text';
                    idInput.placeholder = '填写已上传的素材 ID，或先选择本地文件作为草稿';
                    idInput.value = creationCardValueText(field.value);
                    const fileInput = document.createElement('input');
                    fileInput.type = 'file';
                    fileInput.accept = field.accept || '*/*';
                    fileInput.addEventListener('change', () => {
                        const file = fileInput.files?.[0];
                        if (file) note.textContent = `已加入本地草稿：${file.name}（未上传，提交前仍需素材 ID）`;
                    });
                    const note = document.createElement('div');
                    note.className = 'asset-picker-note';
                    note.textContent = '本地文件仅用于准备素材，不会自动上传；执行前仍需对应平台素材 ID。';
                    idInput.addEventListener('change', () => {
                        field.value = idInput.value.trim() || undefined;
                        creationCardState.set(card.id, card);
                        scheduleCreationCardEvaluation(card, field.path);
                    });
                    control.append(idInput, fileInput, note);
                } else if (field.control === 'asset_picker') {
                    control = document.createElement('div');
                    control.className = 'asset-picker';
                    const fileInput = document.createElement('input');
                    fileInput.type = 'file';
                    fileInput.multiple = true;
                    fileInput.accept = field.accept || '*/*';
                    fileInput.addEventListener('change', () => {
                        const existing = Array.isArray(field.value) ? field.value : [];
                        field.value = [...existing, ...Array.from(fileInput.files || []).map(file => ({
                            local_file: file.name, mime_type: file.type || 'application/octet-stream',
                            size_bytes: file.size, source: 'local_staging',
                        }))];
                        creationCardState.set(card.id, card);
                        scheduleCreationCardEvaluation(card, field.path);
                        updateCreationCardIndicators(wrapper, card);
                    });
                    control.appendChild(fileInput);
                    const list = document.createElement('div');
                    list.className = 'asset-picker-list';
                    (Array.isArray(field.value) ? field.value : []).forEach(asset => {
                        const chip = document.createElement('span');
                        chip.className = 'asset-chip';
                        chip.textContent = asset?.local_file || asset?.name || asset?.asset || asset?.resource_name || '已选素材';
                        list.appendChild(chip);
                    });
                    control.appendChild(list);
                    const note = document.createElement('div');
                    note.className = 'asset-picker-note';
                    note.textContent = '当前加入本地草稿，不会自动上传或调用渠道接口。';
                    control.appendChild(note);
                } else if (field.control === 'derived_readonly') {
                    control = document.createElement('input');
                    control.className = 'derived-readonly';
                    control.readOnly = true;
                    control.disabled = true;
                    control.value = creationCardValueText(field.value || options[0]);
                } else if (field.control === 'select' || field.control === 'multiselect') {
                    const useChoiceTiles = field.control === 'multiselect'
                        || (options.length > 0 && options.length <= 6 && field.options_state !== 'awaiting_dependency' && field.options_state !== 'no_matching_rule');
                    if (useChoiceTiles) {
                        const multiple = field.control === 'multiselect';
                        control = renderChoiceTiles(options, field.value, multiple, option => field.option_labels?.[String(option.value)] || '', value => {
                            field.value = multiple && !value.length ? undefined : value;
                            creationCardState.set(card.id, card);
                            scheduleCreationCardEvaluation(card, field.path);
                            updateCreationCardIndicators(wrapper, card);
                        });
                        control.dataset.customChoice = 'true';
                    } else {
                    control = document.createElement('select');
                    if (field.control === 'select') {
                        const empty = document.createElement('option');
                        empty.value = '';
                        empty.textContent = field.options_state === 'awaiting_dependency'
                            ? '请先完成上游选择…'
                            : field.options_state === 'no_matching_rule'
                                ? '当前组合暂无可用选项'
                                : field.required ? '请选择…' : '不设置';
                        control.appendChild(empty);
                    }
                    if (field.options_state === 'awaiting_dependency' || field.options_state === 'no_matching_rule') {
                        control.disabled = true;
                    }
                    options.forEach(option => {
                        const node = document.createElement('option');
                        node.value = creationCardValueText(option.value);
                        node.textContent = field.option_labels?.[String(option.value)] || option.label || node.value;
                        if (Array.isArray(field.value) ? field.value.map(String).includes(node.value) : String(field.value ?? '') === node.value) node.selected = true;
                        control.appendChild(node);
                    });
                    }
                } else if (field.control === 'lookup') {
                    if (!card.selection_tokens) card.selection_tokens = {};
                    if (!card.selection_token_tools) card.selection_token_tools = {};
                    control = renderLookupPicker(field, {
                        platform: card.provider,
                        accountId: card.account_id,
                        getAccountId: () => card.account_id,
                        accountRequired: field.lookup?.account_required,
                        getLookupContext: () => lookupContextFromFields(card.fields),
                        targetToolName: field.tool,
                        fieldName: field.provider_field || field.path,
                        selectionTokens: card.selection_tokens,
                        optionsStore: card.lookup_options || (card.lookup_options = {}),
                        onSelection: ({ value, tokens }) => {
                            const key = field.provider_field || field.path;
                            field.value = value;
                            if (tokens) {
                                card.selection_tokens[key] = tokens;
                                card.selection_token_tools[key] = field.tool;
                            } else {
                                delete card.selection_tokens[key];
                                delete card.selection_token_tools[key];
                            }
                            creationCardState.set(card.id, card);
                            scheduleCreationCardEvaluation(card, field.path);
                            updateCreationCardIndicators(wrapper, card);
                        },
                    });
                } else if (field.control === 'checkbox') {
                    control = document.createElement('input');
                    control.type = 'checkbox';
                    control.checked = Boolean(field.value);
                } else if (field.control === 'text_list') {
                    control = document.createElement('textarea');
                    control.className = 'asset-text-list';
                    control.placeholder = '每行填写一条';
                    control.value = creationCardDisplayValue(field);
                } else if (field.control === 'object_editor') {
                    control = renderStructuredObjectEditor(
                        field.object_shape === 'array'
                            ? { type: 'array', items: { type: 'object', properties: field.object_properties || {} } }
                            : { type: 'object', properties: field.object_properties || {} },
                        field.value,
                        value => {
                            field.value = value;
                            creationCardState.set(card.id, card);
                            scheduleCreationCardEvaluation(card, field.path);
                            updateCreationCardIndicators(wrapper, card);
                        },
                        field.object_properties || {},
                        {
                            platform: card.provider,
                            accountId: card.account_id,
                            getAccountId: () => card.account_id,
                            targetToolName: field.tool,
                            fieldPath: field.provider_field,
                            accountRequired: field.lookup?.account_required,
                            getLookupContext: () => lookupContextFromFields(card.fields),
                            selectionTokens: card.selection_tokens || (card.selection_tokens = {}),
                            optionsStore: card.lookup_options || (card.lookup_options = {}),
                            onSelection: ({ fieldName, tokens }) => {
                                if (!card.selection_token_tools) card.selection_token_tools = {};
                                if (tokens) {
                                    card.selection_tokens[fieldName] = tokens;
                                    card.selection_token_tools[fieldName] = field.tool;
                                } else {
                                    delete card.selection_tokens[fieldName];
                                    delete card.selection_token_tools[fieldName];
                                }
                            },
                        },
                    );
                } else if (field.control === 'json' || field.control === 'advanced_json') {
                    control = document.createElement('textarea');
                    control.className = field.control === 'advanced_json' ? 'advanced-json-editor' : '';
                    control.placeholder = field.json_shape === 'array' ? '[...]'
                        : field.json_shape === 'object_or_array' ? '{...} 或 [...]'
                            : '{...}';
                    control.value = creationCardValueText(field.value);
                } else {
                    control = document.createElement('input');
                    control.type = field.control === 'number' ? 'number' : 'text';
                    control.value = creationCardValueText(field.value);
                }
                let controlNode = control;
                let checkboxState = null;
                if (field.control === 'checkbox') {
                    const checkboxLabel = document.createElement('label');
                    checkboxLabel.className = 'checkbox-control';
                    const visual = document.createElement('span');
                    visual.className = 'checkbox-visual';
                    const copy = document.createElement('span');
                    copy.className = 'checkbox-copy';
                    const title = document.createElement('strong');
                    title.textContent = '启用该设置';
                    checkboxState = document.createElement('small');
                    checkboxState.textContent = control.checked ? '已开启' : '未开启';
                    copy.append(title, checkboxState);
                    checkboxLabel.append(control, visual, copy);
                    controlNode = checkboxLabel;
                }
                control.dataset.path = field.path;
                const updateValue = () => {
                    if (field.control === 'asset_picker' || field.control === 'file_reference' || field.control === 'derived_readonly') return;
                    let value;
                    if (field.control === 'checkbox') value = control.checked;
                    else if (field.control === 'multiselect') value = Array.from(control.selectedOptions).map(option => option.value);
                    else value = parseCreationCardValue(field, control.value.trim());
                    if (checkboxState) checkboxState.textContent = control.checked ? '已开启' : '未开启';
                    field.value = value;
                    item.classList.toggle('missing', creationFieldNeedsUserInput(field) && (value === undefined || value === null || value === ''));
                    creationCardState.set(card.id, card);
                    scheduleCreationCardEvaluation(card, field.path);
                    const status = wrapper.querySelector('.creation-card-status');
                    updateCreationCardIndicators(wrapper, card);
                };
                if (!control.dataset.customChoice && field.control !== 'asset_picker' && field.control !== 'file_reference' && field.control !== 'derived_readonly' && field.control !== 'object_editor' && field.control !== 'lookup') control.addEventListener('change', updateValue);
                if (field.control === 'text' || field.control === 'text_list' || field.control === 'number' || field.control === 'advanced_json') control.addEventListener('input', updateValue);
                item.appendChild(controlNode);
                if (field.auto_filled && field.default_reason) {
                    const defaultNote = document.createElement('div');
                    defaultNote.className = 'creation-card-default-note';
                    defaultNote.textContent = `默认逻辑：${field.default_reason}`;
                    item.appendChild(defaultNote);
                }
                const source = document.createElement('div');
                source.className = 'source';
                source.textContent = field.auto_filled
                    ? '系统默认值 · 可直接修改'
                    : field.control === 'derived_readonly'
                    ? '由当前广告系列类型自动匹配'
                    : field.source === 'lookup' || field.control === 'lookup' ? '需要从指定账户中选择'
                        : (field.control === 'asset_picker' || field.control === 'file_reference') ? '本地素材草稿'
                            : field.control === 'object_editor' ? '按字段填写，系统会按 Tool Schema 组装'
                                : field.control === 'advanced_json' ? '高级 Provider 字段；请使用已审核的当前版本 payload'
                                    : '可直接填写';
                item.appendChild(source);
                if (field.manual_entry && typeof field.manual_entry === 'object') {
                    const help = document.createElement('div');
                    help.className = 'manual-entry-help';
                    const title = field.manual_entry.title || '需要手动提供的外部标识';
                    const instructions = field.manual_entry.instructions || '该字段当前没有可用的受控列表查询。';
                    help.innerHTML = `<strong>${escapeHtml(title)}</strong><br>${escapeHtml(instructions)}${field.manual_entry.example ? `<br>示例：${escapeHtml(field.manual_entry.example)}` : ''}`;
                    item.appendChild(help);
                }
                if (field.local_error) {
                    const error = document.createElement('div');
                    error.className = 'creation-card-field-error';
                    error.textContent = field.local_error;
                    item.appendChild(error);
                }
                sectionFields.appendChild(item);
                });
            });
            main.appendChild(fields);

            const footer = document.createElement('div');
            footer.className = 'creation-card-footer';
            const status = document.createElement('span');
            status.className = 'creation-card-status';
            status.textContent = creationCardStatus(card);
            footer.appendChild(status);
            const focusAction = document.createElement('button');
            focusAction.type = 'button';
            focusAction.className = 'creation-card-focus-action';
            focusAction.textContent = creationCardInvalidLabels(card).length ? '查看问题' : '定位待填项';
            focusAction.hidden = !(!String(card.account_id || '').trim() || creationCardPendingLabels(card).length || creationCardInvalidLabels(card).length);
            focusAction.addEventListener('click', () => focusCreationCardIssue(card, wrapper));
            footer.appendChild(focusAction);
            const actions = document.createElement('div');
            actions.className = 'creation-card-actions';
            (card.actions || []).forEach(action => {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = `creation-card-action${action.id === 'submit_create' ? ' primary' : ''}`;
                button.dataset.creationAction = action.id;
                button.textContent = action.label || action.id;
                if (action.id === 'submit_create') button.disabled = !creationCardCanSubmit(card);
                button.addEventListener('click', () => handleCreationCardAction(card.id, action.id));
                actions.appendChild(button);
            });
            footer.appendChild(actions);
            main.appendChild(footer);
            renderCreationCardFieldNav(card, wrapper);
            renderCreationCardSummary(card, wrapper);
            renderCreationCardAutomation(card, wrapper);
            return wrapper;
        }

        function renderUiCards(ui) {
            const fragment = document.createDocumentFragment();
            (ui?.cards || []).forEach(card => fragment.appendChild(renderCreationCard(card)));
            return fragment;
        }

        async function handleCreationCardAction(cardId, action) {
            const card = creationCardState.get(cardId);
            if (!card) return;
            if (action === 'continue_chat') {
                setInput(`请继续完善“${card.title || '广告创建'}”，我可以直接在输入框里补充参数。`);
                return;
            }
            if (action === 'open_form') {
                const selectionField = card.fields?.find(field => field.selection_kind === 'blueprint_variant');
                const selectedOption = selectionField?.options?.find(option => option.value === selectionField.value);
                const selected = selectedOption?.selector_value
                    || card.fields?.find(field => field.value)?.value
                    || null;
                openBlueprintManager(
                    card.provider,
                    selected,
                    selectedOption?.blueprint_id || null,
                );
                return;
            }
            if (action === 'validate') {
                await evaluateCreationCard(card, null);
                addMessage(card.ready ? '参数检查完成，当前填写内容满足蓝图要求。' : '参数检查完成，请根据卡片中的提示补充或调整参数。', 'agent');
                return;
            }
            if (action === 'preview') {
                showCreationPreview(card);
                return;
            }
            if (action === 'submit_create') {
                showCreationReview(card);
            }
        }

        // Add message to chat
        function addMessage(content, type = 'agent', tools = null, isError = false, toolSummaryHtml = '', messageTime = null, ui = null) {
            const container = document.getElementById('chatContainer');
            const welcome = document.getElementById('welcomePage');
            if (welcome) welcome.style.display = 'none';

            const msg = document.createElement('div');
            msg.className = `message ${type}${isError ? ' error' : ''}`;

            const parsedTime = messageTime ? new Date(messageTime) : new Date();
            const time = Number.isNaN(parsedTime.getTime())
                ? new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
                : parsedTime.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });

            let bodyHtml = `<div class="message-content-text">${formatContent(content)}</div>`;
            if (toolSummaryHtml) {
                bodyHtml += toolSummaryHtml;
            } else if (tools && tools.length > 0) {
                bodyHtml += `<div class="tool-results">${tools.map(t => `
                    <span class="tool-tag ${t.success ? 'success' : 'error'}">
                        ${t.success ? '✓' : '✗'} ${t.tool}
                    </span>
                `).join('')}</div>`;
            }
            if (ui?.cards?.length) bodyHtml += '<div class="message-ui-cards"></div>';
            if (ui?.clarification?.options?.length) {
                const options = ui.clarification.options
                    .filter(option => option && (option.label || option.value))
                    .slice(0, 12);
                if (options.length) {
                    bodyHtml += `<div class="message-clarification-options">${options.map(option => {
                        const answer = String(option.label || option.value);
                        return `<button type="button" class="clarification-option" data-answer="${escapeHtml(answer)}">${escapeHtml(answer)}</button>`;
                    }).join('')}</div>`;
                }
            }
            if (ui?.clarification?.fields?.length) {
                const fields = ui.clarification.fields
                    .filter(field => field && (field.label || field.path))
                    .slice(0, 12);
                if (fields.length) {
                    bodyHtml += `<div class="message-clarification-fields">${fields.map(field => {
                        const source = field.source === 'lookup'
                            ? '从资源列表选择'
                            : field.source === 'enum' ? '从可选值中选择' : '直接补充';
                        const hint = field.hint ? ` · ${field.hint}` : '';
                        return `<div class="clarification-field-row"><span class="clarification-field-label">${escapeHtml(field.label || field.path)}</span><span class="clarification-field-source">${escapeHtml(source)}${escapeHtml(hint)}</span></div>`;
                    }).join('')}</div>`;
                }
            }

            msg.innerHTML = `
                <div class="message-avatar">${type === 'user' ? '👤' : '🤖'}</div>
                <div class="message-content">
                    <div class="message-header">
                        ${type === 'user' ? '' : '<span class="message-sender">AI Ops Agent</span>'}
                        <span class="message-time">${time}</span>
                    </div>
                    <div class="message-body">${bodyHtml}</div>
                </div>
            `;

            if (ui?.cards?.length) {
                msg.classList.add('has-ui-cards');
                msg.querySelector('.message-ui-cards').appendChild(renderUiCards(ui));
            }
            msg.querySelectorAll('.clarification-option').forEach(button => {
                button.addEventListener('click', () => {
                    if (isSending) return;
                    setInput(button.dataset.answer || '');
                    sendMessage();
                });
            });

            container.appendChild(msg);
            document.getElementById('chatArea').scrollTop = document.getElementById('chatArea').scrollHeight;

            return msg;
        }

        // Add loading indicator
        function addLoading() {
            const container = document.getElementById('chatContainer');
            const msg = document.createElement('div');
            msg.className = 'message agent';
            msg.id = 'loadingMsg';

            msg.innerHTML = `
                <div class="message-avatar">🤖</div>
                <div class="message-content">
                    <div class="message-header">
                        <span class="message-sender">AI Ops Agent</span>
                    </div>
                    <div class="loading-indicator">
                        <span></span><span></span><span></span>
                    </div>
                </div>
            `;

            container.appendChild(msg);
            document.getElementById('chatArea').scrollTop = document.getElementById('chatArea').scrollHeight;
        }

        // Remove loading indicator
        function removeLoading() {
            const loading = document.getElementById('loadingMsg');
            if (loading) loading.remove();
        }

        // Show confirmation as inline card in chat
        function showConfirm(payload, originalRequest = null) {
            // 移除旧的确认卡片
            const oldCard = document.getElementById('confirmCard');
            if (oldCard) oldCard.remove();

            pendingRequest = {
                payload,
                originalRequest: originalRequest  // 保存原始请求数据
            };
            markTraceAwaitingConfirmation();

            // 创建确认卡片
            const card = document.createElement('div');
            card.id = 'confirmCard';
            card.className = 'confirm-card';

            let inputHtml = '';
            if (payload.type === 'ask_account') {
                inputHtml = `
                    <div class="confirm-field">
                        <label>📱 ${payload.platform || '平台'} 账户ID</label>
                        <input type="text" id="confirmAccountInput" placeholder="请输入账户ID..." autofocus>
                    </div>
                `;
            } else if (payload.type === 'ask_params') {
                inputHtml = `
                    <div class="confirm-field">
                        <label>📝 缺失参数: ${payload.missing.join(', ')}</label>
                        <input type="text" id="confirmParamInput" placeholder="例如: campaign_id=12345" autofocus>
                    </div>
                `;
            } else if (payload.type === 'confirm_write_plan') {
                const steps = Array.isArray(payload.preview?.steps) ? payload.preview.steps : [];
                const stepHtml = steps.length
                    ? `<div class="confirm-plan-steps">${steps.map((step, index) => `
                        <div class="confirm-plan-step">
                            <span class="confirm-plan-index">${index + 1}</span>
                            <span><strong>${escapeHtml(step.resource_type || '广告资源')}</strong><small>${escapeHtml(step.tool || '')}${step.parent_resource_type ? ` · 依赖 ${escapeHtml(step.parent_resource_type)}` : ''}</small></span>
                        </div>`).join('')}</div>`
                    : '';
                inputHtml = `
                    <div class="confirm-plan-intro">将按以下顺序提交，全部资源会以安全初始状态创建：</div>
                    ${stepHtml}
                    <div class="confirm-plan-account">${escapeHtml(payload.platform || '平台')} · 账户 ${escapeHtml(payload.account_id || '已校验')}</div>
                `;
            }

            card.innerHTML = `
                <div class="confirm-card-header">
                    <span class="confirm-icon">⚠️</span>
                    <span class="confirm-title">${payload.question || '需要确认'}</span>
                </div>
                <div class="confirm-card-body">
                    ${inputHtml}
                </div>
                <div class="confirm-card-footer">
                    <button class="confirm-btn cancel" onclick="cancelConfirm()">取消</button>
                    <button class="confirm-btn confirm" onclick="executeConfirm()">确认执行</button>
                </div>
            `;

            // 插入到输入框上方的容器中
            document.getElementById('confirmCardContainer').appendChild(card);

            // 自动聚焦输入框并滚动到卡片
            setTimeout(() => {
                const input = document.getElementById('confirmAccountInput') || document.getElementById('confirmParamInput');
                if (input) input.focus();
                card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }, 100);
        }

        // Cancel confirmation
        function cancelConfirm() {
            pendingRequest = null;
            pendingCreationReview = null;
            const card = document.getElementById('confirmCard');
            if (card) card.remove();
            addMessage('❌ 操作已取消', 'agent');
        }

        // Execute confirmation
        async function executeConfirm() {
            if (!pendingRequest) return;

            const { payload, originalRequest } = pendingRequest;
            pendingRequest = null;

            // 先获取用户输入（在移除卡片之前）
            const accountInput = document.getElementById('confirmAccountInput');
            const paramInput = document.getElementById('confirmParamInput');

            let account_id = null;
            let extra_params = {};

            // 获取账户 ID
            if (accountInput && accountInput.value.trim()) {
                account_id = accountInput.value.trim();
            }

            // 获取缺失参数值（支持多种格式）
            if (paramInput && paramInput.value.trim()) {
                const paramValue = paramInput.value.trim();
                // 支持 "campaign_id=12345" 或 "12345" 格式
                if (paramValue.includes('=')) {
                    const parts = paramValue.split('=');
                    extra_params[parts[0].trim()] = parts[1].trim();
                } else {
                    // 如果只输入了值，使用 payload.missing[0] 作为参数名
                    if (payload.missing && payload.missing.length > 0) {
                        extra_params[payload.missing[0]] = paramValue;
                    }
                }
            }

            // 移除卡片
            const card = document.getElementById('confirmCard');
            if (card) card.remove();

            // The confirmation is a user action. Keep it as a user message
            // so the transcript does not invent a second Agent turn.
            addMessage('确认并继续执行', 'user');
            addLoading();
            startExecutionTrace(originalRequest?.user_input || '确认并继续执行');

            // 发送带参数的请求 - 使用原始 user_input
            const userInput = originalRequest ? originalRequest.user_input : '';
            try {
                // 构建 platform_params，合并原始参数和用户提供的新参数
                const originalParams = originalRequest?.platform_params || {};
                const platforms = originalRequest?.platforms || [];

                const requestParams = {
                    user_input: userInput,
                    user_id: 'web_user',
                    session_id: sessionId,
                    confirmed: true,
                    confirmation_payload: payload,
                    creation_blueprint_id: originalRequest?.creation_blueprint_id || null,
                    creation_blueprint_version: originalRequest?.creation_blueprint_version || null,
                };

                // 如果有额外参数，添加到对应平台的 params 中
                if (Object.keys(extra_params).length > 0 && platforms.length > 0) {
                    const firstPlatform = platforms[0];
                    requestParams.platform_params = {
                        [firstPlatform]: {
                            ...(originalParams[firstPlatform] || {}),
                            ...extra_params
                        }
                    };
                }

                if (account_id) {
                    requestParams.account_id = account_id;
                }

                const data = await streamChatRequest(requestParams);
                removeLoading();
                renderStreamResult(data, requestParams);
                await refreshConversationHistory({ silent: true });

            } catch (error) {
                removeLoading();
                markTraceFailed(error.message);
                addMessage('❌ 请求失败: ' + error.message, 'agent', null, true);
            }
        }

        // Send message
        async function sendMessage() {
            const input = document.getElementById('userInput');
            const text = input.value.trim();
            if (!text || isSending) return;

            isSending = true;
            const sendButton = document.getElementById('sendBtn');
            if (sendButton) {
                sendButton.disabled = true;
                sendButton.classList.add('is-sending');
                sendButton.setAttribute('aria-busy', 'true');
                sendButton.setAttribute('aria-label', 'Agent 正在处理');
                sendButton.title = 'Agent 正在处理';
            }

            input.value = '';
            input.style.height = 'auto';

            addMessage(text, 'user');
            addLoading();
            startExecutionTrace(text);

            conversationCount++;
            const statToday = document.getElementById('statToday');
            if (statToday) statToday.textContent = conversationCount;

            try {
                const requestParams = {
                    user_input: text,
                    user_id: 'web_user',
                    session_id: sessionId,
                    ...(pendingBlueprintRequest || {}),
                };
                pendingBlueprintRequest = null;
                const data = await streamChatRequest(requestParams);
                removeLoading();
                apiCallCount++;
                const statApiCalls = document.getElementById('statAPICalls');
                if (statApiCalls) statApiCalls.textContent = apiCallCount;
                renderStreamResult(data, requestParams);
                await refreshConversationHistory({ silent: true });

            } catch (error) {
                removeLoading();
                markTraceFailed(error.message);
                addMessage('请求失败: ' + error.message, 'agent', null, true);
            } finally {
                isSending = false;
                if (sendButton) {
                    sendButton.disabled = false;
                    sendButton.classList.remove('is-sending');
                    sendButton.removeAttribute('aria-busy');
                    sendButton.setAttribute('aria-label', '发送');
                    sendButton.title = '发送';
                }
            }
        }

        // Render response
        function renderResponse(data) {
            const tools = data.results?.map(r => ({
                tool: r.tool,
                success: r.success
            })) || [];

            addMessage(data.reply || '服务端未返回可展示的结果。', 'agent', tools);
        }

        // Escape HTML special characters
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        // Format markdown-like content: bold, tables, code, line breaks
        function formatContent(content) {
            if (!content) return '';
            let html = escapeHtml(content);

            // Bold
            html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

            // Inline code
            html = html.replace(/`(.+?)`/g, '<code>$1</code>');

            // Markdown tables: detect table blocks and convert
            const lines = html.split('\n');
            let inTable = false;
            let tableLines = [];
            let result = [];

            function flushTable() {
                if (tableLines.length > 0) {
                    try {
                        const rows = tableLines.map(row => row.split('|').map(c => c.trim()).filter(Boolean));
                        if (rows.length >= 2) {
                            const headerRow = rows[0];
                            const dataRows = rows.slice(1).filter(r => !r.every(c => /^[-:]+$/.test(c)));
                            let thHtml = '<tr>' + headerRow.map(c => `<th>${c}</th>`).join('') + '</tr>';
                            let tdHtml = dataRows.map(r => '<tr>' + r.map(c => `<td>${c}</td>`).join('') + '</tr>').join('');
                            result.push(`<table class="data-table"><thead>${thHtml}</thead><tbody>${tdHtml}</tbody></table>`);
                        } else {
                            result.push(tableLines.join('<br>'));
                        }
                    } catch (e) {
                        result.push(tableLines.join('<br>'));
                    }
                    tableLines = [];
                    inTable = false;
                }
            }

            for (const line of lines) {
                const trimmed = line.trim();
                // Detect table rows (starts and ends with |)
                if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
                    inTable = true;
                    tableLines.push(trimmed);
                } else {
                    flushTable();
                    if (trimmed) {
                        result.push(trimmed);
                    }
                }
            }
            flushTable();

            return result.join('<br>');
        }

        // Format reply content (legacy, kept for compatibility)
        function formatReply(content) {
            return formatContent(content);
        }

        // New chat
        function newChat() {
            stopDurableRunPolling();
            sessionId = null;
            selectedConversationId = null;
            loadedConversationTurnIds.clear();
            pendingRequest = null;
            pendingBlueprintRequest = null;
            pendingCreationReview = null;
            historySelectionMode = false;
            selectedConversationIds.clear();
            document.getElementById('confirmCard')?.remove();
            resetExecutionTrace();
            renderConversationHistory();
            document.getElementById('chatContainer').innerHTML = `
                <div class="welcome-page" id="welcomePage">
                    <div class="welcome-icon">🤖</div>
                    <h1 class="welcome-title">把投放问题，交给一个懂执行的 Agent。</h1>
                    <p class="welcome-desc">从账户查询、效果分析到广告创建，先在安全的 dry-run 环境里看清每一步，再决定是否执行。</p>

                    <div class="feature-grid">
                        <div class="feature-card" onclick="setInput('帮我列出 Meta 账户')">
                            <div class="icon">📘</div>
                            <div class="title">查看账户</div>
                            <div class="desc">账户与 Campaign 概览</div>
                        </div>
                        <div class="feature-card" onclick="setInput('创建 TikTok 广告系列')">
                            <div class="icon">🎵</div>
                            <div class="title">创建 Campaign</div>
                            <div class="desc">从蓝图开始配置广告</div>
                        </div>
                        <div class="feature-card" onclick="setInput('查询 Google Ads 报表')">
                            <div class="icon">🔍</div>
                            <div class="title">分析报表</div>
                            <div class="desc">读懂渠道效果与趋势</div>
                        </div>
                        <div class="feature-card" onclick="setInput('跨渠道预算优化')">
                            <div class="icon">⚡</div>
                            <div class="title">优化预算</div>
                            <div class="desc">比较渠道，找到增长空间</div>
                        </div>
                    </div>
                </div>
            `;
        }

        document.addEventListener('click', (event) => {
            if (!event.target.closest('.global-actions') && !event.target.closest('.workspace-nav') && !event.target.closest('.workspace-popover') && !event.target.closest('.knowledge-overlay') && !event.target.closest('.blueprint-overlay') && !event.target.closest('.monitoring-overlay') && !event.target.closest('#scheduleOverlay') && !event.target.closest('#memoryOverlay') && !event.target.closest('.system-ops-wrap')) {
                closeWorkspacePopovers();
            }
        });
        document.getElementById('knowledgeOverlay')?.addEventListener('click', (event) => {
            if (event.target.id === 'knowledgeOverlay') closeWorkspacePopovers();
        });
        document.getElementById('blueprintOverlay')?.addEventListener('click', (event) => {
            // Only the backdrop is a close target.  The console also stops
            // propagation inline so a list item can safely replace its own
            // DOM during selection without triggering a document-level
            // popover close.
            if (event.target === event.currentTarget) closeBlueprintManager();
        });
        document.getElementById('historyDeleteOverlay')?.addEventListener('click', (event) => {
            if (event.target.id === 'historyDeleteOverlay') closeHistoryDeleteDialog();
        });
        document.getElementById('historyRenameOverlay')?.addEventListener('click', (event) => {
            if (event.target.id === 'historyRenameOverlay') closeHistoryRenameDialog();
        });
        document.getElementById('monitoringOverlay')?.addEventListener('click', (event) => {
            if (event.target.id === 'monitoringOverlay') closeMonitoring();
        });
        document.getElementById('scheduleOverlay')?.addEventListener('click', (event) => {
            if (event.target.id === 'scheduleOverlay') closeSchedules();
        });
        document.getElementById('memoryOverlay')?.addEventListener('click', (event) => {
            if (event.target.id === 'memoryOverlay') closeMemoryManager();
        });
        document.addEventListener('keydown', (event) => {
            if (event.key !== 'Escape') return;
            if (document.getElementById('monitoringOverlay')?.classList.contains('active')) {
                closeMonitoring();
                return;
            }
            if (document.getElementById('scheduleOverlay')?.classList.contains('active')) {
                closeSchedules();
                return;
            }
            if (document.getElementById('memoryOverlay')?.classList.contains('active')) {
                closeMemoryManager();
                return;
            }
            const renameOverlay = document.getElementById('historyRenameOverlay');
            if (renameOverlay?.classList.contains('active')) {
                closeHistoryRenameDialog();
                return;
            }
            const deleteOverlay = document.getElementById('historyDeleteOverlay');
            if (deleteOverlay?.classList.contains('active')) {
                closeHistoryDeleteDialog();
                return;
            }
            closeWorkspacePopovers();
        });

        // Initialize
        initializeTheme();
        resetExecutionTrace();
        refreshWorkspaceMode();
        refreshConversationHistory();
        document.getElementById('userInput').focus();
