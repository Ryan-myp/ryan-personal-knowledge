        function creationCardValueText(value) {
            if (value === undefined || value === null) return '';
            return typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value);
        }

        function creationCardDisplayValue(field) {
            if (field.control === 'text_list') return presentedLines(field.value);
            return creationCardValueText(field.value);
        }

        function parseCreationCardValue(field, rawValue) {
            if (field.control === 'text_list') {
                const lines = String(rawValue || '').split(/\r?\n/).map(item => item.trim()).filter(Boolean);
                return field.value_shape === 'object_text' ? lines.map(text => ({ text })) : lines;
            }
            if (field.control === 'json' || field.control === 'advanced_json') {
                if (!String(rawValue || '').trim()) {
                    delete field.local_error;
                    return undefined;
                }
                try {
                    const value = JSON.parse(rawValue);
                    const expectedShape = String(field.json_shape || '').toLowerCase();
                    const isObject = value !== null && typeof value === 'object' && !Array.isArray(value);
                    const isArray = Array.isArray(value);
                    if (expectedShape === 'object' && !isObject) {
                        field.local_error = '这里需要填写 JSON 对象，例如 {"key":"value"}。';
                        return rawValue;
                    }
                    if (expectedShape === 'array' && !isArray) {
                        field.local_error = '这里需要填写 JSON 数组，例如 [{"key":"value"}]。';
                        return rawValue;
                    }
                    if (expectedShape === 'object_or_array' && !isObject && !isArray) {
                        field.local_error = '这里需要填写 JSON 对象或数组。';
                        return rawValue;
                    }
                    delete field.local_error;
                    return value;
                } catch (_) {
                    field.local_error = '格式不正确，请填写有效的 JSON 对象或数组。';
                    return rawValue;
                }
            }
            if (field.control === 'number') return rawValue === '' ? undefined : Number(rawValue);
            return rawValue === '' ? undefined : rawValue;
        }

        function setCreationNestedValue(target, path, value) {
            const parts = String(path || '').split('.').filter(Boolean);
            if (!parts.length) return;
            let current = target;
            parts.forEach((part, index) => {
                if (index === parts.length - 1) current[part] = value;
                else current = current[part] && typeof current[part] === 'object' ? current[part] : (current[part] = {});
            });
        }

        // Lookup dependencies are declared by the provider schema.  The
        // picker receives the current form values through this generic
        // projection; it does not know Meta/Google/TikTok field names.
        function lookupContextFromFields(fields) {
            const context = {};
            (fields || []).forEach(field => {
                if (!field || field.value === undefined || field.value === null || field.value === '') return;
                const path = field.provider_field || field.path;
                if (path) setCreationNestedValue(context, path, field.value);
                if (field.path) context[field.path] = field.value;
                const leaf = String(path || '').split('.').pop();
                if (leaf && context[leaf] === undefined) context[leaf] = field.value;
                if (field.value && typeof field.value === 'object' && !Array.isArray(field.value)) {
                    Object.entries(field.value).forEach(([key, value]) => {
                        if (value !== undefined && value !== null && value !== '') context[key] = value;
                    });
                }
            });
            return context;
        }

        function blueprintLookupContext() {
            const context = { ...(blueprintState.values || {}) };
            Object.entries(context).forEach(([path, value]) => {
                const leaf = String(path).split('.').pop();
                if (leaf && context[leaf] === undefined) context[leaf] = value;
                if (value && typeof value === 'object' && !Array.isArray(value)) {
                    Object.entries(value).forEach(([key, child]) => {
                        if (child !== undefined && child !== null && child !== '') context[key] = child;
                    });
                }
            });
            return context;
        }

        function creationCardParams(card) {
            const values = {};
            const scopedSelectionTokens = {};
            (card.fields || []).forEach(field => {
                const value = creationFieldValue(field);
                if (field.visible === false || value === undefined || value === null || value === '') return;
                setCreationNestedValue(values, field.provider_field || field.path, value);
                // Keep a tool-scoped copy for repeated fields such as name or
                // app_id. The top-level copy remains available to the
                // provider-neutral activation predicates; the authoritative
                // Tool builder uses the scoped value for its own schema.
                if (field.tool) {
                    values[field.tool] = values[field.tool] || {};
                    setCreationNestedValue(values[field.tool], field.provider_field || field.path, value);
                }
            });
            Object.entries(card.selection_tokens || {}).forEach(([fieldName, token]) => {
                const toolName = card.selection_token_tools?.[fieldName];
                if (!toolName || !token) return;
                scopedSelectionTokens[toolName] = scopedSelectionTokens[toolName] || {};
                scopedSelectionTokens[toolName][fieldName] = token;
            });
            Object.entries(scopedSelectionTokens).forEach(([toolName, tokens]) => {
                values[toolName] = values[toolName] || {};
                values[toolName].selection_tokens = tokens;
            });
            return { [card.provider]: values };
        }

        function creationCardDraftValues(card) {
            const values = {};
            (card.fields || []).forEach(field => {
                const value = creationFieldValue(field);
                if (value !== undefined && value !== null && value !== '') values[field.path] = value;
            });
            return values;
        }

        async function evaluateCreationCard(card, changedPath) {
            if (!card.blueprint_id) return;
            const localInvalidPaths = new Set(
                (card.fields || []).filter(field => field.local_error).map(field => field.path)
            );
            const revision = (creationCardEvaluationRevisions.get(card.id) || 0) + 1;
            creationCardEvaluationRevisions.set(card.id, revision);
            card.validation_pending = true;
            delete card.validation_error;
            const pendingWrapper = document.querySelector(`.creation-card[data-card-id="${CSS.escape(card.id)}"]`);
            if (pendingWrapper) updateCreationCardIndicators(pendingWrapper, card);
            try {
                const response = await authenticatedFetch(`/creation-blueprints/${encodeURIComponent(card.blueprint_id)}/evaluate`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ values: creationCardDraftValues(card), version: card.blueprint_version, changed_fields: changedPath ? [changedPath] : [] })
                });
                if (!response.ok) throw new Error(`参数检查失败（${response.status}）`);
                const evaluation = await response.json();
                // Typing can queue more than one request when the local
                // service is busy. Never let an older response roll a draft
                // back over a newer value.
                if (creationCardEvaluationRevisions.get(card.id) !== revision) return;
                const reset = new Set(evaluation.reset_fields || []);
                const previousFields = new Map((card.fields || []).map(field => [field.path, field]));
                const structuralChange = reset.size > 0 || (evaluation.fields || []).some(next => {
                    const previous = previousFields.get(next.path);
                    return !previous
                        || previous.visible !== next.visible
                        || previous.required !== next.required
                        || JSON.stringify(previous.options || []) !== JSON.stringify(next.options || []);
                });
                (card.fields || []).forEach(field => {
                    if (reset.has(field.path)) {
                        field.value = undefined;
                        const resetKey = field.provider_field || field.path;
                        delete card.selection_tokens?.[resetKey];
                        delete card.selection_token_tools?.[resetKey];
                    }
                    const state = (evaluation.fields || []).find(item => item.path === field.path);
                    if (state) {
                        field.visible = state.visible;
                        field.required = state.required;
                        field.state = state.state;
                    }
                    if (field.local_error) field.state = 'invalid';
                });
                card.missing_fields = evaluation.missing_fields || [];
                card.invalid_fields = [...new Set([
                    ...(evaluation.invalid_fields || []), ...localInvalidPaths,
                ])];
                card.ready = Boolean(evaluation.ready) && localInvalidPaths.size === 0;
                card.validation_pending = false;
                delete card.validation_error;
                const current = document.querySelector(`.creation-card[data-card-id="${CSS.escape(card.id)}"]`);
                if (current) {
                    if (!structuralChange) {
                        updateCreationCardIndicators(current, card);
                        return;
                    }
                    // Cascade evaluation updates field visibility and
                    // requirements, but replacing the whole card must not
                    // make a person lose focus while typing. Restore the
                    // active control and its caret after the structural
                    // update completes.
                    const active = document.activeElement;
                    const isInsideCard = Boolean(active && current.contains(active));
                    const focusPath = isInsideCard
                        ? (active.dataset?.path || (active.closest('.creation-card-account') ? '__account__' : ''))
                        : '';
                    const selectionStart = isInsideCard && typeof active.selectionStart === 'number' ? active.selectionStart : null;
                    const selectionEnd = isInsideCard && typeof active.selectionEnd === 'number' ? active.selectionEnd : null;
                    const replacement = renderCreationCard(card);
                    current.replaceWith(replacement);
                    const target = focusPath === '__account__'
                        ? replacement.querySelector('.creation-card-account input')
                        : focusPath ? replacement.querySelector(`[data-path="${CSS.escape(focusPath)}"]`) : null;
                    if (target && !target.disabled) {
                        target.focus({ preventScroll: true });
                        if (selectionStart !== null && typeof target.setSelectionRange === 'function') {
                            target.setSelectionRange(selectionStart, selectionEnd ?? selectionStart);
                        }
                    }
                }
            } catch (error) {
                // A transient UI evaluation error does not alter the draft;
                // the next chat submission still passes through the server
                // Tool schema and authoritative cascade validation.
                console.debug('creation card evaluation failed', error);
                if (creationCardEvaluationRevisions.get(card.id) === revision) {
                    card.validation_pending = false;
                    card.ready = false;
                    card.validation_error = '参数检查暂时失败，请点击“检查参数”重试。';
                    const current = document.querySelector(`.creation-card[data-card-id="${CSS.escape(card.id)}"]`);
                    if (current) updateCreationCardIndicators(current, card);
                }
            }
        }

        function scheduleCreationCardEvaluation(card, path) {
            const prior = creationCardEvaluationTimers.get(card.id);
            if (prior) window.clearTimeout(prior);
            card.validation_pending = true;
            delete card.validation_error;
            const current = document.querySelector(`.creation-card[data-card-id="${CSS.escape(card.id)}"]`);
            if (current) updateCreationCardIndicators(current, card);
            const timer = window.setTimeout(() => {
                creationCardEvaluationTimers.delete(card.id);
                evaluateCreationCard(card, path);
            }, 220);
            creationCardEvaluationTimers.set(card.id, timer);
        }

        function creationCardValueEmpty(value) {
            return value === undefined || value === null || value === ''
                || (Array.isArray(value) && value.length === 0)
                || (value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length === 0);
        }

        function creationCardPendingLabels(card) {
            const invalidPaths = new Set(card.invalid_fields || []);
            const pending = [];
            if (!String(card.account_id || '').trim()) pending.push('广告账户 ID');
            (card.fields || []).forEach(field => {
                if (field.visible === false || !creationFieldNeedsUserInput(field)) return;
                const label = field.label || field.path || '参数';
                if (invalidPaths.has(field.path) || field.state === 'invalid') return;
                if (creationCardValueEmpty(creationFieldValue(field)) && !pending.includes(label)) pending.push(label);
            });
            return pending;
        }

        function creationCardInvalidLabels(card) {
            const invalidPaths = new Set(card.invalid_fields || []);
            return (card.fields || []).filter(field => field.visible !== false && (invalidPaths.has(field.path) || field.state === 'invalid' || field.local_error)).map(field => field.label || field.path || '参数').filter((label, index, labels) => labels.indexOf(label) === index);
        }

        function creationProviderLabel(provider) {
            return ({ 'google-ads': 'Google Ads', google: 'Google Ads', meta: 'Meta', tiktok: 'TikTok', dv360: 'DV360' })[String(provider || '').toLowerCase()] || String(provider || '广告平台');
        }

        function blueprintSupportLabel(support) {
            const level = String(support?.level || '').trim();
            return support?.label || ({
                supported_dry_run: '支持草稿校验',
                partial_dry_run: '部分支持草稿',
                declared_only: '暂不支持向导创建',
                contract_only: '已接入字段合同',
            }[level] || '支持状态待确认');
        }

        function blueprintSupportClass(support) {
            const level = String(support?.level || 'contract_only');
            return level === 'supported_dry_run' ? 'supported'
                : level === 'partial_dry_run' ? 'partial'
                    : level === 'declared_only' ? 'declared' : 'contract';
        }

        function creationAccountLabel(provider) {
            return ({ 'google-ads': 'Google Ads 客户 ID', google: 'Google Ads 客户 ID', tiktok: 'TikTok 广告主 ID', meta: 'Meta 广告账户 ID', dv360: 'DV360 广告客户 ID' })[String(provider || '').toLowerCase()] || '广告账户 ID';
        }

        function creationCardStatus(card) {
            const invalid = creationCardInvalidLabels(card);
            const pending = creationCardPendingLabels(card);
            if (card.validation_pending) return '正在检查刚刚修改的参数，请稍候…';
            if (card.validation_error) return card.validation_error;
            if (invalid.length) return `有 ${invalid.length} 项需要调整：${invalid.slice(0, 3).join('、')}${invalid.length > 3 ? '等' : ''}`;
            if (pending.length) return `还需要补充 ${pending.length} 项：${pending.slice(0, 3).join('、')}${pending.length > 3 ? '等' : ''}`;
            return card.ready ? '必填参数已齐全，可以先查看预览' : '参数草稿已保存，可以继续补充';
        }

        function creationCardStatusKind(card) {
            if (!String(card.account_id || '').trim()) return 'account';
            if (card.validation_pending) return 'checking';
            if (card.validation_error) return 'error';
            if (creationCardInvalidLabels(card).length) return 'invalid';
            if ((card.missing_fields || []).length) return 'waiting';
            return card.ready ? 'ready' : 'draft';
        }

        function creationCardStatusLabel(card) {
            const kind = creationCardStatusKind(card);
            const pending = creationCardPendingLabels(card).length;
            return kind === 'ready' ? '可提交' : kind === 'checking' ? '检查中…' : kind === 'error' ? '检查失败' : kind === 'invalid' ? `需调整 ${Math.max(1, creationCardInvalidLabels(card).length)} 项` : pending ? `待补充 ${pending} 项` : '待检查';
        }

        function creationCardProgress(card) {
            const requiredFields = (card.fields || []).filter(field => field.visible !== false && creationFieldNeedsUserInput(field));
            const completedFields = requiredFields.filter(field => !creationCardValueEmpty(creationFieldValue(field)) && !field.local_error && field.state !== 'invalid' && !(card.invalid_fields || []).includes(field.path)).length;
            const accountCompleted = String(card.account_id || '').trim() ? 1 : 0;
            const total = requiredFields.length + 1;
            const completed = completedFields + accountCompleted;
            return { completed, total, percent: total ? Math.round(completed / total * 100) : 0 };
        }

        function creationCardCanSubmit(card) {
            return Boolean(String(card.account_id || '').trim() && !card.validation_pending && !card.validation_error && card.ready && !(card.missing_fields || []).length && !(card.invalid_fields || []).length && !(card.fields || []).some(field => field.local_error));
        }

        function updateCreationCardIndicators(wrapper, card) {
            // Keep field-level feedback synchronous with the local draft. In
            // particular, malformed advanced JSON must be visible before the
            // debounced cascade request returns.
            updateCreationCardFieldStates(wrapper, card);
            const status = wrapper.querySelector('.creation-card-status');
            if (status) status.textContent = creationCardStatus(card);
            const nextValue = wrapper.querySelector('.creation-card-next-value');
            if (nextValue) nextValue.textContent = card.type === 'ad_creation_selector' ? '先选择创建类型，系统会展开对应参数。' : creationCardStatus(card);
            const badge = wrapper.querySelector('.creation-card-state');
            if (badge) {
                badge.className = `creation-card-state ${creationCardStatusKind(card)}`;
                badge.textContent = creationCardStatusLabel(card);
            }
            const progress = creationCardProgress(card);
            const progressValue = wrapper.querySelector('.creation-card-progress-value');
            if (progressValue) progressValue.textContent = `${progress.completed} / ${progress.total} · ${progress.percent}%`;
            const progressBar = wrapper.querySelector('.creation-card-progress-bar');
            if (progressBar) {
                progressBar.style.width = `${progress.percent}%`;
                progressBar.setAttribute('aria-valuenow', String(progress.percent));
            }
            wrapper.querySelectorAll('.creation-card-section').forEach(section => {
                const group = creationFieldGroups(card.fields || []).find(item => item.id === section.dataset.step);
                if (!group) return;
                const groupProgress = fieldGroupProgress(group.fields);
                const count = section.querySelector('.creation-card-section-count');
                if (count) {
                    count.classList.toggle('has-missing', Boolean(groupProgress.missing));
                    count.textContent = groupProgress.missing ? `待填 ${groupProgress.missing}` : `${groupProgress.total} 项`;
                }
            });
            wrapper.querySelectorAll('.creation-card-step').forEach(step => {
                const group = creationFieldGroups(card.fields || []).find(item => item.id === step.dataset.step);
                const groupProgress = group ? fieldGroupProgress(group.fields) : { missing: 0 };
                step.classList.toggle('has-missing', Boolean(groupProgress.missing));
                const copy = step.querySelector('small');
                if (copy) copy.textContent = groupProgress.missing ? `待填 ${groupProgress.missing}` : '已就绪';
            });
            const submitButton = wrapper.querySelector('[data-creation-action="submit_create"]');
            if (submitButton) submitButton.disabled = !creationCardCanSubmit(card);
            const focusButton = wrapper.querySelector('.creation-card-focus-action');
            if (focusButton) {
                const hasIssue = !String(card.account_id || '').trim() || creationCardPendingLabels(card).length || creationCardInvalidLabels(card).length;
                focusButton.hidden = !hasIssue;
                focusButton.textContent = creationCardInvalidLabels(card).length ? '查看问题' : '定位待填项';
            }
            renderCreationCardFieldNav(card, wrapper);
            renderCreationCardSummary(card, wrapper);
            renderCreationCardAutomation(card, wrapper);
        }

        function focusCreationCardIssue(card, wrapper = null) {
            const root = wrapper || document.querySelector(`.creation-card[data-card-id="${CSS.escape(card.id)}"]`);
            if (!root) return;
            if (!String(card.account_id || '').trim()) {
                const account = root.querySelector('.creation-card-account input');
                account?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                account?.focus({ preventScroll: true });
                return;
            }
            const issue = root.querySelector('.creation-card-field.invalid:not(.hidden), .creation-card-field.missing:not(.hidden)');
            if (!issue) return;
            scrollCreationTarget(issue);
            issue.querySelector('input:not([disabled]), select:not([disabled]), textarea:not([disabled]), button')?.focus({ preventScroll: true });
        }

        function creationCardFieldState(field) {
            const invalid = field.local_error || field.state === 'invalid';
            const value = creationFieldValue(field);
            const empty = creationCardValueEmpty(value);
            return {
                visible: field.visible !== false,
                required: creationFieldNeedsUserInput(field),
                value,
                status: invalid ? 'invalid' : creationFieldNeedsUserInput(field) && empty ? 'missing' : empty ? 'empty' : 'complete',
            };
        }

        function creationCardScrollTo(wrapper, target, activeNode = null) {
            if (!target) return;
            const section = target.closest('.blueprint-field-group, .creation-card-section');
            if (section) setCreationSectionExpanded(section, true);
            scrollCreationTarget(target);
            target.querySelector('input:not([disabled]), select:not([disabled]), textarea:not([disabled]), button:not([disabled])')?.focus({ preventScroll: true });
            wrapper.querySelectorAll('.creation-card-nav-item.active, .creation-card-nav-group.active').forEach(node => node.classList.remove('active'));
            activeNode?.classList.add('active');
        }

        function renderCreationCardFieldNav(card, wrapper) {
            const container = wrapper?.querySelector('.creation-card-field-nav');
            if (!container) return;
            container.replaceChildren();
            const header = document.createElement('div');
            header.className = 'creation-card-field-nav-header';
            header.innerHTML = '<span>填写目录</span><small>点击字段快速定位</small>';
            container.appendChild(header);
            creationDirectoryLevelGroups(card.fields || []).forEach(({ hierarchy, fields: levelFields }) => {
                const fields = levelFields.filter(field => field.visible !== false && (!card.focus_mode || !field.advanced));
                if (!fields.length) return;
                const progress = fieldGroupProgress(fields);
                const groupButton = document.createElement('button');
                groupButton.type = 'button';
                groupButton.className = `creation-card-nav-group${progress.missing ? ' missing' : ' complete'}`;
                const marker = document.createElement('span');
                marker.className = 'creation-card-nav-status';
                marker.textContent = progress.missing ? '!' : '✓';
                const copy = document.createElement('span');
                copy.className = 'creation-card-nav-group-copy';
                copy.innerHTML = `<strong>${escapeHtml(hierarchy)}</strong><small>${progress.missing ? `待填 ${progress.missing} · 共 ${progress.total} 项` : `已就绪 · 共 ${progress.total} 项`}</small>`;
                const fieldList = document.createElement('div');
                fieldList.className = 'creation-card-nav-fields';
                const collapsedKey = `card:${card.id}:level:${hierarchy}`;
                const collapsed = creationDirectoryCollapseState.get(collapsedKey) === true;
                if (collapsed) fieldList.classList.add('is-collapsed');
                const groupMarker = document.createElement('span');
                groupMarker.className = 'creation-card-nav-group-marker';
                groupMarker.textContent = collapsed ? '›' : '⌄';
                groupButton.append(marker, copy, groupMarker);
                groupButton.setAttribute('aria-expanded', String(!collapsed));
                groupButton.addEventListener('click', () => {
                    const nextCollapsed = !fieldList.classList.contains('is-collapsed');
                    fieldList.classList.toggle('is-collapsed', nextCollapsed);
                    creationDirectoryCollapseState.set(collapsedKey, nextCollapsed);
                    groupButton.setAttribute('aria-expanded', String(!nextCollapsed));
                    groupMarker.textContent = nextCollapsed ? '›' : '⌄';
                });
                container.appendChild(groupButton);
                fields.forEach(field => {
                    const state = creationCardFieldState(field);
                    const button = document.createElement('button');
                    button.type = 'button';
                    button.className = `creation-card-nav-item${state.status === 'missing' ? ' missing' : ''}${state.status === 'invalid' ? ' invalid' : ''}${state.status === 'complete' ? ' complete' : ''}`;
                    const status = document.createElement('span');
                    status.className = 'creation-card-nav-field-status';
                    status.textContent = state.status === 'invalid' ? '!' : state.status === 'missing' ? '•' : state.status === 'complete' ? '✓' : '·';
                    const itemCopy = document.createElement('span');
                    itemCopy.className = 'creation-card-nav-item-copy';
                    itemCopy.innerHTML = `<span>${escapeHtml(field.label || field.path)}</span><small>${escapeHtml(creationFieldDisplayValue(field))}</small>`;
                    button.append(status, itemCopy);
                    button.addEventListener('click', () => creationCardScrollTo(wrapper, wrapper.querySelector(`.creation-card-field[data-field-path="${CSS.escape(field.path)}"]`), button));
                    fieldList.appendChild(button);
                });
                container.appendChild(fieldList);
            });
            if (!container.querySelector('.creation-card-nav-group')) {
                const empty = document.createElement('div');
                empty.className = 'creation-card-nav-empty';
                empty.textContent = '选择创建类型后显示字段目录。';
                container.appendChild(empty);
            }
        }

        function renderCreationCardSummary(card, wrapper) {
            const container = wrapper?.querySelector('.creation-card-summary');
            if (!container) return;
            container.replaceChildren();
            const progress = creationCardProgress(card);
            const heading = document.createElement('div');
            heading.className = 'creation-card-summary-heading';
            heading.innerHTML = '<span>实时摘要</span><small>填写时始终可见</small>';
            const progressValue = document.createElement('span');
            progressValue.className = `creation-card-summary-progress${progress.percent >= 100 ? ' ready' : ''}`;
            progressValue.textContent = `${progress.completed}/${progress.total} 项已填`;
            heading.appendChild(progressValue);
            container.appendChild(heading);
            const items = document.createElement('div');
            items.className = 'creation-card-summary-items';
            const account = document.createElement('button');
            account.type = 'button';
            account.className = `creation-card-summary-item${card.account_id ? ' filled' : ' pending'}`;
            account.innerHTML = `<span>广告账户</span><strong>${escapeHtml(card.account_id || '未填写')}</strong>`;
            account.addEventListener('click', () => wrapper.querySelector('.creation-card-account input')?.focus());
            items.appendChild(account);
            const filled = (card.fields || []).filter(field => field.visible !== false && !creationCardValueEmpty(creationFieldValue(field)) && creationFieldNeedsUserInput(field));
            filled.slice(0, 5).forEach(field => {
                const item = document.createElement('button');
                item.type = 'button';
                item.className = 'creation-card-summary-item filled';
                item.innerHTML = `<span>${escapeHtml(field.label || field.path)}</span><strong>${escapeHtml(creationFieldDisplayValue(field))}</strong>`;
                item.addEventListener('click', () => creationCardScrollTo(wrapper, wrapper.querySelector(`.creation-card-field[data-field-path="${CSS.escape(field.path)}"]`)));
                items.appendChild(item);
            });
            const remaining = filled.length - Math.min(filled.length, 5);
            if (remaining > 0) {
                const more = document.createElement('span');
                more.className = 'creation-card-summary-more';
                more.textContent = `还有 ${remaining} 项已填写`;
                items.appendChild(more);
            }
            container.appendChild(items);
        }

        function renderCreationCardAutomation(card, wrapper) {
            const container = wrapper?.querySelector('.creation-card-automation');
            if (!container) return;
            const count = Number(card.auto_filled_count || 0);
            const autoText = count ? `系统已按平台规则填好 ${count} 项` : '系统会按平台规则生成安全默认值';
            const missing = creationCardPendingLabels(card).filter(label => label !== '广告账户 ID').length;
            container.querySelector('.creation-card-automation-copy strong').textContent = autoText;
            container.querySelector('.creation-card-automation-copy small').textContent = missing ? `还需要你确认 ${missing} 项；账户、素材和链接仍需使用真实资源` : '你可以直接修改任何默认值，最终会按当前内容提交';
            const toggle = container.querySelector('.creation-card-automation-toggle');
            if (toggle) {
                toggle.textContent = card.focus_mode ? '显示全部参数' : '只看需要确认';
                toggle.setAttribute('aria-pressed', String(Boolean(card.focus_mode)));
            }
        }

        function creationReviewRows(card) {
            const fields = (card.fields || []).filter(field => {
                const value = creationFieldValue(field);
                return field.visible !== false && value !== undefined && value !== null && value !== '';
            }).slice(0, 80);
            return creationDirectoryHierarchyGroups(fields).map(([hierarchy, hierarchyFields]) => {
                const rows = hierarchyFields.map(field => {
                    const fieldValue = creationFieldValue(field);
                    const rawValue = field.control === 'checkbox' ? creationFieldDisplayValue(field, fieldValue)
                        : field.control === 'text_list' ? presentedLines(fieldValue)
                        : field.control === 'asset_picker' ? (Array.isArray(fieldValue) ? fieldValue.map(item => item?.local_file || item?.name || item?.asset || '已选素材').join('、') : '')
                        : field.control === 'object_editor' ? structuredObjectValueText(fieldValue)
                        : creationCardValueText(fieldValue);
                    const value = String(rawValue || '已填写');
                    return `<div class="creation-review-row"><span>${escapeHtml(field.label || field.path)}</span><strong title="${escapeHtml(value)}">${escapeHtml(value.length > 180 ? `${value.slice(0, 180)}…` : value)}</strong></div>`;
                }).join('');
                return `<section class="creation-review-group"><div class="creation-review-group-head"><strong>${escapeHtml(hierarchy)}</strong><small>${hierarchyFields.length} 项</small></div>${rows}</section>`;
            }).join('');
        }

        function showCreationPreview(card) {
            const existing = document.querySelector(`.creation-card-review[data-card-review="${CSS.escape(card.id)}"]`);
            if (existing) { existing.remove(); return; }
            const review = document.createElement('div');
            review.className = 'creation-card-review';
            review.dataset.cardReview = card.id;
            const modeLabel = workspaceMode.mode === 'live' ? 'LIVE · 确认后提交' : 'DRY-RUN · 不修改线上';
            review.innerHTML = `<div class="creation-review-head"><div><strong>参数预览</strong><small>按广告层级汇总已填写内容</small></div><span>${modeLabel}</span></div><div class="creation-review-account"><span>广告账户</span><strong>${escapeHtml(card.account_id || '未填写')}</strong></div><div class="creation-review-groups">${creationReviewRows(card) || '<div class="creation-review-empty">暂无已填写参数</div>'}</div><div class="creation-review-note">这里只是预览，不会产生线上变化；确认后才会继续创建。</div>`;
            const target = document.querySelector(`.creation-card[data-card-id="${CSS.escape(card.id)}"] .creation-card-footer`);
            if (target) target.parentElement.insertBefore(review, target);
        }

        function showCreationReview(card) {
            if (!String(card.account_id || '').trim()) {
                const input = document.querySelector(`.creation-card[data-card-id="${CSS.escape(card.id)}"] .creation-card-account input`);
                input?.focus();
                addMessage('请先填写本次要操作的广告账户 ID，再提交创建。', 'agent', null, true);
                return;
            }
            if (!card.ready || card.validation_pending || card.validation_error || card.missing_fields?.length || card.invalid_fields?.length || (card.fields || []).some(field => field.local_error)) {
                addMessage('还有必填参数或联动参数需要补充，请先完成卡片中的标记项。', 'agent', null, true);
                return;
            }
            pendingCreationReview = card;
            const oldCard = document.getElementById('confirmCard');
            if (oldCard) oldCard.remove();
            const review = document.createElement('div');
            review.id = 'confirmCard';
            review.className = 'confirm-card';
            review.innerHTML = `<div class="confirm-card-header"><span class="confirm-icon">✓</span><span class="confirm-title">请确认创建计划</span></div><div class="confirm-card-body"><p>即将为账户 <strong>${escapeHtml(card.account_id)}</strong> 提交“${escapeHtml(card.title || '广告')}”的创建计划。</p><p>请确认账户、预算、定向和素材均无误。${workspaceMode.mode === 'live' ? '确认后将提交到广告平台。' : '当前为预览状态，不会修改线上账户。'}</p></div><div class="confirm-card-footer"><button class="confirm-btn cancel" onclick="cancelCreationReview()">返回修改</button><button class="confirm-btn confirm" onclick="confirmCreationSubmission()">确认创建</button></div>`;
            document.getElementById('confirmCardContainer').appendChild(review);
            review.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }

        function cancelCreationReview() {
            pendingCreationReview = null;
            document.getElementById('confirmCard')?.remove();
        }

        function confirmCreationSubmission() {
            const card = pendingCreationReview;
            pendingCreationReview = null;
            document.getElementById('confirmCard')?.remove();
            if (!card) return;
            if (!creationCardCanSubmit(card)) {
                addMessage('参数已发生变化，请回到卡片完成检查后再确认创建。', 'agent', null, true);
                return;
            }
            submitCreationCard(card);
        }

        async function submitCreationCard(card) {
            if (!creationCardCanSubmit(card)) {
                addMessage('当前参数还未通过检查，请先完成卡片中的必填项和格式校验。', 'agent', null, true);
                return;
            }
            const userInput = `提交“${card.title || card.provider + '广告'}”创建计划`;
            const requestParams = {
                user_input: userInput,
                user_id: 'web_user',
                session_id: sessionId,
                account_id: String(card.account_id || '').trim(),
                platform_params: creationCardParams(card),
                creation_blueprint_id: card.blueprint_id || null,
                creation_blueprint_version: card.blueprint_version || null,
            };
            addMessage('确认创建', 'user');
            addLoading();
            startExecutionTrace(userInput);
            try {
                const data = await streamChatRequest(requestParams);
                removeLoading();
                renderStreamResult(data, requestParams);
                await refreshConversationHistory({ silent: true });
            } catch (error) {
                removeLoading();
                markTraceFailed(error.message);
                addMessage('提交失败：' + error.message, 'agent', null, true);
            }
        }

        function updateCreationCardFieldStates(wrapper, card) {
            (card.fields || []).forEach(field => {
                const item = wrapper.querySelector(`[data-field-path="${CSS.escape(field.path)}"]`);
                if (!item) return;
                const state = creationCardFieldState(field);
                const invalid = state.status === 'invalid' || (card.invalid_fields || []).includes(field.path);
                item.classList.toggle('missing', state.status === 'missing');
                item.classList.toggle('invalid', invalid);
                item.classList.toggle('hidden', !state.visible);
                let error = item.querySelector('.creation-card-field-error');
                if (field.local_error) {
                    if (!error) {
                        error = document.createElement('div');
                        error.className = 'creation-card-field-error';
                        item.appendChild(error);
                    }
                    error.textContent = field.local_error;
                } else if (error) {
                    error.remove();
                }
            });
        }

        function renderCreationCard(card) {
            creationCardState.set(card.id, card);
            const wrapper = document.createElement('section');
            wrapper.className = `creation-card ${creationCardStatusKind(card)}${card.focus_mode ? ' focus-mode' : ''}`;
            wrapper.dataset.cardId = card.id;

            const header = document.createElement('div');
            header.className = 'creation-card-header';
            const headerTop = document.createElement('div');
            headerTop.className = 'creation-card-header-top';
            const kicker = document.createElement('div');
            kicker.className = 'creation-card-kicker';
            kicker.textContent = card.type === 'ad_creation_selector' ? '广告类型选择' : '广告参数草稿';
            const stateBadge = document.createElement('span');
            stateBadge.className = `creation-card-state ${creationCardStatusKind(card)}`;
            stateBadge.textContent = creationCardStatusLabel(card);
            headerTop.append(kicker, stateBadge);
            const title = document.createElement('div');
            title.className = 'creation-card-title';
            title.textContent = card.title || '广告创建参数';
            const meta = document.createElement('div');
            meta.className = 'creation-card-meta';
            const providerLabel = creationProviderLabel(card.provider);
            meta.textContent = card.blueprint_id ? `${providerLabel} · 参数会按平台规则联动，提交前会再次确认` : `${providerLabel} · 先选择创建类型`;
            header.append(headerTop, title, meta);

            const context = document.createElement('div');
            context.className = 'creation-card-context';
            const contextItems = [
                ['投放平台', providerLabel],
                ['创建类型', card.selector?.value ? creationCardValueText(card.selector.value) : (card.blueprint_id ? '已识别' : '待选择')],
            ];
            contextItems.forEach(([label, value]) => {
                const item = document.createElement('span');
                item.className = 'creation-card-context-item';
                const name = document.createElement('span');
                name.textContent = `${label}：`;
                const content = document.createElement('strong');
                content.textContent = value || '待补充';
                item.append(name, content);
                context.appendChild(item);
            });
            header.appendChild(context);
            const next = document.createElement('div');
            next.className = 'creation-card-next';
            const nextTitle = document.createElement('strong');
            nextTitle.textContent = '下一步  ';
            next.appendChild(nextTitle);
            const nextValue = document.createElement('span');
            nextValue.className = 'creation-card-next-value';
            nextValue.textContent = card.type === 'ad_creation_selector' ? '先选择创建类型，系统会展开对应参数。' : creationCardStatus(card);
            next.appendChild(nextValue);
            header.appendChild(next);
            wrapper.appendChild(header);

            const workbench = document.createElement('div');
            workbench.className = 'creation-card-workbench';
            const fieldNav = document.createElement('aside');
            fieldNav.className = 'creation-card-field-nav';
            fieldNav.setAttribute('aria-label', '参数填写目录');
            const main = document.createElement('div');
            main.className = 'creation-card-main';
            workbench.append(fieldNav, main);
            wrapper.appendChild(workbench);
            const contextGrid = document.createElement('div');
            contextGrid.className = 'creation-card-context-grid';
            main.appendChild(contextGrid);

            const account = document.createElement('div');
            account.className = 'creation-card-account';
            const accountLabel = document.createElement('label');
            accountLabel.textContent = `${creationAccountLabel(card.provider)} *`;
            const accountInput = document.createElement('input');
            accountInput.type = 'text';
            accountInput.autocomplete = 'off';
            accountInput.placeholder = `请输入本次要操作的${creationAccountLabel(card.provider)}`;
            accountInput.value = card.account_id || '';
            accountInput.addEventListener('input', () => {
                const previousAccount = String(card.account_id || '').trim();
                card.account_id = accountInput.value.trim();
                if (previousAccount !== card.account_id) {
                    delete card.validation_error;
                    card.ready = false;
                    const selectionsReset = resetAccountScopedSelections(card);
                    if (selectionsReset) {
                        const cursor = typeof accountInput.selectionStart === 'number' ? accountInput.selectionStart : null;
                        const replacement = renderCreationCard(card);
                        wrapper.replaceWith(replacement);
                        const nextInput = replacement.querySelector('.creation-card-account input');
                        if (nextInput) {
                            nextInput.focus({ preventScroll: true });
                            if (cursor !== null && typeof nextInput.setSelectionRange === 'function') nextInput.setSelectionRange(cursor, cursor);
                        }
                        if (card.blueprint_id) scheduleCreationCardEvaluation(card, null);
                        return;
                    }
                    if (card.blueprint_id) scheduleCreationCardEvaluation(card, null);
                }
                updateCreationCardIndicators(wrapper, card);
                refreshLookupAccountState(wrapper);
            });
            const accountHint = document.createElement('small');
            accountHint.textContent = '请填写你确认过的账户；系统不会替你猜测或自动选择。';
            account.append(accountLabel, accountInput, accountHint);
            contextGrid.appendChild(account);

            const progress = creationCardProgress(card);
            const progressBox = document.createElement('div');
            progressBox.className = 'creation-card-progress';
            progressBox.innerHTML = `<div class="creation-card-progress-head"><strong>必填项完成度</strong><span class="creation-card-progress-value">${progress.completed} / ${progress.total} · ${progress.percent}%</span></div><div class="creation-card-progress-track" role="progressbar" aria-label="必填项完成度" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${progress.percent}"><div class="creation-card-progress-bar" style="width:${progress.percent}%"></div></div>`;
            contextGrid.appendChild(progressBox);
            const summary = document.createElement('div');
            summary.className = 'creation-card-summary';
            main.appendChild(summary);

            const automation = document.createElement('div');
            automation.className = 'creation-card-automation';
            const automationCopy = document.createElement('div');
            automationCopy.className = 'creation-card-automation-copy';
            const automationTitle = document.createElement('strong');
            const automationHint = document.createElement('small');
            automationCopy.append(automationTitle, automationHint);
            const automationToggle = document.createElement('button');
            automationToggle.type = 'button';
            automationToggle.className = 'creation-card-automation-toggle';
            automationToggle.setAttribute('aria-pressed', String(Boolean(card.focus_mode)));
            automationToggle.addEventListener('click', () => {
                card.focus_mode = !card.focus_mode;
                wrapper.classList.toggle('focus-mode', card.focus_mode);
                renderCreationCardAutomation(card, wrapper);
                renderCreationCardFieldNav(card, wrapper);
            });
            automation.append(automationCopy, automationToggle);
            main.appendChild(automation);

            const groups = creationFieldGroups(card.fields || []);
            const stepbar = document.createElement('div');
            stepbar.className = 'creation-card-stepbar';
            groups.forEach((group, index) => {
                const groupProgress = fieldGroupProgress(group.fields);
                const step = document.createElement('button');
                step.type = 'button';
                step.className = `creation-card-step${index === 0 ? ' active' : ''}${groupProgress.missing ? ' has-missing' : ''}`;
                step.dataset.step = group.id;
                step.innerHTML = `<span class="creation-card-step-dot">${index + 1}</span><span><strong>${escapeHtml(group.title)}</strong><small>${groupProgress.missing ? `待填 ${groupProgress.missing}` : '已就绪'}</small></span>`;
                step.addEventListener('click', () => {
                    const target = wrapper.querySelector(`.creation-card-section[data-step="${CSS.escape(group.id)}"]`);
                    creationCardScrollTo(wrapper, target);
                    stepbar.querySelectorAll('.creation-card-step').forEach(node => node.classList.toggle('active', node === step));
                });
                stepbar.appendChild(step);
            });
            main.appendChild(stepbar);

            const fields = document.createElement('div');
            fields.className = 'creation-card-fields';
            groups.forEach(group => {
                const section = document.createElement('section');
                section.className = `creation-card-section${group.id === 'advanced' ? ' collapsible' : ''}`;
                if (['advanced', 'other'].includes(group.id)) section.classList.add('is-collapsed');
                section.dataset.step = group.id;
                const sectionHeader = document.createElement('div');
                sectionHeader.className = 'creation-card-section-header';
                const sectionTitle = document.createElement('div');
                sectionTitle.innerHTML = `<span class="creation-card-section-icon">${group.id === 'campaign' ? '◎' : group.id === 'audience' ? '◌' : group.id === 'creative' ? '▧' : group.id === 'measurement' ? '⌁' : '⋯'}</span><span><strong>${escapeHtml(group.title)}</strong><small>${escapeHtml(group.description)}</small></span>`;
                const sectionProgress = fieldGroupProgress(group.fields);
                const sectionCount = document.createElement('span');
                sectionCount.className = `creation-card-section-count${sectionProgress.missing ? ' has-missing' : ''}`;
                sectionCount.textContent = sectionProgress.missing ? `待填 ${sectionProgress.missing}` : `${sectionProgress.total} 项`;
                const sectionToggle = document.createElement('button');
                sectionToggle.type = 'button';
                sectionToggle.className = 'creation-section-toggle';
                sectionToggle.setAttribute('aria-expanded', String(!section.classList.contains('is-collapsed')));
                sectionToggle.textContent = section.classList.contains('is-collapsed') ? '展开' : '收起';
                sectionToggle.addEventListener('click', event => {
                    event.stopPropagation();
                    setCreationSectionExpanded(section, section.classList.contains('is-collapsed'));
                });
                sectionHeader.append(sectionTitle, sectionCount, sectionToggle);
                section.appendChild(sectionHeader);
                const sectionFields = document.createElement('div');
                sectionFields.className = 'creation-card-section-fields';
                section.appendChild(sectionFields);
                fields.appendChild(section);
                group.fields.forEach(field => {
                const fieldState = creationCardFieldState(field);
                const item = document.createElement('div');
                item.dataset.fieldPath = field.path;
                const wideField = field.control === 'lookup' || ['asset_picker', 'file_reference', 'text_list', 'object_editor', 'json', 'advanced_json'].includes(field.control);
                item.className = `creation-card-field${wideField ? ' wide' : ''}${field.advanced ? ' auto-field' : ''}${field.auto_filled ? ' auto-filled' : ''}${fieldState.visible ? '' : ' hidden'}${fieldState.status === 'missing' ? ' missing' : ''}${fieldState.status === 'invalid' ? ' invalid' : ''}`;
                const label = document.createElement('label');
                label.textContent = field.label || field.path;
                if (creationFieldNeedsUserInput(field)) {
                    const required = document.createElement('span');
                    required.className = 'required';
                    required.textContent = '*';
                    label.appendChild(required);
                }
                const modeLabel = creationFieldModeLabel(field);
                if (modeLabel) {
                    const mode = document.createElement('span');
                    mode.className = `creation-field-mode${field.auto_filled ? ' auto' : ''}`;
                    mode.textContent = modeLabel;
                    label.appendChild(mode);
                }
                const hierarchy = creationHierarchyLabel(field);
                if (hierarchy) {
                    const badge = document.createElement('span');
                    badge.className = 'creation-hierarchy-badge';
                    badge.textContent = hierarchy;
                    label.appendChild(badge);
                }
                item.appendChild(label);
                if (field.description) {
                    const help = document.createElement('div');
                    help.className = 'help';
                    help.textContent = field.description;
                    item.appendChild(help);
                }
                let control;
                const options = Array.isArray(field.options) ? field.options : [];
                if (field.control === 'file_reference') {
                    control = document.createElement('div');
                    control.className = 'asset-picker';
                    const idInput = document.createElement('input');
                    idInput.type = 'text';
                    idInput.placeholder = '填写已上传的素材 ID，或先选择本地文件作为草稿';
                    idInput.value = creationCardValueText(field.value);
                    const fileInput = document.createElement('input');
                    fileInput.type = 'file';
                    fileInput.accept = field.accept || '*/*';
                    fileInput.addEventListener('change', () => {
                        const file = fileInput.files?.[0];
                        if (file) note.textContent = `已加入本地草稿：${file.name}（未上传，提交前仍需素材 ID）`;
                    });
                    const note = document.createElement('div');
                    note.className = 'asset-picker-note';
                    note.textContent = '本地文件仅用于准备素材，不会自动上传；执行前仍需对应平台素材 ID。';
                    idInput.addEventListener('change', () => {
                        field.value = idInput.value.trim() || undefined;
                        creationCardState.set(card.id, card);
                        scheduleCreationCardEvaluation(card, field.path);
                    });
                    control.append(idInput, fileInput, note);
                } else if (field.control === 'asset_picker') {
                    control = document.createElement('div');
                    control.className = 'asset-picker';
                    const fileInput = document.createElement('input');
                    fileInput.type = 'file';
                    fileInput.multiple = true;
                    fileInput.accept = field.accept || '*/*';
                    fileInput.addEventListener('change', () => {
                        const existing = Array.isArray(field.value) ? field.value : [];
                        field.value = [...existing, ...Array.from(fileInput.files || []).map(file => ({
                            local_file: file.name, mime_type: file.type || 'application/octet-stream',
                            size_bytes: file.size, source: 'local_staging',
                        }))];
                        creationCardState.set(card.id, card);
                        scheduleCreationCardEvaluation(card, field.path);
                        updateCreationCardIndicators(wrapper, card);
                    });
                    control.appendChild(fileInput);
                    const list = document.createElement('div');
                    list.className = 'asset-picker-list';
                    (Array.isArray(field.value) ? field.value : []).forEach(asset => {
                        const chip = document.createElement('span');
                        chip.className = 'asset-chip';
                        chip.textContent = asset?.local_file || asset?.name || asset?.asset || asset?.resource_name || '已选素材';
                        list.appendChild(chip);
                    });
                    control.appendChild(list);
                    const note = document.createElement('div');
                    note.className = 'asset-picker-note';
                    note.textContent = '当前加入本地草稿，不会自动上传或调用渠道接口。';
                    control.appendChild(note);
                } else if (field.control === 'derived_readonly') {
                    control = document.createElement('input');
                    control.className = 'derived-readonly';
                    control.readOnly = true;
                    control.disabled = true;
                    control.value = creationCardValueText(field.value || options[0]);
                } else if (field.control === 'select' || field.control === 'multiselect') {
                    const useChoiceTiles = field.control === 'multiselect'
                        || (options.length > 0 && options.length <= 6 && field.options_state !== 'awaiting_dependency' && field.options_state !== 'no_matching_rule');
                    if (useChoiceTiles) {
                        const multiple = field.control === 'multiselect';
                        control = renderChoiceTiles(options, field.value, multiple, option => field.option_labels?.[String(option.value)] || '', value => {
                            field.value = multiple && !value.length ? undefined : value;
                            creationCardState.set(card.id, card);
                            scheduleCreationCardEvaluation(card, field.path);
                            updateCreationCardIndicators(wrapper, card);
                        });
                        control.dataset.customChoice = 'true';
                    } else {
                    control = document.createElement('select');
                    if (field.control === 'select') {
                        const empty = document.createElement('option');
                        empty.value = '';
                        empty.textContent = field.options_state === 'awaiting_dependency'
                            ? '请先完成上游选择…'
                            : field.options_state === 'no_matching_rule'
                                ? '当前组合暂无可用选项'
                                : field.required ? '请选择…' : '不设置';
                        control.appendChild(empty);
                    }
                    if (field.options_state === 'awaiting_dependency' || field.options_state === 'no_matching_rule') {
                        control.disabled = true;
                    }
                    options.forEach(option => {
                        const node = document.createElement('option');
                        node.value = creationCardValueText(option.value);
                        node.textContent = field.option_labels?.[String(option.value)] || option.label || node.value;
                        if (Array.isArray(field.value) ? field.value.map(String).includes(node.value) : String(field.value ?? '') === node.value) node.selected = true;
                        control.appendChild(node);
                    });
                    }
                } else if (field.control === 'lookup') {
                    if (!card.selection_tokens) card.selection_tokens = {};
                    if (!card.selection_token_tools) card.selection_token_tools = {};
                    control = renderLookupPicker(field, {
                        platform: card.provider,
                        accountId: card.account_id,
                        getAccountId: () => card.account_id,
                        accountRequired: field.lookup?.account_required,
                        getLookupContext: () => lookupContextFromFields(card.fields),
                        targetToolName: field.tool,
                        fieldName: field.provider_field || field.path,
                        selectionTokens: card.selection_tokens,
                        optionsStore: card.lookup_options || (card.lookup_options = {}),
                        onSelection: ({ value, tokens }) => {
                            const key = field.provider_field || field.path;
                            field.value = value;
                            if (tokens) {
                                card.selection_tokens[key] = tokens;
                                card.selection_token_tools[key] = field.tool;
                            } else {
                                delete card.selection_tokens[key];
                                delete card.selection_token_tools[key];
                            }
                            creationCardState.set(card.id, card);
                            scheduleCreationCardEvaluation(card, field.path);
                            updateCreationCardIndicators(wrapper, card);
                        },
                    });
                } else if (field.control === 'checkbox') {
                    control = document.createElement('input');
                    control.type = 'checkbox';
                    control.checked = Boolean(field.value);
                } else if (field.control === 'text_list') {
                    control = document.createElement('textarea');
                    control.className = 'asset-text-list';
                    control.placeholder = '每行填写一条';
                    control.value = creationCardDisplayValue(field);
                } else if (field.control === 'object_editor') {
                    control = renderStructuredObjectEditor(
                        field.object_shape === 'array'
                            ? { type: 'array', items: { type: 'object', properties: field.object_properties || {} } }
                            : { type: 'object', properties: field.object_properties || {} },
                        field.value,
                        value => {
                            field.value = value;
                            creationCardState.set(card.id, card);
                            scheduleCreationCardEvaluation(card, field.path);
                            updateCreationCardIndicators(wrapper, card);
                        },
                        field.object_properties || {},
                        {
                            platform: card.provider,
                            accountId: card.account_id,
                            getAccountId: () => card.account_id,
                            targetToolName: field.tool,
                            fieldPath: field.provider_field,
                            accountRequired: field.lookup?.account_required,
                            getLookupContext: () => lookupContextFromFields(card.fields),
                            selectionTokens: card.selection_tokens || (card.selection_tokens = {}),
                            optionsStore: card.lookup_options || (card.lookup_options = {}),
                            onSelection: ({ fieldName, tokens }) => {
                                if (!card.selection_token_tools) card.selection_token_tools = {};
                                if (tokens) {
                                    card.selection_tokens[fieldName] = tokens;
                                    card.selection_token_tools[fieldName] = field.tool;
                                } else {
                                    delete card.selection_tokens[fieldName];
                                    delete card.selection_token_tools[fieldName];
                                }
                            },
                        },
                    );
                } else if (field.control === 'json' || field.control === 'advanced_json') {
                    control = document.createElement('textarea');
                    control.className = field.control === 'advanced_json' ? 'advanced-json-editor' : '';
                    control.placeholder = field.json_shape === 'array' ? '[...]'
                        : field.json_shape === 'object_or_array' ? '{...} 或 [...]'
                            : '{...}';
                    control.value = creationCardValueText(field.value);
                } else {
                    control = document.createElement('input');
                    control.type = field.control === 'number' ? 'number' : 'text';
                    control.value = creationCardValueText(field.value);
                }
                let controlNode = control;
                let checkboxState = null;
                if (field.control === 'checkbox') {
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
                control.dataset.path = field.path;
                const updateValue = () => {
                    if (field.control === 'asset_picker' || field.control === 'file_reference' || field.control === 'derived_readonly') return;
                    let value;
                    if (field.control === 'checkbox') value = control.checked;
                    else if (field.control === 'multiselect') value = Array.from(control.selectedOptions).map(option => option.value);
                    else value = parseCreationCardValue(field, control.value.trim());
                    if (checkboxState) checkboxState.textContent = control.checked ? '已开启' : '未开启';
                    field.value = value;
                    item.classList.toggle('missing', creationFieldNeedsUserInput(field) && (value === undefined || value === null || value === ''));
                    creationCardState.set(card.id, card);
                    scheduleCreationCardEvaluation(card, field.path);
                    const status = wrapper.querySelector('.creation-card-status');
                    updateCreationCardIndicators(wrapper, card);
                };
                if (!control.dataset.customChoice && field.control !== 'asset_picker' && field.control !== 'file_reference' && field.control !== 'derived_readonly' && field.control !== 'object_editor' && field.control !== 'lookup') control.addEventListener('change', updateValue);
                if (field.control === 'text' || field.control === 'text_list' || field.control === 'number' || field.control === 'advanced_json') control.addEventListener('input', updateValue);
                item.appendChild(controlNode);
                if (field.auto_filled && field.default_reason) {
                    const defaultNote = document.createElement('div');
                    defaultNote.className = 'creation-card-default-note';
                    defaultNote.textContent = `默认逻辑：${field.default_reason}`;
                    item.appendChild(defaultNote);
                }
                const source = document.createElement('div');
                source.className = 'source';
                source.textContent = field.auto_filled
                    ? '系统默认值 · 可直接修改'
                    : field.control === 'derived_readonly'
                    ? '由当前广告系列类型自动匹配'
                    : field.source === 'lookup' || field.control === 'lookup' ? '需要从指定账户中选择'
                        : (field.control === 'asset_picker' || field.control === 'file_reference') ? '本地素材草稿'
                            : field.control === 'object_editor' ? '按字段填写，系统会按 Tool Schema 组装'
                                : field.control === 'advanced_json' ? '高级 Provider 字段；请使用已审核的当前版本 payload'
                                    : '可直接填写';
                item.appendChild(source);
                if (field.manual_entry && typeof field.manual_entry === 'object') {
                    const help = document.createElement('div');
                    help.className = 'manual-entry-help';
                    const title = field.manual_entry.title || '需要手动提供的外部标识';
                    const instructions = field.manual_entry.instructions || '该字段当前没有可用的受控列表查询。';
                    help.innerHTML = `<strong>${escapeHtml(title)}</strong><br>${escapeHtml(instructions)}${field.manual_entry.example ? `<br>示例：${escapeHtml(field.manual_entry.example)}` : ''}`;
                    item.appendChild(help);
                }
                if (field.local_error) {
                    const error = document.createElement('div');
                    error.className = 'creation-card-field-error';
                    error.textContent = field.local_error;
                    item.appendChild(error);
                }
                sectionFields.appendChild(item);
                });
            });
            main.appendChild(fields);

            const footer = document.createElement('div');
            footer.className = 'creation-card-footer';
            const status = document.createElement('span');
            status.className = 'creation-card-status';
            status.textContent = creationCardStatus(card);
            footer.appendChild(status);
            const focusAction = document.createElement('button');
            focusAction.type = 'button';
            focusAction.className = 'creation-card-focus-action';
            focusAction.textContent = creationCardInvalidLabels(card).length ? '查看问题' : '定位待填项';
            focusAction.hidden = !(!String(card.account_id || '').trim() || creationCardPendingLabels(card).length || creationCardInvalidLabels(card).length);
            focusAction.addEventListener('click', () => focusCreationCardIssue(card, wrapper));
            footer.appendChild(focusAction);
            const actions = document.createElement('div');
            actions.className = 'creation-card-actions';
            (card.actions || []).forEach(action => {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = `creation-card-action${action.id === 'submit_create' ? ' primary' : ''}`;
                button.dataset.creationAction = action.id;
                button.textContent = action.label || action.id;
                if (action.id === 'submit_create') button.disabled = !creationCardCanSubmit(card);
                button.addEventListener('click', () => handleCreationCardAction(card.id, action.id));
                actions.appendChild(button);
            });
            footer.appendChild(actions);
            main.appendChild(footer);
            renderCreationCardFieldNav(card, wrapper);
            renderCreationCardSummary(card, wrapper);
            renderCreationCardAutomation(card, wrapper);
            return wrapper;
        }

        function renderUiCards(ui) {
            const fragment = document.createDocumentFragment();
            (ui?.cards || []).forEach(card => fragment.appendChild(renderCreationCard(card)));
            return fragment;
        }

        async function handleCreationCardAction(cardId, action) {
            const card = creationCardState.get(cardId);
            if (!card) return;
            if (action === 'continue_chat') {
                setInput(`请继续完善“${card.title || '广告创建'}”，我可以直接在输入框里补充参数。`);
                return;
            }
            if (action === 'open_form') {
                const selectionField = card.fields?.find(field => field.selection_kind === 'blueprint_variant');
                const selectedOption = selectionField?.options?.find(option => option.value === selectionField.value);
                const selected = selectedOption?.selector_value
                    || card.fields?.find(field => field.value)?.value
                    || null;
                openBlueprintManager(
                    card.provider,
                    selected,
                    selectedOption?.blueprint_id || null,
                );
                return;
            }
            if (action === 'validate') {
                await evaluateCreationCard(card, null);
                addMessage(card.ready ? '参数检查完成，当前填写内容满足蓝图要求。' : '参数检查完成，请根据卡片中的提示补充或调整参数。', 'agent');
                return;
            }
            if (action === 'preview') {
                showCreationPreview(card);
                return;
            }
            if (action === 'submit_create') {
                showCreationReview(card);
            }
        }

        // Add message to chat
