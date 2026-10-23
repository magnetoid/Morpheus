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

# api/llm_tasks.py

Symbols in `api/llm_tasks.py`.

- L43 `_cache_key(task_id: str)` (function)
- L47 `_is_authed(request: HttpRequest)` (function) — Accept either a Bearer token OR a staff session — same rule as
- L62 `_owner_id_for(request: HttpRequest)` (function) — Stable owner identifier stored on the cache record.
- L79 `llm_task_create(request: HttpRequest)` (function) — POST /api/llm-tasks/ — queue an LLM completion, return task id.
- L131 `llm_task_status(request: HttpRequest, task_id: str)` (function) — GET /api/llm-tasks/<id>/ — poll task status + result.
