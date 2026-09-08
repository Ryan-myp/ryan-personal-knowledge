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
        };

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
            }
            const keyInput = document.getElementById('knowledgeApiKey');
            if (keyInput && !keyInput.value) keyInput.value = serviceApiKey;
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
            const toggle = document.getElementById('knowledgeComposeToggle');
            if (!composer || !results) return;
            const active = !composer.classList.contains('active');
            composer.classList.toggle('active', active);
            results.classList.toggle('view-hidden', active);
            if (toggle) toggle.textContent = active ? '返回检索' : '写入知识库';
            if (active) document.getElementById('knowledgeTitle')?.focus();
        }

        function showKnowledgeSearchView() {
            const composer = document.getElementById('knowledgeComposer');
            const results = document.getElementById('knowledgeResults');
            const toggle = document.getElementById('knowledgeComposeToggle');
            composer?.classList.remove('active');
            results?.classList.remove('view-hidden');
            if (toggle) toggle.textContent = '写入知识库';
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
            if (!markdown) return '<span class="knowledge-empty">暂无正文</span>';
            let source = escapeHtml(String(markdown));
            const codeBlocks = [];
            source = source.replace(/```(?:[a-zA-Z0-9_-]+)?\n?([\s\S]*?)```/g, (_, code) => {
                const token = `@@KNOWLEDGE_CODE_${codeBlocks.length}@@`;
                codeBlocks.push(`<pre>${code.trim()}</pre>`);
                return token;
            });
            const lines = source.split('\n');
            const output = [];
            let inList = false;
            for (let line of lines) {
                const trimmed = line.trim();
                if (/^[-*]\s+/.test(trimmed)) {
                    if (!inList) { output.push('<ul>'); inList = true; }
                    line = `<li>${trimmed.replace(/^[-*]\s+/, '')}</li>`;
                } else {
                    if (inList) { output.push('</ul>'); inList = false; }
                    if (/^###\s+/.test(trimmed)) line = `<h4>${trimmed.replace(/^###\s+/, '')}</h4>`;
                    else if (/^##\s+/.test(trimmed)) line = `<h3>${trimmed.replace(/^##\s+/, '')}</h3>`;
                    else if (/^#\s+/.test(trimmed)) line = `<h3>${trimmed.replace(/^#\s+/, '')}</h3>`;
                }
                line = line.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
                line = line.replace(/`([^`]+)`/g, '<code>$1</code>');
                line = line.replace(/@@KNOWLEDGE_CODE_(\d+)@@/g, (_, index) => codeBlocks[Number(index)]);
                output.push(line);
            }
            if (inList) output.push('</ul>');
            return output.join('<br>');
        }

        function renderKnowledgeResults(results, summary = '') {
            const container = document.getElementById('knowledgeResults');
            if (!container) return;
            container.replaceChildren();
            if (!results.length) {
                const empty = document.createElement('div');
                empty.className = 'knowledge-empty';
                empty.textContent = '没有匹配的已发布知识。可以换一个关键词或平台。';
                container.appendChild(empty);
                return;
            }
            if (summary) {
                const summaryCard = document.createElement('section');
                summaryCard.className = 'knowledge-summary';
                summaryCard.innerHTML = '<div class="knowledge-summary-label">检索总结</div>';
                const summaryBody = document.createElement('div');
                summaryBody.className = 'knowledge-summary-body';
                // Summary is LLM-generated Markdown too; escape first inside
                // formatKnowledgeMarkdown so formatting cannot introduce HTML.
                summaryBody.innerHTML = formatKnowledgeMarkdown(summary);
                summaryCard.appendChild(summaryBody);
                container.appendChild(summaryCard);
            }
            for (const item of results) {
                const card = document.createElement('article');
                card.className = 'knowledge-result';
                const head = document.createElement('div');
                head.className = 'knowledge-result-head';
                const title = document.createElement('div');
                title.className = 'knowledge-result-title';
                title.textContent = item.title || item.topic || item.document_id || '未命名知识';
                const badge = document.createElement('span');
                badge.className = 'knowledge-result-badge';
                badge.textContent = item.confidence != null ? `可信度 ${Math.round(Number(item.confidence) * 100)}%` : '已发布';
                head.append(title, badge);
                const meta = document.createElement('div');
                meta.className = 'knowledge-result-meta';
                meta.textContent = [item.platform || '通用', item.knowledge_type || item.layer || 'general', item.source_ref || item.source].filter(Boolean).join(' · ');
                const excerpt = document.createElement('div');
                excerpt.className = 'knowledge-result-excerpt';
                excerpt.innerHTML = formatKnowledgeMarkdown(item.excerpt || '暂无正文');
                const details = document.createElement('details');
                details.className = 'knowledge-result-details';
                const detailsSummary = document.createElement('summary');
                detailsSummary.textContent = '查看 Markdown 摘要';
                const fullContent = document.createElement('div');
                fullContent.className = 'knowledge-markdown';
                fullContent.innerHTML = formatKnowledgeMarkdown(item.excerpt || '暂无正文');
                details.append(detailsSummary, fullContent);
                card.append(head, meta, excerpt, details);
                container.appendChild(card);
            }
        }

        async function searchKnowledge() {
            showKnowledgeSearchView();
            const query = document.getElementById('knowledgeQuery')?.value.trim() || '';
            const platform = document.getElementById('knowledgePlatform')?.value || '';
            if (!query) {
                setKnowledgeStatus('请输入要搜索的关键词。', true);
                renderKnowledgeResults([]);
                return;
            }
            const keyInput = document.getElementById('knowledgeApiKey');
            if (keyInput?.value.trim()) serviceApiKey = keyInput.value.trim();
            setKnowledgeStatus('正在检索已发布知识…');
            try {
                const params = new URLSearchParams({ query, limit: '10' });
                if (platform) params.set('platform', platform);
                const response = await authenticatedFetch(`/knowledge/search?${params.toString()}`);
                const text = await response.text();
                let data = {};
                try { data = text ? JSON.parse(text) : {}; } catch (_) { data = {}; }
                if (!response.ok) throw new Error(data.detail || data.error || `知识库请求失败（${response.status}）`);
                const results = Array.isArray(data.results) ? data.results : [];
                renderKnowledgeResults(results, data.summary || '');
                setKnowledgeStatus(`找到 ${results.length} 条已发布知识，已生成业务总结。`);
            } catch (error) {
                renderKnowledgeResults([]);
                setKnowledgeStatus(error.message || '知识库暂时不可用。', true);
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
                const created = await apiFetch('/knowledge/documents', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });
                if (publishNow) {
                    await apiFetch(`/knowledge/documents/${encodeURIComponent(created.document_id)}/publish`, { method: 'POST' });
                    setKnowledgeWriteStatus('已保存并发布；后续检索和 Agent 对话可以使用这份知识。');
                } else {
                    setKnowledgeWriteStatus('已保存为草稿；发布后才会进入检索和 Agent 上下文。');
                }
                if (document.getElementById('knowledgeQuery')?.value.trim()) await searchKnowledge();
                document.getElementById('knowledgeTitle').value = '';
                document.getElementById('knowledgeContent').value = '';
                document.getElementById('knowledgeTags').value = '';
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
                throw new Error(data.detail || data.error || `请求失败（${response.status}）`);
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
                label.textContent = specDescription ? `${name} · ${specDescription}` : name;
                if (spec.required) {
                    const required = document.createElement('span');
                    required.className = 'required';
                    required.textContent = ' *';
                    label.appendChild(required);
                }
                row.appendChild(label);
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
                    control = document.createElement('select');
                    if (spec.type === 'array') control.multiple = true;
                    const empty = document.createElement('option');
                    if (spec.type !== 'array') {
                        empty.value = ''; empty.textContent = spec.required ? '请选择…' : '不设置';
                        control.appendChild(empty);
                    }
                    options.forEach(option => {
                        const item = document.createElement('option');
                        item.value = String(option);
                        item.textContent = spec.option_labels?.[String(option)] || String(option);
                        if (spec.type === 'array' && Array.isArray(current[name]) && current[name].map(String).includes(String(option))) item.selected = true;
                        control.appendChild(item);
                    });
                    if (spec.type !== 'array') control.value = current[name] === undefined ? '' : String(current[name]);
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
                    onChange({ ...current });
                };
                if (!(
                    (spec.type === 'object' && spec.properties && typeof spec.properties === 'object')
                    || (spec.type === 'array' && spec.items?.properties)
                )) {
                    control.addEventListener(control.type === 'checkbox' || control.tagName === 'SELECT' ? 'change' : 'input', commit);
                }
                row.appendChild(control);
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
                const [blueprints, tools] = await Promise.all([
                    apiFetch('/creation-blueprints'),
                    apiFetch('/tools'),
                ]);
                blueprintState.items = Array.isArray(blueprints.blueprints) ? blueprints.blueprints : [];
                blueprintState.tools = Array.isArray(tools.tools) ? tools.tools : [];
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
            if (!blueprintState.items.length) {
                const empty = document.createElement('div');
                empty.className = 'blueprint-empty';
                empty.textContent = '当前还没有可用的广告创建蓝图。';
                list.appendChild(empty);
                return;
            }
            let lastProvider = '';
            for (const item of blueprintState.items) {
                if (item.provider !== lastProvider) {
                    const group = document.createElement('div');
                    group.className = 'blueprint-list-meta';
                    group.textContent = item.provider;
                    list.appendChild(group);
                    lastProvider = item.provider;
                }
                const button = document.createElement('button');
                button.type = 'button';
                button.className = `blueprint-list-item${blueprintState.selected?.id === item.id ? ' active' : ''}`;
                button.onclick = () => selectBlueprint(item.id);
                const title = document.createElement('span');
                title.className = 'blueprint-list-title';
                title.textContent = item.title || item.id;
                const meta = document.createElement('span');
                meta.className = 'blueprint-list-meta';
                meta.textContent = `${item.provider} · ${item.ad_format} · v${item.version}`;
                button.append(title, meta);
                list.appendChild(button);
            }
        }

        function selectBlueprint(blueprintId, selectorValue = null) {
            const item = blueprintState.items.find(value => value.id === blueprintId);
            if (!item) return;
            blueprintState.selected = item;
            blueprintState.values = {};
            blueprintState.previousValues = {};
            blueprintState.evaluation = null;
            blueprintState.localFiles = {};
            blueprintState.selectionTokens = {};
            blueprintState.selectionTokenTools = {};
            blueprintState.lookupOptions = {};
            const selector = item.selector;
            const initialValue = selectorValue || selector?.values?.[0];
            if (selector?.field && initialValue !== undefined) blueprintState.values[selector.field] = initialValue;
            renderBlueprintList();
            renderBlueprintEditor();
            if (selector?.field) evaluateBlueprintDraft(selector.field);
        }

        function renderBlueprintEditor() {
            const blueprint = blueprintState.selected;
            const title = document.getElementById('blueprintEditorTitle');
            const meta = document.getElementById('blueprintEditorMeta');
            if (!blueprint) return;
            if (title) title.textContent = blueprint.title || blueprint.id;
            if (meta) meta.textContent = `${blueprint.provider} · ${blueprint.ad_format} · Blueprint v${blueprint.version}`;
            const accountInput = document.getElementById('blueprintAccountInput');
            if (accountInput) {
                accountInput.value = blueprintState.accountId || '';
                accountInput.oninput = () => {
                    blueprintState.accountId = accountInput.value.trim();
                    refreshLookupAccountState(document.getElementById('blueprintFields'));
                };
            }
            renderBlueprintSelector();
            renderBlueprintFields(blueprintState.evaluation);
        }

        function renderBlueprintFields(evaluation) {
            const container = document.getElementById('blueprintFields');
            const blueprint = blueprintState.selected;
            if (!container || !blueprint) return;
            container.replaceChildren();
            const stateMap = new Map((evaluation?.fields || []).map(item => [item.path, item]));
            for (const field of (blueprint.fields || [])) {
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
                wrapper.className = `blueprint-field${state.visible === false ? ' hidden' : ''}${state.state === 'missing' ? ' missing' : ''}${state.state === 'invalid' ? ' invalid' : ''}`;
                const label = document.createElement('label');
                label.className = 'blueprint-field-label';
                label.textContent = field.label || field.path;
                if (state.required) {
                    const required = document.createElement('span');
                    required.className = 'blueprint-required';
                    required.textContent = '*';
                    label.appendChild(required);
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
                const displayValue = state.value !== undefined && state.value !== null
                    ? state.value : blueprintState.values[field.path];
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
                } else if (schema.type === 'object' || schema.type === 'array' || Array.isArray(schema.type)) {
                    control = document.createElement('textarea');
                    control.placeholder = schema.type === 'array' ? '[...]' : '{...}';
                } else {
                    control = document.createElement('input');
                    control.type = schema.type === 'number' || schema.type === 'integer' ? 'number' : 'text';
                }
                if (field.presentation !== 'asset_picker' && field.presentation !== 'file_reference' && field.presentation !== 'derived_readonly' && schema.type !== 'object') {
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
                container.appendChild(wrapper);
            }
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
                renderBlueprintFields(evaluation);
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
            blueprintState.values = {};
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
                if (field.visible === false || field.value === undefined || field.value === null || field.value === '') return;
                setCreationNestedValue(values, field.provider_field || field.path, field.value);
                // Keep a tool-scoped copy for repeated fields such as name or
                // app_id. The top-level copy remains available to the
                // provider-neutral activation predicates; the authoritative
                // Tool builder uses the scoped value for its own schema.
                if (field.tool) {
                    values[field.tool] = values[field.tool] || {};
                    setCreationNestedValue(values[field.tool], field.provider_field || field.path, field.value);
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
                if (field.value !== undefined && field.value !== null && field.value !== '') values[field.path] = field.value;
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
                if (field.visible === false || !field.required) return;
                const label = field.label || field.path || '参数';
                if (invalidPaths.has(field.path) || field.state === 'invalid') return;
                if (creationCardValueEmpty(field.value) && !pending.includes(label)) pending.push(label);
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
            const requiredFields = (card.fields || []).filter(field => field.visible !== false && field.required);
            const completedFields = requiredFields.filter(field => !creationCardValueEmpty(field.value) && !field.local_error && field.state !== 'invalid' && !(card.invalid_fields || []).includes(field.path)).length;
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
            const submitButton = wrapper.querySelector('[data-creation-action="submit_create"]');
            if (submitButton) submitButton.disabled = !creationCardCanSubmit(card);
        }

        function creationReviewRows(card) {
            return (card.fields || []).filter(field => field.visible !== false && field.value !== undefined && field.value !== null && field.value !== '').slice(0, 80).map(field => {
                const value = field.control === 'text_list' ? presentedLines(field.value)
                    : field.control === 'asset_picker' ? (Array.isArray(field.value) ? field.value.map(item => item?.local_file || item?.name || item?.asset || '已选素材').join('、') : '')
                    : field.control === 'object_editor' ? structuredObjectValueText(field.value)
                    : creationCardValueText(field.value);
                return `<div><span>${escapeHtml(field.label || field.path)}</span><strong>${escapeHtml(value || '已填写')}</strong></div>`;
            }).join('');
        }

        function showCreationPreview(card) {
            const existing = document.querySelector(`.creation-card-review[data-card-review="${CSS.escape(card.id)}"]`);
            if (existing) { existing.remove(); return; }
            const review = document.createElement('div');
            review.className = 'creation-card-review';
            review.dataset.cardReview = card.id;
            review.innerHTML = `<strong>参数预览</strong><div>广告账户：${escapeHtml(card.account_id || '未填写')}</div>${creationReviewRows(card)}<div>这里只是预览，不会产生线上变化；确认后才会继续创建。</div>`;
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
                const invalid = Boolean(field.local_error) || field.state === 'invalid' || (card.invalid_fields || []).includes(field.path);
                item.classList.toggle('missing', field.state === 'missing');
                item.classList.toggle('invalid', invalid);
                item.classList.toggle('hidden', field.visible === false);
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
            wrapper.className = `creation-card ${creationCardStatusKind(card)}`;
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
            wrapper.appendChild(account);

            const progress = creationCardProgress(card);
            const progressBox = document.createElement('div');
            progressBox.className = 'creation-card-progress';
            progressBox.innerHTML = `<div class="creation-card-progress-head"><strong>必填项完成度</strong><span class="creation-card-progress-value">${progress.completed} / ${progress.total} · ${progress.percent}%</span></div><div class="creation-card-progress-track" role="progressbar" aria-label="必填项完成度" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${progress.percent}"><div class="creation-card-progress-bar" style="width:${progress.percent}%"></div></div>`;
            wrapper.appendChild(progressBox);

            const fields = document.createElement('div');
            fields.className = 'creation-card-fields';
            (card.fields || []).forEach(field => {
                const item = document.createElement('div');
                item.dataset.fieldPath = field.path;
                const wideField = ['asset_picker', 'file_reference', 'text_list', 'object_editor', 'json', 'advanced_json'].includes(field.control);
                item.className = `creation-card-field${wideField ? ' wide' : ''}${field.visible === false ? ' hidden' : ''}${field.state === 'missing' ? ' missing' : ''}${field.state === 'invalid' || field.local_error ? ' invalid' : ''}`;
                const label = document.createElement('label');
                label.textContent = field.label || field.path;
                if (field.required) {
                    const required = document.createElement('span');
                    required.className = 'required';
                    required.textContent = '*';
                    label.appendChild(required);
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
                    control = document.createElement('select');
                    if (field.control === 'multiselect') control.multiple = true;
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
                control.dataset.path = field.path;
                const updateValue = () => {
                    if (field.control === 'asset_picker' || field.control === 'file_reference' || field.control === 'derived_readonly') return;
                    let value;
                    if (field.control === 'checkbox') value = control.checked;
                    else if (field.control === 'multiselect') value = Array.from(control.selectedOptions).map(option => option.value);
                    else value = parseCreationCardValue(field, control.value.trim());
                    field.value = value;
                    item.classList.toggle('missing', field.required && (value === undefined || value === null || value === ''));
                    creationCardState.set(card.id, card);
                    scheduleCreationCardEvaluation(card, field.path);
                    const status = wrapper.querySelector('.creation-card-status');
                    updateCreationCardIndicators(wrapper, card);
                };
                if (field.control !== 'asset_picker' && field.control !== 'file_reference' && field.control !== 'derived_readonly' && field.control !== 'object_editor' && field.control !== 'lookup') control.addEventListener('change', updateValue);
                if (field.control === 'text' || field.control === 'text_list' || field.control === 'number' || field.control === 'advanced_json') control.addEventListener('input', updateValue);
                item.appendChild(control);
                const source = document.createElement('div');
                source.className = 'source';
                source.textContent = field.control === 'derived_readonly'
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
                fields.appendChild(item);
            });
            wrapper.appendChild(fields);

            const footer = document.createElement('div');
            footer.className = 'creation-card-footer';
            const status = document.createElement('span');
            status.className = 'creation-card-status';
            status.textContent = creationCardStatus(card);
            footer.appendChild(status);
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
            wrapper.appendChild(footer);
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

            if (ui?.cards?.length) msg.querySelector('.message-ui-cards').appendChild(renderUiCards(ui));

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
            if (!event.target.closest('.global-actions') && !event.target.closest('.workspace-nav') && !event.target.closest('.workspace-popover') && !event.target.closest('.knowledge-overlay') && !event.target.closest('.blueprint-overlay')) {
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
        document.addEventListener('keydown', (event) => {
            if (event.key !== 'Escape') return;
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
