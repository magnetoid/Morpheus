---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# core/audit/services.py

Symbols in `core/audit/services.py`.

- L20 `record(*, event_type: str, actor: Any=None, target: str='', metadata: dict | None=None, severity: str='info', ip_address: str | None=None, request_id: str='')` (function) — Persist one audit row. Never raises (DB errors are swallowed + logged).
- L59 `record_ai_decision(*, agent: str, tool: str, run_id: str='', args: dict | None=None, output: Any=None, duration_ms: int | None=None, model: str='', provider: str='', actor: Any=None, target: str='', request_id: str='')` (function) — Persist one ``agents.decision`` audit row with full provenance.
