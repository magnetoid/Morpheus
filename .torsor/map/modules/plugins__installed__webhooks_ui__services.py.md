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

# plugins/installed/webhooks_ui/services.py

Symbols in `plugins/installed/webhooks_ui/services.py`.

- L12 `enqueue_delivery(*, endpoint, event_name: str, payload: dict)` (function) — Create a WebhookDelivery row and queue the celery task.
- L31 `sign_payload(secret: str, body: bytes)` (function) — Same scheme used by core.tasks.compute_hmac_signature.
- L36 `build_signed_request_body(*, event_name: str, payload: dict)` (function) — Core's body (core.tasks._canonical_payload): the event's payload, the
