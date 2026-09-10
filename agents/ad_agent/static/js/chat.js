(function () {
    const sources = [
        'chat-state.js',
        'chat-workspace.js',
        'chat-knowledge.js',
        'chat-trace.js',
        'chat-requests.js',
        'chat-blueprint-core.js',
        'chat-blueprint-editor.js',
        'chat-skills.js',
        'chat-mcp.js',
        'chat-creation.js',
        'chat-messages.js',
    ];
    const load = index => {
        if (index >= sources.length) return;
        const script = document.createElement('script');
        script.src = `/static/js/${sources[index]}?v=20260910-mcp-inline-error-v1`;
        script.onload = () => load(index + 1);
        script.onerror = () => console.error(`Failed to load ${sources[index]}`);
        document.head.appendChild(script);
    };
    load(0);
})();
