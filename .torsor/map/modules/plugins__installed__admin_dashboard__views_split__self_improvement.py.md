---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/admin_dashboard/views_split/self_improvement.py

Symbols in `plugins/installed/admin_dashboard/views_split/self_improvement.py`.

- L23 `overview(request: HttpRequest)` (function) — Main /dashboard/system/self-improvement/ page.
- L97 `approve(request: HttpRequest, recommendation_id: int)` (function)
- L108 `reject(request: HttpRequest, recommendation_id: int)` (function) — Reject + write an si_suppression row so the same fingerprint
- L133 `snooze(request: HttpRequest, recommendation_id: int)` (function) — Suppress for 30 days, then revisit.
