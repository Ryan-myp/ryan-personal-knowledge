const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function environment(mode = 'dry_run', available = false) {
    const messages = [];
    const context = {
        workspaceMode: { mode, liveAvailable: available, liveReason: 'live disabled', loading: false, saving: false },
        creationCardState: new Map(),
        pendingCreationReview: null,
        pendingRequest: null,
        isSending: false,
        sessionId: 'mode-session',
        document: {
            getElementById: id => id === 'userInput' ? { focus: () => {} } : null,
            querySelector: () => null, addEventListener: () => {},
        },
        addMessage: text => messages.push(text),
        CSS: { escape: value => value },
    };
    for (const file of ['chat-creation.js', 'chat-workspace.js']) {
        vm.runInNewContext(fs.readFileSync(path.resolve(
            __dirname, '../../../deployments/advertising/static/js', file,
        ), 'utf8'), context, { filename: file });
    }
    const refresh = context.refreshWorkspaceMode;
    context.initializeTheme = () => {};
    context.resetExecutionTrace = () => {};
    context.refreshWorkspaceMode = () => {};
    context.refreshConversationHistory = async () => {};
    const messagesPath = path.resolve(__dirname, '../../../deployments/advertising/static/js/chat-messages.js');
    vm.runInNewContext(fs.readFileSync(messagesPath, 'utf8'), context, { filename: messagesPath });
    context.refreshWorkspaceMode = refresh;
    context.addMessage = text => messages.push(text);
    return { context, messages };
}

const readyCard = () => ({
    id: 'draft', account_id: '9055507554', ready: true,
    fields: [], missing_fields: [], invalid_fields: [],
});

test('dry-run remains usable when deployment has no live capability', () => {
    const { context } = environment();
    assert.equal(context.creationCardCanSubmit(readyCard()), true);
});

test('stale live selection cannot open a confirmation when live is disabled', () => {
    const { context, messages } = environment('live', false);
    assert.equal(context.creationCardCanSubmit(readyCard()), false);
    context.showCreationReview(readyCard());
    assert.equal(context.pendingCreationReview, null);
    assert.match(messages[0], /live disabled/);
});

test('a pending mode change prevents creation submission', () => {
    const { context } = environment('live', true);
    context.workspaceMode.saving = true;
    assert.equal(context.creationCardCanSubmit(readyCard()), false);
    context.workspaceMode.saving = false;
    assert.equal(context.creationCardCanSubmit(readyCard()), true);
});

test('the visible confirmation button is locked during a mode change', () => {
    const { context } = environment('live', true);
    const button = { disabled: false, title: '' };
    context.pendingCreationReview = { card: readyCard(), mode: 'live' };
    context.document.getElementById = id => id === 'confirmCard' ? {
        querySelector: () => button,
    } : null;
    context.workspaceMode.saving = true;
    context.refreshCreationSubmissionAvailability();
    assert.equal(button.disabled, true);
    context.workspaceMode.saving = false;
    context.refreshCreationSubmissionAvailability();
    assert.equal(button.disabled, false);
});

test('a failed mode switch restores the last server-confirmed mode', async () => {
    const { context } = environment();
    const select = { value: 'live', disabled: false };
    const status = {};
    context.document.getElementById = id => (
        id === 'executionModeSelect' ? select : id === 'workspaceModeStatus' ? status : null
    );
    context.authenticatedFetch = async () => ({
        ok: false, status: 409, text: async () => JSON.stringify({ detail: 'live not configured' }),
    });
    await context.applyWorkspaceMode();
    assert.equal(context.workspaceMode.mode, 'dry_run');
    assert.equal(select.value, 'dry_run');
    assert.match(status.textContent, /live not configured/);
    assert.equal(context.workspaceMode.saving, false);
});

test('changing mode invalidates an old local confirmation but keeps the draft', () => {
    const { context, messages } = environment('dry_run', true);
    const card = readyCard();
    context.pendingCreationReview = { card, mode: 'live' };
    context.confirmCreationSubmission();
    assert.equal(context.pendingCreationReview, null);
    assert.equal(card.account_id, '9055507554');
    assert.match(messages[0], /模式/);
});

test('a signed confirmation cannot silently change execution mode', async () => {
    const { context, messages } = environment('dry_run', true);
    context.pendingRequest = {
        payload: { type: 'confirm_write_plan' }, mode: 'live',
        originalRequest: { user_input: 'Create paused test campaign', session_id: 'mode-session' },
    };
    let calls = 0;
    context.addLoading = () => {};
    context.removeLoading = () => {};
    context.startExecutionTrace = () => {};
    context.streamChatRequest = async () => { calls += 1; return {}; };
    context.renderStreamResult = () => {};
    context.refreshConversationHistory = async () => {};
    context.markChatRequestFailure = error => error.message;
    await context.executeConfirm();
    assert.equal(calls, 0);
    assert.match(messages[0], /模式/);
});
