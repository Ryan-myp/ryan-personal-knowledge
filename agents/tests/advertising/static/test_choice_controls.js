const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function controls() {
    const context = { choiceDisplayLabel: (value, label) => label || String(value) };
    vm.runInNewContext(fs.readFileSync(path.resolve(
        __dirname, '../../../deployments/advertising/static/js/chat-choice.js',
    ), 'utf8'), context);
    return context;
}

test('multi-choice keeps provider values and searches labels or codes', () => {
    const context = controls();
    const choices = context.multiChoiceOptions([
        { value: 'US', label: '美国' }, { value: 'CN', label: '中国' },
    ], ['US']);
    assert.equal(choices[0].value, 'US');
    assert.equal(context.filterMultiChoices(choices, '美')[0].value, 'US');
    assert.equal(context.filterMultiChoices(choices, 'cn')[0].label, '中国');
    assert.equal(context.filterMultiChoices(choices, 'missing').length, 0);
});

test('multi-choice preserves zero, false and previously saved unavailable values', () => {
    const context = controls();
    const choices = context.multiChoiceOptions([0, false, 'US', 'US'], ['OLD']);
    assert.equal(choices.length, 4);
    assert.equal(choices.find(item => item.key === '0').value, 0);
    assert.equal(choices.find(item => item.key === 'false').value, false);
    assert.equal(choices.find(item => item.key === 'OLD').unavailable, true);
});
