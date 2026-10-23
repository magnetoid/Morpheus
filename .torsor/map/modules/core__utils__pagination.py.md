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

# core/utils/pagination.py

Symbols in `core/utils/pagination.py`.

- L22 `paginate_or_404(object_list, per_page: int, request)` (function) — The requested page of `object_list`, or Http404 when it is not a page.
- L38 `page_href(request, number)` (function) — Path + query for page `number` of the listing `request` is on.
