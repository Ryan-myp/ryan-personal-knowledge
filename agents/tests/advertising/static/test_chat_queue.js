const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function loadQueue() {
    const context = {};
    const source = path.resolve(
        __dirname,
        '../../../deployments/advertising/static/js/chat-queue.js',
    );
    vm.runInNewContext(fs.readFileSync(source, 'utf8'), context, {
        filename: source,
    });
    return vm.runInNewContext('ChatMessageQueue', context);
}

test('queue is FIFO and isolated by conversation session', () => {
    const Queue = loadQueue();
    const queue = new Queue(3);

    assert.equal(queue.enqueue('session-a', { id: 'a1', text: 'first' }).accepted, true);
    assert.equal(queue.enqueue('session-a', { id: 'a2', text: 'second' }).accepted, true);
    assert.equal(queue.enqueue('session-b', { id: 'b1', text: 'other chat' }).accepted, true);
    assert.equal(queue.list('session-a').map(item => item.id).join(','), 'a1,a2');
    assert.equal(queue.list('session-b').map(item => item.id).join(','), 'b1');
    assert.equal(queue.size(), 3);
    assert.equal(queue.size('session-a'), 2);
    assert.equal(queue.dequeue('session-a').id, 'a1');
    assert.equal(queue.dequeue('session-a').id, 'a2');
    assert.equal(queue.dequeue('session-a'), null);
    assert.equal(queue.dequeue('session-b').id, 'b1');
});

test('queue enforces its per-session limit and supports removing a pending item', () => {
    const Queue = loadQueue();
    const queue = new Queue(2);

    assert.equal(queue.enqueue('session-a', { id: 'a1' }).accepted, true);
    assert.equal(queue.enqueue('session-a', { id: 'a2' }).accepted, true);
    const full = queue.enqueue('session-a', { id: 'a3' });
    assert.equal(full.accepted, false);
    assert.equal(full.position, 2);
    assert.equal(queue.enqueue('session-b', { id: 'b1' }).accepted, true);
    assert.equal(queue.remove('session-a', 'a1'), true);
    assert.equal(queue.enqueue('session-a', { id: 'a3' }).accepted, true);
    assert.equal(queue.list('session-a').map(item => item.id).join(','), 'a2,a3');
    assert.equal(queue.remove('session-a', 'missing'), false);
});

test('editing a queued message changes only its text and keeps request metadata', () => {
    const Queue = loadQueue();
    const queue = new Queue();
    const original = {
        id: 'queued-1',
        text: '旧问题',
        attachments: [{ id: 'media-1', filename: 'image.png' }],
        requestParams: {
            user_input: '旧问题',
            session_id: 'session-a',
            media_ids: ['media-1'],
            creation_blueprint_id: 'google-ads.shopping',
            creation_template_id: 'shopping-template',
        },
    };
    queue.enqueue('session-a', original);

    assert.equal(queue.updateText('session-a', 'queued-1', '修订后的问题'), true);
    const updated = queue.list('session-a')[0];

    assert.equal(updated.text, '修订后的问题');
    assert.equal(updated.requestParams.user_input, '修订后的问题');
    assert.equal(updated.requestParams.session_id, 'session-a');
    assert.equal(updated.requestParams.media_ids[0], 'media-1');
    assert.equal(
        updated.requestParams.creation_blueprint_id,
        'google-ads.shopping',
    );
    assert.equal(updated.requestParams.creation_template_id, 'shopping-template');
    assert.equal(updated.attachments[0].filename, 'image.png');
    assert.equal(original.text, '旧问题');
    assert.equal(original.requestParams.user_input, '旧问题');
    assert.equal(queue.updateText('session-a', 'missing', 'not queued'), false);
});

test('queue rejects missing sessions and malformed entries', () => {
    const Queue = loadQueue();
    const queue = new Queue();

    assert.throws(() => queue.enqueue('', { id: 'a1' }), /session/i);
    assert.throws(() => queue.enqueue('session-a', null), /item/i);
});

test('queue also applies a bounded total across sessions', () => {
    const Queue = loadQueue();
    const queue = new Queue(2, 3);

    assert.equal(queue.enqueue('session-a', { id: 'a1' }).accepted, true);
    assert.equal(queue.enqueue('session-a', { id: 'a2' }).accepted, true);
    assert.equal(queue.enqueue('session-b', { id: 'b1' }).accepted, true);
    const full = queue.enqueue('session-b', { id: 'b2' });
    assert.equal(full.accepted, false);
    assert.equal(full.reason, 'total_limit');
    assert.equal(queue.size(), 3);
});
