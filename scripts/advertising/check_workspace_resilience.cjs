// Offline acceptance: no requests reach an Agent service or external provider.
const {chromium} = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const base = path.resolve(__dirname, '../../agents/deployments/advertising');
const output = path.resolve(process.argv[2] || '/tmp/workspace-resilience');
fs.mkdirSync(output, {recursive:true});
const origin = 'http://127.0.0.1:48792';
const evidence = {network:'All requests fulfilled from local files or in-memory fixtures; no live API calls', errors:[], checks:[]};
const settings = {models:{profiles:[{id:'fixture',name:'离线测试配置',model:'fixture-chat',
    purpose:'chat',source:'vault',active:true,api_key_configured:true}]}, providers:{}, web_search:{backend:'duckduckgo'}};

async function openPage(browser, {preload=true, delay=0, failModule=false}={}) {
    const context = await browser.newContext({viewport:{width:1440,height:900}});
    const page = await context.newPage();
    const control = {failModule, failRead:'', failWrite:false, scripts:[], settingsReads:0, writes:0};
    page.on('pageerror', error => evidence.errors.push(error.message));
    await page.route('**/*', async route => {
        const request = route.request(), url = new URL(request.url());
        if (url.origin !== origin) return route.abort();
        if (url.pathname === '/' || url.pathname.startsWith('/static/')) {
            const file = url.pathname === '/' ? path.join(base,'templates/chat.html') : path.join(base,url.pathname);
            if (!file.startsWith(base+path.sep) || !fs.existsSync(file)) return route.fulfill({status:404,body:'missing'});
            if (file.endsWith('.js')) {
                control.scripts.push(url.pathname);
                if (delay) await new Promise(done => setTimeout(done,delay));
                if (control.failModule && file.endsWith('/chat-media.js')) return route.abort();
            }
            if (file.endsWith('/chat.js') && !preload) return route.fulfill({contentType:'text/javascript',
                body:fs.readFileSync(file,'utf8').replace('        prepare(index);','        // Sequential-download baseline')});
            return route.fulfill({path:file});
        }
        if (control.failRead === url.pathname) return route.fulfill({contentType:'text/html',body:'<html>invalid gateway response</html>'});
        if (url.pathname.startsWith('/settings') && request.method() !== 'GET') {
            control.writes++;
            if (control.failWrite) return route.fulfill({status:422,json:{detail:[{loc:['body','api_key'],input:'test-only-placeholder'}]}});
            return route.fulfill({json:settings});
        }
        let data = {};
        if (url.pathname === '/settings') {control.settingsReads++; data = settings;}
        else if (url.pathname === '/sessions') data = {sessions:[]};
        else if (url.pathname.includes('execution-mode')) data = {mode:'dry_run',available_modes:['dry_run']};
        else if (url.pathname === '/knowledge/catalog') data = {documents:[{document_id:'example',title:'知识目录测试',excerpt:'保留已加载内容。',platform:'all'}]};
        else if (url.pathname === '/knowledge/documents') data = {documents:[]};
        else if (url.pathname === '/skills') data = {builtin_skills:[{skill_name:'example',description:'技能列表测试',source:'builtin',version:'1.0.0',status:'published'}]};
        else if (url.pathname === '/mcp/servers') data = {servers:[{server_id:'example',name:'工具列表测试',source:'external',status:'draft',tools:[]}]};
        return route.fulfill({json:data});
    });
    const start = Date.now();
    await page.goto(origin);
    const ready = async () => {
        await page.waitForFunction(() => typeof newChat === 'function' && document.getElementById('workspaceBootStatus').hidden);
        return Date.now()-start;
    };
    return {context,page,control,ready};
}

(async () => {
    const browser = await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE || undefined});
    try {
        const baseline = await openPage(browser,{preload:false,delay:50});
        const sequentialMs = await baseline.ready();
        await baseline.context.close();
        const optimized = await openPage(browser,{delay:50});
        const preloadedMs = await optimized.ready();
        evidence.startup = {simulatedDelayPerScriptMs:50,sequentialMs,preloadedMs,
            requests:optimized.control.scripts.length,uniqueScripts:new Set(optimized.control.scripts).size};
        assert.ok(preloadedMs < sequentialMs, 'bounded preload should reduce injected network waiting');
        assert.equal(evidence.startup.requests,evidence.startup.uniqueScripts,'preloads must be reused');
        await optimized.context.close();

        const {context,page,control,ready} = await openPage(browser,{failModule:true});
        await page.locator('#workspaceBootRetry').waitFor({state:'visible'});
        control.failModule = false;
        await page.locator('#workspaceBootRetry').click();
        await ready();
        evidence.checks.push('failed-module-retry-without-replaying-loaded-modules');

        const catalogs = [
            ['knowledge','/knowledge/catalog','toggleKnowledgePopover','loadKnowledgeCatalog'],
            ['skills','/skills','openSkillManager','loadManagedSkills'],
            ['mcp','/mcp/servers','openMCPManager','loadMCPServers'],
        ];
        for (const [kind,endpoint,open,load] of catalogs) {
            await page.evaluate(name => window[name](),open);
            await page.locator(`.${kind}-catalog-row`).first().waitFor();
            control.failRead = endpoint;
            await page.evaluate(name => window[name](),load);
            assert.equal(await page.locator(`.${kind}-catalog-row`).count(),1);
            assert.match(await page.locator(`#${kind}CatalogStatus`).textContent(),/响应格式/);
            await page.screenshot({path:path.join(output,`${kind}-error-desktop.png`)});
            control.failRead = '';
            await page.locator(`#${kind}CatalogRetry`).click();
            await page.locator(`#${kind}CatalogStatus`).waitFor({state:'hidden'});
            evidence.checks.push(`${kind}-preserved-and-recovered`);
        }

        await page.evaluate(() => openAgentSettings('providers'));
        await page.locator('#agentProviderFields input').first().waitFor();
        const credential = page.locator('#agentProviderFields input[name="client_id"]');
        await credential.fill('test-only-placeholder');
        await page.locator('#settingsWebSearchTab').click();
        await page.locator('#settingsProvidersTab').click();
        assert.equal(await credential.inputValue(),'test-only-placeholder');
        await page.evaluate(() => closeAgentSettings());
        await page.evaluate(() => openAgentSettings('providers'));
        assert.equal(control.settingsReads,1);
        await page.getByRole('button',{name:'刷新配置',exact:true}).click();
        await page.waitForFunction(() => document.getElementById('agentSettingsStatus').textContent.includes('编辑已保留'));
        assert.equal(await credential.inputValue(),'test-only-placeholder');
        await page.locator('#settingsDiscardDraft').click();
        assert.equal(await credential.inputValue(),'');
        evidence.checks.push('settings-drafts-survive-tab-reopen-refresh-and-can-be-discarded');

        await page.locator('#settingsModelsTab').click();
        await page.locator('#agentModelApiKey').fill('test-only-placeholder');
        control.failWrite = true;
        await page.getByRole('button',{name:'保存并切换',exact:true}).click();
        await page.waitForFunction(() => document.getElementById('agentSettingsStatus').textContent.includes('校验失败'));
        assert.equal(await page.locator('#agentModelApiKey').inputValue(),'test-only-placeholder');
        assert.doesNotMatch(await page.locator('#agentSettingsStatus').textContent(),/test-only-placeholder/);
        control.failWrite = false;
        await page.getByRole('button',{name:'保存并切换',exact:true}).click();
        await page.waitForFunction(() => document.getElementById('agentSettingsStatus').textContent.includes('已保存'));
        assert.equal(await page.locator('#agentModelApiKey').inputValue(),'');
        assert.equal(control.writes,2);
        evidence.checks.push('settings-failure-preserves-input-success-clears-secret');

        for (const theme of ['light','dark']) {
            await page.evaluate(value => applyTheme(value), theme);
            for (const width of [1440,390]) {
                await page.setViewportSize({width,height:900});
                await page.evaluate(() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done))));
                await page.screenshot({path:path.join(output,`settings-${theme}-${width}.png`),animations:'disabled'});
                assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth+1));
                if (width === 390) {
                    const layout = await page.evaluate(() => ({
                        headerCount:document.querySelectorAll('.global-topbar').length,
                        header:document.querySelector('.global-topbar').getBoundingClientRect().toJSON(),
                        surface:document.getElementById('agentSettingsOverlay').getBoundingClientRect().toJSON(),
                        bottomElement:document.elementFromPoint(20,840)?.tagName,
                    }));
                    assert.equal(layout.headerCount,1);
                    assert.equal(layout.header.y,0);
                    evidence[`mobile-${theme}`] = layout;
                }
                await page.evaluate(() => openMCPManager());
                control.failRead = '/mcp/servers';
                await page.evaluate(() => loadMCPServers());
                await page.screenshot({path:path.join(output,`catalog-${theme}-${width}.png`)});
                const bounds = await page.locator('#mcpCatalogStatus').boundingBox();
                assert.ok(bounds.x >= 0 && bounds.x+bounds.width <= width+1);
                control.failRead = '';
                await page.evaluate(() => openAgentSettings());
            }
        }
        evidence.checks.push('light-dark-desktop-mobile-layout');
        await context.close();
        assert.deepEqual(evidence.errors,[]);
        fs.writeFileSync(path.join(output,'evidence.json'),JSON.stringify(evidence,null,2));
        process.stdout.write(JSON.stringify(evidence,null,2));
    } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode=1;});
