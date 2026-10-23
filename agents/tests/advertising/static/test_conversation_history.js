const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function environment(messages, fetchHandler = null) {
    const displayed = [];
    const container = {
        children: [],
        get firstChild() { return this.children[0] || null; },
        replaceChildren() { this.children = []; },
        prepend(node) { this.children.unshift(node); },
        appendChild(node) { this.children.push(node); return node; },
        insertBefore(node, before) {
            const index = this.children.indexOf(before);
            this.children.splice(index < 0 ? this.children.length : index, 0, node);
            return node;
        },
    };
    const scrollListeners = {};
    const chatArea = {
        scrollTop: 0,
        scrollHeight: 100,
        clientHeight: 500,
        addEventListener(name, callback) { scrollListeners[name] = callback; },
    };
    const buttonListeners = {};
    const paginationPanel = { hidden: true };
    const paginationButton = {
        disabled: false,
        textContent: '',
        addEventListener(name, callback) { buttonListeners[name] = callback; },
    };
    const paginationStatus = { textContent: '' };
    const sessionPaginationPanel = { hidden: true };
    const sessionPaginationButton = {
        disabled: false,
        textContent: '',
        addEventListener(name, callback) { buttonListeners[`sessions:${name}`] = callback; },
    };
    const sessionPaginationStatus = { textContent: '' };
    const nodes = {
        chatContainer: container,
        chatArea,
        chatHistory: container,
        chatHistoryStatus: { textContent: '' },
        conversationListPagination: sessionPaginationPanel,
        loadOlderConversationSessions: sessionPaginationButton,
        conversationListPaginationStatus: sessionPaginationStatus,
        conversationHistoryPagination: paginationPanel,
        loadOlderConversationButton: paginationButton,
        conversationHistoryPaginationStatus: paginationStatus,
    };
    const context = {
        sessionId: null, selectedConversationId: null,
        isSending: false, activeRunSessionId: null,
        loadedConversationTurnIds: new Set(), pendingRequest: null,
        pendingBlueprintRequest: null, pendingBlueprintContinuation: null,
        pendingCreationReview: false,
        conversationHistory: [],
        conversationHistoryRequest: 0,
        conversationHistoryListPage: {
            nextCursor: null, hasMore: false, loading: false, error: '',
        },
        URLSearchParams,
        conversationLoadSequence: 0,
        conversationHistoryPage: {
            sessionId: null, nextCursor: null, hasMore: false, loading: false, generation: 0,
        },
        document: {
            getElementById: id => nodes[id] || null,
            createElement: tag => ({
                tagName: tag,
                className: '',
                textContent: '',
                children: [],
                appendChild(node) { this.children.push(node); return node; },
            }),
        },
        window: { setTimeout() {} },
        resetCreationWorkbench: () => {},
        restoreExecutionTrace: () => {},
        loadLatestDurableRun: async () => {},
        clearPendingChatMedia: () => {},
        updateChatQueuePanel: () => {},
        showHistoryNotice: () => {},
        addMessage: (...args) => {
            displayed.push(args);
            const node = { content: args[0] };
            const options = args[7] || {};
            if (options.insertBefore) container.insertBefore(node, options.insertBefore);
            else container.appendChild(node);
            chatArea.scrollHeight += 100;
            return node;
        },
    };
    const source = path.resolve(__dirname, '../../../deployments/advertising/static/js/chat-requests.js');
    vm.runInNewContext(fs.readFileSync(source, 'utf8'), context, { filename: source });
    const calls = [];
    context.serviceFetch = async url => {
        calls.push(url);
        const payload = fetchHandler
            ? await fetchHandler(url, calls.length)
            : { session_id: 'history', messages };
        return { ok: true, text: async () => JSON.stringify(payload) };
    };
    context.renderConversationHistory = () => {};
    return {
        context, displayed, calls, chatArea, container, scrollListeners,
        paginationPanel, paginationButton, buttonListeners, paginationStatus,
        sessionPaginationPanel, sessionPaginationButton, sessionPaginationStatus,
    };
}

test('history ignores empty internal assistant placeholders and non-chat roles', async () => {
    const { context, displayed } = environment([
        { role: 'user', content: '有模板吗', turn_id: 'turn' },
        { role: 'assistant', content: '\n\n', turn_id: 'turn' },
        { role: 'tool', content: '{"templates": []}', turn_id: 'turn' },
        { role: 'assistant', content: '有三个模板。', turn_id: 'turn' },
    ]);
    await context.loadConversation('history');
    assert.deepEqual(displayed.map(args => args[0]), ['有模板吗', '有三个模板。']);
});

test('conversation switching is blocked while a Run is active', async () => {
    const { context, calls } = environment([]);
    context.isSending = true;

    await context.loadConversation('history');

    assert.equal(calls.length, 0);
    assert.equal(context.sessionId, null);
});

test('history preserves the reply text, error style, Tool badges and card launcher', async () => {
    const tools = [{ tool: 'google_create_campaign', success: false }];
    const ui = { cards: [{ id: 'shopping', type: 'ad_creation_form' }] };
    const { context, displayed } = environment([
        { role: 'user', content: '确认创建', turn_id: 'turn' },
        { role: 'assistant', content: '本次执行未完成：未开启真实写入。', is_error: true, tools, ui, turn_id: 'turn' },
    ]);
    await context.loadConversation('history');
    assert.equal(displayed.length, 2);
    assert.equal(displayed[1][3], true);
    assert.deepEqual(JSON.parse(JSON.stringify(displayed[1][2])), tools);
    assert.deepEqual(JSON.parse(JSON.stringify(displayed[1][6])), ui);
    assert.equal(displayed[1][7].openWorkbench, false);
});

test('a meaningful card-only interaction remains visible, an empty bubble does not', () => {
    const { context } = environment([]);
    assert.equal(context.chatMessageHasPresentation('', null, { cards: [{}] }), true);
    assert.equal(context.chatMessageHasPresentation('  \n', [], {}), false);
    assert.equal(context.chatMessageHasPresentation('实际回复', null, null), true);
});

test('a media-gallery-only reply remains visible in conversation history', () => {
    const { context } = environment([]);
    assert.equal(
        context.chatMessageHasPresentation('', null, { media_gallery: [{ kind: 'image' }] }),
        true,
    );
});

test('conversation history loads the newest page, then prepends older pages without moving the viewport', async () => {
    const {
        context, displayed, calls, chatArea, container, scrollListeners, paginationPanel,
    } = environment(
        [],
        (_url, requestNumber) => requestNumber === 1
            ? {
                session_id: 'history',
                messages: [
                    { role: 'user', content: 'new question', turn_id: 'new' },
                    { role: 'assistant', content: 'new answer', turn_id: 'new' },
                ],
                has_more: true,
                next_cursor: 'older-turn-message',
            }
            : {
                session_id: 'history',
                messages: [
                    { role: 'user', content: 'old question', turn_id: 'old' },
                    { role: 'assistant', content: 'old answer', turn_id: 'old' },
                ],
                has_more: false,
                next_cursor: null,
            },
    );

    await context.loadConversation('history');
    assert.match(calls[0], /limit=10/);
    assert.deepEqual(displayed.map(args => args[0]), ['new question', 'new answer']);
    assert.equal(chatArea.scrollTop, chatArea.scrollHeight);
    assert.equal(paginationPanel.hidden, false);

    chatArea.scrollTop = 24;
    const previousHeight = chatArea.scrollHeight;
    await scrollListeners.scroll();

    assert.match(calls[1], /before_message_id=older-turn-message/);
    assert.deepEqual(
        container.children.map(node => node.content),
        ['old question', 'old answer', 'new question', 'new answer'],
    );
    assert.equal(chatArea.scrollTop, 24 + chatArea.scrollHeight - previousHeight);
    assert.equal(paginationPanel.hidden, true);
});

test('conversation list appends older scoped pages and deduplicates session IDs', async () => {
    const { context, calls, sessionPaginationPanel } = environment(
        [],
        (url, requestNumber) => requestNumber === 1
            ? {
                sessions: [
                    { session_id: 'newer', title: '最近对话' },
                    { session_id: 'duplicate', title: '重复记录' },
                ],
                has_more: true,
                next_cursor: {
                    updated_at: '2026-10-19T12:00:00+00:00',
                    session_id: 'duplicate',
                },
            }
            : {
                sessions: [
                    { session_id: 'duplicate', title: '不应重复' },
                    { session_id: 'older', title: '更早的对话' },
                ],
                has_more: false,
                next_cursor: null,
            },
    );

    await context.refreshConversationHistory({ silent: true });
    assert.equal(context.conversationHistory.length, 2);
    assert.equal(context.conversationHistoryListPage.hasMore, true);
    assert.equal(sessionPaginationPanel.hidden, false);
    await context.loadMoreConversationSessions();

    assert.match(calls[0], /\/sessions\?limit=50$/);
    assert.match(calls[1], /before_updated_at=2026-10-19T12%3A00%3A00%2B00%3A00/);
    assert.match(calls[1], /before_session_id=duplicate/);
    assert.deepEqual(
        Array.from(context.conversationHistory, item => item.session_id),
        ['newer', 'duplicate', 'older'],
    );
    assert.equal(context.conversationHistoryListPage.hasMore, false);
    assert.equal(context.conversationHistoryListPage.loading, false);
    assert.equal(sessionPaginationPanel.hidden, true);
});

test('live rendering preserves the same persisted failure reply without another prefix', () => {
    const { context, displayed } = environment([]);
    const content = '本次执行未完成：当时未开启真实写入。';
    context.renderStreamResult({
        session_id: 'history', status: 'failed', content,
        results: [{ tool: 'google_create_campaign', success: false }],
    }, {});
    assert.equal(displayed[0][0], content);
    assert.equal(displayed[0][3], true);
});

test('empty stream replies explain that no operation ran instead of pointing to the trace panel', () => {
    const { context, displayed } = environment([]);
    context.renderStreamResult({
        session_id: 'history',
        status: 'succeeded',
        content: '',
        results: [],
    }, {});

    assert.match(displayed[0][0], /没有执行工具操作/);
    assert.doesNotMatch(displayed[0][0], /右侧|执行轨迹/);
});
