const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const scripts = path.resolve(__dirname, '../../../deployments/advertising/static/js');
const marked = require(path.join(scripts, 'vendor/marked-18.1.1.umd.js'));
const sanitizerCalls = [];

class MockElement {
    constructor(tagName) {
        this.tagName = tagName.toUpperCase();
        this.children = [];
        this.attributes = {};
        this.listeners = {};
        this.style = {};
        this.className = '';
        this.textContent = '';
        this.open = false;
        this.classList = {
            add: name => {
                this.className = `${this.className} ${name}`.trim();
            },
        };
    }

    set innerHTML(value) {
        this._innerHTML = value;
        this.children = [];
        if (String(value).includes('<svg')) this.appendChild(new MockElement('svg'));
    }

    get innerHTML() {
        return this._innerHTML || '';
    }

    appendChild(child) {
        child.parentElement = this;
        this.children.push(child);
        return child;
    }

    replaceChildren(...children) {
        this.children = [];
        children.forEach(child => this.appendChild(child));
    }

    setAttribute(name, value) {
        this.attributes[name] = value;
        if (name === 'class') this.className = value;
    }

    addEventListener(name, listener) {
        this.listeners[name] = listener;
    }

    click() {
        this.listeners.click?.({ target: this, currentTarget: this });
    }

    focus() {
        this.focused = true;
    }

    showModal() {
        this.open = true;
    }

    close() {
        this.open = false;
        this.listeners.close?.({ target: this });
    }

    querySelector(selector) {
        const matches = element => selector.startsWith('.')
            ? element.className.split(/\s+/).includes(selector.slice(1))
            : element.tagName.toLowerCase() === selector.toLowerCase();
        const visit = element => {
            for (const child of element.children) {
                if (matches(child)) return child;
                const nested = visit(child);
                if (nested) return nested;
            }
            return null;
        };
        return visit(this);
    }
}

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

test('escaped newlines in prose render as Markdown line breaks', () => {
    const html = context.formatContent(
        '请确认以下信息：\\n1. 推广目标？\\n2. 预算模式？\\n3. 预算金额？',
    );

    assert.match(html, /请确认以下信息：/);
    assert.match(html, /<ol>/);
    assert.match(html, /推广目标/);
    assert.match(html, /预算模式/);
    assert.doesNotMatch(html, /\\n/);
});

test('escaped newline normalization does not alter code spans or fences', () => {
    const html = context.formatContent(
        '示例 `a\\nb` 后继续\\n第二行\n\n```text\nline\\nliteral\n```',
    );

    assert.match(html, /<code>a\\nb<\/code>/);
    assert.match(html, /line\\nliteral/);
    assert.match(html, /第二行/);
});

test('Mermaid code fences preserve their language marker for diagram rendering', () => {
    const html = context.formatContent('```mermaid\ngraph TD\nA --> B\n```');

    assert.match(html, /<code class="language-mermaid">graph TD\nA --&gt; B\n<\/code>/);
});

test('unlabelled Mermaid code fences remain identifiable for diagram rendering', () => {
    const html = context.formatContent('```\ngraph TD\nA --> B\n```');

    assert.match(html, /<pre><code>graph TD\nA --&gt; B\n<\/code><\/pre>/);
});

test('Mermaid flowcharts render with strict settings and sanitized SVG', async () => {
    const rendered = [];
    const options = [];
    context.window = {
        mermaid: {
            initialize(value) {
                options.push(value);
            },
            async render(id, source) {
                rendered.push({ id, source });
                return { svg: '<svg><path d="M0 0"></path></svg>' };
            },
        },
    };
    context.document = {
        createElement(tagName) {
            return new MockElement(tagName);
        },
        body: new MockElement('body'),
    };
    const pre = {
        classList: { add(name) { this[name] = true; } },
        replaceWith(element) { this.replacedWith = element; },
    };
    const code = { textContent: 'graph TD\nA --> B', parentElement: pre };
    const root = {
        querySelectorAll(selector) {
            return selector === 'pre > code' ? [code] : [];
        },
    };

    await context.renderMermaidDiagrams(root);

    assert.equal(rendered.length, 1);
    assert.equal(rendered[0].source, 'graph TD\nA --> B');
    assert.equal(options[0].securityLevel, 'strict');
    assert.equal(options[0].startOnLoad, false);
    assert.equal(pre.replacedWith.className, 'mermaid-diagram');
    assert.equal(pre.replacedWith.innerHTML, '<svg><path d="M0 0"></path></svg>');
    assert.equal(pre.replacedWith.attributes.role, 'group');
    const zoomButton = pre.replacedWith.children.find(
        child => child.className === 'mermaid-diagram-zoom',
    );
    assert.ok(zoomButton, 'rendered diagrams expose a zoom button');
    zoomButton.click();
    const dialog = context.document.body.children[0];
    assert.equal(dialog.tagName, 'DIALOG');
    assert.equal(dialog.open, true);
    const viewport = dialog.querySelector('.mermaid-viewer-viewport');
    assert.equal(viewport.innerHTML, '<svg><path d="M0 0"></path></svg>');
    assert.equal(viewport.querySelector('svg').style.maxWidth, 'none');
    const zoomIn = dialog.querySelector('.mermaid-viewer-zoom-in');
    zoomIn.click();
    assert.equal(viewport.querySelector('svg').style.width, '125%');
    const fit = dialog.querySelector('.mermaid-viewer-fit');
    fit.click();
    assert.equal(viewport.querySelector('svg').style.width, '100%');
    dialog.querySelector('.mermaid-viewer-close').click();
    assert.equal(dialog.open, false);
    assert.equal(zoomButton.focused, true, 'closing restores focus to the opener');
    const svgSanitizerOptions = sanitizerCalls.at(-1).options;
    assert.ok(svgSanitizerOptions.USE_PROFILES.svg);
    assert.ok(svgSanitizerOptions.USE_PROFILES.html);
    assert.ok(svgSanitizerOptions.ADD_TAGS.includes('foreignObject'));
    assert.equal(svgSanitizerOptions.HTML_INTEGRATION_POINTS.foreignobject, true);
    delete context.window;
    delete context.document;
});

test('Mermaid time-series charts render from a fenced xychart-beta block', async () => {
    const rendered = [];
    context.window = {
        mermaid: {
            initialize() {},
            async render(id, source) {
                rendered.push({ id, source });
                return { svg: '<svg><path d="M0 0"></path></svg>' };
            },
        },
    };
    context.document = {
        createElement(tagName) { return new MockElement(tagName); },
        body: new MockElement('body'),
    };
    const pre = {
        classList: { add(name) { this[name] = true; } },
        replaceWith(element) { this.replacedWith = element; },
    };
    const source = 'xychart-beta\n  x-axis ["10-01", "10-02"]\n  y-axis "USD/CNY" 7.0 --> 7.2\n  line [7.11, 7.12]';
    const code = { textContent: source, parentElement: pre };
    const root = {
        querySelectorAll(selector) {
            return selector === 'pre > code' ? [code] : [];
        },
    };

    const count = await context.renderMermaidDiagrams(root);

    assert.equal(count, 1);
    assert.equal(rendered[0].source, source);
    assert.equal(pre.replacedWith.className, 'mermaid-diagram');
});

test('Mermaid repairs quoted edge labels from generated diagrams before rendering', async () => {
    const rendered = [];
    context.window = {
        mermaid: {
            initialize() {},
            async render(_id, source) {
                rendered.push(source);
                return { svg: '<svg></svg>' };
            },
        },
    };
    context.document = {
        createElement(tagName) {
            return new MockElement(tagName);
        },
        body: new MockElement('body'),
    };
    const pre = {
        classList: { add() {} },
        replaceWith(element) { this.replacedWith = element; },
    };
    const code = {
        className: 'language-mermaid',
        textContent: [
            'flowchart TB',
            'subgraph Traditional["传统手动模式"]',
            '    T1["手动选受众"]',
            'end',
            'Traditional --> "操作复杂<br>学习成本高"',
            'Smart --> "简单易用<br>算法驱动"',
        ].join('\n'),
        parentElement: pre,
    };
    const root = {
        querySelectorAll: selector => selector === 'pre > code' ? [code] : [],
    };

    await context.renderMermaidDiagrams(root);

    assert.equal(rendered.length, 1);
    assert.match(
        rendered[0],
        /Traditional --> ChatGeneratedNode1\["操作复杂<br>学习成本高"\]/,
    );
    assert.match(
        rendered[0],
        /Smart --> ChatGeneratedNode2\["简单易用<br>算法驱动"\]/,
    );
    assert.equal(pre.replacedWith.className, 'mermaid-diagram');
    delete context.window;
    delete context.document;
});

test('Mermaid mindmaps render as hierarchy diagrams with escaped labels', async () => {
    const rendered = [];
    context.window = {
        mermaid: {
            initialize() {},
            async render(_id, source) {
                rendered.push(source);
                return { svg: '<svg></svg>' };
            },
        },
    };
    context.document = {
        createElement(tagName) {
            return new MockElement(tagName);
        },
        body: new MockElement('body'),
    };
    const pre = {
        classList: { add() {} },
        replaceWith(element) { this.replacedWith = element; },
    };
    const code = {
        className: 'language-mermaid',
        textContent: [
            'mindmap',
            '  root((TikTok 层级约束))',
            '    Campaign层',
            '      Objective决定AdGroup可选项',
            '      Smart+/Spark类型影响素材来源',
            '    Ad Group层',
            '      定向规模<10k导致探索受限',
            '      修改预算>20%重置学习期',
            '    Ad/Creative层',
            '      Spark必须绑定已授权Identity',
        ].join('\n'),
        parentElement: pre,
    };

    const renderedCount = await context.renderMermaidDiagrams({
        querySelectorAll: selector => selector === 'pre > code' ? [code] : [],
    });

    assert.equal(renderedCount, 1);
    assert.equal(pre.replacedWith.className, 'mermaid-diagram');
    assert.match(rendered[0], /^flowchart TB\n/);
    assert.match(rendered[0], /ChatMindmapNode0\(\("TikTok 层级约束"\)\)/);
    assert.match(rendered[0], /ChatMindmapNode0 --> ChatMindmapNode1\["Campaign层"\]/);
    assert.match(rendered[0], /ChatMindmapNode1 --> ChatMindmapNode2\["Objective决定AdGroup可选项"\]/);
    assert.match(rendered[0], /Smart\+\/Spark类型影响素材来源/);
    assert.match(rendered[0], /定向规模&lt;10k导致探索受限/);
    assert.match(rendered[0], /修改预算&gt;20%重置学习期/);
    assert.match(rendered[0], /ChatMindmapNode0 --> ChatMindmapNode\d+\["Ad\/Creative层"\]/);
    delete context.window;
    delete context.document;
});

test('Mermaid mindmaps keep malformed top-level nodes as source', async () => {
    const rendered = [];
    context.window = {
        mermaid: {
            initialize() {},
            async render(_id, source) {
                rendered.push(source);
                return { svg: '<svg></svg>' };
            },
        },
    };
    context.document = {
        createElement: tagName => new MockElement(tagName),
        body: new MockElement('body'),
    };
    const pre = {
        attributes: {},
        classList: { add() {} },
        setAttribute(name, value) { this.attributes[name] = value; },
        replaceWith(element) { this.replacedWith = element; },
    };
    const code = {
        className: 'language-mermaid',
        textContent: 'mindmap\n  root((Root))\n    Child\n  Orphan',
        parentElement: pre,
    };

    const renderedCount = await context.renderMermaidDiagrams({
        querySelectorAll: selector => selector === 'pre > code' ? [code] : [],
    });

    assert.equal(renderedCount, 0);
    assert.deepEqual(rendered, []);
    assert.equal(pre.replacedWith, undefined);
    assert.equal(pre.attributes['data-render-failure'], 'syntax');
    delete context.window;
    delete context.document;
});

test('Mermaid renders all diagrams in a long answer beyond the previous limit', async () => {
    const rendered = [];
    context.window = {
        mermaid: {
            initialize() {},
            async render(_id, source) {
                rendered.push(source);
                return { svg: '<svg></svg>' };
            },
        },
    };
    context.document = {
        createElement(tagName) {
            return new MockElement(tagName);
        },
        body: new MockElement('body'),
    };
    const codeBlocks = Array.from({ length: 10 }, (_, index) => {
        const pre = {
            classList: { add() {} },
            replaceWith(element) { this.replacedWith = element; },
        };
        return {
            className: 'language-mermaid',
            textContent: `flowchart TD\nA${index} --> B${index}`,
            parentElement: pre,
            pre,
        };
    });

    const renderedCount = await context.renderMermaidDiagrams({
        querySelectorAll: selector => selector === 'pre > code' ? codeBlocks : [],
    });

    assert.equal(renderedCount, 10);
    assert.equal(rendered.length, 10);
    assert.ok(codeBlocks.every(code => code.pre.replacedWith?.className === 'mermaid-diagram'));
    delete context.window;
    delete context.document;
});

test('Mermaid preserves source beyond the expanded per-message safety limit', async () => {
    const rendered = [];
    context.window = {
        mermaid: {
            initialize() {},
            async render(_id, source) {
                rendered.push(source);
                return { svg: '<svg></svg>' };
            },
        },
    };
    context.document = {
        createElement(tagName) {
            return new MockElement(tagName);
        },
        body: new MockElement('body'),
    };
    const codeBlocks = Array.from({ length: 33 }, (_, index) => {
        const pre = {
            attributes: {},
            classList: { add() {} },
            setAttribute(name, value) { this.attributes[name] = value; },
            replaceWith(element) { this.replacedWith = element; },
        };
        return {
            className: 'language-mermaid',
            textContent: `flowchart TD\nA${index} --> B${index}`,
            parentElement: pre,
            pre,
        };
    });

    const renderedCount = await context.renderMermaidDiagrams({
        querySelectorAll: selector => selector === 'pre > code' ? codeBlocks : [],
    });

    assert.equal(renderedCount, 32);
    assert.equal(rendered.length, 32);
    assert.equal(codeBlocks[32].pre.replacedWith, undefined);
    assert.equal(codeBlocks[32].pre.attributes['data-render-failure'], 'restricted');
    delete context.window;
    delete context.document;
});

test('Mermaid render failures preserve source and identify syntax errors', async () => {
    context.window = {
        mermaid: {
            initialize() {},
            async render() {
                throw new Error('parser detail is not exposed');
            },
        },
    };
    context.document = { createElement: tagName => new MockElement(tagName) };
    const pre = {
        attributes: {},
        classList: { add() {} },
        setAttribute(name, value) { this.attributes[name] = value; },
        replaceWith() {},
    };
    const code = {
        className: 'language-mermaid',
        textContent: 'flowchart TB\nA --> B',
        parentElement: pre,
    };

    await context.renderMermaidDiagrams({
        querySelectorAll: selector => selector === 'pre > code' ? [code] : [],
    });

    assert.equal(pre.attributes['data-render-failure'], 'syntax');
    assert.equal(
        pre.attributes.title,
        '流程图语法或安全校验失败，已保留源码；请检查节点 ID 和连线写法。',
    );
    delete context.window;
    delete context.document;
});

test('Mermaid configuration directives stay visible and are not executed', async () => {
    const rendered = [];
    context.window = {
        mermaid: {
            initialize() {},
            async render(_id, source) {
                rendered.push(source);
                return { svg: '<svg></svg>' };
            },
        },
    };
    context.document = {
        createElement() {
            return {
                attributes: {},
                setAttribute(name, value) {
                    this.attributes[name] = value;
                },
            };
        },
    };
    const pre = {
        classList: { add(name) { this[name] = true; } },
        setAttribute(name, value) { this[name] = value; },
        replaceWith(element) { this.replacedWith = element; },
    };
    const code = {
        className: 'language-mermaid',
        textContent: '%%{init: {"securityLevel":"loose"}}%%\ngraph TD\nA --> B',
        parentElement: pre,
    };
    const root = {
        querySelectorAll: selector => selector === 'pre > code' ? [code] : [],
    };

    await context.renderMermaidDiagrams(root);

    assert.deepEqual(rendered, []);
    assert.equal(pre.replacedWith, undefined);
    assert.equal(pre.title, '流程图内容超出限制或包含受限配置，已保留源码。');
    delete context.window;
    delete context.document;
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
