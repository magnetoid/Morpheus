---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:52'
updated: '2026-10-23T04:51:52'
rules: []
---

# plugins/installed/seo/middleware.py

Symbols in `plugins/installed/seo/middleware.py`.

- L40 `SeoRedirectMiddleware` (class) — Resolve `request.path_info` against the redirect rules before the view runs.
- L55 `__init__(self, get_response)` (method)
- L58 `__call__(self, request)` (method)
- L71 `_redirect_for(self, request, path: str)` (method) — The redirect/gone response for ``path``, or None to let the view run.
- L99 `_passthrough(self, request, path: str)` (method)
- L111 `_is_pagination_404(request)` (function) — A page number past the end of a REAL listing is not a broken address.
- L141 `_page_one_redirect(request)` (function) — 301 `?page=1` onto the clean URL.
- L155 `_seo_active()` (function)
- L164 `_split_language_prefix(path: str)` (function) — `('/fr', '/old/')` for `/fr/old/` — or `('', path)` when there is none.
- L177 `_safe_target(to_path: str, *, prefix: str, query: str)` (function) — Refuse anything that would send a visitor off-site.
- L198 `_count_hit(path: str)` (function)
