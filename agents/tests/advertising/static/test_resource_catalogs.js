const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function environment() {
    const context = {console};
    vm.createContext(context);
    vm.runInContext(fs.readFileSync(path.resolve(__dirname,
        '../../../deployments/advertising/static/js/chat-resource-catalogs.js'), 'utf8'), context);
    return context;
}

test('catalog pagination intersects search and filters and clamps a removed final page', () => {
    const {resourceCatalogPage} = environment();
    const items = Array.from({length:23},(_,i)=>({title:'报表 '+i,search:'report',filters:{source:i%2?'builtin':'managed',status:'published'}}));
    const page = resourceCatalogPage(items,{q:'REPORT',filters:{source:'managed'},page:9,limit:10});
    assert.equal(page.total,12);
    assert.equal(page.page,2);
    assert.equal(page.items.length,2);
    assert.equal(resourceCatalogPage([],{page:4,limit:20}).page,1);
    assert.equal(resourceCatalogPage(items,{q:'missing'}).total,0);
});

test('knowledge catalog merges published and managed entries without duplicates', () => {
    const {mergeKnowledgeCatalog} = environment();
    const items = mergeKnowledgeCatalog([
        {document_id:'builtin:one',title:'内置'},
        {document_id:'managed:saved',title:'已发布'},
    ],[{document_id:'saved',title:'已发布',status:'published'},{document_id:'draft',title:'草稿',status:'draft'}]);
    assert.equal(items.length,3);
    assert.equal(items.find(x=>x.document_id==='managed:saved').status,'published');
    assert.equal(items.find(x=>x.document_id==='managed:draft').status,'draft');
});

test('skill revision suggestions avoid existing versions while preserving major and minor', () => {
    const {nextSkillRevision} = environment();
    assert.equal(nextSkillRevision('growth','1.2.3',[{skill_name:'growth',version:'1.2.4'}]),'1.2.5');
    assert.equal(nextSkillRevision('growth','1.2.3-rc.1',[]),'1.2.4');
});
