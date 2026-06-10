---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:49'
updated: '2026-06-10T20:08:49'
---

# plugins/installed/admin_dashboard/views_split/home.py

Symbols in `plugins/installed/admin_dashboard/views_split/home.py`.

- L39 `_safe_block(label: str)` (function) — Swallow any exception from a dashboard tile so one broken plugin
- L51 `dashboard_home(request: HttpRequest)` (function)
- L277 `pulse_refresh(request: HttpRequest)` (function) — Force a Pulse regeneration on demand. Sync — small enough to not need a task.
- L293 `pulse_dismiss(request: HttpRequest, insight_id: str)` (function) — Mark a Pulse card read so it falls off the panel.
- L304 `_compute_activity_feed(limit: int=20)` (function) — Recent platform events as a single chronological list.
- L428 `_compute_setup_steps()` (function) — Build the first-time merchant setup checklist.
