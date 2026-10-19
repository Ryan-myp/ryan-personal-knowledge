const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function settingsContext(location) {
    const source = path.resolve(
        __dirname,
        '../../../deployments/advertising/static/js/chat-settings.js',
    );
    const context = {
        location,
        document: { getElementById: () => null },
        console,
        Promise,
    };
    vm.runInNewContext(fs.readFileSync(source, 'utf8'), context, {
        filename: source,
    });
    return context;
}

test('secret writes allow HTTPS and local development origins only', () => {
    assert.equal(
        settingsContext({ protocol: 'https:', hostname: 'agent.example.com' })
            .isSecureSettingsOrigin(),
        true,
    );
    assert.equal(
        settingsContext({ protocol: 'http:', hostname: 'localhost' })
            .isSecureSettingsOrigin(),
        true,
    );
    assert.equal(
        settingsContext({ protocol: 'http:', hostname: '0.0.0.0' })
            .isSecureSettingsOrigin(),
        true,
    );
    assert.equal(
        settingsContext({ protocol: 'http:', hostname: '192.168.1.20' })
            .isSecureSettingsOrigin(),
        false,
    );
});
