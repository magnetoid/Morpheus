---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/agent_core/tests/test_approvals.py

Symbols in `plugins/installed/agent_core/tests/test_approvals.py`.

- L18 `ResolverTests` (class)
- L19 `setUp(self)` (method)
- L23 `_approved(self, *, args=_ARGS, decided_delta=timedelta(0), consumed=False)` (method)
- L34 `test_denies_without_any_request(self)` (method)
- L37 `test_denies_pending_request(self)` (method)
- L47 `test_approves_and_consumes(self)` (method)
- L53 `test_expired_grant_denied(self)` (method)
- L57 `test_fingerprint_mismatch_denied(self)` (method)
- L62 `test_no_run_denied(self)` (method)
- L67 `RecordPendingTests` (class)
- L68 `setUp(self)` (method)
- L71 `test_records_pending_and_pauses_run(self)` (method)
- L79 `test_idempotent_single_pending(self)` (method)
- L86 `test_no_run_is_noop(self)` (method)
