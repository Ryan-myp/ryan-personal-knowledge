// Real chat UI smoke test. It loads and edits a template but never confirms a write.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

async function main() {
    const baseURL = process.env.AD_AGENT_TEST_URL || 'http://127.0.0.1:8766';
    assert(['localhost', '127.0.0.1'].includes(new URL(baseURL).hostname));
    const output = path.resolve(process.env.AD_AGENT_TEST_OUTPUT || 'outputs/template-dialog');
    fs.mkdirSync(output, { recursive: true });
    const browser = await chromium.launch({
        headless: true, channel: process.env.PLAYWRIGHT_BROWSER_CHANNEL || 'chrome',
    });
    let page;
    try {
        page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
        page.setDefaultTimeout(500_000);
        const errors = [];
        const requests = [];
        const providerLookups = process.env.AD_AGENT_VERIFY_PROVIDER_LOOKUPS === '1';
        if (!providerLookups) {
            await page.route('**/parameter-options/resolve?*', route => route.fulfill({
                contentType: 'application/json',
                body: JSON.stringify({ options: [], selections: [], data_status: 'test_stub' }),
            }));
        }
        page.on('pageerror', error => errors.push(error.message));
        page.on('request', request => {
            if (!request.url().endsWith('/chat/stream')) return;
            const body = request.postDataJSON();
            assert(!body.confirmed, 'Smoke test must never confirm a live write');
            requests.push(body);
        });
        await page.goto(baseURL);
        await page.waitForLoadState('networkidle');
        const send = async text => {
            await page.locator('#userInput').fill(text);
            const response = page.waitForResponse(result =>
                result.url().endsWith('/chat/stream') && result.request().method() === 'POST');
            await page.locator('#userInput').press('Enter');
            const result = await response;
            assert.equal(result.status(), 200);
            await result.finished();
            await page.waitForFunction(() => !isSending);
        };
        await send('创建 TikTok 广告系列，先列出测试账号的内置模板让我选择，不要提交创建。');
        const choice = page.locator('.clarification-option').filter({ hasText: '商品目录销售' });
        if (await choice.count()) {
            const response = page.waitForResponse(result => result.url().endsWith('/chat/stream'));
            await choice.first().click();
            await (await response).finished();
            await page.waitForFunction(() => !isSending);
        } else {
            await send('TikTok 测试账号 · 商品目录销售');
        }
        await page.locator('#creation-workbench-host .creation-card').waitFor({ state: 'visible' });
        const initial = await page.evaluate(() => {
            const card = creationCardState.get(workbenchState.activeCardId);
            return {
                template_id: card?.template_id,
                blueprint_id: card?.blueprint_id,
                fields: Object.fromEntries((card?.fields || []).map(field => [field.path, field.value])),
            };
        });
        assert.equal(initial.blueprint_id, 'tiktok.product_sales_video');
        assert(initial.template_id);
        for (const field of ['ad_group.catalog_id', 'ad.video_id', 'ad.identity_id', 'ad.call_to_action_id']) {
            assert(initial.fields[field], `Template field ${field} is missing`);
        }
        const name = `template_ui_${Date.now()}`;
        const start = new Date(Date.now() + 86_400_000).toISOString().slice(0, 10);
        const end = new Date(Date.now() + 172_800_000).toISOString().slice(0, 10);
        await send(`Campaign 名称：${name}，开始时间：${start} 00:00 UTC，结束时间：${end} 00:00 UTC，总预算：50 USD。先更新创建区域的草稿，不要提交。`);
        const updated = await page.evaluate(() => {
            const card = creationCardState.get(workbenchState.activeCardId);
            return {
                ready: card?.ready,
                fields: Object.fromEntries((card?.fields || []).map(field => [field.path, field.value])),
            };
        });
        assert.equal(updated.fields['campaign.campaign_name'], name);
        assert.equal(updated.fields['ad_group.budget'], 50);
        assert(updated.fields['ad_group.schedule_start_time']);
        assert(updated.fields['ad_group.schedule_end_time']);
        for (const field of ['ad_group.catalog_id', 'ad.video_id', 'ad.identity_id', 'ad.call_to_action_id']) {
            assert.deepEqual(updated.fields[field], initial.fields[field]);
        }
        assert.equal(requests.at(-1).creation_template_id, initial.template_id);
        await page.screenshot({ path: path.join(output, 'desktop.png'), fullPage: true });
        await page.setViewportSize({ width: 390, height: 844 });
        await page.screenshot({ path: path.join(output, 'mobile.png'), fullPage: true });
        assert.deepEqual(errors, []);
        console.log(JSON.stringify({
            verified: true, confirmed_writes: 0, request_count: requests.length,
            ready: updated.ready, template_id: initial.template_id,
            provider_lookups: providerLookups ? 'live' : 'stubbed', output,
        }, null, 2));
    } catch (error) {
        if (page) await page.screenshot({ path: path.join(output, 'failure.png'), fullPage: true });
        throw error;
    } finally {
        await browser.close();
    }
}

main().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
