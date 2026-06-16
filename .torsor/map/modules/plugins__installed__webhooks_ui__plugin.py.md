---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/webhooks_ui/plugin.py

Symbols in `plugins/installed/webhooks_ui/plugin.py`.

- L31 `_flatten(value)` (function) — Best-effort serializable representation of a domain object.
- L51 `_make_fanout(event_name: str)` (function) — Build a named handler closure — hook registry needs `__qualname__`.
- L63 `WebhooksUiPlugin` (class)
- L75 `ready(self)` (method)
- L90 `_fanout(event_name: str, **payload)` (method) — Find every WebhookEndpoint subscribed to `event_name` and queue.
- L125 `contribute_dashboard_pages(self)` (method)
