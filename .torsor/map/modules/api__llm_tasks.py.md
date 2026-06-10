---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:00'
updated: '2026-06-09T21:57:00'
---

# api/llm_tasks.py

Symbols in `api/llm_tasks.py`.

- L42 `_cache_key(task_id: str)` (function)
- L46 `_is_authed(request: HttpRequest)` (function) — Accept either a Bearer token OR a staff session — same rule as
- L61 `_owner_id_for(request: HttpRequest)` (function) — Stable owner identifier stored on the cache record.
- L78 `llm_task_create(request: HttpRequest)` (function) — POST /api/llm-tasks/ — queue an LLM completion, return task id.
- L130 `llm_task_status(request: HttpRequest, task_id: str)` (function) — GET /api/llm-tasks/<id>/ — poll task status + result.
