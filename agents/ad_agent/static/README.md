# ad-agent web assets

The web UI is intentionally split by responsibility:

- `../templates/chat.html` contains the page structure and server entrypoint.
- `css/chat.css` contains design tokens, responsive layout, and component styles.
- `js/chat.js` contains chat, execution trace, Skills, knowledge, and blueprint interactions.

Keep provider behavior and API contracts in Python modules. The browser layer should only render
declared data and call the existing HTTP endpoints.
