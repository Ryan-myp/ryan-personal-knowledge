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

