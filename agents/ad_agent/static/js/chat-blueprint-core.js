        function openBlueprintManager(provider = null, selectorValue = null, blueprintId = null, mode = 'wizard') {
            blueprintState.mode = mode === 'templates' ? 'templates' : 'wizard';
            closeWorkspacePopovers();
            const overlay = document.getElementById('blueprintOverlay');
            if (!overlay) return;
            const title = document.getElementById('blueprintConsoleTitle');
            const subtitle = document.querySelector('.blueprint-console-subtitle');
            if (blueprintState.mode === 'templates') {
                if (title) title.textContent = '模板管理';
                if (subtitle) subtitle.textContent = '管理已保存的创建参数模板；模板只负责复用参数，不替代广告创建向导。';
            } else {
                if (title) title.textContent = '广告创建向导';
                if (subtitle) subtitle.textContent = '选择渠道与投放目标，按业务阶段完成参数；系统会实时校验联动关系，当前只生成草稿。';
            }
            overlay.classList.add('active');
            overlay.setAttribute('aria-hidden', 'false');
            loadCreationBlueprints(blueprintId || null).then(() => {
                if (!provider) return;
                const item = blueprintState.items.find(candidate =>
                    candidate.provider === provider && (
                        (blueprintId && candidate.id === blueprintId)
                        || (!blueprintId && (!selectorValue || (candidate.selector?.values || []).map(String).includes(String(selectorValue))))
                    )
                );
                if (item) selectBlueprint(item.id, selectorValue);
            });
        }

        function openCreationTemplateManager() {
            openBlueprintManager(null, null, null, 'templates');
        }

        function closeBlueprintManager() {
            document.getElementById('blueprintOverlay')?.classList.remove('active');
            document.getElementById('blueprintOverlay')?.setAttribute('aria-hidden', 'true');
        }

        function focusBlueprintIssue() {
            const account = document.getElementById('blueprintAccountInput');
            if (!String(account?.value || '').trim()) {
                account?.focus();
                account?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                return;
            }
            const issue = document.querySelector('#blueprintFields .blueprint-field.invalid:not(.hidden), #blueprintFields .blueprint-field.missing:not(.hidden)');
            if (!issue) return;
            scrollCreationTarget(issue);
            issue.querySelector('input:not([disabled]), select:not([disabled]), textarea:not([disabled])')?.focus({ preventScroll: true });
        }

        function blueprintToolFieldSchema(toolRef) {
            const parts = String(toolRef || '').split('.');
            const toolName = parts.shift();
            const fieldPath = parts.join('.');
            const tool = blueprintState.tools.find(item => item.name === toolName);
            let schema = tool?.input_schema?.properties || {};
            for (const part of fieldPath.split('.')) {
                if (!part) continue;
                schema = schema?.[part] || {};
            }
            return { toolName, fieldPath, schema: schema || {} };
        }

        function blueprintFieldDefault(field) {
            if (field && Object.prototype.hasOwnProperty.call(field, 'default')) return field.default;
            const schema = blueprintToolFieldSchema(field?.tool_ref).schema || {};
            if (Object.prototype.hasOwnProperty.call(schema, 'default')) return schema.default;
            return schema.type === 'boolean' ? false : undefined;
        }

        function blueprintDefaultValues(blueprint) {
            const values = {};
            (blueprint?.fields || []).forEach(field => {
                const value = blueprintFieldDefault(field);
                if (value !== undefined) values[field.path] = value;
            });
            return values;
        }

        function blueprintOptions(field, evaluatedState = null) {
            // An evaluated empty list is meaningful: the parent selector is
            // still missing. Do not fall back to the provider's full enum or
            // the cascade would look dynamic while showing invalid values.
            if (evaluatedState && Object.prototype.hasOwnProperty.call(evaluatedState, 'options')) {
                return Array.isArray(evaluatedState.options) ? evaluatedState.options : [];
            }
            const schema = blueprintToolFieldSchema(field.tool_ref).schema || {};
            const arraySchema = schema.type === 'array' || (Array.isArray(schema.type) && schema.type.includes('array'));
            if (Array.isArray(field.options) && !arraySchema) return field.options;
            if (Array.isArray(schema.enum)) return schema.enum;
            if (Array.isArray(schema.items?.enum)) return schema.items.enum;
            return [];
        }

        function blueprintOptionLabel(field, option) {
            const labels = field?.option_labels;
            if (labels && typeof labels === 'object') {
                return labels[String(option)] || String(option);
            }
            return String(option);
        }

        function schemaConstraintHint(schema) {
            if (!schema || typeof schema !== 'object') return '';
            const hints = [];
            if (schema.minItems !== undefined) hints.push(`至少 ${schema.minItems} 项`);
            if (schema.maxItems !== undefined) hints.push(`最多 ${schema.maxItems} 项`);
            if (schema.minLength !== undefined) hints.push(`最少 ${schema.minLength} 个字符`);
            if (schema.maxLength !== undefined) hints.push(`最多 ${schema.maxLength} 个字符`);
            if (schema.minimum !== undefined) hints.push(`最小值 ${schema.minimum}`);
            if (schema.maximum !== undefined) hints.push(`最大值 ${schema.maximum}`);
            if (schema.items?.minLength !== undefined) hints.push(`每项最少 ${schema.items.minLength} 个字符`);
            if (schema.items?.maxLength !== undefined) hints.push(`每项最多 ${schema.items.maxLength} 个字符`);
            if (schema.known_values && schema.allow_custom) hints.push('可选标准值，也可填写自定义值');
            return hints.join('；');
        }

        function presentedLines(value) {
            if (!Array.isArray(value)) return value ? String(value) : '';
            return value.map(item => {
                if (item && typeof item === 'object') return item.text || item.name || item.asset || item.resource_name || '';
                return String(item ?? '');
            }).filter(Boolean).join('\n');
        }

        function parsePresentedValue(field, rawValue, schema) {
            if (field.presentation === 'text_list') {
                const lines = String(rawValue || '').split(/\r?\n/).map(item => item.trim()).filter(Boolean);
                return field.value_shape === 'object_text' ? lines.map(text => ({ text })) : lines;
            }
            if (schema.type === 'object' || schema.type === 'array' || Array.isArray(schema.type)) {
                try { return JSON.parse(rawValue); } catch (_) { return rawValue; }
            }
            if (schema.type === 'number' || schema.type === 'integer') return Number(rawValue);
            return rawValue;
        }

        function structuredObjectValueText(value) {
            if (!value || typeof value !== 'object' || Array.isArray(value)) return '';
            return Object.entries(value)
                .filter(([, item]) => item !== undefined && item !== null && item !== '')
                .map(([key, item]) => `${key}: ${Array.isArray(item) ? item.join(', ') : typeof item === 'object' ? JSON.stringify(item) : item}`)
                .join(' · ');
        }

        function parseStructuredObjectChild(spec, rawValue) {
            const type = spec?.type;
            if (type === 'number' || type === 'integer') return rawValue === '' ? undefined : Number(rawValue);
            if (type === 'boolean') return Boolean(rawValue);
            if (type === 'array') {
                if (spec.items?.type === 'string') return String(rawValue || '').split(/\r?\n/).map(item => item.trim()).filter(Boolean);
                try { return JSON.parse(rawValue); } catch (_) { return rawValue; }
            }
            if (type === 'object') {
                try { return JSON.parse(rawValue); } catch (_) { return rawValue; }
            }
            return rawValue === '' ? undefined : rawValue;
        }

        function ensureLookupSessionId() {
            if (sessionId) return sessionId;
            try {
                sessionId = crypto.randomUUID();
            } catch (_) {
                sessionId = `web-${Date.now()}-${Math.random().toString(16).slice(2)}`;
            }
            return sessionId;
        }

        function lookupValueKey(value) {
            if (value === undefined || value === null) return '';
            return JSON.stringify(value, (_, item) => item, 0);
        }

        function lookupFieldValue(field, context = {}) {
            if (typeof context.getValue === 'function') return context.getValue();
            return field.value;
        }

        function lookupFieldName(field, context = {}) {
            return String(context.fieldName || field.provider_field || field.path || '').trim();
        }

        function lookupToolName(field, context = {}) {
            return String(
                context.targetToolName || field.tool || field.lookup_tool || field.lookup?.tool || ''
            ).trim();
        }

        function lookupIsMultiple(field, context = {}) {
            if (context.multiple !== undefined) return Boolean(context.multiple);
            return Boolean(field.lookup_multiple || field.control === 'multiselect');
        }

        function lookupAccountRequired(field, context = {}) {
            if (context.accountRequired !== undefined) return Boolean(context.accountRequired);
            if (field?.lookup?.account_required !== undefined) return Boolean(field.lookup.account_required);
            if (field?.lookup_account_required !== undefined) return Boolean(field.lookup_account_required);
            return true;
        }

        function lookupSourceAccountRequired(toolName) {
            const tool = (blueprintState.tools || []).find(item => item.name === toolName);
            const required = tool?.input_schema?.required || [];
            return required.some(name => ['account_id', 'advertiser_id', 'customer_id'].includes(name));
        }

        function lookupContextValues(context = {}) {
            if (typeof context.getLookupContext === 'function') {
                const value = context.getLookupContext();
                return value && typeof value === 'object' ? value : {};
            }
            return context.lookupContext && typeof context.lookupContext === 'object'
                ? context.lookupContext : {};
        }

        function lookupSelectedValues(field, context = {}) {
            const value = lookupFieldValue(field, context);
            if (lookupIsMultiple(field, context)) return Array.isArray(value) ? value : [];
            return value === undefined || value === null || value === '' ? [] : [value];
        }

        function lookupOptionLabel(option) {
            return String(option?.label ?? option?.name ?? option?.value ?? '');
        }

        function lookupOptionValue(option) {
            return option?.value;
        }

        function lookupOptionValueText(value) {
            if (value && typeof value === 'object') {
                return String(value.id ?? value.audience_id ?? value.value ?? JSON.stringify(value));
            }
            return String(value ?? '');
        }

        function lookupOptionMatches(option, query) {
            if (!query) return true;
            return `${lookupOptionLabel(option)} ${lookupOptionValueText(lookupOptionValue(option))}`
                .toLowerCase().includes(query.toLowerCase());
        }

        function lookupSelectionTokensFor(context, field) {
            const store = context.selectionTokens || {};
            const key = lookupFieldName(field, context);
            const value = store[key];
            if (lookupIsMultiple(field, context)) return Array.isArray(value) ? value : [];
            return value ? [value] : [];
        }

        function renderLookupPicker(field, context = {}) {
            const picker = document.createElement('div');
            picker.className = 'lookup-picker';
            const fieldName = lookupFieldName(field, context);
            const toolName = lookupToolName(field, context);
            const multiple = lookupIsMultiple(field, context);
            const accountId = () => String(
                typeof context.getAccountId === 'function' ? context.getAccountId() : context.accountId || ''
            ).trim();
            const accountRequired = lookupAccountRequired(field, context);
            const optionsStore = context.optionsStore || {};
            const optionsKey = `${toolName}:${fieldName}`;
            let options = Array.isArray(optionsStore[optionsKey]) ? optionsStore[optionsKey] : [];

            const toolbar = document.createElement('div');
            toolbar.className = 'lookup-picker-toolbar';
            const searchInput = document.createElement('input');
            searchInput.type = 'search';
            searchInput.autocomplete = 'off';
            searchInput.placeholder = '输入名称或 ID 筛选，再查询可用项';
            const searchButton = document.createElement('button');
            searchButton.type = 'button';
            searchButton.className = 'lookup-picker-search';
            searchButton.textContent = '查询';
            toolbar.append(searchInput, searchButton);
            picker.appendChild(toolbar);

            const status = document.createElement('div');
            status.className = 'lookup-picker-status';
            picker.appendChild(status);
            const results = document.createElement('div');
            results.className = 'lookup-picker-results';
            picker.appendChild(results);
            const selected = document.createElement('div');
            selected.className = 'lookup-picker-selected';
            picker.appendChild(selected);

            const getSelected = () => lookupSelectedValues(field, context);
            const tokenStore = context.selectionTokens || {};

            function optionForValue(value) {
                return options.find(option => lookupValueKey(lookupOptionValue(option)) === lookupValueKey(value))
                    || { value, label: String(value ?? '') };
            }

            function renderSelected() {
                selected.replaceChildren();
                const values = getSelected();
                const tokens = lookupSelectionTokensFor(context, field);
                values.forEach((value, index) => {
                    const option = optionForValue(value);
                    const chip = document.createElement('span');
                    chip.className = 'lookup-selection-chip';
                    const label = document.createElement('span');
                    label.textContent = `${lookupOptionLabel(option)} · ${lookupOptionValueText(value)}`;
                    const remove = document.createElement('button');
                    remove.type = 'button';
                    remove.setAttribute('aria-label', `移除 ${lookupOptionLabel(option)}`);
                    remove.textContent = '×';
                    remove.onclick = () => {
                        const next = multiple ? values.filter((_, valueIndex) => valueIndex !== index) : [];
                        const nextTokens = multiple ? tokens.filter((_, tokenIndex) => tokenIndex !== index) : [];
                        commitSelection(next, nextTokens, null);
                    };
                    chip.append(label, remove);
                    selected.appendChild(chip);
                });
                if (!values.length) {
                    const empty = document.createElement('span');
                    empty.className = 'lookup-picker-status';
                    empty.textContent = '尚未选择；请选择查询结果中的项目。';
                    selected.appendChild(empty);
                }
            }

            function renderResults() {
                results.replaceChildren();
                const selectedKeys = new Set(getSelected().map(lookupValueKey));
                const query = searchInput.value.trim();
                const visible = options.filter(option => lookupOptionMatches(option, query));
                if (!visible.length) {
                    status.textContent = options.length ? '没有匹配的项目，请换一个名称或 ID。' : '点击“查询”加载该账户下的可用项。';
                    return;
                }
                status.textContent = `已加载 ${options.length} 项${query ? `，当前显示 ${visible.length} 项` : ''}`;
                visible.slice(0, 100).forEach(option => {
                    const value = lookupOptionValue(option);
                    const button = document.createElement('button');
                    button.type = 'button';
                    button.className = `lookup-option${selectedKeys.has(lookupValueKey(value)) ? ' selected' : ''}`;
                    button.disabled = !multiple && selectedKeys.has(lookupValueKey(value));
                    const label = document.createElement('span');
                    label.className = 'lookup-option-label';
                    label.textContent = lookupOptionLabel(option);
                    const id = document.createElement('span');
                    id.className = 'lookup-option-value';
                    id.textContent = lookupOptionValueText(value);
                    button.append(label, id);
                    button.onclick = () => {
                        const current = getSelected();
                        const currentTokens = lookupSelectionTokensFor(context, field);
                        if (multiple) {
                            if (current.some(item => lookupValueKey(item) === lookupValueKey(value))) return;
                            commitSelection([...current, value], [...currentTokens, option.selection_token || ''], option);
                        } else {
                            commitSelection([value], [option.selection_token || ''], option);
                        }
                    };
                    results.appendChild(button);
                });
            }

            function commitSelection(values, tokens, option) {
                const nextValue = multiple ? values : (values[0] ?? undefined);
                const nextTokens = multiple ? tokens : (tokens[0] || undefined);
                const key = lookupFieldName(field, context);
                if (nextTokens) tokenStore[key] = nextTokens;
                else delete tokenStore[key];
                if (typeof context.onSelection === 'function') {
                    context.onSelection({ value: nextValue, tokens: nextTokens, option });
                }
                renderSelected();
                renderResults();
            }

            async function queryOptions() {
                const account = accountId();
                if (!account && accountRequired) {
                    status.textContent = '请先填写广告账户 ID，再查询该账户下的可用项。';
                    searchButton.disabled = true;
                    return;
                }
                if (!toolName || !fieldName || !context.platform) {
                    status.textContent = '当前字段缺少受控查询配置，暂时无法加载选项。';
                    return;
                }
                searchButton.disabled = true;
                status.textContent = '正在查询该账户的可用项…';
                try {
                    ensureLookupSessionId();
                    const params = new URLSearchParams({
                        platform: String(context.platform), field: fieldName,
                        tool_name: toolName, session_id: sessionId,
                    });
                    if (account) params.set('account_id', account);
                    const lookupContext = lookupContextValues(context);
                    if (Object.keys(lookupContext).length) params.set('lookup_context', JSON.stringify(lookupContext));
                    if (field?.lookup?.query_field && searchInput.value.trim()) params.set('query', searchInput.value.trim());
                    const response = await authenticatedFetch(`/parameter-options/resolve?${params.toString()}`);
                    const body = await response.text();
                    let data = {};
                    try { data = body ? JSON.parse(body) : {}; } catch (_) { data = {}; }
                    if (!response.ok) throw new Error(data.detail || data.error || `查询失败（${response.status}）`);
                    options = Array.isArray(data.options) ? data.options : [];
                    optionsStore[optionsKey] = options;
                    renderResults();
                    renderSelected();
                } catch (error) {
                    status.textContent = error.message || '暂时无法查询可用项，请稍后重试。';
                } finally {
                    searchButton.disabled = false;
                    refreshLookupAccountState(picker);
                }
            }

            searchInput.addEventListener('input', renderResults);
            searchButton.addEventListener('click', queryOptions);
            picker.dataset.accountRequired = accountRequired ? 'true' : 'false';
            picker.dataset.accountValue = accountId();
            refreshLookupAccountState(picker);
            renderSelected();
            renderResults();
            return picker;
        }

        function refreshLookupAccountState(root = document) {
            const accountInput = root?.closest?.('.creation-card')?.querySelector('.creation-card-account input')
                || root?.querySelector?.('.creation-card-account input')
                || document.getElementById('blueprintAccountInput');
            const account = String(accountInput?.value || '').trim();
            (root?.matches?.('.lookup-picker') ? [root] : root?.querySelectorAll?.('.lookup-picker') || []).forEach(picker => {
                picker.dataset.accountValue = account;
                const button = picker.querySelector('.lookup-picker-search');
                const accountRequired = picker.dataset.accountRequired !== 'false';
                if (button && !button.disabled) button.disabled = accountRequired && !account;
                if (!account && accountRequired) {
                    const status = picker.querySelector('.lookup-picker-status');
                    if (status && !picker.querySelector('.lookup-picker-results:not(:empty)')) {
                        status.textContent = '请先填写广告账户 ID，再查询该账户下的可用项。';
                    }
                }
            });
        }

        function clearAccountScopedLookupValues(value, properties) {
            if (Array.isArray(value)) {
                return value.map(item => clearAccountScopedLookupValues(item, properties));
            }
            if (!value || typeof value !== 'object' || !properties || typeof properties !== 'object') {
                return value;
            }
            const result = { ...value };
            Object.entries(properties).forEach(([name, spec]) => {
                if (!spec || typeof spec !== 'object') return;
                if (spec.lookup_tool || spec.source === 'lookup' || spec.lookup) {
                    delete result[name];
                    return;
                }
                if (spec.properties && result[name] && typeof result[name] === 'object') {
                    result[name] = clearAccountScopedLookupValues(result[name], spec.properties);
                } else if (spec.items?.properties && Array.isArray(result[name])) {
                    result[name] = clearAccountScopedLookupValues(result[name], spec.items.properties);
                }
            });
            return result;
        }

        function resetAccountScopedSelections(card) {
            let changed = false;
            card.lookup_options = {};
            card.selection_tokens = {};
            card.selection_token_tools = {};
            (card.fields || []).forEach(field => {
                if (!field || field.visible === false) return;
                if (field.control === 'lookup' && field.lookup?.account_required !== false && !creationCardValueEmpty(field.value)) {
                    field.value = undefined;
                    field.state = 'missing';
                    changed = true;
                }
                if (field.object_properties && !creationCardValueEmpty(field.value)) {
                    const cleared = clearAccountScopedLookupValues(field.value, field.object_properties);
                    if (JSON.stringify(cleared) !== JSON.stringify(field.value)) {
                        field.value = cleared;
                        changed = true;
                    }
                }
            });
            return changed;
        }

        function renderStructuredObjectEditor(schema, value, onChange, metadata = null, lookupContext = null) {
            // Arrays of provider objects are first-class form values (for
            // example carousel cards and asset lists).  Keep the collection
            // wrapper here so every provider gets the same add/remove UX;
            // no channel-specific renderer is needed.
            if (schema?.type === 'array' && schema.items?.properties) {
                const collection = document.createElement('div');
                collection.className = 'structured-object-collection';
                const itemProperties = metadata || schema.items.properties || {};
                const items = Array.isArray(value) ? value.map(item => ({ ...(item || {}) })) : [];
                const list = document.createElement('div');
                list.className = 'structured-object-collection-list';

                const renderItems = () => {
                    list.replaceChildren();
                    items.forEach((itemValue, index) => {
                        const itemBox = document.createElement('div');
                        itemBox.className = 'structured-object-item';
                        const itemHead = document.createElement('div');
                        itemHead.className = 'structured-object-item-head';
                        const itemTitle = document.createElement('strong');
                        itemTitle.textContent = `第 ${index + 1} 项`;
                        const remove = document.createElement('button');
                        remove.type = 'button';
                        remove.className = 'structured-object-remove';
                        remove.textContent = '移除';
                        remove.addEventListener('click', () => {
                            items.splice(index, 1);
                            onChange(items.length ? items.map(item => ({ ...item })) : undefined);
                            renderItems();
                        });
                        itemHead.append(itemTitle, remove);
                        itemBox.appendChild(itemHead);
                        itemBox.appendChild(renderStructuredObjectEditor(
                            schema.items,
                            itemValue,
                            nextValue => {
                                items[index] = nextValue || {};
                                onChange(items.map(item => ({ ...item })));
                            },
                            itemProperties,
                            lookupContext,
                        ));
                        list.appendChild(itemBox);
                    });
                };

                const add = document.createElement('button');
                add.type = 'button';
                add.className = 'structured-object-add';
                add.textContent = '＋ 新增一项';
                add.disabled = schema.maxItems !== undefined && items.length >= Number(schema.maxItems);
                add.addEventListener('click', () => {
                    if (schema.maxItems !== undefined && items.length >= Number(schema.maxItems)) return;
                    items.push({});
                    onChange(items.map(item => ({ ...item })));
                    renderItems();
                    add.disabled = schema.maxItems !== undefined && items.length >= Number(schema.maxItems);
                });
                collection.append(list, add);
                renderItems();
                return collection;
            }
            const editor = document.createElement('div');
            editor.className = 'structured-object-editor';
            const properties = metadata || schema?.properties || {};
            const current = value && typeof value === 'object' && !Array.isArray(value) ? { ...value } : {};
            Object.entries(properties).slice(0, 40).forEach(([name, rawSpec]) => {
                const spec = rawSpec || {};
                const row = document.createElement('div');
                row.className = 'structured-object-row';
                const label = document.createElement('label');
                const specHint = schemaConstraintHint(spec);
                const specDescription = [spec.description, specHint ? `参数限制：${specHint}` : '']
                    .filter(Boolean).join('；');
                const friendlyName = spec.title || {
                    age_groups: '年龄段', operating_systems: '操作系统', placement_type: '版位方式',
                    placements: '投放版位', targeting_optimization_mode: '定向优化方式',
                    billing_event: '计费事件', optimization_event: '优化事件',
                }[name] || name.replace(/[_-]+/g, ' ').replace(/\b\w/g, character => character.toUpperCase());
                label.textContent = friendlyName;
                const key = document.createElement('span');
                key.className = 'structured-object-key';
                key.textContent = name;
                label.appendChild(key);
                if (spec.required) {
                    const required = document.createElement('span');
                    required.className = 'required';
                    required.textContent = ' *';
                    label.appendChild(required);
                }
                row.appendChild(label);
                if (specDescription) {
                    const help = document.createElement('div');
                    help.className = 'structured-object-help';
                    help.textContent = specDescription;
                    row.appendChild(help);
                }
                let control;
                const options = Array.isArray(spec.enum)
                    ? spec.enum
                    : Array.isArray(spec.items?.enum) ? spec.items.enum : [];
                if (spec.lookup_tool || spec.lookup?.tool) {
                    const childPath = [lookupContext?.fieldPath, name].filter(Boolean).join('.');
                    control = renderLookupPicker({
                        ...spec, path: childPath, provider_field: childPath,
                        tool: lookupContext?.targetToolName,
                        lookup: {
                            tool: spec.lookup_tool || spec.lookup?.tool,
                            query_field: spec.lookup_query_field || spec.lookup?.query_field,
                        },
                        lookup_multiple: spec.type === 'array',
                        value: current[name],
                    }, {
                        ...lookupContext,
                        fieldName: childPath,
                        targetToolName: lookupContext?.targetToolName,
                        multiple: spec.type === 'array',
                        getValue: () => current[name],
                        onSelection: ({ value: selectedValue, tokens }) => {
                            if (selectedValue === undefined) delete current[name];
                            else current[name] = selectedValue;
                            onChange({ ...current });
                            lookupContext?.onSelection?.({ fieldName: childPath, tokens });
                        },
                    });
                } else if (
                    spec.type === 'object' && spec.properties && typeof spec.properties === 'object'
                ) {
                    const childPath = [lookupContext?.fieldPath, name].filter(Boolean).join('.');
                    control = renderStructuredObjectEditor(
                        spec,
                        current[name],
                        selectedValue => {
                            if (selectedValue === undefined) delete current[name];
                            else current[name] = selectedValue;
                            onChange({ ...current });
                        },
                        null,
                        {
                            ...(lookupContext || {}),
                            fieldPath: childPath,
                        },
                    );
                } else if (
                    spec.type === 'array' && spec.items?.properties
                    && typeof spec.items.properties === 'object'
                ) {
                    const childPath = [lookupContext?.fieldPath, name].filter(Boolean).join('.');
                    control = renderStructuredObjectEditor(
                        spec,
                        current[name],
                        selectedValue => {
                            if (selectedValue === undefined) delete current[name];
                            else current[name] = selectedValue;
                            onChange({ ...current });
                        },
                        null,
                        { ...(lookupContext || {}), fieldPath: childPath },
                    );
                } else if (spec.options_state === 'awaiting_dependency' || spec.options_state === 'no_matching_rule') {
                    control = document.createElement('select');
                    control.disabled = true;
                    const waiting = document.createElement('option');
                    waiting.value = '';
                    waiting.textContent = spec.options_state === 'awaiting_dependency'
                        ? '请先完成上游选择…' : '当前组合暂无可用选项';
                    control.appendChild(waiting);
                } else if (options.length) {
                    const useChoiceTiles = spec.type === 'array' || options.length <= 6;
                    if (useChoiceTiles) {
                        const multiple = spec.type === 'array';
                        control = renderChoiceTiles(options, current[name], multiple, option => spec.option_labels?.[String(option)] || '', selected => {
                            if (selected === '' || (Array.isArray(selected) && !selected.length)) delete current[name];
                            else current[name] = selected;
                            onChange({ ...current });
                        });
                        control.dataset.customChoice = 'true';
                    } else {
                        control = document.createElement('select');
                        const empty = document.createElement('option');
                        empty.value = ''; empty.textContent = spec.required ? '请选择…' : '不设置';
                        control.appendChild(empty);
                        options.forEach(option => {
                            const item = document.createElement('option');
                            item.value = String(option);
                            item.textContent = spec.option_labels?.[String(option)] || String(option);
                            control.appendChild(item);
                        });
                        control.value = current[name] === undefined ? '' : String(current[name]);
                    }
                } else if (spec.type === 'boolean') {
                    control = document.createElement('input');
                    control.type = 'checkbox'; control.checked = Boolean(current[name]);
                } else if (spec.type === 'array') {
                    control = document.createElement('textarea');
                    control.className = 'structured-object-list';
                    control.placeholder = spec.items?.type === 'string' ? '每行一项' : '[...]';
                    control.value = spec.items?.type === 'string'
                        ? (Array.isArray(current[name]) ? current[name].join('\n') : '')
                        : (current[name] === undefined ? '' : JSON.stringify(current[name]));
                } else {
                    control = document.createElement('input');
                    control.type = spec.type === 'number' || spec.type === 'integer' ? 'number' : 'text';
                    control.value = current[name] === undefined ? '' : String(current[name]);
                }
                let controlNode = control;
                let checkboxState = null;
                if (spec.type === 'boolean') {
                    const checkboxLabel = document.createElement('label');
                    checkboxLabel.className = 'checkbox-control';
                    const visual = document.createElement('span');
                    visual.className = 'checkbox-visual';
                    const copy = document.createElement('span');
                    copy.className = 'checkbox-copy';
                    const title = document.createElement('strong');
                    title.textContent = '启用该设置';
                    checkboxState = document.createElement('small');
                    checkboxState.textContent = control.checked ? '已开启' : '未开启';
                    copy.append(title, checkboxState);
                    checkboxLabel.append(control, visual, copy);
                    controlNode = checkboxLabel;
                }
                if (spec.manual_entry && typeof spec.manual_entry === 'object') {
                    const help = document.createElement('div');
                    help.className = 'manual-entry-help';
                    const title = spec.manual_entry.title || '需要手动提供的外部标识';
                    const instructions = spec.manual_entry.instructions || '该字段当前没有可用的受控列表查询。';
                    help.innerHTML = `<strong>${escapeHtml(title)}</strong><br>${escapeHtml(instructions)}${spec.manual_entry.example ? `<br>示例：${escapeHtml(spec.manual_entry.example)}` : ''}`;
                    row.appendChild(help);
                }
                const commit = () => {
                    if (spec.lookup_tool || spec.lookup?.tool) return;
                    const value = control.type === 'checkbox'
                        ? control.checked
                        : control.tagName === 'SELECT' && control.multiple
                            ? Array.from(control.selectedOptions).map(option => option.value)
                            : parseStructuredObjectChild(spec, control.value.trim());
                    if (value === undefined) delete current[name]; else current[name] = value;
                    if (checkboxState) checkboxState.textContent = control.checked ? '已开启' : '未开启';
                    onChange({ ...current });
                };
                if (!control.dataset.customChoice && !(
                    (spec.type === 'object' && spec.properties && typeof spec.properties === 'object')
                    || (spec.type === 'array' && spec.items?.properties)
                )) {
                    control.addEventListener(control.type === 'checkbox' || control.tagName === 'SELECT' ? 'change' : 'input', commit);
                }
                row.appendChild(controlNode);
                editor.appendChild(row);
            });
            if (!Object.keys(properties).length) {
                const empty = document.createElement('div');
                empty.className = 'asset-picker-note';
                empty.textContent = '当前 Tool 未声明可编辑的子字段。';
                editor.appendChild(empty);
            }
            return editor;
        }

