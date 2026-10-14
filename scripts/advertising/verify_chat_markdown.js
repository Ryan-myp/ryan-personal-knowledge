const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const root = path.resolve(__dirname, '../..');
const output = path.resolve(process.argv[2] || path.join(root, 'outputs/markdown-rendering'));
const session = process.argv[3];
const baseURL = process.env.AD_AGENT_TEST_URL || 'http://127.0.0.1:8765';
const base = new URL(baseURL);
assert.ok(['127.0.0.1', 'localhost', '[::1]'].includes(base.hostname), 'Local service only');

async function verify() {
    fs.mkdirSync(output, { recursive: true });
    const browser = await chromium.launch({ channel: 'chrome', headless: true });
    const failures = [];
    try {
        const context = await browser.newContext({
            viewport: { width: 1557, height: 900 },
            extraHTTPHeaders: process.env.AD_AGENT_API_KEY
                ? { 'X-API-Key': process.env.AD_AGENT_API_KEY } : {},
        });
        await context.route('**/*', route => {
            const request = route.request();
            if (new URL(request.url()).origin !== base.origin || request.method() !== 'GET') {
                return route.abort();
            }
            return route.continue();
        });
        await context.addInitScript(() => localStorage.setItem('ad-agent-theme', 'light'));
        const page = await context.newPage();
        page.on('pageerror', error => failures.push(error.message));
        await page.goto(baseURL);
        await page.waitForLoadState('networkidle');
        await page.waitForFunction(() => typeof formatContent === 'function' && typeof loadConversation === 'function');

        const security = await page.evaluate(() => {
            const host = document.createElement('div');
            host.innerHTML = formatContent([
                '[Danger](javascript:alert(1))',
                '[Data](data:text/html;base64,PHNjcmlwdD4=)',
                '<script>window.__markdownAttack = true</script>',
                '<img src=x onerror="window.__markdownAttack = true">',
                '<svg onload="window.__markdownAttack = true"></svg>',
                '<iframe srcdoc="<script>alert(1)</script>"></iframe>',
                '![Remote](https://example.test/tracking.png)',
                '- [ ] Disabled task',
            ].join('\n\n'));
            document.body.appendChild(host);
            const result = {
                activeNodes: host.querySelectorAll('script,img,svg,iframe,object,form,style').length,
                badLinks: [...host.querySelectorAll('a[href]')].filter(link =>
                    /^(javascript|data|vbscript):/i.test(link.getAttribute('href').trim())
                ).length,
                handlers: [...host.querySelectorAll('*')].flatMap(node =>
                    [...node.attributes].filter(attribute => /^on/i.test(attribute.name))
                ).length,
                enabledTasks: host.querySelectorAll('input:not([disabled])').length,
                executed: Boolean(window.__markdownAttack),
            };
            host.remove();
            return result;
        });
        assert.deepEqual(security, {
            activeNodes: 0, badLinks: 0, handlers: 0, enabledTasks: 0, executed: false,
        });

        if (session) {
            const response = await context.request.get(`${baseURL}/sessions/${encodeURIComponent(session)}?limit=500`);
            assert.ok(response.ok(), 'Conversation must be accessible');
            const conversation = await response.json();
            await page.evaluate(id => loadConversation(id), session);
            await page.waitForSelector('.message.agent .message-content-text h2');
            const expected = conversation.messages.filter(message =>
                ['user', 'assistant'].includes(message.role)
            ).length;
            assert.equal(await page.locator('#chatContainer > .message').count(), expected);
            const preview = await page.locator('.chat-history-item.active .chat-history-preview').innerText();
            assert.doesNotMatch(preview, /^#+\s|`|\*\*/);
        } else {
            await page.evaluate(() => addMessage([
                '## Campaign diagnosis', '### Summary',
                '| Resource | Empty | State |\n|---|---|---|\n| Campaign | | `PAUSED` |',
                '---', '#### Budget', '```text', '## literal heading', 'budget = 50', '```',
                '- [ ] Check account', '- [x] Checked',
            ].join('\n\n')));
        }
        const live = await page.locator('.message.agent .message-content-text').last().evaluate(node => ({
            headings: node.querySelectorAll('h2,h3,h4').length,
            breaks: node.querySelectorAll('hr').length,
            tables: node.querySelectorAll('.markdown-table-scroll > table.data-table').length,
            codeBlocks: node.querySelectorAll('pre > code').length,
            tasks: node.querySelectorAll('input[type="checkbox"][disabled]').length,
            rawHeadingMarkers: [...node.querySelectorAll('h1,h2,h3,h4,h5,h6')].some(heading =>
                /^#{1,6}\s/.test(heading.textContent)
            ),
        }));
        assert.ok(live.headings >= 3);
        assert.ok(live.breaks > 0);
        assert.ok(live.tables > 0);
        assert.ok(live.codeBlocks > 0);
        assert.ok(live.tasks > 0);
        assert.equal(live.rawHeadingMarkers, false);

        const heading = page.locator('.message.agent .message-content-text').last().locator('h2').first();
        await heading.evaluate(node => node.scrollIntoView({ block: 'start' }));
        await page.screenshot({ path: path.join(output, 'desktop.png'), fullPage: true });
        await page.setViewportSize({ width: 390, height: 844 });
        await heading.evaluate(node => node.scrollIntoView({ block: 'start' }));
        await page.screenshot({ path: path.join(output, 'mobile.png'), fullPage: true });
        const layout = await page.evaluate(() => ({
            viewport: window.innerWidth,
            page: document.documentElement.scrollWidth,
            tableWidths: [...document.querySelectorAll('.markdown-table-scroll')].map(node => ({
                visible: node.clientWidth, content: node.scrollWidth,
            })),
        }));
        assert.ok(layout.page <= layout.viewport + 1, 'Markdown must not overflow the page');
        await page.evaluate(() => applyTheme('dark'));
        await page.screenshot({ path: path.join(output, 'mobile-dark.png'), fullPage: true });
        assert.deepEqual(failures, []);
        fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify({ security, live, layout }, null, 2));
        console.log(JSON.stringify({ passed: true, security, live, layout, output }));
    } finally {
        await browser.close();
    }
}

verify().catch(error => {
    console.error(error.message);
    process.exitCode = 1;
});
