---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:50'
updated: '2026-06-10T20:08:50'
---

# plugins/installed/rbac/services.py

Symbols in `plugins/installed/rbac/services.py`.

- L10 `has_capability(user, capability: str, *, channel=None)` (function) — True if `user` is granted `capability` (optionally on `channel`).
- L31 `capabilities_for(user, *, channel=None)` (function) — The full set of capabilities `user` has — useful for menu visibility.
- L49 `grant(user, role_slug: str, *, channel=None, granted_by=None)` (function)
- L73 `revoke(user, role_slug: str, *, channel=None, revoked_by=None)` (function)
