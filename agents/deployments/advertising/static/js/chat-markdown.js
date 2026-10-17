const chatMarkdownRenderer = new marked.Renderer();
const chatMarkdownTable = chatMarkdownRenderer.table;
const chatMarkdownCode = chatMarkdownRenderer.code;

chatMarkdownRenderer.html = ({ text }) => escapeHtml(text);
chatMarkdownRenderer.table = function (token) {
    const table = chatMarkdownTable.call(this, token)
        .replace('<table>', '<table class="data-table">');
    return `<div class="markdown-table-scroll" role="region" aria-label="Table" tabindex="0">${table}</div>`;
};
chatMarkdownRenderer.code = function (token) {
    const html = chatMarkdownCode.call(this, token);
    const language = String(token.lang || '').trim().split(/\s+/, 1)[0].toLowerCase();
    return language === 'mermaid'
        ? html.replace('<pre>', '<pre class="mermaid-source">')
        : html;
};

const chatMarkdownParser = new marked.Marked({
    gfm: true,
    breaks: true,
    renderer: chatMarkdownRenderer,
});

function formatContent(content) {
    if (content == null || content === '') return '';
    const source = String(content).replace(/\r\n?/g, '\n');
    return DOMPurify.sanitize(chatMarkdownParser.parse(source), {
        ALLOWED_TAGS: [
            'p', 'br', 'hr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'strong', 'em', 'del', 'blockquote', 'pre', 'code', 'ul', 'ol', 'li',
            'a', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'div', 'input',
        ],
        ALLOWED_ATTR: [
            'href', 'title', 'class', 'align', 'start', 'type', 'disabled', 'checked',
            'role', 'aria-label', 'tabindex',
        ],
        ALLOW_DATA_ATTR: false,
        ALLOW_ARIA_ATTR: false,
    });
}

const MAX_MERMAID_SOURCE_LENGTH = 12000;
const MAX_MERMAID_DIAGRAMS_PER_MESSAGE = 8;
const MERMAID_DIAGRAM_HEADER = /^(?:graph|flowchart|sequencediagram|classdiagram|statediagram(?:-v2)?|erdiagram|journey|gantt|pie|gitgraph|mindmap|timeline|quadrantchart|sankey-beta|xychart-beta)\b/i;
let mermaidLoadPromise = null;
let mermaidInitializedApi = null;
let mermaidRenderSequence = 0;
let mermaidViewer = null;

function createMermaidViewerButton(className, label, text, onClick) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = className;
    button.title = label;
    button.setAttribute('aria-label', label);
    button.textContent = text;
    button.addEventListener('click', onClick);
    return button;
}

function ensureMermaidViewer() {
    if (mermaidViewer) return mermaidViewer;

    const dialog = document.createElement('dialog');
    dialog.className = 'mermaid-viewer';
    dialog.setAttribute('aria-label', '放大查看流程图');
    const header = document.createElement('header');
    header.className = 'mermaid-viewer-header';
    const title = document.createElement('strong');
    title.className = 'mermaid-viewer-title';
    title.textContent = '流程图';
    const actions = document.createElement('div');
    actions.className = 'mermaid-viewer-actions';
    const zoomStatus = document.createElement('span');
    zoomStatus.className = 'mermaid-viewer-zoom-status';
    zoomStatus.setAttribute('role', 'status');
    zoomStatus.setAttribute('aria-live', 'polite');
    const viewport = document.createElement('div');
    viewport.className = 'mermaid-viewer-viewport';
    viewport.setAttribute('role', 'region');
    viewport.setAttribute('aria-label', '放大后的流程图');

    let zoom = 1;
    let activeSvg = null;
    let opener = null;
    const updateZoom = nextZoom => {
        zoom = Math.max(0.5, Math.min(3, nextZoom));
        if (activeSvg) activeSvg.style.width = `${Math.round(zoom * 100)}%`;
        zoomStatus.textContent = `${Math.round(zoom * 100)}%`;
    };
    const close = () => {
        if (dialog.open) dialog.close();
    };
    const closeButton = createMermaidViewerButton(
        'mermaid-viewer-control mermaid-viewer-close',
        '关闭流程图',
        '×',
        close,
    );
    [
        createMermaidViewerButton(
            'mermaid-viewer-control mermaid-viewer-zoom-out',
            '缩小流程图',
            '-',
            () => updateZoom(zoom - 0.25),
        ),
        createMermaidViewerButton(
            'mermaid-viewer-control mermaid-viewer-zoom-in',
            '放大流程图',
            '+',
            () => updateZoom(zoom + 0.25),
        ),
        createMermaidViewerButton(
            'mermaid-viewer-control mermaid-viewer-fit',
            '适配窗口',
            '适配',
            () => {
                viewport.scrollTop = 0;
                viewport.scrollLeft = 0;
                updateZoom(1);
            },
        ),
        zoomStatus,
        closeButton,
    ].forEach(button => actions.appendChild(button));
    header.appendChild(title);
    header.appendChild(actions);
    dialog.appendChild(header);
    dialog.appendChild(viewport);
    dialog.addEventListener('click', event => {
        if (event.target === dialog) close();
    });
    dialog.addEventListener('close', () => {
        viewport.replaceChildren();
        activeSvg = null;
        const previousOpener = opener;
        opener = null;
        previousOpener?.focus?.();
    });
    document.body.appendChild(dialog);

    mermaidViewer = {
        dialog,
        viewport,
        closeButton,
        open(svg, sourceButton) {
            viewport.innerHTML = svg;
            activeSvg = viewport.querySelector('svg');
            if (!activeSvg) return false;
            activeSvg.style.maxWidth = 'none';
            opener = sourceButton;
            updateZoom(1);
            if (!dialog.open) dialog.showModal();
            closeButton.focus();
            return true;
        },
    };
    return mermaidViewer;
}

function openMermaidViewer(svg, sourceButton) {
    try {
        ensureMermaidViewer().open(svg, sourceButton);
    } catch (_error) {
        sourceButton?.focus?.();
        console.warn('Mermaid diagram viewer could not be opened.');
    }
}

function loadMermaidRenderer() {
    if (typeof window !== 'undefined' && window.mermaid?.render) {
        return Promise.resolve(window.mermaid);
    }
    if (mermaidLoadPromise) return mermaidLoadPromise;
    mermaidLoadPromise = new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = '/static/js/vendor/mermaid-tiny-12.2.0.js?v=20261016-mermaid-v1';
        script.async = true;
        script.onload = () => {
            const api = window.mermaid;
            if (api?.render && api?.initialize) resolve(api);
            else reject(new Error('Mermaid renderer was unavailable after load'));
        };
        script.onerror = () => reject(new Error('Mermaid renderer failed to load'));
        document.head.appendChild(script);
    }).catch(error => {
        mermaidLoadPromise = null;
        throw error;
    });
    return mermaidLoadPromise;
}

function keepMermaidSource(code, message) {
    const pre = code?.parentElement;
    pre?.classList?.add('mermaid-render-fallback');
    if (message) pre?.setAttribute?.('title', message);
}

function isMermaidCodeBlock(code) {
    const classes = String(
        code?.className || code?.getAttribute?.('class') || '',
    ).split(/\s+/);
    const source = String(code?.textContent || '').trim();
    return classes.includes('language-mermaid')
        || MERMAID_DIAGRAM_HEADER.test(source);
}

async function renderMermaidDiagrams(root) {
    if (!root?.querySelectorAll) return 0;
    const codeBlocks = Array.from(
        root.querySelectorAll('pre > code'),
    ).filter(isMermaidCodeBlock);
    if (!codeBlocks.length) return 0;

    const renderable = codeBlocks.slice(0, MAX_MERMAID_DIAGRAMS_PER_MESSAGE)
        .filter(code => {
            const source = String(code.textContent || '').trim();
            if (
                !source
                || source.length > MAX_MERMAID_SOURCE_LENGTH
                || /^\s*%%\s*\{(?:init|config)\s*:/im.test(source)
            ) {
                keepMermaidSource(code, '流程图内容超出限制或包含受限配置，已保留源码。');
                return false;
            }
            return true;
        });
    codeBlocks.slice(MAX_MERMAID_DIAGRAMS_PER_MESSAGE).forEach(code => {
        keepMermaidSource(code, '单条消息中的流程图数量超出限制，已保留源码。');
    });
    if (!renderable.length) return 0;

    let api;
    try {
        api = await loadMermaidRenderer();
        if (mermaidInitializedApi !== api) {
            api.initialize({
                startOnLoad: false,
                securityLevel: 'strict',
                suppressErrorRendering: true,
                maxTextSize: MAX_MERMAID_SOURCE_LENGTH,
                maxEdges: 200,
                secure: [
                    'secure', 'securityLevel', 'startOnLoad',
                    'suppressErrorRendering', 'maxTextSize', 'maxEdges',
                    'htmlLabels',
                ],
                flowchart: { htmlLabels: false },
                sequence: { useMaxWidth: true },
                theme: 'neutral',
            });
            mermaidInitializedApi = api;
        }
    } catch (_error) {
        renderable.forEach(code => {
            keepMermaidSource(code, '流程图渲染器不可用，已保留原始源码。');
        });
        return 0;
    }

    let renderedCount = 0;
    for (const code of renderable) {
        const pre = code.parentElement;
        if (!pre?.replaceWith) continue;
        try {
            const id = `chat-mermaid-${++mermaidRenderSequence}`;
            const result = await api.render(id, String(code.textContent || '').trim());
            const svg = DOMPurify.sanitize(result.svg, {
                USE_PROFILES: { html: true, svg: true },
                ADD_TAGS: ['foreignObject'],
                HTML_INTEGRATION_POINTS: { foreignobject: true },
                ALLOW_DATA_ATTR: false,
            });
            if (!/<svg(?:\s|>)/i.test(svg)) {
                throw new Error('Sanitized Mermaid output did not contain SVG');
            }
            const diagram = document.createElement('div');
            diagram.className = 'mermaid-diagram';
            diagram.setAttribute('role', 'group');
            diagram.setAttribute('aria-label', '流程图');
            diagram.innerHTML = svg;
            const zoomButton = createMermaidViewerButton(
                'mermaid-diagram-zoom',
                '放大流程图',
                '放大',
                () => openMermaidViewer(svg, zoomButton),
            );
            diagram.appendChild(zoomButton);
            pre.replaceWith(diagram);
            renderedCount += 1;
        } catch (_error) {
            keepMermaidSource(code, '流程图语法无法解析，已保留原始源码。');
            console.warn('Mermaid diagram rendering failed; original source was kept.');
        }
    }
    return renderedCount;
}

function markdownTokenText(token) {
    if (Array.isArray(token.tokens)) return token.tokens.map(markdownTokenText).join('');
    if (token.type === 'list') return token.items.map(markdownTokenText).join(' ');
    if (token.type === 'table') {
        return [...token.header, ...token.rows.flat()].map(markdownTokenText).join(' ');
    }
    return String(token.text || '');
}

function markdownPreview(content) {
    if (content == null || content === '') return '';
    const source = String(content);
    const tokens = chatMarkdownParser.lexer(source);
    // Stored previews collapse newlines; do not merge later headings into the title.
    if (!source.includes('\n') && tokens[0]?.type === 'heading') {
        return markdownTokenText(tokens[0]).split(/\s+#{1,6}\s+/)[0].trim();
    }
    return tokens.map(markdownTokenText).join(' ').replace(/\s+/g, ' ').trim();
}
