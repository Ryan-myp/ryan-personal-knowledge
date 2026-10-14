const chatMarkdownRenderer = new marked.Renderer();
const chatMarkdownTable = chatMarkdownRenderer.table;

chatMarkdownRenderer.html = ({ text }) => escapeHtml(text);
chatMarkdownRenderer.table = function (token) {
    const table = chatMarkdownTable.call(this, token)
        .replace('<table>', '<table class="data-table">');
    return `<div class="markdown-table-scroll" role="region" aria-label="Table" tabindex="0">${table}</div>`;
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
