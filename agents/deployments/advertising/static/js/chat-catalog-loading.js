/* Request state shared by management catalogs; no cached payloads or credentials. */
const catalogLoads = new Map();

function beginCatalogLoad(kind, {slot = 'list', retry} = {}) {
    const request = {kind, slot, retry, pending: true, error: ''};
    catalogLoads.set(`${kind}:${slot}`, request);
    renderCatalogLoadStatus(kind);
    return request;
}

function isCurrentCatalogLoad(request) {
    return catalogLoads.get(`${request.kind}:${request.slot}`) === request;
}

function finishCatalogLoad(request, error = '') {
    if (!isCurrentCatalogLoad(request)) return;
    request.pending = false;
    request.error = error;
    renderCatalogLoadStatus(request.kind);
}

function catalogLoadPresentation(kind) {
    const requests = [...catalogLoads.values()].filter(item => item.kind === kind);
    const pending = requests.some(item => item.pending);
    const failed = requests.filter(item => item.error);
    return {pending, failed, message: failed.length
        ? `读取未完成：${failed.map(item => item.error).join('；')}`
        : pending ? '正在读取内容…' : ''};
}

function renderCatalogLoadStatus(kind) {
    const view = catalogLoadPresentation(kind);
    const catalog = document.getElementById(`${kind}Catalog`);
    catalog?.setAttribute('aria-busy', String(view.pending));
    const status = document.getElementById(`${kind}CatalogStatus`);
    if (status) {status.hidden = !view.message; status.classList.toggle('error', view.failed.length > 0);}
    const message = document.getElementById(`${kind}CatalogStatusMessage`);
    if (message) message.textContent = view.message;
    const retry = document.getElementById(`${kind}CatalogRetry`);
    if (retry) {
        retry.hidden = !view.failed.length;
        retry.disabled = view.pending;
        retry.onclick = () => view.failed.forEach(item => item.retry?.());
    }
    const empty = document.getElementById(`${kind}CatalogEmpty`);
    if (empty) empty.textContent = view.failed.length ? '内容暂时无法读取，请重试。'
        : view.pending ? '正在读取内容…' : '没有匹配的内容，请调整筛选或新建。';
}
