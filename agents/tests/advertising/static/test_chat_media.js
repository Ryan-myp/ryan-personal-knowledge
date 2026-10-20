const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

class Element {
    constructor(tagName) {
        this.tagName = tagName.toUpperCase();
        this.children = [];
        this.attributes = {};
        this.className = '';
        this.textContent = '';
        this.childElementCount = 0;
    }

    appendChild(child) {
        this.children.push(child);
        this.childElementCount = this.children.length;
        return child;
    }

    setAttribute(name, value) {
        this.attributes[name] = value;
    }

    replaceWith(replacement) {
        this.replacement = replacement;
    }
}

class VideoElement extends Element {
    constructor() {
        super('video');
    }
}

const context = {
    URL,
    HTMLVideoElement: VideoElement,
    location: { origin: 'https://agent.example' },
    serviceFetch: async () => ({
        ok: true,
        blob: async () => new Blob(['creative']),
    }),
    document: {
        createElement(tagName) {
            return tagName === 'video'
                ? new VideoElement()
                : new Element(tagName);
        },
    },
    pendingChatAttachments: [],
    chatMediaObjectUrls: new Map(),
};
const sourcePath = path.resolve(
    __dirname,
    '../../../deployments/advertising/static/js/chat-media.js',
);
vm.runInNewContext(fs.readFileSync(sourcePath, 'utf8'), context, {
    filename: sourcePath,
});

test('remote media previews accept only credential-free HTTPS URLs', () => {
    assert.equal(
        context.safeRemoteChatMediaUrl('https://cdn.example.test/a.png'),
        'https://cdn.example.test/a.png',
    );
    for (const value of [
        'javascript:alert(1)',
        'http://cdn.example.test/a.png',
        'https://user:pass@cdn.example.test/a.png',
        'https://cdn.example.test:444/a.png',
    ]) {
        assert.equal(context.safeRemoteChatMediaUrl(value), '');
    }
});

test('internal creative asset paths are exact same-origin routes', () => {
    assert.equal(
        context.safeInternalCreativeAssetUrl(
            '/creative/assets/1234567890abcdef1234567890abcdef',
        ),
        '/creative/assets/1234567890abcdef1234567890abcdef',
    );
    for (const value of [
        '//attacker.example/creative/assets/1234567890abcdef1234567890abcdef',
        '/creative/assets/1234567890abcdef1234567890abcdef/extra',
        '/creative/assets/../settings',
        '/chat/media/1234567890abcdef1234567890abcdef',
        'https://attacker.example/creative/assets/1234567890abcdef1234567890abcdef',
    ]) {
        assert.equal(context.safeInternalCreativeAssetUrl(value), '');
    }
});

test('internal creative media loads through authenticated fetch and displays inline', async () => {
    const requests = [];
    context.serviceFetch = async url => {
        requests.push(url);
        return {
            ok: true,
            blob: async () => new Blob(['creative']),
        };
    };
    context.URL.createObjectURL = () => 'blob:creative-preview';
    const placeholder = new Element('div');
    placeholder.isConnected = true;
    const item = {
        kind: 'video',
        id: '1234567890abcdef1234567890abcdef',
        name: 'Generated video',
        url: '/creative/assets/1234567890abcdef1234567890abcdef',
    };

    await context.loadInternalCreativeAsset(placeholder, item);

    assert.deepEqual(requests, [item.url]);
    const player = placeholder.replacement.children.find(
        child => child.tagName === 'VIDEO',
    );
    assert.ok(player);
    assert.equal(player.src, 'blob:creative-preview');
    assert.equal(player.controls, true);
});

test('media gallery ignores unsafe URLs and writes labels as text nodes', () => {
    const container = new Element('div');
    context.renderMediaGallery(container, [
        {
            kind: 'image',
            name: '<img src=x onerror=alert(1)>',
            url: 'javascript:alert(1)',
        },
        {
            kind: 'image',
            name: '<img src=x onerror=alert(1)>',
            url: 'https://cdn.example.test/image.png',
        },
    ]);

    assert.equal(container.children.length, 1);
    assert.equal(
        container.children[0].children[0].children[0].children[0].src,
        'https://cdn.example.test/image.png',
    );
    assert.equal(
        container.children[0].children[0].children[1].textContent,
        '<img src=x onerror=alert(1)>',
    );
});

test('video media sources render as controllable inline players', () => {
    const container = new Element('div');
    context.renderMediaGallery(container, [{
        kind: 'video',
        name: 'Demo',
        url: 'https://video.example/demo.mp4?signature=short-lived',
        poster: 'https://video.example/demo.jpg',
        permalink_url: 'https://www.facebook.com/watch/?v=video-1',
    }]);

    const figure = container.children[0].children[0];
    const player = figure.children.find(child => child.tagName === 'VIDEO');
    const openLink = figure.children.find(child => child.className === 'chat-media-source-link');
    assert.ok(player);
    assert.equal(player.src, 'https://video.example/demo.mp4?signature=short-lived');
    assert.equal(player.controls, true);
    assert.equal(player.playsInline, true);
    assert.equal(player.preload, 'metadata');
    assert.equal(player.poster, 'https://video.example/demo.jpg');
    assert.equal(openLink.href, 'https://www.facebook.com/watch/?v=video-1');
    assert.equal(openLink.textContent, '在平台打开视频');
});

test('Facebook permalink uses an embedded player without treating it as a media source', () => {
    const container = new Element('div');
    context.renderMediaGallery(container, [{
        kind: 'video',
        name: 'Restricted video',
        poster: 'https://video.example/restricted.jpg',
        permalink_url: 'https://www.facebook.com/watch/?v=2',
    }]);

    const figure = container.children[0].children[0];
    assert.equal(figure.children.some(child => child.tagName === 'VIDEO'), false);
    const iframe = figure.children.find(child => child.tagName === 'IFRAME');
    assert.ok(iframe);
    assert.equal(
        new URL(iframe.src).searchParams.get('href'),
        'https://www.facebook.com/watch/?v=2',
    );
    assert.equal(figure.children.some(child => child.tagName === 'IMG'), false);
    assert.equal(figure.children.at(-1).textContent, '在平台打开视频');
});

test('assistant text with a Facebook video URL renders one constrained player', () => {
    const container = new Element('div');
    const permalink = (
        'https://www.facebook.com/23845088583740250/videos/'
        + '3521725561330657/'
    );
    context.renderFacebookVideoEmbeds(
        container,
        `请预览：\n\`\`\`\n${permalink}\n\`\`\`\n${permalink}`,
    );

    assert.equal(container.children.length, 1);
    const figure = container.children[0];
    const iframe = figure.children.find(child => child.tagName === 'IFRAME');
    assert.ok(iframe);
    assert.equal(
        new URL(iframe.src).searchParams.get('href'),
        permalink,
    );
    assert.equal(iframe.loading, 'lazy');
    assert.equal(iframe.referrerPolicy, 'strict-origin-when-cross-origin');
    assert.match(iframe.attributes.sandbox, /allow-scripts/);
    assert.match(iframe.attributes.sandbox, /allow-presentation/);
    assert.equal(figure.children.at(-1).href, permalink);
});

test('Facebook embed rejects lookalike hosts and non-video pages', () => {
    const container = new Element('div');
    context.renderFacebookVideoEmbeds(container, [
        'https://www.facebook.com.attacker.test/123/videos/456/',
        'https://www.facebook.com/advertiser/settings/',
        'https://www.facebook.com/123/',
    ].join('\n'));

    assert.equal(container.children.length, 0);
});

test('media gallery URL and message permalink do not render the same video twice', () => {
    const container = new Element('div');
    const permalink = 'https://www.facebook.com/watch/?v=123456';
    context.renderFacebookVideoEmbeds(container, permalink, [{
        kind: 'video',
        permalink_url: permalink,
    }]);

    assert.equal(container.children.length, 0);
});
