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
            if (!event.target.closest('.global-actions') && !event.target.closest('.workspace-nav') && !event.target.closest('.workspace-popover') && !event.target.closest('.knowledge-overlay') && !event.target.closest('.blueprint-overlay') && !event.target.closest('.monitoring-overlay') && !event.target.closest('#scheduleOverlay') && !event.target.closest('#memoryOverlay') && !event.target.closest('.mcp-overlay') && !event.target.closest('.system-ops-wrap')) {
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
        document.getElementById('mcpOverlay')?.addEventListener('click', (event) => {
            if (event.target === event.currentTarget) closeMCPManager();
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
            if (document.getElementById('mcpOverlay')?.classList.contains('active')) {
                closeMCPManager();
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
