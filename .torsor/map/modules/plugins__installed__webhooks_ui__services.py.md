---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:02'
updated: '2026-06-09T21:57:02'
---

# plugins/installed/webhooks_ui/services.py

Symbols in `plugins/installed/webhooks_ui/services.py`.

- L12 `enqueue_delivery(*, endpoint, event_name: str, payload: dict)` (function) — Create a WebhookDelivery row and queue the celery task.
- L27 `sign_payload(secret: str, body: bytes)` (function) — Same scheme used by core.tasks.compute_hmac_signature.
- L32 `build_signed_request_body(*, event_name: str, payload: dict)` (function)
