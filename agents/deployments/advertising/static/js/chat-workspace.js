        let scheduleRefreshTimer = null;
        let scheduleRefreshSequence = 0;
        let scheduleActionsPending = new Set();
        let schedulesById = new Map();
        let scheduleRunsById = new Map();
        let scheduleResultSequence = 0;
        let scheduleEditSequence = 0;

        function scheduleDisplayTime(value) {
            const date = new Date(value);
            return value && !Number.isNaN(date.getTime())
                ? date.toLocaleString('zh-CN', {hour12:false}) : '—';
        }

        function scheduleResultText(result, status) {
            const response = result.response || result.message;
            if (typeof response === 'string' && response.trim()) return response;
            const messages = Array.isArray(result.messages) ? result.messages : [];
            const final = [...messages].reverse().find(item => item.role === 'assistant'
                && typeof item.content === 'string' && item.content.trim());
            if (final) return final.content;
            const tools = messages.filter(item => item.role === 'tool').length;
            if (['queued', 'running'].includes(status)) return '任务仍在执行，可刷新查看最新结果。';
            return `本次执行未生成最终文字答复。${tools ? `已保存 ${tools} 条工具执行记录，可在技术详情中查看。` : '请查看执行状态和错误原因。'}`;
        }

        function closeScheduleRun() {
            scheduleResultSequence += 1;
            const panel = document.getElementById('scheduleRunDetail');
            if (panel) panel.hidden = true;
        }

        async function loadScheduleRunResult(run) {
            if (run.task_id) {
                try { return await apiFetch(`/tasks/${encodeURIComponent(run.task_id)}`); }
                catch (error) { if (error.status !== 404) throw error; }
            }
            if (run.result || !run.schedule_id) return run;
            const detail = await apiFetch(`/schedules/${encodeURIComponent(run.schedule_id)}/runs/${encodeURIComponent(run.schedule_run_id)}`);
            return detail.run;
        }

        async function showScheduleRun(runId) {
            const run = scheduleRunsById.get(String(runId));
            if (!run) return;
            const sequence = ++scheduleResultSequence;
            const panel = document.getElementById('scheduleRunDetail');
            const content = document.getElementById('scheduleRunContent');
            const status = document.getElementById('scheduleRunDetailStatus');
            const error = document.getElementById('scheduleRunError');
            const conversation = document.getElementById('scheduleRunConversation');
            panel.hidden = false;
            content.textContent = '正在读取执行结果…';
            error.textContent = '';
            conversation.hidden = true;
            status.textContent = `${scheduleStatusLabel(run.status)} · ${scheduleDisplayTime(run.scheduled_for)}`;
            document.getElementById('scheduleRunTechnical').open = false;
            document.getElementById('scheduleRunRaw').textContent = '';
            try {
                const task = await loadScheduleRunResult(run);
                if (sequence !== scheduleResultSequence) return;
                const result = task.result || run.result || {};
                status.textContent = `${scheduleStatusLabel(task.status || run.status)} · ${scheduleDisplayTime(run.scheduled_for)}`;
                error.textContent = task.error || run.error || '';
                content.innerHTML = formatContent(scheduleResultText(result, task.status || run.status).slice(0, 60000));
                document.getElementById('scheduleRunRaw').textContent = JSON.stringify({task_id:run.task_id, result}, null, 2).slice(0, 60000);
                const sessionId = result.session_id || task.payload?.session_id;
                conversation.hidden = !sessionId;
                conversation.onclick = () => { closeSchedules(); loadConversation(sessionId); };
                document.getElementById('scheduleRunDetailRefresh').onclick = () => showScheduleRun(runId);
            } catch (failure) {
                if (sequence !== scheduleResultSequence) return;
                content.textContent = '执行结果读取失败，请重试。';
                error.textContent = failure.message || '未知错误';
                document.getElementById('scheduleRunDetailRefresh').onclick = () => showScheduleRun(runId);
            }
        }

        function stopScheduleRefresh() {
            scheduleRefreshSequence += 1;
            if (scheduleRefreshTimer) window.clearTimeout(scheduleRefreshTimer);
            scheduleRefreshTimer = null;
        }

        function toggleWorkspaceNavigation() {
            const open = document.body.classList.toggle('navigation-open');
            document.getElementById('workspaceNavigationToggle')?.setAttribute('aria-expanded', String(open));
        }

        function closeWorkspacePopovers() {
            document.body?.classList.remove('navigation-open');
            document.getElementById('workspaceNavigationToggle')?.setAttribute('aria-expanded', 'false');
            if (typeof closeSkillManager === 'function') closeSkillManager();
            if (typeof closeAgentSettings === 'function') closeAgentSettings();
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
            document.getElementById('feedbackTrendOverlay')?.classList.remove('active');
            document.getElementById('feedbackTrendOverlay')?.setAttribute('aria-hidden', 'true');
            if (typeof closeFeedbackTrend === 'function') closeFeedbackTrend();
            document.getElementById('scheduleOverlay')?.classList.remove('active');
            document.getElementById('scheduleOverlay')?.setAttribute('aria-hidden', 'true');
            closeScheduleEditor();
            document.getElementById('memoryOverlay')?.classList.remove('active');
            document.getElementById('memoryOverlay')?.setAttribute('aria-hidden', 'true');
            document.getElementById('mcpOverlay')?.classList.remove('active');
            document.getElementById('mcpOverlay')?.setAttribute('aria-hidden', 'true');
            if (monitoringRefreshTimer) window.clearTimeout(monitoringRefreshTimer);
            monitoringRefreshTimer = null;
            stopScheduleRefresh();
            closeScheduleRun();
        }

        function toggleSystemOpsMenu() {
            const menu = document.getElementById('systemOpsMenu');
            const button = document.getElementById('systemOpsButton');
            if (!menu || !button) return;
            const open = menu.classList.contains('active');
            const navigationOpen = document.body?.classList.contains('navigation-open');
            closeWorkspacePopovers();
            if (!open) {
                if (navigationOpen) {
                    document.body.classList.add('navigation-open');
                    document.getElementById('workspaceNavigationToggle')?.setAttribute('aria-expanded', 'true');
                }
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
            return ({ queued: '排队中', running: '运行中', cancelling: '取消中', paused: '已暂停', succeeded: '已成功', failed: '失败', cancelled: '已取消', skipped: '已跳过', recovery_required: '需恢复' })[status] || status;
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

        let monitoringRecoverySelection = 0;

        function renderMonitoringExperience(experience = {}, recovery = {}) {
            const formatValue = (value, duration) => {
                if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) return '—';
                if (!duration) return value.toLocaleString('zh-CN');
                return value < 1000 ? `${Math.round(value)} ms` : `${(value / 1000).toFixed(1)} s`;
            };
            const rows = [
                ['first_progress_ms', '首次工具进度或文字', true],
                ['first_text_ms', '首次文字', true],
                ['total_ms', '完整回合', true],
                ['model_attempts', '模型调用次数', false],
                ['prompt_chars_peak', '模型消息字符峰值', false],
            ];
            const target = document.getElementById('monitoringExperienceRows');
            if (target) target.innerHTML = rows.map(([key, label, duration]) => {
                const values = experience[key] || {};
                return `<tr><td>${label}</td><td>${formatValue(values.p50, duration)}</td><td>${formatValue(values.p95, duration)}</td><td>${formatValue(values.samples, false)}</td></tr>`;
            }).join('');
            const items = Array.isArray(recovery.items) ? recovery.items.slice(0, 30) : [];
            const list = document.getElementById('monitoringRecoveryRows');
            if (list) {
                list.innerHTML = items.length ? items.map(item => `<tr>
                    <td>${item.kind === 'task' ? '任务' : '回合'}</td>
                    <td title="${escapeHtml(item.id || '')}">${escapeHtml(String(item.id || '—').slice(0, 8))}</td>
                    <td>${escapeHtml(item.reason || '执行结果待核验')}</td>
                    <td><div class="template-row-actions"><button type="button" data-recovery-kind="${escapeHtml(item.kind || '')}" data-recovery-id="${escapeHtml(item.id || '')}">查看记录</button></div></td>
                </tr>`).join('') : '<tr><td colspan="4" class="monitoring-empty">暂无待核验记录</td></tr>';
                list.onclick = event => {
                    const button = event.target.closest('[data-recovery-id]');
                    if (button && list.contains(button)) {
                        inspectMonitoringRecovery(button.dataset.recoveryKind, button.dataset.recoveryId);
                    }
                };
            }
            const total = document.getElementById('monitoringRecoveryTotal');
            if (total) total.textContent = `共 ${Number(recovery.total || 0)} 条${recovery.has_more ? ' · 显示最早 30 条' : ''}`;
        }

        async function inspectMonitoringRecovery(kind, id) {
            if (!['run', 'task'].includes(kind) || typeof id !== 'string' || !id) return;
            const target = document.getElementById('monitoringRecoveryDetail');
            if (!target) return;
            const selection = ++monitoringRecoverySelection;
            target.hidden = false;
            target.textContent = '正在读取执行记录…';
            const endpoint = kind === 'run'
                ? `/runs/${encodeURIComponent(id)}/events?limit=100` : `/tasks/${encodeURIComponent(id)}`;
            try {
                const detail = await apiFetch(endpoint);
                if (selection !== monitoringRecoverySelection) return;
                target.textContent = JSON.stringify(detail, null, 2);
            } catch (error) {
                if (selection === monitoringRecoverySelection) {
                    target.textContent = `记录读取失败：${error.message || '请重试'}`;
                }
            }
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
            renderMonitoringExperience(instance.experience_metrics, snapshot.recovery);
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

        async function fetchServiceReadiness() {
            const response = await serviceFetch('/readyz');
            if (!response.ok && response.status !== 503) {
                throw new Error(`服务健康读取失败（HTTP ${response.status}）`);
            }
            const report = await response.json();
            if (!report || !['ready', 'not_ready'].includes(report.status) || !report.checks) {
                throw new Error('服务健康返回格式不完整，请刷新重试。');
            }
            return report;
        }

        function renderServiceHealth(report) {
            const labels = {
                runtime: 'Agent Runtime', llm: '文本模型配置', tool_registry: 'Tool 注册表',
                supervisor: '后台任务服务', deployment: '部署依赖',
                deployment_health: '部署依赖', persistence: '持久化存储', workers: '后台任务服务',
            };
            document.getElementById('monitoringHealthChecks').innerHTML = Object.entries(report.checks)
                .map(([key, value]) => `<div class="service-health-row"><span>${escapeHtml(labels[key] || key)}</span><strong class="${value === true ? 'ready' : 'not-ready'}">${value === true ? '就绪' : value === false ? '未就绪' : '未知'}</strong></div>`).join('');
            monitoringSetStatus(report.status === 'ready' ? 'healthy' : 'critical', report.status === 'ready'
                ? '服务已就绪，可以接收请求' : '服务尚未就绪，请检查下方未通过的项目');
            document.getElementById('monitoringUpdated').textContent = `更新于 ${new Date().toLocaleTimeString('zh-CN')}`;
        }

        async function loadMonitoring(schedule = false) {
            if (monitoringRefreshTimer) window.clearTimeout(monitoringRefreshTimer);
            monitoringRefreshTimer = null;
            const token = ++monitoringRequestToken;
            if (!document.getElementById('monitoringOverlay')?.classList.contains('active')) return;
            try {
                const health = document.getElementById('monitoringOverlay').dataset.monitoringView === 'health';
                const snapshot = await (health ? fetchServiceReadiness() : apiFetch('/monitoring/overview'));
                if (token !== monitoringRequestToken || !document.getElementById('monitoringOverlay')?.classList.contains('active')) return;
                if (health) renderServiceHealth(snapshot);
                else renderMonitoring(snapshot);
            } catch (error) {
                if (token !== monitoringRequestToken) return;
                const message = error?.status === 404
                    ? '当前服务进程尚未加载监控接口（404）。请重启 ad-agent 服务后再刷新。'
                    : error?.status === 401 || error?.status === 403
                        ? '当前共享服务身份没有读取系统运维数据的权限。'
                        : error?.message || '监控数据读取失败';
                monitoringSetStatus('critical', message);
                document.getElementById('monitoringUpdated').textContent = '读取失败';
            } finally {
                if (schedule && token === monitoringRequestToken && document.getElementById('monitoringOverlay')?.classList.contains('active')) {
                    monitoringRefreshTimer = window.setTimeout(() => loadMonitoring(true), 15000);
                }
            }
        }

        function openMonitoring(view = 'overview') {
            closeWorkspacePopovers();
            const overlay = document.getElementById('monitoringOverlay');
            if (!overlay) return;
            const titles = {overview: '运行监控', health: '服务健康', events: '事件投递'};
            const selectedView = titles[view] ? view : 'overview';
            overlay.dataset.monitoringView = selectedView;
            document.getElementById('monitoringConsoleTitle').textContent = titles[selectedView];
            for (const name of Object.keys(titles)) {
                document.getElementById(`monitoringTab-${name}`)?.setAttribute('aria-pressed', String(name === selectedView));
            }
            monitoringSetStatus('loading', '正在读取最新状态…');
            document.getElementById('monitoringHealthChecks').textContent = '正在检查服务依赖…';
            overlay.classList.add('active');
            overlay.setAttribute('aria-hidden', 'false');
            loadMonitoring(true);
        }

        function closeMonitoring() {
            monitoringRequestToken++;
            monitoringRecoverySelection++;
            document.getElementById('monitoringOverlay')?.classList.remove('active');
            document.getElementById('monitoringOverlay')?.setAttribute('aria-hidden', 'true');
            if (monitoringRefreshTimer) window.clearTimeout(monitoringRefreshTimer);
            monitoringRefreshTimer = null;
        }

        function scheduleStatusLabel(status) {
            return ({
                active: '已启用', paused: '已暂停', disabled: '已停用',
                queued: '排队中', running: '执行中', succeeded: '成功',
                failed: '失败', partially_failed: '部分失败',
                awaiting_input: '等待补充', recovery_required: '需核实',
                cancelled: '已取消', skipped: '已跳过',
            })[status] || status || '—';
        }

        async function scheduleAction(scheduleId, action, button = null) {
            const labels = { pause: '暂停', resume: '恢复', delete: '删除', 'run-now': '立即执行' };
            if (action === 'delete' && !window.confirm('确认删除这个定时任务？历史执行记录也会被一并删除。')) return;
            if (action === 'run-now' && (scheduleActionsPending.has(scheduleId) || button?.disabled)) return;
            const originalLabel = button?.textContent || labels[action] || '操作';
            if (action === 'run-now') {
                scheduleActionsPending.add(scheduleId);
                if (button) {
                    button.disabled = true;
                    button.textContent = '提交中…';
                    button.setAttribute('aria-busy', 'true');
                }
            }
            try {
                const endpoint = action === 'delete'
                    ? `/schedules/${encodeURIComponent(scheduleId)}`
                    : `/schedules/${encodeURIComponent(scheduleId)}/${action}`;
                await apiFetch(endpoint, { method: action === 'delete' ? 'DELETE' : 'POST' });
                if (action === 'delete' && schedulePages.selectedId === scheduleId) await showScheduleList();
                else await loadSchedules();
            } catch (error) { window.alert(`${labels[action] || '操作'}失败：${error.message || '请稍后重试'}`); }
            finally {
                if (action === 'run-now') {
                    scheduleActionsPending.delete(scheduleId);
                    if (button?.isConnected) {
                        button.disabled = false;
                        button.textContent = originalLabel;
                        button.removeAttribute('aria-busy');
                    }
                }
            }
        }

        async function editSchedule(scheduleId) {
            const sequence = ++scheduleEditSequence;
            let schedule = schedulesById.get(String(scheduleId || ''));
            if (!schedule) return;
            if (typeof schedule.prompt !== 'string') {
                try {
                    schedule = (await apiFetch(`/schedules/${encodeURIComponent(scheduleId)}?include_runs=false`)).schedule;
                } catch (error) {
                    if (sequence === scheduleEditSequence) window.alert(`任务读取失败：${error.message || '请重试'}`);
                    return;
                }
            }
            if (!schedule || sequence !== scheduleEditSequence) return;
            document.getElementById('scheduleEditId').value = schedule.schedule_id || '';
            document.getElementById('scheduleEditName').value = schedule.name || '';
            document.getElementById('scheduleEditPrompt').value = schedule.prompt || '';
            document.getElementById('scheduleEditCron').value = schedule.cron_expression || '';
            document.getElementById('scheduleEditTimezone').value = schedule.timezone || 'Asia/Shanghai';
            document.getElementById('scheduleEditStatus').textContent = '';
            const overlay = document.getElementById('scheduleEditOverlay');
            overlay?.classList.add('active');
            overlay?.setAttribute('aria-hidden', 'false');
            document.getElementById('scheduleEditName')?.focus();
        }

        function closeScheduleEditor() {
            scheduleEditSequence += 1;
            const overlay = document.getElementById('scheduleEditOverlay');
            overlay?.classList.remove('active');
            overlay?.setAttribute('aria-hidden', 'true');
            const status = document.getElementById('scheduleEditStatus');
            if (status) status.textContent = '';
        }

        async function saveScheduleEdit(event) {
            event?.preventDefault?.();
            const scheduleId = String(
                document.getElementById('scheduleEditId')?.value || '',
            ).trim();
            const submit = document.getElementById('scheduleEditSubmit');
            const status = document.getElementById('scheduleEditStatus');
            if (!scheduleId || !submit || !status || submit.disabled) return;
            submit.disabled = true;
            status.textContent = '正在保存…';
            try {
                await apiFetch(`/schedules/${encodeURIComponent(scheduleId)}`, {
                    method: 'PATCH',
                    body: JSON.stringify({
                        name: document.getElementById('scheduleEditName').value,
                        prompt: document.getElementById('scheduleEditPrompt').value,
                        cron_expression: document.getElementById('scheduleEditCron').value,
                        timezone: document.getElementById('scheduleEditTimezone').value,
                    }),
                });
                closeScheduleEditor();
                await loadSchedules();
            } catch (error) {
                status.textContent = error.message || '保存失败，请稍后重试。';
            } finally {
                submit.disabled = false;
            }
        }

        function openSchedules() {
            closeWorkspacePopovers();
            const overlay = document.getElementById('scheduleOverlay');
            if (!overlay) return;
            overlay.classList.add('active'); overlay.setAttribute('aria-hidden', 'false');
            showScheduleList();
        }

        function closeSchedules() {
            closeScheduleRun();
            closeScheduleEditor();
            document.getElementById('scheduleOverlay')?.classList.remove('active');
            document.getElementById('scheduleOverlay')?.setAttribute('aria-hidden', 'true');
            stopScheduleRefresh();
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
                const rect = button?.getBoundingClientRect();
                if (rect) {
                    const width = Math.min(380, window.innerWidth - 24);
                    popover.style.width = `${width}px`;
                    popover.style.left = `${Math.max(12, Math.min(rect.left, window.innerWidth - width - 12))}px`;
                    popover.style.right = 'auto';
                    popover.style.top = popoverId === 'modePopover' ? 'auto' : `${rect.bottom + 8}px`;
                    popover.style.bottom = popoverId === 'modePopover' ? `${window.innerHeight - rect.top + 8}px` : 'auto';
                }
            }
        }

        function renderWorkspaceMode() {
            if (typeof refreshCreationSubmissionAvailability === 'function') refreshCreationSubmissionAvailability();
            const title = document.getElementById('workspaceModeTitle');
            const description = document.getElementById('workspaceModeDescription');
            if (!title || !description) return;
            const toggleLabel = document.getElementById('modeToggleLabel');
            const toggleIcon = document.getElementById('modeToggleIcon');
            const select = document.getElementById('executionModeSelect');
            const liveSelected = workspaceMode.mode === 'live';
            const liveAvailable = Boolean(workspaceMode.liveAvailable);
            const liveExecutable = liveSelected && liveAvailable;
            if (workspaceMode.loading) {
                title.textContent = '正在读取服务模式…';
                description.textContent = '正在读取当前 Runtime 的执行策略。';
                if (select) select.disabled = true;
                return;
            }
            if (liveExecutable) {
                title.textContent = 'live 模式 · 受控执行';
                description.textContent = '受控写入；仍需权限、测试账户白名单和二次确认。';
                if (toggleLabel) toggleLabel.textContent = 'live';
                if (toggleIcon) toggleIcon.textContent = '●';
            } else if (liveSelected && !workspaceMode.liveAvailable) {
                const reason = workspaceMode.liveReason || '服务端未开放 live 写入';
                title.textContent = 'live 模式 · 当前不可用';
                description.textContent =
                    `live 写入当前不可用：${reason}。服务端执行门禁仍然有效，请切换到 dry-run 预览。`;
                if (toggleLabel) toggleLabel.textContent = 'live · 不可用';
                if (toggleIcon) toggleIcon.textContent = '⚠';
            } else {
                title.textContent = 'dry-run 模式 · 安全预览';
                description.textContent = '只生成计划与预览，不修改线上广告账户。';
                if (toggleLabel) toggleLabel.textContent = 'dry-run';
                if (toggleIcon) toggleIcon.textContent = '◈';
            }
            const blueprintModeBadge = document.querySelector('.blueprint-dry-run-badge');
            if (blueprintModeBadge) {
                blueprintModeBadge.textContent = liveExecutable
                    ? 'LIVE · 确认后提交'
                    : liveSelected ? 'LIVE 不可用' : 'DRY-RUN';
                blueprintModeBadge.classList.toggle('live', liveExecutable);
            }
            if (select) {
                select.disabled = workspaceMode.saving;
                // Keep the user's selection visible while the request is in
                // flight. On failure applyWorkspaceMode explicitly restores
                // the last server-confirmed mode.
                if (!workspaceMode.saving && select.value !== workspaceMode.mode) {
                    select.value = workspaceMode.mode || 'dry_run';
                }
                const liveOption = select.querySelector('option[value="live"]');
                if (liveOption) {
                    liveOption.disabled = !liveAvailable;
                    liveOption.textContent = liveAvailable
                        ? 'live · 受控执行'
                        : 'live · 不可用';
                    liveOption.title = liveAvailable ? '' : (workspaceMode.liveReason || 'live 当前不可用');
                }
            }
            const traceMode = document.getElementById('traceMode');
            if (traceMode) {
                traceMode.textContent = liveExecutable
                    ? 'live · 受控执行，写操作需确认'
                    : liveSelected
                        ? `live 不可用 · ${workspaceMode.liveReason || '服务端写入门禁未开放'}`
                        : 'dry-run · 不调用线上写 API';
            }
        }

        async function refreshWorkspaceMode() {
            workspaceMode.loading = true;
            renderWorkspaceMode();
            try {
                const response = await serviceFetch('/settings/execution-mode');
                const text = await response.text();
                let data = {};
                try { data = text ? JSON.parse(text) : {}; } catch (_) { data = {}; }
                if (!response.ok) throw new Error(data.detail || data.error || `读取失败（${response.status}）`);
                workspaceMode.mode = data.mode || 'dry_run';
                workspaceMode.liveAvailable = Boolean(data.live_mode_available);
                workspaceMode.liveReason = data.live_mode_reason || '';
                syncMCPExecutionMode(workspaceMode.mode);
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

        function handleWorkspaceModeChange() {
            clearWorkspaceModeStatus();
            const select = document.getElementById('executionModeSelect');
            if (!select || select.value === workspaceMode.mode || workspaceMode.saving) return;
            if (select.value === 'live' && !workspaceMode.liveAvailable) {
                select.value = workspaceMode.mode || 'dry_run';
                const status = document.getElementById('workspaceModeStatus');
                if (status) {
                    status.textContent = workspaceMode.liveReason || '服务端当前未开放 live 写入';
                    status.className = 'workspace-mode-status warning';
                }
                return;
            }
            // The select is the action: changing it persists the scoped mode
            // immediately, so the next run uses the new policy without a
            // second confirmation click.
            applyWorkspaceMode();
        }

        async function applyWorkspaceMode() {
            const select = document.getElementById('executionModeSelect');
            const status = document.getElementById('workspaceModeStatus');
            const mode = select?.value || 'dry_run';
            workspaceMode.saving = true;
            clearWorkspaceModeStatus();
            renderWorkspaceMode();
            try {
                const response = await serviceFetch('/settings/execution-mode', {
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
                syncMCPExecutionMode(workspaceMode.mode);
                if (status) {
                    status.textContent = data.message || '已切换当前会话模式，无需重启服务';
                    status.className = 'workspace-mode-status success';
                }
            } catch (error) {
                if (select) select.value = workspaceMode.mode || 'dry_run';
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
                showResourceList('knowledge');
                if (!knowledgeState.items.length) loadKnowledgeCatalog();
                loadManagedKnowledgeDocuments();
                loadKnowledgeSemanticIndexStatus();
            }
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
