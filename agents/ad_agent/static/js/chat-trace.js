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
            traceState = { nodes: [], events: [], selectedId: null, collapsed: false, expanded: false, activeTurn: traceState.activeTurn, traceId: null, status: 'unknown', orderCounter: 0 };
            const preserveCreationWorkbench = typeof workbenchState !== 'undefined'
                && workbenchState.open
                && workbenchState.activeView === 'creation';
            if (preserveCreationWorkbench) {
                setWorkbenchView('creation');
            } else if (typeof closeAgentWorkbench === 'function') {
                closeAgentWorkbench();
            } else {
                document.body.classList.remove('workbench-open', 'trace-collapsed', 'trace-expanded');
                document.querySelector('.right-panel')?.classList.remove('trace-collapsed');
            }
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

        function traceToolIdentity(event) {
            const tool = String(event.tool || event.tool_name || event.name || '').trim();
            const namespace = String(event.platform || event.namespace || tool.split('.')[0] || '').trim();
            const parts = tool.split('.');
            return {
                tool,
                namespace,
                resource_type: event.resource_type || parts[1] || '',
                action: event.action || parts.slice(2).join('.') || parts[1] || '',
            };
        }

        function normalizeExecutionEvent(rawEvent) {
            const raw = rawEvent && typeof rawEvent === 'object' ? rawEvent : {};
            const type = String(raw.type || raw.event_type || '').trim();
            if (!type || !['agent_start', 'agent_end', 'tool_execution_start', 'tool_execution_end', 'turn_start', 'turn_end', 'message_end', 'model_usage'].includes(type)) {
                return { ...raw, type: type || raw.event_type };
            }
            if (type === 'agent_start') {
                return { ...raw, type: 'start', event_type: 'start', status: 'running' };
            }
            if (type === 'agent_end') {
                return {
                    ...raw,
                    type: 'done',
                    event_type: 'done',
                    status: raw.status === 'failed' ? 'failed' : 'succeeded',
                };
            }
            if (type === 'tool_execution_start') {
                const identity = traceToolIdentity(raw);
                return {
                    ...raw,
                    type: 'node_started',
                    event_type: 'node_started',
                    node_id: raw.node_id || `tool:${raw.tool_call_id || identity.tool || traceState.orderCounter + 1}`,
                    tool: identity.tool,
                    platform: identity.namespace,
                    resource_type: identity.resource_type,
                    action: identity.action,
                    status: 'running',
                    safe_input: raw.safe_input !== undefined ? raw.safe_input : raw.arguments,
                };
            }
            if (type === 'tool_execution_end') {
                const identity = traceToolIdentity(raw);
                const failed = Boolean(raw.is_error || raw.result?.is_error);
                return {
                    ...raw,
                    type: 'node_status',
                    event_type: 'node_status',
                    node_id: raw.node_id || `tool:${raw.tool_call_id || identity.tool || ''}`,
                    tool: identity.tool,
                    platform: identity.namespace,
                    resource_type: identity.resource_type,
                    action: identity.action,
                    status: failed ? 'failed' : 'succeeded',
                    safe_output: raw.safe_output !== undefined ? raw.safe_output : raw.result,
                    safe_metadata: {
                        ...(raw.safe_metadata || {}),
                        reason: raw.safe_metadata?.reason || (failed ? 'tool_execution_failed' : 'tool_execution_succeeded'),
                    },
                };
            }
            return raw;
        }

        function shouldOpenTraceForEvent(event) {
            return ['plan', 'stage_started', 'stage_status', 'node_discovered', 'node_started', 'node_status', 'confirmation'].includes(event.type);
        }

        function upsertTraceToolNode(event) {
            const identity = traceToolIdentity(event);
            const id = String(event.node_id || `tool:${event.tool_call_id || identity.tool || traceState.orderCounter + 1}`);
            const existing = traceState.nodes.find(item => item.id === id);
            const node = {
                ...(existing || {}),
                id,
                title: event.title || identity.tool || event.action || 'Tool 节点',
                meta: [identity.namespace, identity.resource_type, identity.action].filter(Boolean).join(' · '),
                kind: identity.namespace || event.platform || 'Tool',
                tool: identity.tool || existing?.tool,
                platform: identity.namespace || event.platform || existing?.platform,
                resource_type: identity.resource_type || existing?.resource_type,
                action: identity.action || existing?.action,
                state: event.status || existing?.state || 'unknown',
                order: existing?.order || (++traceState.orderCounter),
                reason: event.safe_metadata?.reason || existing?.reason,
                duration_ms: event.safe_metadata?.duration_ms || existing?.duration_ms,
                input: event.safe_input !== undefined ? event.safe_input : existing?.input,
                output: event.safe_output !== undefined ? event.safe_output : existing?.output,
            };
            traceState.nodes = traceState.nodes.filter(item => item.id !== id);
            traceState.nodes.push(node);
            return node;
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
            if (!event || !(event.type || event.event_type)) return null;
            event = normalizeExecutionEvent(event);
            if (!event.type) return null;
            const duplicateStart = event.type === 'start' && traceState.events.some(item => item.type === 'start');
            if (shouldOpenTraceForEvent(event) && typeof openAgentWorkbench === 'function') {
                openAgentWorkbench('trace');
            }
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
                const node = upsertTraceToolNode(event);
                if (node) {
                    node.state = event.status || 'unknown';
                    node.title = event.title || node.title;
                    node.meta = [node.platform, node.resource_type, node.action].filter(Boolean).join(' · ');
                    node.reason = event.safe_metadata?.reason || node.reason;
                    node.duration_ms = event.safe_metadata?.duration_ms || node.duration_ms;
                    if (event.safe_input !== undefined) node.input = event.safe_input;
                    if (event.safe_output !== undefined) node.output = event.safe_output;
                    traceState.selectedId = node.state === 'failed' || node.state === 'recovery_required' ? node.id : traceState.selectedId;
                }
                updateTraceHeader(event.status || 'unknown', node ? `${node.tool || node.title} · ${traceStatusLabel(event.status)}` : 'Tool 事件已到达');
            }
            if (event.type === 'done') updateTraceHeader(event.status || 'succeeded', event.status === 'awaiting_confirmation' ? '等待用户确认后继续' : '本回合已完成');
            if (event.type === 'error') updateTraceHeader('failed', '本回合未完成，请查看安全事件');
            if (!duplicateStart) pushTraceEvent(event);
            renderExecutionTrace();
            return event;
        }
