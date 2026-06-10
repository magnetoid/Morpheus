---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:48'
updated: '2026-06-10T20:08:48'
---

# core/audit/services.py

Symbols in `core/audit/services.py`.

- L19 `record(*, event_type: str, actor: Any=None, target: str='', metadata: Optional[dict]=None, severity: str='info', ip_address: Optional[str]=None, request_id: str='')` (function) — Persist one audit row. Never raises (DB errors are swallowed + logged).
- L52 `record_ai_decision(*, agent: str, tool: str, run_id: str='', args: Optional[dict]=None, output: Any=None, duration_ms: Optional[int]=None, model: str='', provider: str='', actor: Any=None, target: str='', request_id: str='')` (function) — Persist one ``agents.decision`` audit row with full provenance.
