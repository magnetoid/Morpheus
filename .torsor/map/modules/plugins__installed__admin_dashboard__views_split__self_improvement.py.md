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

# plugins/installed/admin_dashboard/views_split/self_improvement.py

Symbols in `plugins/installed/admin_dashboard/views_split/self_improvement.py`.

- L26 `overview(request: HttpRequest)` (function) — Main /dashboard/system/self-improvement/ page.
- L101 `approve(request: HttpRequest, recommendation_id: int)` (function)
- L110 `_suppress_recommendation(rec, *, reason: str, created_by, expires_at=None)` (function) — Write si_suppression rows that actually match what the collectors emit.
- L157 `reject(request: HttpRequest, recommendation_id: int)` (function) — Reject + write si_suppression rows so the same signal doesn't come back.
- L179 `snooze(request: HttpRequest, recommendation_id: int)` (function) — Suppress for 30 days, then revisit.
