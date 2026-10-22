const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

class Element {
    constructor() {
        this.textContent = '';
        this.innerHTML = '';
        this.disabled = false;
        this.hidden = false;
        this.value = '';
        this.children = [];
        this.attributes = {};
        this.listeners = {};
        this.classList = {
            add() {},
            remove() {},
            toggle() {},
            contains: () => false,
        };
    }

    append(...children) {
        this.children.push(...children);
    }

    appendChild(child) {
        this.children.push(child);
        return child;
    }

    replaceChildren(...children) {
        this.children = [...children];
    }

    addEventListener(type, listener) {
        this.listeners[type] = listener;
    }

    setAttribute(name, value) {
        this.attributes[name] = value;
    }
}

function workflowEnvironment(apiFetch) {
    const elements = new Map();
    const document = {
        getElementById(id) {
            if (!elements.has(id)) elements.set(id, new Element());
            return elements.get(id);
        },
        createElement() {
            return new Element();
        },
        querySelectorAll() {
            return [];
        },
        addEventListener() {},
    };
    const context = { document, apiFetch, console, Date };
    for (const filename of ['chat-knowledge.js', 'chat-feedback.js']) {
        const source = path.resolve(
            __dirname,
            '../../../deployments/advertising/static/js',
            filename,
        );
        vm.runInNewContext(
            fs.readFileSync(source, 'utf8'),
            context,
            { filename },
        );
    }
    return { context, elements };
}

test('knowledge semantic index can be rebuilt again after a successful run', async () => {
    const calls = [];
    const { context, elements } = workflowEnvironment(async endpoint => {
        calls.push(endpoint);
        return {
            configured: true,
            builtin: { available: true, chunk_count: 8 },
            tenant: { available: true, chunk_count: 3 },
        };
    });
    const button = context.document.getElementById(
        'knowledgeSemanticRebuildButton',
    );

    await context.rebuildKnowledgeSemanticIndex();
    assert.equal(button.disabled, false);
    assert.match(elements.get('knowledgeSemanticStatus').textContent, /索引已完成/);

    await context.rebuildKnowledgeSemanticIndex();
    assert.equal(button.disabled, false);
    assert.deepEqual(calls, [
        '/knowledge/semantic-index/rebuild',
        '/knowledge/semantic-index/rebuild',
    ]);
});

test('feedback regression candidates require human-written expected behavior', async () => {
    const calls = [];
    const { context, elements } = workflowEnvironment(async (endpoint, options = {}) => {
        calls.push([endpoint, options]);
        if (endpoint === '/feedback/review?status=pending&limit=100') {
            return { items: [] };
        }
        return {};
    });

    await context.reviewFeedbackItem('feedback-1', 'candidate', '  ');
    assert.deepEqual(calls, []);
    assert.match(
        elements.get('feedbackReviewStatusText').textContent,
        /请填写期望行为/,
    );

    await context.reviewFeedbackItem(
        'feedback-1',
        'candidate',
        '先核对统计日期，再解释指标。',
    );
    assert.equal(calls.length, 2);
    assert.equal(calls[0][0], '/feedback/review/feedback-1');
    assert.equal(calls[0][1].method, 'PUT');
    assert.deepEqual(JSON.parse(calls[0][1].body), {
        review_status: 'candidate',
        expected_behavior: '先核对统计日期，再解释指标。',
        assertions: {},
    });
    assert.equal(
        calls[1][0],
        '/feedback/review?status=pending&limit=100',
    );
});

test('feedback assertions reject invalid JSON and preserve closed data for the API', () => {
    const { context } = workflowEnvironment(async () => ({}));
    assert.throws(() => context.parseFeedbackAssertions('[]'), /对象/);
    assert.throws(() => context.parseFeedbackAssertions('{bad}'), /JSON/);
    assert.equal(context.parseFeedbackAssertions('{"max_tool_calls":1}').max_tool_calls, 1);
});

test('dismissed feedback does not advertise an unsupported pending transition', () => {
    const { context, elements } = workflowEnvironment(async () => ({}));
    context.renderFeedbackReviewQueue([{ feedback_id: 'one', review_status: 'dismissed' }]);
    const actions = elements.get('feedbackReviewList').children[0].children.at(-1);
    assert.equal(actions.children[1].textContent, '已忽略');
    assert.equal(actions.children[1].disabled, true);
});
