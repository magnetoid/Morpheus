---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:50'
updated: '2026-06-10T20:08:50'
---

# plugins/installed/tracking/services/measurement_protocol.py

Symbols in `plugins/installed/tracking/services/measurement_protocol.py`.

- L45 `_endpoint(region: str)` (function)
- L49 `_new_client_id()` (function) — Synthetic GA-format client_id when we have nothing real.
- L54 `_is_duplicate(settings_row, event_name: str, transaction_id: str, client_id: str)` (function) — Look back inside the dedup window for a matching SENT row.
- L77 `send_event(*, event_name: str, params: dict[str, Any], client_id: str='', session_id: str='', user_id: str='', consent: dict[str, str] | None=None, transaction_id: str='')` (function) — Fire one GA4 event server-side. Returns the audit row.
