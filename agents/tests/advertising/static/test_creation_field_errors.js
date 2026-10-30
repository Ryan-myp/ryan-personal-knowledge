const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

test('conversation fields display and clear server validation errors without remounting inputs', () => {
    let error = null;
    const control = {
        attrs: {}, setAttribute(name, value) { this.attrs[name] = value; },
        getAttribute(name) { return this.attrs[name]; },
        removeAttribute(name) { delete this.attrs[name]; },
    };
    const item = {
        classList: { toggle() {} },
        querySelector: () => error,
        querySelectorAll: () => [control],
        appendChild(node) { error = node; },
    };
    const ctx = {
        CSS: { escape: value => value },
        document: { createElement: () => ({
            setAttribute() {}, remove() { error = null; },
        }) },
    };
    vm.runInNewContext(fs.readFileSync(path.resolve(__dirname,
        '../../../deployments/advertising/static/js/chat-creation.js'), 'utf8'), ctx);
    ctx.creationCardFieldState = field => ({ visible: true, status: field.state });
    const card = { id: 'test', fields: [{
        path: 'ad.headlines', state: 'invalid', validation_errors: ['标题至少需要 3 项。'],
    }] };
    const wrapper = { querySelector: () => item };
    ctx.updateCreationCardFieldStates(wrapper, card);
    assert.equal(error?.textContent, '标题至少需要 3 项。');
    assert.equal(control.attrs['aria-invalid'], 'true');
    assert.equal(control.attrs['aria-describedby'], error.id);
    card.fields[0].state = 'set';
    card.fields[0].validation_errors = [];
    ctx.updateCreationCardFieldStates(wrapper, card);
    assert.equal(error, null);
    assert.equal(control.attrs['aria-invalid'], undefined);
});
