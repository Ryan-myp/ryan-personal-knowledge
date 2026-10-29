(function () {
    const sources = [
        'vendor/marked-18.1.1.umd.js',
        'vendor/purify-3.4.17.min.js',
        'chat-markdown.js',
        'chat-queue.js',
        'chat-state.js',
        'chat-catalog-loading.js',
        'chat-resource-catalogs.js',
        'chat-media.js',
        'chat-workbench.js',
        'chat-workspace.js',
        'chat-schedules.js',
        'chat-feedback.js',
        'chat-knowledge.js',
        'chat-trace.js',
        'chat-requests.js',
        'chat-settings.js',
        'chat-blueprint-core.js',
        'chat-choice.js',
        'chat-blueprint-editor.js',
        'chat-template-browser.js',
        'chat-creation-import.js',
        'chat-skills.js',
        'chat-mcp.js',
        'chat-management-catalogs.js',
        'chat-creation.js',
        'chat-messages.js',
    ];
    const version = '20261029-workspace-resilience-v1';
    const status = document.getElementById('workspaceBootStatus');
    const message = document.getElementById('workspaceBootMessage');
    const retry = document.getElementById('workspaceBootRetry');
    const preloads = new Map();
    const sourceURL = index => `/static/js/${sources[index]}?v=${version}`;
    const prepare = index => {
        // Download a small window ahead, but execute only after each dependency loads.
        for (let next = index; next < Math.min(index + 4, sources.length); next++) {
            if (preloads.has(next)) continue;
            const link = document.createElement('link');
            link.rel = 'preload';
            link.as = 'script';
            link.href = sourceURL(next);
            preloads.set(next, link);
            document.head.appendChild(link);
        }
    };
    const load = index => {
        if (index >= sources.length) {
            if (status) status.hidden = true;
            return;
        }
        prepare(index);
        if (message) message.textContent = `正在准备工作区 · ${index + 1} / ${sources.length}`;
        if (retry) retry.hidden = true;
        const script = document.createElement('script');
        script.src = sourceURL(index);
        script.onload = () => {
            preloads.get(index)?.remove();
            preloads.delete(index);
            load(index + 1);
        };
        script.onerror = () => {
            if (message) message.textContent = '工作区加载失败，请检查连接后重试。';
            if (!retry) return;
            retry.hidden = false;
            retry.onclick = () => { script.remove(); load(index); };
        };
        document.head.appendChild(script);
    };
    load(0);
})();
