const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function boot(version = 'content-version-a') {
    const elements = new Map();
    const scripts = [], links = [];
    const element = () => ({hidden: false, textContent: '', dataset: {}, setAttribute() {},
        remove() {this.removed = true;}});
    for (const id of ['workspaceBootStatus', 'workspaceBootMessage', 'workspaceBootRetry']) elements.set(id, element());
    const listeners = new Map();
    let reloads = 0;
    const context = {console, URL, setTimeout: () => 1, clearTimeout() {}, window: {
        addEventListener(name, fn) { listeners.set(name, fn); },
        removeEventListener(name, fn) { if (listeners.get(name) === fn) listeners.delete(name); },
        location: {reload() { reloads++; }},
    }, document: {
        currentScript: {src: `http://localhost/static/js/chat.js?v=${version}`},
        getElementById: id => elements.get(id), createElement: element,
        head: {appendChild(node) { (node.rel === 'preload' ? links : scripts).push(node); }},
    }};
    vm.runInNewContext(fs.readFileSync(path.resolve(__dirname,
        '../../../deployments/advertising/static/js/chat.js'), 'utf8'), context);
    return {scripts, links, elements, listeners, get reloads() { return reloads; }};
}

test('boot preloads a bounded window while executing scripts strictly in order', () => {
    const {scripts, links, elements} = boot();
    assert.equal(scripts.length, 1);
    assert.ok(links.length >= 2 && links.length <= 4);
    assert.match(scripts[0].src, /marked/);
    scripts[0].onload();
    assert.match(scripts[1].src, /purify/);
    for (let i = 1; i < scripts.length; i++) {
        scripts[i].onload();
        assert.ok(links.filter(link => !link.removed).length <= 4);
    }
    assert.equal(new Set(scripts.map(script => script.src)).size, scripts.length);
    assert.equal(elements.get('workspaceBootStatus').hidden, true);
});

test('all dependencies and preloads inherit the served loader version', () => {
    for (const version of ['content-version-a', 'content-version-b']) {
        const {scripts, links} = boot(version);
        for (let i = 0; i < scripts.length; i++) scripts[i].onload();
        for (const resource of [...scripts.map(row => row.src), ...links.map(row => row.href)]) {
            assert.equal(new URL(resource, 'http://localhost').searchParams.get('v'), version);
        }
    }
});

test('failed module offers retry at that module without reexecuting previous scripts', () => {
    const {scripts, elements} = boot();
    scripts[0].onload();
    scripts[1].onerror();
    assert.match(elements.get('workspaceBootMessage').textContent, /加载失败/);
    assert.equal(elements.get('workspaceBootRetry').hidden, false);
    elements.get('workspaceBootRetry').onclick();
    assert.equal(scripts[2].src, scripts[1].src);
    scripts[2].onload();
    assert.match(scripts[3].src, /chat-markdown/);
    assert.equal(scripts.filter(script => script.src.includes('marked')).length, 1);
});

test('script execution failure stops boot and reloads the page without exposing raw errors', () => {
    const state = boot();
    const {scripts, elements, listeners} = state;
    scripts[0].onload();
    listeners.get('error')?.({filename: `http://localhost${scripts[1].src}`, message: 'private error details'});
    scripts[1].onload(); // HTTP 200 still fires load after an evaluation error.
    assert.equal(scripts.length, 2);
    assert.equal(elements.get('workspaceBootStatus').hidden, false);
    assert.match(elements.get('workspaceBootMessage').textContent, /初始化失败/);
    assert.doesNotMatch(elements.get('workspaceBootMessage').textContent, /private/);
    assert.equal(elements.get('workspaceBootRetry').hidden, false);
    elements.get('workspaceBootRetry').onclick();
    assert.equal(state.reloads, 1);
    assert.equal(scripts.length, 2);
    assert.equal(listeners.size, 0);
});

test('unrelated window errors do not mark a module broken and handlers are cleaned up', () => {
    const {scripts, listeners, elements} = boot();
    listeners.get('error')?.({filename: 'http://localhost/unrelated.js'});
    for (let i = 0; i < scripts.length; i++) scripts[i].onload();
    assert.equal(elements.get('workspaceBootStatus').hidden, true);
    assert.equal(listeners.size, 0);
});
