const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function environment(fetch) {
    const context = {fetch, Headers, AbortController, setTimeout, clearTimeout,
        document: {getElementById: () => null}, showSkillNotice() {}};
    vm.createContext(context);
    for (const file of ['chat-requests.js', 'chat-settings.js']) {
        vm.runInContext(fs.readFileSync(path.resolve(__dirname,
            '../../../deployments/advertising/static/js', file), 'utf8'), context);
    }
    return context;
}

test('JSON request rejects successful HTML/empty replies instead of silently replacing data', async () => {
    for (const body of ['<html>gateway diagnostic</html>', '', 'null']) {
        const context = environment(async () => new Response(body));
        await assert.rejects(context.apiFetch('/skills'), /响应格式/);
        await assert.rejects(context.settingsRequest('/settings'), /响应格式/);
    }
});

test('JSON request accepts 204 and JSON, and still removes browser API key headers', async () => {
    let headers;
    const context = environment(async (_url, options) => {
        headers = options.headers;
        return new Response(null, {status: 204});
    });
    const result = await context.apiFetch('/settings', {headers: {'X-API-Key': 'not-a-real-key'}});
    assert.equal(Object.keys(result).length, 0);
    assert.equal(headers.has('X-API-Key'), false);
});

test('validation errors report field paths without echoing rejected credential values', async () => {
    const context = environment(async () => new Response(JSON.stringify({detail: [{
        loc: ['body', 'api_key'], msg: 'invalid value', input: 'PRIVATE-INPUT', ctx: {value: 'PRIVATE-INPUT'},
    }]}), {status: 422}));
    await assert.rejects(context.apiFetch('/settings'), error => {
        assert.equal(error.status, 422);
        assert.match(error.message, /api_key/);
        assert.doesNotMatch(error.message, /PRIVATE-INPUT|object Object/);
        return true;
    });
});

test('deadline covers a stalled response body and never retries a write', async () => {
    let calls = 0;
    const context = environment(async (_url, {signal}) => {
        calls++;
        return {ok: true, status: 200, text: () => new Promise((_resolve, reject) => {
            signal.addEventListener('abort', () => reject(signal.reason), {once: true});
        })};
    });
    await assert.rejects(context.apiFetch('/settings', {method: 'PUT', timeoutMs: 10}), /无法确认.*结果/);
    assert.equal(calls, 1);
    await assert.rejects(context.apiFetch('/skills', {timeoutMs: 10}), /超时/);
});

test('caller cancellation is preserved and no request is sent when already cancelled', async () => {
    let calls = 0;
    const context = environment(async () => { calls++; return new Response('{}'); });
    const controller = new AbortController();
    controller.abort();
    await assert.rejects(context.apiFetch('/skills', {signal: controller.signal}), {name: 'AbortError'});
    assert.equal(calls, 0);
});

test('failed HTML responses expose status but do not reflect gateway response markup', async () => {
    const context = environment(async () => new Response('<script>private gateway</script>', {status: 502}));
    await assert.rejects(context.apiFetch('/skills'), error => {
        assert.equal(error.status, 502);
        assert.match(error.message, /502/);
        assert.doesNotMatch(error.message, /private|script/);
        return true;
    });
});

test('unreadable write results require verification before retrying', async () => {
    let calls = 0;
    const context = environment(async () => {calls++; return new Response('<html>gateway</html>');});
    await assert.rejects(context.apiFetch('/settings', {method:'POST'}), /无法确认.*结果/);
    assert.equal(calls,1);
});
