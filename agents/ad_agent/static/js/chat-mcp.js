        const mcpState = {
            servers: [],
            selectedId: '',
            selected: null,
            builtinTools: [],
            selectedBuiltin: null,
            selectedExternalTool: null,
        };

        function mcpStatusLabel(status) {
            return ({
                draft: '草稿', not_run: '未校验', partial: '部分通过', validated: '已校验',
                active: '运行中', disabled: '已停用', error: '校验失败', deleted: '已移除',
                passed: '通过', failed: '失败', pending: '待校验', enabled: '已启用',
                discovered: '已发现',
            })[status] || status || '未知';
        }

        function showMCPNotice(message, isError = false) {
            const notice = document.getElementById('mcpNotice');
            if (!notice) return;
            notice.textContent = message || '';
            notice.className = `mcp-notice active ${isError ? 'error' : 'success'}`;
        }

        function clearMCPNotice() {
            const notice = document.getElementById('mcpNotice');
            if (notice) { notice.textContent = ''; notice.className = 'mcp-notice'; }
        }

        function openMCPManager() {
            closeWorkspacePopovers();
            const overlay = document.getElementById('mcpOverlay');
            if (!overlay) return;
            overlay.classList.add('active');
            overlay.setAttribute('aria-hidden', 'false');
            loadMCPServers();
        }

        function closeMCPManager() {
            const overlay = document.getElementById('mcpOverlay');
            if (!overlay) return;
            overlay.classList.remove('active');
            overlay.setAttribute('aria-hidden', 'true');
        }

        function newMCPServer() {
            mcpState.selectedId = '';
            mcpState.selected = null;
            document.getElementById('mcpDetailTitle').textContent = '新建 MCP Server';
            document.getElementById('mcpServerStatus').textContent = '草稿';
            for (const [id, value] of [['mcpNameInput', ''], ['mcpEndpointInput', ''], ['mcpCredentialRefInput', ''], ['mcpAuthHeaderInput', ''], ['mcpDescriptionInput', '']]) {
                const field = document.getElementById(id);
                if (field) field.value = value;
            }
            document.getElementById('mcpAuthTypeInput').value = 'none';
            document.getElementById('mcpTimeoutInput').value = '20';
            document.getElementById('mcpToolList').innerHTML = '<div class="mcp-empty">保存并完成连通性校验后显示远端 Tool。</div>';
            hideMCPExternalTestPanel();
            document.getElementById('mcpCheckGrid').innerHTML = '<div class="mcp-empty">完整校验会检查配置、握手、Tool Schema 和策略。</div>';
            document.getElementById('mcpValidationMeta').textContent = '尚未运行';
            document.getElementById('mcpEnableButton').disabled = true;
            document.getElementById('mcpDeleteButton').disabled = true;
            updateMCPAuthHint();
            clearMCPNotice();
            renderMCPServerList();
        }

        function updateMCPAuthHint() {
            const type = document.getElementById('mcpAuthTypeInput')?.value || 'none';
            const ref = document.getElementById('mcpCredentialRefInput');
            const header = document.getElementById('mcpAuthHeaderInput');
            if (ref) ref.disabled = type === 'none';
            if (header) {
                header.disabled = type === 'none';
                if (type === 'bearer' && !header.value) header.value = 'Authorization';
                if (type === 'api_key' && (!header.value || header.value === 'Authorization')) header.value = 'X-API-Key';
            }
            const hint = document.getElementById('mcpAuthHint');
            if (hint) hint.textContent = type === 'none'
                ? '当前 Server 不发送认证 Header。'
                : `页面只保存 credential_ref；部署环境需提供 AD_AGENT_MCP_CREDENTIAL_${(ref?.value || '<REF>').replace(/[^A-Za-z0-9]/g, '_').toUpperCase()}。`;
        }

        async function loadMCPServers(selectId = null) {
            clearMCPNotice();
            try {
                const data = await apiFetch('/mcp/servers?limit=200');
                mcpState.servers = Array.isArray(data.servers) ? data.servers : [];
                renderMCPServerList();
                const id = selectId || mcpState.selectedId || mcpState.servers[0]?.server_id;
                if (id) selectMCPServer(id);
                else newMCPServer();
            } catch (error) {
                mcpState.servers = [];
                renderMCPServerList();
                showMCPNotice(error.message || 'MCP Server 读取失败', true);
            }
        }

        function renderMCPServerList() {
            const list = document.getElementById('mcpServerList');
            if (!list) return;
            list.replaceChildren();
            if (!mcpState.servers.length) {
                const empty = document.createElement('div');
                empty.className = 'mcp-empty';
                empty.textContent = '当前租户还没有 MCP Server。点击“接入 MCP Server”开始。';
                list.appendChild(empty);
                return;
            }
            for (const server of mcpState.servers) {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = `mcp-server-item${mcpState.selectedId === server.server_id ? ' active' : ''}`;
                button.innerHTML = `<span class="mcp-server-item-mark">${server.enabled ? '●' : '○'}</span><span class="mcp-server-item-copy"><strong>${escapeHtml(server.name || server.server_id)}</strong><small>${escapeHtml(mcpStatusLabel(server.status))} · ${(server.tools || []).length} Tools</small></span><span class="mcp-server-item-arrow">›</span>`;
                button.addEventListener('click', () => selectMCPServer(server.server_id));
                list.appendChild(button);
            }
        }

        function selectMCPServer(serverId) {
            const server = mcpState.servers.find(item => String(item.server_id) === String(serverId));
            if (!server) return;
            mcpState.selectedId = server.server_id;
            mcpState.selected = server;
            document.getElementById('mcpDetailTitle').textContent = server.name || server.server_id;
            document.getElementById('mcpServerStatus').textContent = mcpStatusLabel(server.status);
            document.getElementById('mcpNameInput').value = server.name || '';
            document.getElementById('mcpEndpointInput').value = server.endpoint || '';
            document.getElementById('mcpAuthTypeInput').value = server.auth_type || 'none';
            document.getElementById('mcpCredentialRefInput').value = server.credential_ref || '';
            document.getElementById('mcpAuthHeaderInput').value = server.auth_header || '';
            document.getElementById('mcpTimeoutInput').value = server.timeout_seconds || 20;
            document.getElementById('mcpDescriptionInput').value = server.description || '';
            document.getElementById('mcpEnableButton').disabled = server.validation_status !== 'passed' && !server.enabled;
            document.getElementById('mcpEnableButton').textContent = server.enabled ? '停用 Server' : '启用 Server';
            document.getElementById('mcpDeleteButton').disabled = false;
            updateMCPAuthHint();
            renderMCPValidation(server);
            renderMCPTools(server);
            hideMCPExternalTestPanel();
            renderMCPServerList();
        }

        function renderMCPValidation(server) {
            const report = server.validation_report || {};
            const checks = report.checks || {};
            const grid = document.getElementById('mcpCheckGrid');
            const meta = document.getElementById('mcpValidationMeta');
            if (meta) meta.textContent = report.checked_at ? `${mcpStatusLabel(server.validation_status)} · ${new Date(report.checked_at).toLocaleString('zh-CN')}` : '尚未运行';
            if (!grid) return;
            const labels = { configuration: '配置', connectivity: '连通性与握手', tool_schema: 'Tool Schema', policy: '安全策略' };
            const entries = Object.entries(labels).map(([key, label]) => {
                const item = checks[key] || {};
                const passed = item.status === 'passed';
                const detail = item.error || (key === 'connectivity' && item.tool_count != null ? `发现 ${item.tool_count} 个 Tool` : key === 'policy' ? '写 Tool 需确认，默认不可重放' : '未运行');
                return `<div class="mcp-check-card ${passed ? 'passed' : item.status === 'failed' ? 'failed' : 'pending'}"><span class="mcp-check-icon">${passed ? '✓' : item.status === 'failed' ? '!' : '·'}</span><span><strong>${label}</strong><small>${escapeHtml(String(detail))}</small></span><em>${mcpStatusLabel(item.status)}</em></div>`;
            }).join('');
            grid.innerHTML = entries || '<div class="mcp-empty">尚未运行校验。</div>';
        }

        function renderMCPTools(server) {
            const list = document.getElementById('mcpToolList');
            if (!list) return;
            const tools = Array.isArray(server.tools) ? server.tools : [];
            if (!tools.length) { list.innerHTML = '<div class="mcp-empty">完成连通性校验后显示远端 Tool。</div>'; return; }
            list.replaceChildren();
            for (const tool of tools) {
                const row = document.createElement('div');
                const readOnly = tool.annotations?.readOnlyHint === true && tool.annotations?.destructiveHint !== true;
                row.className = `mcp-tool-row ${tool.enabled ? 'enabled' : ''}`;
                const testAction = readOnly && tool.enabled
                    ? '<button class="btn btn-secondary mcp-tool-test-button" type="button">测试</button>'
                    : readOnly ? '<span class="mcp-tool-test-note">启用后可测试</span>' : '<span class="mcp-tool-test-note">写入不可直测</span>';
                row.innerHTML = `<div class="mcp-tool-copy"><div><strong>${escapeHtml(tool.title || tool.remote_name)}</strong><span class="mcp-tool-risk ${readOnly ? 'read' : 'write'}">${readOnly ? '只读' : '写入 · 高风险'}</span></div><small>${escapeHtml(tool.description || tool.remote_name)}</small><code>${escapeHtml(tool.remote_name)}</code></div><div class="mcp-tool-actions">${testAction}<button class="btn ${tool.enabled ? 'btn-secondary' : 'btn-primary'} mcp-tool-toggle-button" type="button">${tool.enabled ? '停用' : '启用'}</button></div>`;
                row.querySelector('.mcp-tool-toggle-button').addEventListener('click', () => setMCPToolState(server.server_id, tool.tool_id, !tool.enabled));
                row.querySelector('.mcp-tool-test-button')?.addEventListener('click', () => selectMCPExternalTool(server.server_id, tool.tool_id));
                list.appendChild(row);
            }
        }

        async function saveMCPServer() {
            const payload = {
                name: document.getElementById('mcpNameInput').value.trim(),
                endpoint: document.getElementById('mcpEndpointInput').value.trim(),
                auth_type: document.getElementById('mcpAuthTypeInput').value,
                credential_ref: document.getElementById('mcpCredentialRefInput').value.trim() || null,
                auth_header: document.getElementById('mcpAuthHeaderInput').value.trim(),
                timeout_seconds: Number(document.getElementById('mcpTimeoutInput').value || 20),
                description: document.getElementById('mcpDescriptionInput').value.trim(),
                transport: 'streamable_http',
            };
            if (!payload.name || !payload.endpoint) { showMCPNotice('请填写 Server 名称和 Endpoint。', true); return; }
            try {
                const isNew = !mcpState.selectedId;
                const result = await apiFetch(isNew ? '/mcp/servers' : `/mcp/servers/${encodeURIComponent(mcpState.selectedId)}`, {
                    method: isNew ? 'POST' : 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
                });
                showMCPNotice(isNew ? 'MCP Server 已保存为草稿，请运行完整校验。' : 'MCP Server 配置已保存；连接配置变化后需要重新校验。');
                await loadMCPServers(result.server_id);
            } catch (error) { showMCPNotice(error.message || 'MCP Server 保存失败', true); }
        }

        async function validateMCPServer() {
            if (!mcpState.selectedId) { showMCPNotice('请先保存 MCP Server。', true); return; }
            const selected = document.getElementById('mcpValidationSelect').value || 'all';
            try {
                const result = await apiFetch(`/mcp/servers/${encodeURIComponent(mcpState.selectedId)}/validate`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ checks: [selected] }),
                });
                mcpState.selected = result;
                showMCPNotice(result.validation_status === 'passed' ? '完整校验通过，可以启用 Server。' : '校验已完成，请根据结果修正配置或策略。', result.validation_status !== 'passed');
                await loadMCPServers(mcpState.selectedId);
            } catch (error) { showMCPNotice(error.message || 'MCP 校验失败', true); }
        }

        async function toggleMCPServer() {
            if (!mcpState.selectedId) return;
            const enabled = Boolean(mcpState.selected?.enabled);
            if (!enabled && !window.confirm('启用后，已启用的 MCP Tool 会进入 Agent Runtime，并遵守权限、确认和审计门禁。继续吗？')) return;
            try {
                await apiFetch(`/mcp/servers/${encodeURIComponent(mcpState.selectedId)}/${enabled ? 'disable' : 'enable'}`, { method: 'POST' });
                showMCPNotice(enabled ? 'MCP Server 已停用。' : 'MCP Server 已启用；可继续逐个启用 Tool。');
                await loadMCPServers(mcpState.selectedId);
            } catch (error) { showMCPNotice(error.message || 'MCP Server 状态更新失败', true); }
        }

        async function setMCPToolState(serverId, toolId, enabled) {
            try {
                await apiFetch(`/mcp/servers/${encodeURIComponent(serverId)}/tools/${encodeURIComponent(toolId)}/${enabled ? 'enable' : 'disable'}`, { method: 'POST' });
                showMCPNotice(enabled ? 'MCP Tool 已启用并进入 Runtime Registry。' : 'MCP Tool 已停用。');
                await loadMCPServers(serverId);
            } catch (error) { showMCPNotice(error.message || 'MCP Tool 状态更新失败', true); }
        }

        function hideMCPExternalTestPanel() {
            const panel = document.getElementById('mcpExternalTestPanel');
            if (panel) panel.hidden = true;
            mcpState.selectedExternalTool = null;
        }

        function selectMCPExternalTool(serverId, toolId) {
            const server = mcpState.servers.find(item => String(item.server_id) === String(serverId));
            const tool = server?.tools?.find(item => String(item.tool_id) === String(toolId));
            if (!server || !tool) return;
            const readOnly = tool.annotations?.readOnlyHint === true && tool.annotations?.destructiveHint !== true;
            if (!readOnly || !tool.enabled) {
                showMCPNotice(readOnly ? '请先启用该 MCP Tool，再执行只读测试。' : '外部 MCP 写 Tool 不支持管理台直测。', true);
                return;
            }
            mcpState.selectedExternalTool = { serverId: server.server_id, toolId: tool.tool_id, tool };
            const panel = document.getElementById('mcpExternalTestPanel');
            if (!panel) return;
            panel.hidden = false;
            document.getElementById('mcpExternalSelectedName').textContent = tool.title || tool.remote_name;
            document.getElementById('mcpExternalSelectedDescription').textContent = `${tool.description || tool.remote_name}；这是只读测试，会沿用 Runtime Schema、权限和审计。`;
            document.getElementById('mcpExternalInput').value = JSON.stringify({}, null, 2);
            document.getElementById('mcpExternalTestStatus').textContent = '';
            document.getElementById('mcpExternalResult').textContent = '尚未测试';
        }

        async function testMCPTool() {
            const selected = mcpState.selectedExternalTool;
            if (!selected) return;
            let input;
            try { input = JSON.parse(document.getElementById('mcpExternalInput').value || '{}'); } catch (_) { showMCPNotice('JSON 输入格式不正确。', true); return; }
            if (!input || typeof input !== 'object' || Array.isArray(input)) { showMCPNotice('JSON 输入必须是 object。', true); return; }
            const button = document.getElementById('mcpExternalTestButton');
            const status = document.getElementById('mcpExternalTestStatus');
            button.disabled = true;
            status.textContent = '测试中…';
            try {
                const result = await apiFetch(`/mcp/servers/${encodeURIComponent(selected.serverId)}/tools/${encodeURIComponent(selected.toolId)}/test`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ input, account_id: document.getElementById('mcpExternalAccountInput').value.trim() || null }),
                });
                document.getElementById('mcpExternalResult').textContent = JSON.stringify(result, null, 2);
                status.textContent = result.success ? '测试成功' : '测试完成但 Tool 返回失败';
                showMCPNotice(result.success ? '外部 MCP 只读 Tool 测试完成。' : '外部 MCP Tool 返回失败。', !result.success);
            } catch (error) {
                document.getElementById('mcpExternalResult').textContent = error.message || 'Tool 测试失败';
                status.textContent = '测试失败';
                showMCPNotice(error.message || '外部 MCP Tool 测试失败', true);
            } finally { button.disabled = false; }
        }

        async function deleteMCPServer() {
            if (!mcpState.selectedId || !window.confirm('移除后会停用 Server 和全部 Tool，但保留控制面审计记录。继续吗？')) return;
            try {
                await apiFetch(`/mcp/servers/${encodeURIComponent(mcpState.selectedId)}`, { method: 'DELETE' });
                showMCPNotice('MCP Server 已移除。');
                mcpState.selectedId = '';
                await loadMCPServers();
            } catch (error) { showMCPNotice(error.message || 'MCP Server 移除失败', true); }
        }

        function toggleBuiltinMCPPanel() {
            const panel = document.getElementById('mcpBuiltinPanel');
            if (!panel) return;
            const opening = panel.hidden;
            panel.hidden = !opening;
            if (opening) loadBuiltinMCPTools();
        }

        async function loadBuiltinMCPTools() {
            try {
                const data = await apiFetch('/mcp/builtin/tools');
                mcpState.builtinTools = Array.isArray(data.tools) ? data.tools : [];
                const meta = document.getElementById('mcpBuiltinMeta');
                if (meta) meta.textContent = `${mcpState.builtinTools.length} 个 Registry Tool · ${data.enabled ? 'HTTP MCP 已开启' : 'HTTP 暴露默认关闭'}`;
                renderBuiltinMCPTools();
                if (!mcpState.selectedBuiltin && mcpState.builtinTools[0]) selectBuiltinMCPTool(mcpState.builtinTools[0].name);
            } catch (error) {
                mcpState.builtinTools = [];
                renderBuiltinMCPTools();
                showMCPNotice(error.message || '渠道 Tool 目录读取失败', true);
            }
        }

        function filterBuiltinMCPTools() {
            renderBuiltinMCPTools();
        }

        function renderBuiltinMCPTools() {
            const list = document.getElementById('mcpBuiltinToolList');
            if (!list) return;
            const query = (document.getElementById('mcpBuiltinSearch')?.value || '').trim().toLowerCase();
            const tools = mcpState.builtinTools.filter(tool => !query || `${tool.name} ${tool.namespace} ${tool.description} ${tool.action} ${tool.resource_type}`.toLowerCase().includes(query));
            list.replaceChildren();
            if (!tools.length) {
                const empty = document.createElement('div');
                empty.className = 'mcp-empty';
                empty.textContent = query ? '没有匹配的渠道 Tool。' : '当前 Runtime 没有已注册的 Tool。';
                list.appendChild(empty);
                return;
            }
            for (const tool of tools) {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = `mcp-builtin-tool-item${mcpState.selectedBuiltin?.name === tool.name ? ' active' : ''}`;
                const name = document.createElement('strong');
                name.textContent = tool.name;
                const detail = document.createElement('small');
                detail.textContent = `${tool.namespace} · ${tool.action || 'invoke'} · ${tool.effect_class}`;
                button.append(name, detail);
                button.addEventListener('click', () => selectBuiltinMCPTool(tool.name));
                list.appendChild(button);
            }
        }

        function selectBuiltinMCPTool(toolName) {
            const tool = mcpState.builtinTools.find(item => item.name === toolName);
            if (!tool) return;
            mcpState.selectedBuiltin = tool;
            document.getElementById('mcpBuiltinSelectedName').textContent = tool.name;
            document.getElementById('mcpBuiltinSelectedDescription').textContent = `${tool.description} 所需权限：${(tool.required_permissions || []).join(', ') || '无'}；${tool.effect_class === 'read' ? '可执行只读测试' : '写入只生成 dry-run 模拟结果'}`;
            document.getElementById('mcpBuiltinInput').value = JSON.stringify({
                ...(tool.input_schema?.properties ? Object.fromEntries(Object.entries(tool.input_schema.properties).filter(([, value]) => value.default !== undefined).map(([key, value]) => [key, value.default])) : {}),
            }, null, 2);
            document.getElementById('mcpBuiltinTestButton').disabled = false;
            document.getElementById('mcpBuiltinTestStatus').textContent = '';
            renderBuiltinMCPTools();
        }

        async function testBuiltinMCPTool() {
            const tool = mcpState.selectedBuiltin;
            if (!tool) return;
            let input;
            try { input = JSON.parse(document.getElementById('mcpBuiltinInput').value || '{}'); } catch (_) { showMCPNotice('JSON 输入格式不正确。', true); return; }
            if (!input || typeof input !== 'object' || Array.isArray(input)) { showMCPNotice('JSON 输入必须是 object。', true); return; }
            const button = document.getElementById('mcpBuiltinTestButton');
            const status = document.getElementById('mcpBuiltinTestStatus');
            button.disabled = true;
            status.textContent = '测试中…';
            try {
                const result = await apiFetch(`/mcp/builtin/tools/${encodeURIComponent(tool.name)}/test`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ input, account_id: document.getElementById('mcpBuiltinAccountInput').value.trim() || null }),
                });
                document.getElementById('mcpBuiltinResult').textContent = JSON.stringify(result, null, 2);
                status.textContent = result.success ? '测试成功' : '测试完成但 Tool 返回失败';
                showMCPNotice(result.mode === 'dry_run' ? 'Tool 测试完成；写入能力只生成 dry-run 结果。' : 'Tool 测试完成。', !result.success);
            } catch (error) {
                document.getElementById('mcpBuiltinResult').textContent = error.message || 'Tool 测试失败';
                status.textContent = '测试失败';
                showMCPNotice(error.message || '渠道 Tool 测试失败', true);
            } finally { button.disabled = false; }
        }
