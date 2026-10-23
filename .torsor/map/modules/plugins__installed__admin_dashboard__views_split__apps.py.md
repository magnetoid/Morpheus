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

# plugins/installed/admin_dashboard/views_split/apps.py

Symbols in `plugins/installed/admin_dashboard/views_split/apps.py`.

- L21 `apps_view(request: HttpRequest)` (function)
- L124 `apps_store_view(request: HttpRequest)` (function) — Browse + install surface for community apps.
- L221 `is_protected(name: str)` (function) — True if this app may not be disabled (soft-brick risk).
- L228 `is_system(name: str)` (function) — True if this app is never listed in the Apps catalogue.
- L236 `_toggle_plugin(request: HttpRequest)` (function) — POST handler on the apps page: flip a plugin's enabled state.
