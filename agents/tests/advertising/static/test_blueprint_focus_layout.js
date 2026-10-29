const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function context() {
    const state = {selected:{id:'old'}, values:{}, templates:[]};
    const ctx = {blueprintState:state, console, document:{getElementById:()=>null}};
    vm.createContext(ctx);
    vm.runInContext(fs.readFileSync(path.resolve(__dirname,
        '../../../deployments/advertising/static/js/chat-blueprint-editor.js'), 'utf8'), ctx);
    return ctx;
}

test('focus layout keeps required and invalid fields prominent, including invalid defaults', () => {
    const ctx = context();
    assert.equal(ctx.blueprintFieldIsPrimary({}, {required:true}), true);
    assert.equal(ctx.blueprintFieldIsPrimary({}, {required:false}), false);
    assert.equal(ctx.blueprintFieldIsPrimary({presentation:'derived_readonly'}, {required:true,state:'set'}), false);
    assert.equal(ctx.blueprintFieldIsPrimary({presentation:'derived_readonly'}, {state:'invalid'}), true);
});

test('stale validation cannot replace another blueprint or reset its values', async () => {
    const ctx = context(); let resolve;
    ctx.apiFetch = () => new Promise(done => { resolve=done; });
    let rendered = 0;
    for (const name of ['renderBlueprintFlowbar','renderBlueprintFields','renderBlueprintFieldNav','renderBlueprintSummary']) ctx[name]=()=>rendered++;
    const request = ctx.evaluateBlueprintDraft('campaign.name');
    ctx.blueprintState.selected = {id:'new'};
    ctx.blueprintState.values = {'campaign.name':'NEW'};
    resolve({missing_fields:[],reset_fields:['campaign.name']});
    await request;
    assert.equal(rendered,0);
    assert.equal(ctx.blueprintState.values['campaign.name'],'NEW');
});
