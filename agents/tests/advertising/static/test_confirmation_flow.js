const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function environment() {
    const requests = [];
    const displayed = [];
    const nodes = {};
    const node = () => ({
        hidden: false, value: '', innerHTML: '', textContent: '',
        classList: { add() {}, remove() {}, toggle() {} },
        setAttribute() {}, focus() {}, querySelector: () => null,
        appendChild(child) { nodes[child.id] = child; },
        replaceChildren() {},
        remove() { delete nodes[this.id]; },
    });
    for (const id of ['confirmation-workbench-host', 'creation-workbench-host', 'creation-workbench-view', 'userInput']) {
        nodes[id] = node();
    }
    const context = {
        sessionId: 'session', selectedConversationId: 'session',
        isSending: false, pendingRequest: null, pendingCreationReview: null,
        pendingBlueprintRequest: null,
        pendingBlueprintContinuation: null,
        workspaceMode: { mode: 'live', liveAvailable: true, saving: false, loading: false },
        document: {
            getElementById: id => nodes[id] || null,
            createElement: node, querySelector: () => null,
            addEventListener() {},
            body: { classList: { add() {}, remove() {} } },
        },
        setTimeout() {}, escapeHtml: value => String(value).replaceAll('<', '&lt;').replaceAll('>', '&gt;'),
        creationSubmissionModeError: () => '',
        markTraceAwaitingConfirmation() {}, addLoading() {}, removeLoading() {},
        initializeTheme() {}, resetExecutionTrace() {}, refreshWorkspaceMode() {},
        startExecutionTrace() {}, refreshConversationHistory: async () => {},
        markChatRequestFailure: error => error.message,
    };
    for (const file of [
        'chat-queue.js', 'chat-workbench.js', 'chat-messages.js',
        'chat-requests.js',
    ]) {
        vm.runInNewContext(fs.readFileSync(path.resolve(
            __dirname, '../../../deployments/advertising/static/js', file,
        ), 'utf8'), context, { filename: file });
    }
    context.chatMessageQueue = vm.runInNewContext(
        'new ChatMessageQueue(10)', context,
    );
    context.pausedChatQueueSessions = new Set();
    context.editingQueueMessage = null;
    context.chatMediaUploading = false;
    context.MAX_CHAT_QUEUE_SIZE = 10;
    context.isStopping = false;
    context.activeRunSessionId = null;
    context.addMessage = (...args) => displayed.push(args);
    context.addLoading = () => {};
    context.removeLoading = () => {};
    context.markChatRequestFailure = error => error.message;
    context.streamChatRequest = async params => {
        requests.push(params);
        return { session_id: 'session', status: 'succeeded', content: 'Done', results: [] };
    };
    context.refreshConversationHistory = async () => {};
    context.creationContextForCard = card => ({
        account_id: card.account_id,
        platform_params: card.platform_params,
        creation_blueprint_id: card.blueprint_id,
        creation_blueprint_version: card.blueprint_version,
        creation_template_id: card.template_id,
    });
    context.creationContinuationContextForCard = (
        card, assistantPrompt, targetSessionId, previous,
    ) => ({
        session_id: targetSessionId,
        assistant_prompt: assistantPrompt,
        fields: card?.fields || previous?.fields || [],
        reply_options: previous?.reply_options || [],
    });
    return { context, requests, displayed, nodes, node };
}

const approval = (overrides = {}) => ({
    type: 'confirm_write_plan', session_id: 'session',
    account_id: '9055507554', platform: 'google-ads',
    confirmation_token: 'one-time-approval', expires_at: '2099-01-01T00:00:00Z',
    tools: ['google_create_campaign', 'google_create_ad_group'],
    ...overrides,
});

const original = () => ({
    user_input: '提交 Shopping 创建计划', session_id: 'session',
    account_id: '9055507554', execution_mode: 'live',
    creation_blueprint_id: 'google-ads.shopping',
    creation_blueprint_version: '1.1.0', creation_template_id: 'shopping-template',
    tool_allowlist: ['google_create_campaign', 'google_create_ad_group'],
    platform_params: {
        'google-ads': {
            google_create_campaign: { campaign_name: 'Paused Shopping', daily_budget: 20, status: 'PAUSED' },
            google_create_ad_group: { name: 'Paused Group', cpc_bid_micros: 500000 },
        },
        example: { preserved: true },
    },
});

test('a confirmation preserves the signed account, all namespace parameters and Tool scope', async () => {
    const { context, requests } = environment();
    const request = original();
    context.showConfirm(approval(), request);
    await context.executeConfirm();
    assert.equal(requests.length, 1);
    const sent = requests[0];
    assert.equal(sent.account_id, request.account_id);
    assert.deepEqual(JSON.parse(JSON.stringify(sent.platform_params)), request.platform_params);
    assert.deepEqual(JSON.parse(JSON.stringify(sent.tool_allowlist)), request.tool_allowlist);
    assert.equal(sent.creation_template_id, request.creation_template_id);
    assert.equal(sent.confirmed, true);
    assert.equal(sent.confirmation_payload.confirmation_token, 'one-time-approval');
});

test('an open confirmation snapshots the draft instead of reading later edits', async () => {
    const { context, requests } = environment();
    const request = original();
    context.showConfirm(approval(), request);
    request.platform_params['google-ads'].google_create_campaign.daily_budget = 999;
    await context.executeConfirm();
    assert.equal(requests[0].platform_params['google-ads'].google_create_campaign.daily_budget, 20);
});

test('asking for an account resumes planning, not approval of a write', async () => {
    const { context, requests, nodes, node } = environment();
    context.showConfirm({ type: 'ask_account', platform: 'google-ads' }, { ...original(), account_id: null });
    nodes.confirmAccountInput = node();
    nodes.confirmAccountInput.value = '9055507554';
    await context.executeConfirm();
    assert.equal(requests[0].account_id, '9055507554');
    assert.equal(requests[0].confirmed, false);
    assert.equal(requests[0].confirmation_payload, null);
    assert.equal(requests[0].platform_params['google-ads'].google_create_campaign.daily_budget, 20);
});

test('selecting an account continues the existing request without repeating its prompt or attachments', async () => {
    const { context, requests, displayed } = environment();
    const previousPrompt = '查询 Meta campaign 并导出';
    context.renderStreamResult = () => {};
    context.streamChatRequest = async params => {
        requests.push(params);
        return { session_id: 'session', status: 'succeeded', content: '查询完成', results: [] };
    };

    await context.continueWithSelectedAccount('meta-account-1', {
        user_input: previousPrompt,
        session_id: 'session',
        media_ids: ['already-submitted-image'],
        execution_mode: 'live',
    });

    assert.equal(requests.length, 1);
    assert.equal(requests[0].user_input, '使用账户 meta-account-1 继续');
    assert.equal(requests[0].account_id, 'meta-account-1');
    assert.equal(requests[0].session_id, 'session');
    assert.equal(requests[0].execution_mode, 'live');
    assert.equal('media_ids' in requests[0], false);
    assert.equal(displayed[0][0], '使用账户 meta-account-1 继续');
    assert.doesNotMatch(displayed[0][0], new RegExp(previousPrompt));
});

test('missing parameters merge only into the indicated namespace while preserving the draft', async () => {
    const { context, requests, nodes, node } = environment();
    context.showConfirm({ type: 'ask_params', platform: 'google-ads', missing: ['campaign_id'] }, original());
    nodes.confirmParamInput = node();
    nodes.confirmParamInput.value = 'campaign_id=123';
    await context.executeConfirm();
    assert.equal(requests[0].confirmed, false);
    assert.equal(requests[0].platform_params['google-ads'].campaign_id, '123');
    assert.equal(requests[0].platform_params.example.preserved, true);
});

for (const stale of ['<redacted>', '', 'expired']) {
    test(`historical ${stale || 'missing'} approval regenerates a plan without authorizing a write`, async () => {
        const { context, requests } = environment();
        const payload = approval();
        payload.confirmation_token = stale === 'expired' ? 'old-approval' : stale;
        if (stale === 'expired') payload.expires_at = '2020-01-01T00:00:00Z';
        const request = original();
        request.platform_params['google-ads'].google_create_campaign.selection_tokens = { asset: '<redacted>' };
        context.showConfirm(payload, request);
        await context.executeConfirm();
        assert.equal(requests[0].confirmed, false);
        assert.equal(requests[0].confirmation_payload, null);
        assert.equal(requests[0].platform_params['google-ads'].google_create_campaign.selection_tokens, undefined);
    });
}

test('a confirmation from another conversation cannot be submitted in the current one', async () => {
    const { context, requests, displayed } = environment();
    context.showConfirm(approval(), original());
    context.sessionId = 'other-session';
    await context.executeConfirm();
    assert.equal(requests.length, 0);
    assert.match(displayed.at(-1)[0], /对话/);
});

test('a rendered creation draft is carried into the next message in the same session', () => {
    const { context } = environment();
    const draft = {
        type: 'ad_creation_form',
        account_id: 'tiktok-test-account',
        blueprint_id: 'tiktok.product-sales',
        blueprint_version: '1.0.0',
        template_id: 'tiktok.test.product-sales',
        platform_params: {
            tiktok: { campaign_name: 'Paused test campaign', daily_budget: 20 },
        },
    };

    context.renderStreamResult({
        session_id: 'session',
        status: 'awaiting_input',
        content: '已加载模板草稿。',
        results: [],
        ui: { cards: [draft] },
    }, { session_id: 'session' });

    const queued = context.captureChatMessage('创建吧', []);
    assert.equal(queued.requestParams.account_id, 'tiktok-test-account');
    assert.equal(queued.requestParams.creation_blueprint_id, 'tiktok.product-sales');
    assert.equal(queued.requestParams.creation_template_id, 'tiktok.test.product-sales');
    assert.deepEqual(
        JSON.parse(JSON.stringify(queued.requestParams.platform_params)),
        draft.platform_params,
    );
});

test('a reply matching the previous creation prompt keeps the template context', () => {
    const { context } = environment();
    context.pendingBlueprintRequest = {
        session_id: 'session',
        account_id: 'tiktok-test-account',
        creation_blueprint_id: 'tiktok.product_sales_video',
        creation_blueprint_version: '2.3.0',
        creation_template_id: 'tiktok.test.sales',
        platform_params: { tiktok: { campaign_name: 'Paused test campaign' } },
    };
    context.pendingBlueprintContinuation = {
        session_id: 'session',
        assistant_prompt: '时间可以使用建议值，请回复“使用建议时间”，也可以填写具体时间。',
        fields: [{ label: '开始时间', path: 'ad_group.schedule_start_time', required: true }],
        reply_options: ['使用建议时间'],
    };

    const queued = context.captureChatMessage('使用建议时间', []);

    assert.equal(queued.requestParams.creation_blueprint_id, 'tiktok.product_sales_video');
    assert.equal(queued.requestParams.creation_template_id, 'tiktok.test.sales');
    assert.deepEqual(
        JSON.parse(JSON.stringify(queued.requestParams.platform_params)),
        { tiktok: { campaign_name: 'Paused test campaign' } },
    );
    assert.equal('pendingBlueprintContinuation' in queued.requestParams, false);
});

test('editing a known field without submitting keeps its template context', () => {
    const { context } = environment();
    context.pendingBlueprintRequest = {
        session_id: 'session', creation_template_id: 'selected-template',
    };
    context.pendingBlueprintContinuation = {
        session_id: 'session', fields: [{ label: 'Campaign 名称', path: 'campaign.name' }],
    };
    const queued = context.captureChatMessage(
        'Campaign 名称：demo，总预算50，先补充草稿，不要提交创建。', [],
    );
    assert.equal(queued.requestParams.creation_template_id, 'selected-template');
});

test('a chat continuation keeps the draft attached to the signed confirmation request', async () => {
    const { context, requests } = environment();
    const draft = {
        type: 'ad_creation_form',
        account_id: 'tiktok-test-account',
        blueprint_id: 'tiktok.product-sales',
        blueprint_version: '1.0.0',
        template_id: 'tiktok.test.product-sales',
        platform_params: {
            tiktok: { campaign_name: 'Paused test campaign', daily_budget: 20 },
        },
    };
    context.renderStreamResult({
        session_id: 'session',
        status: 'awaiting_input',
        content: '已加载模板草稿。',
        results: [],
        ui: { cards: [draft] },
    }, { session_id: 'session' });

    const continuation = context.captureChatMessage('创建吧', []);
    context.showConfirm(approval({
        account_id: 'tiktok-test-account',
        platform: 'tiktok',
        tools: ['tiktok_create_campaign', 'tiktok_create_ad_group'],
    }), continuation.requestParams);
    await context.executeConfirm();

    assert.equal(requests.length, 1);
    assert.equal(requests[0].account_id, 'tiktok-test-account');
    assert.equal(requests[0].creation_template_id, 'tiktok.test.product-sales');
    assert.deepEqual(
        JSON.parse(JSON.stringify(requests[0].platform_params)),
        draft.platform_params,
    );
    assert.equal(requests[0].confirmed, true);
    assert.equal(requests[0].confirmation_payload.confirmation_token, 'one-time-approval');
});

test('a creation draft from another conversation is not copied into a new message', () => {
    const { context } = environment();
    context.pendingBlueprintRequest = {
        session_id: 'old-session',
        account_id: 'old-account',
        creation_template_id: 'old-template',
        platform_params: { tiktok: { campaign_name: 'old draft' } },
    };

    const queued = context.captureChatMessage('查询 Google campaign', []);

    assert.equal('account_id' in queued.requestParams, false);
    assert.equal('creation_template_id' in queued.requestParams, false);
    assert.equal('platform_params' in queued.requestParams, false);
    assert.equal(context.pendingBlueprintRequest, null);
    assert.equal(context.pendingBlueprintContinuation, null);
});

test('an unrelated query in the same conversation does not inherit a creation draft', () => {
    const { context } = environment();
    context.pendingBlueprintRequest = {
        session_id: 'session',
        account_id: 'tiktok-test-account',
        creation_template_id: 'tiktok.test.product-sales',
        platform_params: { tiktok: { campaign_name: 'draft' } },
    };

    const queued = context.captureChatMessage('查询 Google campaign 列表', []);

    assert.equal('account_id' in queued.requestParams, false);
    assert.equal('creation_template_id' in queued.requestParams, false);
    assert.equal('platform_params' in queued.requestParams, false);
});

test('sending a creation answer does not clear the draft before its response arrives', async () => {
    const { context, nodes } = environment();
    context.pendingBlueprintRequest = {
        session_id: 'session',
        creation_blueprint_id: 'tiktok.product_sales_video',
        creation_template_id: 'tiktok.test.sales',
        platform_params: { tiktok: { daily_budget: 20 } },
    };
    context.pendingBlueprintContinuation = {
        session_id: 'session',
        assistant_prompt: '回复“使用建议时间”继续。',
        reply_options: ['使用建议时间'],
        fields: [],
    };
    context.pendingChatAttachments = [];
    context.clearPendingChatMedia = () => {};
    context.executeChatMessage = () => {};
    nodes.userInput.value = '使用建议时间';
    nodes.userInput.style = {};

    await context.sendMessage();

    assert.equal(context.pendingBlueprintRequest.creation_template_id, 'tiktok.test.sales');
    assert.equal(context.pendingBlueprintContinuation.session_id, 'session');
});

test('a completed non-interactive turn clears stale creation context', () => {
    const { context } = environment();
    context.pendingBlueprintRequest = {
        session_id: 'session',
        creation_blueprint_id: 'tiktok.product_sales_video',
        creation_template_id: 'tiktok.test.sales',
    };
    context.pendingBlueprintContinuation = {
        session_id: 'session',
        reply_options: ['使用建议时间'],
        fields: [],
    };

    context.renderStreamResult({
        session_id: 'session',
        status: 'succeeded',
        content: '查询完成。',
        results: [],
    }, { session_id: 'session' });

    assert.equal(context.pendingBlueprintRequest, null);
    assert.equal(context.pendingBlueprintContinuation, null);
});

test('a live response launcher keeps the usable approval rather than its redacted history copy', () => {
    const { context, displayed } = environment();
    const payload = approval();
    context.renderStreamResult({
        session_id: 'session', status: 'awaiting_confirmation',
        needs_confirmation: true, confirmation_payload: payload,
        ui: { confirmation: { payload: { ...payload, confirmation_token: '<redacted>' }, original_request: original() } },
        results: [],
    }, original());
    assert.equal(displayed[0][6].confirmation.payload.confirmation_token, 'one-time-approval');
    assert.equal(displayed[0][6].confirmation.original_request.account_id, '9055507554');
});

test('finishing a confirmation does not leave an empty confirmation workbench visible', async () => {
    const { context, nodes } = environment();
    context.showConfirm(approval(), original());
    await context.executeConfirm();
    assert.equal(nodes['confirmation-workbench-host'].hidden, true);
});

test('the renderer can show a newly returned confirmation while the request is still finishing', () => {
    const { context, nodes } = environment();
    context.isSending = true;
    context.renderStreamResult({
        session_id: 'session', status: 'awaiting_confirmation',
        needs_confirmation: true, confirmation_payload: approval(), results: [],
    }, original());
    assert.equal(context.pendingRequest.payload.confirmation_token, 'one-time-approval');
    assert.equal(nodes['confirmation-workbench-host'].hidden, false);
});

test('an empty account entry can be corrected without reopening a dead confirmation', async () => {
    const { context, requests, nodes, node } = environment();
    context.showConfirm({ type: 'ask_account', platform: 'google-ads' }, { ...original(), account_id: null });
    nodes.confirmAccountInput = node();
    await context.executeConfirm();
    assert.equal(requests.length, 0);
    assert.ok(context.pendingRequest);
    nodes.confirmAccountInput.value = '9055507554';
    await context.executeConfirm();
    assert.equal(requests.length, 1);
    assert.equal(requests[0].confirmed, false);
});
