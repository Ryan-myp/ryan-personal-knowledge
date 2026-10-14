const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const scripts = path.resolve(__dirname, '../../../deployments/advertising/static/js');
const marked = require(path.join(scripts, 'vendor/marked-18.1.1.umd.js'));
const sanitizerCalls = [];
// This mock checks sanitizer invocation; the browser check exercises real DOMPurify.
const context = {
    marked,
    DOMPurify: {
        sanitize(html, options) {
            sanitizerCalls.push({ html, options });
            return html;
        },
    },
    escapeHtml: value => String(value).replace(/[&<>"']/g, character => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    })[character]),
};
vm.runInNewContext(fs.readFileSync(path.join(scripts, 'chat-markdown.js'), 'utf8'), context, {
    filename: path.join(scripts, 'chat-markdown.js'),
});

test('diagnostic reply renders heading levels and thematic breaks', () => {
    const html = context.formatContent('## Campaign 1878914955316449\n\n### Summary\n\n---\n\n#### Budget');
    assert.match(html, /<h2>Campaign 1878914955316449<\/h2>/);
    assert.match(html, /<h3>Summary<\/h3>/);
    assert.match(html, /<h4>Budget<\/h4>/);
    assert.match(html, /<hr\s*\/?>/);
    assert.doesNotMatch(html, /## |---/);
});

test('fenced code preserves line breaks and literal markdown', () => {
    const html = context.formatContent('```text\n## literal heading\n**literal bold**\nbudget = 50\n```');
    assert.match(html, /<pre><code[^>]*>## literal heading\n\*\*literal bold\*\*\nbudget = 50\n<\/code><\/pre>/);
    assert.doesNotMatch(html, /<h2>|<strong>/);
});

test('tables retain empty cells, escaped pipes and inline code', () => {
    const html = context.formatContent('| Name | Empty | Note |\n|---|---|---|\n| `Campaign` | | a\\|b |');
    assert.match(html, /class="markdown-table-scroll"/);
    assert.match(html, /<table class="data-table">/);
    assert.match(html, /<td><code>Campaign<\/code><\/td>\s*<td><\/td>\s*<td>a\|b<\/td>/);
});

test('lists, quotes, task items, emphasis and links use semantic elements', () => {
    const html = context.formatContent(
        '> **Notice**\n\n1. *First*\n2. ~~Second~~\n\n- [ ] Check budget\n- [x] Checked\n\n[Guide](https://example.test/docs)',
    );
    assert.match(html, /<blockquote>/);
    assert.match(html, /<ol>/);
    assert.match(html, /<em>First<\/em>/);
    assert.match(html, /<del>Second<\/del>/);
    assert.match(html, /<input[^>]*disabled/);
    assert.match(html, /href="https:\/\/example.test\/docs"/);
});

test('raw HTML remains literal and all parsed output goes through the sanitizer', () => {
    const html = context.formatContent('<script>alert(1)</script>\n\n<img src=x onerror=alert(1)>');
    assert.doesNotMatch(html, /<script>|<img/);
    assert.match(html, /&lt;script&gt;/);
    const last = sanitizerCalls.at(-1);
    assert.equal(last.options.ALLOW_DATA_ATTR, false);
    assert.ok(last.options.ALLOWED_TAGS.includes('h4'));
    assert.ok(!last.options.ALLOWED_TAGS.includes('img'));
    assert.ok(!last.options.ALLOWED_ATTR.includes('style'));
    assert.ok(!last.options.ALLOWED_ATTR.includes('onclick'));
});

test('history preview keeps readable text without markdown syntax', () => {
    assert.equal(context.markdownPreview('## Campaign **123**\n\n### Summary'), 'Campaign 123 Summary');
    assert.equal(context.markdownPreview('Ad Set `123` has **2** ads.'), 'Ad Set 123 has 2 ads.');
    assert.equal(context.markdownPreview('[Guide](https://example.test/docs)'), 'Guide');
    assert.equal(context.markdownPreview('- [ ] Check budget\n- [x] Checked'), 'Check budget Checked');
});

test('collapsed heading previews do not expose the next section markup', () => {
    assert.equal(
        context.markdownPreview('## Campaign 123 diagnosis ### Summary | State | Value |'),
        'Campaign 123 diagnosis',
    );
});

test('table previews include cell text without table separators', () => {
    assert.equal(
        context.markdownPreview('| Resource | State |\n|---|---|\n| Campaign | **PAUSED** |'),
        'Resource State Campaign PAUSED',
    );
    assert.equal(context.markdownPreview('   '), '');
});

test('empty replies and CRLF input remain well-defined', () => {
    assert.equal(context.formatContent(null), '');
    assert.equal(context.formatContent(''), '');
    assert.equal(context.markdownPreview(null), '');
    assert.match(context.formatContent('## Title\r\n\r\nText'), /<h2>Title<\/h2>\s*<p>Text<\/p>/);
});
