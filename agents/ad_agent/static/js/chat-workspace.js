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

