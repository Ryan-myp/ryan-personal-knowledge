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

