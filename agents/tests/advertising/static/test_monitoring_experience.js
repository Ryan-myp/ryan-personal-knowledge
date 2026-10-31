const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function environment(apiFetch = async () => ({})) {
    const elements = new Map();
    const context = {
        console, apiFetch,
        document: { getElementById(id) {
            if (!elements.has(id)) elements.set(id, {
                innerHTML: '', textContent: '', hidden: true, dataset: {},
            });
            return elements.get(id);
        } },
        escapeHtml: value => String(value).replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;')
            .replaceAll("'", '&#39;'),
    };
    vm.createContext(context);
    vm.runInContext(fs.readFileSync(path.resolve(
        __dirname, '../../../deployments/advertising/static/js/chat-workspace.js',
    ), 'utf8'), context);
    return {context, elements};
}

test('experience table distinguishes absent samples from zero and escapes recovery fields', () => {
    const {context, elements} = environment();
    context.renderMonitoringExperience({
        first_text_ms: {p50: 0, p95: 1200, samples: 1},
        total_ms: {p50: null, p95: null, samples: 0},
    }, {total: 1, items: [{kind: 'run', id: '<script>', updated_at: '',
        reason: '<img>', reason_code: 'stale_execution_run'}]});
    const experience = elements.get('monitoringExperienceRows').innerHTML;
    assert.match(experience, /0 ms/);
    assert.match(experience, /1.2 s/);
    assert.match(experience, /—/);
    const recovery = elements.get('monitoringRecoveryRows').innerHTML;
    assert.match(recovery, /&lt;script&gt;/);
    assert.match(recovery, /&lt;img&gt;/);
    assert.doesNotMatch(recovery, /<script>|<img>/);
});

test('recovery detail is read only and retains a visible error on failure', async () => {
    const calls = [];
    const {context, elements} = environment(async endpoint => {
        calls.push(endpoint);
        throw new Error('读取失败');
    });
    await context.inspectMonitoringRecovery('run', 'a/b');
    assert.deepEqual(calls, ['/runs/a%2Fb/events?limit=100']);
    assert.match(elements.get('monitoringRecoveryDetail').textContent, /读取失败/);
    assert.equal(elements.get('monitoringRecoveryDetail').hidden, false);
});

test('workflow recovery is listed and opens its scoped read-only detail', async () => {
    const calls = [];
    const {context, elements} = environment(async endpoint => {
        calls.push(endpoint);
        return {workflow_id: 'w/1', status: 'recovery_required'};
    });
    context.renderMonitoringExperience({}, {
        total: 1, items: [{kind: 'workflow', id: 'w/1', reason: '需核验'}],
    });
    assert.match(elements.get('monitoringRecoveryRows').innerHTML, /工作流/);
    await context.inspectMonitoringRecovery('workflow', 'w/1');
    assert.deepEqual(calls, ['/workflows/w%2F1']);
    assert.match(elements.get('monitoringRecoveryDetail').textContent, /recovery_required/);
});

test('late recovery detail cannot replace a newer selection', async () => {
    let resolveFirst;
    const pending = new Promise(resolve => {resolveFirst = resolve;});
    let count = 0;
    const {context, elements} = environment(async () => ++count === 1
        ? pending : {status: 'recovery_required', task_id: 'new'});
    const first = context.inspectMonitoringRecovery('run', 'old');
    await context.inspectMonitoringRecovery('task', 'new');
    resolveFirst({run_id: 'old'});
    await first;
    assert.match(elements.get('monitoringRecoveryDetail').textContent, /new/);
    assert.doesNotMatch(elements.get('monitoringRecoveryDetail').textContent, /old/);
});
