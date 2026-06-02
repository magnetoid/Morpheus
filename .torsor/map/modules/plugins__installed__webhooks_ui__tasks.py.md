---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:53'
updated: '2026-06-02T18:07:53'
---

# plugins/installed/webhooks_ui/tasks.py

Symbols in `plugins/installed/webhooks_ui/tasks.py`.

- L21 `deliver_webhook(delivery_id: str)` (function) — Single delivery attempt. Schedules itself again on transient failure;
- L99 `replay_delivery(delivery_id: str)` (function) — Reset a failed/DLQ delivery and re-enqueue. Triggered by the
