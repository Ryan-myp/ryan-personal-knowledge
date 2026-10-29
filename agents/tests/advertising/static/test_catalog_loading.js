const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function environment() {
    const nodes = new Map();
    const context = {document:{getElementById(id) {
        if (!nodes.has(id)) nodes.set(id,{hidden:false,disabled:false,textContent:'',
            setAttribute() {},classList:{toggle() {}}});
        return nodes.get(id);
    }}};
    vm.createContext(context);
    vm.runInContext(fs.readFileSync(path.resolve(__dirname,
        '../../../deployments/advertising/static/js/chat-catalog-loading.js'),'utf8'),context);
    return {context,nodes};
}

test('a failed knowledge source stays visible while another source finishes successfully', () => {
    const {context,nodes} = environment();
    let retries = 0;
    const publicSource = context.beginCatalogLoad('knowledge',{retry:()=>{retries++;}});
    const managedSource = context.beginCatalogLoad('knowledge',{slot:'managed'});
    context.finishCatalogLoad(publicSource,'目录暂不可用');
    assert.equal(nodes.get('knowledgeCatalogRetry').disabled,true);
    context.finishCatalogLoad(managedSource);
    assert.match(nodes.get('knowledgeCatalogStatusMessage').textContent,/目录暂不可用/);
    assert.equal(nodes.get('knowledgeCatalogRetry').disabled,false);
    nodes.get('knowledgeCatalogRetry').onclick();
    assert.equal(retries,1);
});

test('older request completion cannot clear the loading/error state of its replacement', () => {
    const {context,nodes} = environment();
    const old = context.beginCatalogLoad('mcp');
    const current = context.beginCatalogLoad('mcp');
    context.finishCatalogLoad(old,'obsolete');
    assert.equal(context.isCurrentCatalogLoad(old),false);
    assert.match(nodes.get('mcpCatalogEmpty').textContent,/正在读取/);
    context.finishCatalogLoad(current,'current error');
    assert.doesNotMatch(nodes.get('mcpCatalogStatusMessage').textContent,/obsolete/);
});

test('a retry removes the stale error and success restores an honest empty state', () => {
    const {context,nodes} = environment();
    context.finishCatalogLoad(context.beginCatalogLoad('skills'),'offline');
    assert.match(nodes.get('skillsCatalogEmpty').textContent,/无法读取/);
    const retry = context.beginCatalogLoad('skills');
    assert.match(nodes.get('skillsCatalogEmpty').textContent,/正在读取/);
    context.finishCatalogLoad(retry);
    assert.equal(nodes.get('skillsCatalogStatus').hidden,true);
    assert.match(nodes.get('skillsCatalogEmpty').textContent,/没有匹配/);
});
