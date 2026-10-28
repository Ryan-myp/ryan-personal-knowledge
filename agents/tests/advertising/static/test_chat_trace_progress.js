const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function element() {
    return {
        innerHTML: '',
        textContent: '',
        children: [],
        classList: { add() {}, remove() {}, toggle() {} },
        style: { setProperty() {}, removeProperty() {} },
        replaceChildren() { this.children = []; },
        appendChild(child) { this.children.push(child); },
        querySelector() { return null; },
        setAttribute() {},
    };
}

function environment() {
    const elements = new Map();
    const context = {
        document: {
            getElementById(id) {
                if (!elements.has(id)) elements.set(id, element());
                return elements.get(id);
            },
            createElement() {
                return {
                    ...element(),
                    addEventListener() {},
                    offsetTop: 0,
                    offsetHeight: 0,
                };
            },
            querySelector() { return null; },
            body: { classList: { add() {}, remove() {}, toggle() {} } },
        },
        escapeHtml: value => String(value ?? ''),
        traceFilter: { platform: 'all', status: 'all', kind: 'all' },
        setWorkbenchView() {},
        closeAgentWorkbench() {},
    };
    for (const filename of [
        'chat-queue.js', 'chat-state.js', 'chat-knowledge.js', 'chat-trace.js',
    ]) {
        const source = path.resolve(
            __dirname, '../../../deployments/advertising/static/js', filename,
        );
        vm.runInNewContext(fs.readFileSync(source, 'utf8'), context, { filename });
    }
    return { context, elements };
}

test('model lifecycle events become safe, readable trace stages', () => {
    const { context, elements } = environment();

    context.applyExecutionEvent({
        type: 'model_start',
        model_call_id: 'model-call-1',
        provider: 'configured-model',
        attempt: 1,
        tool_count: 2,
        tool_choice_required: false,
    });
    const trace = vm.runInNewContext('traceState', context);
    const stage = trace.nodes.find(node => node.id.startsWith('stage:model:'));
    assert.ok(stage);
    assert.equal(stage.title, '模型分析');
    assert.equal(stage.state, 'running');
    assert.match(stage.subtitle, /本次模型请求已提供 2 个匹配 Tool/);
    assert.equal(elements.get('traceSubtitle').textContent.includes('模型分析'), true);

    context.applyExecutionEvent({
        type: 'progress',
        safe_metadata: { elapsed_seconds: 15 },
    });
    assert.match(elements.get('loadingStatus').textContent, /模型分析/);
    assert.match(elements.get('loadingStatus').textContent, /15 秒/);

    context.applyExecutionEvent({
        type: 'model_end',
        model_call_id: 'model-call-1',
        provider: 'configured-model',
        attempt: 1,
        tool_call_count: 2,
    });
    assert.equal(
        trace.nodes.find(node => node.id === stage.id).state,
        'succeeded',
    );
    assert.match(
        trace.nodes.find(node => node.id === stage.id).subtitle,
        /2 个工具/,
    );
    assert.match(elements.get('loadingStatus').textContent, /2 个工具/);
    assert.equal(
        context.applyExecutionEvent({
            type: 'model_delta', delta: 'private intermediate model text',
        }),
        null,
    );
    assert.equal(
        JSON.stringify(trace.events).includes('private intermediate model text'),
        false,
    );

    context.applyExecutionEvent({
        type: 'model_start',
        model_call_id: 'model-call-2',
        provider: 'configured-model',
        attempt: 1,
    });
    assert.equal(
        trace.nodes.filter(node => node.title === '模型分析').length,
        2,
    );
});

test('schedule list uses one global runs request instead of sequential details', async () => {
    const calls = [];
    const elements = new Map();
    const context = {
        document: {
            getElementById(id) {
                if (!elements.has(id)) {
                    elements.set(id, {
                        textContent: '',
                        innerHTML: '',
                        classList: { contains: () => false },
                    });
                }
                return elements.get(id);
            },
        },
        window: { setTimeout, clearTimeout, confirm: () => true, alert() {} },
        escapeHtml: value => String(value ?? ''),
        apiFetch: async endpoint => {
            calls.push(endpoint);
            if (endpoint.startsWith('/schedules?')) {
                return { schedules: [{
                    schedule_id: 'schedule-1', name: 'Daily', status: 'active',
                }] };
            }
            if (endpoint === '/monitoring/overview') return { schedules: {} };
            if (endpoint.startsWith('/schedule-runs?')) return { runs: [] };
            throw new Error(`unexpected request: ${endpoint}`);
        },
    };
    const source = path.resolve(
        __dirname, '../../../deployments/advertising/static/js/chat-workspace.js',
    );
    vm.runInNewContext(fs.readFileSync(source, 'utf8'), context, { filename: source });

    await context.loadSchedules();

    assert.deepEqual(calls, [
        '/schedules?limit=100',
        '/monitoring/overview',
        '/schedule-runs?limit=100',
    ]);
    assert.equal(calls.some(endpoint => /^\/schedules\/[^?]+$/.test(endpoint)), false);
});

test('running a schedule refreshes its visible queued run state', async () => {
    const calls = [];
    const elements = new Map();
    const context = {
        document: {
            getElementById(id) {
                if (!elements.has(id)) {
                    elements.set(id, {
                        textContent: '',
                        innerHTML: '',
                        classList: { contains: () => id === 'scheduleOverlay' },
                    });
                }
                return elements.get(id);
            },
        },
        window: {
            setTimeout: () => 1,
            clearTimeout() {},
            confirm: () => true,
            alert(message) { throw new Error(message); },
        },
        escapeHtml: value => String(value ?? ''),
        apiFetch: async (endpoint, options = {}) => {
            calls.push([endpoint, options]);
            if (endpoint === '/schedules/schedule-1/run-now') {
                return {
                    task: { task_id: 'task-1', status: 'queued' },
                    run: {
                        schedule_id: 'schedule-1',
                        task_id: 'task-1',
                        status: 'queued',
                    },
                };
            }
            if (endpoint === '/schedules?limit=100') {
                return {
                    schedules: [{
                        schedule_id: 'schedule-1',
                        name: 'Daily report',
                        status: 'active',
                    }],
                };
            }
            if (endpoint === '/monitoring/overview') {
                return { schedules: { runs_by_status: { queued: 1 } } };
            }
            if (endpoint === '/schedule-runs?limit=100') {
                return {
                    runs: [{
                        schedule_id: 'schedule-1',
                        task_id: 'task-1',
                        status: 'queued',
                        scheduled_for: '2026-10-18T10:00:00+00:00',
                    }],
                };
            }
            throw new Error(`unexpected request: ${endpoint}`);
        },
    };
    const source = path.resolve(
        __dirname, '../../../deployments/advertising/static/js/chat-workspace.js',
    );
    vm.runInNewContext(fs.readFileSync(source, 'utf8'), context, { filename: source });
    const button = {
        textContent: '立即执行',
        disabled: false,
        isConnected: false,
        setAttribute() {},
        removeAttribute() {},
    };

    await context.scheduleAction('schedule-1', 'run-now', button);

    assert.equal(calls[0][0], '/schedules/schedule-1/run-now');
    assert.equal(calls[0][1].method, 'POST');
    assert.match(elements.get('scheduleList').innerHTML, /最近执行/);
    assert.match(elements.get('scheduleList').innerHTML, /排队中/);
    assert.match(elements.get('scheduleList').innerHTML, /disabled aria-busy="true"/);
});

test('schedule editor loads an existing schedule and saves it through scoped PATCH', async () => {
    const calls = [];
    const elements = new Map();
    const context = {
        document: {
            getElementById(id) {
                if (!elements.has(id)) {
                    elements.set(id, {
                        value: '',
                        textContent: '',
                        innerHTML: '',
                        disabled: false,
                        classList: {
                            add() {},
                            remove() {},
                            contains: () => false,
                        },
                        setAttribute() {},
                        focus() {},
                    });
                }
                return elements.get(id);
            },
        },
        window: {
            setTimeout,
            clearTimeout,
            confirm: () => true,
            alert(message) { throw new Error(message); },
        },
        escapeHtml: value => String(value ?? ''),
        monitoringNumber: value => String(value ?? 0),
        scheduleStatusLabel: value => String(value || ''),
        apiFetch: async (endpoint, options = {}) => {
            calls.push([endpoint, options]);
            if (endpoint === '/schedules/schedule-1') {
                return { schedule: { schedule_id: 'schedule-1' } };
            }
            if (endpoint === '/schedules?limit=100') {
                return { schedules: [] };
            }
            if (endpoint === '/monitoring/overview') return { schedules: {} };
            if (endpoint === '/schedule-runs?limit=100') return { runs: [] };
            throw new Error(`unexpected request: ${endpoint}`);
        },
    };
    const source = path.resolve(
        __dirname, '../../../deployments/advertising/static/js/chat-workspace.js',
    );
    vm.runInNewContext(fs.readFileSync(source, 'utf8'), context, { filename: source });

    context.renderSchedules({
        schedules: [{
            schedule_id: 'schedule-1',
            name: 'Daily report',
            prompt: 'Summarize campaigns',
            cron_expression: '0 9 * * *',
            timezone: 'Asia/Shanghai',
            status: 'active',
        }],
        runs: [],
        metrics: {},
    });
    context.editSchedule('schedule-1');
    assert.equal(elements.get('scheduleEditName').value, 'Daily report');
    assert.equal(elements.get('scheduleEditOverlay').classList.contains('active'), false);
    elements.get('scheduleEditName').value = 'Weekly report';
    elements.get('scheduleEditPrompt').value = 'Summarize campaign results';

    await context.saveScheduleEdit({ preventDefault() {} });

    assert.equal(calls[0][0], '/schedules/schedule-1');
    assert.equal(calls[0][1].method, 'PATCH');
    assert.deepEqual(JSON.parse(calls[0][1].body), {
        name: 'Weekly report',
        prompt: 'Summarize campaign results',
        cron_expression: '0 9 * * *',
        timezone: 'Asia/Shanghai',
    });
    assert.equal(elements.get('scheduleEditStatus').textContent, '');
});
