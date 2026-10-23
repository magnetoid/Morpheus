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

# core/services/permalinks.py

Symbols in `core/services/permalinks.py`.

- L31 `PermalinkError` (class) — A merchant permalink setting is unsafe or cannot produce a URL.
- L36 `PermalinkResolver` (class)
- L40 `from_settings(cls, settings)` (method)
- L47 `path(self, kind: str, *, slug: str)` (method)
- L57 `validate_template(kind: str, template: str)` (function) — Accept only normalized local slug paths safe for SEO canonical use.
- L80 `resolver_for_settings(settings=None)` (function)
