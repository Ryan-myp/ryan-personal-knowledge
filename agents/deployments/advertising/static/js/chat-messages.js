        function renderAccountSelection(selection, originalRequest) {
            const section = document.createElement('section');
            section.className = 'message-account-selection';

            const prompt = document.createElement('div');
            prompt.className = 'account-selection-prompt';
            prompt.textContent = selection.prompt || '请选择一个当前身份可用的广告账户。';
            section.appendChild(prompt);

            const options = Array.isArray(selection.account_options)
                ? selection.account_options.slice(0, 20)
                : [];
            if (!options.length) {
                const empty = document.createElement('div');
                empty.className = 'account-selection-empty';
                empty.textContent = '当前身份没有可用于此渠道的授权账户。';
                section.appendChild(empty);
                return section;
            }

            const actions = document.createElement('div');
            actions.className = 'account-selection-options';
            options.forEach(option => {
                if (!option || option.value == null || String(option.value).trim() === '') return;
                const accountId = String(option.value);
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'account-selection-option';
                button.dataset.accountId = accountId;
                button.setAttribute('data-account-id', accountId);
                button.textContent = `使用账户 ${String(option.label || accountId)}`;
                button.disabled = !String(originalRequest?.user_input || '').trim();
                button.addEventListener('click', () => {
                    continueWithSelectedAccount(accountId, originalRequest || {});
                });
                actions.appendChild(button);
            });
            section.appendChild(actions);
            return section;
        }

        function addMessage(content, type = 'agent', tools = null, isError = false, toolSummaryHtml = '', messageTime = null, ui = null, uiOptions = null) {
            if (!toolSummaryHtml && !chatMessageHasPresentation(content, tools, ui)) return null;
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
            if (ui?.account_selection) {
                bodyHtml += '<div class="message-account-selection-host"></div>';
            }
            if (toolSummaryHtml) {
                bodyHtml += toolSummaryHtml;
            } else if (tools && tools.length > 0) {
                bodyHtml += `<div class="tool-results">${tools.map(t => `
                    <span class="tool-tag ${t.success ? 'success' : 'error'}">
                        ${t.success ? '✓' : '✗'} ${escapeHtml(t.tool)}
                    </span>
                `).join('')}</div>`;
            }
            if (ui?.cards?.length) bodyHtml += '<div class="message-ui-cards"></div>';
            if (ui?.confirmation?.payload) {
                bodyHtml += `
                    <div class="message-confirmation-launcher">
                        <span>${escapeHtml(ui.confirmation.payload.question || '本回合需要确认')}</span>
                        <button type="button" class="message-confirmation-button">打开确认</button>
                    </div>
                `;
            }
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
                msg.querySelector('.message-ui-cards').appendChild(
                    renderUiCards(ui, uiOptions || {}),
                );
            }
            if (ui?.account_selection) {
                msg.querySelector('.message-account-selection-host')?.appendChild(
                    renderAccountSelection(
                        ui.account_selection,
                        uiOptions?.originalRequest || null,
                    ),
                );
            }
            const confirmationButton = msg.querySelector('.message-confirmation-button');
            if (confirmationButton && ui?.confirmation?.payload) {
                confirmationButton.addEventListener('click', () => {
                    if (isSending) return;
                    showConfirm(
                        ui.confirmation.payload,
                        ui.confirmation.original_request || null,
                    );
                });
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

        function confirmationCanExecute(payload) {
            if (!['confirm_write', 'confirm_write_plan'].includes(payload?.type)) return false;
            const token = payload.confirmation_token;
            const expires = Date.parse(payload.expires_at || '');
            return typeof token === 'string' && Boolean(token.trim())
                && token !== '<redacted>' && Number.isFinite(expires) && expires > Date.now();
        }

        function confirmationRequestParams(originalRequest, payload, accountId, extraParams) {
            const confirmed = confirmationCanExecute(payload);
            const params = JSON.parse(JSON.stringify(originalRequest.platform_params || {},
                (key, value) => !confirmed && ['selection_tokens', 'selection_token'].includes(key) ? undefined : value));
            const platform = payload.platform || originalRequest.platforms?.[0]
                || (Object.keys(params).length === 1 ? Object.keys(params)[0] : null);
            if (Object.keys(extraParams).length) {
                if (!platform) throw new Error('无法确定补充参数所属渠道，请重新打开创建草稿。');
                params[platform] = { ...(params[platform] || {}), ...extraParams };
            }
            return {
                user_input: originalRequest.user_input,
                session_id: originalRequest.session_id,
                account_id: accountId || originalRequest.account_id || null,
                platform_params: params,
                confirmed,
                confirmation_payload: confirmed ? payload : null,
                creation_blueprint_id: originalRequest.creation_blueprint_id || null,
                creation_blueprint_version: originalRequest.creation_blueprint_version || null,
                creation_template_id: originalRequest.creation_template_id || null,
                execution_mode: workspaceMode.mode,
                ...(originalRequest.tool_allowlist ? { tool_allowlist: [...originalRequest.tool_allowlist] } : {}),
            };
        }

        // Snapshot the exact submitted draft; a later edit needs a new approval.
        function showConfirm(payload, originalRequest = null) {
            // 移除旧的确认卡片
            const oldCard = document.getElementById('confirmCard');
            if (oldCard) oldCard.remove();

            pendingRequest = {
                payload,
                originalRequest: originalRequest ? JSON.parse(JSON.stringify({
                    ...originalRequest,
                    session_id: originalRequest.session_id || payload.session_id || sessionId,
                })) : null,
                mode: originalRequest?.execution_mode || workspaceMode.mode,
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
                        <label for="confirmAccountInput">📱 ${escapeHtml(payload.platform || '平台')} 账户ID</label>
                        <input type="text" id="confirmAccountInput" placeholder="请输入账户ID..." required autofocus>
                    </div>
                `;
            } else if (payload.type === 'ask_params') {
                inputHtml = `
                    <div class="confirm-field">
                        <label for="confirmParamInput">📝 缺失参数: ${escapeHtml(payload.missing.join(', '))}</label>
                        <input type="text" id="confirmParamInput" placeholder="例如: campaign_id=12345" required autofocus>
                    </div>
                `;
            } else if (payload.type === 'confirm_write_plan') {
                const steps = Array.isArray(payload.preview?.steps) ? payload.preview.steps
                    : (payload.tools || []).map(tool => ({ tool }));
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
            if (['confirm_write', 'confirm_write_plan'].includes(payload.type) && !confirmationCanExecute(payload)) {
                inputHtml += '<p role="status">历史确认或过期凭证不能直接执行。请先重新生成计划，再确认本次写入。</p>';
            }

            card.innerHTML = `
                <div class="confirm-card-header">
                    <span class="confirm-icon">⚠️</span>
                    <span class="confirm-title">${escapeHtml(payload.question || '需要确认')}</span>
                </div>
                <div class="confirm-card-body">
                    ${inputHtml}
                </div>
                <div class="confirm-card-footer">
                    <button class="confirm-btn cancel" onclick="cancelConfirm()">取消</button>
                    <button class="confirm-btn confirm" onclick="executeConfirm()">${confirmationCanExecute(payload) ? '确认执行' : ['confirm_write', 'confirm_write_plan'].includes(payload.type) ? '重新生成确认计划' : '补充后继续'}</button>
                </div>
            `;

            // Confirmation is a workbench artifact. Keep the chat transcript
            // focused on conversation and leave the full action surface in
            // the right-side workspace.
            const target = document.getElementById('confirmation-workbench-host')
                || document.getElementById('confirmCardContainer');
            target?.appendChild(card);
            if (typeof openConfirmationWorkbench === 'function') openConfirmationWorkbench();

            // 自动聚焦输入框并滚动到卡片
            setTimeout(() => {
                const input = document.getElementById('confirmAccountInput') || document.getElementById('confirmParamInput');
                if (input) input.focus();
                if (!document.getElementById('creation-workbench-view')?.hidden) {
                    input?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
            }, 100);
        }

        // Cancel confirmation
        function cancelConfirm() {
            pendingRequest = null;
            pendingCreationReview = null;
            const card = document.getElementById('confirmCard');
            if (card) card.remove();
            if (typeof clearWorkbenchConfirmation === 'function') clearWorkbenchConfirmation();
            if (typeof workbenchState !== 'undefined' && workbenchState.activeCardId) {
                reopenCreationCard(workbenchState.activeCardId);
            } else if (typeof closeCreationWorkbench === 'function') closeCreationWorkbench();
            addMessage('❌ 操作已取消', 'agent');
        }

        // Execute confirmation
        async function executeConfirm() {
            if (!pendingRequest || isSending) return;

            const { payload, originalRequest, mode } = pendingRequest;
            if (!originalRequest?.user_input?.trim()) {
                addMessage('这条历史确认缺少原始请求，请重新打开创建草稿生成计划。', 'agent', null, true);
                return;
            }
            if (originalRequest.session_id !== sessionId) {
                addMessage('当前对话已切换，请回到原对话重新打开确认计划。', 'agent', null, true);
                return;
            }
            if (['confirm_write', 'confirm_write_plan'].includes(payload.type)
                && (mode !== workspaceMode.mode || creationSubmissionModeError())) {
                pendingRequest = null;
                document.getElementById('confirmCard')?.remove();
                if (typeof clearWorkbenchConfirmation === 'function') clearWorkbenchConfirmation();
                addMessage('执行模式已变化或当前不可用，请按当前模式重新生成并确认计划。', 'agent', null, true);
                return;
            }

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
            if (payload.type === 'ask_account' && !account_id) {
                addMessage('请先填写要操作的广告账户 ID。', 'agent', null, true);
                return;
            }
            if (payload.type === 'ask_params' && !Object.keys(extra_params).length) {
                addMessage('请先补充计划所需的参数。', 'agent', null, true);
                return;
            }
            pendingRequest = null;

            // 移除卡片
            const card = document.getElementById('confirmCard');
            if (card) card.remove();
            if (typeof clearWorkbenchConfirmation === 'function') clearWorkbenchConfirmation();
            if (typeof workbenchState !== 'undefined' && workbenchState.activeCardId) {
                openCreationWorkbench(workbenchState.cards.get(workbenchState.activeCardId));
            } else if (typeof closeCreationWorkbench === 'function') closeCreationWorkbench();

            // The confirmation is a user action. Keep it as a user message
            // so the transcript does not invent a second Agent turn.
            const authorizing = confirmationCanExecute(payload);
            addMessage(authorizing ? '确认并继续执行' : '补充信息并重新生成确认计划', 'user');
            isSending = true;
            addLoading();
            startExecutionTrace(originalRequest?.user_input || '确认并继续执行');

            // 发送带参数的请求 - 使用原始 user_input
            try {
                const requestParams = confirmationRequestParams(
                    originalRequest, payload, account_id, extra_params,
                );
                const data = await streamChatRequest(requestParams);
                removeLoading();
                renderStreamResult(data, requestParams);
                await refreshConversationHistory({ silent: true });

            } catch (error) {
                removeLoading();
                addMessage(markChatRequestFailure(error), 'agent', null, true);
            } finally {
                isSending = false;
            }
        }

        async function continueWithSelectedAccount(accountId, originalRequest) {
            if (isSending || accountId == null) return;
            const sourceText = String(originalRequest?.user_input || '').trim();
            const selectedId = String(accountId).trim();
            if (!sourceText || !selectedId) return;

            const userInput = `${sourceText}\n使用账户 ${selectedId} 继续`;
            const requestParams = {
                ...(originalRequest || {}),
                user_input: userInput,
                user_id: 'web_user',
                session_id: sessionId,
                account_id: selectedId,
            };
            isSending = true;
            const sendButton = document.getElementById('sendBtn');
            if (sendButton) {
                sendButton.disabled = true;
                sendButton.classList.add('is-sending');
                sendButton.setAttribute('aria-busy', 'true');
            }
            addMessage(userInput, 'user');
            addLoading();
            startExecutionTrace(userInput);
            try {
                const data = await streamChatRequest(requestParams);
                removeLoading();
                renderStreamResult(data, requestParams);
                await refreshConversationHistory({ silent: true });
            } catch (error) {
                removeLoading();
                addMessage(markChatRequestFailure(error), 'agent', null, true);
            } finally {
                isSending = false;
                if (sendButton) {
                    sendButton.disabled = false;
                    sendButton.classList.remove('is-sending');
                    sendButton.removeAttribute('aria-busy');
                }
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
                addMessage(markChatRequestFailure(error), 'agent', null, true);
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
            if (typeof resetCreationWorkbench === 'function') resetCreationWorkbench();
            resetExecutionTrace();
            renderConversationHistory();
            document.getElementById('chatContainer').innerHTML = `
                <div class="welcome-page" id="welcomePage">
                    <div class="welcome-icon">🤖</div>
                    <h1 class="welcome-title">把投放问题，交给一个懂执行的 Agent。</h1>
                    <p class="welcome-desc" id="welcomeModeDescription">从账户查询、效果分析到广告创建，先在安全的 dry-run 环境里看清每一步，再决定是否执行。</p>

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
