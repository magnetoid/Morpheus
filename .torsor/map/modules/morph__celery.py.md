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

# morph/celery.py

Symbols in `morph/celery.py`.

- L123 `_on_task_failure(sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwargs)` (function) — Persist task failures into the ErrorEvent table + Redis deadletter.
- L155 `_on_task_retry(sender=None, request=None, reason=None, einfo=None, **kwargs)` (function) — A task retry is recorded while detailed capture is on (core/errors/mode.py).
- L186 `debug_task(self)` (function)
