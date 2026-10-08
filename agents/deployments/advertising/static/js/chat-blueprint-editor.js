        function creationTemplateVerificationLabel(status) {
            return ({
                live_verified: '已验证',
                partial_live_verified: '部分验证',
                live_verified_with_provider_limits: '已验证 · 渠道限制',
                provider_limited: '渠道限制',
                dry_run_only: '仅草稿',
            }[status] || status || '未标注');
        }

        function blueprintDraftPlatformParams(blueprint) {
            const values = {};
            const scopedSelectionTokens = {};
            const evaluated = new Map((blueprintState.evaluation?.fields || []).map(item => [item.path, item]));
            for (const field of (blueprint?.fields || [])) {
                if (field.visible === false) continue;
                let value = blueprintState.values[field.path];
                if (value === undefined) value = evaluated.get(field.path)?.value;
                if (value === undefined) value = blueprintFieldDefault(field);
                const options = blueprintOptions(field, evaluated.get(field.path));
                if (value === undefined && field.presentation === 'derived_readonly' && options.length === 1) value = options[0];
                if (value === undefined || value === null || value === '') continue;
                const { toolName, fieldPath } = blueprintToolFieldSchema(field.tool_ref);
                setCreationNestedValue(values, fieldPath || field.path, value);
                if (toolName) {
                    values[toolName] = values[toolName] || {};
                    setCreationNestedValue(values[toolName], fieldPath || field.path, value);
                }
            }
            Object.entries(blueprintState.selectionTokens || {}).forEach(([fieldName, token]) => {
                const toolName = blueprintState.selectionTokenTools?.[fieldName];
                if (!toolName || !token) return;
                scopedSelectionTokens[toolName] = scopedSelectionTokens[toolName] || {};
                scopedSelectionTokens[toolName][fieldName] = token;
            });
            Object.entries(scopedSelectionTokens).forEach(([toolName, tokens]) => {
                values[toolName] = values[toolName] || {};
                values[toolName].selection_tokens = tokens;
            });
            return { [blueprint.provider]: values };
        }

        function blueprintSelectorOptions(blueprint) {
            const selector = blueprint?.selector;
            if (!selector?.dimension) return [];
            const options = new Map();
            for (const item of blueprintState.items) {
                if (item.provider !== blueprint.provider || item.selector?.dimension !== selector.dimension) continue;
                const labels = new Map((item.selector.options || []).map(option => [String(option.value), option.label || option.value]));
                for (const value of (item.selector.values || [])) {
                    const key = String(value);
                    if (!options.has(key)) options.set(key, labels.get(key) || key);
                }
            }
            return [...options].map(([value, label]) => ({ value, label }));
        }

        function creationFieldGroups(fields) {
            const grouped = new Map(
                BLUEPRINT_HIERARCHY_GROUPS.map(group => [group.id, { ...group, fields: [] }])
            );
            (fields || []).forEach(field => {
                if (field.visible === false) return;
                const group = grouped.get(blueprintHierarchyInfo(field).id) || grouped.get('extension');
                group.fields.push(field);
            });
            return BLUEPRINT_HIERARCHY_GROUPS
                .map(group => grouped.get(group.id))
                .filter(group => group.fields.length);
        }

        function creationDirectoryHierarchy(field) {
            return creationHierarchyLabel(field) || '平台扩展层级';
        }

        function creationDirectoryHierarchyGroups(fields) {
            const grouped = new Map();
            (fields || []).forEach(field => {
                const hierarchy = creationDirectoryHierarchy(field);
                if (!grouped.has(hierarchy)) grouped.set(hierarchy, []);
                grouped.get(hierarchy).push(field);
            });
            return [...grouped.entries()];
        }

        function creationDirectoryLevelGroups(fields) {
            const preferredOrder = [
                'Campaign 层级', 'Ad Set 层级', 'Ad Group 层级', 'Ad 层级',
                'Insertion Order 层级', 'Line Item 层级', 'Creative 层级', '平台扩展层级',
            ];
            const grouped = new Map();
            (fields || []).forEach(field => {
                const hierarchy = creationDirectoryHierarchy(field);
                if (!grouped.has(hierarchy)) grouped.set(hierarchy, []);
                grouped.get(hierarchy).push(field);
            });
            return [...grouped.entries()]
                .sort(([left], [right]) => {
                    const leftIndex = preferredOrder.indexOf(left);
                    const rightIndex = preferredOrder.indexOf(right);
                    return (leftIndex < 0 ? preferredOrder.length : leftIndex)
                        - (rightIndex < 0 ? preferredOrder.length : rightIndex);
                })
                .map(([hierarchy, levelFields]) => ({ hierarchy, fields: levelFields }));
        }

        function creationFieldValue(field, value = field?.value) {
            return value === undefined && field?.control === 'checkbox' ? false : value;
        }

        function creationFieldDisplayValue(field, value = field?.value) {
            const normalized = creationFieldValue(field, value);
            if (field?.control === 'checkbox') return normalized ? '已开启' : '未开启';
            return blueprintDisplayValue(normalized);
        }

        function creationFieldNeedsUserInput(field) {
            if (field?.user_required !== undefined) return Boolean(field.user_required);
            return Boolean(field?.required);
        }

        function creationFieldIsAuto(field) {
            return ['auto_default', 'auto_derived'].includes(String(field?.input_mode || '').toLowerCase());
        }

        function creationFieldModeLabel(field) {
            if (field?.auto_filled) return '系统已填 · 可修改';
            if (field?.input_mode === 'context_required') return '需要从账户或业务上下文确认';
            if (field?.input_mode === 'asset_required') return '需要选择素材或素材资源';
            if (creationFieldIsAuto(field)) return '系统将按当前目标自动处理';
            return '';
        }

        function fieldGroupProgress(fields) {
            const visible = (fields || []).filter(field => field.visible !== false);
            const required = visible.filter(creationFieldNeedsUserInput);
            const missing = required.filter(field => creationCardValueEmpty(creationFieldValue(field)) || field.local_error || field.state === 'invalid');
            return { total: visible.length, missing: missing.length, complete: required.length - missing.length };
        }

        function blueprintFieldEvaluation(field, evaluation) {
            const evaluated = evaluation?.fields?.find(item => item.path === field.path) || {};
            const rawValue = evaluated.value !== undefined
                ? evaluated.value
                : blueprintState.values[field.path] !== undefined
                    ? blueprintState.values[field.path] : blueprintFieldDefault(field);
            const value = creationFieldValue(field, rawValue);
            const required = evaluated.required !== undefined ? evaluated.required : Boolean(field.required);
            const visible = evaluated.visible !== false && field.visible !== false;
            const invalid = evaluated.state === 'invalid' || evaluated.local_error;
            const empty = creationCardValueEmpty(value);
            const status = invalid ? 'invalid' : required && empty ? 'missing' : empty ? 'empty' : 'complete';
            return { ...evaluated, value, required, visible, status };
        }

        function blueprintDisplayValue(value) {
            if (creationCardValueEmpty(value)) return '未填写';
            if (Array.isArray(value)) {
                const values = value.map(item => {
                    if (item && typeof item === 'object') return item.name || item.label || item.text || item.asset_id || item.local_file || '已选择';
                    return String(item);
                });
                return values.length > 2 ? `${values.slice(0, 2).join('、')} +${values.length - 2}` : values.join('、');
            }
            if (typeof value === 'object') {
                const entries = Object.entries(value).slice(0, 2).map(([key, item]) => `${key}: ${blueprintDisplayValue(item)}`);
                return entries.join(' · ') || '已填写';
            }
            const text = String(value);
            return text.length > 42 ? `${text.slice(0, 42)}…` : text;
        }

        function creationHierarchyLabel(field) {
            const path = String(field?.path || '').toLowerCase();
            if (/^(campaign|campaigns)\./.test(path)) return 'Campaign 层级';
            if (/^(ad_set|adset)\./.test(path)) return 'Ad Set 层级';
            if (/^(ad_group|adgroup)\./.test(path)) return 'Ad Group 层级';
            if (/^ad\./.test(path)) return 'Ad 层级';
            if (/^insertion_order\./.test(path)) return 'Insertion Order 层级';
            if (/^line_item\./.test(path)) return 'Line Item 层级';
            if (/^creative\./.test(path)) return 'Creative 层级';
            return '';
        }

        const BLUEPRINT_HIERARCHY_GROUPS = [
            {
                id: 'campaign',
                roots: ['campaign', 'campaigns'],
                title: 'Campaign',
                label: '广告系列',
                description: '先确定目标、预算、投放时间和竞价方式。',
            },
            {
                id: 'insertion_order',
                roots: ['insertion_order'],
                title: 'Insertion Order',
                label: '订单层级',
                description: '配置 DV360 订单、预算和投放周期。',
            },
            {
                id: 'ad_set',
                roots: ['ad_set', 'adset'],
                title: 'Ad Set',
                label: '广告组',
                description: '配置受众、版位、优化目标和账户资源。',
            },
            {
                id: 'ad_group',
                roots: ['ad_group', 'adgroup'],
                title: 'Ad Group',
                label: '广告组',
                description: '配置关键词、受众、出价和广告组级资源。',
            },
            {
                id: 'line_item',
                roots: ['line_item'],
                title: 'Line Item',
                label: '广告项',
                description: '配置 DV360 广告项的渠道、出价和投放约束。',
            },
            {
                id: 'asset_group',
                roots: ['asset_group'],
                title: 'Asset Group',
                label: '素材组',
                description: '组织 Performance Max 或 Demand Gen 的素材组合。',
            },
            {
                id: 'product_group',
                roots: ['product_group', 'listing_group_filter'],
                title: 'Product Group',
                label: '商品组',
                description: '配置商品筛选、分组和商品级出价。',
            },
            {
                id: 'ad',
                roots: ['ad'],
                title: 'Ad',
                label: '广告',
                description: '填写文案、素材、行动按钮和落地页。',
            },
            {
                id: 'creative',
                roots: ['creative'],
                title: 'Creative',
                label: '创意',
                description: '配置可复用创意及其平台资源引用。',
            },
            {
                id: 'extension',
                roots: [],
                title: 'Provider Extension',
                label: '平台扩展',
                description: '渠道特有或暂未归类的参数。',
            },
        ];

        function blueprintHierarchyInfo(field) {
            const root = String(field?.path || '').split('.', 1)[0].toLowerCase();
            return BLUEPRINT_HIERARCHY_GROUPS.find(group => group.roots.includes(root))
                || BLUEPRINT_HIERARCHY_GROUPS[BLUEPRINT_HIERARCHY_GROUPS.length - 1];
        }

        function blueprintHierarchyStats(fields, evaluation) {
            const states = (fields || []).map(field => blueprintFieldEvaluation(field, evaluation));
            const required = states.filter(state => state.required);
            const missing = required.filter(state => state.status === 'missing' || state.status === 'invalid');
            const completed = states.filter(state => state.status === 'complete').length;
            return {
                total: states.length,
                required: required.length,
                missing: missing.length,
                completed,
            };
        }

        function blueprintHierarchyGroups(fields, evaluation) {
            const grouped = new Map(
                BLUEPRINT_HIERARCHY_GROUPS.map(group => [group.id, { ...group, fields: [] }])
            );
            (fields || []).forEach(field => {
                const state = blueprintFieldEvaluation(field, evaluation);
                if (state.visible === false) return;
                const group = grouped.get(blueprintHierarchyInfo(field).id) || grouped.get('extension');
                group.fields.push(field);
            });
            return BLUEPRINT_HIERARCHY_GROUPS
                .map(group => grouped.get(group.id))
                .filter(group => group.fields.length)
                .map(group => ({
                    ...group,
                    fields: group.fields
                        .map((field, index) => ({
                            field,
                            index,
                            state: blueprintFieldEvaluation(field, evaluation),
                        }))
                        .sort((left, right) => {
                            const priority = item => {
                                if (item.state.status === 'missing' || item.state.status === 'invalid') return 0;
                                if (item.state.required) return 1;
                                if (creationFieldIsAuto(item.field)) return 2;
                                return 3;
                            };
                            return priority(left) - priority(right) || left.index - right.index;
                        })
                        .map(item => item.field),
                }));
        }

        function setCreationSectionExpanded(section, expanded) {
            if (!section) return;
            section.classList.toggle('is-collapsed', !expanded);
            const toggle = section.querySelector('.creation-section-toggle');
            if (toggle) {
                toggle.textContent = expanded ? '收起' : '展开';
                toggle.setAttribute('aria-expanded', String(expanded));
            }
        }

        function scrollCreationTarget(target) {
            if (!target) return;
            const container = target.closest('.blueprint-fields, .creation-card-fields');
            if (!container) {
                target.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                return;
            }
            const targetRect = target.getBoundingClientRect();
            const containerRect = container.getBoundingClientRect();
            const offset = targetRect.top - containerRect.top;
            const delta = targetRect.height <= containerRect.height
                ? offset - (containerRect.height - targetRect.height) / 2
                : offset - 12;
            container.scrollBy({ top: delta, behavior: 'smooth' });
        }

        function blueprintScrollTo(target, activeNode = null) {
            if (!target) return;
            const section = target.closest('.blueprint-field-group, .creation-card-section');
            if (section) setCreationSectionExpanded(section, true);
            scrollCreationTarget(target);
            const focusable = target.querySelector('input:not([disabled]), select:not([disabled]), textarea:not([disabled]), button:not([disabled])');
            focusable?.focus({ preventScroll: true });
            document.querySelectorAll('.blueprint-nav-item.active, .blueprint-nav-group.active').forEach(node => node.classList.remove('active'));
            activeNode?.classList.add('active');
        }

        function renderBlueprintFieldNav(blueprint, evaluation) {
            const container = document.getElementById('blueprintFieldNav');
            if (!container || !blueprint) return;
            container.replaceChildren();

            const header = document.createElement('div');
            header.className = 'blueprint-field-nav-header';
            header.innerHTML = '<span>填写目录</span><small>点击字段快速定位</small>';
            container.appendChild(header);

            blueprintHierarchyGroups(blueprint.fields || [], evaluation).forEach((group, groupIndex) => {
                const levelFields = group.fields;
                const states = levelFields.map(field => blueprintFieldEvaluation(field, evaluation));
                const visibleFields = levelFields.filter((field, index) => states[index].visible);
                if (!visibleFields.length) return;
                const progress = blueprintHierarchyStats(levelFields, evaluation);
                const branchKey = `blueprint:${blueprint.id || blueprint.provider}:hierarchy:${group.id}`;
                const collapsed = creationDirectoryCollapseState.has(branchKey)
                    ? creationDirectoryCollapseState.get(branchKey) === true
                    : groupIndex > 0 && !progress.missing;

                const groupButton = document.createElement('button');
                groupButton.type = 'button';
                groupButton.className = 'blueprint-nav-group';
                groupButton.setAttribute('aria-expanded', String(!collapsed));
                const groupCopy = document.createElement('span');
                groupCopy.className = 'blueprint-nav-group-copy';
                const groupTitle = document.createElement('strong');
                groupTitle.textContent = `${group.title} · ${group.label}`;
                const groupMeta = document.createElement('small');
                groupMeta.textContent = progress.missing
                    ? `待填 ${progress.missing} · ${progress.total} 项`
                    : `${progress.completed}/${progress.total} 项已处理`;
                groupCopy.append(groupTitle, groupMeta);
                const groupStatus = document.createElement('span');
                groupStatus.className = `blueprint-nav-status${progress.missing ? ' missing' : ' complete'}`;
                groupStatus.textContent = progress.missing ? '!' : '✓';
                const groupMarker = document.createElement('span');
                groupMarker.className = 'blueprint-nav-group-marker';
                groupMarker.textContent = collapsed ? '›' : '⌄';
                groupButton.append(groupStatus, groupCopy, groupMarker);
                const fieldList = document.createElement('div');
                fieldList.className = `blueprint-nav-fields${collapsed ? ' is-collapsed' : ''}`;
                groupButton.addEventListener('click', () => {
                    const nextCollapsed = !fieldList.classList.contains('is-collapsed');
                    fieldList.classList.toggle('is-collapsed', nextCollapsed);
                    creationDirectoryCollapseState.set(branchKey, nextCollapsed);
                    groupButton.setAttribute('aria-expanded', String(!nextCollapsed));
                    groupMarker.textContent = nextCollapsed ? '›' : '⌄';
                });
                container.appendChild(groupButton);

                visibleFields.forEach(field => {
                        const state = blueprintFieldEvaluation(field, evaluation);
                        const button = document.createElement('button');
                        button.type = 'button';
                        button.className = `blueprint-nav-item${state.status === 'missing' ? ' missing' : ''}${state.status === 'invalid' ? ' invalid' : ''}${state.status === 'complete' ? ' complete' : ''}`;
                        button.dataset.fieldPath = field.path;
                        const status = document.createElement('span');
                        status.className = 'blueprint-nav-field-status';
                        status.textContent = state.status === 'invalid' ? '!' : state.status === 'missing' ? '•' : state.status === 'complete' ? '✓' : '·';
                        const copy = document.createElement('span');
                        copy.className = 'blueprint-nav-item-copy';
                        const label = document.createElement('span');
                        label.textContent = field.label || field.path;
                        const value = document.createElement('small');
                        value.textContent = creationFieldDisplayValue(field, state.value);
                        copy.append(label, value);
                        button.append(status, copy);
                        button.addEventListener('click', () => {
                            blueprintScrollTo(document.querySelector(`#blueprintFields [data-field-path="${CSS.escape(field.path)}"]`), button);
                        });
                        fieldList.appendChild(button);
                });
                container.appendChild(fieldList);
            });
        }

        function renderBlueprintSummary(blueprint, evaluation) {
            const container = document.getElementById('blueprintSummary');
            if (!container || !blueprint) return;
            container.replaceChildren();
            const fields = (blueprint.fields || []).filter(field => blueprintFieldEvaluation(field, evaluation).visible);
            const completed = fields.filter(field => !creationCardValueEmpty(blueprintFieldEvaluation(field, evaluation).value));
            const totalRequired = fields.filter(field => blueprintFieldEvaluation(field, evaluation).required).length;
            const missing = evaluation?.missing_fields?.length || fields.filter(field => blueprintFieldEvaluation(field, evaluation).status === 'missing').length;

            const heading = document.createElement('div');
            heading.className = 'blueprint-summary-heading';
            heading.innerHTML = '<span>实时摘要</span><small>滚动填写时始终可见</small>';
            const progress = document.createElement('span');
            progress.className = `blueprint-summary-progress${missing ? ' pending' : ' ready'}`;
            progress.textContent = missing ? `待补 ${missing} 项` : `${Math.min(completed.length, totalRequired || completed.length)}/${totalRequired || completed.length} 项就绪`;
            heading.appendChild(progress);
            container.appendChild(heading);

            const items = document.createElement('div');
            items.className = 'blueprint-summary-items';
            const accountItem = document.createElement('button');
            accountItem.type = 'button';
            accountItem.className = `blueprint-summary-item${blueprintState.accountId ? ' filled' : ' pending'}`;
            accountItem.innerHTML = `<span class="blueprint-summary-item-label">${escapeHtml(creationAccountLabel(blueprint.provider))}</span><strong>${escapeHtml(blueprintState.accountId || '未填写')}</strong>`;
            accountItem.addEventListener('click', () => document.getElementById('blueprintAccountInput')?.focus());
            items.appendChild(accountItem);

            const selectedFields = fields.filter(field => !creationCardValueEmpty(blueprintFieldEvaluation(field, evaluation).value)).slice(0, 6);
            selectedFields.forEach(field => {
                const state = blueprintFieldEvaluation(field, evaluation);
                const item = document.createElement('button');
                item.type = 'button';
                item.className = `blueprint-summary-item${state.status === 'invalid' ? ' invalid' : ' filled'}`;
                item.innerHTML = `<span class="blueprint-summary-item-label">${escapeHtml(field.label || field.path)}</span><strong>${escapeHtml(creationFieldDisplayValue(field, state.value))}</strong>`;
                item.addEventListener('click', () => {
                    blueprintScrollTo(document.querySelector(`#blueprintFields [data-field-path="${CSS.escape(field.path)}"]`));
                });
                items.appendChild(item);
            });
            const remaining = completed.length - selectedFields.length;
            if (remaining > 0) {
                const more = document.createElement('span');
                more.className = 'blueprint-summary-more';
                more.textContent = `还有 ${remaining} 项已填写`;
                items.appendChild(more);
            }
            container.appendChild(items);
        }

        function choiceDisplayLabel(value, label = '') {
            if (label && String(label) !== String(value)) return String(label);
            const text = String(value ?? '');
            const known = {
                ANDROID: 'Android', IOS: 'iOS',
                PLACEMENT_TIKTOK: 'TikTok 信息流', PLACEMENT_PANGLE: 'Pangle',
                PLACEMENT_GLOBAL_APP_BUNDLE: 'Global App Bundle',
                AGE_13_17: '13–17 岁', AGE_18_24: '18–24 岁', AGE_25_34: '25–34 岁',
                AGE_35_44: '35–44 岁', AGE_45_54: '45–54 岁', AGE_55_64: '55–64 岁', 'AGE_65+': '65 岁以上',
            };
            if (known[text]) return known[text];
            return text.toLowerCase().split(/[_-]+/).map(part => part ? part[0].toUpperCase() + part.slice(1) : '').join(' ');
        }

        function renderChoiceTiles(options, selectedValues, multiple, labelFor, onChange) {
            const control = document.createElement('div');
            control.className = `choice-tiles${multiple ? ' multiple' : ''}`;
            const groupName = `choice-${Math.random().toString(36).slice(2)}`;
            const selected = new Set((Array.isArray(selectedValues) ? selectedValues : [selectedValues])
                .filter(value => value !== undefined && value !== null && value !== '').map(String));
            options.forEach(option => {
                const value = typeof option === 'object' ? String(option.value ?? '') : String(option);
                if (!value) return;
                const suppliedLabel = typeof option === 'object' ? (option.label || labelFor?.(option.value) || '') : (labelFor?.(option) || '');
                const label = choiceDisplayLabel(value, suppliedLabel);
                const item = document.createElement('label');
                item.className = `choice-tile${selected.has(value) ? ' selected' : ''}`;
                const input = document.createElement('input');
                input.type = multiple ? 'checkbox' : 'radio';
                input.name = groupName;
                input.value = value;
                input.checked = selected.has(value);
                input.addEventListener('change', () => {
                    if (multiple) {
                        item.classList.toggle('selected', input.checked);
                        const values = Array.from(control.querySelectorAll('input:checked')).map(node => node.value);
                        onChange(values);
                    } else if (input.checked) {
                        control.querySelectorAll('.choice-tile').forEach(node => node.classList.remove('selected'));
                        item.classList.add('selected');
                        onChange(value);
                    }
                });
                const copy = document.createElement('span');
                copy.className = 'choice-copy';
                const title = document.createElement('strong');
                title.textContent = label;
                copy.appendChild(title);
                if (label !== value) {
                    const raw = document.createElement('small');
                    raw.textContent = value;
                    copy.appendChild(raw);
                }
                item.append(input, copy);
                control.appendChild(item);
            });
            return control;
        }

        function renderBlueprintFlowbar(blueprint, evaluation) {
            const container = document.getElementById('blueprintFlowbar');
            if (!container || !blueprint) return;
            const groups = blueprintHierarchyGroups(blueprint.fields || [], evaluation);
            container.replaceChildren();
            const label = document.createElement('div');
            label.className = 'blueprint-flowbar-label';
            label.innerHTML = '<strong>投放层级</strong><small>按上游到下游填写</small>';
            container.appendChild(label);
            groups.forEach((group, index) => {
                const progress = blueprintHierarchyStats(group.fields, evaluation);
                const button = document.createElement('button');
                button.type = 'button';
                button.className = `blueprint-flow-step${index === 0 ? ' active' : ''}${progress.missing ? ' has-missing' : ''}`;
                button.dataset.step = group.id;
                button.innerHTML = `<span class="blueprint-flow-index">${String(index + 1).padStart(2, '0')}</span><span class="blueprint-flow-copy"><strong>${escapeHtml(group.label)}</strong><small>${escapeHtml(group.title)} · ${progress.missing ? `待填 ${progress.missing}` : '已就绪'}</small></span>`;
                button.addEventListener('click', () => {
                    blueprintScrollTo(document.querySelector(`#blueprintFields [data-step="${CSS.escape(group.id)}"]`));
                    container.querySelectorAll('.blueprint-flow-step').forEach(node => node.classList.toggle('active', node === button));
                });
                container.appendChild(button);
            });
            if (evaluation) {
                const summary = document.createElement('span');
                summary.className = 'blueprint-flow-summary';
                summary.textContent = evaluation.missing_fields?.length ? `${evaluation.missing_fields.length} 项待补充` : '必填参数已齐';
                container.appendChild(summary);
            }
        }

        function renderBlueprintSelector() {
            const container = document.getElementById('blueprintSelector');
            const blueprint = blueprintState.selected;
            if (!container || !blueprint?.selector) {
                if (container) container.replaceChildren();
                return;
            }
            const selector = blueprint.selector;
            const options = blueprintSelectorOptions(blueprint);
            container.replaceChildren();
            const label = document.createElement('label');
            label.className = 'blueprint-selector-label';
            label.textContent = `${blueprint.provider} · ${selector.label || (selector.dimension === 'objective' ? '推广目标' : '广告系列类型')}`;
            const control = document.createElement('select');
            const placeholder = document.createElement('option');
            placeholder.value = '';
            placeholder.textContent = '请选择入口…';
            control.appendChild(placeholder);
            for (const option of options) {
                const optionNode = document.createElement('option');
                optionNode.value = option.value;
                optionNode.textContent = option.label;
                control.appendChild(optionNode);
            }
            const current = blueprintState.values[selector.field];
            control.value = current === undefined ? '' : String(current);
            control.onchange = () => chooseBlueprintEntry(blueprint.provider, selector.dimension, control.value);
            const hint = document.createElement('div');
            hint.className = 'blueprint-selector-hint';
            hint.textContent = selector.dimension === 'objective'
                ? '先选推广目标，后续只展示该目标适用的参数。'
                : '先选广告系列类型，后续只展示该类型适用的参数。';
            container.append(label, control, hint);
        }

        function chooseBlueprintEntry(provider, dimension, value) {
            if (!value) return;
            const item = blueprintState.items.find(candidate =>
                candidate.provider === provider && candidate.selector?.dimension === dimension &&
                (candidate.selector.values || []).map(String).includes(String(value))
            );
            if (item) selectBlueprint(item.id, value);
        }

        async function loadCreationBlueprints(selectId = null) {
            const list = document.getElementById('blueprintList');
            if (list) list.innerHTML = `<div class="blueprint-empty">正在加载${blueprintState.mode === 'templates' ? '模板' : '广告创建蓝图'}…</div>`;
            try {
                const [blueprints, tools, templates, formats] = await Promise.all([
                    apiFetch('/creation-blueprints'),
                    apiFetch('/tools'),
                    apiFetch('/creation-templates').catch(() => ({ templates: [] })),
                    apiFetch('/ad-formats').catch(() => ({ formats: [] })),
                ]);
                blueprintState.items = Array.isArray(blueprints.blueprints) ? blueprints.blueprints : [];
                blueprintState.formats = Array.isArray(formats.formats) ? formats.formats : [];
                blueprintState.tools = Array.isArray(tools.tools) ? tools.tools : [];
                blueprintState.templates = Array.isArray(templates.templates) ? templates.templates : [];
                renderBlueprintList();
                if (blueprintState.mode === 'templates') {
                    const selectedTemplate = blueprintState.templates.find(item => item.template_id === blueprintState.selectedTemplateId)
                        || blueprintState.templates[0];
                    if (selectedTemplate) {
                        selectCreationTemplate(selectedTemplate.template_id);
                    } else {
                        blueprintState.selected = null;
                        renderBlueprintEditor();
                    }
                    return;
                }
                const target = selectId || blueprintState.selected?.id || blueprintState.items[0]?.id;
                if (target) selectBlueprint(target);
            } catch (error) {
                if (list) {
                    list.replaceChildren();
                    const empty = document.createElement('div');
                    empty.className = 'blueprint-empty';
                    empty.textContent = error.message || '蓝图加载失败，请稍后重试。';
                    list.appendChild(empty);
                }
            }
        }

        function blueprintFormatTokens(value) {
            return new Set(String(value || '').toLowerCase().split(/[^a-z0-9]+/).filter(Boolean));
        }

        function blueprintMatchesFormat(blueprint, format) {
            const formatId = String(format?.format_id || '').toLowerCase();
            const category = String(format?.category || '').toLowerCase();
            const blueprintFormat = String(blueprint?.ad_format || '').toLowerCase();
            const blueprintSuffix = String(blueprint?.id || '').split('.').pop().toLowerCase();
            if ([formatId, category].some(value => value && [blueprintFormat, blueprintSuffix].includes(value))) {
                return true;
            }
            const formatTokens = new Set([...blueprintFormatTokens(formatId), ...blueprintFormatTokens(category)]);
            const blueprintTokens = new Set([...blueprintFormatTokens(blueprintFormat), ...blueprintFormatTokens(blueprintSuffix)]);
            return [...formatTokens].some(token => blueprintTokens.has(token));
        }

        function renderBlueprintList() {
            const list = document.getElementById('blueprintList');
            if (!list) return;
            list.replaceChildren();
            const toolbar = document.createElement('div');
            toolbar.className = 'blueprint-list-toolbar';
            const toolbarTitle = document.createElement('div');
            toolbarTitle.className = 'blueprint-list-toolbar-title';
            toolbarTitle.innerHTML = blueprintState.mode === 'templates'
                ? '<strong>模板库</strong><span>只管理已保存模板，不重复展示系统蓝图</span>'
                : '<strong>创建工作台</strong><span>先选我的模板，也可以从系统蓝图开始</span>';
            if (blueprintState.mode === 'templates') {
                const wizardButton = document.createElement('button');
                wizardButton.type = 'button';
                wizardButton.className = 'blueprint-list-open-wizard';
                wizardButton.textContent = '去创建向导';
                wizardButton.onclick = () => openBlueprintManager();
                toolbarTitle.appendChild(wizardButton);
            }
            const search = document.createElement('input');
            search.type = 'search';
            search.className = 'blueprint-list-search';
            search.placeholder = '搜索广告类型…';
            search.value = blueprintState.listQuery || '';
            search.setAttribute('aria-label', '搜索广告创建模板');
            search.addEventListener('input', () => {
                blueprintState.listQuery = search.value;
                renderBlueprintList();
                const next = document.querySelector('.blueprint-list-search');
                next?.focus({ preventScroll: true });
                if (next) next.setSelectionRange(blueprintState.listQuery.length, blueprintState.listQuery.length);
            });
            const providers = [...new Set(blueprintState.items.map(item => item.provider))];
            const filter = document.createElement('select');
            filter.className = 'blueprint-list-filter';
            filter.setAttribute('aria-label', '按广告平台筛选');
            [['all', '全部渠道'], ...providers.map(provider => [provider, creationProviderLabel(provider)])].forEach(([value, label]) => {
                const option = document.createElement('option');
                option.value = value;
                option.textContent = label;
                option.selected = value === (blueprintState.listProvider || 'all');
                filter.appendChild(option);
            });
            filter.addEventListener('change', () => {
                blueprintState.listProvider = filter.value;
                renderBlueprintList();
            });
            toolbar.append(toolbarTitle, search, filter);
            list.appendChild(toolbar);
            const stats = document.createElement('div');
            stats.className = 'blueprint-list-stats';
            const statValues = blueprintState.mode === 'templates'
                ? [
                    ['模板总数', blueprintState.templates.length],
                    ['已启用', blueprintState.templates.filter(item => item.status === 'active').length],
                    ['默认模板', blueprintState.templates.filter(item => item.is_default).length],
                ]
                : [
                    ['广告类型', blueprintState.items.length],
                    ['渠道', new Set(blueprintState.items.map(item => item.provider)).size],
                    ['草稿可校验', blueprintState.items.filter(item => ['supported_dry_run', 'partial_dry_run'].includes(item.support?.level)).length],
                ];
            statValues.forEach(([label, value]) => {
                const stat = document.createElement('div');
                stat.className = 'blueprint-list-stat';
                stat.innerHTML = `<strong>${escapeHtml(String(value))}</strong><span>${escapeHtml(label)}</span>`;
                stats.appendChild(stat);
            });
            list.appendChild(stats);
            const items = document.createElement('div');
            items.className = 'blueprint-list-items';
            list.appendChild(items);
            const query = String(blueprintState.listQuery || '').trim().toLowerCase();
            const matches = item => {
                const provider = item.provider || item.platform;
                if (blueprintState.listProvider !== 'all' && provider !== blueprintState.listProvider) return false;
                if (!query) return true;
                return [item.title, item.name, item.id, provider, item.ad_format, item.format_id, item.category, item.scope_label, item.selector?.label]
                    .filter(Boolean).join(' ').toLowerCase().includes(query);
            };
            const visibleTemplates = blueprintState.templates.filter(matches);
            const builtinTemplates = visibleTemplates.filter(template => template.source === 'builtin');
            const userTemplates = visibleTemplates.filter(template => template.source !== 'builtin');
            const visibleItems = blueprintState.mode === 'templates' ? [] : blueprintState.items.filter(matches);
            const visibleFormats = blueprintState.mode === 'templates' ? [] : blueprintState.formats.filter(format => {
                if (!matches(format)) return false;
                return !blueprintState.items.some(item => blueprintMatchesFormat(item, format));
            });
            const renderSection = (title, subtitle, values, renderItem) => {
                if (!values.length) return;
                const section = document.createElement('section');
                section.className = 'blueprint-list-section';
                const heading = document.createElement('div');
                heading.className = 'blueprint-list-section-heading';
                heading.innerHTML = `<strong>${escapeHtml(title)}</strong><span>${escapeHtml(subtitle)}</span>`;
                section.appendChild(heading);
                values.forEach(item => section.appendChild(renderItem(item)));
                items.appendChild(section);
            };
            const renderTemplate = template => {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = `blueprint-list-item blueprint-template-item${blueprintState.selectedTemplateId === template.template_id ? ' active' : ''}`;
                button.onclick = () => selectCreationTemplate(template.template_id);
                button.title = template.required_inputs?.length
                    ? `仍需补充：${template.required_inputs.join('、')}`
                    : '可直接应用此模板';
                const title = document.createElement('span');
                title.className = 'blueprint-list-title';
                title.textContent = template.name || '未命名模板';
                const meta = document.createElement('span');
                meta.className = 'blueprint-list-meta';
                const sourceLabel = template.source === 'builtin' ? '内置' : (template.scope_label || '个人通用');
                const accountLabel = template.account_id ? ` · 账号 ${template.account_id}` : '';
                const usageLabel = template.source === 'builtin'
                    ? ' · 只读'
                    : ` · 使用 ${template.usage_count || 0} 次`;
                meta.textContent = `${creationProviderLabel(template.provider)} · ${sourceLabel}${accountLabel}${template.is_default ? ' · 默认' : ''}${template.status !== 'active' ? ' · 已停用' : ''} · ${creationTemplateVerificationLabel(template.verification_status)} · ${template.covered_fields || 0} 项${usageLabel}`;
                button.append(title, meta);
                const status = document.createElement('span');
                status.className = `blueprint-template-status ${template.source === 'builtin' ? 'builtin' : (template.status === 'active' ? 'active' : 'inactive')}`;
                status.textContent = template.source === 'builtin'
                    ? '内置'
                    : (template.status === 'active' ? '启用' : '停用');
                button.appendChild(status);
                return button;
            };
            renderSection('内置模板', '绑定受控测试账号，应用后仍需补充账户资产与素材', builtinTemplates, renderTemplate);
            renderSection('我的模板', '可按账户与地区复用并继续编辑', userTemplates, renderTemplate);
            renderSection('系统蓝图', '平台维护的字段与联动规则', visibleItems, item => {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = `blueprint-list-item${!blueprintState.selectedTemplateId && blueprintState.selected?.id === item.id ? ' active' : ''}`;
                button.onclick = () => selectBlueprint(item.id);
                const title = document.createElement('span');
                title.className = 'blueprint-list-title';
                title.textContent = item.title || item.id;
                const meta = document.createElement('span');
                meta.className = 'blueprint-list-meta';
                const contract = item.ui_contract || {};
                const support = item.support || {};
                meta.textContent = `${creationProviderLabel(item.provider)} · ${item.ad_format} · ${contract.field_count || item.fields?.length || 0} 项 · ${blueprintSupportLabel(support)}`;
                button.append(title, meta);
                const supportBadge = document.createElement('span');
                supportBadge.className = `blueprint-support-badge ${blueprintSupportClass(support)}`;
                supportBadge.textContent = blueprintSupportLabel(support);
                button.appendChild(supportBadge);
                return button;
            });
            renderSection('暂未纳入向导', '目录已有记录，但当前没有完整创建合同', visibleFormats, format => {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'blueprint-list-item blueprint-unavailable-item';
                button.title = (format.gaps || []).join('、') || '当前没有可信的创建 Tool';
                const title = document.createElement('span');
                title.className = 'blueprint-list-title';
                title.textContent = format.title || format.name || format.format_id;
                const meta = document.createElement('span');
                meta.className = 'blueprint-list-meta';
                meta.textContent = `${creationProviderLabel(format.platform)} · ${format.format_id} · ${format.coverage === 'declared_only' ? '仅目录声明' : '创建字段待补齐'}`;
                button.append(title, meta);
                const badge = document.createElement('span');
                badge.className = 'blueprint-support-badge declared';
                badge.textContent = '暂不支持';
                button.appendChild(badge);
                return button;
            });
            if (!visibleTemplates.length && !visibleItems.length && !visibleFormats.length) {
                const empty = document.createElement('div');
                empty.className = 'blueprint-empty';
                empty.textContent = '没有匹配的模板或广告类型，换个关键词试试。';
                items.appendChild(empty);
            }
        }

        function selectBlueprint(blueprintId, selectorValue = null, template = null) {
            const item = blueprintState.items.find(value => value.id === blueprintId);
            if (!item) return;
            if (!template) {
                template = blueprintState.templates.find(candidate => candidate.status === 'active'
                    && candidate.is_default
                    && candidate.blueprint_id === item.id
                    && (!candidate.blueprint_version || candidate.blueprint_version === item.version)
                    && (candidate.scope_type === 'general'
                        || (candidate.scope_type === 'account' && candidate.account_id === blueprintState.accountId))
                ) || null;
            }
            blueprintState.selected = item;
            blueprintState.values = blueprintDefaultValues(item);
            blueprintState.previousValues = {};
            blueprintState.evaluation = null;
            blueprintState.localFiles = {};
            blueprintState.selectionTokens = {};
            blueprintState.selectionTokenTools = {};
            blueprintState.lookupOptions = {};
            blueprintState.selectedTemplateId = template?.template_id || '';
            const selector = item.selector;
            const initialValue = selectorValue || selector?.values?.[0];
            if (selector?.field && initialValue !== undefined) blueprintState.values[selector.field] = initialValue;
            if (template?.values && typeof template.values === 'object') {
                Object.assign(blueprintState.values, template.values);
                if (template.account_id) blueprintState.accountId = template.account_id;
            }
            const templatePanel = document.getElementById('blueprintTemplatePanel');
            if (templatePanel) templatePanel.hidden = true;
            blueprintState.templatePanelOpen = false;
            blueprintState.templateSaveAsNew = false;
            renderBlueprintList();
            renderBlueprintEditor();
            if (template) showBlueprintNotice(`已应用“${template.name || '我的模板'}”，你仍可修改本次投放参数。`);
            if (selector?.field) evaluateBlueprintDraft(selector.field);
        }

        function selectCreationTemplate(templateId) {
            const template = blueprintState.templates.find(item => item.template_id === templateId);
            if (!template) return;
            const blueprint = blueprintState.items.find(item => item.id === template.blueprint_id && (
                !template.blueprint_version || item.version === template.blueprint_version
            )) || blueprintState.items.find(item => item.id === template.blueprint_id);
            if (!blueprint) {
                showBlueprintNotice('模板依赖的系统蓝图已升级或下线，请复制模板后重新配置。');
                return;
            }
            selectBlueprint(blueprint.id, null, template);
            if (blueprintState.mode === 'wizard' && template.status === 'active') {
                apiFetch(`/creation-templates/${encodeURIComponent(templateId)}/apply`, { method: 'POST' }).catch(() => {});
            } else if (blueprintState.mode === 'wizard') {
                showBlueprintNotice('这是已停用模板，仅用于查看和编辑；重新启用后才能带入对话。');
            }
        }

        function toggleCreationTemplatePanel(force, saveAsNew = false) {
            const panel = document.getElementById('blueprintTemplatePanel');
            if (!panel) return;
            const open = force === undefined ? panel.hidden : Boolean(force);
            panel.hidden = !open;
            blueprintState.templatePanelOpen = open;
            blueprintState.templateSaveAsNew = open && saveAsNew;
            if (!open) return;
            const template = !blueprintState.templateSaveAsNew
                ? blueprintState.templates.find(item => item.template_id === blueprintState.selectedTemplateId)
                : null;
            const fields = {
                creationTemplateName: template?.name || '',
                creationTemplateScope: template?.scope_type || 'general',
                creationTemplateAccount: template?.account_id || blueprintState.accountId || '',
                creationTemplateRegion: template?.region || '',
                creationTemplateTags: Array.isArray(template?.tags) ? template.tags.join(', ') : '',
                creationTemplateDescription: template?.description || '',
            };
            Object.entries(fields).forEach(([id, value]) => {
                const control = document.getElementById(id);
                if (control) control.value = value;
            });
            const title = document.getElementById('blueprintTemplatePanelTitle');
            if (title) title.textContent = template ? '更新当前模板' : '保存当前参数为模板';
            const submit = document.getElementById('creationTemplateSubmitButton');
            if (submit) submit.textContent = template ? '保存修改' : '保存模板';
            const defaultInput = document.getElementById('creationTemplateDefault');
            if (defaultInput) defaultInput.checked = Boolean(template?.is_default);
        }

        function creationTemplatePayload() {
            const blueprint = blueprintState.selected;
            if (!blueprint) return null;
            return {
                name: document.getElementById('creationTemplateName')?.value.trim() || '',
                description: document.getElementById('creationTemplateDescription')?.value.trim() || '',
                provider: blueprint.provider,
                blueprint_id: blueprint.id,
                blueprint_version: blueprint.version,
                ad_format: blueprint.ad_format,
                scope_type: document.getElementById('creationTemplateScope')?.value || 'general',
                account_id: document.getElementById('creationTemplateAccount')?.value.trim() || '',
                region: document.getElementById('creationTemplateRegion')?.value.trim() || '',
                tags: (document.getElementById('creationTemplateTags')?.value || '').split(',').map(item => item.trim()).filter(Boolean),
                values: { ...(blueprintState.values || {}) },
                status: 'active',
                is_default: Boolean(document.getElementById('creationTemplateDefault')?.checked),
            };
        }

        async function saveCreationTemplate(forceCreate = false) {
            const payload = creationTemplatePayload();
            if (!payload) return;
            if (!payload.name) {
                showBlueprintNotice('请先填写模板名称。');
                document.getElementById('creationTemplateName')?.focus();
                return;
            }
            const templateId = forceCreate || blueprintState.templateSaveAsNew ? '' : blueprintState.selectedTemplateId;
            try {
                const result = await apiFetch(templateId
                    ? `/creation-templates/${encodeURIComponent(templateId)}`
                    : '/creation-templates', {
                        method: templateId ? 'PATCH' : 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload),
                    });
                const index = blueprintState.templates.findIndex(item => item.template_id === result.template_id);
                if (index >= 0) blueprintState.templates[index] = result;
                else blueprintState.templates.unshift(result);
                blueprintState.selectedTemplateId = result.template_id;
                toggleCreationTemplatePanel(false);
                renderBlueprintList();
                renderBlueprintEditor();
                showBlueprintNotice(`模板“${result.name}”已保存，可在左侧“我的模板”中复用。`);
            } catch (error) {
                showBlueprintNotice(error.message || '模板保存失败。');
            }
        }

        function updateSelectedCreationTemplate() {
            if (!blueprintState.selectedTemplateId) return;
            const template = blueprintState.templates.find(item => item.template_id === blueprintState.selectedTemplateId);
            if (template?.source === 'builtin') {
                showBlueprintNotice('内置模板为只读配置，请使用“复制”保存为个人模板。');
                return;
            }
            toggleCreationTemplatePanel(true);
        }

        async function duplicateSelectedCreationTemplate() {
            const templateId = blueprintState.selectedTemplateId;
            if (!templateId) return;
            const source = blueprintState.templates.find(item => item.template_id === templateId);
            const name = window.prompt('请输入副本名称', `${source?.name || '创建模板'} · 副本`);
            if (!name) return;
            try {
                const result = await apiFetch(`/creation-templates/${encodeURIComponent(templateId)}/duplicate`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }),
                });
                blueprintState.templates.unshift(result);
                blueprintState.selectedTemplateId = result.template_id;
                renderBlueprintList();
                renderBlueprintEditor();
                showBlueprintNotice(`模板副本“${result.name}”已创建。`);
            } catch (error) { showBlueprintNotice(error.message || '模板复制失败。'); }
        }

        async function toggleSelectedCreationTemplateStatus() {
            const template = blueprintState.templates.find(item => item.template_id === blueprintState.selectedTemplateId);
            if (!template) return;
            if (template.source === 'builtin') {
                showBlueprintNotice('内置模板不能停用，请复制后管理个人模板。');
                return;
            }
            const nextStatus = template.status === 'active' ? 'inactive' : 'active';
            try {
                const result = await apiFetch(`/creation-templates/${encodeURIComponent(template.template_id)}`, {
                    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status: nextStatus }),
                });
                const index = blueprintState.templates.findIndex(item => item.template_id === result.template_id);
                if (index >= 0) blueprintState.templates[index] = result;
                renderBlueprintList();
                renderBlueprintEditor();
                showBlueprintNotice(nextStatus === 'active' ? '模板已重新启用。' : '模板已停用，不会再出现在可应用模板中。');
            } catch (error) { showBlueprintNotice(error.message || '模板状态更新失败。'); }
        }

        async function deleteSelectedCreationTemplate() {
            const template = blueprintState.templates.find(item => item.template_id === blueprintState.selectedTemplateId);
            if (!template || !window.confirm(`确定删除模板“${template.name}”吗？`)) return;
            if (template.source === 'builtin') {
                showBlueprintNotice('内置模板不能删除，请复制后管理个人模板。');
                return;
            }
            try {
                await apiFetch(`/creation-templates/${encodeURIComponent(template.template_id)}`, { method: 'DELETE' });
                blueprintState.templates = blueprintState.templates.filter(item => item.template_id !== template.template_id);
                blueprintState.selectedTemplateId = '';
                selectBlueprint(blueprintState.selected?.id || blueprintState.items[0]?.id);
                showBlueprintNotice('模板已删除。');
            } catch (error) { showBlueprintNotice(error.message || '模板删除失败。'); }
        }

        function renderBlueprintEditor() {
            const blueprint = blueprintState.selected;
            const title = document.getElementById('blueprintEditorTitle');
            const meta = document.getElementById('blueprintEditorMeta');
            if (!blueprint) {
                if (title) title.textContent = '还没有可管理的模板';
                if (meta) meta.textContent = '请先在广告创建向导中填写参数并保存模板';
                ['blueprintTemplateSaveButton', 'blueprintTemplateUpdateButton', 'blueprintTemplateDuplicateButton', 'blueprintTemplateStatusButton', 'blueprintTemplateDeleteButton'].forEach(id => {
                    const button = document.getElementById(id);
                    if (button) button.hidden = true;
                });
                const panel = document.getElementById('blueprintTemplatePanel');
                if (panel) panel.hidden = true;
                ['blueprintFields', 'blueprintFieldNav', 'blueprintSummary', 'blueprintContractOverview'].forEach(id => {
                    const container = document.getElementById(id);
                    if (container) container.innerHTML = '<div class="blueprint-empty">暂无模板内容。模板从广告创建向导中保存。</div>';
                });
                const readiness = document.getElementById('blueprintReadiness');
                if (readiness) readiness.textContent = '暂无模板';
                return;
            }
            const template = blueprintState.templates.find(item => item.template_id === blueprintState.selectedTemplateId);
            const managementMode = blueprintState.mode === 'templates';
            if (title) title.textContent = managementMode && template ? template.name : blueprint.title || blueprint.id;
            if (meta) meta.textContent = template && managementMode
                ? `${creationProviderLabel(blueprint.provider)} · ${blueprint.ad_format} · ${template.account_id ? `账号 ${template.account_id} · ` : ''}${template.source === 'builtin' ? '内置只读' : (template.scope_label || '个人通用')} · ${template.source === 'builtin' ? creationTemplateVerificationLabel(template.verification_status) : (template.status === 'active' ? '已启用' : '已停用')} · ${template.source === 'builtin' ? '应用后仍需补充资源' : `使用 ${template.usage_count || 0} 次`} · 蓝图 v${blueprint.version}`
                : `${creationProviderLabel(blueprint.provider)} · ${blueprint.ad_format} · 蓝图 v${blueprint.version}${template ? ` · 已应用模板：${template.name}` : ''}`;
            const saveButton = document.getElementById('blueprintTemplateSaveButton');
            const updateButton = document.getElementById('blueprintTemplateUpdateButton');
            const duplicateButton = document.getElementById('blueprintTemplateDuplicateButton');
            const statusButton = document.getElementById('blueprintTemplateStatusButton');
            const deleteButton = document.getElementById('blueprintTemplateDeleteButton');
            if (saveButton) {
                saveButton.textContent = template ? '另存为模板' : '保存为模板';
                saveButton.hidden = managementMode;
            }
            if (updateButton) updateButton.hidden = !managementMode || !template || template.source === 'builtin';
            if (duplicateButton) duplicateButton.hidden = !managementMode || !template;
            if (statusButton) {
                statusButton.hidden = !managementMode || !template || template.source === 'builtin';
                statusButton.textContent = template?.status === 'active' ? '停用' : '启用';
            }
            if (deleteButton) deleteButton.hidden = !managementMode || !template || template.source === 'builtin';
            const accountInput = document.getElementById('blueprintAccountInput');
            const accountLabel = document.querySelector('label[for="blueprintAccountInput"]');
            if (accountLabel) accountLabel.innerHTML = `${escapeHtml(creationAccountLabel(blueprint.provider))} <span class="blueprint-required">*</span>`;
            if (accountInput) {
                accountInput.placeholder = `请输入本次要操作的${creationAccountLabel(blueprint.provider)}`;
                accountInput.value = blueprintState.accountId || '';
                accountInput.oninput = () => {
                    blueprintState.accountId = accountInput.value.trim();
                    refreshLookupAccountState(document.getElementById('blueprintFields'));
                    renderBlueprintSummary(blueprint, blueprintState.evaluation);
                };
            }
            renderBlueprintSelector();
            renderBlueprintFlowbar(blueprint, blueprintState.evaluation);
            renderBlueprintContractOverview(blueprint);
            renderBlueprintFields(blueprintState.evaluation);
            renderBlueprintFieldNav(blueprint, blueprintState.evaluation);
            renderBlueprintSummary(blueprint, blueprintState.evaluation);
        }

        function renderBlueprintContractOverview(blueprint) {
            const container = document.getElementById('blueprintContractOverview');
            if (!container || !blueprint) return;
            container.replaceChildren();
            const contract = blueprint.ui_contract || {};
            const support = blueprint.support || {};
            const header = document.createElement('div');
            header.className = 'blueprint-contract-heading';
            const copy = document.createElement('div');
            copy.innerHTML = `<strong>这类广告怎么填</strong><small>${escapeHtml(blueprint.description || '字段来源于已注册的渠道 Tool，系统会按层级和联动关系组织。')}</small>`;
            const badge = document.createElement('span');
            badge.className = `blueprint-support-badge ${blueprintSupportClass(support)}`;
            badge.textContent = blueprintSupportLabel(support);
            header.append(copy, badge);
            container.appendChild(header);
            const metrics = document.createElement('div');
            metrics.className = 'blueprint-contract-metrics';
            [
                ['字段', contract.field_count || blueprint.fields?.length || 0],
                ['必填', contract.required_count || 0],
                ['契约默认', contract.declared_default_count || 0],
                ['可选查询', contract.lookup_count || 0],
                ['平台特有', contract.advanced_count || 0],
            ].forEach(([label, value]) => {
                const metric = document.createElement('div');
                metric.className = 'blueprint-contract-metric';
                metric.innerHTML = `<strong>${escapeHtml(String(value))}</strong><span>${escapeHtml(label)}</span>`;
                metrics.appendChild(metric);
            });
            container.appendChild(metrics);
            const selectedTemplate = blueprintState.templates.find(item =>
                item.template_id === blueprintState.selectedTemplateId
            );
            if (selectedTemplate?.source === 'builtin' && Array.isArray(selectedTemplate.required_inputs)
                && selectedTemplate.required_inputs.length) {
                const requirements = document.createElement('div');
                requirements.className = 'blueprint-template-requirements';
                const heading = document.createElement('strong');
                heading.textContent = '应用模板后仍需补充';
                const list = document.createElement('span');
                list.textContent = selectedTemplate.required_inputs.join('、');
                requirements.append(heading, list);
                container.appendChild(requirements);
            }
            const hierarchies = Array.isArray(contract.hierarchies) ? contract.hierarchies : [];
            if (hierarchies.length) {
                const hierarchy = document.createElement('div');
                hierarchy.className = 'blueprint-contract-hierarchies';
                hierarchy.innerHTML = '<span>层级结构</span>';
                hierarchies.forEach(item => {
                    const chip = document.createElement('span');
                    chip.textContent = `${item.name} · ${item.field_count}`;
                    hierarchy.appendChild(chip);
                });
                container.appendChild(hierarchy);
            }
            const notices = [];
            if (support.level === 'declared_only') notices.push('该广告类型已有渠道目录记录，但当前没有可验证的创建 Tool，因此不会出现在可提交创建流程中。');
            if (Array.isArray(support.gaps) && support.gaps.length) notices.push(`当前边界：${support.gaps.slice(0, 3).join('、')}`);
            if (notices.length) {
                const notice = document.createElement('div');
                notice.className = `blueprint-contract-notice ${support.level === 'declared_only' ? 'warning' : ''}`;
                notice.textContent = notices.join(' ');
                container.appendChild(notice);
            }
        }

        function renderBlueprintFields(evaluation) {
            const container = document.getElementById('blueprintFields');
            const blueprint = blueprintState.selected;
            if (!container || !blueprint) return;
            container.replaceChildren();
            const stateMap = new Map((evaluation?.fields || []).map(item => [item.path, item]));
            const groups = blueprintHierarchyGroups(blueprint.fields || [], evaluation);
            groups.forEach((group, groupIndex) => {
                const section = document.createElement('section');
                const progress = blueprintHierarchyStats(group.fields, evaluation);
                const branchKey = `blueprint:${blueprint.id || blueprint.provider}:hierarchy:${group.id}`;
                const defaultCollapsed = groupIndex > 0 && !progress.missing;
                const collapsed = creationDirectoryCollapseState.has(branchKey)
                    ? creationDirectoryCollapseState.get(branchKey) === true
                    : defaultCollapsed;
                section.className = `blueprint-field-group${groupIndex === 0 ? ' active' : ''}${collapsed ? ' is-collapsed' : ''}`;
                section.dataset.hierarchy = group.id;
                section.dataset.step = group.id;
                const sectionHeader = document.createElement('div');
                sectionHeader.className = 'blueprint-field-group-header';
                sectionHeader.innerHTML = `<div class="blueprint-field-group-heading"><span class="blueprint-field-group-index">${String(groupIndex + 1).padStart(2, '0')}</span><div><span class="blueprint-field-group-kicker">${escapeHtml(group.title)}</span><h3>${escapeHtml(group.label)}</h3><p>${escapeHtml(group.description)}</p></div></div><span class="blueprint-field-group-count">${progress.required ? `${progress.required} 必填 · ` : ''}${progress.total} 项</span>`;
                const sectionToggle = document.createElement('button');
                sectionToggle.type = 'button';
                sectionToggle.className = 'creation-section-toggle';
                sectionToggle.setAttribute('aria-expanded', String(!section.classList.contains('is-collapsed')));
                sectionToggle.textContent = section.classList.contains('is-collapsed') ? '展开' : '收起';
                sectionToggle.addEventListener('click', event => {
                    event.stopPropagation();
                    setCreationSectionExpanded(section, section.classList.contains('is-collapsed'));
                });
                sectionHeader.appendChild(sectionToggle);
                section.appendChild(sectionHeader);
                const sectionFields = document.createElement('div');
                sectionFields.className = 'blueprint-field-group-fields';
                section.appendChild(sectionFields);
                container.appendChild(section);
                for (const field of group.fields) {
                const fieldRef = blueprintToolFieldSchema(field.tool_ref);
                const schema = fieldRef.schema || {};
                const sourceTool = (blueprintState.tools || []).find(item => item.name === fieldRef.toolName);
                const schemaRequired = Boolean(
                    schema.required ||
                    sourceTool?.input_schema?.required?.includes?.(fieldRef.fieldPath)
                );
                const fieldSource = schema.lookup_tool || schema.lookup?.tool
                    ? 'lookup'
                    : field.source || (schema.enum || schema.items?.enum ? 'enum' : 'tool_schema');
                const fieldView = {
                    ...field,
                    source: fieldSource,
                    presentation: field.presentation || schema.presentation,
                    accept: field.accept || schema.accept,
                    lookup_tool: field.lookup_tool || schema.lookup_tool,
                    lookup_result_key: field.lookup_result_key || schema.lookup_result_key,
                    lookup_query_field: field.lookup_query_field || schema.lookup_query_field,
                    lookup_defaults: field.lookup_defaults || schema.lookup_defaults,
                    manual_entry: field.manual_entry || schema.manual_entry,
                };
                const state = stateMap.get(field.path) || {
                    visible: true,
                    required: Boolean(field.required || schemaRequired),
                    state: 'optional',
                };
                const wrapper = document.createElement('div');
                const wideField = fieldView.source === 'lookup'
                    || ['asset_picker', 'file_reference', 'text_list', 'object_editor'].includes(fieldView.presentation)
                    || schema.type === 'object' || schema.type === 'array' || Array.isArray(schema.type);
                wrapper.className = `blueprint-field${wideField ? ' wide' : ''}${state.visible === false ? ' hidden' : ''}${state.state === 'missing' ? ' missing' : ''}${state.state === 'invalid' ? ' invalid' : ''}`;
                wrapper.dataset.fieldPath = field.path;
                const label = document.createElement('label');
                label.className = 'blueprint-field-label';
                label.textContent = field.label || field.path;
                if (state.required) {
                    const required = document.createElement('span');
                    required.className = 'blueprint-required';
                    required.textContent = '*';
                    label.appendChild(required);
                }
                wrapper.appendChild(label);
                const fieldHint = schemaConstraintHint(schema);
                const fieldDescription = [field.description || schema.description, fieldHint ? `参数限制：${fieldHint}` : '']
                    .filter(Boolean).join('；');
                if (fieldDescription) {
                    const help = document.createElement('div');
                    help.className = 'blueprint-field-help';
                    help.textContent = fieldDescription;
                    wrapper.appendChild(help);
                }
                const options = blueprintOptions(fieldView, state);
                const defaultValue = blueprintFieldDefault(field);
                const displayValue = state.value !== undefined && state.value !== null
                    ? state.value : blueprintState.values[field.path] !== undefined
                        ? blueprintState.values[field.path] : defaultValue;
                let control;
                if (fieldView.presentation === 'file_reference') {
                    control = document.createElement('div');
                    control.className = 'asset-picker';
                    const idInput = document.createElement('input');
                    idInput.type = 'text';
                    idInput.placeholder = '填写已上传的素材 ID，或先选择本地文件作为草稿';
                    idInput.value = displayValue === undefined ? '' : String(displayValue);
                    idInput.addEventListener('change', () => updateBlueprintField(field, idInput.value.trim()));
                    const fileInput = document.createElement('input');
                    fileInput.type = 'file';
                    fileInput.accept = fieldView.accept || '*/*';
                    fileInput.addEventListener('change', () => {
                        const file = fileInput.files?.[0];
                        if (!file) return;
                        blueprintState.localFiles[field.path] = {
                            local_file: file.name,
                            mime_type: file.type || 'application/octet-stream',
                            size_bytes: file.size,
                            source: 'local_staging',
                        };
                        const note = control.querySelector('.asset-picker-note');
                        if (note) note.textContent = `已加入本地草稿：${file.name}（未上传，提交前仍需素材 ID）`;
                    });
                    control.append(idInput, fileInput);
                    const note = document.createElement('div');
                    note.className = 'asset-picker-note';
                    note.textContent = '本地文件仅用于准备素材，不会自动上传；执行前仍需对应平台素材 ID。';
                    control.appendChild(note);
                } else if (fieldView.presentation === 'asset_picker') {
                    control = document.createElement('div');
                    control.className = 'asset-picker';
                    const fileInput = document.createElement('input');
                    fileInput.type = 'file';
                    fileInput.multiple = true;
                    fileInput.accept = fieldView.accept || '*/*';
                    fileInput.addEventListener('change', () => {
                        const existing = Array.isArray(blueprintState.values[field.path]) ? blueprintState.values[field.path] : [];
                        const selected = Array.from(fileInput.files || []).map(file => ({
                            local_file: file.name, mime_type: file.type || 'application/octet-stream', size_bytes: file.size,
                            source: 'local_staging',
                        }));
                        blueprintState.values[field.path] = [...existing, ...selected];
                        evaluateBlueprintDraft(field.path);
                    });
                    control.appendChild(fileInput);
                    const staged = Array.isArray(displayValue) ? displayValue : [];
                    if (staged.length) {
                        const list = document.createElement('div');
                        list.className = 'asset-picker-list';
                        staged.slice(0, 20).forEach(item => {
                            const chip = document.createElement('span');
                            chip.className = 'asset-chip';
                            chip.textContent = item && typeof item === 'object'
                                ? `${item.local_file || item.asset_id || item.name || '素材'}${item.source === 'local_staging' ? ' · 未上传' : ''}`
                                : String(item);
                            list.appendChild(chip);
                        });
                        control.appendChild(list);
                    }
                    const note = document.createElement('div');
                    note.className = 'asset-picker-note';
                    note.textContent = '可选择本地文件加入草稿；当前只保存文件信息，不上传到广告平台。';
                    control.appendChild(note);
                } else if (fieldView.presentation === 'derived_readonly') {
                    control = document.createElement('input');
                    control.className = 'derived-readonly';
                    control.readOnly = true;
                    control.disabled = true;
                    control.value = displayValue === undefined ? (options[0] || '') : String(displayValue);
                } else if (fieldView.source === 'lookup') {
                    const lookupRef = blueprintToolFieldSchema(field.tool_ref);
                    const lookupKey = lookupRef.fieldPath || field.path;
                    control = renderLookupPicker({ ...fieldView, value: displayValue, tool: lookupRef.toolName }, {
                        platform: blueprint.provider,
                        accountId: blueprintState.accountId,
                        getAccountId: () => blueprintState.accountId,
                        accountRequired: lookupSourceAccountRequired(fieldView.lookup_tool || lookupRef.schema?.lookup_tool || lookupRef.schema?.lookup?.tool),
                        getLookupContext: blueprintLookupContext,
                        targetToolName: lookupRef.toolName,
                        fieldName: lookupKey,
                        selectionTokens: blueprintState.selectionTokens,
                        optionsStore: blueprintState.lookupOptions,
                        onSelection: ({ value, tokens }) => {
                            if (tokens) {
                                blueprintState.selectionTokens[lookupKey] = tokens;
                                blueprintState.selectionTokenTools[lookupKey] = lookupRef.toolName;
                            } else {
                                delete blueprintState.selectionTokens[lookupKey];
                                delete blueprintState.selectionTokenTools[lookupKey];
                            }
                            updateBlueprintField(field, value);
                        },
                    });
                } else if (schema.type === 'object') {
                    control = renderStructuredObjectEditor(
                        schema,
                        displayValue,
                        value => updateBlueprintField(field, value),
                        null,
                        {
                            platform: blueprint.provider,
                            accountId: blueprintState.accountId,
                            getAccountId: () => blueprintState.accountId,
                            targetToolName: blueprintToolFieldSchema(field.tool_ref).toolName,
                            fieldPath: blueprintToolFieldSchema(field.tool_ref).fieldPath,
                            getLookupContext: blueprintLookupContext,
                            selectionTokens: blueprintState.selectionTokens,
                            optionsStore: blueprintState.lookupOptions,
                            onSelection: ({ fieldName, tokens }) => {
                                if (tokens) {
                                    blueprintState.selectionTokens[fieldName] = tokens;
                                    blueprintState.selectionTokenTools[fieldName] = blueprintToolFieldSchema(field.tool_ref).toolName;
                                } else {
                                    delete blueprintState.selectionTokens[fieldName];
                                    delete blueprintState.selectionTokenTools[fieldName];
                                }
                            },
                        },
                    );
                } else if (field.presentation === 'text_list') {
                    control = document.createElement('textarea');
                    control.className = 'asset-text-list';
                    control.placeholder = '每行填写一条';
                } else if (options.length) {
                    const arraySchema = schema.type === 'array' || (Array.isArray(schema.type) && schema.type.includes('array'));
                    const useChoiceTiles = arraySchema || options.length <= 6;
                    if (useChoiceTiles) {
                        control = renderChoiceTiles(options, displayValue, arraySchema, option => blueprintOptionLabel(field, option), value => updateBlueprintField(field, value));
                        control.dataset.customChoice = 'true';
                    } else {
                        control = document.createElement('select');
                    const placeholder = document.createElement('option');
                    placeholder.value = '';
                    placeholder.textContent = state.required ? '请选择…' : '不设置';
                    control.appendChild(placeholder);
                    for (const option of options) {
                        const optionNode = document.createElement('option');
                        optionNode.value = String(option);
                        optionNode.textContent = blueprintOptionLabel(field, option);
                        control.appendChild(optionNode);
                    }
                    }
                } else if (schema.type === 'object' || schema.type === 'array' || Array.isArray(schema.type)) {
                    control = document.createElement('textarea');
                    control.placeholder = schema.type === 'array' ? '[...]' : '{...}';
                } else {
                    control = document.createElement('input');
                    control.type = schema.type === 'number' || schema.type === 'integer' ? 'number' : 'text';
                }
                if (!control.dataset.customChoice && field.presentation !== 'asset_picker' && field.presentation !== 'file_reference' && field.presentation !== 'derived_readonly' && schema.type !== 'object') {
                    control.value = field.presentation === 'text_list'
                        ? presentedLines(displayValue)
                        : displayValue === undefined
                            ? ''
                            : (typeof displayValue === 'object' ? JSON.stringify(displayValue) : String(displayValue));
                    control.onchange = () => updateBlueprintField(field, control.value);
                }
                wrapper.appendChild(control);
                const source = document.createElement('div');
                source.className = 'blueprint-field-source';
                const dependencyLabels = (state.missing_option_dependencies || []).map(path =>
                    blueprint.fields?.find(item => item.path === path)?.label || path
                );
                source.textContent = state.options_state === 'awaiting_dependency'
                    ? `请先完成：${dependencyLabels.join('、') || '上游选择'}`
                    : field.presentation === 'derived_readonly'
                    ? '已根据当前入口自动匹配'
                    : field.source === 'lookup' || field.control === 'lookup'
                        ? '需要从指定账户中选择'
                        : (field.presentation === 'asset_picker' || field.presentation === 'file_reference')
                            ? '本地素材草稿，不会自动上传'
                            : schema.type === 'object' ? '按字段填写，系统会按 Tool Schema 组装'
                            : field.presentation === 'text_list' ? '每行填写一条' : '可直接填写';
                wrapper.appendChild(source);
                sectionFields.appendChild(wrapper);
                }
            });
            const readiness = document.getElementById('blueprintReadiness');
            if (readiness) {
                const missing = evaluation?.missing_fields || [];
                const invalid = evaluation?.invalid_fields || [];
                readiness.textContent = evaluation
                    ? (invalid.length ? `有 ${invalid.length} 项不适用于当前选择`
                        : missing.length ? `还需要填写 ${missing.length} 项` : '参数草稿已满足蓝图必填条件')
                    : '等待填写参数';
            }
        }

        async function updateBlueprintField(field, rawValue) {
            const prior = { ...blueprintState.values };
            const schema = blueprintToolFieldSchema(field.tool_ref).schema || {};
            if (rawValue === '') {
                delete blueprintState.values[field.path];
            } else {
                blueprintState.values[field.path] = typeof rawValue === 'string'
                    ? parsePresentedValue(field, rawValue, schema)
                    : rawValue;
            }
            blueprintState.previousValues = prior;
            await evaluateBlueprintDraft(field.path);
        }

        async function evaluateBlueprintDraft(changedPath, allowReset = true) {
            const blueprint = blueprintState.selected;
            if (!blueprint) return;
            try {
                const evaluation = await apiFetch(`/creation-blueprints/${encodeURIComponent(blueprint.id)}/evaluate`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        values: blueprintState.values,
                        previous_values: blueprintState.previousValues,
                        changed_fields: changedPath ? [changedPath] : [],
                        version: blueprint.version,
                    }),
                });
                blueprintState.evaluation = evaluation;
                if (allowReset && evaluation.reset_fields?.length) {
                    for (const path of evaluation.reset_fields) {
                        delete blueprintState.values[path];
                        const resetField = blueprint.fields?.find(item => item.path === path);
                        const resetKey = resetField ? blueprintToolFieldSchema(resetField.tool_ref).fieldPath : path;
                        delete blueprintState.selectionTokens[resetKey];
                        delete blueprintState.selectionTokenTools[resetKey];
                    }
                    showBlueprintNotice(`已根据字段变化清理 ${evaluation.reset_fields.length} 个不再适用的下游参数。`);
                    await evaluateBlueprintDraft(changedPath, false);
                    return;
                }
                renderBlueprintFlowbar(blueprint, evaluation);
                renderBlueprintFields(evaluation);
                renderBlueprintFieldNav(blueprint, evaluation);
                renderBlueprintSummary(blueprint, evaluation);
            } catch (error) {
                showBlueprintNotice(error.message || '参数校验失败。');
            }
        }

        function showBlueprintNotice(message) {
            const notice = document.getElementById('blueprintNotice');
            if (!notice) return;
            notice.textContent = message || '';
            notice.classList.toggle('active', Boolean(message));
        }

        function resetBlueprintDraft() {
            blueprintState.values = blueprintDefaultValues(blueprintState.selected);
            blueprintState.previousValues = {};
            blueprintState.evaluation = null;
            blueprintState.localFiles = {};
            blueprintState.selectionTokens = {};
            blueprintState.selectionTokenTools = {};
            blueprintState.lookupOptions = {};
            showBlueprintNotice('');
            renderBlueprintEditor();
        }

        function useBlueprintInChat() {
            const blueprint = blueprintState.selected;
            if (!blueprint) return;
            if (!blueprintState.accountId.trim()) {
                showBlueprintNotice('请先填写本次要操作的广告账户 ID，平台不会自动选择账户。');
                document.getElementById('blueprintAccountInput')?.focus();
                return;
            }
            pendingBlueprintRequest = {
                account_id: blueprintState.accountId.trim(),
                platform_params: blueprintDraftPlatformParams(blueprint),
                creation_blueprint_id: blueprint.id,
                creation_blueprint_version: blueprint.version,
            };
            setInput(`请按“${blueprint.title || blueprint.id}”继续创建广告。参数草稿已带入，请先检查并确认后提交。`);
            closeBlueprintManager();
        }
