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

# plugins/installed/seo/pages/resolve.py

Symbols in `plugins/installed/seo/pages/resolve.py`.

- L130 `resolve_page(request, context=None)` (function) — Resolve the page. Never raises; worst case returns a bare static page.
- L158 `_is_error_render(context)` (function) — True while Django is rendering `404.html`.
- L174 `is_error_page(page: SeoPage)` (function) — The page Django renders for a 404 — not a page in any search sense.
- L179 `_from_hook(request, context)` (function)
- L192 `_view_name(request)` (function) — `(view_name, url_name)` of the matched route — `('', '')` when unmatched.
- L200 `_builtin(request, context)` (function)
- L264 `_finish(page: SeoPage, request, context)` (function) — Fill in whatever the source left blank, and apply path-level rules.
- L307 `_deny_before_launch(page: SeoPage)` (function) — A store that has not launched keeps every page out of the index.
- L320 `_search_query(request)` (function)
- L327 `_item_count(page: SeoPage, context)` (function) — How many things the listing shows, or None when nobody said.
- L344 `_path_of(request)` (function)
- L353 `_is_private(path: str)` (function)
- L360 `_og_type_for(kind: str)` (function)
- L368 `_clean(value)` (function)
- L374 `_attr(obj, name: str)` (function) — Objects arrive as models OR as GraphQL dicts (the PDP renders a dict).
- L383 `_title_from_object(page: SeoPage)` (function)
- L392 `_description_from_object(page: SeoPage)` (function)
- L405 `_fallback_title(page: SeoPage)` (function) — Last resort so no page ever renders untitled.
