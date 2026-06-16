---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/webhooks_ui/services.py

Symbols in `plugins/installed/webhooks_ui/services.py`.

- L13 `enqueue_delivery(*, endpoint, event_name: str, payload: dict)` (function) — Create a WebhookDelivery row and queue the celery task.
- L32 `sign_payload(secret: str, body: bytes)` (function) — Same scheme used by core.tasks.compute_hmac_signature.
- L37 `build_signed_request_body(*, event_name: str, payload: dict)` (function)
