        let knowledgeReadSequence = 0;
        let knowledgeEditSequence = 0;
        let knowledgeSavePending = false;
        let knowledgeCatalogPending = null;

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
            const notice = document.getElementById('knowledgeNotice');
            if (notice) { notice.textContent = message || ''; notice.hidden = !message; notice.classList.toggle('error', isError); }
            const status = document.getElementById('knowledgeWriteStatus');
            if (!status) return;
            status.textContent = message || '';
            status.classList.toggle('error', isError);
        }

        function setKnowledgeSemanticStatus(message, isError = false) {
            const status = document.getElementById('knowledgeSemanticStatus');
            if (!status) return;
            status.textContent = message || '';
            status.classList.toggle('error', Boolean(isError));
        }

        async function loadKnowledgeSemanticIndexStatus() {
            const rebuild = document.getElementById('knowledgeSemanticRebuildButton');
            if (rebuild) rebuild.disabled = true;
            setKnowledgeSemanticStatus('正在读取索引状态…');
            try {
                const result = await apiFetch('/knowledge/semantic-index/status');
                const builtin = result.builtin || {};
                const tenant = result.tenant || {};
                const configured = Boolean(result.configured);
                const description = configured
                    ? `内置 ${builtin.current ? '最新' : '待重建'} · 当前租户 ${tenant.current ? '最新' : '待重建'}`
                    : '请先在模型管理中配置知识库 Embedding 模型';
                setKnowledgeSemanticStatus(description);
                if (rebuild) rebuild.disabled = !configured;
            } catch (error) {
                const message = error?.status === 401 || error?.status === 403
                    ? '当前身份没有知识库索引状态权限。'
                    : error?.message || '索引状态读取失败。';
                setKnowledgeSemanticStatus(message, true);
            }
        }

        async function rebuildKnowledgeSemanticIndex() {
            const button = document.getElementById('knowledgeSemanticRebuildButton');
            if (button) button.disabled = true;
            setKnowledgeSemanticStatus('正在重建内置与当前租户索引…');
            try {
                const result = await apiFetch('/knowledge/semantic-index/rebuild', {
                    method: 'POST',
                });
                if (!result.configured) {
                    setKnowledgeSemanticStatus('Embedding 模型未配置；普通查询继续使用词法检索。', true);
                    return;
                }
                const builtin = result.builtin || {};
                const tenant = result.tenant || {};
                const completed = Boolean(builtin.available && tenant.available);
                setKnowledgeSemanticStatus(
                    completed
                        ? `索引已完成 · 内置 ${builtin.chunk_count || 0} 段 · 当前租户 ${tenant.chunk_count || 0} 段`
                        : '索引未能完整重建；知识查询已回退到词法检索，请检查模型配置后重试。',
                    !completed,
                );
                if (button) button.disabled = false;
            } catch (error) {
                const message = error?.status === 401 || error?.status === 403
                    ? '当前身份没有重建权限，需要 knowledge.write。'
                    : error?.message || '知识语义索引重建失败。';
                setKnowledgeSemanticStatus(message, true);
                if (button) button.disabled = false;
            }
        }

        function toggleKnowledgeComposer() {
            newKnowledgeCatalogDocument();
        }

        function showKnowledgeManagementView(focusTitle = true) {
            setResourceView('knowledge', 'edit');
            resourceCatalogs.knowledge.hasDraft = true;
            trackResourceDraft('knowledge', '#knowledgeComposer');
            document.getElementById('knowledgeComposer')?.classList.add('active');
            if (focusTitle) document.getElementById('knowledgeTitle')?.focus();
        }

        function showKnowledgeSearchView() {
            showResourceList('knowledge');
        }

        function setKnowledgeEditorMode(documentId = '', metadata = {}) {
            knowledgeState.editingDocumentId = documentId || '';
            knowledgeState.editorMetadata = {...metadata};
            const editing = Boolean(knowledgeState.editingDocumentId || metadata.derived_from?.startsWith('builtin:'));
            const cancel = document.getElementById('knowledgeCancelEditButton');
            const draftButton = document.getElementById('knowledgeSaveDraftButton');
            const publishButton = document.getElementById('knowledgeSavePublishButton');
            if (cancel) cancel.hidden = !editing;
            if (draftButton) draftButton.textContent = editing ? '保存修改' : '保存草稿';
            if (publishButton) publishButton.textContent = editing ? '保存并发布新版本' : '保存并发布';
        }

        function resetKnowledgeEditor() {
            knowledgeEditSequence += 1;
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
            knowledgeState.managedItems = Array.isArray(items) ? items : [];
            renderKnowledgeCatalogTable();
        }

        function loadManagedKnowledgeDocuments() {
            const state = resourceCatalogs.knowledge;
            const params = new URLSearchParams({
                limit: String(state.limit), offset: String((state.page - 1) * state.limit),
                source: state.filters.source || 'all',
                q: document.getElementById('knowledgeQuery')?.value.trim() || '',
                platform: document.getElementById('knowledgePlatform')?.value || '',
                category: state.filters.category || '', status: state.filters.status || '',
            });
            return loadKnowledgeManagementPage(params);
        }

        function loadKnowledgeManagementPage(params) {
            const key = params.toString();
            if (knowledgeCatalogPending?.key === key) return knowledgeCatalogPending.promise;
            const promise = fetchKnowledgeManagementPage(new URLSearchParams(key));
            knowledgeCatalogPending = {key, promise};
            void promise.finally(() => {
                if (knowledgeCatalogPending?.promise === promise) knowledgeCatalogPending = null;
            });
            return promise;
        }

        async function fetchKnowledgeManagementPage(params) {
            const request = beginCatalogLoad('knowledge', {retry: () => loadKnowledgeManagementPage(params)});
            ++knowledgeReadSequence;
            setKnowledgeStatus('正在读取知识列表…');
            try {
                let data = await apiFetch(`/knowledge/documents?${params.toString()}`);
                if (!isCurrentCatalogLoad(request)) return false;
                // A deletion can remove the last page. Refetch its new boundary once.
                if (data.offset > 0 && data.offset >= data.total) {
                    params.set('offset', String(Math.max(0, Math.ceil(data.total / data.limit) - 1) * data.limit));
                    data = await apiFetch(`/knowledge/documents?${params.toString()}`);
                    if (!isCurrentCatalogLoad(request)) return false;
                }
                knowledgeState.catalogItems = data.documents.map(item => item.catalog_source === 'managed'
                    ? {...item, document_id: `managed:${item.document_id}`} : item);
                knowledgeState.catalogCategories = data.categories || [];
                knowledgeState.catalogPage = {total:data.total, page:Math.floor(data.offset / data.limit) + 1,
                    pages:Math.max(1,Math.ceil(data.total / data.limit)), has_more:data.has_more};
                resourceCatalogs.knowledge.page = knowledgeState.catalogPage.page;
                knowledgeState.summary = '';
                renderKnowledgeCatalogTable();
                setKnowledgeStatus(`知识列表 · 共 ${data.total} 条`);
                return true;
            } catch (error) {
                if (!isCurrentCatalogLoad(request)) return false;
                request.error = error.message || '知识列表读取失败';
                setKnowledgeStatus(`${request.error}；保留此前列表，请重试。`, true);
                return false;
            } finally {
                finishCatalogLoad(request, request.error);
            }
        }

        async function editKnowledgeDocument(documentId) {
            const sequence = ++knowledgeEditSequence;
            try {
                const item = await apiFetch(`/knowledge/documents/${encodeURIComponent(documentId)}`);
                if (sequence !== knowledgeEditSequence) return;
                fillKnowledgeEditor(item, documentId);
            } catch (error) {
                if (sequence !== knowledgeEditSequence) return;
                setKnowledgeWriteStatus(error.message || '知识文档读取失败。', true);
            }
        }

        function fillKnowledgeEditor(item, documentId = '') {
            const metadata = Object.fromEntries(['layer','source_ref','confidence','wiki_type',
                'derived_from','raw_sha256','wikilinks'].filter(key => item[key] != null).map(key => [key,item[key]]));
            const revision = !documentId || item.status === 'published' || Boolean(item.published_at);
            const versions = (knowledgeState.managedItems || []).filter(row => row.title === item.title
                || (metadata.derived_from && row.derived_from === metadata.derived_from)).map(row => row.version);
            document.getElementById('knowledgeTitle').value = item.title || item.topic || '';
            document.getElementById('knowledgeContent').value = item.content || '';
            document.getElementById('knowledgeWritePlatform').value = item.platform || 'all';
            document.getElementById('knowledgeWriteType').value = item.knowledge_type || 'general';
            document.getElementById('knowledgeVersion').value = revision ? nextResourceRevision(item.version, versions) : item.version;
            document.getElementById('knowledgeTags').value = (item.tags || []).join(', ');
            document.getElementById('knowledgeSource').value = item.source || 'user';
            setKnowledgeEditorMode(documentId, metadata);
            setKnowledgeWriteStatus(revision ? '修改将保存为新版本；发布后生效，旧版本保留。' : '正在编辑草稿；发布后生效。');
            showKnowledgeManagementView(false);
            document.getElementById('knowledgeContent')?.focus();
        }

        async function editBuiltinKnowledgeDocument(item) {
            const origin = `builtin:${item.document_id}`;
            const existing = (knowledgeState.managedItems || []).find(row => row.derived_from === origin && row.status !== 'deprecated');
            if (existing) return editKnowledgeDocument(existing.document_id);
            const sequence = ++knowledgeEditSequence;
            try {
                const detail = await apiFetch(`/knowledge/builtin/${encodeURIComponent(item.document_id)}`);
                if (sequence !== knowledgeEditSequence) return;
                fillKnowledgeEditor({...detail, derived_from:origin});
            } catch (error) {
                if (sequence === knowledgeEditSequence) setKnowledgeWriteStatus(error.message || '知识正文读取失败，请重试。', true);
            }
        }

        async function changeKnowledgePublication(documentId, publish) {
            try {
                await apiFetch(`/knowledge/documents/${encodeURIComponent(documentId)}/${publish ? 'publish' : 'unpublish'}`, { method: 'POST' });
                setKnowledgeWriteStatus(publish ? '知识已发布，Agent 后续可以检索。' : '知识已下线，Agent 不会再检索。');
                await loadManagedKnowledgeDocuments();
                showResourceList('knowledge');
            } catch (error) { window.alert(`${publish ? '发布' : '下线'}失败：${error.message || '请稍后重试'}`); }
        }

        async function deleteKnowledgeDocument(documentId, status) {
            const prompt = status === 'published' ? '确认归档这篇已发布知识？归档后仍保留历史记录，但不再参与检索。' : '确认删除这篇草稿？删除后不可恢复。';
            if (!documentId || !window.confirm(prompt)) return;
            try {
                await apiFetch(`/knowledge/documents/${encodeURIComponent(documentId)}`, { method: 'DELETE' });
                if (knowledgeState.editingDocumentId === documentId) resetKnowledgeEditor();
                if (resourceCatalogs.knowledge.draft?.documentId === documentId) {
                    resourceCatalogs.knowledge.draft = null;
                    resourceCatalogs.knowledge.hasDraft = false;
                }
                setKnowledgeWriteStatus(status === 'published' ? '知识已归档。' : '草稿已删除。');
                await loadManagedKnowledgeDocuments();
                showResourceList('knowledge');
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
                if (file.size > 120000 * 4) throw new Error('文件过大，请上传不超过 480 KB 的文本文件。');
                const content = await file.text();
                if (!content.trim()) throw new Error('文件内容为空，请选择有正文的文件。');
                if (content.length > 120000) throw new Error('文件正文超过 120,000 字，请精简后再上传。');
                setKnowledgeWriteStatus(`正在保存 ${file.name} 的原始文件并启动自动 ingest…`);
                const mediaType = extension === 'json'
                    ? 'application/json'
                    : extension === 'md' || extension === 'markdown'
                        ? 'text/markdown'
                        : 'text/plain';
                const result = await apiFetch('/knowledge/raw', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        filename: file.name,
                        content,
                        media_type: mediaType,
                    }),
                });
                const sourceId = result.source?.source_id || '';
                setKnowledgeWriteStatus(
                    result.created === false
                        ? '这个原始文件已经存在，正在复用已有 ingest 任务…'
                        : '原始文件已保存，LLM 正在生成待审核 Wiki 草稿…'
                );
                if (sourceId) await waitForKnowledgeIngest(sourceId);
            } catch (error) {
                setKnowledgeWriteStatus(error.message || '文件读取失败，请检查文件格式。', true);
            } finally {
                input.value = '';
            }
        }

        async function waitForKnowledgeIngest(sourceId) {
            for (let attempt = 0; attempt < 20; attempt += 1) {
                await new Promise(resolve => window.setTimeout(resolve, attempt ? 1200 : 250));
                const source = await apiFetch(`/knowledge/raw/${encodeURIComponent(sourceId)}`);
                if (source.status === 'draft_ready') {
                    setKnowledgeWriteStatus('自动 ingest 完成，Wiki 草稿已生成；请在知识列表中审核并发布。');
                    await loadManagedKnowledgeDocuments();
                    return source;
                }
                if (source.status === 'failed') {
                    throw new Error(source.ingest_error || '自动 ingest 失败，请检查原始文档。');
                }
                setKnowledgeWriteStatus(`原始文档已保存，自动 ingest 中…（${source.status || 'queued'}）`);
            }
            setKnowledgeWriteStatus('原始文档已保存，ingest 仍在后台进行；稍后刷新知识列表查看草稿。');
            return null;
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
            campaign_planning: '投放规划',
            campaign_operations: '投放配置',
            compliance: '合规与审核',
            optimization: '优化方法',
            measurement: '测量与报表',
            reporting: '报表分析',
            industry_playbooks: '行业打法',
            budget_bidding: '预算与出价',
            audience_targeting: '受众与定向',
            creative: '创意与素材',
            cross_platform_foundation: '跨平台基础',
            programmatic_advertising: '程序化广告',
            diagnostics: '诊断与排障',
            experimentation: '实验与学习',
            general: '通用知识',
        };

        function knowledgeCategoryLabel(value) {
            const key = String(value || 'general');
            return knowledgeCategoryLabels[key] || `自定义分类（${key}）`;
        }

        function knowledgePlatformLabel(value) {
            const key = String(value || 'all');
            return { all: '通用', meta: 'Meta', tiktok: 'TikTok',
                'google-ads': 'Google Ads', dv360: 'DV360' }[key] || `自定义平台（${key}）`;
        }

        function knowledgeTypeLabel(value) {
            const key = String(value || 'general');
            const options = document.getElementById('knowledgeWriteType')?.options || [];
            const option = Array.from(options).find(item => item.value === key);
            return option?.textContent || `自定义类型（${key}）`;
        }

        function selectKnowledgeResult(key) {
            const item = knowledgeState.items.find((entry, index) => knowledgeItemKey(entry, index) === key);
            const reader = document.getElementById('knowledgeReader');
            if (!item || !reader) return;
            knowledgeState.selectedKey = key;
            setResourceView('knowledge', 'detail');
            renderKnowledgeReader(item);
        }

        function renderKnowledgeReader(item) {
            const reader = document.getElementById('knowledgeReader');
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
            kicker.textContent = [knowledgePlatformLabel(item.platform),
                knowledgeCategoryLabel(item.category), knowledgeTypeLabel(item.knowledge_type || item.layer)].filter(Boolean).join(' / ');
            const title = document.createElement('h1');
            title.textContent = item.title || item.topic || item.document_id || '未命名知识';
            const badge = document.createElement('span');
            badge.className = 'knowledge-reader-badge';
            badge.textContent = item.status === 'draft' ? '草稿' : item.status === 'deprecated' ? '已归档' : item.confidence != null ? `可信度 ${Math.round(Number(item.confidence) * 100)}%` : '已发布';
            const meta = document.createElement('div');
            meta.className = 'knowledge-reader-meta';
            meta.textContent = [item.source || item.source_ref, item.version ? `v${item.version}` : '', item.updated_at ? `更新于 ${String(item.updated_at).slice(0, 10)}` : ''].filter(Boolean).join('  ·  ');
            if (item.source_ref && item.source) meta.title = `来源引用：${item.source_ref}`;
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
                const published = !item.status || item.status === 'published';
                unpublish.type = 'button'; unpublish.textContent = published ? '下线' : '发布';
                unpublish.onclick = () => changeKnowledgePublication(managedId, !published);
                const archive = document.createElement('button');
                archive.type = 'button'; archive.className = 'danger'; archive.textContent = published ? '归档' : '删除';
                archive.onclick = () => deleteKnowledgeDocument(managedId, item.status || 'published');
                if (item.status !== 'deprecated') actions.append(edit, unpublish);
                actions.append(archive);
            } else {
                const readOnly = document.createElement('span');
                readOnly.className = 'knowledge-reader-readonly';
                readOnly.textContent = '内置原版';
                const edit = document.createElement('button');
                edit.type = 'button'; edit.textContent = '编辑文档';
                edit.onclick = () => editBuiltinKnowledgeDocument(item);
                const clone = document.createElement('button');
                clone.type = 'button'; clone.textContent = '复制为我的草稿';
                clone.onclick = () => cloneKnowledgeDocument(item);
                actions.append(readOnly, edit, clone);
            }
            const footer = document.createElement('footer');
            footer.className = 'knowledge-reader-footer';
            footer.textContent = '仅作为 Agent 业务上下文使用，不会直接调用广告渠道接口。';
            header.append(actions);
            reader.append(header, context, body, footer);
        }

        async function cloneKnowledgeDocument(item) {
            const sequence = ++knowledgeEditSequence;
            try {
                const detail = await apiFetch(`/knowledge/builtin/${encodeURIComponent(item.document_id)}`);
                if (sequence !== knowledgeEditSequence) return;
                fillClonedKnowledgeDocument({...detail, excerpt:detail.content || ''});
            } catch (error) {
                if (sequence === knowledgeEditSequence) setKnowledgeWriteStatus(error.message || '知识正文读取失败', true);
            }
        }

        function fillClonedKnowledgeDocument(item) {
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
            knowledgeState.items = Array.isArray(results) ? results : [];
            knowledgeState.summary = summary || '';
            knowledgeState.summaryMode = summaryMode || 'lexical';
            renderKnowledgeCatalogTable();
        }

        async function searchKnowledge() {
            showKnowledgeSearchView();
            resourceCatalogs.knowledge.page = 1;
            const loaded = await loadManagedKnowledgeDocuments();
            if (!loaded) return;
            const query = document.getElementById('knowledgeQuery')?.value.trim() || '';
            const platform = document.getElementById('knowledgePlatform')?.value || '';
            const summarize = document.getElementById('knowledgeSmartSummary')?.checked || false;
            if (!query || !summarize) return;
            const sequence = ++knowledgeReadSequence;
            setKnowledgeStatus('列表已加载；正在总结已发布知识…');
            try {
                const params = new URLSearchParams({ query, limit: '10', summarize: String(summarize) });
                if (platform) params.set('platform', platform);
                const data = await apiFetch(`/knowledge/search?${params.toString()}`, {timeoutMs: summarize ? 120000 : 30000});
                if (sequence !== knowledgeReadSequence) return;
                const results = Array.isArray(data.results) ? data.results : [];
                knowledgeState.summary = data.summary || '';
                knowledgeState.summaryMode = data.summary_mode || 'llm';
                setKnowledgeStatus(`知识列表 · 共 ${knowledgeState.catalogPage.total} 条 · 已总结 ${results.length} 条已发布知识。`);
            } catch (error) {
                if (sequence !== knowledgeReadSequence) return;
                setKnowledgeStatus(error.message || '知识库暂时不可用。', true);
            }
        }

        function loadKnowledgeCatalog() {
            return loadManagedKnowledgeDocuments();
        }

        function knowledgeEditorSnapshot() {
            return Object.fromEntries([
                'knowledgeTitle', 'knowledgeContent', 'knowledgeWritePlatform', 'knowledgeWriteType',
                'knowledgeTags', 'knowledgeSource', 'knowledgeVersion',
            ].map(id => [id, document.getElementById(id)?.value || '']));
        }

        function preservePendingKnowledgeEdits(snapshot) {
            if (JSON.stringify(knowledgeEditorSnapshot()) === JSON.stringify(snapshot)) return false;
            resourceCatalogs.knowledge.hasDraft = true;
            resourceCatalogs.knowledge.draft = null;
            setKnowledgeWriteStatus('提交时的内容已保存；新增编辑仍未保存，请再次保存。');
            return true;
        }

        async function saveKnowledgeDocument(publishNow = false) {
            if (knowledgeSavePending) return;
            const title = document.getElementById('knowledgeTitle')?.value.trim() || '';
            const content = document.getElementById('knowledgeContent')?.value.trim() || '';
            if (!title || !content) {
                setKnowledgeWriteStatus('请填写标题和 Markdown 正文。', true);
                return;
            }
            setKnowledgeWriteStatus('正在保存知识文档…');
            knowledgeSavePending = true;
            const sequence = knowledgeEditSequence;
            const snapshot = knowledgeEditorSnapshot();
            resourceCatalogs.knowledge.hasDraft = true;
            for (const id of ['knowledgeSaveDraftButton', 'knowledgeSavePublishButton']) {
                const button = document.getElementById(id);
                if (button) button.disabled = true;
            }
            const payload = {
                confidence: 0.8,
                ...(knowledgeState.editorMetadata || {}),
                title,
                content,
                platform: document.getElementById('knowledgeWritePlatform')?.value || 'all',
                knowledge_type: document.getElementById('knowledgeWriteType')?.value || 'general',
                tags: (document.getElementById('knowledgeTags')?.value || '').split(',').map(item => item.trim()).filter(Boolean),
                source: document.getElementById('knowledgeSource')?.value.trim() || 'user',
                version: document.getElementById('knowledgeVersion')?.value.trim() || '1.0.0',
            };
            try {
                const editingId = knowledgeState.editingDocumentId;
                const created = await apiFetch(editingId ? `/knowledge/documents/${encodeURIComponent(editingId)}` : '/knowledge/documents', {
                    method: editingId ? 'PUT' : 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });
                if (sequence !== knowledgeEditSequence) return;
                setKnowledgeEditorMode(created.document_id, Object.fromEntries(
                    Object.keys(knowledgeState.editorMetadata || {}).map(key => [key, created[key] ?? payload[key]])));
                const versionInput = document.getElementById('knowledgeVersion');
                if (versionInput.value === snapshot.knowledgeVersion) {
                    versionInput.value = created.version || payload.version;
                    snapshot.knowledgeVersion = versionInput.value;
                }
                if (publishNow) {
                    await apiFetch(`/knowledge/documents/${encodeURIComponent(created.document_id)}/publish`, { method: 'POST' });
                    if (sequence !== knowledgeEditSequence) return;
                    setKnowledgeWriteStatus('已保存并发布；后续检索和 Agent 对话可以使用这份知识。');
                } else {
                    setKnowledgeWriteStatus(created.version_mode === 'new_draft' ? '已生成新版本草稿；发布后才会进入检索和 Agent 上下文。' : '已保存为草稿；发布后才会进入检索和 Agent 上下文。');
                }
                if (preservePendingKnowledgeEdits(snapshot)) return;
                await loadManagedKnowledgeDocuments();
                if (sequence !== knowledgeEditSequence || preservePendingKnowledgeEdits(snapshot)) return;
                resourceCatalogs.knowledge.hasDraft = false;
                showResourceList('knowledge');
            } catch (error) {
                if (sequence !== knowledgeEditSequence) return;
                setKnowledgeWriteStatus(error.message || '知识文档保存失败，请检查权限和内容。', true);
            } finally {
                knowledgeSavePending = false;
                for (const id of ['knowledgeSaveDraftButton', 'knowledgeSavePublishButton']) {
                    const button = document.getElementById(id);
                    if (button) button.disabled = false;
                }
            }
        }
