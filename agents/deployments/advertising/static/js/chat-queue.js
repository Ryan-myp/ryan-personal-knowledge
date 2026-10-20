class ChatMessageQueue {
    constructor(maxSize = 10, maxTotalSize = 50) {
        const limit = Number(maxSize);
        const totalLimit = Number(maxTotalSize);
        if (
            !Number.isInteger(limit) || limit <= 0
            || !Number.isInteger(totalLimit) || totalLimit <= 0
        ) {
            throw new RangeError('queue limits must be positive integers');
        }
        this.maxSize = limit;
        this.maxTotalSize = totalLimit;
        this.sessions = new Map();
    }

    list(sessionId) {
        const key = this._sessionKey(sessionId);
        return [...(this.sessions.get(key) || [])];
    }

    size(sessionId) {
        if (sessionId !== undefined) {
            return this.list(sessionId).length;
        }
        let total = 0;
        for (const items of this.sessions.values()) total += items.length;
        return total;
    }

    enqueue(sessionId, item) {
        const key = this._sessionKey(sessionId);
        if (!item || typeof item !== 'object' || Array.isArray(item)) {
            throw new TypeError('queue item must be an object');
        }
        const items = this.sessions.get(key) || [];
        if (items.length >= this.maxSize) {
            return {
                accepted: false,
                position: items.length,
                reason: 'session_limit',
            };
        }
        if (this.size() >= this.maxTotalSize) {
            return {
                accepted: false,
                position: items.length,
                reason: 'total_limit',
            };
        }
        items.push(Object.freeze({ ...item }));
        this.sessions.set(key, items);
        return { accepted: true, position: items.length };
    }

    dequeue(sessionId) {
        const key = this._sessionKey(sessionId);
        const items = this.sessions.get(key);
        if (!items?.length) return null;
        const next = items.shift();
        if (!items.length) this.sessions.delete(key);
        return next;
    }

    remove(sessionId, itemId) {
        const key = this._sessionKey(sessionId);
        const items = this.sessions.get(key);
        if (!items) return false;
        const index = items.findIndex(item => String(item.id) === String(itemId));
        if (index < 0) return false;
        items.splice(index, 1);
        if (!items.length) this.sessions.delete(key);
        return true;
    }

    updateText(sessionId, itemId, text) {
        const key = this._sessionKey(sessionId);
        if (typeof text !== 'string') {
            throw new TypeError('queued message text must be a string');
        }
        const items = this.sessions.get(key);
        if (!items) return false;
        const index = items.findIndex(item => String(item.id) === String(itemId));
        if (index < 0) return false;

        const current = items[index];
        const requestParams = {
            ...(current.requestParams || {}),
            user_input: text,
        };
        items[index] = Object.freeze({
            ...current,
            text,
            requestParams: Object.freeze(requestParams),
        });
        return true;
    }

    _sessionKey(sessionId) {
        const key = String(sessionId || '').trim();
        if (!key) throw new TypeError('session id is required for queued messages');
        return key;
    }
}
