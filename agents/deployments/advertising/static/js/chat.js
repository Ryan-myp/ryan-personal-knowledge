(function () {
    const sources = [
        'vendor/marked-18.1.1.umd.js',
        'vendor/purify-3.4.17.min.js',
        'chat-markdown.js',
        'chat-queue.js',
        'chat-state.js',
        'chat-media.js',
        'chat-workbench.js',
        'chat-workspace.js',
        'chat-feedback.js',
        'chat-knowledge.js',
        'chat-trace.js',
        'chat-requests.js',
        'chat-settings.js',
        'chat-blueprint-core.js',
        'chat-blueprint-editor.js',
        'chat-creation-import.js',
        'chat-skills.js',
        'chat-mcp.js',
        'chat-creation.js',
        'chat-messages.js',
    ];
    const load = index => {
        if (index >= sources.length) return;
        const script = document.createElement('script');
        script.src = `/static/js/${sources[index]}?v=20261023-progress-language-v10`;
        script.onload = () => load(index + 1);
        script.onerror = () => console.error(`Failed to load ${sources[index]}`);
        document.head.appendChild(script);
    };
    load(0);
})();
