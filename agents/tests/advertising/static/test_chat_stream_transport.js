const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function environment(fetch) {
    const events = [];
    const context = {fetch, Headers, AbortController, TextDecoder, Uint8Array, setTimeout, clearTimeout,
        document: {getElementById: () => null},
        activeDurableRunId: '', applyExecutionEvent: event => {events.push(event); return event;},
        markTraceConnectionUnknown: () => events.push('unknown'),
        markTraceFailed: () => events.push('failed')};
    vm.createContext(context);
    vm.runInContext(fs.readFileSync(path.resolve(__dirname,
        '../../../deployments/advertising/static/js/chat-requests.js'), 'utf8'), context);
    return {context, events};
}

function streamResponse(parts, {open = false} = {}) {
    let cancelled = false;
    const body = new ReadableStream({
        start(controller) {
            parts.forEach(part => controller.enqueue(typeof part === 'string' ? new TextEncoder().encode(part) : part));
            if (!open) controller.close();
        },
        cancel() {cancelled = true;},
    });
    return {response: new Response(body), body, cancelled: () => cancelled};
}

test('final reply completes immediately even when server leaves connection open', {timeout: 1000}, async () => {
    const stream = streamResponse(['data: {"type":"reply","content":"完成","run_id":"r1"}\n\n'], {open: true});
    const {context} = environment(async () => stream.response);
    assert.equal((await context.streamChatRequest({})).content, '完成');
    assert.equal(context.activeDurableRunId, 'r1');
    assert.equal(stream.cancelled(), true);
    assert.equal(stream.body.locked, false);
});

test('SSE accepts multiline data, heartbeats and split unicode/CRLF boundaries', async () => {
    const payload = ': heartbeat\r\n\r\ndata: {"type":"reply",\r\ndata: "content":"完成🙂"}\r\n\r\n';
    const bytes = new TextEncoder().encode(payload);
    const stream = streamResponse(Array.from(bytes, byte => new Uint8Array([byte])));
    const {context, events} = environment(async () => stream.response);
    assert.equal((await context.streamChatRequest({})).content, '完成🙂');
    assert.equal(events.length, 1);
    assert.equal(stream.body.locked, false);
});

test('EOF without a reply remains unknown and never resubmits the POST', async () => {
    let calls = 0;
    const stream = streamResponse(['data: {"type":"progress","run_id":"r2"}\n\n']);
    const {context, events} = environment(async () => {calls++; return stream.response;});
    await assert.rejects(context.streamChatRequest({}), error => {
        assert.equal(context.isChatTransportFailure(error), true);
        assert.match(context.markChatRequestFailure(error), /无法确认/);
        assert.match(context.chatRequestFailureMessage(error), /未收到最终回复/);
        return true;
    });
    assert.equal(calls, 1);
    assert.equal(context.activeDurableRunId, 'r2');
    assert.equal(events.at(-1), 'unknown');
    assert.equal(stream.body.locked, false);
});

test('stalled stream times out, cleans up and preserves uncertainty', {timeout: 1000}, async () => {
    const stream = streamResponse([], {open: true});
    const {context} = environment(async () => stream.response);
    await assert.rejects(context.streamChatRequest({}, {idleTimeoutMs: 10}), error =>
        context.isChatTransportFailure(error));
    assert.equal(stream.cancelled(), true);
    assert.equal(stream.body.locked, false);
});

test('oversized or invalid events cannot produce a false success', async () => {
    for (const payload of ['data: ' + 'x'.repeat(80), 'data: invalid\n\n', 'data: null\n\n']) {
        const stream = streamResponse([payload]);
        const {context} = environment(async () => stream.response);
        await assert.rejects(context.streamChatRequest({}, {maxEventChars: 64}), error =>
            context.isChatTransportFailure(error));
        assert.equal(stream.body.locked, false);
    }
});

test('explicit server failure stays a failure and partial failures explain their cause', async () => {
    const stream = streamResponse(['data: {"type":"error","error":"scope denied"}\n\n']);
    const {context} = environment(async () => stream.response);
    await assert.rejects(context.streamChatRequest({}), error => {
        assert.equal(context.isChatTransportFailure(error), false);
        return /scope denied/.test(error.message);
    });
    assert.match(context.streamResultFallback({status: 'partially_failed', results: [
        {success: true}, {success: false, error: 'scope denied'},
    ]}), /部分.*scope denied/);
});

test('a stalled initial response is bounded and is never retried', {timeout: 1000}, async () => {
    let calls = 0;
    let signal;
    const {context} = environment(async (_url, options) => {
        calls++;
        signal = options.signal;
        return new Promise(() => {});
    });
    await assert.rejects(context.streamChatRequest({}, {idleTimeoutMs: 10}), error =>
        context.isChatTransportFailure(error));
    assert.equal(calls, 1);
    assert.equal(signal.aborted, true);
});

test('reader errors are uncertain even when the browser uses an ordinary Error', async () => {
    const body = new ReadableStream({start(controller) {controller.error(new Error('socket closed'));}});
    const {context} = environment(async () => new Response(body));
    await assert.rejects(context.streamChatRequest({}), error => context.isChatTransportFailure(error));
    assert.equal(body.locked, false);
});

test('HTTP validation errors preserve safe field paths without rejected secret input', async () => {
    const {context} = environment(async () => new Response(JSON.stringify({detail: [{
        loc: ['body', 'api_key'], msg: 'invalid', input: 'PRIVATE-INPUT',
    }]}), {status: 422}));
    await assert.rejects(context.streamChatRequest({}), error => {
        assert.equal(error.status, 422);
        assert.match(error.message, /api_key/);
        assert.doesNotMatch(error.message, /PRIVATE-INPUT/);
        return true;
    });
});

test('heartbeats refresh the idle deadline during a long task', {timeout: 1000}, async () => {
    const body = new ReadableStream({
        async start(controller) {
            for (let index = 0; index < 8; index++) {
                controller.enqueue(new TextEncoder().encode(': heartbeat\n\n'));
                await new Promise(resolve => setTimeout(resolve, 10));
            }
            controller.enqueue(new TextEncoder().encode('data: {"type":"reply","content":"done"}\n\n'));
            controller.close();
        },
    });
    const {context} = environment(async () => new Response(body));
    assert.equal((await context.streamChatRequest({}, {idleTimeoutMs: 60})).content, 'done');
});
