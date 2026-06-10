---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:50'
updated: '2026-06-10T20:08:50'
---

# plugins/installed/seo/services/redirects.py

Symbols in `plugins/installed/seo/services/redirects.py`.

- L13 `resolve_redirect(path: str)` (function) — Return (target_path, status_code) for `path`, or None if no alias exists.
- L37 `record_404(*, path: str, referrer: str='')` (function)
- L52 `suggest_redirect(path: str)` (function) — Suggest a live URL for a 404 path.
- L132 `refresh_404_suggestions(*, limit: int=50)` (function) — Fill in suggested_target on the top unresolved 404s.
