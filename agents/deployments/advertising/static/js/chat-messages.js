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
                    continueWithSelectedAccount(accountId, originalRequest || {}, selection);
                });
                actions.appendChild(button);
            });
            section.appendChild(actions);
            return section;
        }

        function addMessage(content, type = 'agent', tools = null, isError = false, toolSummaryHtml = '', messageTime = null, ui = null, uiOptions = null) {
            const attachments = uiOptions?.attachments || [];
            const feedbackTurnId = String(uiOptions?.feedback?.turnId || '').trim();
            if (!toolSummaryHtml && !chatMessageHasPresentation(content, tools, ui, attachments)) return null;
            const activeThinkingMessage = type === 'agent'
                ? [...document.querySelectorAll(
                    '#chatContainer .message.agent.thinking-message-active',
                )].at(-1) || null
                : null;
            const mergedThinkingBox = activeThinkingMessage?.querySelector('.thinking-box') || null;
            if (mergedThinkingBox && typeof finalizeStreamingThought === 'function') {
                finalizeStreamingThought();
            }
            activeThinkingMessage?.remove();
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
            if (attachments.length) bodyHtml += '<div class="message-attachments-host"></div>';
            if (ui?.media_gallery?.length) bodyHtml += '<div class="message-media-gallery-host"></div>';
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
            if (type === 'agent' && feedbackTurnId) {
                bodyHtml += '<div class="message-feedback-host"></div>';
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
            if (mergedThinkingBox) {
                const contentHost = msg.querySelector('.message-content');
                const bodyHost = msg.querySelector('.message-body');
                contentHost?.insertBefore(mergedThinkingBox, bodyHost);
            }

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
            const attachmentHost = msg.querySelector('.message-attachments-host');
            if (attachmentHost) {
                renderMessageAttachments(attachmentHost, attachments, sessionId);
            }
            const feedbackHost = msg.querySelector('.message-feedback-host');
            if (feedbackHost) {
                renderAssistantFeedback(
                    feedbackHost,
                    feedbackTurnId,
                    uiOptions?.feedback?.rating || '',
                );
            }
            const mediaGalleryHost = msg.querySelector('.message-media-gallery-host');
            if (mediaGalleryHost) {
                renderMediaGallery(mediaGalleryHost, ui.media_gallery);
            }
            if (type === 'agent') {
                renderFacebookVideoEmbeds(
                    msg.querySelector('.message-body'),
                    content,
                    ui?.media_gallery,
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

            if (uiOptions?.insertBefore) container.insertBefore(msg, uiOptions.insertBefore);
            else container.appendChild(msg);
            void renderSvgImages(msg.querySelector('.message-content-text'));
            if (type === 'agent') {
                void renderMermaidDiagrams(
                    msg.querySelector('.message-content-text'),
                );
            }
            const chatArea = document.getElementById('chatArea');
            if (chatArea && !uiOptions?.suppressScroll) {
                chatArea.scrollTop = chatArea.scrollHeight;
            }

            return msg;
        }

        function renderAssistantFeedback(host, turnId, savedRating = '') {
            const controls = document.createElement('div');
            controls.className = 'message-feedback';
            controls.setAttribute('aria-label', '对回答提供反馈');

            const label = document.createElement('span');
            label.className = 'message-feedback-label';
            label.textContent = '这条回答有帮助吗？';
            controls.appendChild(label);

            const status = document.createElement('span');
            status.className = 'message-feedback-status';
            status.setAttribute('aria-live', 'polite');

            let currentRating = ['positive', 'negative'].includes(savedRating)
                ? savedRating
                : '';
            let saving = false;
            for (const [rating, symbol, labelText] of [
                ['positive', '👍', '有帮助'],
                ['negative', '👎', '没帮助'],
            ]) {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'message-feedback-button';
                button.dataset.rating = rating;
                button.textContent = symbol;
                button.title = labelText;
                button.setAttribute('aria-label', labelText);
                button.setAttribute('aria-pressed', String(currentRating === rating));
                if (currentRating === rating) button.classList.add('selected');
                button.addEventListener('click', async () => {
                    if (saving || currentRating === rating) return;
                    saving = true;
                    status.textContent = '保存中…';
                    controls.querySelectorAll('button').forEach(item => {
                        item.disabled = true;
                    });
                    try {
                        await submitAssistantFeedback(
                            sessionId,
                            turnId,
                            rating,
                        );
                        currentRating = rating;
                        status.textContent = '已记录';
                        controls.querySelectorAll('button').forEach(item => {
                            const selected = item.dataset.rating === currentRating;
                            item.classList.toggle('selected', selected);
                            item.setAttribute('aria-pressed', String(selected));
                        });
                    } catch (error) {
                        const detail = String(error?.message || '').trim();
                        status.textContent = detail
                            ? `保存失败：${detail.slice(0, 100)}`
                            : '保存失败，请稍后重试';
                    } finally {
                        saving = false;
                        controls.querySelectorAll('button').forEach(item => {
                            item.disabled = false;
                        });
                    }
                });
                controls.appendChild(button);
            }
            controls.appendChild(status);
            host.appendChild(controls);
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
                    <div class="loading-status" id="loadingStatus">正在分析你的请求…</div>
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
            pendingBlueprintRequest = null;
            pendingBlueprintContinuation = null;
            const card = document.getElementById('confirmCard');
            if (card) card.remove();
            if (typeof clearWorkbenchConfirmation === 'function') clearWorkbenchConfirmation();
            if (typeof workbenchState !== 'undefined' && workbenchState.activeCardId) {
                reopenCreationCard(workbenchState.activeCardId);
            } else if (typeof closeCreationWorkbench === 'function') closeCreationWorkbench();
            addMessage('❌ 操作已取消', 'agent');
        }

        function updateChatQueuePanel() {
            const panel = document.getElementById('chatQueuePanel');
            const sendButton = document.getElementById('sendBtn');
            const stopButton = document.getElementById('stopBtn');
            const hint = document.getElementById('chatInputHint');
            const queue = sessionId ? chatMessageQueue.list(sessionId) : [];
            const paused = Boolean(sessionId && pausedChatQueueSessions.has(sessionId));
            const editingQueuedMessage = queueMessageEditBlocksSession(sessionId);
            const queueSize = sessionId ? chatMessageQueue.size(sessionId) : 0;

            if (panel) {
                panel.replaceChildren();
                panel.hidden = queue.length === 0;
                if (queue.length) {
                    const header = document.createElement('div');
                    header.className = 'chat-queue-header';
                    const title = document.createElement('span');
                    title.textContent = editingQueuedMessage
                        ? `编辑中 · ${queue.length} 条待发送`
                        : paused
                            ? `已暂停 · ${queue.length} 条待发送`
                            : `后续消息 · ${queue.length}/${MAX_CHAT_QUEUE_SIZE}`;
                    header.appendChild(title);
                    if (paused && !editingQueuedMessage) {
                        const resume = document.createElement('button');
                        resume.className = 'chat-queue-resume';
                        resume.type = 'button';
                        resume.textContent = '继续发送';
                        resume.disabled = isSending;
                        resume.title = isSending ? '等待当前运行停止后继续' : '继续发送排队消息';
                        resume.addEventListener('click', resumeQueuedMessages);
                        header.appendChild(resume);
                    }
                    panel.appendChild(header);

                    const list = document.createElement('div');
                    list.className = 'chat-queue-items';
                    queue.forEach((item, index) => {
                        const row = document.createElement('div');
                        row.className = 'chat-queue-item';
                        const isEditing = editingQueueMessage
                            && editingQueueMessage.sessionId === sessionId
                            && String(editingQueueMessage.itemId) === String(item.id);
                        if (isEditing) {
                            row.classList.add('chat-queue-item-editing');
                            const editor = document.createElement('textarea');
                            editor.className = 'chat-queue-edit-input';
                            editor.rows = 2;
                            editor.maxLength = 12_000;
                            editor.value = editingQueueMessage.draft;
                            editor.setAttribute(
                                'aria-label',
                                `编辑第 ${index + 1} 条排队消息`,
                            );
                            editor.addEventListener('input', () => {
                                editingQueueMessage.draft = editor.value;
                                editingQueueMessage.error = '';
                                const save = row.querySelector('.chat-queue-save');
                                if (save) {
                                    save.disabled = !editor.value.trim()
                                        && !item.attachments?.length;
                                }
                                const error = row.querySelector('.chat-queue-edit-error');
                                if (error) error.textContent = '';
                            });
                            editor.addEventListener('keydown', event => {
                                if (event.key === 'Escape') {
                                    event.preventDefault();
                                    cancelQueuedMessageEdit(sessionId, item.id);
                                } else if (
                                    event.key === 'Enter'
                                    && (event.ctrlKey || event.metaKey)
                                ) {
                                    event.preventDefault();
                                    saveQueuedMessageEdit(sessionId, item.id);
                                }
                            });
                            row.appendChild(editor);

                            if (item.attachments?.length) {
                                const metadata = document.createElement('span');
                                metadata.className = 'chat-queue-item-meta chat-queue-edit-meta';
                                metadata.textContent = `保留 ${item.attachments.length} 个附件`;
                                row.appendChild(metadata);
                            }

                            const error = document.createElement('span');
                            error.className = 'chat-queue-edit-error';
                            error.setAttribute('role', 'status');
                            error.textContent = editingQueueMessage.error || '';
                            row.appendChild(error);

                            const actions = document.createElement('div');
                            actions.className = 'chat-queue-actions';
                            const save = document.createElement('button');
                            save.className = 'chat-queue-action chat-queue-save';
                            save.type = 'button';
                            save.textContent = '保存';
                            save.disabled = !editingQueueMessage.draft.trim()
                                && !item.attachments?.length;
                            save.addEventListener('click', () => {
                                saveQueuedMessageEdit(sessionId, item.id);
                            });
                            actions.appendChild(save);

                            const cancel = document.createElement('button');
                            cancel.className = 'chat-queue-action chat-queue-cancel';
                            cancel.type = 'button';
                            cancel.textContent = '取消';
                            cancel.addEventListener('click', () => {
                                cancelQueuedMessageEdit(sessionId, item.id);
                            });
                            actions.appendChild(cancel);
                            row.appendChild(actions);
                        } else {
                            const text = document.createElement('span');
                            text.className = 'chat-queue-item-text';
                            text.textContent = item.text || '分析图片或视频附件';
                            text.title = item.text || '分析图片或视频附件';
                            row.appendChild(text);
                            if (item.attachments?.length) {
                                const metadata = document.createElement('span');
                                metadata.className = 'chat-queue-item-meta';
                                metadata.textContent = `${item.attachments.length} 个附件`;
                                row.appendChild(metadata);
                            }

                            const actions = document.createElement('div');
                            actions.className = 'chat-queue-actions';
                            const edit = document.createElement('button');
                            edit.className = 'chat-queue-action chat-queue-edit';
                            edit.type = 'button';
                            edit.textContent = '编辑';
                            edit.title = `编辑第 ${index + 1} 条排队消息`;
                            edit.setAttribute('aria-label', edit.title);
                            edit.addEventListener('click', () => {
                                beginQueuedMessageEdit(sessionId, item);
                            });
                            actions.appendChild(edit);

                            const remove = document.createElement('button');
                            remove.className = 'chat-queue-remove';
                            remove.type = 'button';
                            remove.textContent = '×';
                            remove.title = `移除第 ${index + 1} 条排队消息`;
                            remove.setAttribute('aria-label', remove.title);
                            remove.addEventListener('click', () => {
                                removeQueuedChatMessage(item.id);
                            });
                            actions.appendChild(remove);
                            row.appendChild(actions);
                        }
                        list.appendChild(row);
                    });
                    panel.appendChild(list);
                }
            }

            if (sendButton) {
                sendButton.disabled = Boolean(
                    chatMediaUploading
                    || ((isSending || paused || queue.length > 0)
                        && queueSize >= MAX_CHAT_QUEUE_SIZE),
                );
                const queueMode = Boolean(isSending || paused || queue.length);
                sendButton.classList.toggle('is-queue-mode', queueMode);
                sendButton.setAttribute(
                    'aria-label',
                    queueMode ? '加入排队消息' : '发送',
                );
                sendButton.title = queueMode ? '按顺序排队发送' : '发送';
                if (isSending) sendButton.setAttribute('aria-busy', 'true');
                else sendButton.removeAttribute('aria-busy');
            }

            if (stopButton) {
                stopButton.hidden = !isSending;
                stopButton.disabled = isStopping;
                stopButton.setAttribute(
                    'aria-label',
                    isStopping ? '正在停止当前运行' : '停止当前运行',
                );
                stopButton.title = isStopping ? '正在请求停止…' : '停止当前运行';
            }

            if (hint) {
                if (isStopping) {
                    hint.textContent = '正在请求停止；已提交的写操作不会回滚，排队消息将暂停';
                } else if (isSending) {
                    hint.textContent = `Agent 正在运行；继续发送会排队（${queueSize}/${MAX_CHAT_QUEUE_SIZE}）`;
                } else if (editingQueuedMessage) {
                    hint.textContent = '排队消息正在编辑；保存或取消后继续发送';
                } else if (paused && queue.length) {
                    hint.textContent = '当前队列已暂停，可移除消息或点击“继续发送”';
                } else {
                    hint.textContent = 'Enter 发送 · Shift+Enter 换行 · 支持图片、视频和文档';
                }
            }
        }

        function queueMessageEditBlocksSession(targetSessionId) {
            if (
                !editingQueueMessage
                || editingQueueMessage.sessionId !== targetSessionId
            ) return false;
            return chatMessageQueue
                .list(targetSessionId)
                .some(item => String(item.id) === String(editingQueueMessage.itemId));
        }

        function beginQueuedMessageEdit(targetSessionId, item) {
            editingQueueMessage = {
                sessionId: targetSessionId,
                itemId: item.id,
                draft: item.text || '',
                error: '',
            };
            updateChatQueuePanel();
            document.querySelector('.chat-queue-edit-input')?.focus();
        }

        function cancelQueuedMessageEdit(targetSessionId, itemId) {
            if (
                !editingQueueMessage
                || editingQueueMessage.sessionId !== targetSessionId
                || String(editingQueueMessage.itemId) !== String(itemId)
            ) return;
            editingQueueMessage = null;
            updateChatQueuePanel();
            processNextQueuedMessage();
        }

        function saveQueuedMessageEdit(targetSessionId, itemId) {
            if (
                !editingQueueMessage
                || editingQueueMessage.sessionId !== targetSessionId
                || String(editingQueueMessage.itemId) !== String(itemId)
            ) return;
            const item = chatMessageQueue
                .list(targetSessionId)
                .find(queued => String(queued.id) === String(itemId));
            if (!item) {
                editingQueueMessage = null;
                updateChatQueuePanel();
                processNextQueuedMessage();
                return;
            }
            const text = String(editingQueueMessage.draft || '').trim();
            if (text.length > 12_000) {
                editingQueueMessage.error = '消息不能超过 12000 个字符。';
                updateChatQueuePanel();
                document.querySelector('.chat-queue-edit-input')?.focus();
                return;
            }
            if (!text && !item.attachments?.length) {
                editingQueueMessage.error = '消息内容不能为空。';
                updateChatQueuePanel();
                document.querySelector('.chat-queue-edit-input')?.focus();
                return;
            }
            if (!chatMessageQueue.updateText(targetSessionId, itemId, text)) return;
            editingQueueMessage = null;
            updateChatQueuePanel();
            processNextQueuedMessage();
        }

        function removeQueuedChatMessage(itemId) {
            if (!sessionId) return;
            const queued = chatMessageQueue
                .list(sessionId)
                .find(item => String(item.id) === String(itemId));
            if (!queued || !chatMessageQueue.remove(sessionId, itemId)) return;
            if (
                editingQueueMessage
                && editingQueueMessage.sessionId === sessionId
                && String(editingQueueMessage.itemId) === String(itemId)
            ) {
                editingQueueMessage = null;
            }
            const query = new URLSearchParams({ session_id: sessionId });
            for (const attachmentId of queued.requestParams.media_ids || []) {
                void serviceFetch(
                    `/chat/media/${encodeURIComponent(attachmentId)}?${query}`,
                    { method: 'DELETE' },
                ).catch(() => {});
            }
            if (!chatMessageQueue.size(sessionId)) {
                pausedChatQueueSessions.delete(sessionId);
            }
            updateChatQueuePanel();
        }

        function resumeQueuedMessages() {
            if (!sessionId || isSending) return;
            pausedChatQueueSessions.delete(sessionId);
            updateChatQueuePanel();
            processNextQueuedMessage();
        }

        function processNextQueuedMessage() {
            if (
                isSending || !sessionId
                || pausedChatQueueSessions.has(sessionId)
                || queueMessageEditBlocksSession(sessionId)
            ) return;
            const next = chatMessageQueue.dequeue(sessionId);
            updateChatQueuePanel();
            if (next) void executeChatMessage(next);
        }

        function finishChatTurn() {
            const finishedSessionId = activeRunSessionId;
            if (finishedSessionId) {
                const hasQueuedMessages = chatMessageQueue.size(finishedSessionId) > 0;
                if (isStopping && hasQueuedMessages) {
                    pausedChatQueueSessions.add(finishedSessionId);
                } else if (!hasQueuedMessages) {
                    pausedChatQueueSessions.delete(finishedSessionId);
                }
            }
            isSending = false;
            isStopping = false;
            activeRunSessionId = null;
            updateChatQueuePanel();
            processNextQueuedMessage();
        }

        async function requestChatCancellation() {
            if (!isSending || !activeRunSessionId || isStopping) return;
            isStopping = true;
            pausedChatQueueSessions.add(activeRunSessionId);
            updateChatQueuePanel();
            try {
                const response = await serviceFetch('/chat/cancel', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ session_id: activeRunSessionId }),
                });
                const text = await response.text();
                let data = {};
                try { data = text ? JSON.parse(text) : {}; } catch (_) { data = {}; }
                if (!response.ok) {
                    throw new Error(
                        data.detail || data.error || `停止请求失败（${response.status}）`,
                    );
                }
                if (data.status === 'not_running') {
                    isStopping = false;
                    updateChatQueuePanel();
                }
            } catch (error) {
                isStopping = false;
                updateChatQueuePanel();
                addMessage(
                    `停止请求未能送达：${String(error?.message || error)}`,
                    'agent',
                    null,
                    true,
                );
            }
        }

        function queueItemId() {
            return globalThis.crypto?.randomUUID?.()
                || `queued-${Date.now()}-${Math.random().toString(16).slice(2)}`;
        }

        function normalizeCreationReply(value) {
            return String(value || '').trim().toLowerCase().replace(/[\s，。！？、；：,.!?;:'"`“”‘’「」『』（）()【】\[\]{}]/g, '');
        }

        function isCreationDraftContinuation(text) {
            const normalized = String(text || '').trim().toLowerCase();
            if (!normalized) return false;
            const reply = normalizeCreationReply(text);
            const continuation = pendingBlueprintContinuation;
            const choices = [
                ...(continuation?.reply_options || []),
                ...(continuation?.fields || []).flatMap(field => [
                    field.label,
                    field.path,
                    ...(field.options || []).flatMap(option => (
                        typeof option === 'object'
                            ? [option.label, option.value]
                            : [option]
                    )),
                ]),
            ].map(normalizeCreationReply).filter(Boolean);
            const matchesField = choices.some(choice => choice === reply || (
                choice.length >= 3 && reply.includes(choice)
            ));
            if (matchesField) return true;
            if (/(?:不要|别|先不|暂不|不再).{0,5}(?:创建|新建|提交|执行)/.test(normalized)) {
                return false;
            }
            return [
                '创建', '新建', '提交', '执行', '继续', '确认',
                '修改', '调整', '改成', '改为', '调到', 'change',
                'update', 'edit', 'submit', 'create', 'continue', 'confirm',
            ].some(cue => normalized.includes(cue));
        }

        function captureChatMessage(text, submittedAttachments) {
            const targetSessionId = sessionId || ensureChatMediaSession();
            const pendingContext = pendingBlueprintRequest;
            const contextSessionId = pendingContext?.session_id
                || pendingBlueprintContinuation?.session_id;
            const matchesSession = !contextSessionId || contextSessionId === targetSessionId;
            const continueDraft = matchesSession && isCreationDraftContinuation(text);
            if (!matchesSession || ((pendingContext || pendingBlueprintContinuation) && !continueDraft)) {
                pendingBlueprintRequest = null;
                pendingBlueprintContinuation = null;
            }
            const requestParams = {
                ...(continueDraft ? pendingContext || {} : {}),
                user_input: text,
                session_id: targetSessionId,
            };
            if (submittedAttachments.length) {
                requestParams.media_ids = submittedAttachments.map(item => item.id);
            } else if (!Array.isArray(requestParams.media_ids)) {
                delete requestParams.media_ids;
            }
            return {
                id: queueItemId(),
                session_id: targetSessionId,
                requestParams,
                attachments: submittedAttachments,
                text,
            };
        }

        async function executeChatMessage(item) {
            if (isSending || item.session_id !== sessionId) return;
            isSending = true;
            isStopping = false;
            activeRunSessionId = item.session_id;
            updateChatQueuePanel();
            const { requestParams, attachments } = item;
            const text = String(requestParams.user_input || '');
            addMessage(text, 'user', null, false, '', null, null, {
                attachments,
            });
            addLoading();
            startExecutionTrace(text || '分析图片或视频附件');
            conversationCount++;
            const statToday = document.getElementById('statToday');
            if (statToday) statToday.textContent = conversationCount;

            try {
                const data = await streamChatRequest(requestParams);
                removeLoading();
                apiCallCount++;
                const statApiCalls = document.getElementById('statAPICalls');
                if (statApiCalls) statApiCalls.textContent = apiCallCount;
                renderStreamResult(data, requestParams);
                if (['cancelled', 'recovery_required'].includes(data.status)) {
                    pausedChatQueueSessions.add(item.session_id);
                }
                await refreshConversationHistory({ silent: true });
            } catch (error) {
                removeLoading();
                pausedChatQueueSessions.add(item.session_id);
                addMessage(markChatRequestFailure(error), 'agent', null, true);
            } finally {
                finishChatTurn();
            }
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
            isStopping = false;
            activeRunSessionId = originalRequest.session_id || sessionId;
            updateChatQueuePanel();
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
                if (activeRunSessionId) {
                    pausedChatQueueSessions.add(activeRunSessionId);
                }
                addMessage(markChatRequestFailure(error), 'agent', null, true);
            } finally {
                finishChatTurn();
            }
        }

        async function continueWithSelectedAccount(accountId, originalRequest, selection = {}) {
            if (isSending || accountId == null) return;
            const sourceText = String(originalRequest?.user_input || '').trim();
            const selectedId = String(accountId).trim();
            if (!sourceText || !selectedId) return;

            const userInput = `使用账户 ${selectedId} 继续`;
            const continuationRequest = { ...(originalRequest || {}) };
            delete continuationRequest.media_ids;
            const requestParams = {
                ...continuationRequest,
                user_input: userInput,
                user_id: 'web_user',
                session_id: sessionId,
                account_id: selectedId,
                ...(selection.turn_id && selection.tool ? {
                    interaction_response: {
                        type: 'account_selection',
                        turn_id: String(selection.turn_id),
                        tool_name: String(selection.tool),
                        value: selectedId,
                    },
                } : {}),
            };
            isSending = true;
            isStopping = false;
            activeRunSessionId = sessionId;
            updateChatQueuePanel();
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
                if (activeRunSessionId) {
                    pausedChatQueueSessions.add(activeRunSessionId);
                }
                addMessage(markChatRequestFailure(error), 'agent', null, true);
            } finally {
                finishChatTurn();
            }
        }

        // Send message
        async function sendMessage() {
            const input = document.getElementById('userInput');
            const text = input.value.trim();
            if ((!text && !pendingChatAttachments.length) || chatMediaUploading) return;
            const submittedAttachments = pendingChatAttachments.map(item => ({
                id: item.id,
                filename: item.filename,
                media_type: item.media_type,
                size: item.size,
            }));
            const item = captureChatMessage(text, submittedAttachments);
            const pendingCount = chatMessageQueue.size(item.session_id);
            if (!pendingCount) pausedChatQueueSessions.delete(item.session_id);
            const sessionPaused = pendingCount > 0
                && pausedChatQueueSessions.has(item.session_id);

            if (
                isSending || sessionPaused || pendingCount > 0
            ) {
                if (isSending && activeRunSessionId !== item.session_id) {
                    addMessage(
                        '当前运行属于另一个会话，请等待它结束后再发送。',
                        'agent',
                        null,
                        true,
                    );
                    return;
                }
                const queued = chatMessageQueue.enqueue(item.session_id, item);
                if (!queued.accepted) {
                    addMessage(
                        queued.reason === 'total_limit'
                            ? `当前页面的待发送消息已满（最多 ${MAX_CHAT_QUEUE_TOTAL_SIZE} 条），请先清理其他会话中的队列。`
                            : `本会话排队已满（最多 ${MAX_CHAT_QUEUE_SIZE} 条），请等一条完成或移除队列消息后再发送。`,
                        'agent',
                        null,
                        true,
                    );
                    return;
                }
                input.value = '';
                input.style.height = 'auto';
                clearPendingChatMedia({ revoke: true, deleteStored: false });
                updateChatQueuePanel();
                if (!isSending && !sessionPaused) processNextQueuedMessage();
                return;
            }

            input.value = '';
            input.style.height = 'auto';
            clearPendingChatMedia({ revoke: true, deleteStored: false });
            void executeChatMessage(item);
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
        function renderWelcomePage() {
            const template = document.getElementById('welcomeTemplate');
            const container = document.getElementById('chatContainer');
            if (template?.content && container) {
                container.replaceChildren(template.content.cloneNode(true));
            }
        }

        function newChat() {
            if (isSending) {
                showHistoryNotice('当前对话仍在运行。可以先停止或等它完成，再新建对话。');
                return;
            }
            stopDurableRunPolling();
            clearPendingChatMedia({ revoke: true });
            conversationLoadSequence += 1;
            conversationHistoryPage = {
                sessionId: null,
                nextCursor: null,
                hasMore: false,
                loading: false,
                generation: conversationLoadSequence,
            };
            if (typeof updateConversationHistoryPagination === 'function') {
                updateConversationHistoryPagination();
            }
            sessionId = null;
            updateChatQueuePanel();
            selectedConversationId = null;
            loadedConversationTurnIds.clear();
            pendingRequest = null;
            pendingBlueprintRequest = null;
            pendingBlueprintContinuation = null;
            pendingCreationReview = null;
            historySelectionMode = false;
            selectedConversationIds.clear();
            document.getElementById('confirmCard')?.remove();
            if (typeof resetCreationWorkbench === 'function') resetCreationWorkbench();
            resetExecutionTrace();
            renderConversationHistory();
            renderWelcomePage();
        }

        document.addEventListener('click', (event) => {
            if (!(event.composedPath?.() || []).some(node => node.classList?.contains('management-workspace')) && !event.target.closest('.management-workspace') && !event.target.closest('.global-actions') && !event.target.closest('.workspace-nav') && !event.target.closest('.workspace-popover') && !event.target.closest('.knowledge-overlay') && !event.target.closest('.blueprint-overlay') && !event.target.closest('.monitoring-overlay') && !event.target.closest('#scheduleOverlay') && !event.target.closest('#memoryOverlay') && !event.target.closest('.mcp-overlay') && !event.target.closest('.system-ops-wrap')) {
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
        renderWelcomePage();
        initializeTheme();
        resetExecutionTrace();
        refreshWorkspaceMode();
        refreshConversationHistory();
        document.getElementById('userInput').focus();
