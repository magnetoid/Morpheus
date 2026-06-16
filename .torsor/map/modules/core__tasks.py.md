---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# core/tasks.py

Symbols in `core/tasks.py`.

- L22 `_canonical_payload(payload: Any)` (function) — Stable JSON representation used for signing (sorted keys, no spaces).
- L27 `compute_hmac_signature(secret: str, payload: Any)` (function) — Compute X-Morpheus-Signature for an outbound webhook payload.
- L33 `verify_hmac_signature(secret: str, payload_bytes: bytes, provided_signature: str)` (function) — Constant-time verification helper for inbound webhook receivers.
- L45 `dispatch_webhook(self, url: str, secret: str, event_name: str, payload: dict[str, Any])` (function) — POST event data to a Remote Plugin endpoint.
- L101 `_publish_to_nats_sync(event_type: str, payload: dict[str, Any])` (function) — Synchronous NATS publisher used from Celery workers.
- L150 `process_outbox(self)` (function) — Drain pending OutboxEvent rows into NATS JetStream.
- L198 `run_hook_handler_async(self, event: str, handler_path: str, kwargs: dict)` (function) — Re-invoke a hook handler from a Celery worker.
