const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

class FakeNode {
    constructor() {
        this.children = [];
        this.classList = { add() {}, remove() {}, toggle() {} };
    }

    appendChild(child) {
        this.children.push(child);
        return child;
    }

    append(...children) {
        this.children.push(...children);
    }

    replaceChildren(...children) {
        this.children = [...children];
    }

    addEventListener() {}
}

function environment() {
    const summary = new FakeNode();
    const context = {
        document: { createElement: () => new FakeNode() },
        escapeHtml: value => String(value),
        creationCardProgress: () => ({ completed: 2, total: 5, percent: 40 }),
        creationFieldValue: field => field.value,
        creationCardValueEmpty: value => value === undefined || value === null || value === '',
        creationFieldNeedsUserInput: field => Boolean(field.user_required),
        creationFieldDisplayValue: field => String(field.value ?? ''),
        creationCardInvalidLabels: () => [],
        creationCardScrollTo() {},
        creationCardPendingLabels: card => (
            (card.fields || []).filter(field => field.user_required && !field.value)
                .map(field => field.label)
        ),
        creationDirectoryHierarchyGroups: fields => [
            ['Campaign 层级', fields],
        ],
    };
    vm.runInNewContext(
        fs.readFileSync(path.resolve(
            __dirname,
            '../../../deployments/advertising/static/js/chat-creation.js',
        ), 'utf8'),
        context,
    );
    return { context, summary };
}

test('cascade options preserve labels and omit no-longer-valid choices', () => {
    const { context } = environment();
    const field = { options: [
        { value: 'APP', label: '应用' }, { value: 'WEB', label: '网站' },
    ] };
    const options = context.evaluatedCreationFieldOptions(field, { options: ['APP'] });
    assert.deepEqual(JSON.parse(JSON.stringify(options)), [{ value: 'APP', label: '应用' }]);
    assert.deepEqual(context.evaluatedCreationFieldOptions(field, {}), field.options);
    assert.equal(context.evaluatedCreationFieldOptions(field, { options: [] }).length, 0);
});

test('the live creation summary includes populated template fields', () => {
    const { context, summary } = environment();
    const card = {
        account_id: 'tiktok-test-account',
        template_id: 'tiktok.test.sales',
        fields: [
            {
                path: 'campaign.campaign_name',
                label: 'Campaign 名称',
                value: 'Paused sales test',
                user_required: true,
            },
            {
                path: 'campaign.objective',
                label: '优化目标',
                value: 'PRODUCT_SALES',
                user_required: false,
                auto_filled: true,
                default_source: 'template',
            },
        ],
    };
    const wrapper = { querySelector: () => summary };

    context.renderCreationCardSummary(card, wrapper);

    const summaryItems = summary.children.find(
        item => item.className === 'creation-card-summary-items',
    );
    const rendered = summaryItems.children
        .map(item => `${item.textContent || ''} ${item.innerHTML || ''}`)
        .join(' ');
    assert.match(rendered, /Paused sales test/);
    assert.match(rendered, /PRODUCT_SALES/);
});

test('the full creation review includes template-prefilled values', () => {
    const { context } = environment();
    const html = context.creationReviewRows({
        fields: [
            {
                path: 'campaign.objective',
                label: '优化目标',
                value: 'PRODUCT_SALES',
                control: 'text',
                visible: true,
                user_required: false,
            },
            {
                path: 'campaign.daily_budget',
                label: '日预算',
                value: 25,
                control: 'number',
                visible: true,
                user_required: false,
            },
        ],
    });

    assert.match(html, /PRODUCT_SALES/);
    assert.match(html, /25/);
});

test('creation continuation hints are derived from template fields and the prior prompt', () => {
    const { context } = environment();
    const continuation = context.creationContinuationContextForCard({
        ready: false,
        missing_fields: ['campaign.name'],
        fields: [{
            path: 'campaign.name',
            label: 'Campaign 名称',
            user_required: true,
            options: [],
        }],
    }, '请回复“使用建议时间”继续。', 'session-a');

    assert.equal(continuation.session_id, 'session-a');
    assert.ok(continuation.reply_options.includes('使用建议时间'));
    assert.equal(continuation.fields[0].label, 'Campaign 名称');
    assert.equal(continuation.expects_input, true);
});
