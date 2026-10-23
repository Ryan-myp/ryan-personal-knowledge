const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function matches(node, selector) {
    if (selector.startsWith('.')) {
        return String(node.className || '').split(/\s+/).includes(selector.slice(1));
    }
    if (selector.startsWith('#')) return node.id === selector.slice(1);
    return false;
}

function findNode(root, selector) {
    for (const child of root?.children || []) {
        if (matches(child, selector)) return child;
        const nested = findNode(child, selector);
        if (nested) return nested;
    }
    return null;
}

function createEnvironment() {
    const nodes = new Map();
    const createNode = () => ({
        id: '',
        className: '',
        textContent: '',
        value: '',
        hidden: false,
        disabled: false,
        maxLength: 0,
        children: [],
        listeners: {},
        attributes: {},
        classList: {
            add() {},
            remove() {},
            toggle() {},
            contains() { return false; },
        },
        setAttribute(name, value) { this.attributes[name] = value; },
        removeAttribute(name) { delete this.attributes[name]; },
        addEventListener(name, callback) { this.listeners[name] = callback; },
        appendChild(child) {
            this.children.push(child);
            return child;
        },
        replaceChildren(...children) { this.children = [...children]; },
        querySelector(selector) { return findNode(this, selector); },
        focus() {},
        remove() {},
        dispatch(name, event = {}) {
            this.listeners[name]?.({
                preventDefault() {},
                ...event,
            });
        },
    });
    const elementIds = [
        'chatQueuePanel', 'sendBtn', 'stopBtn', 'chatInputHint', 'userInput',
    ];
    for (const id of elementIds) {
        const node = createNode();
        node.id = id;
        nodes.set(id, node);
    }

    const context = {
        document: {
            getElementById: id => nodes.get(id) || null,
            createElement: createNode,
            querySelector: selector => findNode(nodes.get('chatQueuePanel'), selector),
            addEventListener() {},
        },
        initializeTheme() {},
        resetExecutionTrace() {},
        refreshWorkspaceMode() {},
        refreshConversationHistory() {},
        showHistoryNotice() {},
        closeWorkspacePopovers() {},
        chatMediaUploading: false,
        isSending: true,
        isStopping: false,
        sessionId: 'session-a',
        activeRunSessionId: 'session-a',
        MAX_CHAT_QUEUE_SIZE: 10,
        MAX_CHAT_QUEUE_TOTAL_SIZE: 50,
        pausedChatQueueSessions: new Set(),
        pendingBlueprintRequest: null,
        pendingBlueprintContinuation: null,
    };

    for (const filename of ['chat-queue.js', 'chat-messages.js']) {
        const sourcePath = path.resolve(
            __dirname,
            '../../../deployments/advertising/static/js',
            filename,
        );
        vm.runInNewContext(fs.readFileSync(sourcePath, 'utf8'), context, {
            filename: sourcePath,
        });
    }
    context.chatMessageQueue = vm.runInNewContext(
        'new ChatMessageQueue(10, 50)',
        context,
    );
    context.editingQueueMessage = null;

    return { context, nodes };
}

test('a queued message can be edited, saved, and cancelled without losing attachments', () => {
    const { context, nodes } = createEnvironment();
    context.chatMessageQueue.enqueue('session-a', {
        id: 'queued-1',
        text: '原始问题',
        attachments: [{ id: 'media-1', filename: 'image.png' }],
        requestParams: {
            user_input: '原始问题',
            session_id: 'session-a',
            media_ids: ['media-1'],
            creation_template_id: 'template-1',
        },
    });

    context.updateChatQueuePanel();
    nodes.get('chatQueuePanel')
        .querySelector('.chat-queue-edit')
        .dispatch('click');

    let editor = nodes.get('chatQueuePanel').querySelector('.chat-queue-edit-input');
    assert.ok(editor);
    assert.equal(editor.value, '原始问题');
    editor.value = '修订后的问题';
    editor.dispatch('input');
    context.isSending = false;
    context.processNextQueuedMessage();
    assert.equal(context.chatMessageQueue.size('session-a'), 1);
    context.isSending = true;
    nodes.get('chatQueuePanel')
        .querySelector('.chat-queue-save')
        .dispatch('click');

    let queued = context.chatMessageQueue.list('session-a')[0];
    assert.equal(queued.text, '修订后的问题');
    assert.equal(queued.requestParams.user_input, '修订后的问题');
    assert.equal(queued.requestParams.media_ids[0], 'media-1');
    assert.equal(queued.requestParams.creation_template_id, 'template-1');

    nodes.get('chatQueuePanel')
        .querySelector('.chat-queue-edit')
        .dispatch('click');
    editor = nodes.get('chatQueuePanel').querySelector('.chat-queue-edit-input');
    editor.value = '不保存的草稿';
    editor.dispatch('input');
    nodes.get('chatQueuePanel')
        .querySelector('.chat-queue-cancel')
        .dispatch('click');

    queued = context.chatMessageQueue.list('session-a')[0];
    assert.equal(queued.text, '修订后的问题');
    assert.equal(context.editingQueueMessage, null);
});

test('a stale paused flag with an empty queue does not delay a new message', async () => {
    const { context, nodes } = createEnvironment();
    const executed = [];
    context.isSending = false;
    context.pausedChatQueueSessions.add('session-a');
    context.pendingChatAttachments = [];
    context.pendingBlueprintRequest = null;
    context.clearPendingChatMedia = () => {};
    context.executeChatMessage = item => executed.push(item);
    nodes.get('userInput').value = '新问题直接发送';
    nodes.get('userInput').style = {};

    await context.sendMessage();

    assert.equal(executed.length, 1);
    assert.equal(executed[0].requestParams.user_input, '新问题直接发送');
    assert.equal(context.chatMessageQueue.size('session-a'), 0);
    assert.equal(context.pausedChatQueueSessions.has('session-a'), false);
});

test('a paused queue keeps new messages behind its existing entries', async () => {
    const { context, nodes } = createEnvironment();
    const executed = [];
    context.isSending = false;
    context.pausedChatQueueSessions.add('session-a');
    context.pendingChatAttachments = [];
    context.pendingBlueprintRequest = null;
    context.clearPendingChatMedia = () => {};
    context.executeChatMessage = item => executed.push(item);
    context.chatMessageQueue.enqueue('session-a', {
        id: 'queued-existing',
        text: '前一条',
        requestParams: { user_input: '前一条', session_id: 'session-a' },
    });
    nodes.get('userInput').value = '后续消息';
    nodes.get('userInput').style = {};

    await context.sendMessage();

    assert.equal(executed.length, 0);
    assert.equal(context.chatMessageQueue.size('session-a'), 2);
    assert.equal(
        context.chatMessageQueue.list('session-a')[1].requestParams.user_input,
        '后续消息',
    );
});

test('finishing a stopped turn clears the pause when the queue is empty', () => {
    const { context } = createEnvironment();
    context.isStopping = true;
    context.activeRunSessionId = 'session-a';
    context.pausedChatQueueSessions.add('session-a');

    context.finishChatTurn();

    assert.equal(context.isSending, false);
    assert.equal(context.isStopping, false);
    assert.equal(context.activeRunSessionId, null);
    assert.equal(context.pausedChatQueueSessions.has('session-a'), false);
});
