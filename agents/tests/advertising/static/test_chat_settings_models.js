const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

class Element {
    constructor(tagName = 'div', id = '') {
        this.tagName = tagName.toUpperCase();
        this.id = id;
        this.children = [];
        this.attributes = {};
        this.className = '';
        this.textContent = '';
        this.value = '';
        this.readOnly = false;
        this.disabled = false;
    }

    append(...children) {
        this.children.push(...children);
    }

    appendChild(child) {
        this.append(child);
        return child;
    }

    addEventListener() {}

    focus() {
        this.focused = true;
    }

    replaceChildren(...children) {
        this.children = [...children];
    }

    setAttribute(name, value) {
        this.attributes[name] = value;
    }

    reset() {
        this.children = [];
    }

    get childElementCount() {
        return this.children.length;
    }
}

const elements = new Map();
for (const id of [
    'agentSettingsStatus',
    'agentModelProfileList',
    'agentMediaModelCatalog',
    'agentModelForm',
    'agentModelProfileId',
    'agentModelPurpose',
    'agentModelName',
    'agentModelId',
    'agentModelBaseUrl',
    'agentModelHint',
    'agentModelApiKey',
]) {
    elements.set(id, new Element('div', id));
}
elements.get('agentModelPurpose').value = 'chat';

const context = {
    document: {
        createElement(tagName) {
            return new Element(tagName);
        },
        getElementById(id) {
            return elements.get(id) || null;
        },
    },
};
const sourcePath = path.resolve(
    __dirname,
    '../../../deployments/advertising/static/js/chat-settings.js',
);
vm.runInNewContext(fs.readFileSync(sourcePath, 'utf8'), context, {
    filename: sourcePath,
});
vm.runInContext(`
    agentSettingsState.snapshot = {
        media_model_catalog: {
            image_generation: {
                model: 'agnes-image-2.5-flash',
                name: 'Agnes Image 2.5 Flash',
                availability: 'free',
                base_url: 'https://apihub.agnes-ai.com/v1'
            },
            video_generation: {
                model: 'agnes-video-2.5-flash',
                name: 'Agnes Video 2.5 Flash',
                availability: 'free_limited_time',
                base_url: 'https://apihub.agnes-ai.com/v1'
            }
        },
        models: {
            profiles: [{
                id: '__environment__',
                name: 'Chat',
                model: 'agnes-3.0-flash',
                purpose: 'chat',
                source: 'environment',
                active: true
            }]
        }
    };
    renderAgentModelProfiles();
`, context);

test('settings lists the separate free image and video profiles', () => {
    const catalog = elements.get('agentMediaModelCatalog');
    assert.equal(catalog.children.length, 2);
    assert.equal(
        catalog.children[0].children[0].children[0].textContent,
        'Agnes Image 2.5 Flash',
    );
    assert.equal(
        catalog.children[1].children[0].children[2].textContent,
        '免费（限时）',
    );
});

test('configured media models are not duplicated in the available-model catalog', () => {
    vm.runInContext(`
        agentSettingsState.snapshot.models.profiles = [
            {
                id: 'image-profile',
                name: 'Agnes Image 2.5 Flash',
                model: 'agnes-image-2.5-flash',
                purpose: 'image_generation',
                source: 'vault',
                active: true,
                api_key_configured: true,
                supported: true
            },
            {
                id: 'video-profile',
                name: 'Agnes Video 2.5 Flash',
                model: 'agnes-video-2.5-flash',
                purpose: 'video_generation',
                source: 'vault',
                active: true,
                api_key_configured: true,
                supported: true
            }
        ];
        renderAgentModelProfiles();
    `, context);

    const catalog = elements.get('agentMediaModelCatalog');
    assert.equal(catalog.children.length, 1);
    assert.match(catalog.children[0].textContent, /都已配置/);
});

test('available-model catalog only shows media purposes not already configured', () => {
    vm.runInContext(`
        agentSettingsState.snapshot.models.profiles = [{
            id: 'image-profile',
            name: 'Agnes Image 2.5 Flash',
            model: 'agnes-image-2.5-flash',
            purpose: 'image_generation',
            source: 'vault',
            active: true,
            api_key_configured: true,
            supported: true
        }];
        renderAgentModelProfiles();
    `, context);

    const catalog = elements.get('agentMediaModelCatalog');
    assert.equal(catalog.children.length, 1);
    assert.equal(
        catalog.children[0].children[0].children[0].textContent,
        'Agnes Video 2.5 Flash',
    );
});

test('choosing image generation locks the free model and official endpoint', () => {
    vm.runInContext("configureMediaModel('image_generation')", context);

    assert.equal(
        elements.get('agentModelId').value,
        'agnes-image-2.5-flash',
    );
    assert.equal(elements.get('agentModelId').readOnly, true);
    assert.equal(
        elements.get('agentModelBaseUrl').value,
        'https://apihub.agnes-ai.com/v1',
    );
    assert.equal(elements.get('agentModelBaseUrl').readOnly, true);
    assert.match(elements.get('agentSettingsStatus').textContent, /API Key/);
});

test('changing back to chat removes media-only model and endpoint values', () => {
    elements.get('agentModelPurpose').value = 'image_generation';
    vm.runInContext('updateAgentModelChoices()', context);
    elements.get('agentModelPurpose').value = 'chat';
    vm.runInContext('updateAgentModelChoices()', context);

    assert.equal(elements.get('agentModelId').value, '');
    assert.equal(elements.get('agentModelId').readOnly, false);
    assert.equal(elements.get('agentModelBaseUrl').value, '');
    assert.equal(elements.get('agentModelBaseUrl').readOnly, false);
});
