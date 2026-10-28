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
            ga4: [
                ['client_id', 'OAuth Client ID'],
                ['client_secret', 'OAuth Client Secret'],
                ['refresh_token', 'OAuth Refresh Token'],
            ],
            search_console: [
                ['client_id', 'OAuth Client ID'],
                ['client_secret', 'OAuth Client Secret'],
                ['refresh_token', 'OAuth Refresh Token'],
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
            agentSettingsState.tab = ['providers', 'web-search'].includes(tab)
                ? tab
                : 'models';
            const modelsActive = agentSettingsState.tab === 'models';
            const providersActive = agentSettingsState.tab === 'providers';
            const webSearchActive = agentSettingsState.tab === 'web-search';
            const modelsTab = document.getElementById('settingsModelsTab');
            const providersTab = document.getElementById('settingsProvidersTab');
            const webSearchTab = document.getElementById('settingsWebSearchTab');
            const modelsPanel = document.getElementById('settingsModelsPanel');
            const providersPanel = document.getElementById('settingsProvidersPanel');
            const webSearchPanel = document.getElementById('settingsWebSearchPanel');
            modelsTab?.classList.toggle('active', modelsActive);
            modelsTab?.setAttribute('aria-selected', String(modelsActive));
            providersTab?.classList.toggle('active', providersActive);
            providersTab?.setAttribute('aria-selected', String(providersActive));
            webSearchTab?.classList.toggle('active', webSearchActive);
            webSearchTab?.setAttribute('aria-selected', String(webSearchActive));
            if (modelsPanel) modelsPanel.hidden = !modelsActive;
            if (providersPanel) providersPanel.hidden = !providersActive;
            if (webSearchPanel) webSearchPanel.hidden = !webSearchActive;
            if (providersActive) renderAgentProviderFields();
            if (webSearchActive) renderWebSearchSettings();
        }

        async function loadAgentSettings() {
            setAgentSettingsStatus('读取配置中…');
            try {
                agentSettingsState.snapshot = await settingsRequest('/settings');
                renderAgentModelProfiles();
                renderAgentProviderFields();
                renderWebSearchSettings();
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
                const purposeLabels = {
                    chat: '对话与文案',
                    knowledge_embedding: '知识库语义检索',
                    image_generation: '图片生成',
                    video_generation: '视频生成',
                };
                model.textContent = `${purposeLabels[profile.purpose] || '对话与文案'} · ${profile.model || '未配置模型 ID'}`;
                const status = document.createElement('small');
                status.textContent = profile.supported === false
                    ? '已禁用：请更换为免费 Agnes Flash'
                    : profile.active
                        ? '当前使用'
                        : (profile.api_key_configured ? '已配置 Key' : '未配置 Key');
                activate.append(name, model, status);
                activate.disabled = profile.supported === false;
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
            renderAgentMediaModelCatalog();
            if (!document.getElementById('agentModelProfileId')?.value) {
                const active = (settings.profiles || []).find(item => item.active);
                if (active?.source === 'vault') editAgentModelProfile(active);
                else {
                    const form = document.getElementById('agentModelForm');
                    if (form) form.reset();
                    updateAgentModelChoices();
                }
            }
        }

        function renderAgentMediaModelCatalog() {
            const list = document.getElementById('agentMediaModelCatalog');
            if (!list) return;
            const catalog = agentSettingsState.snapshot?.media_model_catalog || {};
            const profiles = agentSettingsState.snapshot?.models?.profiles || [];
            list.replaceChildren();
            const available = Object.entries(catalog).filter(([purpose]) => {
                const profile = profiles.find(item => item.purpose === purpose);
                return !profile
                    || profile.supported === false
                    || !profile.api_key_configured;
            });
            if (!available.length) {
                const configured = document.createElement('div');
                configured.className = 'service-settings-empty';
                configured.textContent = '图片与视频模型都已配置，可在上方列表中编辑。';
                list.appendChild(configured);
                return;
            }
            for (const [purpose, option] of available) {
                const profile = profiles.find(item => item.purpose === purpose);
                const row = document.createElement('div');
                row.className = `service-settings-profile${profile?.active ? ' active' : ''}`;
                const choose = document.createElement('button');
                choose.className = 'service-settings-profile-main';
                choose.type = 'button';
                choose.addEventListener('click', () => configureMediaModel(purpose));
                const name = document.createElement('strong');
                name.textContent = option.name || option.model;
                const model = document.createElement('span');
                model.textContent = option.model || '';
                const status = document.createElement('small');
                status.textContent = option.availability === 'free_limited_time'
                    ? '免费（限时）'
                    : '免费';
                choose.append(name, model, status);
                row.appendChild(choose);
                const details = document.createElement('div');
                details.className = 'service-settings-model-catalog-status';
                details.textContent = profile?.supported === false
                    ? '旧配置已禁用，点击后替换为当前免费型号'
                    : profile?.api_key_configured
                        ? '已配置，可点击编辑'
                        : '未配置 API Key';
                row.appendChild(details);
                list.appendChild(row);
            }
        }

        function configureMediaModel(purpose) {
            const settings = agentSettingsState.snapshot;
            const option = settings?.media_model_catalog?.[purpose];
            if (!option) return;
            const existing = (settings.models?.profiles || []).find(
                profile => profile.purpose === purpose && profile.source === 'vault',
            );
            if (existing) {
                editAgentModelProfile(existing);
            } else {
                newAgentModelProfile();
                document.getElementById('agentModelPurpose').value = purpose;
                updateAgentModelChoices();
                document.getElementById('agentModelName').value = option.name || '';
            }
            document.getElementById('agentModelApiKey')?.focus();
            setAgentSettingsStatus(
                `${option.name} 已选定。填写 Agnes API Key 后保存即可使用。`,
            );
        }

        function updateAgentModelChoices({ preserveChatModel = false } = {}) {
            const purpose = document.getElementById('agentModelPurpose')?.value || 'chat';
            const model = document.getElementById('agentModelId');
            const baseUrl = document.getElementById('agentModelBaseUrl');
            const hint = document.getElementById('agentModelHint');
            if (!model) return;
            const option = agentSettingsState.snapshot?.media_model_catalog?.[purpose];
            if (option) {
                model.value = option.model || '';
                model.readOnly = true;
                model.title = '仅允许当前 Agnes 免费型号';
                if (baseUrl) {
                    baseUrl.value = option.base_url || '';
                    baseUrl.placeholder = '使用 Agnes 官方 API';
                    baseUrl.readOnly = true;
                }
                if (hint) {
                    hint.textContent = option.availability === 'free_limited_time'
                        ? '仅接入当前免费 Flash 型号；视频模型为限时免费。'
                        : '仅接入当前最新免费 Flash 型号；收费型号不会被启用。';
                }
                return;
            }
            const wasReadOnly = model.readOnly;
            model.readOnly = false;
            model.title = '';
            if (wasReadOnly && !preserveChatModel) {
                model.value = '';
                if (baseUrl) baseUrl.value = '';
            }
            if (baseUrl) {
                baseUrl.readOnly = false;
                baseUrl.placeholder = '留空使用 SDK 默认地址';
            }
            if (hint) hint.textContent = '对话模型由当前模型服务商配置。';
        }

        function newAgentModelProfile() {
            const form = document.getElementById('agentModelForm');
            form?.reset();
            const profileId = document.getElementById('agentModelProfileId');
            if (profileId) profileId.value = '';
            const purpose = document.getElementById('agentModelPurpose');
            if (purpose) {
                purpose.value = 'chat';
                purpose.disabled = false;
            }
            updateAgentModelChoices();
            setAgentSettingsStatus('');
            document.getElementById('agentModelName')?.focus();
        }

        function editAgentModelProfile(profile) {
            document.getElementById('agentModelProfileId').value = profile.id;
            document.getElementById('agentModelName').value = profile.name || '';
            document.getElementById('agentModelPurpose').value = profile.purpose || 'chat';
            document.getElementById('agentModelPurpose').disabled = true;
            document.getElementById('agentModelId').value = profile.model || '';
            document.getElementById('agentModelBaseUrl').value = profile.base_url || '';
            document.getElementById('agentModelApiKey').value = '';
            updateAgentModelChoices({ preserveChatModel: true });
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
                purpose: document.getElementById('agentModelPurpose')?.value || 'chat',
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
                setAgentSettingsStatus('模型配置已保存并切换；对话、图片和视频模型互不影响。');
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
            const hint = document.getElementById('providerCredentialsHint');
            if (hint) {
                const hints = {
                    ga4: '使用具有 GA4 属性只读权限的 Google OAuth Refresh Token（scope: https://www.googleapis.com/auth/analytics.readonly）。Google Ads 的 Refresh Token 不能保证包含此权限。',
                    search_console: '使用具有 Search Console 站点只读权限的 Google OAuth Refresh Token（scope: https://www.googleapis.com/auth/webmasters.readonly）。Google Ads 的 Refresh Token 不能保证包含此权限。',
                };
                hint.textContent = hints[provider] || '';
            }
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
            setAgentSettingsStatus('保存凭证中…');
            try {
                agentSettingsState.snapshot = await settingsRequest(
                    `/settings/providers/${encodeURIComponent(agentSettingsState.provider)}`,
                    {
                        method: 'PUT',
                        body: JSON.stringify({ fields, clear_fields: clearFields }),
                    },
                );
                renderAgentProviderFields();
                setAgentSettingsStatus('凭证已保存。');
            } catch (error) {
                setAgentSettingsStatus(error.message || '凭证保存失败。', true);
            }
        }

        function renderWebSearchSettings() {
            const settings = agentSettingsState.snapshot?.web_search || {};
            const provider = document.getElementById('webSearchProvider');
            if (provider && ['duckduckgo', 'brave'].includes(settings.backend)) {
                provider.value = settings.backend;
            }
            const apiKeyInput = document.getElementById('webSearchApiKey');
            if (apiKeyInput) apiKeyInput.value = '';
            const clearKeyInput = document.getElementById('webSearchClearKey');
            if (clearKeyInput) clearKeyInput.checked = false;
            if (provider) {
                provider.disabled = settings.provider_source === 'environment';
            }
            toggleWebSearchProviderFields();
        }

        function toggleWebSearchProviderFields() {
            const settings = agentSettingsState.snapshot?.web_search || {};
            const provider = document.getElementById('webSearchProvider');
            const input = document.getElementById('webSearchApiKey');
            const keyField = document.getElementById('webSearchApiKeyField');
            const status = document.getElementById('webSearchKeyStatus');
            const clear = document.getElementById('webSearchClearKey');
            const selectedBackend = provider?.value === 'brave'
                ? 'brave'
                : 'duckduckgo';
            const currentBackend = settings.backend === 'brave'
                ? 'brave'
                : 'duckduckgo';
            const isBrave = selectedBackend === 'brave';
            if (keyField) keyField.hidden = !isBrave;
            if (input) {
                input.placeholder = settings.api_key_configured
                    ? '已配置，留空表示不轮换'
                    : '输入 Brave Search API Key';
            }
            if (status) {
                const source = settings.source === 'environment'
                    ? '环境变量'
                    : settings.source === 'vault' ? '加密设置' : '';
                const message = selectedBackend !== currentBackend
                    ? isBrave
                        ? settings.api_key_configured
                            ? '保存后将切换到 Brave Search'
                            : '切换后需要配置 Brave Search API Key'
                        : '保存后将切换到免 Key 的 DuckDuckGo'
                    : isBrave
                        ? settings.api_key_configured
                            ? `Brave Search 已配置${source ? ` · ${source}` : ''}`
                            : 'Brave Search 需要 API Key 才能搜索'
                        : 'DuckDuckGo 已选中，无需 API Key 或独立搜索服务';
                status.textContent = message;
                status.className = `service-provider-field-status${isBrave && settings.api_key_configured ? ' configured' : ''}`;
            }
            if (input) input.disabled = !isBrave;
            if (clear) clear.closest('.service-provider-clear')?.toggleAttribute(
                'hidden',
                !isBrave || !settings.api_key_configured,
            );
        }

        function toggleWebSearchKeyInput() {
            const input = document.getElementById('webSearchApiKey');
            const clear = document.getElementById('webSearchClearKey');
            if (!input || !clear) return;
            input.disabled = clear.checked;
            if (clear.checked) input.value = '';
        }

        async function saveWebSearchCredentials(event) {
            event?.preventDefault();
            const provider = String(
                document.getElementById('webSearchProvider')?.value || 'duckduckgo',
            );
            const apiKey = provider === 'brave'
                ? String(
                    document.getElementById('webSearchApiKey')?.value || '',
                ).trim()
                : '';
            const clear = provider === 'brave' && Boolean(
                document.getElementById('webSearchClearKey')?.checked,
            );
            if ((apiKey || clear) && !isSecureSettingsOrigin()) {
                setAgentSettingsStatus('远程连接请使用 HTTPS 后再保存网页搜索密钥。', true);
                return;
            }
            if (apiKey && clear) {
                setAgentSettingsStatus('不能同时更新和清除密钥。', true);
                return;
            }
            setAgentSettingsStatus('保存网页搜索密钥中…');
            try {
                agentSettingsState.snapshot = await settingsRequest(
                    '/settings/web-search',
                    {
                        method: 'PUT',
                        body: JSON.stringify({
                            provider,
                            api_key: apiKey,
                            clear,
                        }),
                    },
                );
                renderWebSearchSettings();
                setAgentSettingsStatus('网页搜索密钥设置已保存。');
            } catch (error) {
                setAgentSettingsStatus(error.message || '网页搜索密钥保存失败。', true);
            }
        }
