/* Shared bounded, searchable multi-select for schema-driven forms. */
let multiChoiceSequence = 0;

function multiChoiceOptions(options, selectedValues = [], labelFor) {
    const entries = new Map();
    for (const option of options) {
        const object = option !== null && typeof option === 'object';
        const value = object ? option.value : option;
        if (value === undefined || value === null || value === '') continue;
        const key = String(value);
        const label = choiceDisplayLabel(value, (object ? option.label : '') || labelFor?.(value));
        entries.set(key, {key, value, label, unavailable: false});
    }
    for (const value of selectedValues) {
        if (value === undefined || value === null || value === '') continue;
        const key = String(value);
        if (!entries.has(key)) entries.set(key, {key, value, label: key, unavailable: true});
    }
    return [...entries.values()];
}

function filterMultiChoices(options, query) {
    const text = String(query || '').trim().toLocaleLowerCase();
    return options.filter(option => `${option.label} ${option.key}`.toLocaleLowerCase().includes(text));
}

function renderSearchableMultiChoice(options, selectedValues, labelFor, onChange) {
    const values = Array.isArray(selectedValues) ? selectedValues : [];
    const entries = multiChoiceOptions(options, values, labelFor);
    let committed = new Set(values.map(String));
    let pending = new Set(committed);
    const control = document.createElement('div');
    control.className = 'multi-choice';
    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'multi-choice-trigger';
    trigger.setAttribute('aria-haspopup', 'dialog');
    trigger.setAttribute('aria-expanded', 'false');
    const panel = document.createElement('div');
    panel.className = 'multi-choice-popover';
    panel.id = `multi-choice-${++multiChoiceSequence}`;
    panel.popover = 'auto';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', '选择多个选项');
    trigger.setAttribute('popovertarget', panel.id);
    trigger.setAttribute('aria-controls', panel.id);
    const search = document.createElement('input');
    search.type = 'search';
    search.placeholder = '搜索名称或代码';
    search.setAttribute('aria-label', '搜索选项');
    const list = document.createElement('div');
    list.className = 'multi-choice-options';
    const footer = document.createElement('div');
    footer.className = 'multi-choice-footer';
    const count = document.createElement('span');
    count.setAttribute('aria-live', 'polite');
    const clear = document.createElement('button');
    clear.type = 'button';
    clear.textContent = '清空';
    const apply = document.createElement('button');
    apply.type = 'button';
    apply.className = 'multi-choice-apply';
    apply.textContent = '应用选择';
    footer.append(count, clear, apply);
    panel.append(search, list, footer);
    control.append(trigger, panel);

    function renderSummary() {
        const selected = entries.filter(item => committed.has(item.key));
        const labels = selected.slice(0, 2).map(item => item.label).join('、');
        trigger.textContent = selected.length > 2 ? `${labels} 等 ${selected.length} 项` : labels || '请选择…';
        trigger.title = selected.map(item => item.label).join('、');
    }

    function renderOptions() {
        list.replaceChildren();
        const matches = filterMultiChoices(entries, search.value);
        for (const item of matches) {
            const row = document.createElement('label');
            row.className = 'multi-choice-option';
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = item.key;
            checkbox.checked = pending.has(item.key);
            checkbox.addEventListener('change', () => {
                if (checkbox.checked) pending.add(item.key);
                else pending.delete(item.key);
                count.textContent = `已选 ${pending.size} 项`;
            });
            const name = document.createElement('span');
            name.textContent = item.label;
            const code = document.createElement('small');
            code.textContent = item.unavailable ? `${item.key} · 不在当前选项中` : item.label === item.key ? '' : item.key;
            row.append(checkbox, name, code);
            list.append(row);
        }
        if (!matches.length) list.textContent = '没有匹配的选项，请尝试其他名称或代码。';
        count.textContent = `已选 ${pending.size} 项`;
    }

    panel.addEventListener('beforetoggle', event => {
        const opening = event.newState === 'open';
        trigger.setAttribute('aria-expanded', String(opening));
        if (!opening) return;
        pending = new Set(committed);
        search.value = '';
        renderOptions();
        const rect = trigger.getBoundingClientRect();
        const viewportHeight = window.innerHeight;
        const height = Math.min(360, viewportHeight - 24);
        const width = Math.min(Math.max(rect.width, 300), 560, window.innerWidth - 24);
        panel.style.width = `${width}px`;
        panel.style.maxHeight = `${height}px`;
        panel.style.left = `${Math.max(12, Math.min(rect.left, window.innerWidth - width - 12))}px`;
        panel.style.top = `${Math.max(12, Math.min(rect.bottom + 4, viewportHeight - height - 12))}px`;
    });
    panel.addEventListener('toggle', event => {
        if (event.newState === 'open') search.focus();
    });
    search.addEventListener('input', renderOptions);
    search.addEventListener('keydown', event => {
        if (event.key === 'Enter') event.preventDefault();
    });
    clear.addEventListener('click', () => { pending.clear(); renderOptions(); });
    apply.addEventListener('click', () => {
        committed = new Set(pending);
        renderSummary();
        panel.hidePopover();
        trigger.focus();
        onChange(entries.filter(item => committed.has(item.key)).map(item => item.value));
    });
    renderSummary();
    return control;
}
