        const agentSettingsState = {
            snapshot: null,
            provider: 'google',
            tab: 'models',
        };

        const providerCredentialFields = {
            google: [
                ['client_id', 'OAuth Client ID'],
                ['client_secret', 'OAuth Client Secret'],
                ['developer_token', 'Developer Token'],
                ['refresh_token', 'Refresh Token'],
                ['access_token', 'Access Token'],
                ['login_customer_id', 'Login Customer ID'],
            ],
            meta: [
                ['access_token', 'Access Token'],
                ['business_id', 'Business ID'],
            ],
            tiktok: [
                ['app_key', 'App Key'],
                ['app_secret', 'App Secret'],
                ['access_token', 'Access Token'],
                ['bc_id', 'Business Center ID'],
            ],
        };

        async function settingsRequest(url, options = {}) {
            const response = await serviceFetch(url, {
                ...options,
                headers: {
                    'Content-Type': 'application/json',
                    ...(options.headers || {}),
                },
            });
            const text = await response.text();
            let payload = {};
            try {
                payload = text ? JSON.parse(text) : {};
            } catch (_) {
                payload = {};
            }
            if (!response.ok) {
                throw new Error(payload.detail || `请求失败（${response.status}）`);
            }
            return payload;
        }
        function setAgentSettingsStatus(message, isError = false) {
            const status = document.getElementById('agentSettingsStatus');
            if (!status) return;
            status.textContent = message || '';
            status.className = `service-settings-status${message ? ' active' : ''}${isError ? ' error' : ''}`;
        }

        function isSecureSettingsOrigin() {
            if (typeof location === 'undefined') return false;
            if (location.protocol === 'https:') return true;
            const host = String(location.hostname || '')
                .toLowerCase()
                .replace(/^\[|\]$/g, '');
            return host === 'localhost'
                || host === '0.0.0.0'
                || host === '::1'
                || /^127(?:\.\d{1,3}){3}$/.test(host);
        }

        function openAgentSettings(tab = 'models') {
            closeWorkspacePopovers();
            const overlay = document.getElementById('agentSettingsOverlay');
            if (!overlay) return;
            overlay.classList.add('active');
            overlay.setAttribute('aria-hidden', 'false');
            selectAgentSettingsTab(tab);
            loadAgentSettings();
        }

        function closeAgentSettings() {
            const overlay = document.getElementById('agentSettingsOverlay');
            overlay?.classList.remove('active');
            overlay?.setAttribute('aria-hidden', 'true');
        }

        function selectAgentSettingsTab(tab) {
            agentSettingsState.tab = tab === 'providers' ? 'providers' : 'models';
            const modelsActive = agentSettingsState.tab === 'models';
            const modelsTab = document.getElementById('settingsModelsTab');
            const providersTab = document.getElementById('settingsProvidersTab');
            const modelsPanel = document.getElementById('settingsModelsPanel');
            const providersPanel = document.getElementById('settingsProvidersPanel');
            modelsTab?.classList.toggle('active', modelsActive);
            modelsTab?.setAttribute('aria-selected', String(modelsActive));
            providersTab?.classList.toggle('active', !modelsActive);
            providersTab?.setAttribute('aria-selected', String(!modelsActive));
            if (modelsPanel) modelsPanel.hidden = !modelsActive;
            if (providersPanel) providersPanel.hidden = modelsActive;
            if (!modelsActive) renderAgentProviderFields();
        }

        async function loadAgentSettings() {
            setAgentSettingsStatus('读取配置中…');
            try {
                agentSettingsState.snapshot = await settingsRequest('/settings');
                renderAgentModelProfiles();
                renderAgentProviderFields();
                setAgentSettingsStatus('');
            } catch (error) {
                setAgentSettingsStatus(error.message || '读取设置失败。', true);
            }
        }

        function renderAgentModelProfiles() {
            const list = document.getElementById('agentModelProfileList');
            const settings = agentSettingsState.snapshot?.models;
            if (!list || !settings) return;
            list.replaceChildren();
            for (const profile of settings.profiles || []) {
                const row = document.createElement('div');
                row.className = `service-settings-profile${profile.active ? ' active' : ''}`;
                const activate = document.createElement('button');
                activate.className = 'service-settings-profile-main';
                activate.type = 'button';
                activate.setAttribute(
                    'aria-current',
                    profile.active ? 'true' : 'false',
                );
                const name = document.createElement('strong');
                name.textContent = profile.name || '未命名配置';
                const model = document.createElement('span');
                model.textContent = profile.model || '未配置模型 ID';
                const status = document.createElement('small');
                status.textContent = profile.active
                    ? '当前使用'
                    : (profile.api_key_configured ? '已配置 Key' : '未配置 Key');
                activate.append(name, model, status);
                activate.addEventListener('click', () => activateAgentModelProfile(profile.id));
                row.appendChild(activate);

                if (profile.source === 'vault') {
                    const actions = document.createElement('div');
                    actions.className = 'service-settings-profile-actions';
                    const edit = document.createElement('button');
                    edit.type = 'button';
                    edit.className = 'btn btn-secondary';
                    edit.textContent = '编辑';
                    edit.addEventListener('click', () => editAgentModelProfile(profile));
                    actions.appendChild(edit);
                    if (!profile.active) {
                        const remove = document.createElement('button');
                        remove.type = 'button';
                        remove.className = 'btn btn-secondary';
                        remove.textContent = '删除';
                        remove.addEventListener('click', () => deleteAgentModelProfile(profile));
                        actions.appendChild(remove);
                    }
                    row.appendChild(actions);
                }
                list.appendChild(row);
            }
            if (!list.childElementCount) {
                const empty = document.createElement('div');
                empty.className = 'service-settings-empty';
                empty.textContent = '暂无模型配置。';
                list.appendChild(empty);
            }
            if (!document.getElementById('agentModelProfileId')?.value) {
                const active = (settings.profiles || []).find(item => item.active);
                if (active?.source === 'vault') editAgentModelProfile(active);
                else {
                    const form = document.getElementById('agentModelForm');
                    if (form) form.reset();
                }
            }
        }

        function newAgentModelProfile() {
            const form = document.getElementById('agentModelForm');
            form?.reset();
            const profileId = document.getElementById('agentModelProfileId');
            if (profileId) profileId.value = '';
            setAgentSettingsStatus('');
            document.getElementById('agentModelName')?.focus();
        }

        function editAgentModelProfile(profile) {
            document.getElementById('agentModelProfileId').value = profile.id;
            document.getElementById('agentModelName').value = profile.name || '';
            document.getElementById('agentModelId').value = profile.model || '';
            document.getElementById('agentModelBaseUrl').value = profile.base_url || '';
            document.getElementById('agentModelApiKey').value = '';
            setAgentSettingsStatus('');
        }

        async function saveAgentModelProfile(event) {
            event?.preventDefault();
            if (!isSecureSettingsOrigin()) {
                setAgentSettingsStatus('远程连接请使用 HTTPS 后再保存模型密钥。', true);
                return;
            }
            const profileId = document.getElementById('agentModelProfileId')?.value || '';
            const body = {
                name: document.getElementById('agentModelName')?.value || '',
                model: document.getElementById('agentModelId')?.value || '',
                base_url: document.getElementById('agentModelBaseUrl')?.value || '',
                api_key: document.getElementById('agentModelApiKey')?.value || '',
            };
            setAgentSettingsStatus('保存并切换中…');
            try {
                const url = profileId
                    ? `/settings/models/${encodeURIComponent(profileId)}`
                    : '/settings/models';
                agentSettingsState.snapshot = await settingsRequest(url, {
                    method: profileId ? 'PUT' : 'POST',
                    body: JSON.stringify(body),
                });
                document.getElementById('agentModelApiKey').value = '';
                document.getElementById('agentModelProfileId').value = '';
                renderAgentModelProfiles();
                setAgentSettingsStatus('模型配置已保存并切换。');
            } catch (error) {
                setAgentSettingsStatus(error.message || '模型配置保存失败。', true);
            }
        }

        async function activateAgentModelProfile(profileId) {
            setAgentSettingsStatus('切换模型中…');
            try {
                agentSettingsState.snapshot = await settingsRequest(
                    `/settings/models/${encodeURIComponent(profileId)}/activate`,
                    { method: 'POST' },
                );
                document.getElementById('agentModelProfileId').value = '';
                renderAgentModelProfiles();
                setAgentSettingsStatus('当前模型已切换。');
            } catch (error) {
                setAgentSettingsStatus(error.message || '模型切换失败。', true);
            }
        }

        async function deleteAgentModelProfile(profile) {
            if (!window.confirm(`删除模型配置“${profile.name}”？`)) return;
            setAgentSettingsStatus('删除中…');
            try {
                agentSettingsState.snapshot = await settingsRequest(
                    `/settings/models/${encodeURIComponent(profile.id)}`,
                    { method: 'DELETE' },
                );
                document.getElementById('agentModelProfileId').value = '';
                renderAgentModelProfiles();
                setAgentSettingsStatus('模型配置已删除。');
            } catch (error) {
                setAgentSettingsStatus(error.message || '删除模型配置失败。', true);
            }
        }

        function selectSettingsProvider(provider) {
            if (!providerCredentialFields[provider]) return;
            agentSettingsState.provider = provider;
            document.querySelectorAll('.service-provider-tab').forEach(button => {
                button.classList.toggle('active', button.dataset.provider === provider);
                button.setAttribute(
                    'aria-selected',
                    String(button.dataset.provider === provider),
                );
            });
            renderAgentProviderFields();
        }

        function renderAgentProviderFields() {
            const container = document.getElementById('agentProviderFields');
            if (!container) return;
            const provider = agentSettingsState.provider;
            const fields = providerCredentialFields[provider] || [];
            const configured = agentSettingsState.snapshot?.providers?.[provider]?.fields || {};
            container.replaceChildren();
            for (const [field, label] of fields) {
                const row = document.createElement('div');
                row.className = 'service-provider-field';
                const fieldLabel = document.createElement('label');
                fieldLabel.className = 'service-settings-field';
                fieldLabel.textContent = label;
                const input = document.createElement('input');
                input.type = 'password';
                input.name = field;
                input.autocomplete = 'new-password';
                input.spellcheck = false;
                input.maxLength = 8192;
                input.placeholder = configured[field] ? '已配置，留空保持不变' : '输入密钥或凭证';
                fieldLabel.appendChild(input);
                const fieldStatus = document.createElement('span');
                fieldStatus.className = `service-provider-field-status${configured[field] ? ' configured' : ''}`;
                fieldStatus.textContent = configured[field] ? '已配置' : '未配置';
                const clearLabel = document.createElement('label');
                clearLabel.className = 'service-provider-clear';
                const clearInput = document.createElement('input');
                clearInput.type = 'checkbox';
                clearInput.name = `clear:${field}`;
                clearInput.addEventListener('change', () => {
                    input.disabled = clearInput.checked;
                    input.value = '';
                });
                const clearText = document.createElement('span');
                clearText.textContent = '清除';
                clearLabel.append(clearInput, clearText);
                row.append(fieldLabel, fieldStatus, clearLabel);
                container.appendChild(row);
            }
        }

        async function saveAgentProviderCredentials(event) {
            event?.preventDefault();
            if (!isSecureSettingsOrigin()) {
                setAgentSettingsStatus('远程连接请使用 HTTPS 后再保存渠道密钥。', true);
                return;
            }
            const form = document.getElementById('agentProviderForm');
            if (!form) return;
            const fields = {};
            const clearFields = [];
            for (const [field] of providerCredentialFields[agentSettingsState.provider]) {
                const input = form.elements.namedItem(field);
                const clear = form.elements.namedItem(`clear:${field}`);
                const value = String(input?.value || '').trim();
                if (clear?.checked) clearFields.push(field);
                else if (value) fields[field] = value;
            }
            setAgentSettingsStatus('保存渠道凭证中…');
            try {
                agentSettingsState.snapshot = await settingsRequest(
                    `/settings/providers/${encodeURIComponent(agentSettingsState.provider)}`,
                    {
                        method: 'PUT',
                        body: JSON.stringify({ fields, clear_fields: clearFields }),
                    },
                );
                renderAgentProviderFields();
                setAgentSettingsStatus('渠道凭证已保存。');
            } catch (error) {
                setAgentSettingsStatus(error.message || '渠道凭证保存失败。', true);
            }
        }
