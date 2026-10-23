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

# core/i18n_links.py

Symbols in `core/i18n_links.py`.

- L32 `_language_routed(language: str, path: str)` (function) — Whether `/<language><path>` is a page (a route under `i18n_patterns`).
- L45 `localize_url(url: str, language: str, host: str='')` (function) — `url` in `language`'s tree when it names a language-routed page.
- L67 `localize_links(html: str, language: str, host: str='')` (function) — `html` with its internal page links moved into `language`'s tree.
- L84 `page_language(request)` (function) — The prefixed language this request is served in, or `''`.
- L96 `LocalizedLinksMiddleware` (class) — Rewrite internal links on HTML pages served under a language prefix.
- L103 `__init__(self, get_response)` (method)
- L106 `__call__(self, request)` (method)
