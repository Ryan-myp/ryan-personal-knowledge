let feedbackTrendDays = 30;
let feedbackTrendRequestToken = 0;
let feedbackReviewRequestToken = 0;
const feedbackReviewPage = {page: 1, limit: 10, status: 'pending', q: '', since: ''};
const feedbackReviewDrafts = new Map();

function feedbackTrendSetStatus(state, message) {
    const banner = document.getElementById('feedbackTrendStatus');
    const label = document.getElementById('feedbackTrendStatusText');
    if (!banner || !label) return;
    banner.className = `monitoring-status-banner ${state === 'ready' ? '' : state}`.trim();
    label.textContent = message;
}

function feedbackTrendCount(value) {
    const count = Number(value);
    return Number.isFinite(count) ? count.toLocaleString('zh-CN') : '—';
}

function renderFeedbackTrend(data) {
    const points = Array.isArray(data.daily) ? data.daily : [];
    const svg = document.getElementById('feedbackTrendChart');
    const empty = document.getElementById('feedbackTrendEmpty');
    if (!svg || !empty) return;

    const values = points.flatMap(item => [
        Math.max(0, Number(item.positive) || 0),
        Math.max(0, Number(item.negative) || 0),
    ]);
    const maximum = Math.max(1, ...values);
    const width = 720;
    const height = 250;
    const padding = { top: 14, right: 14, bottom: 32, left: 34 };
    const plotWidth = width - padding.left - padding.right;
    const plotHeight = height - padding.top - padding.bottom;
    const xFor = index => padding.left + (
        points.length <= 1 ? plotWidth / 2 : index / (points.length - 1) * plotWidth
    );
    const yFor = value => padding.top + plotHeight - (
        Math.max(0, Number(value) || 0) / maximum * plotHeight
    );
    const line = key => points.map(
        (item, index) => `${xFor(index).toFixed(1)},${yFor(item[key]).toFixed(1)}`
    ).join(' ');
    const ticks = [0, maximum / 2, maximum];
    const grid = ticks.map(value => {
        const y = yFor(value);
        const label = Number.isInteger(value) ? String(value) : value.toFixed(1);
        return `<line class="feedback-chart-grid" x1="${padding.left}" y1="${y.toFixed(1)}" x2="${width - padding.right}" y2="${y.toFixed(1)}"></line><text class="feedback-chart-axis" x="${padding.left - 8}" y="${(y + 3).toFixed(1)}" text-anchor="end">${label}</text>`;
    }).join('');
    const labelStep = Math.max(1, Math.ceil(points.length / 6));
    const labels = points.map((item, index) => {
        if (index !== 0 && index !== points.length - 1 && index % labelStep !== 0) return '';
        const date = String(item.date || '');
        const label = date.slice(5);
        return `<text class="feedback-chart-axis" x="${xFor(index).toFixed(1)}" y="${height - 7}" text-anchor="middle">${escapeHtml(label)}</text>`;
    }).join('');
    const dots = key => points.map((item, index) => {
        const title = `${String(item.date || '')}: ${key === 'positive' ? '正向' : '负向'} ${Number(item[key]) || 0}`;
        return `<circle class="feedback-chart-point ${key}" cx="${xFor(index).toFixed(1)}" cy="${yFor(item[key]).toFixed(1)}" r="3"><title>${escapeHtml(title)}</title></circle>`;
    }).join('');
    svg.innerHTML = `${grid}<polyline class="feedback-chart-line positive" points="${line('positive')}"></polyline><polyline class="feedback-chart-line negative" points="${line('negative')}"></polyline>${dots('positive')}${dots('negative')}${labels}`;

    const total = Math.max(0, Number(data.total) || 0);
    const positive = Math.max(0, Number(data.positive) || 0);
    const negative = Math.max(0, Number(data.negative) || 0);
    document.getElementById('feedbackTotal').textContent = feedbackTrendCount(total);
    document.getElementById('feedbackPositive').textContent = feedbackTrendCount(positive);
    document.getElementById('feedbackNegative').textContent = feedbackTrendCount(negative);
    const rate = data.positive_rate === null || data.positive_rate === undefined
        ? null
        : Number(data.positive_rate);
    document.getElementById('feedbackPositiveRate').textContent = rate === null || !Number.isFinite(rate)
        ? '—'
        : `${(rate * 100).toFixed(1).replace(/\.0$/, '')}%`;
    document.getElementById('feedbackTrendRange').textContent = data.since && data.until
        ? `${data.since} 至 ${data.until} · UTC`
        : `最近 ${Number(data.days) || feedbackTrendDays} 天`;
    empty.hidden = total > 0;
}

async function loadFeedbackTrend(days = feedbackTrendDays) {
    const selectedDays = Number(days);
    if (![7, 30, 90].includes(selectedDays)) return;
    feedbackTrendDays = selectedDays;
    const requestToken = ++feedbackTrendRequestToken;
    document.querySelectorAll('[data-feedback-days]').forEach(button => {
        button.setAttribute(
            'aria-pressed',
            String(Number(button.dataset.feedbackDays) === selectedDays),
        );
    });
    feedbackTrendSetStatus('attention', '正在读取反馈统计…');
    try {
        const data = await apiFetch(`/feedback/trend?days=${selectedDays}`);
        if (requestToken !== feedbackTrendRequestToken) return;
        renderFeedbackTrend(data);
        const updated = document.getElementById('feedbackTrendUpdated');
        if (updated) updated.textContent = `更新于 ${new Date().toLocaleTimeString('zh-CN')}`;
        feedbackTrendSetStatus('ready', data.total
            ? `已读取 ${feedbackTrendCount(data.total)} 条主动反馈`
            : '所选范围内暂无主动反馈');
    } catch (error) {
        if (requestToken !== feedbackTrendRequestToken) return;
        const message = error?.status === 401 || error?.status === 403
            ? '当前身份没有读取反馈趋势的权限。'
            : error?.status === 404
                ? '当前服务尚未加载反馈趋势接口，请重启服务后刷新。'
                : error?.message || '反馈趋势读取失败';
        feedbackTrendSetStatus('critical', message);
        const updated = document.getElementById('feedbackTrendUpdated');
        if (updated) updated.textContent = '读取失败';
    }
}

function feedbackReviewSetStatus(message, isError = false) {
    const status = document.getElementById('feedbackReviewStatusText');
    if (!status) return;
    status.textContent = message || '';
    status.classList.toggle('error', Boolean(isError));
}

function renderFeedbackReviewQueue(items) {
    const list = document.getElementById('feedbackReviewList');
    if (!list) return;
    list.replaceChildren();
    const records = Array.isArray(items) ? items : [];
    if (!records.length) {
        const empty = document.createElement('div');
        empty.className = 'feedback-review-empty';
        empty.textContent = '此审核状态下没有反馈记录。';
        list.appendChild(empty);
        return;
    }

    records.forEach(item => {
        const card = document.createElement('article');
        card.className = 'feedback-review-item';
        card.dataset.feedbackId = item.feedback_id;
        const header = document.createElement('div');
        header.className = 'feedback-review-item-header';
        const title = document.createElement('strong');
        title.textContent = item.reason || '用户提交了负向反馈';
        const timestamp = document.createElement('time');
        const submitted = new Date(item.submitted_at);
        timestamp.textContent = Number.isNaN(submitted.getTime()) ? '' : submitted.toLocaleString('zh-CN', {hour12: false});
        timestamp.dateTime = item.submitted_at || '';
        const reviewStatus = document.createElement('span');
        reviewStatus.className = 'feedback-review-state';
        reviewStatus.textContent = {pending:'待审核', candidate:'已收录', dismissed:'已忽略'}[item.review_status] || '';
        header.append(title, reviewStatus, timestamp);
        card.appendChild(header);

        for (const [label, value] of [
            ['用户问题', item.user_input],
            ['当时回答', item.assistant_reply],
        ]) {
            const block = document.createElement('div');
            block.className = 'feedback-review-copy';
            const caption = document.createElement('span');
            caption.textContent = label;
            const content = document.createElement('p');
            content.textContent = value || '（无内容）';
            block.append(caption, content);
            card.appendChild(block);
        }

        const expectedLabel = document.createElement('label');
        expectedLabel.className = 'feedback-review-expected';
        expectedLabel.textContent = '期望行为';
        const expected = document.createElement('textarea');
        expected.maxLength = 2000;
        expected.rows = 3;
        const draft = feedbackReviewDrafts.get(item.feedback_id);
        expected.value = draft?.expected ?? item.expected_behavior ?? '';
        expected.placeholder = '人工写明正确回答应该满足的条件';
        expectedLabel.appendChild(expected);
        card.appendChild(expectedLabel);

        const advanced = document.createElement('details');
        const summary = document.createElement('summary');
        summary.textContent = '自动回归条件';
        const assertionsLabel = document.createElement('label');
        assertionsLabel.className = 'feedback-review-expected';
        assertionsLabel.textContent = '验收断言 (JSON)';
        const assertionsInput = document.createElement('textarea');
        assertionsInput.rows = 4;
        assertionsInput.maxLength = 8000;
        assertionsInput.setAttribute('aria-describedby', 'feedbackReviewStatusText');
        assertionsInput.value = draft?.assertions ?? JSON.stringify(item.assertions || {}, null, 2);
        const rememberDraft = () => feedbackReviewDrafts.set(item.feedback_id, {
            expected: expected.value, assertions: assertionsInput.value,
        });
        expected.addEventListener('input', rememberDraft);
        assertionsInput.addEventListener('input', rememberDraft);
        assertionsLabel.appendChild(assertionsInput);
        advanced.append(summary, assertionsLabel);
        card.appendChild(advanced);

        const actions = document.createElement('div');
        actions.className = 'feedback-review-item-actions';
        const accept = document.createElement('button');
        accept.type = 'button';
        accept.className = 'btn btn-primary';
        accept.textContent = item.review_status === 'candidate' ? '更新回归样例' : '收录为回归样例';
        accept.addEventListener('click', () => {
            try {
                const assertions = parseFeedbackAssertions(assertionsInput.value);
                assertionsInput.setAttribute('aria-invalid', 'false');
                reviewFeedbackItem(item.feedback_id, 'candidate', expected.value, assertions);
            } catch (error) {
                assertionsInput.setAttribute('aria-invalid', 'true');
                assertionsInput.focus();
                feedbackReviewSetStatus(error.message, true);
            }
        });
        const dismiss = document.createElement('button');
        dismiss.type = 'button';
        dismiss.className = 'btn btn-secondary';
        dismiss.textContent = item.review_status === 'dismissed' ? '已忽略' : '忽略';
        dismiss.disabled = item.review_status === 'dismissed';
        dismiss.addEventListener('click', () => reviewFeedbackItem(
            item.feedback_id,
            'dismissed',
            '',
        ));
        actions.append(accept, dismiss);
        card.appendChild(actions);
        list.appendChild(card);
    });
}

async function loadFeedbackReviewQueue() {
    const params = new URLSearchParams({status:feedbackReviewPage.status,
        page:feedbackReviewPage.page, limit:feedbackReviewPage.limit});
    for (const field of ['q', 'since']) {
        if (feedbackReviewPage[field]) params.set(field, feedbackReviewPage[field]);
    }
    const requestToken = ++feedbackReviewRequestToken;
    document.getElementById('feedbackReviewPrevious').disabled = true;
    document.getElementById('feedbackReviewNext').disabled = true;
    document.getElementById('feedbackReviewList').setAttribute('aria-busy', 'true');
    feedbackReviewSetStatus('正在读取审核队列…');
    try {
        const result = await apiFetch(`/feedback/review?${params}`);
        if (requestToken !== feedbackReviewRequestToken) return;
        const items = Array.isArray(result.items) ? result.items : [];
        const pagination = result.pagination || {page:1, pages:1, total:items.length};
        feedbackReviewPage.page = pagination.page;
        renderFeedbackReviewQueue(items);
        document.getElementById('feedbackReviewPageInfo').textContent =
            `共 ${pagination.total} 条 · 第 ${pagination.page} / ${pagination.pages} 页`;
        document.getElementById('feedbackReviewPrevious').disabled = pagination.page <= 1;
        document.getElementById('feedbackReviewNext').disabled = pagination.page >= pagination.pages;
        feedbackReviewSetStatus(items.length ? `当前页 ${items.length} 条` : '没有匹配的反馈，请调整筛选条件。');
    } catch (error) {
        if (requestToken !== feedbackReviewRequestToken) return;
        document.getElementById('feedbackReviewList')?.replaceChildren();
        document.getElementById('feedbackReviewPageInfo').textContent = '读取失败';
        const message = error?.status === 401 || error?.status === 403
            ? '当前身份没有反馈审核权限；需要显式授予 feedback.review。'
            : error?.message || '反馈审核队列读取失败。';
        feedbackReviewSetStatus(message, true);
    } finally {
        if (requestToken === feedbackReviewRequestToken) {
            document.getElementById('feedbackReviewList').setAttribute('aria-busy', 'false');
        }
    }
}

async function applyFeedbackReviewFilters() {
    feedbackReviewPage.page = 1;
    feedbackReviewPage.status = document.getElementById('feedbackReviewStatus').value || 'pending';
    feedbackReviewPage.limit = Number(document.getElementById('feedbackReviewSize').value) || 10;
    feedbackReviewPage.q = (document.getElementById('feedbackReviewQuery').value || '').trim();
    const days = Number(document.getElementById('feedbackReviewRange').value);
    feedbackReviewPage.since = days ? new Date(Date.now() - days * 86400000).toISOString() : '';
    await loadFeedbackReviewQueue();
}

async function changeFeedbackReviewPage(direction) {
    feedbackReviewPage.page = Math.max(1, feedbackReviewPage.page + direction);
    await loadFeedbackReviewQueue();
    document.querySelector('.feedback-review-panel')?.scrollIntoView({block: 'start'});
}

function parseFeedbackAssertions(text) {
    if (String(text || '').length > 8000) throw new Error('回归断言不能超过 8000 个字符。');
    let value;
    try {
        value = JSON.parse(String(text || '').trim() || '{}');
    } catch {
        throw new Error('回归断言必须是有效的 JSON 对象。');
    }
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
        throw new Error('回归断言必须是 JSON 对象。');
    }
    return value;
}

async function reviewFeedbackItem(feedbackId, reviewStatus, expectedBehavior, assertions = {}) {
    const requestToken = feedbackReviewRequestToken;
    const submittedDraft = feedbackReviewDrafts.get(feedbackId);
    const safeExpected = String(expectedBehavior || '').trim();
    if (reviewStatus === 'candidate' && !safeExpected) {
        feedbackReviewSetStatus('请填写期望行为后再收录。', true);
        return;
    }
    feedbackReviewSetStatus('正在保存审核结果…');
    try {
        await apiFetch(`/feedback/review/${encodeURIComponent(feedbackId)}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                review_status: reviewStatus,
                expected_behavior: safeExpected,
                assertions,
            }),
        });
        if (feedbackReviewDrafts.get(feedbackId) === submittedDraft) feedbackReviewDrafts.delete(feedbackId);
        if (requestToken !== feedbackReviewRequestToken) return;
        feedbackReviewSetStatus(
            reviewStatus === 'candidate'
                ? '已人工确认并保存为回归候选。'
                : '已将该反馈标记为忽略。',
        );
        await loadFeedbackReviewQueue();
    } catch (error) {
        if (requestToken !== feedbackReviewRequestToken) return;
        feedbackReviewSetStatus(error?.message || '反馈审核保存失败。', true);
    }
}

async function exportFeedbackRegressionCases() {
    feedbackReviewSetStatus('正在导出已审核的回归样例…');
    try {
        const payload = await apiFetch('/feedback/regression-cases/export');
        const blob = new Blob(
            [JSON.stringify(payload, null, 2)],
            { type: 'application/json;charset=utf-8' },
        );
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'ad-agent-regression-cases.json';
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
        feedbackReviewSetStatus(
            `${(payload.cases || []).length} 条人工审核样例已导出${payload.truncated ? '；达到 100 条导出上限' : ''}。`,
        );
    } catch (error) {
        feedbackReviewSetStatus(error?.message || '回归样例导出失败。', true);
    }
}

function openFeedbackTrend() {
    closeWorkspacePopovers();
    const overlay = document.getElementById('feedbackTrendOverlay');
    if (!overlay) return;
    overlay.classList.add('active');
    overlay.setAttribute('aria-hidden', 'false');
    loadFeedbackTrend(30);
    loadFeedbackReviewQueue();
}

function closeFeedbackTrend() {
    feedbackTrendRequestToken += 1;
    feedbackReviewRequestToken += 1;
    document.getElementById('feedbackTrendOverlay')?.classList.remove('active');
    document.getElementById('feedbackTrendOverlay')?.setAttribute('aria-hidden', 'true');
}

document.getElementById('feedbackTrendOverlay')?.addEventListener('click', event => {
    if (event.target === event.currentTarget) closeFeedbackTrend();
});

document.addEventListener('keydown', event => {
    if (event.key === 'Escape'
        && document.getElementById('feedbackTrendOverlay')?.classList.contains('active')) {
        closeFeedbackTrend();
    }
});
