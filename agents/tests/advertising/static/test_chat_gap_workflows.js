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
        this.dataset = {};
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
        querySelector() { return null; },
        addEventListener() {},
    };
    const context = { document, apiFetch, console, Date, URLSearchParams };
    for (const filename of ['chat-resource-catalogs.js', 'chat-knowledge.js', 'chat-management-catalogs.js', 'chat-feedback.js']) {
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
    context.renderResourceCatalog = (_kind, rows) => { context.catalogRows = rows; };
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

test('knowledge labels localize catalog metadata without changing stored keys', () => {
    const { context, elements } = workflowEnvironment(async () => ({}));
    const types = new Map([
        ['general', '通用'], ['decision_framework', '决策框架'],
        ['test_account_e2e', '测试账号 E2E'],
    ]);
    const selector = context.document.getElementById('knowledgeWriteType');
    selector.options = Array.from(types, ([value, textContent]) => ({ value, textContent }));

    assert.equal(context.knowledgeCategoryLabel('programmatic_advertising'), '程序化广告');
    assert.equal(context.knowledgeCategoryLabel('campaign_planning'), '投放规划');
    assert.equal(context.knowledgeCategoryLabel('reporting'), '报表分析');
    assert.equal(context.knowledgeCategoryLabel('compliance'), '合规与审核');
    assert.equal(context.knowledgeCategoryLabel('custom_area'), '自定义分类（custom_area）');
    assert.equal(context.knowledgePlatformLabel('meta'), 'Meta');
    assert.equal(context.knowledgePlatformLabel('tiktok'), 'TikTok');
    assert.equal(context.knowledgePlatformLabel('google-ads'), 'Google Ads');
    assert.equal(context.knowledgeTypeLabel('decision_framework'), '决策框架');
    assert.equal(context.knowledgeTypeLabel('test_account_e2e'), '测试账号 E2E');
    assert.equal(context.knowledgeTypeLabel('custom_rule'), '自定义类型（custom_rule）');
    assert.equal(selector.value, '');
    assert.equal(context.knowledgeCategoryLabel('campaign_operations'), '投放配置');
    assert.ok(elements.has('knowledgeWriteType'));
});

test('knowledge catalog uses readable type labels and preserves native resource names', () => {
    const { context, elements } = workflowEnvironment(async () => ({}));
    context.knowledgeState = {};
    context.escapeHtml = value => value;
    context.document.getElementById('knowledgeWriteType').options = [
        { value: 'general', textContent: '通用' },
        { value: 'hierarchy', textContent: '层级' },
        { value: 'test_account_e2e', textContent: '测试账号 E2E' },
    ];
    context.renderKnowledgeResults([{
        document_id: 'meta-ad-set',
        title: 'Meta Campaign 与 Ad Set 查询',
        platform: 'meta',
        category: 'campaign_operations',
        subcategory: 'campaign-and-ad-set-operations',
        knowledge_type: 'test_account_e2e',
        excerpt: '使用 adset_id 查询 Ad Set。',
    }]);
    const row = context.catalogRows[0];
    assert.equal(elements.has('knowledgeReader'), false);
    context.selectKnowledgeResult('meta-ad-set');
    const reader = elements.get('knowledgeReader');
    assert.match(row.cells[1], /投放配置/);
    assert.equal(row.title, 'Meta Campaign 与 Ad Set 查询');
    assert.doesNotMatch(row.cells[1], /campaign-and-ad-set-operations/);
    assert.match(reader.children[0].children[0].textContent, /Meta \/ 投放配置 \/ 测试账号 E2E/);

    const template = fs.readFileSync(path.resolve(
        __dirname, '../../../deployments/advertising/templates/chat.html',
    ), 'utf8');
    for (const key of ['bidding_strategy', 'targeting_strategy', 'creative_guide',
        'decision_framework', 'test_account_e2e']) {
        assert.match(template, new RegExp(`<option value="${key}"`));
    }
});

test('knowledge source and managed platform use readable labels while preserving provenance', () => {
    const { context, elements } = workflowEnvironment(async () => ({}));
    context.knowledgeState = {};
    context.escapeHtml = value => value;
    context.document.getElementById('knowledgeWriteType').options = [
        { value: 'general', textContent: '通用' },
    ];
    context.renderKnowledgeResults([{
        document_id: 'meta-campaign',
        title: 'Meta Campaign 与 Ad Set',
        platform: 'meta',
        knowledge_type: 'general',
        source: 'Meta Marketing API 官方文档',
        source_ref: 'https://developers.facebook.com/docs/marketing-api/',
    }]);
    context.selectKnowledgeResult('meta-campaign');
    const reader = elements.get('knowledgeReader');
    assert.match(reader.children[0].children[3].textContent, /Meta Marketing API 官方文档/);
    assert.doesNotMatch(reader.children[0].children[3].textContent, /https:\/\//);
    assert.match(reader.children[0].children[3].title, /developers\.facebook\.com/);

    context.renderManagedKnowledgeDocuments([{
        document_id: 'meta-campaign',
        title: 'Meta Campaign 与 Ad Set',
        platform: 'meta',
        status: 'published',
        version: '1.0.0',
    }]);
    const managed = context.catalogRows.find(item=>item.filters.source==='managed');
    assert.equal(managed.cells[0], 'Meta');
    assert.equal(managed.cells[2], '1.0.0');
    assert.equal(managed.cells[3], '已发布');
});

test('feedback regression candidates require human-written expected behavior', async () => {
    const calls = [];
    const { context, elements } = workflowEnvironment(async (endpoint, options = {}) => {
        calls.push([endpoint, options]);
        if (endpoint === '/feedback/review?status=pending&page=1&limit=10') {
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
        '/feedback/review?status=pending&page=1&limit=10',
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

test('feedback filters reset the page and preserve input drafts across page loads', async () => {
    const calls = [];
    const {context, elements} = workflowEnvironment(async endpoint => {
        calls.push(endpoint);
        const page = new URLSearchParams(endpoint.split('?')[1]).get('page');
        return {items:[{feedback_id:'one',review_status:'pending'}],
            pagination:{page:Number(page),limit:10,total:25,pages:3}};
    });
    await context.loadFeedbackReviewQueue();
    const expected = elements.get('feedbackReviewList').children[0].children[3].children[0];
    expected.value = '未保存的期望行为';
    expected.listeners.input();
    await context.changeFeedbackReviewPage(1);
    assert.match(calls.at(-1), /page=2/);
    const edited = elements.get('feedbackReviewList').children[0].children[3].children[0];
    assert.equal(edited.value, '未保存的期望行为');
    context.document.getElementById('feedbackReviewQuery').value = '预算';
    context.document.getElementById('feedbackReviewStatus').value = 'all';
    context.document.getElementById('feedbackReviewRange').value = '7';
    await context.applyFeedbackReviewFilters();
    const params = new URLSearchParams(calls.at(-1).split('?')[1]);
    assert.equal(params.get('page'), '1');
    assert.equal(params.get('q'), '预算');
    assert.equal(params.get('status'), 'all');
    assert(params.get('since'));
    assert.equal(elements.get('feedbackReviewPrevious').disabled, true);
});

test('late feedback response cannot overwrite new filters or reopen a closed page', async () => {
    let release;
    const first = new Promise(resolve => {release = resolve;});
    const {context,elements} = workflowEnvironment(() => first);
    const reading = context.loadFeedbackReviewQueue();
    context.apiFetch = async () => ({items:[{feedback_id:'new',reason:'NEW'}]});
    await context.applyFeedbackReviewFilters();
    release({items:[{feedback_id:'old',reason:'OLD'}]});
    await reading;
    assert.equal(elements.get('feedbackReviewList').children[0].children[0].children[0].textContent,'NEW');
    let finish;
    context.apiFetch = () => new Promise(resolve => {finish = resolve;});
    const closed = context.loadFeedbackReviewQueue();
    context.closeFeedbackTrend();
    finish({items:[{feedback_id:'closed',reason:'CLOSED'}]});
    await closed;
    assert.equal(elements.get('feedbackReviewList').children[0].children[0].children[0].textContent,'NEW');
});

test('feedback read failure allows retry and keeps unsaved review input', async () => {
    const {context,elements} = workflowEnvironment(async () => ({items:[{feedback_id:'one'}]}));
    await context.loadFeedbackReviewQueue();
    const expected=elements.get('feedbackReviewList').children[0].children[3].children[0];
    expected.value='保留草稿';
    expected.listeners.input();
    context.apiFetch=async()=>{throw new Error('暂时不可用');};
    await context.loadFeedbackReviewQueue();
    assert.match(elements.get('feedbackReviewStatusText').textContent,/暂时不可用/);
    assert.equal(elements.get('feedbackReviewList').attributes['aria-busy'],'false');
    assert.equal(elements.get('feedbackReviewNext').disabled,true);
    context.apiFetch=async()=>({items:[{feedback_id:'one'}]});
    await context.loadFeedbackReviewQueue();
    assert.equal(elements.get('feedbackReviewList').children[0].children[3].children[0].value,'保留草稿');
});
