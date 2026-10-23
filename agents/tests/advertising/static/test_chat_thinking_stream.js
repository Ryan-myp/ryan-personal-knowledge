const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function element() {
    const listeners = {};
    const children = [];
    const attributes = {};
    return {
        id: '',
        className: '',
        innerHTML: '',
        textContent: '',
        dataset: {},
        children,
        classList: {
            values: new Set(),
            add(value) { this.values.add(value); },
            remove(value) { this.values.delete(value); },
            toggle(value, force) {
                if (force === true) this.values.add(value);
                else if (force === false) this.values.delete(value);
                else if (this.values.has(value)) this.values.delete(value);
                else this.values.add(value);
            },
            contains(value) { return this.values.has(value); },
        },
        addEventListener(name, callback) { listeners[name] = callback; },
        dispatch(name) { listeners[name]?.({ preventDefault() {} }); },
        appendChild(child) { children.push(child); return child; },
        append(...items) { children.push(...items); },
        insertBefore(child, before) {
            const index = children.indexOf(before);
            children.splice(index < 0 ? children.length : index, 0, child);
            return child;
        },
        get firstChild() { return children[0] || null; },
        remove() {},
        setAttribute(name, value) { attributes[name] = String(value); },
        getAttribute(name) { return attributes[name]; },
        querySelector(selector) {
            const className = selector.startsWith('.') ? selector.slice(1) : '';
            const matches = node => (
                Boolean(className)
                && String(node.className || '').split(/\s+/).includes(className)
            );
            const visit = node => {
                for (const child of node.children || []) {
                    if (matches(child)) return child;
                    const nested = visit(child);
                    if (nested) return nested;
                }
                return null;
            };
            return visit(this);
        },
    };
}

function environment() {
    const elements = new Map();
    const chatContainer = element();
    const chatArea = element();
    elements.set('chatContainer', chatContainer);
    elements.set('chatArea', chatArea);
    const context = {
        document: {
            getElementById(id) {
                if (id === 'activeThinkingMessage') {
                    return chatContainer.children.find(node => node.id === id) || null;
                }
                return elements.get(id) || null;
            },
            createElement() {
                const node = element();
                node.toggle = element();
                node.content = element();
                node.box = element();
                return node;
            },
            querySelector() { return null; },
            body: { classList: { add() {}, remove() {}, toggle() {} } },
        },
        escapeHtml: value => String(value ?? ''),
        traceFilter: { platform: 'all', status: 'all', kind: 'all' },
        setWorkbenchView() {},
        closeAgentWorkbench() {},
    };
    for (const filename of ['chat-queue.js', 'chat-state.js', 'chat-trace.js']) {
        const source = path.resolve(
            __dirname,
            '../../../deployments/advertising/static/js',
            filename,
        );
        vm.runInNewContext(fs.readFileSync(source, 'utf8'), context, {
            filename: source,
        });
    }
    context.updateTraceHeader = () => {};
    context.renderExecutionTrace = () => {};
    return { context, chatContainer, chatArea };
}

test('execution summary follows its own bottom unless the reader scrolls up', () => {
    const { context, chatContainer, chatArea } = environment();
    chatArea.clientHeight = 300;
    chatArea.scrollHeight = 500;
    chatArea.scrollTop = 200;
    context.applyExecutionEvent({
        type: 'reasoning_delta', content_type: 'execution_summary',
        language_code: 'zh', content: '第一段',
    });
    const content = chatContainer.children[0].querySelector('.thinking-content');
    content.clientHeight = 100;
    content.scrollHeight = 400;
    content.scrollTop = 300;
    context.applyExecutionEvent({
        type: 'reasoning_delta', content_type: 'execution_summary',
        language_code: 'zh', content: '第二段',
    });
    assert.equal(content.scrollTop, 400);

    content.scrollTop = 120;
    chatArea.scrollTop = 80;
    content.scrollHeight = 600;
    chatArea.scrollHeight = 800;
    context.applyExecutionEvent({
        type: 'reasoning_delta', content_type: 'execution_summary',
        language_code: 'zh', content: '第三段',
    });
    assert.equal(content.scrollTop, 120);
    assert.equal(chatArea.scrollTop, 80);
    assert.equal(content.textContent, '第一段第二段第三段');
});

test('localized execution summaries share a collapsible box and auto-collapse', () => {
    const { context, chatContainer } = environment();

    context.applyExecutionEvent({
        type: 'reasoning_delta',
        content_type: 'execution_summary', language_code: 'zh',
        content: '正在检查请求。',
    });
    context.applyExecutionEvent({
        type: 'reasoning_delta',
        content_type: 'execution_summary', language_code: 'zh',
        content: '工具已返回。',
    });

    const message = chatContainer.children[0];
    assert.ok(message);
    const content = message.querySelector('.thinking-content');
    const box = message.querySelector('.thinking-box');
    assert.equal(content.textContent, '正在检查请求。工具已返回。');
    assert.equal(box.classList.contains('collapsed'), false);

    message.querySelector('.thinking-toggle').dispatch('click');
    assert.equal(box.classList.contains('collapsed'), true);
    message.querySelector('.thinking-toggle').dispatch('click');
    assert.equal(box.classList.contains('collapsed'), false);

    context.applyExecutionEvent({ type: 'done', status: 'succeeded' });
    assert.equal(box.classList.contains('collapsed'), true);
    assert.equal(message.id, '');
    assert.equal(content.textContent, '正在检查请求。工具已返回。');
});

test('raw or legacy provider reasoning is not rendered as user-facing progress', () => {
    const { context, chatContainer } = environment();
    context.applyExecutionEvent({ type: 'reasoning_delta', content: 'Private scratchpad' });
    context.applyExecutionEvent({ type: 'model_reasoning_delta', delta: 'Private scratchpad' });
    assert.equal(chatContainer.children.length, 0);
});

test('English progress uses English summary controls', () => {
    const { context, chatContainer } = environment();
    context.applyExecutionEvent({
        type: 'reasoning_delta', content_type: 'execution_summary',
        language_code: 'en', content: 'Checking the request requirements.',
    });
    const message = chatContainer.children[0];
    const title = message.querySelector('.thinking-toggle').children[0];
    assert.equal(title.textContent, 'Execution Summary');
    assert.equal(message.querySelector('.thinking-toggle-state').textContent, 'Collapse');
    context.finalizeStreamingThought();
    assert.equal(message.querySelector('.thinking-toggle-state').textContent, 'Expand');
});

test('summary controls keep their language after merging into the final reply', () => {
    const { context, chatContainer } = environment();
    context.applyExecutionEvent({
        type: 'reasoning_delta', content_type: 'execution_summary',
        language_code: 'en', content: 'Checking the request requirements.',
    });
    const message = chatContainer.children[0];
    context.finalizeStreamingThought();
    const box = message.querySelector('.thinking-box');
    const contentHost = message.querySelector('.message-content');
    contentHost.children.splice(contentHost.children.indexOf(box), 1);
    const finalReply = element();
    finalReply.append(box);

    const button = finalReply.querySelector('.thinking-toggle');
    button.dispatch('click');
    assert.equal(box.classList.contains('collapsed'), false);
    assert.equal(button.getAttribute('aria-expanded'), 'true');
    assert.equal(button.querySelector('.thinking-toggle-state').textContent, 'Collapse');
    button.dispatch('click');
    assert.equal(button.getAttribute('aria-expanded'), 'false');
    assert.equal(button.querySelector('.thinking-toggle-state').textContent, 'Expand');
});
