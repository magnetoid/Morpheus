---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/webhooks_ui/tasks.py

Symbols in `plugins/installed/webhooks_ui/tasks.py`.

- L21 `deliver_webhook(delivery_id: str)` (function) — Single delivery attempt. Schedules itself again on transient failure;
- L121 `replay_delivery(delivery_id: str)` (function) — Reset a failed/DLQ delivery and re-enqueue. Triggered by the
