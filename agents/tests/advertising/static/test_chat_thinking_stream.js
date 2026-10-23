const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function element() {
    const listeners = {};
    const children = [];
    return {
        id: '',
        className: '',
        innerHTML: '',
        textContent: '',
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
        remove() {},
        setAttribute() {},
        querySelector(selector) {
            if (selector === '.thinking-toggle') return this.toggle;
            if (selector === '.thinking-content') return this.content;
            if (selector === '.thinking-box') return this.box;
            return null;
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
    return { context, chatContainer };
}

test('reasoning deltas stream into a collapsible box and auto-collapse', () => {
    const { context, chatContainer } = environment();

    context.applyExecutionEvent({
        type: 'reasoning_delta',
        content: '先分析需求。',
    });
    context.applyExecutionEvent({
        type: 'reasoning_delta',
        content: '再确定输出。',
    });

    const message = chatContainer.children[0];
    assert.ok(message);
    assert.equal(message.content.textContent, '先分析需求。再确定输出。');
    assert.equal(message.box.classList.contains('collapsed'), false);

    message.toggle.dispatch('click');
    assert.equal(message.box.classList.contains('collapsed'), true);
    message.toggle.dispatch('click');
    assert.equal(message.box.classList.contains('collapsed'), false);

    context.applyExecutionEvent({ type: 'done', status: 'succeeded' });
    assert.equal(message.box.classList.contains('collapsed'), true);
    assert.equal(message.id, '');
    assert.equal(message.content.textContent, '先分析需求。再确定输出。');
});
