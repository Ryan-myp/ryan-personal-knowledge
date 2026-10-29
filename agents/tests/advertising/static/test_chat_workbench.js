const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function element() {
    const handlers = {};
    return {
        handlers,
        hidden: false,
        textContent: '',
        innerHTML: '',
        className: '',
        dataset: {},
        children: [],
        get childElementCount() { return this.children.length; },
        attributes: {},
        classList: {
            add() {},
            remove() {},
            toggle() {},
        },
        appendChild(child) {
            this.children.push(child);
            return child;
        },
        focus() {},
        replaceChildren(...children) {
            this.children = children;
        },
        querySelector(selector) {
            return selector === 'button' ? this.button : null;
        },
        setAttribute(name, value) {
            this.attributes[name] = value;
        },
        addEventListener(name, handler) {
            handlers[name] = handler;
        },
    };
}

function environment() {
    const elements = new Map();
    const rightPanel = element();
    const context = {
        CSS: { escape: value => String(value) },
        creationCardState: new Map(),
        sessionId: null,
        selectedConversationId: null,
        workspaceMode: { mode: 'dry_run' },
        pendingCreationReview: null,
        pendingRequest: null,
        pendingBlueprintRequest: null,
        pendingBlueprintContinuation: null,
        initializeTheme() {},
        resetExecutionTrace() {},
        refreshWorkspaceMode() {},
        refreshConversationHistory() {},
        document: {
            addEventListener() {},
            body: { classList: element().classList },
            getElementById(id) {
                if (!elements.has(id)) elements.set(id, element());
                return elements.get(id);
            },
            querySelector(selector) {
                return selector === '.right-panel' ? rightPanel : null;
            },
            createElement() {
                const node = element();
                node.button = element();
                return node;
            },
            createDocumentFragment: element,
        },
        escapeHtml: value => String(value ?? ''),
        creationFieldValue: field => field.value,
        renderCreationCard: () => element(),
        addMessage() {},
        showConfirm() {},
    };
    for (const filename of [
        'chat-workbench.js',
        'chat-creation.js',
        'chat-requests.js',
    ]) {
        const source = path.resolve(
            __dirname,
            '../../../deployments/advertising/static/js',
            filename,
        );
        vm.runInNewContext(fs.readFileSync(source, 'utf8'), context, {
            filename: source,
        });
    }
    context.renderCreationCard = () => element();
    context.addMessage = () => {};
    return { context, elements };
}

const card = id => ({ id, title: `Draft ${id}` });
const workbenchSize = context => vm.runInNewContext(
    'workbenchState.cards.size',
    context,
);

test('opening traces without artifacts does not expose an empty creation tab', () => {
    const { context, elements } = environment();
    context.openTraceWorkbench();
    assert.equal(elements.get('workbenchTabbar').hidden, true);
    assert.equal(elements.get('workbench-tab-creation').hidden, true);
    context.setWorkbenchView('creation');
    assert.equal(elements.get('creation-workbench-view').hidden, true);
    assert.equal(elements.get('trace-workbench-view').hidden, false);
});

test('creation navigation follows the current draft and disappears when cleared', () => {
    const { context, elements } = environment();
    context.renderCreationCardInWorkbench(card('current'));
    assert.equal(elements.get('workbenchTabbar').hidden, false);
    assert.equal(elements.get('workbenchContextLabel').textContent, '广告创建');
    context.openTraceWorkbench();
    assert.equal(elements.get('workbench-tab-creation').hidden, false);
    context.clearCreationWorkbenchDraft();
    assert.equal(elements.get('workbenchTabbar').hidden, true);
    assert.equal(elements.get('creation-workbench-view').hidden, true);
});

test('generic confirmations have a neutral context and clear without leaving a creation tab', () => {
    const { context, elements } = environment();
    context.document.getElementById('confirmation-workbench-host').appendChild(element());
    context.openConfirmationWorkbench();
    assert.equal(elements.get('workbenchContextLabel').textContent, '操作确认');
    assert.equal(elements.get('workbenchCreationTitle').textContent, '确认与补充');
    assert.equal(elements.get('workbenchCreationSubtitle').textContent.includes('预算'), false);
    context.closeCreationWorkbench();
    context.openTraceWorkbench();
    context.setWorkbenchView('creation');
    assert.equal(elements.get('confirmation-workbench-host').hidden, false);
    context.clearWorkbenchConfirmation();
    assert.equal(elements.get('workbenchTabbar').hidden, true);
    assert.equal(elements.get('trace-workbench-view').hidden, false);
});

test('an empty confirmation cannot open an artifact tab and reset removes old context', () => {
    const { context, elements } = environment();
    context.openConfirmationWorkbench();
    assert.equal(elements.get('workbench-tab-creation').hidden, true);
    context.renderCreationCardInWorkbench(card('old'));
    context.resetCreationWorkbench();
    context.openTraceWorkbench();
    assert.equal(elements.get('workbench-tab-creation').hidden, true);
    assert.equal(elements.get('workbenchTabbar').hidden, true);
});

test('history cards stay in the transcript and only enter the workbench when reopened', () => {
    const { context, elements } = environment();
    const rendered = context.renderUiCards({ cards: [card('old-draft')] }, {
        openWorkbench: false,
    });

    assert.equal(rendered.children.length, 1);
    assert.equal(workbenchSize(context), 0);
    assert.equal(elements.get('workbenchCreationCount').hidden, true);
    assert.equal(context.creationCardState.has('old-draft'), true);

    rendered.children[0].button.handlers.click();

    assert.equal(workbenchSize(context), 1);
    assert.equal(elements.get('workbenchCreationCount').textContent, '1 张');
    assert.equal(elements.get('workbenchCreationCount').hidden, false);
});

test('reopening a historical template restores its editable context without approval', () => {
    const { context } = environment();
    context.sessionId = 'current-session';
    context.creationCardState.set('historical', {
        id: 'historical', type: 'ad_creation_form', provider: 'example',
        account_id: 'test-account', blueprint_id: 'example.complete',
        blueprint_version: '1.0.0', template_id: 'saved-template', ready: false,
        fields: [{ path: 'campaign.name', provider_field: 'name', tool: 'example_create', value: 'draft' }],
    });
    context.reopenCreationCard('historical');
    assert.equal(context.pendingBlueprintRequest.creation_template_id, 'saved-template');
    assert.equal(context.pendingBlueprintRequest.session_id, 'current-session');
    assert.equal(context.pendingBlueprintRequest.confirmed, undefined);
    assert.equal(context.pendingBlueprintRequest.confirmation_payload, undefined);
});

test('a completed non-creation turn clears the stale creation workspace', () => {
    const { context, elements } = environment();
    context.renderCreationCardInWorkbench(card('stale-draft'));
    context.renderCreationCardInWorkbench(card('stale-draft-2'));
    assert.equal(elements.get('workbenchCreationCount').textContent, '2 张');
    context.renderStreamResult({
        session_id: 'session-1',
        status: 'succeeded',
        content: '查询结果已返回。',
        results: [],
    }, {});

    assert.equal(workbenchSize(context), 0);
    assert.equal(elements.get('workbenchCreationCount').hidden, true);
    assert.equal(elements.get('creation-workbench-host').hidden, true);
    assert.equal(elements.get('trace-workbench-view').hidden, false);

    context.renderStreamResult({
        session_id: 'session-1',
        status: 'succeeded',
        content: '第二轮查询结果已返回。',
        results: [],
    }, {});
    assert.equal(workbenchSize(context), 0);
    assert.equal(elements.get('workbenchCreationCount').hidden, true);
});

test('failed and awaiting-input turns preserve the current creation draft', () => {
    const { context, elements } = environment();
    context.renderCreationCardInWorkbench(card('active-draft'));

    context.renderStreamResult({
        session_id: 'session-1',
        status: 'failed',
        content: '创建失败。',
        results: [],
    }, {});
    assert.equal(workbenchSize(context), 1);

    context.renderStreamResult({
        session_id: 'session-1',
        status: 'awaiting_input',
        content: '请选择一个账户。',
        ui: { account_selection: { prompt: '请选择账户' } },
        results: [],
    }, {});
    assert.equal(workbenchSize(context), 1);
    assert.equal(elements.get('workbenchCreationCount').hidden, false);
});

test('an outstanding confirmation protects the creation workbench', () => {
    const { context } = environment();
    context.renderCreationCardInWorkbench(card('confirmed-draft'));
    context.pendingRequest = { payload: { type: 'confirm_write_plan' } };

    context.renderStreamResult({
        session_id: 'session-1',
        status: 'succeeded',
        content: '查询已完成。',
        results: [],
    }, {});

    assert.equal(workbenchSize(context), 1);
});
