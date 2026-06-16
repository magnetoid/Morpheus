---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/seo/services/redirects.py

Symbols in `plugins/installed/seo/services/redirects.py`.

- L14 `resolve_redirect(path: str)` (function) — Return (target_path, status_code) for `path`, or None if no alias exists.
- L38 `record_404(*, path: str, referrer: str='')` (function)
- L55 `suggest_redirect(path: str)` (function) — Suggest a live URL for a 404 path.
- L133 `refresh_404_suggestions(*, limit: int=50)` (function) — Fill in suggested_target on the top unresolved 404s.
