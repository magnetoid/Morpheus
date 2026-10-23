---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:52'
updated: '2026-10-23T04:51:52'
rules: []
---

# plugins/installed/webhooks_ui/tasks.py

Symbols in `plugins/installed/webhooks_ui/tasks.py`.

- L20 `_mark_refused(d, error)` (function) — A private or non-http(s) endpoint: the delivery fails without a retry
- L30 `deliver_webhook(delivery_id: str)` (function) — Single delivery attempt. Schedules itself again on transient failure;
- L151 `replay_delivery(delivery_id: str)` (function) — Reset a failed/DLQ delivery and re-enqueue. Triggered by the
