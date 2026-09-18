# ad-agent web assets

The web UI is split by responsibility and loaded in a stable order:

- `../templates/chat.html` contains the page shell and static workspace overlays.
- `css/chat.css` is a small stylesheet manifest; component styles live in the imported files.
- `css/chat-foundation.css` contains the base shell, tokens, navigation, and shared controls.
- `css/chat-workspaces.css` contains Skills and Blueprint workspace styles.
- `css/chat-creation.css` contains conversational creation and confirmation card styles.
- `css/chat-overrides.css` contains theme, responsive, and final product-polish overrides.
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

The scripts remain classic scripts rather than ES modules so existing inline handlers and global
actions continue to work. Keep provider behavior and API contracts in Python modules; the browser
layer only renders declared data and calls the existing HTTP endpoints.
