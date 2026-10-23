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

# core/tests/test_outbox_retry.py

Symbols in `core/tests/test_outbox_retry.py`.

- L26 `OutboxRetryTests` (class)
- L27 `_event(self)` (method)
- L30 `test_success_marks_published(self)` (method)
- L40 `test_transient_failure_stays_pending_for_retry(self)` (method)
- L49 `test_dead_letters_after_max_attempts(self)` (method)
- L58 `test_retry_then_success_publishes(self)` (method)
- L69 `test_drain_skips_when_nats_unconfigured(self)` (method)
