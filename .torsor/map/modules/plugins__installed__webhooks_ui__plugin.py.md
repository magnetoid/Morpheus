---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:53'
updated: '2026-06-02T18:07:53'
---

# plugins/installed/webhooks_ui/plugin.py

Symbols in `plugins/installed/webhooks_ui/plugin.py`.

- L30 `_flatten(value)` (function) — Best-effort serializable representation of a domain object.
- L50 `_make_fanout(event_name: str)` (function) — Build a named handler closure — hook registry needs `__qualname__`.
- L60 `WebhooksUiPlugin` (class)
- L72 `ready(self)` (method)
- L87 `_fanout(event_name: str, **payload)` (method) — Find every WebhookEndpoint subscribed to `event_name` and queue.
- L116 `contribute_dashboard_pages(self)` (method)
