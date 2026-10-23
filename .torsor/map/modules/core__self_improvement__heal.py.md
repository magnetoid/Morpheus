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

# core/self_improvement/heal.py

Symbols in `core/self_improvement/heal.py`.

- L29 `execute_queue()` (function) — Pick up status='approved' or 'auto_applied' rows and run them.
- L50 `run_one(rec: Any)` (function) — Walk the healing phases for one recommendation. Returns the
- L151 `_rollback(rec, healer, run_id)` (function)
- L171 `_log(rec, phase, outcome, run_id, *, details=None, duration_ms=0)` (function)
- L184 `_mark_failed(rec, reason: str)` (function)
- L194 `_ms(started)` (function)
