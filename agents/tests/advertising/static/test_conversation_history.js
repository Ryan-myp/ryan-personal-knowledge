const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function environment(messages) {
    const displayed = [];
    const container = { replaceChildren: () => {} };
    const context = {
        sessionId: null, selectedConversationId: null,
        loadedConversationTurnIds: new Set(), pendingRequest: null,
        document: { getElementById: id => id === 'chatContainer' ? container : null },
        resetCreationWorkbench: () => {},
        restoreExecutionTrace: () => {},
        loadLatestDurableRun: async () => {},
        addMessage: (...args) => displayed.push(args),
    };
    const source = path.resolve(__dirname, '../../../deployments/advertising/static/js/chat-requests.js');
    vm.runInNewContext(fs.readFileSync(source, 'utf8'), context, { filename: source });
    context.authenticatedFetch = async () => ({
        ok: true, text: async () => JSON.stringify({ session_id: 'history', messages }),
    });
    context.renderConversationHistory = () => {};
    return { context, displayed };
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
