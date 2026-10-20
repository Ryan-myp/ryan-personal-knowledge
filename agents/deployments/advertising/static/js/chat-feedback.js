let feedbackTrendDays = 30;
let feedbackTrendRequestToken = 0;

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

function openFeedbackTrend() {
    closeWorkspacePopovers();
    const overlay = document.getElementById('feedbackTrendOverlay');
    if (!overlay) return;
    overlay.classList.add('active');
    overlay.setAttribute('aria-hidden', 'false');
    loadFeedbackTrend(30);
}

function closeFeedbackTrend() {
    feedbackTrendRequestToken += 1;
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
