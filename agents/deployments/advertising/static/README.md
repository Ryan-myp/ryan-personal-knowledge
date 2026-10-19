# ad-agent web assets

The web UI is split by responsibility and loaded in a stable order:

- `../templates/chat.html` contains the page shell and static workspace overlays.
- `css/chat.css` is a small stylesheet manifest; component styles live in the imported files.
- `css/chat-foundation.css` contains the base shell, tokens, navigation, and shared controls.
- `css/chat-workspaces.css` contains Skills and Blueprint workspace styles.
- `css/chat-creation.css` contains conversational creation and confirmation card styles.
- `css/chat-overrides.css` contains theme, responsive, and final product-polish overrides.
- `css/chat-markdown.css` contains bounded message typography, code blocks, and scrollable tables.
- `js/chat.js` is the compatibility entrypoint and loads the ordered classic scripts.
- `js/chat-state.js` owns shared state and trace labels.
- `js/chat-workbench.js` owns the shared right-side artifact workspace for
  creation cards and confirmation surfaces, while trace remains a switchable
  view in the same panel.
- `js/chat-workspace.js` owns runtime mode, monitoring, schedules, memory, and popovers.
- `js/chat-knowledge.js` owns knowledge catalog, search, editing, and publication actions.
- `js/chat-trace.js` owns execution trace rendering and durable-run updates.
- `js/chat-requests.js` owns request streaming, authentication, and conversation history.
- `js/chat-blueprint-core.js` and `js/chat-blueprint-editor.js` own Blueprint data and editor UI.
- `js/chat-skills.js` owns Skills management and evaluation UI.
- `js/chat-creation.js` owns ad creation card fields, lookups, validation, and review.
- `js/chat-messages.js` owns chat rendering, send flow, and page initialization.
- `js/chat-markdown.js` renders sanitized GFM and derives plain-text conversation previews.

Markdown dependencies are pinned and served locally from `js/vendor/`:
Marked 18.1.1 (MIT) and DOMPurify 3.4.17 (Apache-2.0 OR MPL-2.0).
The unmodified npm distribution files and upstream licenses are checked in;
there is no browser CDN dependency. Markdown HTML is escaped before final
allowlist sanitization. Fenced code remains literal, and history previews use
plain text rather than injecting HTML. Tool/system records are replayed in the
execution trace, not as chat bubbles. Only the frontend rendering changes;
stored messages, provider contracts and write gates are unchanged.

Mermaid 12.2.0 Tiny (MIT) is also served locally. It is loaded only when an
assistant message contains a Mermaid code fence, initialized in strict mode,
and its SVG output is sanitized before insertion. Flowchart and sequence
diagrams are supported; unsupported syntax remains visible as source text.
Rendering is bounded to 32 diagrams per message, 12,000 source characters and
200 edges per diagram; Mermaid configuration directives remain blocked.

Run message-rendering and lookup regressions with:

```bash
node --test agents/tests/advertising/static/test_*.js
```

The scripts remain classic scripts rather than ES modules so existing inline handlers and global
actions continue to work. Keep provider behavior and API contracts in Python modules; the browser
layer only renders declared data and calls the existing HTTP endpoints.
