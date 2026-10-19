        function chatMessageHasPresentation(content, tools, ui, attachments) {
            return Boolean(
                String(content ?? '').trim() || tools?.length || ui?.cards?.length
                || ui?.account_selection || ui?.confirmation?.payload
                || ui?.clarification?.options?.length || ui?.clarification?.fields?.length
                || ui?.media_gallery?.length || attachments?.length
            );
        }

        async function streamChatRequest(requestParams) {
            const response = await serviceFetch('/chat/stream', {
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

        function isChatTransportFailure(error) {
            return error instanceof TypeError
                || /failed to fetch|load failed|networkerror|network request failed/i
                    .test(String(error?.message || error || ''));
        }

        function chatRequestFailureMessage(error) {
            if (isChatTransportFailure(error)) {
                return '连接中断，暂时无法确认本次执行结果。请先查看最新执行轨迹；创建或更新操作不要直接重试，以免重复提交。';
            }
            return `请求失败：${String(error?.message || error || '请稍后重试。')}`;
        }

        function markChatRequestFailure(error) {
            if (isChatTransportFailure(error)) markTraceConnectionUnknown();
            else markTraceFailed(error?.message || '');
            return chatRequestFailureMessage(error);
        }

        function streamResultFallback(data) {
            const accountPrompt = data.ui?.account_selection?.prompt;
            if (accountPrompt) return accountPrompt;

            const clarification = data.ui?.clarification;
            if (clarification?.question) return clarification.question;

            if (data.ui?.cards?.length) {
                return '已打开广告创建草稿，尚未提交。请在卡片中补充标记项后继续。';
            }

            if (data.status === 'failed') return '本次处理未完成，请查看执行轨迹中的失败步骤。';
            if (data.status === 'recovery_required') {
                return '本次处理需要核实后恢复，请先查看执行轨迹，不要重复提交。';
            }
            if (data.status === 'unknown') return '本次处理状态暂时无法确认，请先检查执行记录。';
            if (data.status === 'awaiting_input') return '还需要补充一项信息才能继续。';
            return '本回合没有返回文字说明，请查看右侧的实际执行状态。';
        }

        function renderStreamResult(data, requestParams) {
            sessionId = data.session_id || sessionId;
            selectedConversationId = sessionId;
            const results = data.results || [];
            const runFailed = ['failed', 'partially_failed', 'recovery_required', 'unknown', 'cancelled']
                .includes(String(data.status || '').toLowerCase());
            const creationNeedsCorrection = data.response_source === 'creation_card' || data.response_source === 'creation_validation';
            const hasCreationCards = Boolean(data.ui?.cards?.length) && (!requestParams?.creation_blueprint_id || creationNeedsCorrection);
            let ui = data.ui || null;
            let confirmationRequest = null;
            if (data.confirmation_payload) {
                confirmationRequest = {
                    ...(ui?.confirmation?.original_request || {}),
                    ...(requestParams || {}),
                    session_id: requestParams?.session_id || data.session_id || sessionId,
                    execution_mode: requestParams?.execution_mode || workspaceMode.mode,
                };
                ui = {
                    ...(ui || {}),
                    confirmation: {
                        payload: data.confirmation_payload,
                        original_request: confirmationRequest,
                    },
                };
            }
            if (!runFailed && data.needs_confirmation && data.confirmation_payload && !hasCreationCards) {
                addMessage(
                    data.content || streamResultFallback(data),
                    'agent',
                    results.map(item => ({ tool: item.tool, success: item.success })),
                    false,
                    '',
                    null,
                    ui,
                    { originalRequest: requestParams },
                );
                showConfirm(data.confirmation_payload, confirmationRequest);
                return;
            }
            const tools = results.map(item => ({ tool: item.tool, success: item.success }));
            const content = String(data.content || '').trim() || streamResultFallback(data);
            addMessage(
                content,
                'agent',
                tools,
                runFailed,
                '',
                null,
                ui,
                { originalRequest: requestParams },
            );
            const awaitingInteraction = data.status === 'awaiting_input'
                || data.needs_confirmation
                || ui?.confirmation?.payload
                || ui?.clarification
                || ui?.account_selection;
            if (
                !runFailed
                && !data.ui?.cards?.length
                && !awaitingInteraction
                && !pendingCreationReview
                && !pendingRequest
                && typeof clearCreationWorkbenchDraft === 'function'
            ) {
                clearCreationWorkbenchDraft();
            }
        }

        function requestHeaders(extra = {}) {
            const headers = new Headers(extra);
            headers.delete('X-API-Key');
            return headers;
        }

        async function serviceFetch(url, options = {}) {
            return fetch(url, {
                ...options,
                headers: requestHeaders(options.headers || {}),
            });
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
            updateConversationListPagination();
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
                    preview.textContent = markdownPreview(conversation.preview) || '暂无消息预览';
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
            conversationHistoryListPage = {
                nextCursor: null, hasMore: false, loading: false, error: '',
            };
            updateConversationListPagination();
            if (!silent) {
                const status = document.getElementById('chatHistoryStatus');
                if (status) status.textContent = '正在加载历史对话…';
            }
            try {
                const response = await serviceFetch('/sessions?limit=50');
                const text = await response.text();
                let data = {};
                try { data = text ? JSON.parse(text) : {}; } catch (_) { data = {}; }
                if (!response.ok) throw new Error(data.detail || data.error || `历史对话加载失败（${response.status}）`);
                if (requestId !== conversationHistoryRequest) return;
                conversationHistory = Array.isArray(data.sessions) ? data.sessions : [];
                conversationHistoryListPage.nextCursor = data.next_cursor || null;
                conversationHistoryListPage.hasMore = Boolean(
                    data.has_more && conversationHistoryListPage.nextCursor,
                );
                renderConversationHistory();
                updateConversationListPagination();
            } catch (error) {
                if (requestId !== conversationHistoryRequest) return;
                conversationHistory = [];
                conversationHistoryListPage.error = '历史对话暂时不可用，请稍后重试。';
                const message = error?.message || '';
                const status = /401|403|授权/i.test(message)
                    ? '历史对话暂不可用，请检查当前共享服务身份的访问权限。'
                    : '历史对话暂时不可用，请稍后重试。';
                const container = document.getElementById('chatHistory');
                if (container) {
                    container.replaceChildren();
                    const errorNode = document.createElement('div');
                    errorNode.className = 'chat-history-status error';
                    errorNode.textContent = status;
                    container.appendChild(errorNode);
                }
                updateConversationListPagination(conversationHistoryListPage.error);
            }
        }

        function updateConversationListPagination(errorMessage = '') {
            const page = conversationHistoryListPage;
            const panel = document.getElementById('conversationListPagination');
            const button = document.getElementById('loadOlderConversationSessions');
            const status = document.getElementById('conversationListPaginationStatus');
            if (!panel || !button || !status) return;
            panel.hidden = !page.hasMore && !page.loading && !errorMessage;
            button.disabled = page.loading || !page.hasMore;
            button.textContent = page.loading ? '正在加载…' : '加载更早的对话';
            status.textContent = errorMessage || (page.loading ? '正在读取更早的对话…' : '');
        }

        async function loadMoreConversationSessions() {
            const page = conversationHistoryListPage;
            const cursor = page.nextCursor;
            if (page.loading || !page.hasMore || !cursor) return;
            const requestId = conversationHistoryRequest;
            page.loading = true;
            page.error = '';
            updateConversationListPagination();
            try {
                const query = new URLSearchParams({
                    limit: '50',
                    before_updated_at: cursor.updated_at,
                    before_session_id: cursor.session_id,
                });
                const response = await serviceFetch(`/sessions?${query.toString()}`);
                const text = await response.text();
                let data = {};
                try { data = text ? JSON.parse(text) : {}; } catch (_) { data = {}; }
                if (!response.ok) {
                    throw new Error(data.detail || data.error || `历史对话加载失败（${response.status}）`);
                }
                if (requestId !== conversationHistoryRequest || page !== conversationHistoryListPage) {
                    return;
                }
                const knownSessionIds = new Set(
                    conversationHistory.map(item => String(item.session_id || '')),
                );
                for (const session of Array.isArray(data.sessions) ? data.sessions : []) {
                    const sessionId = String(session.session_id || '');
                    if (sessionId && !knownSessionIds.has(sessionId)) {
                        knownSessionIds.add(sessionId);
                        conversationHistory.push(session);
                    }
                }
                page.nextCursor = data.next_cursor || null;
                page.hasMore = Boolean(data.has_more && page.nextCursor);
                renderConversationHistory();
            } catch (error) {
                if (requestId === conversationHistoryRequest && page === conversationHistoryListPage) {
                    page.error = error?.message || '历史对话加载失败，请重试。';
                }
            } finally {
                if (requestId === conversationHistoryRequest && page === conversationHistoryListPage) {
                    page.loading = false;
                    updateConversationListPagination(page.error);
                }
            }
        }

        async function loadConversation(targetSessionId) {
            if (!targetSessionId) return;
            const requestSequence = ++conversationLoadSequence;
            try {
                const response = await serviceFetch(
                    `/sessions/${encodeURIComponent(targetSessionId)}?limit=10`,
                );
                const text = await response.text();
                let data = {};
                try { data = text ? JSON.parse(text) : {}; } catch (_) { data = {}; }
                if (!response.ok) throw new Error(data.detail || data.error || `对话加载失败（${response.status}）`);
                if (requestSequence !== conversationLoadSequence) return;
                clearPendingChatMedia({ revoke: true });
                sessionId = data.session_id || targetSessionId;
                selectedConversationId = sessionId;
                conversationHistoryPage = {
                    sessionId,
                    nextCursor: data.next_cursor || null,
                    hasMore: Boolean(data.has_more && data.next_cursor),
                    loading: false,
                    generation: requestSequence,
                };
                loadedConversationTurnIds.clear();
                for (const message of (Array.isArray(data.messages) ? data.messages : [])) {
                    if (message.turn_id) loadedConversationTurnIds.add(message.turn_id);
                }
                pendingRequest = null;
                document.getElementById('confirmCard')?.remove();
                if (typeof resetCreationWorkbench === 'function') resetCreationWorkbench();
                const container = document.getElementById('chatContainer');
                container.replaceChildren();
                renderConversationHistoryMessages(data.messages, { position: 'append' });
                if (!data.messages?.length) {
                    const empty = document.createElement('div');
                    empty.className = 'chat-history-empty';
                    empty.textContent = conversationHistoryPage.hasMore
                        ? '当前页没有可展示的消息，可继续加载更早的历史。'
                        : '这个对话还没有可展示的消息。';
                    container.appendChild(empty);
                }
                updateConversationHistoryPagination();
                const chatArea = document.getElementById('chatArea');
                if (chatArea) {
                    const previousBehavior = chatArea.style?.scrollBehavior;
                    if (chatArea.style) chatArea.style.scrollBehavior = 'auto';
                    chatArea.scrollTop = chatArea.scrollHeight;
                    if (chatArea.style) chatArea.style.scrollBehavior = previousBehavior || '';
                }
                restoreExecutionTrace(data.execution_traces);
                await loadLatestDurableRun(sessionId);
                if (requestSequence !== conversationLoadSequence) return;
                renderConversationHistory();
            } catch (error) {
                if (requestSequence !== conversationLoadSequence) return;
                addMessage(error?.message || '对话加载失败，请稍后重试。', 'agent', null, true);
            }
        }

        function renderConversationHistoryMessages(messages, { position = 'append' } = {}) {
            const container = document.getElementById('chatContainer');
            if (!container) return 0;
            if (position === 'prepend') {
                container.querySelector?.('.chat-history-empty')?.remove();
            }
            const insertBefore = position === 'prepend' ? container.firstChild : null;
            let precedingUserInput = '';
            let rendered = 0;
            for (const message of Array.isArray(messages) ? messages : []) {
                if (message.turn_id) loadedConversationTurnIds.add(message.turn_id);
                if (!['user', 'assistant'].includes(message.role)) continue;
                if (!chatMessageHasPresentation(
                    message.content, message.tools, message.ui, message.attachments,
                )) continue;
                const role = message.role === 'user' ? 'user' : 'agent';
                if (role === 'user') precedingUserInput = String(message.content || '');
                addMessage(
                    message.content || '',
                    role,
                    message.tools || null,
                    Boolean(message.is_error),
                    '',
                    message.created_at,
                    message.ui || null,
                    {
                        openWorkbench: false,
                        suppressScroll: true,
                        ...(insertBefore ? { insertBefore } : {}),
                        attachments: message.attachments || [],
                        originalRequest: role === 'agent' && precedingUserInput
                            ? { user_input: precedingUserInput, session_id: sessionId }
                            : null,
                    },
                );
                rendered += 1;
            }
            return rendered;
        }

        function updateConversationHistoryPagination(errorMessage = '') {
            const page = conversationHistoryPage;
            const panel = document.getElementById('conversationHistoryPagination');
            const button = document.getElementById('loadOlderConversationButton');
            const status = document.getElementById('conversationHistoryPaginationStatus');
            if (!panel || !button || !status) return;
            panel.hidden = !page.hasMore && !page.loading && !errorMessage;
            button.disabled = page.loading || !page.hasMore;
            button.textContent = page.loading ? '正在加载…' : '加载更早的消息';
            status.textContent = errorMessage || (page.loading ? '正在读取更早的消息…' : '');
        }

        async function loadOlderConversationMessages() {
            const page = conversationHistoryPage;
            if (
                !page.hasMore || page.loading || !page.sessionId || !page.nextCursor
                || page.sessionId !== sessionId
            ) return;
            const generation = page.generation;
            const cursor = page.nextCursor;
            const chatArea = document.getElementById('chatArea');
            const container = document.getElementById('chatContainer');
            if (!chatArea || !container) return;
            const previousHeight = chatArea.scrollHeight;
            const previousTop = chatArea.scrollTop;
            page.loading = true;
            let failureMessage = '';
            updateConversationHistoryPagination();
            try {
                const query = new URLSearchParams({
                    limit: '10',
                    before_message_id: cursor,
                });
                const response = await serviceFetch(
                    `/sessions/${encodeURIComponent(page.sessionId)}?${query.toString()}`,
                );
                const text = await response.text();
                let data = {};
                try { data = text ? JSON.parse(text) : {}; } catch (_) { data = {}; }
                if (!response.ok) {
                    throw new Error(data.detail || data.error || `历史消息加载失败（${response.status}）`);
                }
                if (
                    generation !== conversationLoadSequence
                    || page !== conversationHistoryPage
                    || sessionId !== page.sessionId
                ) return;
                renderConversationHistoryMessages(data.messages, { position: 'prepend' });
                page.nextCursor = data.next_cursor || null;
                page.hasMore = Boolean(data.has_more && page.nextCursor);
                const previousBehavior = chatArea.style?.scrollBehavior;
                if (chatArea.style) chatArea.style.scrollBehavior = 'auto';
                chatArea.scrollTop = previousTop + chatArea.scrollHeight - previousHeight;
                if (chatArea.style) chatArea.style.scrollBehavior = previousBehavior || '';
            } catch (error) {
                if (generation === conversationLoadSequence && page === conversationHistoryPage) {
                    failureMessage = error?.message || '历史消息加载失败，请重试。';
                }
            } finally {
                if (generation === conversationLoadSequence && page === conversationHistoryPage) {
                    page.loading = false;
                    updateConversationHistoryPagination(failureMessage);
                }
            }
        }

        async function apiFetch(url, options = {}) {
            const response = await serviceFetch(url, options);
            const text = await response.text();
            let data = {};
            try { data = text ? JSON.parse(text) : {}; } catch (_) { data = { detail: text }; }
            if (!response.ok) {
                if (response.status === 401 || response.status === 403) {
                    showSkillNotice('当前共享服务身份没有执行此操作的权限。', true);
                }
                const error = new Error(data.detail || data.error || `请求失败（${response.status}）`);
                error.status = response.status;
                throw error;
            }
            return data;
        }

        function bindConversationHistoryPagination() {
            const chatArea = document.getElementById('chatArea');
            const button = document.getElementById('loadOlderConversationButton');
            const sessionButton = document.getElementById('loadOlderConversationSessions');
            sessionButton?.addEventListener('click', () => loadMoreConversationSessions());
            if (!chatArea || !button) return;
            button.addEventListener('click', () => {
                return loadOlderConversationMessages();
            });
            chatArea.addEventListener('scroll', () => {
                if (chatArea.scrollTop <= 56) {
                    return loadOlderConversationMessages();
                }
                return undefined;
            }, { passive: true });
        }

        bindConversationHistoryPagination();
