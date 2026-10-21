const CHAT_MEDIA_IMAGE_LIMIT = 15 * 1024 * 1024;
const CHAT_MEDIA_VIDEO_LIMIT = 50 * 1024 * 1024;
const CHAT_MEDIA_DOCUMENT_LIMIT = 20 * 1024 * 1024;
const CHAT_MEDIA_TYPES = new Set([
    'image/jpeg', 'image/png', 'image/gif', 'image/webp',
    'video/mp4', 'video/quicktime', 'video/webm',
]);
const CHAT_DOCUMENT_EXTENSIONS = new Map([
    ['.csv', 'text/csv'],
    ['.md', 'text/markdown'],
    ['.markdown', 'text/markdown'],
    ['.pdf', 'application/pdf'],
    ['.txt', 'text/plain'],
    [
        '.xlsx',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    ],
]);
let chatMediaUploading = false;
let chatMediaObserver = null;

function chatUploadMediaType(file) {
    const filename = String(file?.name || '').toLowerCase();
    const extension = filename.includes('.')
        ? `.${filename.split('.').pop()}`
        : '';
    if (CHAT_DOCUMENT_EXTENSIONS.has(extension)) {
        return CHAT_DOCUMENT_EXTENSIONS.get(extension);
    }
    return CHAT_MEDIA_TYPES.has(file?.type) ? file.type : '';
}

function chatDocumentTypeLabel(mediaType) {
    return ({
        'application/pdf': 'PDF 文档',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'Excel 工作簿',
        'text/csv': 'CSV 表格',
        'text/markdown': 'Markdown 文档',
        'text/plain': '文本文件',
    })[mediaType] || '文档附件';
}

function chatFileSizeLabel(size) {
    const bytes = Number(size);
    if (!Number.isFinite(bytes) || bytes <= 0) return '';
    if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function ensureChatMediaSession() {
    if (!sessionId) {
        sessionId = globalThis.crypto?.randomUUID?.()
            || 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, token => {
                const random = Math.floor(Math.random() * 16);
                return (token === 'x' ? random : (random & 0x3) | 0x8).toString(16);
            });
    }
    selectedConversationId = sessionId;
    return sessionId;
}

function chatMediaElement(metadata, src, { gallery = false } = {}) {
    const wrapper = document.createElement('figure');
    wrapper.className = gallery ? 'chat-media-item' : 'chat-attachment-item';

    const mediaType = String(metadata.media_type || '');
    const isVideo = mediaType.startsWith('video/');
    const isImage = mediaType.startsWith('image/');
    if (!isVideo && !isImage) {
        const preview = document.createElement('div');
        preview.className = 'chat-document-preview';
        preview.setAttribute('aria-label', chatDocumentTypeLabel(mediaType));
        const typeLabel = document.createElement('span');
        typeLabel.className = 'chat-document-type';
        typeLabel.textContent = chatDocumentTypeLabel(mediaType);
        preview.appendChild(typeLabel);
        const filename = document.createElement('span');
        filename.className = 'chat-document-filename';
        filename.textContent = String(metadata.name || metadata.filename || '文档附件');
        preview.appendChild(filename);
        const fileSize = chatFileSizeLabel(metadata.size);
        if (fileSize) {
            const sizeLabel = document.createElement('span');
            sizeLabel.className = 'chat-document-size';
            sizeLabel.textContent = fileSize;
            preview.appendChild(sizeLabel);
        }
        wrapper.appendChild(preview);
        return wrapper;
    }

    const media = isVideo
        ? document.createElement('video')
        : document.createElement('img');
    if (isVideo) {
        media.controls = true;
        media.playsInline = true;
        media.preload = 'metadata';
        if (metadata.poster) media.poster = metadata.poster;
    } else {
        media.loading = 'lazy';
        media.alt = String(metadata.name || metadata.filename || '图片素材');
    }
    media.src = src;
    media.className = 'chat-media-preview';
    if (gallery && media.tagName === 'IMG') {
        const link = document.createElement('a');
        link.href = src;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.setAttribute('aria-label', '在新标签页打开原始图片');
        link.appendChild(media);
        wrapper.appendChild(link);
    } else {
        wrapper.appendChild(media);
    }

    const caption = String(metadata.name || metadata.filename || '').trim();
    if (caption) {
        const label = document.createElement('figcaption');
        label.textContent = caption;
        wrapper.appendChild(label);
    }
    const permalink = safeRemoteChatMediaUrl(metadata.permalink_url);
    if (media instanceof HTMLVideoElement && permalink) {
        wrapper.appendChild(chatMediaExternalLink(permalink));
    }
    return wrapper;
}

function chatMediaExternalLink(url) {
    const link = document.createElement('a');
    link.className = 'chat-media-source-link';
    link.href = url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.textContent = '在平台打开视频';
    return link;
}

function chatFacebookVideoPermalink(value) {
    const raw = String(value || '').trim();
    if (!raw || raw.length > 4096 || raw.startsWith('//')) return '';
    let url;
    try {
        url = new URL(
            raw.startsWith('/') ? raw : raw,
            raw.startsWith('/') ? 'https://www.facebook.com' : undefined,
        );
    } catch (_) {
        return '';
    }
    const allowedHosts = new Set([
        'facebook.com',
        'www.facebook.com',
        'm.facebook.com',
    ]);
    if (
        url.protocol !== 'https:'
        || !allowedHosts.has(url.hostname.toLowerCase())
        || url.username
        || url.password
        || (url.port && url.port !== '443')
    ) {
        return '';
    }

    const path = url.pathname || '/';
    if (/^\/[^/]+\/videos\/\d+\/?$/.test(path) || /^\/reel\/\d+\/?$/.test(path)) {
        return `https://www.facebook.com${path}`;
    }
    if (['/watch', '/watch/', '/video.php'].includes(path)) {
        const videoId = url.searchParams.get('v') || '';
        if (/^\d{1,30}$/.test(videoId)) {
            const route = path.startsWith('/watch') ? '/watch/' : '/video.php';
            return `https://www.facebook.com${route}?v=${videoId}`;
        }
    }
    return '';
}

function chatFacebookVideoFrame(permalink) {
    const iframe = document.createElement('iframe');
    iframe.className = 'chat-media-facebook-player';
    iframe.title = 'Facebook 视频播放器';
    iframe.loading = 'lazy';
    iframe.referrerPolicy = 'strict-origin-when-cross-origin';
    iframe.allow = 'autoplay; clipboard-write; encrypted-media; picture-in-picture; web-share';
    iframe.allowFullscreen = true;
    iframe.width = '560';
    iframe.height = '315';
    iframe.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-presentation');
    iframe.setAttribute('allowfullscreen', '');
    iframe.src = (
        'https://www.facebook.com/plugins/video.php'
        + `?href=${encodeURIComponent(permalink)}&show_text=false&width=560`
    );
    return iframe;
}

function facebookVideoPermalinksFromText(content) {
    const candidates = String(content || '').match(/https?:\/\/[^\s<>"'`]+/gi) || [];
    const unique = new Set();
    candidates.forEach(candidate => {
        const cleaned = candidate.replace(/[.,;:!?)}\]，。；：！？）】]+$/u, '');
        const permalink = chatFacebookVideoPermalink(cleaned);
        if (permalink) unique.add(permalink);
    });
    return [...unique].slice(0, 3);
}

function renderFacebookVideoEmbeds(container, content, existingItems = []) {
    if (!container) return;
    const existing = new Set(
        (Array.isArray(existingItems) ? existingItems : [])
            .filter(item => item?.kind === 'video')
            .map(item => chatFacebookVideoPermalink(item.permalink_url))
            .filter(Boolean),
    );
    facebookVideoPermalinksFromText(content).forEach(permalink => {
        if (existing.has(permalink)) return;
        const wrapper = document.createElement('figure');
        wrapper.className = 'chat-media-item chat-media-facebook-embed';
        wrapper.appendChild(chatFacebookVideoFrame(permalink));
        wrapper.appendChild(chatMediaExternalLink(permalink));
        container.appendChild(wrapper);
    });
}

function chatVideoLinkFallback(item, permalink, poster) {
    const wrapper = document.createElement('figure');
    wrapper.className = 'chat-media-item';
    const facebookPermalink = chatFacebookVideoPermalink(permalink);
    if (facebookPermalink) {
        wrapper.appendChild(chatFacebookVideoFrame(facebookPermalink));
    } else if (poster) {
        const previewLink = document.createElement('a');
        previewLink.href = permalink;
        previewLink.target = '_blank';
        previewLink.rel = 'noopener noreferrer';
        previewLink.setAttribute('aria-label', '在平台打开视频');
        const preview = document.createElement('img');
        preview.className = 'chat-media-preview';
        preview.loading = 'lazy';
        preview.alt = String(item.name || '视频封面');
        preview.src = poster;
        previewLink.appendChild(preview);
        wrapper.appendChild(previewLink);
    } else {
        const unavailable = document.createElement('div');
        unavailable.className = 'chat-media-video-unavailable';
        unavailable.textContent = '此视频暂不支持内嵌播放';
        wrapper.appendChild(unavailable);
    }
    const caption = String(item.name || '').trim();
    if (caption) {
        const label = document.createElement('figcaption');
        label.textContent = caption;
        wrapper.appendChild(label);
    }
    wrapper.appendChild(chatMediaExternalLink(facebookPermalink || permalink));
    return wrapper;
}

function renderPendingChatMedia() {
    const container = document.getElementById('chatMediaPending');
    if (!container) return;
    container.replaceChildren();
    container.hidden = pendingChatAttachments.length === 0;

    pendingChatAttachments.forEach((attachment, index) => {
        const wrapper = document.createElement('div');
        wrapper.className = 'chat-media-pending-item';
        const previewUrl = chatMediaObjectUrls.get(attachment.id);
        if (
            previewUrl
            || attachment.media_type?.startsWith('text/')
            || attachment.media_type === 'application/pdf'
            || attachment.media_type
                === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ) {
            wrapper.appendChild(chatMediaElement({
                ...attachment,
                media_type: attachment.media_type,
            }, previewUrl || ''));
        }
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'chat-media-remove';
        remove.setAttribute('aria-label', `移除 ${attachment.filename}`);
        remove.title = '移除附件';
        remove.textContent = '×';
        remove.addEventListener('click', async () => {
            remove.disabled = true;
            try {
                const query = new URLSearchParams({ session_id: sessionId || '' });
                const response = await serviceFetch(
                    `/chat/media/${encodeURIComponent(attachment.id)}?${query}`,
                    { method: 'DELETE' },
                );
                if (!response.ok) throw new Error(`附件移除失败（${response.status}）`);
            } catch (error) {
                remove.disabled = false;
                addMessage(String(error?.message || error), 'agent', null, true);
                return;
            }
            pendingChatAttachments.splice(index, 1);
            const objectUrl = chatMediaObjectUrls.get(attachment.id);
            if (objectUrl) URL.revokeObjectURL(objectUrl);
            chatMediaObjectUrls.delete(attachment.id);
            renderPendingChatMedia();
        });
        wrapper.appendChild(remove);
        container.appendChild(wrapper);
    });
}

async function uploadChatMediaFiles(files) {
    if (chatMediaUploading || !files.length) return;
    if (pendingChatAttachments.length + files.length > 5) {
        addMessage('每条消息最多添加 5 个附件。', 'agent', null, true);
        return;
    }
    const accepted = [];
    for (const file of files) {
        const mediaType = chatUploadMediaType(file);
        if (!mediaType) {
            addMessage(`暂不支持 ${file.name}（${file.type || '未知格式'}）。`, 'agent', null, true);
            continue;
        }
        const sizeLimit = mediaType.startsWith('image/')
            ? CHAT_MEDIA_IMAGE_LIMIT
            : mediaType.startsWith('video/')
                ? CHAT_MEDIA_VIDEO_LIMIT
                : CHAT_MEDIA_DOCUMENT_LIMIT;
        if (!file.size || file.size > sizeLimit) {
            const limitLabel = mediaType.startsWith('image/')
                ? '15 MiB'
                : mediaType.startsWith('video/') ? '50 MiB' : '20 MiB';
            addMessage(`${file.name} 超过 ${limitLabel} 限制。`, 'agent', null, true);
            continue;
        }
        accepted.push({ file, mediaType });
    }
    if (!accepted.length) return;

    chatMediaUploading = true;
    const button = document.getElementById('chatMediaButton');
    if (button) button.disabled = true;
    try {
        const activeSessionId = ensureChatMediaSession();
        for (const { file, mediaType } of accepted) {
            const query = new URLSearchParams({
                session_id: activeSessionId,
                filename: file.name,
            });
            const response = await serviceFetch(`/chat/media?${query}`, {
                method: 'POST',
                headers: { 'Content-Type': mediaType },
                body: file,
            });
            const text = await response.text();
            let metadata = {};
            try { metadata = text ? JSON.parse(text) : {}; } catch (_) { metadata = {}; }
            if (!response.ok) {
                throw new Error(metadata.detail || `附件上传失败（${response.status}）`);
            }
            if (mediaType.startsWith('image/') || mediaType.startsWith('video/')) {
                const previewUrl = URL.createObjectURL(file);
                chatMediaObjectUrls.set(metadata.id, previewUrl);
            }
            pendingChatAttachments.push(metadata);
        }
        renderPendingChatMedia();
    } catch (error) {
        addMessage(`附件上传失败：${String(error?.message || error)}`, 'agent', null, true);
    } finally {
        chatMediaUploading = false;
        if (button) button.disabled = false;
        const input = document.getElementById('chatMediaInput');
        if (input) input.value = '';
    }
}

function handleChatMediaSelection(event) {
    const files = Array.from(event?.target?.files || []);
    void uploadChatMediaFiles(files);
}

function handleChatPaste(event) {
    const files = Array.from(event?.clipboardData?.items || [])
        .filter(item => item.kind === 'file')
        .map(item => item.getAsFile())
        .filter(Boolean);
    if (!files.length) return;
    event.preventDefault();
    void uploadChatMediaFiles(files);
}

function renderMessageAttachments(container, attachments, activeSessionId) {
    if (!Array.isArray(attachments) || !attachments.length) return;
    const gallery = document.createElement('div');
    gallery.className = 'chat-media-gallery chat-attachment-gallery';
    container.appendChild(gallery);

    attachments.slice(0, 5).forEach(attachment => {
        if (!attachment || !attachment.id) return;
        const existingUrl = chatMediaObjectUrls.get(String(attachment.id));
        if (
            attachment.media_type?.startsWith('text/')
            || attachment.media_type === 'application/pdf'
            || attachment.media_type
                === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ) {
            gallery.appendChild(chatMediaElement(attachment, ''));
            return;
        }
        if (existingUrl) {
            gallery.appendChild(chatMediaElement(attachment, existingUrl));
            return;
        }
        const placeholder = document.createElement('div');
        placeholder.className = 'chat-media-loading';
        placeholder.textContent = `加载附件：${String(attachment.filename || '媒体文件')}`;
        gallery.appendChild(placeholder);
        observeProtectedChatMedia(placeholder, attachment, activeSessionId);
    });
}

function ensureChatMediaObserver() {
    if (chatMediaObserver) return chatMediaObserver;
    chatMediaObserver = new IntersectionObserver(entries => {
        for (const entry of entries) {
            if (!entry.isIntersecting) continue;
            chatMediaObserver.unobserve(entry.target);
            if (entry.target.chatCreativeAsset) {
                void loadInternalCreativeAsset(
                    entry.target,
                    entry.target.chatCreativeAsset,
                );
            } else {
                void loadProtectedChatMedia(
                    entry.target,
                    entry.target.chatAttachment,
                    entry.target.chatSessionId,
                );
            }
        }
    }, { root: document.getElementById('chatArea'), rootMargin: '240px' });
    return chatMediaObserver;
}

function observeProtectedChatMedia(placeholder, attachment, activeSessionId) {
    ensureChatMediaObserver();
    placeholder.chatAttachment = attachment;
    placeholder.chatSessionId = activeSessionId;
    chatMediaObserver.observe(placeholder);
}

async function loadProtectedChatMedia(placeholder, attachment, activeSessionId) {
    try {
        const query = new URLSearchParams({ session_id: activeSessionId || '' });
        const response = await serviceFetch(
            `/chat/media/${encodeURIComponent(attachment.id)}?${query}`,
        );
        if (!response.ok) throw new Error('附件不可用');
        const objectUrl = URL.createObjectURL(await response.blob());
        if (!placeholder.isConnected) {
            URL.revokeObjectURL(objectUrl);
            return;
        }
        chatMediaObjectUrls.set(String(attachment.id), objectUrl);
        placeholder.replaceWith(chatMediaElement(attachment, objectUrl));
    } catch (_) {
        if (placeholder.isConnected) placeholder.textContent = '附件暂时无法加载';
    }
}

function safeRemoteChatMediaUrl(value) {
    try {
        const url = new URL(String(value || ''));
        return url.protocol === 'https:'
            && Boolean(url.hostname)
            && !url.username
            && !url.password
            && (!url.port || url.port === '443')
            ? url.href
            : '';
    } catch (_) {
        return '';
    }
}

function safeInternalCreativeAssetUrl(value) {
    const raw = String(value || '').trim();
    if (!raw || raw.length > 128 || !raw.startsWith('/') || raw.startsWith('//')) {
        return '';
    }
    try {
        const url = new URL(raw, location.origin);
        return url.origin === location.origin
            && !url.search
            && !url.hash
            && /^\/creative\/assets\/[0-9a-f]{32}$/.test(url.pathname)
            ? url.pathname
            : '';
    } catch (_) {
        return '';
    }
}

async function loadInternalCreativeAsset(placeholder, item) {
    const url = safeInternalCreativeAssetUrl(item?.url);
    if (!url) {
        if (placeholder?.isConnected) placeholder.textContent = '素材地址无效';
        return;
    }
    const cacheKey = `creative:${String(item.id || '')}`;
    const cachedUrl = chatMediaObjectUrls.get(cacheKey);
    if (cachedUrl) {
        if (placeholder?.isConnected) {
            placeholder.replaceWith(chatMediaElement({
                ...item,
                media_type: item.media_type
                    || (item.kind === 'video' ? 'video/mp4' : 'image/jpeg'),
            }, cachedUrl, { gallery: true }));
        }
        return;
    }
    try {
        const response = await serviceFetch(url);
        if (!response.ok) throw new Error('creative asset unavailable');
        const objectUrl = URL.createObjectURL(await response.blob());
        if (!placeholder?.isConnected) {
            URL.revokeObjectURL(objectUrl);
            return;
        }
        chatMediaObjectUrls.set(cacheKey, objectUrl);
        placeholder.replaceWith(chatMediaElement({
            ...item,
            media_type: item.media_type
                || (item.kind === 'video' ? 'video/mp4' : 'image/jpeg'),
        }, objectUrl, { gallery: true }));
    } catch (_) {
        if (placeholder?.isConnected) placeholder.textContent = '创意素材暂时无法加载';
    }
}

function observeInternalCreativeAsset(placeholder, item) {
    placeholder.chatCreativeAsset = item;
    ensureChatMediaObserver();
    chatMediaObserver.observe(placeholder);
}

function renderMediaGallery(container, items) {
    if (!Array.isArray(items) || !items.length) return;
    const gallery = document.createElement('div');
    gallery.className = 'chat-media-gallery';
    items.slice(0, 12).forEach(item => {
        if (!item || !['image', 'video'].includes(item.kind)) return;
        const internalUrl = safeInternalCreativeAssetUrl(item.url);
        if (internalUrl) {
            const placeholder = document.createElement('div');
            placeholder.className = 'chat-media-loading';
            placeholder.textContent = '加载创意素材…';
            gallery.appendChild(placeholder);
            observeInternalCreativeAsset(placeholder, {
                ...item,
                url: internalUrl,
            });
            return;
        }
        const url = safeRemoteChatMediaUrl(item.url);
        const permalink = item.kind === 'video'
            ? safeRemoteChatMediaUrl(item.permalink_url)
            : '';
        const poster = safeRemoteChatMediaUrl(item.poster);
        if (!url) {
            if (item.kind === 'video' && permalink) {
                gallery.appendChild(chatVideoLinkFallback(item, permalink, poster));
            }
            return;
        }
        gallery.appendChild(chatMediaElement({
            ...item,
            media_type: item.kind === 'video' ? 'video/mp4' : 'image/jpeg',
            poster,
            permalink_url: permalink,
        }, url, { gallery: true }));
    });
    if (gallery.childElementCount) container.appendChild(gallery);
}

function clearPendingChatMedia({
    revoke = true,
    deleteStored = !isSending,
} = {}) {
    const attachmentsToDelete = revoke ? [...pendingChatAttachments] : [];
    pendingChatAttachments = [];
    renderPendingChatMedia();
    if (revoke) {
        const activeSessionId = sessionId;
        if (deleteStored) {
            for (const attachment of attachmentsToDelete) {
                if (!activeSessionId) continue;
                const query = new URLSearchParams({ session_id: activeSessionId });
                void serviceFetch(
                    `/chat/media/${encodeURIComponent(attachment.id)}?${query}`,
                    { method: 'DELETE' },
                ).catch(() => {});
            }
        }
        releaseChatMediaObjectUrls();
    }
}

function releaseChatMediaObjectUrls() {
    chatMediaObserver?.disconnect();
    chatMediaObserver = null;
    for (const objectUrl of chatMediaObjectUrls.values()) {
        URL.revokeObjectURL(objectUrl);
    }
    chatMediaObjectUrls.clear();
}
