---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/rbac/services.py

Symbols in `plugins/installed/rbac/services.py`.

- L10 `has_capability(user, capability: str, *, channel=None)` (function) — True if `user` is granted `capability` (optionally on `channel`).
- L33 `capabilities_for(user, *, channel=None)` (function) — The full set of capabilities `user` has — useful for menu visibility.
- L53 `grant(user, role_slug: str, *, channel=None, granted_by=None)` (function)
- L80 `revoke(user, role_slug: str, *, channel=None, revoked_by=None)` (function)
