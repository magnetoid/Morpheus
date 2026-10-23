---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# core/tasks.py

Symbols in `core/tasks.py`.

- L27 `_canonical_payload(payload: Any)` (function) — Stable JSON representation used for signing (sorted keys, no spaces).
- L32 `compute_hmac_signature(secret: str, payload: Any)` (function) — Compute X-Morpheus-Signature for an outbound webhook payload.
- L38 `verify_hmac_signature(secret: str, payload_bytes: bytes, provided_signature: str)` (function) — Constant-time verification helper for inbound webhook receivers.
- L50 `dispatch_webhook(self, url: str, secret: str, event_name: str, payload: dict[str, Any])` (function) — POST event data to a Remote Plugin endpoint.
- L122 `_publish_to_nats_sync(event_type: str, payload: dict[str, Any])` (function) — Synchronous NATS publisher used from Celery workers.
- L175 `_nats_configured()` (function) — True only when NATS is actually wired up for this deployment (NATS_URL set).
- L188 `_process_outbox_event(event)` (function) — Publish a single OutboxEvent with bounded retry, in its own transaction.
- L233 `process_outbox(self)` (function) — Drain pending OutboxEvent rows into NATS JetStream.
- L274 `run_hook_handler_async(self, event: str, handler_path: str, kwargs: dict)` (function) — Re-invoke a hook handler from a Celery worker.
- L344 `check_for_updates()` (function) — Daily: fetch upstream + cache update status so dashboard surfaces can
- L365 `clear_expired_sessions()` (function) — Delete expired sessions (database-backed). Nothing ever ran Django's
