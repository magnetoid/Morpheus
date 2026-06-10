---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:49'
updated: '2026-06-10T20:08:49'
---

# core/self_improvement/heal.py

Symbols in `core/self_improvement/heal.py`.

- L29 `execute_queue()` (function) — Pick up status='approved' or 'auto_applied' rows and run them.
- L50 `run_one(rec: Any)` (function) — Walk the healing phases for one recommendation. Returns the
- L136 `_rollback(rec, healer, run_id)` (function)
- L156 `_log(rec, phase, outcome, run_id, *, details=None, duration_ms=0)` (function)
- L169 `_mark_failed(rec, reason: str)` (function)
- L179 `_ms(started)` (function)
