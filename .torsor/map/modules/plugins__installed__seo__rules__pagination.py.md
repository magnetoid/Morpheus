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

# plugins/installed/seo/rules/pagination.py

Symbols in `plugins/installed/seo/rules/pagination.py`.

- L23 `page_number(page_obj)` (function) — The 1-based number of a Django paginator page, or 0 if there isn't one.
- L31 `page_value(raw)` (function) — The page number a paginator would read from `?page=`, or 0 if it isn't one.
- L46 `page_one_redirect_target(request)` (function) — Where `?page=1` should go — or `''` when this URL is fine as it is.
- L71 `paginated_title(title: str, page_obj)` (function) — Give page 2 onwards a title of its own.
