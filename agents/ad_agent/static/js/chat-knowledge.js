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

